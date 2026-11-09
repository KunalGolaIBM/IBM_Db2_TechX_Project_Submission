/**
 * CarbonNova — Carbon Estimation Engine (SCIENCE LAYER)
 * =====================================================
 * A separate, explainable calculation module. It contains NO AI calls and is
 * never mixed with the AI assistant layer. Every output carries:
 *   - the exact formula used,
 *   - the inputs (with their data source),
 *   - documented assumptions,
 *   - an uncertainty range,
 *   - explicit data limitations.
 *
 * WHAT THIS ENGINE DOES *NOT* DO:
 *   - It does NOT measure carbon. Sensors measure soil respiration (a CO₂
 *     *flux out of the soil*), moisture, temperature, pH and EC. Respiration
 *     is an indicator of microbial activity — it is NOT soil carbon stock and
 *     NOT proof of sequestration.
 *   - It does NOT produce verified carbon credits. Outputs are INDICATIVE
 *     estimates for monitoring/decision-support only.
 *
 * Methodology references (simplified, documented in METHODOLOGY below):
 *   - IPCC 2006 Guidelines, Vol. 4 (AFOLU): carbon stock change approach.
 *   - Van Bemmelen factor: soil organic matter → soil organic C (×0.58).
 *   - RothC / CENTURY-class models motivate the temperature-moisture
 *     response function used as a respiration proxy.
 */

import { ACRES_TO_HA } from '../db.js';

/** Van Bemmelen factor: 1 g organic matter ≈ 0.58 g organic carbon */
export const VAN_BEMMELEN = 0.58;
/** C → CO₂ molar mass ratio */
export const C_TO_CO2 = 44 / 12;

/**
 * Default parameters by land / project type.
 * soc_pct         : baseline soil organic carbon, 0–30 cm (% w/w)
 * bulk_density    : soil bulk density (g/cm³)
 * soc_sequestration_rate : indicative net SOC sequestration (tCO₂e/ha/yr)
 * rh_base         : baseline heterotrophic soil respiration (mg CO₂ m⁻² h⁻¹)
 * These are literature-style defaults used ONLY when no lab data exists.
 */
export const LAND_TYPE_PARAMS = {
  agroforestry: { soc_pct: 1.6, bulk_density: 1.25, soc_sequestration_rate: 3.8, rh_base: 350 },
  forestry:     { soc_pct: 2.6, bulk_density: 1.15, soc_sequestration_rate: 5.6, rh_base: 420 },
  cropland:     { soc_pct: 1.1, bulk_density: 1.35, soc_sequestration_rate: 1.2, rh_base: 300 },
  pasture:      { soc_pct: 1.9, bulk_density: 1.30, soc_sequestration_rate: 2.1, rh_base: 330 },
  mangrove:     { soc_pct: 3.4, bulk_density: 1.05, soc_sequestration_rate: 8.9, rh_base: 480 },
  solar:        { soc_pct: 0.6, bulk_density: 1.45, soc_sequestration_rate: 0.4, rh_base: 120 },
  biogas:       { soc_pct: 1.4, bulk_density: 1.30, soc_sequestration_rate: 1.6, rh_base: 460 },
};

/** Standard sampling depth (cm) for SOC stock calculations */
export const SOC_DEPTH_CM = 30;

const round = (v, dp = 2) => Number(v.toFixed(dp));

/**
 * Temperature-moisture response function for microbial (heterotrophic)
 * respiration, R/Tref style. Returns a dimensionless multiplier ~0–1.2.
 * Optima: soil moisture ≈ 45 % VWC, soil temperature ≈ 25 °C.
 */
export function environmentResponse(soilMoisturePct, soilTempC) {
  const fMoisture = Math.exp(-((soilMoisturePct - 45) ** 2) / (2 * 18 ** 2));
  const fTemp = Math.exp(-((soilTempC - 25) ** 2) / (2 * 10 ** 2));
  return round(fMoisture * fTemp, 4);
}

/**
 * Soil organic carbon stock in the top SOC_DEPTH_CM.
 *   SOC stock (t C/ha) = C% × ρb (g/cm³) × depth (cm) × 100 / 1000 …
 *   Simplified: t C/ha = soc_pct × bulk_density × depth_m × 100
 * Example: 1.6 % × 1.25 g/cm³ × 0.3 m × 100 = 60 t C/ha.
 */
export function socStockTCPerHa(socPct, bulkDensity, depthCm = SOC_DEPTH_CM) {
  const depthM = depthCm / 100;
  return socPct * bulkDensity * depthM * 100;
}

/**
 * Convert measured soil CO₂ respiration (mg CO₂ m⁻² h⁻¹) to a daily flux
 *   Rh (kg CO₂/ha/day) = R (mg CO₂ m⁻² h⁻¹) × 24 h × 10000 m²/ha × 1e-6 kg/mg
 */
export function respirationToKgCo2PerHaPerDay(respirationMgM2h) {
  return respirationMgM2h * 24 * 10000 * 1e-6;
}

/**
 * Main entry point. Pure function: (project, readings) → explainable estimate.
 *
 * @param {object} project  { name, land_type, area_acres, ... }
 * @param {Array}  readings latest sensor readings (newest last), may be empty
 * @returns {object} full explainable result
 */
export function estimateCarbon(project, readings = []) {
  const landType = LAND_TYPE_PARAMS[project.land_type] ? project.land_type : 'agroforestry';
  const params = LAND_TYPE_PARAMS[landType];
  const areaHa = round((project.area_acres || 0) * ACRES_TO_HA, 2);
  const hasLabSoc = Number.isFinite(project.soc_pct) && project.soc_pct >= 0 && project.soc_pct <= 30;
  const hasBulkDensity = Number.isFinite(project.bulk_density) && project.bulk_density > 0 && project.bulk_density <= 2.65;
  const socPct = hasLabSoc ? project.soc_pct : params.soc_pct;
  const bulkDensity = hasBulkDensity ? project.bulk_density : params.bulk_density;

  const readingsUsed = readings.slice(-24); // last 24 samples for averaging
  const avg = (key) => {
    const vals = readingsUsed.map((r) => r.values?.[key]).filter((v) => typeof v === 'number');
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  };

  const moisture = avg('soil_moisture_pct');
  const soilTemp = avg('soil_temp_c');
  const respiration = avg('soil_co2_respiration');
  const ph = avg('soil_ph');
  const ec = avg('ec_ds_m');

  const simulated = readingsUsed.length > 0 && readingsUsed.every((r) => r.is_simulated);
  const dataSource = readingsUsed.length === 0
    ? 'no_sensor_data (defaults only)'
    : simulated ? 'simulated' : (readingsUsed.every((r) => r.data_source === 'device') ? 'device' : 'mixed');

  // --- 1) SOC stock (stock, not flux) -------------------------------------
  const socTCPerHa = socStockTCPerHa(socPct, bulkDensity);
  const socStockTC = round(socTCPerHa * areaHa, 1);
  const socStockTCO2e = round(socStockTC * C_TO_CO2, 1);

  // --- 2) Environmental response factor (from measurements when available) --
  const envResponse = (moisture !== null && soilTemp !== null)
    ? environmentResponse(moisture, soilTemp)
    : 1;

  // --- 3) Soil respiration flux (a LOSS term, not sequestration) -----------
  const rhMg = respiration ?? params.rh_base;
  const rhKgPerHaPerDay = round(respirationToKgCo2PerHaPerDay(rhMg), 1);
  const rhTCO2ePerHaPerYr = round((rhKgPerHaPerDay * 365) / 1000, 2);
  const rhProjectTCO2ePerYr = round(rhTCO2ePerHaPerYr * areaHa, 1);

  // --- 4) Indicative net SOC sequestration estimate ------------------------
  //   Net = base rate × area × environmental response (capped at 1.2)
  const envFactor = Math.min(envResponse, 1.2);
  const netTCO2ePerHaPerYr = round(params.soc_sequestration_rate * envFactor, 2);
  const netProjectTCO2ePerYr = round(netTCO2ePerHaPerYr * areaHa, 1);

  // Uncertainty: ±50% with only default SOC data, ±35% with sensor-informed env response
  const uncertaintyPct = moisture !== null ? 35 : 50;
  const uncertainty = (v) => ({
    low: round(v * (1 - uncertaintyPct / 100), 1),
    high: round(v * (1 + uncertaintyPct / 100), 1),
  });

  return {
    generated_at: new Date().toISOString(),
    project_id: project.id,
    land_type: landType,
    area: { acres: project.area_acres ?? null, hectares: areaHa },
    data_source: dataSource,
    uses_simulated_data: simulated || readingsUsed.length === 0,
    inputs_used: {
      avg_soil_moisture_pct: moisture !== null ? round(moisture, 1) : null,
      avg_soil_temp_c: soilTemp !== null ? round(soilTemp, 1) : null,
      avg_soil_respiration_mg_m2_h: respiration !== null ? round(respiration, 0) : null,
      avg_soil_ph: ph !== null ? round(ph, 2) : null,
      avg_ec_ds_m: ec !== null ? round(ec, 2) : null,
      sample_count: readingsUsed.length,
      soc_pct_used: socPct,
      soc_pct_is_default: !hasLabSoc,
      bulk_density_used: bulkDensity,
      bulk_density_is_default: !hasBulkDensity,
    },
    metrics: {
      soc_stock_tC_ha: round(socTCPerHa, 1),
      soc_stock_total_tC: socStockTC,
      soc_stock_total_tCO2e: socStockTCO2e,
      environmental_response_factor: envFactor,
      soil_respiration_kgCO2_ha_day: rhKgPerHaPerDay,
      soil_respiration_tCO2e_ha_yr: rhTCO2ePerHaPerYr,
      soil_respiration_project_tCO2e_yr: rhProjectTCO2ePerYr,
      net_sequestration_tCO2e_ha_yr: netTCO2ePerHaPerYr,
      net_sequestration_project_tCO2e_yr: netProjectTCO2ePerYr,
      net_sequestration_uncertainty: {
        pct: uncertaintyPct,
        ...uncertainty(netProjectTCO2ePerYr),
      },
    },
    formulas: [
      {
        id: 'soc_stock',
        name: 'Soil Organic Carbon stock (top 30 cm)',
        formula: 'SOC (t C/ha) = C% × bulk density (g/cm³) × depth (m) × 100;  total tC = SOC × area (ha)',
        inputs: ['C% (default for land type — no lab data)', 'bulk density (default)', 'area (ha)'],
      },
      {
        id: 'c_to_co2e',
        name: 'Carbon → CO₂ equivalent',
        formula: 'tCO₂e = tC × (44/12)',
        inputs: ['SOC stock (tC)'],
      },
      {
        id: 'env_response',
        name: 'Environmental response factor',
        formula: 'f = exp(−(θ−45)²/(2·18²)) × exp(−(T−25)²/(2·10²)), θ = soil moisture %, T = soil temp °C',
        inputs: ['soil moisture (sensor, 24-sample avg)', 'soil temperature (sensor, 24-sample avg)'],
      },
      {
        id: 'soil_respiration',
        name: 'Soil respiration flux',
        formula: 'Rh (kg CO₂/ha/day) = R (mg CO₂ m⁻² h⁻¹) × 24 × 10⁴ × 10⁻⁶',
        inputs: ['sensor CO₂/respiration reading (24-sample avg)'],
      },
      {
        id: 'net_seq',
        name: 'Indicative net SOC sequestration',
        formula: 'Net (tCO₂e/ha/yr) = base rate (land type) × min(f, 1.2);  project total = × area (ha)',
        inputs: ['land-type base rate (documented default)', 'environmental response factor'],
      },
    ],
    assumptions: [
      hasLabSoc && hasBulkDensity
        ? `SOC ${socPct}% and bulk density ${bulkDensity} g/cm³ supplied as project field inputs; laboratory method and sampling records must be attached before treating them as verified measurements.`
        : `SOC ${hasLabSoc ? socPct : params.soc_pct}% and bulk density ${hasBulkDensity ? bulkDensity : params.bulk_density} g/cm³ include literature-style defaults for '${landType}'; no complete lab soil analysis has been confirmed.`,
      `Sampling depth fixed at ${SOC_DEPTH_CM} cm; subsoil (below ${SOC_DEPTH_CM} cm) carbon is excluded.`,
      'Soil respiration measured at the sensor point represents the field average; spatial variability across the project is not sampled.',
      'Net sequestration uses a land-type base rate scaled by a temperature-moisture response; it does not model land-use history, erosion, or dissolved carbon export.',
      'Below-ground carbon only. Biomass (trees, crops) and dead organic matter pools are not included in this estimate.',
    ],
    missing_inputs: [
      ...(!hasLabSoc ? ['Laboratory-measured soil organic carbon percentage and sampling provenance.'] : []),
      ...(!hasBulkDensity ? ['Measured soil bulk density with sampling provenance.'] : []),
      ...(readings.length === 0 ? ['Timestamped field observations linked to the assessed parcel.'] : []),
    ],
    assessment_classification: 'Indicative model output; not verified carbon stock, additional removals, or issued/retired credits.',
    limitations: [
      'Simulated/demo readings (if flagged) are synthetic and carry no evidentiary value.',
      'Soil respiration is a carbon LOSS flux — it cannot by itself demonstrate sequestration.',
      'A single-point sensor cannot verify project-scale carbon; MRV requires stratified sampling and periodic lab analysis.',
      'These estimates are NOT verified carbon credits and must not be used for compliance registries without third-party validation.',
    ],
    disclaimer:
      'INDICATIVE ESTIMATE — NOT A VERIFIED CARBON CREDIT. Produced by a simplified documented model from limited sensor data and default parameters. Independent verification (lab SOC sampling, sampling design, third-party audit) is required before any credit claim.',
  };
}

/** Static methodology text reused in reports & UI. */
export const METHODOLOGY = {
  framework: 'Simplified IPCC 2006 AFOLU-style stock approach combined with a soil-respiration environment-response proxy.',
  engine_version: '1.0.0',
  standards_note: 'Not aligned to any specific credit standard (Verra/Gold Standard) in this prototype. Methodology is documented and auditable but unvalidated.',
};
