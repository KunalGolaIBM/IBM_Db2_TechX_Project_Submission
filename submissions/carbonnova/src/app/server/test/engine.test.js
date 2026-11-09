/** Unit tests — Carbon estimation engine (pure science layer). Run: npm test */
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import {
  estimateCarbon,
  socStockTCPerHa,
  respirationToKgCo2PerHaPerDay,
  environmentResponse,
  LAND_TYPE_PARAMS,
  METHODOLOGY,
  C_TO_CO2,
  VAN_BEMMELEN,
} from '../lib/carbonEngine.js';

const PROJECT = {
  id: 'proj_test', name: 'Test Plot', land_type: 'agroforestry',
  area_acres: 100, location: 'Testville', status: 'active',
};

const reading = (overrides = {}) => ({
  recorded_at: '2026-10-01T06:00:00.000Z',
  data_source: 'simulated',
  is_simulated: true,
  values: {
    soil_moisture_pct: 45, soil_temp_c: 25, soil_co2_respiration: 300,
    soil_ph: 6.5, ec_ds_m: 0.8, air_temp_c: 28, air_humidity_pct: 60,
    ...overrides,
  },
});

describe('carbonEngine formulas', () => {
  test('SOC stock: 1.6% × 1.25 g/cm³ × 0.3 m × 100 = 60 t C/ha', () => {
    assert.equal(socStockTCPerHa(1.6, 1.25, 30), 60);
  });

  test('respiration conversion: 100 mg CO₂ m⁻² h⁻¹ → 24 kg CO₂/ha/day', () => {
    assert.equal(respirationToKgCo2PerHaPerDay(100), 24);
  });

  test('environmental response peaks (≈1.0) at optimum 45% moisture / 25°C', () => {
    const f = environmentResponse(45, 25);
    assert.ok(Math.abs(f - 1) < 0.001, `expected ≈1, got ${f}`);
    // and degrades away from optimum
    assert.ok(environmentResponse(10, 40) < 0.5);
  });

  test('C → CO₂ ratio is 44/12 and Van Bemmelen factor documented as 0.58', () => {
    assert.ok(Math.abs(C_TO_CO2 - 44 / 12) < 1e-9);
    assert.equal(VAN_BEMMELEN, 0.58);
  });

  test('all land types have documented default parameters', () => {
    for (const lt of ['agroforestry', 'forestry', 'cropland', 'pasture', 'mangrove', 'solar', 'biogas']) {
      const p = LAND_TYPE_PARAMS[lt];
      assert.ok(p, `missing params for ${lt}`);
      assert.ok(p.soc_pct > 0 && p.bulk_density > 0 && p.soc_sequestration_rate >= 0);
    }
  });
});

describe('estimateCarbon output contract', () => {
  test('with simulated readings: values derived, everything labelled simulated', () => {
    const readings = Array.from({ length: 24 }, () => reading());
    const est = estimateCarbon(PROJECT, readings);
    assert.equal(est.data_source, 'simulated');
    assert.equal(est.uses_simulated_data, true);
    assert.equal(est.area.hectares, Number((100 * 0.0404686).toFixed(2)));
    assert.equal(est.inputs_used.sample_count, 24);
    assert.ok(est.metrics.soc_stock_total_tC > 0);
    assert.ok(est.metrics.soil_respiration_project_tCO2e_yr > 0);
    assert.ok(est.metrics.net_sequestration_project_tCO2e_yr > 0);
  });

  test('uncertainty band is present and brackets the point estimate', () => {
    const est = estimateCarbon(PROJECT, [reading()]);
    const u = est.metrics.net_sequestration_uncertainty;
    assert.ok(u.pct > 0 && u.pct <= 50);
    assert.ok(u.low < est.metrics.net_sequestration_project_tCO2e_yr);
    assert.ok(u.high > est.metrics.net_sequestration_project_tCO2e_yr);
    assert.ok(Math.abs(u.low - est.metrics.net_sequestration_project_tCO2e_yr * (1 - u.pct / 100)) < 0.5);
  });

  test('is explainable: formulas, assumptions and limitations all present', () => {
    const est = estimateCarbon(PROJECT, [reading()]);
    assert.ok(est.formulas.length >= 4, 'formulas must be documented');
    for (const f of est.formulas) {
      assert.ok(f.name && f.formula && Array.isArray(f.inputs));
    }
    assert.ok(est.assumptions.length >= 4);
    assert.ok(est.limitations.length >= 3);
    assert.ok(est.limitations.some((l) => /respiration.*LOSS|LOSS flux/i.test(l)), 'must state respiration is a loss flux');
    assert.ok(METHODOLOGY.framework.length > 20);
  });

  test('never claims verification: disclaimer present and explicit', () => {
    const est = estimateCarbon(PROJECT, [reading()]);
    assert.match(est.disclaimer, /NOT A VERIFIED CARBON CREDIT/i);
    assert.ok(est.limitations.some((l) => /NOT verified carbon credits|not verified/i.test(l)));
  });

  test('distinguishes respiration (loss) from sequestration (net gain) as separate metrics', () => {
    const est = estimateCarbon(PROJECT, [reading()]);
    assert.notEqual(est.metrics.soil_respiration_project_tCO2e_yr, est.metrics.net_sequestration_project_tCO2e_yr);
    assert.ok(est.formulas.some((f) => f.id === 'soil_respiration'));
    assert.ok(est.formulas.some((f) => f.id === 'net_seq'));
  });

  test('no readings → defaults used, flagged as such', () => {
    const est = estimateCarbon(PROJECT, []);
    assert.equal(est.inputs_used.sample_count, 0);
    assert.equal(est.inputs_used.avg_soil_moisture_pct, null);
    assert.match(est.data_source, /no_sensor_data/);
    assert.equal(est.uses_simulated_data, true);
    assert.ok(est.metrics.net_sequestration_project_tCO2e_yr > 0);
  });

  test('sensor-informed path lowers assumed uncertainty vs defaults-only (35% vs 50%)', () => {
    const withSensors = estimateCarbon(PROJECT, [reading()]);
    const without = estimateCarbon(PROJECT, []);
    assert.equal(withSensors.metrics.net_sequestration_uncertainty.pct, 35);
    assert.equal(without.metrics.net_sequestration_uncertainty.pct, 50);
  });

  test('reports missing laboratory inputs instead of concealing default parameters', () => {
    const est = estimateCarbon(PROJECT, []);
    assert.ok(est.missing_inputs.some((item) => /Laboratory-measured soil organic carbon/i.test(item)));
    assert.equal(est.inputs_used.soc_pct_is_default, true);
    assert.equal(est.inputs_used.bulk_density_is_default, true);
    const lab = estimateCarbon({ ...PROJECT, soc_pct: 2.2, bulk_density: 1.1 }, []);
    assert.equal(lab.inputs_used.soc_pct_used, 2.2);
    assert.equal(lab.inputs_used.bulk_density_used, 1.1);
    assert.equal(lab.inputs_used.soc_pct_is_default, false);
  });

  test('is deterministic: identical inputs → identical outputs', () => {
    const readings = [reading(), reading({ soil_moisture_pct: 50 })];
    const a = estimateCarbon(PROJECT, readings);
    const b = estimateCarbon(PROJECT, readings);
    assert.deepEqual(a.metrics, b.metrics);
  });
});
