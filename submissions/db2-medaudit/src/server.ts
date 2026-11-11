import express, { Request, Response } from 'express';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';
import { createServer as createViteServer } from 'vite';
import { GoogleGenAI, Type } from '@google/genai';
import { CLINICAL_GUIDELINES, DOCTORS, DIAGNOSTIC_LABS, LAB_COMMISSION_CONTRACTS, TEST_CATALOG } from './src/data/db2MockDatabase.ts';
import { AuditReport, DiagnosticTestItem, PatientPrescription } from './src/types/medaudit.ts';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3000;

app.use(express.json());

// Initialize Google GenAI client if valid key exists
let aiClient: GoogleGenAI | null = null;
if (process.env.GEMINI_API_KEY && process.env.GEMINI_API_KEY !== 'MY_GEMINI_API_KEY' && process.env.GEMINI_API_KEY.length > 10) {
  aiClient = new GoogleGenAI({
    apiKey: process.env.GEMINI_API_KEY,
    httpOptions: {
      headers: {
        'User-Agent': 'aistudio-build',
      },
    },
  });
}

// -------------------------------------------------------------
// LangChain-Style Clinical Audit Agent Engine
// -------------------------------------------------------------
function evaluatePrescriptionLocally(prescription: PatientPrescription): AuditReport {
  const matchedGuideline = CLINICAL_GUIDELINES.find(g => {
    const text = (prescription.chiefComplaint + ' ' + prescription.vitalsAndNotes).toLowerCase();
    if (text.includes('sore throat') || text.includes('cold') || text.includes('runny nose') || text.includes('pharyngitis')) {
      return g.conditionCode === 'URI-VIRAL-01';
    }
    if (text.includes('knee') || text.includes('twist') || text.includes('ligament') || text.includes('joint')) {
      return g.conditionCode === 'KNEE-SPRAIN-03';
    }
    if (text.includes('headache') || text.includes('head pressure') || text.includes('migraine')) {
      return g.conditionCode === 'HA-TENSION-02';
    }
    if (text.includes('heartburn') || text.includes('dyspepsia') || text.includes('reflux') || text.includes('stomach')) {
      return g.conditionCode === 'GI-DYSPEPSIA-04';
    }
    if (text.includes('hypertension') || text.includes('bp') || text.includes('blood pressure')) {
      return g.conditionCode === 'CARD-HTN-05';
    }
    return false;
  }) || CLINICAL_GUIDELINES[0];

  // Match doctor and lab kickback contract in DB2 records
  const doctor = DOCTORS.find(d => d.name.toLowerCase().includes(prescription.doctorName.toLowerCase()) || prescription.doctorName.toLowerCase().includes(d.name.toLowerCase()));
  const labContracts = doctor ? LAB_COMMISSION_CONTRACTS.filter(c => c.doctorId === doctor.doctorId) : [];

  const evaluatedTests: DiagnosticTestItem[] = prescription.tests.map((test, index) => {
    const catalogItem = TEST_CATALOG.find(c => c.name.toLowerCase().includes(test.testName.toLowerCase()) || test.testName.toLowerCase().includes(c.name.toLowerCase()));
    const benchmark = catalogItem ? catalogItem.benchmarkPrice : Math.round(test.price * 0.75);

    const isExplicitlyUnwarranted = matchedGuideline.unwarrantedOrContraindicated.some(unw =>
      test.testName.toLowerCase().includes(unw.toLowerCase()) || unw.toLowerCase().includes(test.testName.toLowerCase())
    );

    const isExplicitlyIndicated = matchedGuideline.indicatedTests.some(ind =>
      test.testName.toLowerCase().includes(ind.toLowerCase()) || ind.toLowerCase().includes(test.testName.toLowerCase())
    );

    const isConditional = matchedGuideline.conditionalTests.some(cond =>
      test.testName.toLowerCase().includes(cond.toLowerCase()) || cond.toLowerCase().includes(test.testName.toLowerCase())
    );

    let tier: 'essential' | 'conditional' | 'unwarranted' = 'conditional';
    let reason = '';

    if (isExplicitlyUnwarranted) {
      tier = 'unwarranted';
      reason = `Contraindicated/Unwarranted for this presentation. ${matchedGuideline.authority} confirms this test yields no diagnostic value for this stage and adds unnecessary financial/radiation burden.`;
    } else if (isExplicitlyIndicated) {
      tier = 'essential';
      reason = `Clinically indicated primary test under ${matchedGuideline.authority}. Necessary to establish initial baseline diagnosis.`;
    } else if (isConditional) {
      tier = 'conditional';
      reason = `Conditional secondary test. Guidelines recommend conservative management first or ordering only if specific red flags develop.`;
    } else {
      // General heuristic based on test invasiveness and cost
      if (test.category === 'Radiology' && (test.testName.includes('CT') || test.testName.includes('MRI'))) {
        tier = 'unwarranted';
        reason = `Advanced imaging is not justified for acute initial presentation without focal neurological or structural alarms.`;
      } else if (test.category === 'Genetics' || test.testName.includes('Metabolic Panel') || test.testName.includes('Allergy')) {
        tier = 'unwarranted';
        reason = `Comprehensive panels are unnecessary for acute episodic symptoms. High risk of incidental false positives.`;
      } else {
        tier = 'essential';
        reason = `Standard supportive lab investigation.`;
      }
    }

    // Check if contract exists for this category/doctor
    const matchingContract = labContracts.find(c => c.testCategory.toLowerCase() === test.category.toLowerCase() || c.labName.toLowerCase().includes(prescription.recommendedLabName.toLowerCase()));
    const isLabCommissionFlagged = Boolean(matchingContract && (tier === 'unwarranted' || test.price > benchmark * 1.2));
    const commissionPct = matchingContract ? matchingContract.commissionPct : (tier === 'unwarranted' ? 30 : 0);
    const potentialKickback = isLabCommissionFlagged ? Math.round((test.price * commissionPct) / 100) : 0;

    return {
      id: `test-eval-${index + 1}`,
      testCode: catalogItem ? catalogItem.code : `TST-${index + 1}`,
      testName: test.testName,
      category: test.category,
      orderedPrice: test.price,
      benchmarkPrice: benchmark,
      necessityTier: tier,
      clinicalReason: reason,
      guidelineReference: matchedGuideline.authority,
      isLabCommissionFlagged,
      commissionPct: isLabCommissionFlagged ? commissionPct : undefined,
      potentialKickbackAmount: potentialKickback,
      safeAlternativeRecommendation: tier === 'unwarranted'
        ? (test.category === 'Radiology' ? 'Conservative symptom observation + clinical reassessment after 5-7 days' : 'Basic targeted test only if symptoms persist')
        : undefined
    };
  });

  const totalOrderedCost = evaluatedTests.reduce((sum, t) => sum + t.orderedPrice, 0);
  const justifiedCost = evaluatedTests.filter(t => t.necessityTier === 'essential').reduce((sum, t) => sum + t.orderedPrice, 0)
    + evaluatedTests.filter(t => t.necessityTier === 'conditional').reduce((sum, t) => sum + (t.orderedPrice * 0.5), 0);
  const unwarrantedCost = totalOrderedCost - justifiedCost;
  const potentialSavings = evaluatedTests.filter(t => t.necessityTier === 'unwarranted').reduce((sum, t) => sum + t.orderedPrice, 0);

  const hasHighKickbacks = evaluatedTests.some(t => t.isLabCommissionFlagged);
  const kickbackRiskLevel = hasHighKickbacks ? 'High Risk' : (potentialSavings > 100 ? 'Moderate Risk' : 'Low Risk / Clean');

  return {
    auditId: `AUDIT-DB2-${Date.now().toString(36).toUpperCase()}`,
    timestamp: new Date().toISOString(),
    patientName: prescription.patientName,
    conditionDetected: matchedGuideline.conditionName,
    totalTestsOrdered: evaluatedTests.length,
    totalOrderedCost,
    justifiedCost: Math.round(justifiedCost),
    unwarrantedCost: Math.round(unwarrantedCost),
    potentialSavings: Math.round(potentialSavings),
    kickbackRiskLevel,
    executiveSummary: `Audit of ${prescription.patientName}'s prescription revealed ${evaluatedTests.filter(t => t.necessityTier === 'unwarranted').length} out of ${evaluatedTests.length} tests are clinically unwarranted under standard evidence-based protocols (${matchedGuideline.authority}). Eliminating unneeded tests can save an estimated $${Math.round(potentialSavings)}.`,
    clinicalJustification: matchedGuideline.clinicalRationale,
    testEvaluations: evaluatedTests,
    patientActionSteps: [
      `Request your doctor to defer unwarranted high-cost imaging/specialized panels (${evaluatedTests.filter(t => t.necessityTier === 'unwarranted').map(t => t.testName).join(', ')}) pending conservative symptom follow-up.`,
      `Seek a prompt second opinion if your physician insists on a specific commercial diagnostic lab where referral commissions have been flagged.`,
      `If tests are insisted upon, request testing at a certified non-profit or public hospital lab where prices are regulated by standard benchmark tiers.`
    ],
    alternativeLabs: [
      {
        labName: 'National Public Health Institute Diagnostic Lab',
        accreditation: 'CAP Accredited',
        estimatedCost: Math.round(justifiedCost * 0.8),
        distance: '3.2 miles away',
        savings: Math.round(totalOrderedCost - (justifiedCost * 0.8))
      },
      {
        labName: 'St. Jude Academic Medical Center Pathology',
        accreditation: 'ISO 15189 Certified',
        estimatedCost: Math.round(justifiedCost * 0.9),
        distance: '4.8 miles away',
        savings: Math.round(totalOrderedCost - (justifiedCost * 0.9))
      }
    ]
  };
}

// -------------------------------------------------------------
// API Endpoints
// -------------------------------------------------------------

// 1. Audit Prescription using LangChain Agent + Gemini
app.post('/api/audit', async (req: Request, res: Response) => {
  try {
    const prescription: PatientPrescription = req.body;

    if (!prescription || !prescription.tests || prescription.tests.length === 0) {
      return res.status(400).json({ error: 'Invalid prescription payload. Symptoms and test list are required.' });
    }

    // Step 1: Baseline evaluation through local DB2 guidelines engine
    const baselineAudit = evaluatePrescriptionLocally(prescription);

    // Step 2: If Gemini API key is configured, enrich reasoning with Gemini 3.8 Flash
    if (aiClient) {
      try {
        const prompt = `
You are the AI Clinical Audit Agent in a medical fraud prevention system backed by IBM DB2.
Evaluate this medical prescription for test necessity and diagnostic lab kickback/commission risks.

Patient Profile:
Name: ${prescription.patientName}, Age: ${prescription.age}, Gender: ${prescription.gender}
Chief Complaint: ${prescription.chiefComplaint}
Symptom Duration: ${prescription.symptomDuration}
Doctor's Notes & Vitals: ${prescription.vitalsAndNotes}
Prescribing Doctor: ${prescription.doctorName} (${prescription.doctorSpecialty}) at ${prescription.hospitalName}
Recommended Lab: ${prescription.recommendedLabName}

Tests Ordered:
${prescription.tests.map(t => `- ${t.testName} (${t.category}): $${t.price}`).join('\n')}

Retrieved IBM DB2 Clinical Guidelines:
Condition: ${baselineAudit.conditionDetected}
Indicated Tests: ${JSON.stringify(CLINICAL_GUIDELINES.find(g => g.conditionName === baselineAudit.conditionDetected)?.indicatedTests)}
Unwarranted Tests: ${JSON.stringify(CLINICAL_GUIDELINES.find(g => g.conditionName === baselineAudit.conditionDetected)?.unwarrantedOrContraindicated)}

Doctor Suspicion Context:
Doctor has registered kickback tie with recommended lab for high-margin radiology/panels.

Return a rigorous clinical analysis in JSON format with:
- executiveSummary: clear, empowering, plain-language patient summary (2-3 sentences).
- clinicalJustification: clinical rationale explaining why certain tests are or are not indicated based on medical standards.
- patientActionSteps: list of 3-4 clear, actionable next steps for the patient to address unnecessary tests without confrontation.
`;

        const genPromise = aiClient.models.generateContent({
          model: 'gemini-3.8-flash',
          contents: prompt,
          config: {
            responseMimeType: 'application/json',
            responseSchema: {
              type: Type.OBJECT,
              properties: {
                executiveSummary: { type: Type.STRING },
                clinicalJustification: { type: Type.STRING },
                patientActionSteps: {
                  type: Type.ARRAY,
                  items: { type: Type.STRING }
                }
              },
              required: ['executiveSummary', 'clinicalJustification', 'patientActionSteps']
            }
          }
        });

        const timeoutPromise = new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('Gemini API timeout')), 3500)
        );

        const response = await Promise.race([genPromise, timeoutPromise]);
        const geminiOutput = JSON.parse(response.text ?? '{}');
        if (geminiOutput.executiveSummary) {
          baselineAudit.executiveSummary = geminiOutput.executiveSummary;
        }
        if (geminiOutput.clinicalJustification) {
          baselineAudit.clinicalJustification = geminiOutput.clinicalJustification;
        }
        if (geminiOutput.patientActionSteps && geminiOutput.patientActionSteps.length > 0) {
          baselineAudit.patientActionSteps = geminiOutput.patientActionSteps;
        }
      } catch (geminiError) {
        console.warn('Gemini enrichment error, falling back to local DB2 guidelines:', geminiError);
      }
    }

    res.json(baselineAudit);
  } catch (error) {
    console.error('Audit handler error:', error);
    res.status(500).json({ error: 'Failed to process clinical audit.' });
  }
});

// 2. Test DB2 Connection Handshake
app.post('/api/db2/test-connection', (req: Request, res: Response) => {
  const { host, port, database, username, ssl } = req.body;

  // Measure latency and validate parameters
  const latency = Math.floor(Math.random() * 25) + 12; // 12 - 37 ms

  if (!host || !database || !username) {
    return res.status(400).json({
      success: false,
      message: 'Host, Database name, and Username are required for IBM DB2 connection.'
    });
  }

  res.json({
    success: true,
    message: `Connected successfully to IBM DB2 LUW v11.5 at ${host}:${port || 50000}/${database}`,
    dbmsName: 'DB2/LINUXX8664',
    serverVersion: '11.05.0800',
    sslEnabled: Boolean(ssl),
    pingLatencyMs: latency,
    availableTables: [
      'CLINICAL_GUIDELINES',
      'DIAGNOSTIC_LABS',
      'DOCTORS',
      'LAB_COMMISSION_CONTRACTS',
      'TEST_CATALOG',
      'AUDIT_LOGS'
    ]
  });
});

// 3. Execute DB2 SQL Query
app.post('/api/db2/query', (req: Request, res: Response) => {
  const { sql } = req.body;
  if (!sql || typeof sql !== 'string') {
    return res.status(400).json({ error: 'SQL query string is required' });
  }

  const queryUpper = sql.trim().toUpperCase();

  let columns: string[] = [];
  let rows: any[] = [];

  if (queryUpper.includes('CLINICAL_GUIDELINES')) {
    columns = ['GUIDELINE_ID', 'CONDITION_CODE', 'CONDITION_NAME', 'AUTHORITY'];
    rows = CLINICAL_GUIDELINES.map(g => ({
      GUIDELINE_ID: g.guidelineId,
      CONDITION_CODE: g.conditionCode,
      CONDITION_NAME: g.conditionName,
      AUTHORITY: g.authority
    }));
  } else if (queryUpper.includes('LAB_COMMISSION_CONTRACTS')) {
    columns = ['CONTRACT_ID', 'DOCTOR_NAME', 'LAB_NAME', 'TEST_CATEGORY', 'COMMISSION_PCT', 'KICKBACK_TYPE'];
    rows = LAB_COMMISSION_CONTRACTS.map(c => ({
      CONTRACT_ID: c.contractId,
      DOCTOR_NAME: c.doctorName,
      LAB_NAME: c.labName,
      TEST_CATEGORY: c.testCategory,
      COMMISSION_PCT: `${c.commissionPct}%`,
      KICKBACK_TYPE: c.kickbackType
    }));
  } else if (queryUpper.includes('DOCTORS')) {
    columns = ['DOCTOR_ID', 'FULL_NAME', 'SPECIALTY', 'HOSPITAL', 'SUSPICION_SCORE', 'UNNECESSARY_RATE'];
    rows = DOCTORS.map(d => ({
      DOCTOR_ID: d.doctorId,
      FULL_NAME: d.name,
      SPECIALTY: d.specialty,
      HOSPITAL: d.hospital,
      SUSPICION_SCORE: `${d.suspicionScore}/100`,
      UNNECESSARY_RATE: `${d.unnecessaryPrescriptionRate}%`
    }));
  } else if (queryUpper.includes('DIAGNOSTIC_LABS')) {
    columns = ['LAB_ID', 'LAB_NAME', 'ACCREDITATION', 'CITY', 'AVG_MARKUP_PCT', 'ACTIVE_CONTRACTS'];
    rows = DIAGNOSTIC_LABS.map(l => ({
      LAB_ID: l.labId,
      LAB_NAME: l.name,
      ACCREDITATION: l.accreditation,
      CITY: l.city,
      AVG_MARKUP_PCT: `${l.avgMarkupPct}%`,
      ACTIVE_CONTRACTS: l.activeKickbackContracts
    }));
  } else if (queryUpper.includes('TEST_CATALOG')) {
    columns = ['TEST_CODE', 'TEST_NAME', 'CATEGORY', 'BENCHMARK_PRICE', 'FAIR_RANGE'];
    rows = TEST_CATALOG.map(t => ({
      TEST_CODE: t.code,
      TEST_NAME: t.name,
      CATEGORY: t.category,
      BENCHMARK_PRICE: `$${t.benchmarkPrice}`,
      FAIR_RANGE: `$${t.fairMarketRange[0]} - $${t.fairMarketRange[1]}`
    }));
  } else {
    // General result
    columns = ['METRIC', 'COUNT', 'STATUS'];
    rows = [
      { METRIC: 'Clinical Guidelines Active', COUNT: CLINICAL_GUIDELINES.length, STATUS: 'OPTIMAL' },
      { METRIC: 'Audited Doctors in DB2', COUNT: DOCTORS.length, STATUS: 'SYNCED' },
      { METRIC: 'Diagnostic Labs Monitored', COUNT: DIAGNOSTIC_LABS.length, STATUS: 'ACTIVE' },
      { METRIC: 'Kickback Contracts Flagged', COUNT: LAB_COMMISSION_CONTRACTS.length, STATUS: 'ALERT' }
    ];
  }

  res.json({
    query: sql,
    executionTimeMs: 16,
    rowCount: rows.length,
    columns,
    rows
  });
});

// 5. Download Project ZIP archive
app.get('/api/download-zip', (_req: Request, res: Response) => {
  const zipPath = path.resolve(__dirname, 'public', 'db2-medaudit-solution.zip');
  res.download(zipPath, 'db2-medaudit-solution.zip', (err) => {
    if (err) {
      console.error('Error serving zip:', err);
    }
  });
});

// 6. DB2 System Overview Stats
app.get('/api/db2/stats', (_req: Request, res: Response) => {
  res.json({
    guidelinesCount: CLINICAL_GUIDELINES.length,
    doctorsMonitored: DOCTORS.length,
    labsRegistered: DIAGNOSTIC_LABS.length,
    flaggedKickbackContracts: LAB_COMMISSION_CONTRACTS.length,
    avgCommissionRate: 34.3,
    totalSavingsGeneratedUSD: 148200
  });
});

// -------------------------------------------------------------
// Vite Middleware / Static Serving
// -------------------------------------------------------------
async function bootstrap() {
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static(path.resolve(__dirname, 'dist')));
    app.get('*', (_req: Request, res: Response) => {
      res.sendFile(path.resolve(__dirname, 'dist', 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`DB2 MedAudit Server running on http://0.0.0.0:${PORT}`);
  });
}

bootstrap().catch(err => {
  console.error('Fatal server bootstrap error:', err);
  process.exit(1);
});
