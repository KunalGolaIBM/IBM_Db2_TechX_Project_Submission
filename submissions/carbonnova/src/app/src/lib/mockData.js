// Mock data for CarbonChain platform

export const mockUsers = [
  { id: 'user-1', email: 'raj@greenfarm.in', full_name: 'Rajesh Kumar', organization: 'Green Farms Maharashtra', role: 'seller', kyc_status: 'approved', avatar: null },
  { id: 'user-2', email: 'priya@ecosolar.in', full_name: 'Priya Sharma', organization: 'EcoSolar Projects', role: 'seller', kyc_status: 'approved', avatar: null },
  { id: 'user-3', email: 'amit@tatasteel.com', full_name: 'Amit Patel', organization: 'Tata Steel ESG Division', role: 'buyer', kyc_status: 'approved', avatar: null },
  { id: 'user-4', email: 'sneha@infosys.com', full_name: 'Sneha Reddy', organization: 'Infosys Green Initiative', role: 'buyer', kyc_status: 'approved', avatar: null },
  { id: 'user-5', email: 'admin@carbonchain.in', full_name: 'Platform Admin', organization: 'CarbonChain', role: 'admin', kyc_status: 'approved', avatar: null },
  { id: 'user-6', email: 'verifier@climatech.in', full_name: 'Dr. Meera Singh', organization: 'ClimaTech Verifiers', role: 'verifier', kyc_status: 'approved', avatar: null },
];

export const mockProjects = [
  {
    id: 'proj-1', seller_id: 'user-1', name: 'Sahyadri Agroforestry Reserve', type: 'agroforestry',
    location_state: 'Maharashtra', location_district: 'Pune', lat: 18.5204, lng: 73.8567,
    area_acres: 450, methodology: 'Verra', verification_status: 'verified',
    satellite_image_url: null, created_at: '2025-11-15T00:00:00Z',
    description: 'Mixed-species agroforestry system combining fruit trees with native forest species across 450 acres in the Sahyadri foothills.'
  },
  {
    id: 'proj-2', seller_id: 'user-2', name: 'Rajasthan Solar Carbon Offset', type: 'solar',
    location_state: 'Rajasthan', location_district: 'Jaisalmer', lat: 26.9124, lng: 70.9043,
    area_acres: 120, methodology: 'Gold Standard', verification_status: 'verified',
    satellite_image_url: null, created_at: '2025-09-01T00:00:00Z',
    description: '50 MW solar farm preventing grid-based emissions. Grid emission factor: 0.71 kg CO₂/kWh.'
  },
  {
    id: 'proj-3', seller_id: 'user-1', name: 'Vidarbha Community Biogas', type: 'biogas',
    location_state: 'Maharashtra', location_district: 'Nagpur', lat: 21.1458, lng: 79.0882,
    area_acres: 30, methodology: 'India Carbon Market', verification_status: 'pending',
    satellite_image_url: null, created_at: '2026-01-10T00:00:00Z',
    description: 'Community biogas digesters serving 200 households, replacing LPG and firewood.'
  },
  {
    id: 'proj-4', seller_id: 'user-2', name: 'Sundarbans Mangrove Restoration', type: 'forestry',
    location_state: 'West Bengal', location_district: 'South 24 Parganas', lat: 21.9497, lng: 89.1833,
    area_acres: 800, methodology: 'Verra', verification_status: 'verified',
    satellite_image_url: null, created_at: '2025-06-20T00:00:00Z',
    description: 'Mangrove ecosystem restoration and conservation in the Sundarbans delta, one of the world\'s most carbon-dense ecosystems.'
  },
];

export const mockDevices = [
  { id: 'dev-1', device_token: 'tok-abc123', owner_id: 'user-1', project_id: 'proj-1', device_type: 'esp32', last_ping: new Date(Date.now() - 2 * 60 * 1000).toISOString(), battery_pct: 84, is_active: true },
  { id: 'dev-2', device_token: 'tok-def456', owner_id: 'user-2', project_id: 'proj-2', device_type: 'raspberry_pi', last_ping: new Date(Date.now() - 5 * 60 * 1000).toISOString(), battery_pct: 100, is_active: true },
  { id: 'dev-3', device_token: 'tok-ghi789', owner_id: 'user-1', project_id: 'proj-3', device_type: 'esp32', last_ping: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(), battery_pct: 12, is_active: false },
  { id: 'dev-4', device_token: 'tok-jkl012', owner_id: 'user-2', project_id: 'proj-4', device_type: 'raspberry_pi', last_ping: new Date(Date.now() - 1 * 60 * 1000).toISOString(), battery_pct: 91, is_active: true },
];

export const mockSensorReadings = {
  'dev-1': { co2_ppm: 398.2, temperature_c: 26.1, humidity_pct: 68, soil_moisture_pct: 48, pm25: 9.1, pm10: 18.3, energy_kwh: 0, voc_ohm: 12000 },
  'dev-2': { co2_ppm: 415.7, temperature_c: 38.5, humidity_pct: 22, soil_moisture_pct: 15, pm25: 6.4, pm10: 12.1, energy_kwh: 42.8, voc_ohm: 8500 },
  'dev-3': { co2_ppm: 432.0, temperature_c: 29.8, humidity_pct: 71, soil_moisture_pct: 55, pm25: 28.5, pm10: 54.2, energy_kwh: 2.1, voc_ohm: 15000 },
  'dev-4': { co2_ppm: 385.3, temperature_c: 31.2, humidity_pct: 82, soil_moisture_pct: 72, pm25: 7.8, pm10: 15.6, energy_kwh: 0, voc_ohm: 9200 },
};

export const mockListings = [
  {
    id: 'lst-1', project_id: 'proj-1', seller_id: 'user-1', project_name: 'Sahyadri Agroforestry Reserve',
    quantity_total: 1200, quantity_available: 743, price_per_tonne: 2450, currency: 'INR',
    quality_score: 88, quality_tier: 'gold', vintage_year: 2025, expiry_date: '2028-12-31',
    status: 'active', type: 'agroforestry', location_state: 'Maharashtra', methodology: 'Verra',
    blockchain_hash: '0x3f4a8b2c1d9e...', last_score_update: new Date().toISOString(), created_at: '2025-11-20T00:00:00Z'
  },
  {
    id: 'lst-2', project_id: 'proj-2', seller_id: 'user-2', project_name: 'Rajasthan Solar Carbon Offset',
    quantity_total: 8500, quantity_available: 5230, price_per_tonne: 1850, currency: 'INR',
    quality_score: 72, quality_tier: 'silver', vintage_year: 2025, expiry_date: '2027-06-30',
    status: 'active', type: 'solar', location_state: 'Rajasthan', methodology: 'Gold Standard',
    blockchain_hash: '0xab12cd34ef56...', last_score_update: new Date().toISOString(), created_at: '2025-09-05T00:00:00Z'
  },
  {
    id: 'lst-3', project_id: 'proj-4', seller_id: 'user-2', project_name: 'Sundarbans Mangrove Restoration',
    quantity_total: 3200, quantity_available: 2100, price_per_tonne: 3200, currency: 'INR',
    quality_score: 94, quality_tier: 'gold', vintage_year: 2025, expiry_date: '2030-12-31',
    status: 'active', type: 'forestry', location_state: 'West Bengal', methodology: 'Verra',
    blockchain_hash: '0x9e8d7c6b5a4f...', last_score_update: new Date().toISOString(), created_at: '2025-06-25T00:00:00Z'
  },
  {
    id: 'lst-4', project_id: 'proj-3', seller_id: 'user-1', project_name: 'Vidarbha Community Biogas',
    quantity_total: 500, quantity_available: 500, price_per_tonne: 1200, currency: 'INR',
    quality_score: 42, quality_tier: 'flagged', vintage_year: 2026, expiry_date: '2027-12-31',
    status: 'suspended', type: 'biogas', location_state: 'Maharashtra', methodology: 'India Carbon Market',
    blockchain_hash: null, last_score_update: new Date().toISOString(), created_at: '2026-01-15T00:00:00Z'
  },
  {
    id: 'lst-5', project_id: 'proj-1', seller_id: 'user-1', project_name: 'Sahyadri Phase 2 Credits',
    quantity_total: 600, quantity_available: 600, price_per_tonne: 2800, currency: 'INR',
    quality_score: 91, quality_tier: 'gold', vintage_year: 2026, expiry_date: '2029-06-30',
    status: 'active', type: 'agroforestry', location_state: 'Maharashtra', methodology: 'Verra',
    blockchain_hash: '0x1a2b3c4d5e6f...', last_score_update: new Date().toISOString(), created_at: '2026-01-01T00:00:00Z'
  },
  {
    id: 'lst-6', project_id: 'proj-2', seller_id: 'user-2', project_name: 'Gujarat Wind Farm Offsets',
    quantity_total: 4000, quantity_available: 3150, price_per_tonne: 1650, currency: 'INR',
    quality_score: 65, quality_tier: 'silver', vintage_year: 2025, expiry_date: '2027-03-31',
    status: 'active', type: 'solar', location_state: 'Gujarat', methodology: 'Gold Standard',
    blockchain_hash: '0xfe98dc76ba54...', last_score_update: new Date().toISOString(), created_at: '2025-10-10T00:00:00Z'
  },
];

export const mockTransactions = [
  { id: 'txn-1', listing_id: 'lst-1', buyer_id: 'user-3', seller_id: 'user-1', quantity: 50, price_per_tonne: 2450, total_amount: 122500, platform_fee: 2450, payment_gateway: 'razorpay', status: 'completed', created_at: '2026-02-14T10:30:00Z', buyer_name: 'Tata Steel ESG', project_name: 'Sahyadri Agroforestry Reserve' },
  { id: 'txn-2', listing_id: 'lst-3', buyer_id: 'user-4', seller_id: 'user-2', quantity: 100, price_per_tonne: 3200, total_amount: 320000, platform_fee: 6400, payment_gateway: 'razorpay', status: 'completed', created_at: '2026-02-20T14:15:00Z', buyer_name: 'Infosys Green', project_name: 'Sundarbans Mangrove Restoration' },
  { id: 'txn-3', listing_id: 'lst-2', buyer_id: 'user-3', seller_id: 'user-2', quantity: 200, price_per_tonne: 1850, total_amount: 370000, platform_fee: 7400, payment_gateway: 'stripe', status: 'completed', created_at: '2026-03-01T09:00:00Z', buyer_name: 'Tata Steel ESG', project_name: 'Rajasthan Solar Carbon Offset' },
  { id: 'txn-4', listing_id: 'lst-5', buyer_id: 'user-4', seller_id: 'user-1', quantity: 25, price_per_tonne: 2800, total_amount: 70000, platform_fee: 1400, payment_gateway: 'razorpay', status: 'completed', created_at: '2026-03-10T16:45:00Z', buyer_name: 'Infosys Green', project_name: 'Sahyadri Phase 2 Credits' },
  { id: 'txn-5', listing_id: 'lst-6', buyer_id: 'user-3', seller_id: 'user-2', quantity: 80, price_per_tonne: 1650, total_amount: 132000, platform_fee: 2640, payment_gateway: 'razorpay', status: 'pending', created_at: '2026-03-21T08:00:00Z', buyer_name: 'Tata Steel ESG', project_name: 'Gujarat Wind Farm Offsets' },
];

export const mockCertificates = [
  { id: 'cert-1', transaction_id: 'txn-1', buyer_id: 'user-3', project_id: 'proj-1', quantity: 50, issued_at: '2026-02-14T11:00:00Z', retired: false, project_name: 'Sahyadri Agroforestry Reserve', certificate_number: 'CCT-2026-0001' },
  { id: 'cert-2', transaction_id: 'txn-2', buyer_id: 'user-4', project_id: 'proj-4', quantity: 100, issued_at: '2026-02-20T15:00:00Z', retired: true, retired_at: '2026-03-01T00:00:00Z', project_name: 'Sundarbans Mangrove Restoration', certificate_number: 'CCT-2026-0002' },
  { id: 'cert-3', transaction_id: 'txn-3', buyer_id: 'user-3', project_id: 'proj-2', quantity: 200, issued_at: '2026-03-01T10:00:00Z', retired: false, project_name: 'Rajasthan Solar Carbon Offset', certificate_number: 'CCT-2026-0003' },
];

// Generate 24-hour sparkline data
export function generateSparklineData(baseValue, variance = 0.05, points = 24) {
  return Array.from({ length: points }, (_, i) => ({
    hour: `${i}:00`,
    value: +(baseValue * (1 + (Math.random() - 0.5) * variance)).toFixed(2),
  }));
}

// Generate 30-day price history
export function generatePriceHistory(basePrice, days = 30) {
  let price = basePrice * 0.85;
  return Array.from({ length: days }, (_, i) => {
    price = price * (1 + (Math.random() - 0.45) * 0.03);
    const date = new Date();
    date.setDate(date.getDate() - (days - i));
    return { date: date.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }), price: +price.toFixed(0) };
  });
}

export const platformStats = {
  totalCreditsListed: 18000,
  totalCreditsTraded: 4550,
  totalRetired: 1200,
  activeSellers: 47,
  activeBuyers: 23,
  totalGMV: 2340000,
  avgQualityScore: 74.2,
  activeSensors: 38,
};
