/**
 * CarbonNova — Simulated IoT Sensor Module
 * ---------------------------------------
 * Generates DEMO / SIMULATED soil & environmental sensor readings.
 *
 * IMPORTANT: Every reading produced by this module is synthetic. All records
 * carry `is_simulated: true` and `data_source: 'simulated'` so the UI, APIs and
 * reports can (and must) label them clearly. These values must NEVER be
 * presented as real field measurements.
 *
 * When physical sensors (e.g. ESP32 nodes with capacitive moisture probes,
 * DS18B20 temperature sensors, CO2/NDIR sensors, pH and EC probes) are
 * available, they POST real measurements to `POST /api/ingest` with a device
 * token and those records are stored with `data_source: 'device'` instead.
 */

/** Deterministic PRNG (mulberry32) so demo charts are stable across restarts. */
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
const round = (v, dp = 2) => Number(v.toFixed(dp));

/** Metric definitions: key, label, unit, plausible natural range, chart color. */
export const METRICS = [
  { key: 'soil_moisture_pct', label: 'Soil Moisture', unit: '%', min: 18, max: 62, color: '#38cb8d', decimals: 1 },
  { key: 'soil_temp_c', label: 'Soil Temperature', unit: '°C', min: 16, max: 36, color: '#f59e0b', decimals: 1 },
  { key: 'soil_co2_respiration', label: 'Soil CO₂ / Respiration', unit: 'mg CO₂ m⁻² h⁻¹', min: 80, max: 900, color: '#2dd4bf', decimals: 0 },
  { key: 'soil_ph', label: 'Soil pH', unit: 'pH', min: 5.6, max: 7.8, color: '#a78bfa', decimals: 2 },
  { key: 'ec_ds_m', label: 'Electrical Conductivity', unit: 'dS/m', min: 0.2, max: 1.9, color: '#60a5fa', decimals: 2 },
  { key: 'air_temp_c', label: 'Air Temperature', unit: '°C', min: 14, max: 42, color: '#fbbf24', decimals: 1 },
  { key: 'air_humidity_pct', label: 'Air Humidity', unit: '%', min: 25, max: 95, color: '#38bdf8', decimals: 0 },
];

/** Per-land-type baseline profiles used by the SIMULATOR ONLY (not the carbon engine). */
const LAND_PROFILES = {
  agroforestry: { moisture: 42, soilTemp: 25, respiration: 380, ph: 6.5, ec: 0.8 },
  forestry: { moisture: 48, soilTemp: 22, respiration: 450, ph: 5.9, ec: 0.6 },
  cropland: { moisture: 36, soilTemp: 27, respiration: 320, ph: 6.8, ec: 1.2 },
  pasture: { moisture: 40, soilTemp: 24, respiration: 350, ph: 6.4, ec: 0.9 },
  mangrove: { moisture: 55, soilTemp: 28, respiration: 520, ph: 6.1, ec: 1.5 },
  solar: { moisture: 22, soilTemp: 31, respiration: 140, ph: 7.2, ec: 1.0 },
  biogas: { moisture: 45, soilTemp: 29, respiration: 480, ph: 6.9, ec: 1.3 },
};

const DEFAULT_PROFILE = LAND_PROFILES.agroforestry;

/** 24-hour diurnal multiplier for soil temperature (peak ~14:00 local). */
function diurnal(hour) {
  return Math.sin(((hour - 8) / 24) * 2 * Math.PI);
}

/**
 * Generate a single simulated reading for a device at a given time.
 * Deterministic for (deviceId, timestamp) pairs — same inputs, same outputs.
 */
export function simulateReading(deviceId, landType, timestamp = new Date()) {
  const t = timestamp instanceof Date ? timestamp : new Date(timestamp);
  const profile = LAND_PROFILES[landType] || DEFAULT_PROFILE;
  const rng = mulberry32(hashString(deviceId) ^ (Math.floor(t.getTime() / 60000) >>> 0));

  const hour = t.getHours() + t.getMinutes() / 60;
  const dayPhase = diurnal(hour);
  const noise = (scale) => (rng() - 0.5) * scale;

  // Slow multi-day wave so 7d/30d charts show realistic drift
  const dayWave = Math.sin(t.getTime() / (86400000 * 3.5) * 2 * Math.PI);

  const soilMoisture = clamp(profile.moisture + dayWave * 4 + noise(3.5), 5, 80);
  const soilTemp = clamp(profile.soilTemp + dayPhase * 2.5 + noise(1.2), 8, 45);
  // Respiration rises with temperature & moisture (microbial activity)
  const moistureFactor = clamp(1 - Math.abs(soilMoisture - 45) / 60, 0.3, 1);
  const respiration = clamp(profile.respiration * (0.75 + dayPhase * 0.15) * moistureFactor + noise(60), 40, 1200);
  const ph = clamp(profile.ph + noise(0.15), 4.5, 9);
  const ec = clamp(profile.ec + noise(0.15), 0.1, 4);
  const airTemp = clamp(soilTemp + 3 + dayPhase * 4 + noise(2), 5, 48);
  const airHumidity = clamp(70 - dayPhase * 18 + noise(6), 15, 98);

  return {
    recorded_at: t.toISOString(),
    data_source: 'simulated',
    is_simulated: true,
    values: {
      soil_moisture_pct: round(soilMoisture, 1),
      soil_temp_c: round(soilTemp, 1),
      soil_co2_respiration: round(respiration, 0),
      soil_ph: round(ph, 2),
      ec_ds_m: round(ec, 2),
      air_temp_c: round(airTemp, 1),
      air_humidity_pct: round(airHumidity, 0),
    },
  };
}

/**
 * Generate a historical series of simulated readings.
 * @param {string} deviceId
 * @param {string} landType
 * @param {number} hoursBack how many hours of history
 * @param {number} intervalMinutes spacing between readings
 */
export function simulateSeries(deviceId, landType, hoursBack = 24, intervalMinutes = 60) {
  const out = [];
  const end = Date.now();
  const step = intervalMinutes * 60000;
  for (let ms = end - hoursBack * 3600000; ms <= end; ms += step) {
    out.push(simulateReading(deviceId, landType, new Date(ms)));
  }
  return out;
}

export { LAND_PROFILES };
