/**
 * CarbonNova — MRV Report generation (PDF + CSV)
 * ----------------------------------------------
 * Audit-friendly exports containing: project details, timestamped readings,
 * carbon estimate + methodology, data sources, assumptions, uncertainty and
 * the monitoring activity history. Simulated data and AI-generated text are
 * clearly marked in both formats.
 */
import PDFDocument from 'pdfkit';
import { estimateCarbon, METHODOLOGY } from './carbonEngine.js';
import { METRICS } from './simulator.js';
import { ACRES_TO_HA } from '../db.js';

const DISCLAIMER =
  'This report contains INDICATIVE estimates produced by a documented model — NOT verified carbon credits. ' +
  'Where sensor data is marked SIMULATED, values are synthetic demo data with no evidentiary value. ' +
  'Independent third-party verification is required before any credit or compliance claim.';

/** Build the CSV export (readings + metadata header). */
export function buildReadingsCsv(project, readings) {
  const esc = (v) => {
    if (v === null || v === undefined) return '';
    const s = String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [];
  lines.push(`# CarbonNova MRV — Sensor Readings Export`);
  lines.push(`# project_id,${esc(project.id)}`);
  lines.push(`# project,${esc(project.name)}`);
  lines.push(`# land_type,${esc(project.land_type)}`);
  lines.push(`# area,${project.area_acres} acres (${round(project.area_acres * ACRES_TO_HA, 2)} ha)`);
  lines.push(`# generated_at,${new Date().toISOString()}`);
  lines.push(`# data_sources,${[...new Set(readings.map((r) => r.data_source))].join(' | ') || 'none'}`);
  lines.push(`# disclaimer,${esc(DISCLAIMER)}`);
  lines.push(['recorded_at', 'device_id', 'data_source', 'is_simulated', ...METRICS.map((m) => `${m.key} (${m.unit})`)].join(','));
  for (const r of readings) {
    lines.push([
      r.recorded_at,
      r.device_id || '',
      r.data_source,
      r.is_simulated ? 'TRUE' : 'FALSE',
      ...METRICS.map((m) => (r.values?.[m.key] ?? '')),
    ].map(esc).join(','));
  }
  return lines.join('\n');
}

/** Build the carbon-estimate CSV (formula audit trail). */
export function buildEstimateCsv(project, readings) {
  const est = estimateCarbon(project, readings);
  const lines = [];
  lines.push('# CarbonNova MRV — Carbon Estimation Export');
  lines.push(`# project,${escCsv(project.name)}`);
  lines.push(`# engine_version,${METHODOLOGY.engine_version}`);
  lines.push(`# generated_at,${est.generated_at}`);
  lines.push(`# data_source,${est.data_source}`);
  lines.push('# DISCLAIMER,' + escCsv(DISCLAIMER));
  lines.push('section,key,value,unit_or_note');
  for (const [k, v] of Object.entries(est.metrics)) {
    if (v !== null && typeof v !== 'object') lines.push(['metric', k, v, ''].map(escCsv).join(','));
  }
  for (const f of est.formulas) {
    lines.push(['formula', f.id, escCsv(f.formula), f.inputs.join('; ')].map(escCsv).join(','));
  }
  for (const a of est.assumptions) lines.push(['assumption', '', escCsv(a), ''].join(','));
  for (const l of est.limitations) lines.push(['limitation', '', escCsv(l), ''].join(','));
  return lines.join('\n');
}

const escCsv = (v) => {
  const s = String(v ?? '');
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};
const round = (v, dp = 2) => Number(v.toFixed(dp));

/**
 * Build the full MRV monitoring report as a PDF stream.
 * @returns {Promise<Buffer>}
 */
export function buildReportPdf({ project, readings, activity, aiSummary }) {
  return new Promise((resolve, reject) => {
    try {
      const doc = new PDFDocument({ size: 'A4', margin: 50, bufferPages: true });
      const chunks = [];
      doc.on('data', (c) => chunks.push(c));
      doc.on('end', () => resolve(Buffer.concat(chunks)));
      doc.on('error', reject);

      const est = estimateCarbon(project, readings);
      const areaHa = round((project.area_acres || 0) * ACRES_TO_HA, 2);
      const isSim = readings.length > 0 && readings.every((r) => r.is_simulated);
      const h1 = (t) => doc.fontSize(18).font('Helvetica-Bold').text(t).moveDown(0.5);
      const h2 = (t) => doc.moveDown(0.6).fontSize(13).font('Helvetica-Bold').text(t).moveDown(0.3);
      const body = (t) => doc.fontSize(9.5).font('Helvetica').text(t, { lineGap: 2 });
      const kv = (k, v) => doc.fontSize(9.5).font('Helvetica').text(`${k}: ${v}`, { continued: false });

      // ---- Header ----------------------------------------------------------
      doc.fontSize(10).fillColor('#0a9063').font('Helvetica-Bold')
        .text('CARBONNOVA — DIGITAL MRV MONITORING REPORT', { align: 'left' });
      doc.fillColor('#666').fontSize(8)
        .text(`Generated: ${new Date().toISOString()}  |  Engine v${METHODOLOGY.engine_version}  |  Report ID: ${est.project_id}-${Date.now().toString(36)}`);
      doc.moveDown(0.5);
      doc.moveTo(50, doc.y).lineTo(545, doc.y).strokeColor('#0a9063').stroke();
      doc.fillColor('#000').moveDown(0.8);

      h1(project.name);
      body(`Land & Project Management record · Status: ${project.status}`);

      // ---- 1. Project details ---------------------------------------------
      h2('1. Project Details');
      kv('Project name', project.name);
      kv('Land type', project.land_type);
      kv('Location', project.location || 'not specified');
      kv('Land area', `${project.area_acres} acres (${areaHa} hectares)`);
      kv('Monitoring since', project.created_at);
      kv('Description', project.description || '—');

      // ---- 2. Data sources --------------------------------------------------
      h2('2. Data Sources & Integrity');
      kv('Readings included', readings.length);
      kv('Data source label', est.data_source);
      kv('Simulated data', isSim || readings.length === 0 ? 'YES — all readings are SIMULATED demo data' : 'Mixed/real device data');
      if (readings.length) {
        kv('Timestamped window', `${readings[0].recorded_at}  →  ${readings[readings.length - 1].recorded_at}`);
      }

      // ---- 3. Monitoring summary -------------------------------------------
      h2('3. Monitoring Summary (latest / average)');
      if (readings.length === 0) {
        body('No sensor readings available for this project yet.');
      } else {
        const last = readings[readings.length - 1];
        for (const m of METRICS) {
          const vals = readings.map((r) => r.values?.[m.key]).filter((v) => typeof v === 'number');
          if (!vals.length) continue;
          const avg = round(vals.reduce((a, b) => a + b, 0) / vals.length, 2);
          kv(`${m.label} (${m.unit})`, `latest ${last.values?.[m.key]} · avg ${avg} · min ${Math.min(...vals)} · max ${Math.max(...vals)}`);
        }
      }

      // ---- 4. Carbon estimate ----------------------------------------------
      h2('4. Carbon Estimation (INDICATIVE — NOT verified credits)');
      kv('SOC stock (0–30 cm)', `${est.metrics.soc_stock_total_tC} tC  (${est.metrics.soc_stock_tC_ha} t C/ha)  ≈ ${est.metrics.soc_stock_total_tCO2e} tCO₂e`);
      kv('Soil respiration (LOSS flux)', `${est.metrics.soil_respiration_project_tCO2e_yr} tCO₂e/yr  (${est.metrics.soil_respiration_kgCO2_ha_day} kg CO₂/ha/day)`);
      kv('Indicative net sequestration', `${est.metrics.net_sequestration_project_tCO2e_yr} tCO₂e/yr  ±${est.metrics.net_sequestration_uncertainty.pct}%  (range ${est.metrics.net_sequestration_uncertainty.low} – ${est.metrics.net_sequestration_uncertainty.high})`);
      doc.moveDown(0.3);
      body('Methodology: ' + METHODOLOGY.framework);
      doc.moveDown(0.2);
      doc.fontSize(9).font('Helvetica-Bold').text('Formulas used:');
      doc.font('Helvetica');
      for (const f of est.formulas) body(`  • ${f.name}: ${f.formula}`);
      doc.moveDown(0.2);
      doc.font('Helvetica-Bold').text('Assumptions:');
      doc.font('Helvetica');
      for (const a of est.assumptions) body(`  • ${a}`);
      doc.moveDown(0.2);
      doc.font('Helvetica-Bold').text('Limitations:');
      doc.font('Helvetica');
      for (const l of est.limitations) body(`  • ${l}`);

      // ---- 5. AI draft (optional) ------------------------------------------
      if (aiSummary) {
        doc.addPage();
        h2('5. AI-Generated Narrative Summary');
        doc.fillColor('#b45309').fontSize(8.5).font('Helvetica-Bold')
          .text('⚠ AI-GENERATED DRAFT — produced by an NVIDIA Nemotron model via Nebius Token Factory. Not reviewed by a human, not a scientific calculation, not verification.')
          .fillColor('#000');
        doc.moveDown(0.3);
        doc.font('Helvetica');
        body(aiSummary);
      }

      // ---- 6. Audit trail ---------------------------------------------------
      h2(`${aiSummary ? '6' : '5'}. Monitoring Activity Trail`);
      if (!activity?.length) body('No activity recorded.');
      else {
        for (const a of activity.slice(0, 25)) {
          body(`  ${a.at}  [${a.type}] ${a.message} (source: ${a.source})`);
        }
      }

      // ---- Disclaimer footer on every page ---------------------------------
      const range = doc.bufferedPageRange();
      for (let i = range.start; i < range.start + range.count; i++) {
        doc.switchToPage(i);
        doc.fontSize(7).fillColor('#b91c1c').font('Helvetica-Bold')
          .text(DISCLAIMER, 50, doc.page.height - 105, { width: 495, align: 'left' });
        doc.fillColor('#888').font('Helvetica')
          .text('CarbonNova prototype · For monitoring & decision support only', 50, doc.y + 6, { width: 495 });
      }

      doc.end();
    } catch (err) {
      reject(err);
    }
  });
}
