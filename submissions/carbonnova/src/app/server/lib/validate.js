/**
 * CarbonNova — Validation Module
 * ------------------------------
 * Validates sensor payloads, AI questions, and project inputs.
 */

/** Validate an AI question body */
export function validateQuestion(body) {
  const errors = [];

  if (!body?.question) {
    errors.push('question is required');
    return errors;
  }

  const q = String(body.question).trim();

  if (q.length < 3) {
    errors.push('question is too short (minimum 3 characters)');
  }

  if (q.length > 1000) {
    errors.push('question is too long (maximum 1000 characters)');
  }

  // Reject questions that are just whitespace or punctuation
  if (!/[a-zA-Z]/.test(q)) {
    errors.push('question must contain at least one letter');
  }

  return errors;
}

/** Validate ESP32 sensor ingest payload */
export function validateIngest(body) {
  const errors = [];

  if (!body?.device_token) {
    errors.push('device_token is required');
  }

  if (!body?.readings || typeof body.readings !== 'object') {
    errors.push('readings are required');
  } else {
    const allowedKeys = [
      'soil_moisture_pct', 'soil_temp_c', 'soil_co2_respiration',
      'soil_ph', 'ec_ds_m', 'air_temp_c', 'air_humidity_pct', 'co2_ppm', 'humidity_pct',
      'pm25', 'pm10', 'energy_kwh', 'voc_ohm'
    ];
    const keys = Object.keys(body.readings);
    for (const key of keys) {
      if (!allowedKeys.includes(key)) {
        errors.push(`reading key '${key}' is not allowed`);
      }
    }

    if (body.readings.soil_ph !== undefined) {
      const ph = Number(body.readings.soil_ph);
      if (Number.isNaN(ph) || ph < 0 || ph > 14) {
        errors.push('soil_ph must be between 0 and 14');
      }
    }

    // Validate required fields for a minimal reading
    const hasCore = allowedKeys.some((k) => body.readings[k] !== undefined);
    if (!hasCore) {
      errors.push('readings must contain at least one valid sensor field');
    }
  }

  return errors;
}

/** Validate a project creation payload */
export function validateProjectInput(body, options = {}) {
  const errors = [];
  const isPartial = Boolean(options?.partial);

  if (!isPartial || body?.name !== undefined) {
    if (!body?.name) {
      errors.push('name is required');
    } else if (body.name.length < 3) {
      errors.push('name must be at least 3 characters');
    }
  }

  if (!isPartial || body?.land_type !== undefined) {
    if (!body?.land_type) {
      errors.push('land_type is required');
    } else if (!['agroforestry', 'forestry', 'cropland', 'pasture', 'mangrove', 'solar', 'biogas'].includes(body.land_type)) {
      errors.push('land_type must be one of: agroforestry, forestry, cropland, pasture, mangrove, solar, biogas');
    }
  }

  if (!isPartial || body?.area_acres !== undefined) {
    if (body?.area_acres === undefined || body?.area_acres === null) {
      errors.push('area_acres is required');
    } else if (typeof body.area_acres !== 'number' || body.area_acres <= 0) {
      errors.push('area_acres must be a positive number');
    }
  }

  if (!isPartial) {
    if (!body?.description) {
      errors.push('description is required');
    }
  }

  if (body?.soc_pct !== undefined && (!Number.isFinite(Number(body.soc_pct)) || Number(body.soc_pct) < 0 || Number(body.soc_pct) > 30)) {
    errors.push('soc_pct must be between 0 and 30 percent');
  }
  if (body?.bulk_density !== undefined && (!Number.isFinite(Number(body.bulk_density)) || Number(body.bulk_density) <= 0 || Number(body.bulk_density) > 2.65)) {
    errors.push('bulk_density must be greater than 0 and no more than 2.65 g/cm³');
  }

  for (const field of ['latitude', 'longitude']) {
    if (body?.[field] !== undefined && body[field] !== null && body[field] !== '') {
      const value = Number(body[field]);
      const max = field === 'latitude' ? 90 : 180;
      if (!Number.isFinite(value) || Math.abs(value) > max) errors.push(`${field} must be a valid coordinate`);
    }
  }

  return errors;
}