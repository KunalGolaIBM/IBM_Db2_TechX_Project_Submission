/**
 * Db2-backed operations for critical CarbonNova workflows (genuine Db2 SQL/transactions).
 */
import { withTransaction, exec, isDb2Configured } from './db2.js';
import { newId } from '../db.js';

const asNum = (v, d=0) => { const n=Number(v); return Number.isFinite(n)?n:d; };

export async function db2PurchaseCredits({ listingId, buyerId, quantity }) {
  if (!isDb2Configured()) throw Object.assign(new Error('IBM Db2 is not configured.'), { status: 503 });
  if (!(asNum(quantity) > 0)) throw Object.assign(new Error('Positive quantity required.'), { status: 400 });
  return await withTransaction(async (tx) => {
    const listings = await tx.query('SELECT ID, CARBON_PROJECT_ID, SELLER_ID, PROJECT_NAME, QUANTITY_AVAILABLE, PRICE_PER_CREDIT, CURRENCY, MARKET_STATUS, LISTING_STATUS FROM CN_CREDIT_LISTINGS WHERE ID = ? FOR UPDATE', [listingId]);
    const l = Array.isArray(listings) ? listings[0] : listings;
    if (!l) throw Object.assign(new Error('Listing not found.'), { status: 404 });
    const market = l.MARKET_STATUS || l.market_status;
    const avail = asNum(l.QUANTITY_AVAILABLE ?? l.quantity_available);
    if (String(market).toLowerCase() !== 'approved') throw Object.assign(new Error('Listing is not approved for purchase.'), { status: 409 });
    if (quantity > avail) throw Object.assign(new Error(`Insufficient credits. Available: ${avail}`), { status: 409 });
    const sellerId = l.SELLER_ID || l.seller_id;
    if (sellerId === buyerId) throw Object.assign(new Error('Seller cannot purchase own listing.'), { status: 400 });
    const projectId = l.CARBON_PROJECT_ID || l.carbon_project_id;
    const price = asNum(l.PRICE_PER_CREDIT ?? l.price_per_credit);
    const total = Math.round(quantity * price * 100) / 100;
    const newAvail = Math.round((avail - quantity) * 1000) / 1000;
    await tx.query('UPDATE CN_CREDIT_LISTINGS SET QUANTITY_AVAILABLE = ?, QUANTITY_SOLD = COALESCE(QUANTITY_SOLD,0) + ?, LISTING_STATUS = ?, UPDATED_AT = CURRENT TIMESTAMP WHERE ID = ?', [newAvail, quantity, newAvail === 0 ? 'sold_out' : 'active', listingId]);
    await tx.query('MERGE INTO CN_CREDIT_BALANCES t USING (SELECT ? AS OWNER_ID, ? AS OWNER_ROLE, CAST(? AS DOUBLE) AS DQ FROM SYSIBM.SYSDUMMY1) s ON (t.OWNER_ID = s.OWNER_ID) WHEN MATCHED THEN UPDATE SET AVAILABLE_CREDITS = CASE WHEN COALESCE(t.AVAILABLE_CREDITS,0)-s.DQ < 0 THEN 0 ELSE COALESCE(t.AVAILABLE_CREDITS,0)-s.DQ END, SOLD_CREDITS = COALESCE(t.SOLD_CREDITS,0)+s.DQ, UPDATED_AT=CURRENT TIMESTAMP WHEN NOT MATCHED THEN INSERT (OWNER_ID, OWNER_ROLE, AVAILABLE_CREDITS, ACQUIRED_CREDITS, SOLD_CREDITS, UPDATED_AT) VALUES (s.OWNER_ID, s.OWNER_ROLE, 0, 0, s.DQ, CURRENT TIMESTAMP)', [sellerId, 'seller', quantity]);
    await tx.query('MERGE INTO CN_CREDIT_BALANCES t USING (SELECT ? AS OWNER_ID, ? AS OWNER_ROLE, CAST(? AS DOUBLE) AS DQ FROM SYSIBM.SYSDUMMY1) s ON (t.OWNER_ID = s.OWNER_ID) WHEN MATCHED THEN UPDATE SET ACQUIRED_CREDITS = COALESCE(t.ACQUIRED_CREDITS,0)+s.DQ, UPDATED_AT=CURRENT TIMESTAMP WHEN NOT MATCHED THEN INSERT (OWNER_ID, OWNER_ROLE, AVAILABLE_CREDITS, ACQUIRED_CREDITS, SOLD_CREDITS, UPDATED_AT) VALUES (s.OWNER_ID, s.OWNER_ROLE, 0, s.DQ, 0, CURRENT TIMESTAMP)', [buyerId, 'buyer', quantity]);
    const txnId = newId('txn');
    await tx.query('INSERT INTO CN_CREDIT_TRANSACTIONS (ID, LISTING_ID, CARBON_PROJECT_ID, SELLER_ID, BUYER_ID, PROJECT_NAME, QUANTITY, PRICE_PER_CREDIT, CURRENCY, TOTAL_AMOUNT, STATUS, PAYMENT_MODE, CREATED_AT) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT TIMESTAMP)', [txnId, listingId, projectId, sellerId, buyerId, l.PROJECT_NAME || l.project_name, quantity, price, l.CURRENCY || l.currency || 'USD', total, 'completed', 'simulated_demonstration']);
    await tx.query('INSERT INTO CN_AUDIT_LOGS (ID, ACTOR_ID, ACTOR_ROLE, ACTION, ENTITY_TYPE, ENTITY_ID, AFTER_JSON, SOURCE, CREATED_AT) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT TIMESTAMP)', [newId('audit'), buyerId, 'buyer', 'credit_purchase_completed_db2', 'credit_transaction', txnId, JSON.stringify({ listingId, quantity, total, listing_available: newAvail }), 'db2']);
    return { ok: true, source: 'ibm_db2', transaction: { id: txnId, listing_id: listingId, carbon_project_id: projectId, seller_id: sellerId, buyer_id: buyerId, project_name: l.PROJECT_NAME || l.project_name, quantity, price_per_credit: price, currency: l.CURRENCY || 'USD', total_amount: total, status: 'completed', payment_mode: 'simulated_demonstration' }, listing: { id: listingId, quantity_available: newAvail } };
  });
}

export async function db2InsertLandRegistration(row) {
  if (!isDb2Configured()) throw Object.assign(new Error('IBM Db2 is not configured.'), { status: 503 });
  await exec(`INSERT INTO CN_LAND_REGISTRATIONS (ID, SELLER_ID, SELLER_NAME, COUNTRY, STATE, DISTRICT, VILLAGE, LATITUDE, LONGITUDE, LAND_AREA, AREA_UNIT, SOIL_TYPE, CURRENT_CROP, STATUS, ASSESSMENT_SUMMARY, RAW_JSON, CREATED_AT, UPDATED_AT) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT TIMESTAMP, CURRENT TIMESTAMP)`,
    [row.id, row.seller_id, row.seller_name, row.country, row.state, row.district, row.village, row.latitude, row.longitude, row.land_area, row.area_unit, row.soil_type, row.current_crop, row.status, row.assessment_summary, row.raw_json]);
  await exec(`INSERT INTO CN_LAND_ASSESSMENTS (ID, LAND_REGISTRATION_ID, SELLER_ID, ASSESSMENT_TYPE, RESULT_JSON, IS_ESTIMATE, CREATED_AT) VALUES (?, ?, ?, ?, ?, 1, CURRENT TIMESTAMP)`,
    [newId('asmt'), row.id, row.seller_id, 'demo_estimate', row.assessment_summary]);
  return { ok: true, source: 'ibm_db2' };
}
