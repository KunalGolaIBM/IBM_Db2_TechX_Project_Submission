/**
 * CarbonNova — demo seed data
 * Seeds monitoring data + marketplace/governance demo records.
 * Seeded sensor/market values are SIMULATED/DEMONSTRATION data unless explicitly labeled otherwise.
 */
import { getDb, saveDb, logActivity, logAudit } from './db.js';
import { simulateSeries } from './lib/simulator.js';

export const DEMO_OWNER = 'user-1';

const SEED_PROJECTS = [
  { id: 'proj-sahyadri', owner_id: DEMO_OWNER, name: 'Sahyadri Agroforestry Reserve', land_type: 'agroforestry', area_acres: 450, location: 'Pune, Maharashtra, India', latitude: 18.5204, longitude: 73.8567, status: 'active', description: 'Mixed-species agroforestry. Sensor readings are SIMULATED demo data.', created_at: '2025-11-15T00:00:00.000Z' },
  { id: 'proj-vidarbha', owner_id: DEMO_OWNER, name: 'Vidarbha Regenerative Cropland', land_type: 'cropland', area_acres: 120, location: 'Nagpur, Maharashtra, India', latitude: 21.1458, longitude: 79.0882, status: 'active', description: 'Regenerative cropland. Baseline soil sampling pending; sensor readings SIMULATED.', created_at: '2026-01-10T00:00:00.000Z' },
  { id: 'proj-coastal', owner_id: DEMO_OWNER, name: 'Coastal Mangrove Watch (Pilot)', land_type: 'mangrove', area_acres: 80, location: 'Ratnagiri, Maharashtra, India', latitude: 16.9902, longitude: 73.312, status: 'paused', description: 'Pilot monitoring paused; historic SIMULATED readings retained.', created_at: '2025-06-20T00:00:00.000Z' },
];

const SEED_DEVICES = [
  { id: 'dev-sahyadri-1', device_token: 'tok-sahyadri-demo-001', project_id: 'proj-sahyadri', name: 'Sahyadri Node A', type: 'esp32', data_source: 'simulated', is_simulated: true, battery_pct: 84, created_at: '2025-11-16T00:00:00.000Z' },
  { id: 'dev-vidarbha-1', device_token: 'tok-vidarbha-demo-002', project_id: 'proj-vidarbha', name: 'Vidarbha Node A', type: 'esp32', data_source: 'simulated', is_simulated: true, battery_pct: 61, created_at: '2026-01-11T00:00:00.000Z' },
  { id: 'dev-coastal-1', device_token: 'tok-coastal-demo-003', project_id: 'proj-coastal', name: 'Coastal Node A', type: 'esp32', data_source: 'simulated', is_simulated: true, battery_pct: 12, created_at: '2025-06-21T00:00:00.000Z' },
];

let readingSeq = 0;
function makeReading(deviceId, project, r) {
  readingSeq += 1;
  return { id: `rdg_seed_${readingSeq}`, device_id: deviceId, project_id: project.id, recorded_at: r.recorded_at, data_source: r.data_source, is_simulated: r.is_simulated, values: r.values };
}

function seedPlatformDemoData(db, { force = false } = {}) {
  if (!force && (db.carbon_projects?.length || db.credit_listings?.length)) return;
  const now = new Date().toISOString();
  db.profiles = [
    { id:'user-seller-1', role:'seller', full_name:'Asha Patel', email:'asha@seller.demo', organization:'Green Valley Cooperative', country:'India', state:'Maharashtra', status:'approved', avatar:'https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=256', created_at:now },
    { id:'user-seller-2', role:'seller', full_name:'Carlos Mendes', email:'carlos@seller.demo', organization:'Cerrado Regenerative Group', country:'Brazil', state:'Mato Grosso', status:'approved', created_at:now },
    { id:'user-seller-3', role:'seller', full_name:'Mary Wanjiku', email:'mary@seller.demo', organization:'Highland Soil Farmers', country:'Kenya', state:'Nakuru County', status:'pending', created_at:now },
    { id:'user-buyer-1', role:'buyer', full_name:'Jordan Lee', email:'jordan@buyer.demo', organization:'Northwind Climate Fund', country:'United States', state:'California', status:'approved', created_at:now },
    { id:'user-buyer-2', role:'buyer', full_name:'Sophie Müller', email:'sophie@buyer.demo', organization:'Alpine Net Zero GmbH', country:'Germany', state:'Bavaria', status:'approved', created_at:now },
    { id:'user-admin-1', role:'admin', full_name:'Platform Admin', email:'admin@carbonnova.demo', organization:'CarbonNova', country:'Global', state:'N/A', status:'approved', created_at:now },
  ];

  db.land_registrations = [
    { id:'land-1000', seller_id:'user-seller-1', seller_name:'Asha Patel', country:'India', state:'Maharashtra', district:'Pune', village:'Mulshi', latitude:18.51, longitude:73.62, land_area:200, area_unit:'acres', soil_type:'Loam', soil_health:'Good (demo)', soil_moisture:'Moderate (demo)', current_crop:'Agroforestry', previous_crop:'Mixed crops', farming_practices:'Cover crops, reduced tillage', irrigation:'Rainfed + drip', supporting_documents:[{name:'land-record-demo.pdf',type:'land_record',status:'uploaded_demo'}], soil_test_reports:[{name:'soil-test-demo.pdf',type:'soil_test',status:'uploaded_demo'}], sensor_data:'SIMULATED node summary available', status:'verified_demo', ai_assessment:{ label:'Demonstration estimate (not a certified measurement)', land_health_score:78, estimated_soil_carbon_tco2e:1458, estimated_biomass_carbon_tco2e:729, estimated_total_potential_tco2e:2187, note:'Estimated potential only. Not a certified carbon credit.', recommendations:['Maintain soil cover.','Provide independent verification evidence.'] }, linked_carbon_project_id:'cproj-1000', created_at:now, updated_at:now },
    { id:'land-brazil', seller_id:'user-seller-2', seller_name:'Carlos Mendes', country:'Brazil', state:'Mato Grosso', district:'Sinop', village:'Rural zone', latitude:-11.86, longitude:-55.51, land_area:500, area_unit:'hectares', soil_type:'Oxisol', soil_health:'Moderate (demo)', soil_moisture:'Seasonal (demo)', current_crop:'Regenerative soy rotation', farming_practices:'No-till, cover crops', irrigation:'Rainfed', supporting_documents:[{name:'property-doc-demo.pdf',type:'land_record',status:'uploaded_demo'}], status:'submitted', ai_assessment:{ label:'Demonstration estimate', land_health_score:71, estimated_total_potential_tco2e:13500, note:'Not a certified carbon credit.' }, linked_carbon_project_id:'cproj-brazil', created_at:now, updated_at:now },
  ];

  const qa = (overrides={}) => ({ additionality:'Demonstration assessment: project activity described; independent additionality test not completed.', permanence:'Medium (demo): long-term storage risk not independently verified.', leakage_risk:'Low/medium (demo): landscape leakage assessment not independently verified.', monitoring_methodology:'Demo monitoring plan based on reported practices and SIMULATED indicators.', verification_standard:'Not independently verified (demonstration data)', transparency:'Project metadata and document list available in platform.', documentation:'Supporting document metadata available; originals not independently validated.', vintage_year:String(new Date().getFullYear()), project_location:'As declared by seller (demo).', co_benefits:['Soil health improvement (reported)','Biodiversity support (reported)'], ...overrides });

  db.carbon_projects = [
    { id:'cproj-1000', seller_id:'user-seller-1', land_registration_id:'land-1000', project_name:'Mulshi Agroforestry Carbon Project', country:'India', state:'Maharashtra', location:'Mulshi, Pune', land_area:200, land_type:'agroforestry', crop_information:'Agroforestry', estimated_carbon_potential_tco2e:2187, submission_status:'approved', admin_status:'approved', verification_status:'approved_for_listing (demo; not independently certified)', verification_standard:'Demonstration review', methodology:'Demonstration estimate only', description:'Approved demo project used for marketplace and transaction flow testing.', created_at:now, updated_at:now },
    { id:'cproj-brazil', seller_id:'user-seller-2', land_registration_id:'land-brazil', project_name:'Cerrado Regenerative Soil Project', country:'Brazil', state:'Mato Grosso', location:'Sinop', land_area:500, land_type:'cropland', crop_information:'Regenerative soy rotation', estimated_carbon_potential_tco2e:13500, submission_status:'under_review', admin_status:'pending', verification_status:'not_independently_verified', verification_standard:'Not independently verified', methodology:'Demonstration estimate only', description:'Pending verification (demo).', created_at:now, updated_at:now },
    { id:'cproj-kenya', seller_id:'user-seller-3', land_registration_id:null, project_name:'Nakuru Grassland Restoration', country:'Kenya', state:'Nakuru County', location:'Nakuru', land_area:120, land_type:'pasture', crop_information:'Grassland restoration', estimated_carbon_potential_tco2e:980, submission_status:'rejected', admin_status:'rejected', verification_status:'rejected', verification_standard:'Not independently verified', methodology:'Demonstration estimate only', description:'Rejected demo project (insufficient evidence).', review_reason:'Insufficient supporting documents (demo).', created_at:now, updated_at:now },
  ];

  db.credit_listings = [
    { id:'lst-1000', carbon_project_id:'cproj-1000', seller_id:'user-seller-1', project_name:'Mulshi Agroforestry Carbon Project', country:'India', state:'Maharashtra', location:'Mulshi, Pune', land_type:'agroforestry', project_type:'Agroforestry', crop_information:'Agroforestry', quantity_total:1000, quantity_available:1000, quantity_sold:0, price_per_credit:18, currency:'USD', quality_tier:'silver_demo', quality_assessment:qa(), verification_status:'approved_for_listing (demo; not independently certified)', market_status:'approved', listing_status:'active', description:'Demo listing: 1,000 credits available for transaction-flow testing. Not independently certified.', created_at:now, updated_at:now },
    { id:'lst-global-1', carbon_project_id:'cproj-1000', seller_id:'user-seller-1', project_name:'Maharashtra Soil Carbon Pool', country:'India', state:'Maharashtra', location:'Nashik', land_type:'cropland', project_type:'Regenerative Agriculture', crop_information:'Millets', quantity_total:500, quantity_available:320, quantity_sold:180, price_per_credit:22, currency:'USD', quality_tier:'gold_demo', quality_assessment:qa({ permanence:'Medium/high (demo)', verification_standard:'Not independently verified (demonstration data)' }), verification_status:'approved_for_listing (demo)', market_status:'approved', listing_status:'active', description:'Global marketplace demo listing.', created_at:now, updated_at:now },
    { id:'lst-brazil-pending', carbon_project_id:'cproj-brazil', seller_id:'user-seller-2', project_name:'Cerrado Regenerative Soil Project', country:'Brazil', state:'Mato Grosso', location:'Sinop', land_type:'cropland', project_type:'Regenerative Agriculture', quantity_total:2000, quantity_available:2000, quantity_sold:0, price_per_credit:15, currency:'USD', quality_tier:'pending_review', quality_assessment:qa(), verification_status:'not_independently_verified', market_status:'pending', listing_status:'pending_review', description:'Pending admin review; not available for purchase.', created_at:now, updated_at:now },
  ];

  db.project_documents = [
    { id:'doc-1', carbon_project_id:'cproj-1000', seller_id:'user-seller-1', name:'Project Design Note (demo).pdf', doc_type:'project_document', status:'uploaded_demo', uploaded_at:now },
    { id:'doc-2', carbon_project_id:'cproj-1000', seller_id:'user-seller-1', name:'Monitoring Plan (demo).pdf', doc_type:'monitoring_report', status:'uploaded_demo', uploaded_at:now },
    { id:'doc-3', carbon_project_id:'cproj-1000', seller_id:'user-seller-1', name:'Methodology Summary (demo).pdf', doc_type:'methodology', status:'uploaded_demo', uploaded_at:now },
    { id:'doc-4', carbon_project_id:'cproj-brazil', seller_id:'user-seller-2', name:'Property Boundary (demo).pdf', doc_type:'project_document', status:'uploaded_demo', uploaded_at:now },
  ];

  db.credit_balances = [
    { id:'bal-s1', owner_id:'user-seller-1', owner_role:'seller', available_credits:1320, acquired_credits:0, listed_credits:1500, sold_credits:180, updated_at:now },
    { id:'bal-s2', owner_id:'user-seller-2', owner_role:'seller', available_credits:0, acquired_credits:0, listed_credits:0, sold_credits:0, updated_at:now },
    { id:'bal-b1', owner_id:'user-buyer-1', owner_role:'buyer', available_credits:0, acquired_credits:120, listed_credits:0, sold_credits:0, updated_at:now },
    { id:'bal-b2', owner_id:'user-buyer-2', owner_role:'buyer', available_credits:0, acquired_credits:60, listed_credits:0, sold_credits:0, updated_at:now },
  ];

  db.credit_transactions = [
    { id:'txn-seed-1', listing_id:'lst-global-1', carbon_project_id:'cproj-1000', seller_id:'user-seller-1', buyer_id:'user-buyer-1', project_name:'Maharashtra Soil Carbon Pool', quantity:120, price_per_credit:22, currency:'USD', total_amount:2640, status:'completed', payment_mode:'simulated_demonstration', created_at:now },
    { id:'txn-seed-2', listing_id:'lst-global-1', carbon_project_id:'cproj-1000', seller_id:'user-seller-1', buyer_id:'user-buyer-2', project_name:'Maharashtra Soil Carbon Pool', quantity:60, price_per_credit:22, currency:'USD', total_amount:1320, status:'completed', payment_mode:'simulated_demonstration', created_at:now },
  ];

  logAudit({ actor_id:'user-admin-1', actor_role:'admin', action:'demo_seed_loaded', entity_type:'platform', entity_id:'demo', after:{ listings: db.credit_listings.length }, source:'system' });
  logActivity({ type:'system', source:'system', message:'CarbonNova marketplace/governance demo data seeded (global listings, verification states, balances, transactions). Demonstration data only.' });
}

export function seedDemoData(force = false) {
  const db = getDb();
  if (!force && db.projects.length > 0) { seedPlatformDemoData(db); saveDb(); return db; }
  readingSeq = 0;
  db.projects = structuredClone(SEED_PROJECTS);
  db.devices = structuredClone(SEED_DEVICES);
  db.readings = [];
  for (const device of SEED_DEVICES) {
    const project = db.projects.find((p) => p.id === device.project_id);
    const coarse = simulateSeries(device.id, project.land_type, 30 * 24, 360);
    const fine = simulateSeries(device.id, project.land_type, 48, 60);
    const byTs = new Map();
    for (const r of [...coarse, ...fine]) byTs.set(r.recorded_at, makeReading(device.id, project, r));
    db.readings.push(...[...byTs.values()].sort((a, b) => a.recorded_at.localeCompare(b.recorded_at)));
  }
  db.activity = [];
  logActivity({ project_id: null, type: 'system', source: 'system', message: 'Monitoring demo data seeded (SIMULATED sensor readings). Not environmental evidence.' });
  seedPlatformDemoData(db, { force });
  saveDb();
  return db;
}

export { SEED_PROJECTS, SEED_DEVICES };
