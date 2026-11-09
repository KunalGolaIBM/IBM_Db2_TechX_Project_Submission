/**
 * CarbonNova — marketplace, land registration, verification, transactions, admin (demo).
 * Demo role selection is NOT authentication. Actor identity is accepted from request
 * body/query for hackathon demonstration and must not be treated as a security boundary.
 * IBM Db2 integration: when DB2_* is configured, key workflows use real Db2 SQL/transactions.
 * LangChain framework: AI-assisted explanation/document review workflows use LangChain.
 */
import { Router } from 'express';
import { getDb, saveDb, newId, logActivity, logAudit } from '../db.js';
import { chat, isConfigured, AiError } from '../lib/nebius.js';
import { isDb2Configured } from '../lib/db2.js';
import { db2PurchaseCredits, db2InsertLandRegistration } from '../lib/db2Platform.js';
import { explainAssessmentWithLangChain, reviewDocumentsWithLangChain } from '../lib/langchainService.js';

const router = Router();

const DEMO_ACTORS = {
  seller: 'user-seller-1',
  buyer: 'user-buyer-1',
  admin: 'user-admin-1',
};

const actor = (req) => {
  const role = String(req.body?.actor_role || req.query?.actor_role || req.body?.role || req.query?.role || 'seller');
  const id = String(req.body?.actor_id || req.query?.actor_id || DEMO_ACTORS[role] || 'user-demo');
  return { actor_id: id, actor_role: ['seller','buyer','admin'].includes(role) ? role : 'demo' };
};

const requireAdmin = (req, res) => {
  const a = actor(req);
  if (a.actor_role !== 'admin') { res.status(403).json({ error: 'FORBIDDEN', message: 'Admin role required for this demo action.' }); return null; }
  return a;
};

const num = (v, d = 0) => { const n = Number(v); return Number.isFinite(n) ? n : d; };
const str = (v, max = 500) => (v == null ? '' : String(v)).trim().slice(0, max);

function ensureBalance(db, ownerId, ownerRole) {
  let b = db.credit_balances.find((x) => x.owner_id === ownerId);
  if (!b) {
    b = { id: newId('bal'), owner_id: ownerId, owner_role: ownerRole, available_credits: 0, acquired_credits: 0, listed_credits: 0, sold_credits: 0, updated_at: new Date().toISOString() };
    db.credit_balances.push(b);
  }
  return b;
}

function isPurchasable(listing, project) {
  if (!listing) return false;
  if (listing.market_status !== 'approved') return false; // admin/verification gate for marketplace
  if (listing.listing_status && listing.listing_status !== 'active') return false;
  if (project && project.admin_status && !['approved', 'verified'].includes(project.admin_status)) return false;
  if (project && project.verification_status && project.verification_status === 'rejected') return false;
  if (num(listing.quantity_available) <= 0) return false;
  return true;
}

router.get('/platform/demo-users', (req, res) => {
  const db = getDb();
  res.json({ users: db.profiles, balances: db.credit_balances });
});

router.get('/platform/overview', (req, res) => {
  const db = getDb();
  const sellers = db.profiles.filter((p) => p.role === 'seller');
  const buyers = db.profiles.filter((p) => p.role === 'buyer');
  const regs = db.land_registrations || [];
  const cprojects = db.carbon_projects || [];
  const listings = db.credit_listings || [];
  const txns = db.credit_transactions || [];
  res.json({
    overview: {
      total_registered_sellers: sellers.length,
      total_registered_buyers: buyers.length,
      total_land_projects: regs.length,
      total_submitted_projects: cprojects.filter((p) => ['submitted','pending','under_review'].includes(p.submission_status)).length,
      total_verified_projects: cprojects.filter((p) => ['approved','verified'].includes(p.admin_status)).length,
      total_rejected_projects: cprojects.filter((p) => p.admin_status === 'rejected').length,
      total_available_credits: listings.reduce((s, l) => s + (isPurchasable(l, cprojects.find(p=>p.id===l.carbon_project_id)) ? num(l.quantity_available) : 0), 0),
      total_sold_credits: txns.filter(t=>t.status==='completed').reduce((s,t)=>s+num(t.quantity),0),
      total_transactions: txns.length,
      pending_verification_requests: cprojects.filter((p)=>['submitted','pending','under_review'].includes(p.submission_status)).length + listings.filter(l=>l.market_status==='pending').length,
    },
    recent_transactions: txns.slice(0, 20),
    recent_audit: (db.audit_logs||[]).slice(0, 20),
    pending_projects: cprojects.filter((p)=>['submitted','pending','under_review'].includes(p.submission_status)).slice(0,20),
  });
});

router.get('/platform/audit', (req, res) => {
  const admin = requireAdmin(req, res); if (!admin) return;
  const db = getDb();
  res.json({ audit_logs: (db.audit_logs||[]).slice(0, 200) });
});

router.get('/platform/users', (req, res) => {
  const admin = requireAdmin(req, res); if (!admin) return;
  res.json({ users: getDb().profiles });
});

router.patch('/platform/users/:id/status', (req, res) => {
  const admin = requireAdmin(req, res); if (!admin) return;
  const db = getDb();
  const user = db.profiles.find((u)=>u.id===req.params.id);
  if (!user) return res.status(404).json({ error:'NOT_FOUND' });
  const before = { status: user.status };
  const status = str(req.body?.status, 30);
  if (!['active','approved','rejected','suspended','banned','pending'].includes(status)) return res.status(400).json({ error:'VALIDATION_ERROR', message:'Invalid status.' });
  user.status = status;
  user.updated_at = new Date().toISOString();
  const entry = logAudit({ ...admin, action:'user_status_changed', entity_type:'profile', entity_id:user.id, before, after:{ status }, reason:str(req.body?.reason, 300), source:'admin' });
  saveDb();
  res.json({ user, audit: entry });
});

router.get('/land-registrations', (req, res) => {
  const db = getDb();
  const { actor_id, actor_role } = actor(req);
  let items = db.land_registrations || [];
  if (actor_role === 'seller') items = items.filter((r)=>r.seller_id===actor_id);
  res.json({ land_registrations: items });
});

router.post('/land-registrations', (req, res) => {
  const { actor_id } = actor(req);
  const db = getDb();
  const name = str(req.body?.seller_name || req.body?.name, 120);
  const country = str(req.body?.country, 80);
  const state = str(req.body?.state, 80);
  const landArea = num(req.body?.land_area);
  if (name.length < 2 || !country || !state || !(landArea > 0)) {
    return res.status(400).json({ error:'VALIDATION_ERROR', message:'seller_name, country, state, and positive land_area are required.' });
  }
  const now = new Date().toISOString();
  const reg = {
    id: newId('land'), seller_id: actor_id,
    seller_name: name, country, state,
    district: str(req.body?.district, 80), village: str(req.body?.village || req.body?.location, 120),
    gps: req.body?.gps || null, latitude: req.body?.latitude ?? null, longitude: req.body?.longitude ?? null,
    land_area: landArea, area_unit: str(req.body?.area_unit || 'acres', 20),
    soil_type: str(req.body?.soil_type, 80), soil_health: str(req.body?.soil_health, 120),
    soil_moisture: str(req.body?.soil_moisture, 120), current_crop: str(req.body?.current_crop, 120),
    previous_crop: str(req.body?.previous_crop, 120), farming_practices: str(req.body?.farming_practices, 500),
    irrigation: str(req.body?.irrigation, 120), supporting_documents: Array.isArray(req.body?.supporting_documents) ? req.body.supporting_documents : [],
    soil_test_reports: Array.isArray(req.body?.soil_test_reports) ? req.body.soil_test_reports : [],
    sensor_data: req.body?.sensor_data || null,
    status: 'submitted', ai_assessment: null,
    created_at: now, updated_at: now,
  };
  // Demo estimated assessment (clearly labeled)
  const ha = reg.area_unit === 'hectares' ? reg.land_area : reg.land_area * 0.404686;
  reg.ai_assessment = {
    label: 'Demonstration estimate (not a certified measurement)',
    land_health_score: Math.min(95, Math.max(35, Math.round(55 + ha/20 + (reg.soil_health ? 10 : 0)))),
    estimated_soil_carbon_tco2e: Math.round(ha * 18),
    estimated_biomass_carbon_tco2e: Math.round(ha * 9),
    estimated_total_potential_tco2e: Math.round(ha * 27),
    note: 'Estimated carbon potential only. Not a certified carbon credit. Independent verification is required before any credit claim or issuance.',
    recommendations: ['Maintain soil cover and reduce tillage where feasible.', 'Document baseline soil tests and management practices.', 'Submit supporting evidence for verification review.'],
  };
  db.land_registrations.push(reg);
  logActivity({ type:'land_registered', source:'user', message:`Land registration submitted: ${reg.village || reg.state}, ${reg.country} (${reg.land_area} ${reg.area_unit}).` });
  logAudit({ actor_id, actor_role:'seller', action:'land_registration_submitted', entity_type:'land_registration', entity_id:reg.id, after:{ status:reg.status, land_area:reg.land_area }, source:'seller' });
  saveDb();
  res.status(201).json({ land_registration: reg });
});

router.get('/carbon-projects', (req, res) => {
  const db = getDb();
  const { actor_id, actor_role } = actor(req);
  let items = db.carbon_projects || [];
  if (actor_role === 'seller') items = items.filter((p)=>p.seller_id===actor_id);
  res.json({ carbon_projects: items.map(p=>({ ...p, documents: (db.project_documents||[]).filter(d=>d.carbon_project_id===p.id) })) });
});

router.post('/carbon-projects', (req, res) => {
  const { actor_id } = actor(req);
  const db = getDb();
  const landRegId = str(req.body?.land_registration_id, 100);
  const reg = db.land_registrations.find((r)=>r.id===landRegId && r.seller_id===actor_id);
  if (!reg) return res.status(400).json({ error:'VALIDATION_ERROR', message:'Valid seller land_registration_id is required.' });
  const now = new Date().toISOString();
  const cp = {
    id: newId('cproj'), seller_id: actor_id, land_registration_id: reg.id,
    project_name: str(req.body?.project_name || `${reg.current_crop || 'Land'} Carbon Project`, 140),
    country: reg.country, state: reg.state, location: reg.village || reg.district || reg.state,
    land_area: reg.land_area, land_type: str(req.body?.land_type || reg.current_crop || 'cropland', 60),
    crop_information: reg.current_crop,
    estimated_carbon_potential_tco2e: reg.ai_assessment?.estimated_total_potential_tco2e || 0,
    submission_status: 'submitted', admin_status: 'pending', verification_status: 'not_independently_verified',
    verification_standard: 'Not independently verified (demo)', methodology: 'Demonstration estimate only',
    description: str(req.body?.description, 1000), created_at: now, updated_at: now,
  };
  db.carbon_projects.push(cp);
  reg.linked_carbon_project_id = cp.id; reg.status = 'submitted_for_verification'; reg.updated_at = now;
  logAudit({ actor_id, actor_role:'seller', action:'carbon_project_submitted', entity_type:'carbon_project', entity_id:cp.id, after:{ submission_status:cp.submission_status }, source:'seller' });
  saveDb();
  res.status(201).json({ carbon_project: cp });
});

router.patch('/carbon-projects/:id/review', (req, res) => {
  const admin = requireAdmin(req, res); if (!admin) return;
  const db = getDb();
  const cp = db.carbon_projects.find((p)=>p.id===req.params.id);
  if (!cp) return res.status(404).json({ error:'NOT_FOUND' });
  const before = { admin_status: cp.admin_status, submission_status: cp.submission_status };
  const decision = str(req.body?.decision, 30); // approved|rejected|needs_info|suspended
  if (!['approved','rejected','needs_info','suspended'].includes(decision)) return res.status(400).json({ error:'VALIDATION_ERROR' });
  cp.admin_status = decision === 'needs_info' ? 'pending' : decision;
  cp.submission_status = decision === 'approved' ? 'approved' : decision === 'rejected' ? 'rejected' : 'under_review';
  cp.verification_status = decision === 'approved' ? 'approved_for_listing (demo; not independently certified)' : decision === 'rejected' ? 'rejected' : cp.verification_status;
  cp.review_reason = str(req.body?.reason, 500);
  cp.updated_at = new Date().toISOString();
  if (decision !== 'approved') {
    (db.credit_listings||[]).filter(l=>l.carbon_project_id===cp.id).forEach(l=>{ l.market_status='suspended'; l.listing_status='suspended'; l.suspension_reason = cp.review_reason || 'Project not approved for trading.'; });
  }
  logAudit({ ...admin, action:`carbon_project_${decision}`, entity_type:'carbon_project', entity_id:cp.id, before, after:{ admin_status:cp.admin_status, submission_status:cp.submission_status }, reason:cp.review_reason, source:'admin' });
  saveDb();
  res.json({ carbon_project: cp });
});

router.get('/marketplace/listings', (req, res) => {
  const db = getDb();
  const { actor_id, actor_role } = actor(req);
  let listings = (db.credit_listings||[]).map((l) => {
    const project = (db.carbon_projects||[]).find(p=>p.id===l.carbon_project_id) || null;
    const seller = (db.profiles||[]).find(p=>p.id===l.seller_id) || null;
    const docs = (db.project_documents||[]).filter(d=>d.carbon_project_id===l.carbon_project_id);
    return { ...l, project, seller: seller ? { id:seller.id, full_name:seller.full_name, organization:seller.organization, status:seller.status } : null, documents: docs, purchasable: isPurchasable(l, project) };
  });
  if (actor_role === 'seller') listings = listings.filter(l=>l.seller_id===actor_id);
  if (actor_role === 'buyer') listings = listings.filter(l=>l.market_status==='approved' && l.listing_status!=='suspended');
  // filters
  const q = str(req.query?.q, 120).toLowerCase();
  if (q) listings = listings.filter(l => JSON.stringify([l.project_name,l.country,l.state,l.project?.project_name]).toLowerCase().includes(q));
  if (req.query?.country) listings = listings.filter(l=>str(l.country).toLowerCase()===str(req.query.country).toLowerCase());
  if (req.query?.state) listings = listings.filter(l=>str(l.state).toLowerCase().includes(str(req.query.state).toLowerCase()));
  if (req.query?.project_type) listings = listings.filter(l=>str(l.project_type||l.land_type).toLowerCase()===str(req.query.project_type).toLowerCase());
  if (req.query?.verification_status) listings = listings.filter(l=>str(l.verification_status).toLowerCase().includes(str(req.query.verification_status).toLowerCase()));
  res.json({ listings });
});

router.post('/marketplace/listings', (req, res) => {
  const { actor_id } = actor(req);
  const db = getDb();
  const cp = db.carbon_projects.find(p=>p.id===str(req.body?.carbon_project_id,100) && p.seller_id===actor_id);
  if (!cp) return res.status(400).json({ error:'VALIDATION_ERROR', message:'Approved carbon project owned by seller is required.' });
  if (!['approved','verified'].includes(cp.admin_status)) return res.status(400).json({ error:'NOT_ALLOWED', message:'Only admin-approved projects can be listed. Estimated potential is not a tradable credit until approved.' });
  const qty = num(req.body?.quantity);
  const price = num(req.body?.price_per_credit);
  if (!(qty > 0) || !(price >= 0)) return res.status(400).json({ error:'VALIDATION_ERROR', message:'Positive quantity and valid price are required.' });
  const now = new Date().toISOString();
  const listing = {
    id: newId('lst'), carbon_project_id: cp.id, seller_id: actor_id,
    project_name: cp.project_name, country: cp.country, state: cp.state, location: cp.location,
    land_type: cp.land_type, project_type: str(req.body?.project_type || cp.land_type, 60),
    crop_information: cp.crop_information, quantity_total: qty, quantity_available: qty,
    price_per_credit: price, currency: 'USD', quality_tier: str(req.body?.quality_tier || 'pending_review', 40),
    quality_assessment: req.body?.quality_assessment || { additionality:'Not assessed', permanence:'Not assessed', leakage_risk:'Not assessed', monitoring_methodology:cp.methodology, verification_standard:cp.verification_status, transparency:'Pending admin review', documentation:'See project documents', vintage_year:String(new Date().getFullYear()), co_benefits:[] },
    verification_status: cp.verification_status, market_status: 'pending', listing_status: 'pending_review',
    description: str(req.body?.description || cp.description, 1000), created_at: now, updated_at: now,
  };
  db.credit_listings.push(listing);
  logAudit({ actor_id, actor_role:'seller', action:'listing_submitted', entity_type:'credit_listing', entity_id:listing.id, after:{ quantity:qty, market_status:listing.market_status }, source:'seller' });
  saveDb();
  res.status(201).json({ listing });
});

router.patch('/marketplace/listings/:id/review', (req, res) => {
  const admin = requireAdmin(req, res); if (!admin) return;
  const db = getDb();
  const listing = db.credit_listings.find(l=>l.id===req.params.id);
  if (!listing) return res.status(404).json({ error:'NOT_FOUND' });
  const before = { market_status: listing.market_status, listing_status: listing.listing_status };
  const decision = str(req.body?.decision, 30);
  if (!['approved','rejected','suspended'].includes(decision)) return res.status(400).json({ error:'VALIDATION_ERROR' });
  listing.market_status = decision;
  listing.listing_status = decision === 'approved' ? 'active' : decision;
  listing.review_reason = str(req.body?.reason, 500);
  listing.updated_at = new Date().toISOString();
  logAudit({ ...admin, action:`listing_${decision}`, entity_type:'credit_listing', entity_id:listing.id, before, after:{ market_status:listing.market_status }, reason:listing.review_reason, source:'admin' });
  saveDb();
  res.json({ listing });
});

router.post('/marketplace/purchase', async (req, res) => {
  const { actor_id, actor_role } = actor(req);
  if (actor_role !== 'buyer') return res.status(403).json({ error:'FORBIDDEN', message:'Buyer role required for demo purchase.' });
  const listingId = str(req.body?.listing_id, 100);
  const quantity = num(req.body?.quantity);
  if (!(quantity > 0)) return res.status(400).json({ error:'VALIDATION_ERROR', message:'Positive quantity required.' });
  // Genuine IBM Db2 transactional purchase workflow (preferred when configured)
  if (isDb2Configured()) {
    try {
      const result = await db2PurchaseCredits({ listingId, buyerId: actor_id, quantity });
      logActivity({ type:'transaction', source:'ibm_db2', message:`Db2 purchase completed: ${quantity} credits from listing ${listingId}.` });
      return res.status(201).json(result);
    } catch (e) {
      return res.status(e.status || 500).json({ error: e.code || 'DB2_PURCHASE_ERROR', message: String(e.message || e), source: 'ibm_db2' });
    }
  }
  const db = getDb();
  if (!(quantity > 0) || !Number.isInteger(quantity) && quantity !== Math.floor(quantity)) {
    // allow decimals? keep simple integer credits for demo
  }
  if (!(quantity > 0)) return res.status(400).json({ error:'VALIDATION_ERROR', message:'Positive quantity required.' });
  const listing = db.credit_listings.find(l=>l.id===listingId);
  const project = listing ? db.carbon_projects.find(p=>p.id===listing.carbon_project_id) : null;
  if (!listing) return res.status(404).json({ error:'NOT_FOUND', message:'Listing not found.' });
  if (!isPurchasable(listing, project)) return res.status(409).json({ error:'NOT_AVAILABLE', message:'This listing is not available for purchase (not approved, suspended, or unavailable).' });
  if (listing.seller_id === actor_id) return res.status(400).json({ error:'INVALID', message:'Seller cannot purchase own listing.' });
  if (quantity > num(listing.quantity_available)) return res.status(409).json({ error:'INSUFFICIENT_CREDITS', message:`Cannot purchase ${quantity}. Only ${listing.quantity_available} credits available.` });
  // allocate
  const sellerBal = ensureBalance(db, listing.seller_id, 'seller');
  const buyerBal = ensureBalance(db, actor_id, 'buyer');
  const before = { listing_available: listing.quantity_available, seller_available: sellerBal.available_credits, buyer_acquired: buyerBal.acquired_credits };
  listing.quantity_available = Math.round((num(listing.quantity_available) - quantity) * 1000) / 1000;
  if (listing.quantity_available < 0) { listing.quantity_available = before.listing_available; return res.status(409).json({ error:'INSUFFICIENT_CREDITS' }); }
  listing.quantity_sold = Math.round((num(listing.quantity_sold) + quantity) * 1000) / 1000;
  if (listing.quantity_available === 0) listing.listing_status = 'sold_out';
  sellerBal.available_credits = Math.round((num(sellerBal.available_credits) - quantity) * 1000) / 1000;
  sellerBal.sold_credits = Math.round((num(sellerBal.sold_credits) + quantity) * 1000) / 1000;
  buyerBal.acquired_credits = Math.round((num(buyerBal.acquired_credits) + quantity) * 1000) / 1000;
  if (sellerBal.available_credits < 0) { // rollback defensive
    Object.assign(listing, { quantity_available: before.listing_available, quantity_sold: num(listing.quantity_sold)-quantity });
    Object.assign(sellerBal, { available_credits: before.seller_available });
    Object.assign(buyerBal, { acquired_credits: before.buyer_acquired });
    return res.status(409).json({ error:'LEDGER_ERROR', message:'Credit allocation could not be completed safely.' });
  }
  const now = new Date().toISOString();
  sellerBal.updated_at = buyerBal.updated_at = listing.updated_at = now;
  const txn = {
    id: newId('txn'), listing_id: listing.id, carbon_project_id: listing.carbon_project_id,
    seller_id: listing.seller_id, buyer_id: actor_id, project_name: listing.project_name,
    quantity, price_per_credit: listing.price_per_credit, currency: listing.currency || 'USD',
    total_amount: Math.round(quantity * num(listing.price_per_credit) * 100) / 100,
    status: 'completed', payment_mode: 'simulated_demonstration', created_at: now,
  };
  db.credit_transactions.unshift(txn);
  logAudit({ actor_id, actor_role:'buyer', action:'credit_purchase_completed', entity_type:'credit_transaction', entity_id:txn.id, before, after:{ listing_available: listing.quantity_available, seller_available: sellerBal.available_credits, buyer_acquired: buyerBal.acquired_credits, quantity }, source:'buyer' });
  logActivity({ type:'transaction', source:'marketplace', message:`Demo purchase: ${quantity} credits from "${listing.project_name}". Seller balance updated; buyer portfolio updated.` });
  saveDb();
  res.status(201).json({ transaction: txn, listing, balances: { seller: sellerBal, buyer: buyerBal } });
});

router.get('/marketplace/transactions', (req, res) => {
  const db = getDb();
  const { actor_id, actor_role } = actor(req);
  let items = db.credit_transactions || [];
  if (actor_role === 'seller') items = items.filter(t=>t.seller_id===actor_id);
  if (actor_role === 'buyer') items = items.filter(t=>t.buyer_id===actor_id);
  res.json({ transactions: items });
});

router.get('/marketplace/documents', (req, res) => {
  const db = getDb();
  const projectId = str(req.query?.carbon_project_id, 100);
  let docs = db.project_documents || [];
  if (projectId) docs = docs.filter(d=>d.carbon_project_id===projectId);
  res.json({ documents: docs });
});

router.post('/marketplace/documents/review', async (req, res) => {
  const db = getDb();
  const projectId = str(req.body?.carbon_project_id, 100);
  const project = db.carbon_projects.find(p=>p.id===projectId);
  const docs = (db.project_documents||[]).filter(d=>d.carbon_project_id===projectId);
  const findings = [];
  if (!project) return res.status(404).json({ error:'NOT_FOUND' });
  if (!docs.length) findings.push({ type:'missing', severity:'high', message:'No supporting documents uploaded for this project.' });
  const required = ['project_document','monitoring_report','methodology'];
  required.forEach(t=>{ if (!docs.some(d=>String(d.doc_type).includes(t.split('_')[0]))) findings.push({ type:'missing', severity:'medium', message:`Potentially missing document category: ${t}.` }); });
  if (project.verification_status && String(project.verification_status).toLowerCase().includes('not independently')) findings.push({ type:'unsupported_claim_risk', severity:'info', message:'Project is marked as not independently verified. Treat credits as demonstration/pending verification.' });
  let ai_summary = null;
  if (isConfigured()) {
    try {
      const r = await chat([
        { role:'system', content:'You assist with document consistency checks for a carbon project demo. You are NOT an official certifier. Identify missing/inconsistent/unsupported claims based only on provided metadata. Be factual and cautious.' },
        { role:'user', content:`Project: ${JSON.stringify({ name:project.project_name, country:project.country, state:project.state, status:project.admin_status, verification_status:project.verification_status, methodology:project.methodology, estimated_potential:project.estimated_carbon_potential_tco2e })}\nDocuments metadata: ${JSON.stringify(docs)}\nHeuristic findings: ${JSON.stringify(findings)}\nProvide a short verification summary with evidence and risks.` }
      ], { temperature: 0.2, maxTokens: 500 });
      ai_summary = r.content;
    } catch (e) { if (!(e instanceof AiError)) console.warn(e); }
  }
  res.json({ project_id: projectId, findings, ai_summary, disclaimer:'AI-assisted document review is not official certification, validation, or legal verification.' });
});

router.get('/admin/land-registrations', (req, res) => {
  const admin = requireAdmin(req, res); if (!admin) return;
  res.json({ land_registrations: getDb().land_registrations || [] });
});

router.get('/marketplace/balances', (req, res) => {
  const db = getDb();
  const { actor_id, actor_role } = actor(req);
  if (actor_role === 'admin') return res.json({ balances: db.credit_balances || [] });
  res.json({ balance: ensureBalance(db, actor_id, actor_role), balances: (db.credit_balances||[]).filter(b=>b.owner_id===actor_id) });
});

// LangChain framework workflow (genuine integration): grounded assessment explanation
router.post('/ai/langchain/explain-assessment', async (req, res) => {
  try {
    const db = getDb();
    const landId = str(req.body?.land_registration_id, 100);
    const land = db.land_registrations.find((r) => r.id === landId) || req.body?.land || null;
    const project = req.body?.carbon_project_id ? db.carbon_projects.find((p) => p.id === req.body.carbon_project_id) : null;
    const result = await explainAssessmentWithLangChain({ land, assessment: land?.ai_assessment, project });
    if (!result.ok) return res.status(503).json(result);
    res.json(result);
  } catch (e) {
    res.status(500).json({ ok: false, error: String(e && e.message || e) });
  }
});

// LangChain framework workflow: document review
router.post('/ai/langchain/review-documents', async (req, res) => {
  try {
    const db = getDb();
    const projectId = str(req.body?.carbon_project_id, 100);
    const project = db.carbon_projects.find((p) => p.id === projectId);
    if (!project) return res.status(404).json({ ok: false, error: 'Project not found.' });
    const documents = (db.project_documents || []).filter((d) => d.carbon_project_id === projectId);
    const findings = [];
    if (!documents.length) findings.push({ type: 'missing', severity: 'high', message: 'No supporting documents uploaded.' });
    const result = await reviewDocumentsWithLangChain({ project, documents, findings });
    if (!result.ok) return res.status(503).json(result);
    res.json({ ...result, project_id: projectId, findings });
  } catch (e) {
    res.status(500).json({ ok: false, error: String(e && e.message || e) });
  }
});

export default router;
