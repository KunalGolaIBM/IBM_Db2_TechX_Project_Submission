import { ClinicalGuideline, DiagnosticLab, DoctorProfile, LabCommissionContract, PatientPrescription } from '../types/medaudit';

export const CLINICAL_GUIDELINES: ClinicalGuideline[] = [
  {
    guidelineId: 'CG-RESP-01',
    conditionCode: 'URI-VIRAL-01',
    conditionName: 'Acute Viral Upper Respiratory Infection (Common Cold / Pharyngitis)',
    authority: 'NICE Clinical Guidelines (CG69) & ICMR Standard Protocols',
    indicatedTests: [
      'Rapid Strep Antigen Test (if Centor score >= 3)',
      'Throat Culture (if bacterial tonsillitis suspected)',
      'Complete Blood Count (CBC) (only if prolonged fever > 7 days)'
    ],
    conditionalTests: [
      'Chest X-Ray PA View (only if focal lung crackles, dyspnea, or oxygen saturation < 94%)'
    ],
    unwarrantedOrContraindicated: [
      'Brain CT Scan',
      'Whole Body CT Scan',
      'Full Allergy IgE Blood Panel (30+ allergens)',
      'Whole Exome Genetic Sequencing',
      'Serum Procalcitonin (for uncomplicated outpatient cold)',
      'C-Reactive Protein (CRP) Quantitative (routine uncomplicated)'
    ],
    clinicalRationale: 'Uncomplicated upper respiratory symptoms with rhinorrhea and mild sore throat are self-limiting viral infections. Neuroimaging (CT/MRI) and broad allergy/genetic panels provide zero diagnostic utility and expose patients to unnecessary radiation and exorbitant out-of-pocket costs.'
  },
  {
    guidelineId: 'CG-NEURO-02',
    conditionCode: 'HA-TENSION-02',
    conditionName: 'Acute Episodic Tension-Type Headache / Mild Migraine',
    authority: 'American Academy of Neurology (AAN) & European Headache Federation',
    indicatedTests: [
      'Thorough Neurological Physical Examination',
      'Fundoscopy / Visual Acuity Exam (to rule out papilledema)'
    ],
    conditionalTests: [
      'Non-contrast Brain MRI / CT (strictly indicated ONLY if "Red Flags" exist: sudden thunderclap onset, focal neurological deficit, onset after age 50, systemic fever/stiff neck)'
    ],
    unwarrantedOrContraindicated: [
      'Contrast Brain MRI (without focal neurological signs)',
      'Cerebral Digital Subtraction Angiography (DSA)',
      'Extensive Heavy Metal Blood Toxicology Screen',
      'Comprehensive Autoimmune Antibody Battery (ANA, dsDNA)',
      'Cervical Spine Myelography'
    ],
    clinicalRationale: 'Neuroimaging is not warranted in patients with typical tension-type headaches and a normal neurological examination. Routine ordering of advanced imaging in absence of red flags is a recognized driver of defensive medicine and lab kickback generation.'
  },
  {
    guidelineId: 'CG-ORTHO-03',
    conditionCode: 'KNEE-SPRAIN-03',
    conditionName: 'Acute Grade 1 Knee Ligament Strain / Mild Meniscal Contusion',
    authority: 'American College of Radiology (ACR Appropriateness Criteria) & Ottawa Knee Rules',
    indicatedTests: [
      'Physical Ligament Stability Tests (Lachman, McMurray, Anterior Drawer)',
      'Plain Radiograph (Knee X-Ray AP/Lateral - only if Ottawa Knee Rules criteria positive)'
    ],
    conditionalTests: [
      'Knee MRI (only if persistent mechanical locking, gross joint instability, or failure to improve after 4-6 weeks conservative management)'
    ],
    unwarrantedOrContraindicated: [
      'Immediate 3T High-Resolution Knee MRI with Intravenous Gadolinium',
      'Whole Body Bone Scintigraphy (DEXA / SPECT)',
      'Extensive Rheumatoid Factor & HLA-B27 Genetic Panel (in isolated traumatic athletic strain)',
      'Diagnostic Arthroscopy referral prior to conservative trial'
    ],
    clinicalRationale: 'Isolated athletic knee sprains in young patients should initially be managed with RICE therapy (Rest, Ice, Compression, Elevation) and rehabilitation. Immediate expensive contrast MRI yields incidental benign findings and inflates lab bills without altering acute management.'
  },
  {
    guidelineId: 'CG-GASTRO-04',
    conditionCode: 'GI-DYSPEPSIA-04',
    conditionName: 'Uncomplicated Dyspepsia / Gastroesophageal Reflux Disease (GERD) in adults < 45',
    authority: 'American Gastroenterological Association (AGA) & British Society of Gastroenterology',
    indicatedTests: [
      'Helicobacter Pylori Stool Antigen Test or Urea Breath Test',
      'Basic Complete Blood Count (to screen for occult anemia)'
    ],
    conditionalTests: [
      'Upper GI Endoscopy (EGD) (reserved for age > 50 or alarm symptoms: dysphagia, unintentional weight loss, recurrent vomiting)'
    ],
    unwarrantedOrContraindicated: [
      'Immediate Contrast-Enhanced Abdominal CT Scan',
      'Full Food Allergen Elimination IgG/IgE Blood Panel',
      'Gastric Emptying Radio-Scintigraphy (without gastroparesis symptoms)',
      'Comprehensive Tumor Marker Battery (CEA, CA 19-9, AFP in young non-high-risk patients)'
    ],
    clinicalRationale: 'Young patients presenting with typical reflux or dyspepsia should be managed with lifestyle modification, H. pylori testing, and empiric PPI therapy. Directing them to immediate multi-slice abdominal CT scans or tumor markers is unwarranted and heavily prone to kickback arrangements.'
  },
  {
    guidelineId: 'CG-DIAB-05',
    conditionCode: 'DM-TYPE2-NEW-05',
    conditionName: 'Newly Diagnosed Type 2 Diabetes Mellitus (HbA1c 6.5–8.5%, No Complications)',
    authority: 'American Diabetes Association (ADA Standards of Care 2024) & WHO Diabetes Programme',
    indicatedTests: [
      'HbA1c (Glycated Haemoglobin)',
      'Fasting Plasma Glucose',
      'Serum Creatinine & eGFR',
      'Urine Albumin-to-Creatinine Ratio (UACR)',
      'Fasting Lipid Profile',
      'Resting ECG (if age > 40 or cardiac risk factors)',
      'Dilated Fundoscopy at baseline'
    ],
    conditionalTests: [
      'Thyroid Function Tests (TSH) — if symptoms of thyroid dysfunction',
      'Liver Function Tests (LFT) — if starting metformin with hepatic risk'
    ],
    unwarrantedOrContraindicated: [
      'Coronary CT Angiography (CCTA) — in asymptomatic newly diagnosed without cardiac symptoms',
      'Comprehensive Whole Exome Genetic Panel — for standard T2DM without MODY suspicion',
      'Brain MRI / Cognitive Battery — in uncomplicated newly diagnosed diabetes',
      'Gastric Emptying Scintigraphy — without symptoms of gastroparesis'
    ],
    clinicalRationale: 'Newly diagnosed Type 2 Diabetes requires a focused baseline metabolic, renal, lipid, and ophthalmological work-up per ADA standards. Advanced cardiac imaging and genetic sequencing in the absence of clinical indication generate no actionable diagnostic change and represent a documented high-value kickback opportunity in diabetology practices.'
  },
  {
    guidelineId: 'CG-CARD-06',
    conditionCode: 'CARD-PALPITATION-06',
    conditionName: 'Intermittent Palpitations with Normal Resting ECG (Age < 45, No Structural Heart Disease)',
    authority: 'European Heart Rhythm Association (EHRA) & Heart Rhythm Society (HRS) Consensus 2023',
    indicatedTests: [
      'Resting 12-Lead ECG',
      'Holter Monitor (24–48 hour ambulatory ECG)',
      'Serum Electrolytes (K+, Mg2+)',
      'Thyroid Function Tests (TSH, Free T4)',
      'Complete Blood Count (CBC) — to rule out anaemia-related palpitations'
    ],
    conditionalTests: [
      '2D Transthoracic Echocardiogram — if ECG shows pre-excitation, LBBB, or structural abnormality suspected',
      'Event Monitor / Implantable Loop Recorder — if palpitations infrequent and Holter non-diagnostic'
    ],
    unwarrantedOrContraindicated: [
      'Cardiac MRI with Gadolinium — without structural disease on Echo',
      'Coronary CT Angiography (CCTA) — without anginal symptoms or ischaemia evidence',
      'Electrophysiology Study (EPS) — as first-line in non-sustained low-risk palpitations',
      'Cardiac PET Perfusion Scan'
    ],
    clinicalRationale: 'Palpitations in young adults with normal resting ECG are overwhelmingly benign ectopic beats. A structured 24-48hr Holter monitor with basic metabolic and thyroid testing identifies clinically significant arrhythmias in 95% of cases. Cardiac MRI or CCTA without structural evidence represents overutilization driven by imaging center referral incentives.'
  },
  {
    guidelineId: 'CG-CARD-05',
    conditionCode: 'CARD-HTN-05',
    conditionName: 'Essential Hypertension (Routine Stage 1 Follow-Up)',
    authority: 'AHA / ACC / ESC Hypertension Guidelines',
    indicatedTests: [
      'Resting 12-Lead Electrocardiogram (ECG)',
      'Serum Electrolytes (Sodium, Potassium)',
      'Serum Creatinine & Estimated GFR',
      'Fasting Blood Glucose / HbA1c',
      'Lipid Profile',
      'Dipstick Urinalysis'
    ],
    conditionalTests: [
      'Transthoracic Echocardiogram (Echo) (if ECG suggests left ventricular hypertrophy or heart murmur heard)'
    ],
    unwarrantedOrContraindicated: [
      'Coronary CT Angiography (CCTA) (in asymptomatic low-risk routine hypertension)',
      'Cardiac Stress Thallium / PET Perfusion Scan',
      'Renal Artery Doppler Ultrasound (unless refractory hypertension on 3+ drugs)',
      'Plasma Free Metanephrines & 24hr Urinary Catecholamines (without episodic adrenergic spells)'
    ],
    clinicalRationale: 'Asymptomatic stage 1 hypertension requires baseline metabolic, renal, and simple ECG monitoring. Ordering invasive or expensive coronary imaging without anginal symptoms is clinically inappropriate.'
  }
];

export const TEST_CATALOG: Array<{
  code: string;
  name: string;
  category: 'Radiology' | 'Biochemistry' | 'Pathology' | 'Genetics' | 'Cardiology';
  benchmarkPrice: number;
  fairMarketRange: [number, number];
}> = [
  { code: 'RAD-CT-BRN', name: 'Brain CT Scan (Plain + Contrast)', category: 'Radiology', benchmarkPrice: 180, fairMarketRange: [120, 220] },
  { code: 'RAD-MRI-BRN', name: 'Brain MRI with Contrast', category: 'Radiology', benchmarkPrice: 320, fairMarketRange: [240, 380] },
  { code: 'RAD-MRI-KNE', name: '3T Knee MRI with Contrast', category: 'Radiology', benchmarkPrice: 350, fairMarketRange: [250, 420] },
  { code: 'RAD-XR-CHEST', name: 'Chest X-Ray PA View', category: 'Radiology', benchmarkPrice: 25, fairMarketRange: [18, 35] },
  { code: 'RAD-CT-ABD', name: 'Whole Abdomen CT with IV Contrast', category: 'Radiology', benchmarkPrice: 280, fairMarketRange: [200, 340] },
  { code: 'RAD-CCTA', name: 'Coronary CT Angiography (64-Slice)', category: 'Radiology', benchmarkPrice: 420, fairMarketRange: [320, 500] },
  { code: 'BIO-CBC', name: 'Complete Blood Count (CBC) with Automated Differential', category: 'Pathology', benchmarkPrice: 15, fairMarketRange: [10, 22] },
  { code: 'BIO-STREP', name: 'Rapid Strep Antigen Test', category: 'Pathology', benchmarkPrice: 22, fairMarketRange: [15, 30] },
  { code: 'BIO-ALLERGY', name: 'Full Blood Allergy IgE Battery (32 Allergens Panel)', category: 'Biochemistry', benchmarkPrice: 195, fairMarketRange: [140, 240] },
  { code: 'BIO-HPYLORI', name: 'H. Pylori Stool Antigen Assay', category: 'Pathology', benchmarkPrice: 35, fairMarketRange: [25, 45] },
  { code: 'BIO-MET-GEN', name: 'Comprehensive Whole Exome Metabolic Panel', category: 'Genetics', benchmarkPrice: 480, fairMarketRange: [350, 600] },
  { code: 'BIO-TUMOR', name: 'Multiplex Tumor Marker Battery (CEA, CA-125, PSA, AFP)', category: 'Biochemistry', benchmarkPrice: 210, fairMarketRange: [150, 260] },
  { code: 'BIO-LIPID', name: 'Fasting Lipid Profile', category: 'Biochemistry', benchmarkPrice: 25, fairMarketRange: [18, 35] },
  { code: 'BIO-KFT', name: 'Renal Function Test (BUN, Creatinine, Electrolytes)', category: 'Biochemistry', benchmarkPrice: 28, fairMarketRange: [20, 38] },
  { code: 'CARD-ECG', name: 'Resting 12-Lead Electrocardiogram', category: 'Cardiology', benchmarkPrice: 20, fairMarketRange: [15, 30] },
  { code: 'CARD-ECHO', name: '2D Transthoracic Echocardiogram', category: 'Cardiology', benchmarkPrice: 95, fairMarketRange: [70, 130] },
  { code: 'BIO-THYROID-AB', name: 'Thyroid Auto-Antibody Screen (Anti-TPO, Anti-Tg)', category: 'Biochemistry', benchmarkPrice: 90, fairMarketRange: [65, 115] }
];

export const DIAGNOSTIC_LABS: DiagnosticLab[] = [
  {
    labId: 'LAB-METRO-01',
    name: 'MetroScan Premium Diagnostics & Advanced Imaging',
    accreditation: 'NABL',
    city: 'Metro Medical Hub',
    avgMarkupPct: 55,
    activeKickbackContracts: 14
  },
  {
    labId: 'LAB-CITI-02',
    name: 'Apex Horizon Clinical Laboratories & Scan Center',
    accreditation: 'Unaccredited',
    city: 'North Clinic District',
    avgMarkupPct: 70,
    activeKickbackContracts: 22
  },
  {
    labId: 'LAB-CIVIC-03',
    name: 'National Public Health Institute Diagnostic Lab',
    accreditation: 'CAP',
    city: 'Central Civic District',
    avgMarkupPct: 0,
    activeKickbackContracts: 0
  },
  {
    labId: 'LAB-TRUST-04',
    name: 'St. Jude Academic Medical Center Pathology',
    accreditation: 'ISO 15189',
    city: 'Academic Health Corridor',
    avgMarkupPct: 8,
    activeKickbackContracts: 0
  },
  {
    labId: 'LAB-SUGAR-05',
    name: 'GlucoMax Specialty Diagnostics & Genomics Center',
    accreditation: 'NABL',
    city: 'Diabetes Care District',
    avgMarkupPct: 62,
    activeKickbackContracts: 18
  },
  {
    labId: 'LAB-HEART-06',
    name: 'CardioVision Advanced Cardiac Imaging Suite',
    accreditation: 'Unaccredited',
    city: 'Cardiac Sciences Hub',
    avgMarkupPct: 80,
    activeKickbackContracts: 11
  }
];

export const DOCTORS: DoctorProfile[] = [
  {
    doctorId: 'DOC-SHARMA-101',
    name: 'Dr. Rajesh K. Sharma',
    specialty: 'Internal Medicine & General Practice',
    hospital: 'Apex Care Polyclinic',
    suspicionScore: 88,
    activeContractsCount: 3,
    totalPrescriptionsAudited: 420,
    unnecessaryPrescriptionRate: 64.2
  },
  {
    doctorId: 'DOC-MEHTA-102',
    name: 'Dr. Vivek Mehta',
    specialty: 'Orthopedics & Sports Medicine',
    hospital: 'Elite Bone & Joint Institute',
    suspicionScore: 82,
    activeContractsCount: 2,
    totalPrescriptionsAudited: 310,
    unnecessaryPrescriptionRate: 58.7
  },
  {
    doctorId: 'DOC-IYER-103',
    name: 'Dr. Anandita Iyer',
    specialty: 'Family Medicine',
    hospital: 'Community Health Trust',
    suspicionScore: 12,
    activeContractsCount: 0,
    totalPrescriptionsAudited: 512,
    unnecessaryPrescriptionRate: 7.4
  },
  {
    doctorId: 'DOC-KAPOOR-104',
    name: 'Dr. Sanjay Kapoor',
    specialty: 'Neurology & Pain Specialist',
    hospital: 'Metro Neuro Sciences Clinic',
    suspicionScore: 76,
    activeContractsCount: 2,
    totalPrescriptionsAudited: 280,
    unnecessaryPrescriptionRate: 51.5
  },
  {
    doctorId: 'DOC-REDDY-105',
    name: 'Dr. Preethi Reddy',
    specialty: 'Diabetology & Endocrinology',
    hospital: 'SugarCare Diabetes & Metabolic Clinic',
    suspicionScore: 91,
    activeContractsCount: 4,
    totalPrescriptionsAudited: 490,
    unnecessaryPrescriptionRate: 72.8
  },
  {
    doctorId: 'DOC-BOSE-106',
    name: 'Dr. Aniket Bose',
    specialty: 'Cardiology',
    hospital: 'HeartFirst Cardiac Sciences',
    suspicionScore: 68,
    activeContractsCount: 2,
    totalPrescriptionsAudited: 188,
    unnecessaryPrescriptionRate: 44.1
  },
  {
    doctorId: 'DOC-NAIR-107',
    name: 'Dr. Meera Nair',
    specialty: 'General Practice & Preventive Medicine',
    hospital: 'Greenfield Community Clinic',
    suspicionScore: 8,
    activeContractsCount: 0,
    totalPrescriptionsAudited: 634,
    unnecessaryPrescriptionRate: 4.2
  }
];

export const LAB_COMMISSION_CONTRACTS: LabCommissionContract[] = [
  {
    contractId: 'KICK-2025-01',
    doctorId: 'DOC-SHARMA-101',
    doctorName: 'Dr. Rajesh K. Sharma',
    labId: 'LAB-METRO-01',
    labName: 'MetroScan Premium Diagnostics & Advanced Imaging',
    testCategory: 'Radiology',
    commissionPct: 35.0,
    kickbackType: 'Direct Fee Per Referral',
    lastAuditDate: '2026-08-15'
  },
  {
    contractId: 'KICK-2025-02',
    doctorId: 'DOC-SHARMA-101',
    doctorName: 'Dr. Rajesh K. Sharma',
    labId: 'LAB-CITI-02',
    labName: 'Apex Horizon Clinical Laboratories & Scan Center',
    testCategory: 'Biochemistry',
    commissionPct: 30.0,
    kickbackType: 'End-of-Month Volume Rebate',
    lastAuditDate: '2026-09-02'
  },
  {
    contractId: 'KICK-2025-03',
    doctorId: 'DOC-MEHTA-102',
    doctorName: 'Dr. Vivek Mehta',
    labId: 'LAB-METRO-01',
    labName: 'MetroScan Premium Diagnostics & Advanced Imaging',
    testCategory: 'Radiology',
    commissionPct: 40.0,
    kickbackType: 'Direct Fee Per Referral',
    lastAuditDate: '2026-09-18'
  },
  {
    contractId: 'KICK-2025-04',
    doctorId: 'DOC-KAPOOR-104',
    doctorName: 'Dr. Sanjay Kapoor',
    labId: 'LAB-CITI-02',
    labName: 'Apex Horizon Clinical Laboratories & Scan Center',
    testCategory: 'Radiology',
    commissionPct: 32.5,
    kickbackType: 'Sponsored Conference / Gift',
    lastAuditDate: '2026-07-28'
  },
  {
    contractId: 'KICK-2025-05',
    doctorId: 'DOC-REDDY-105',
    doctorName: 'Dr. Preethi Reddy',
    labId: 'LAB-SUGAR-05',
    labName: 'GlucoMax Specialty Diagnostics & Genomics Center',
    testCategory: 'Genetics',
    commissionPct: 45.0,
    kickbackType: 'Direct Fee Per Referral',
    lastAuditDate: '2026-10-05'
  },
  {
    contractId: 'KICK-2025-06',
    doctorId: 'DOC-REDDY-105',
    doctorName: 'Dr. Preethi Reddy',
    labId: 'LAB-METRO-01',
    labName: 'MetroScan Premium Diagnostics & Advanced Imaging',
    testCategory: 'Radiology',
    commissionPct: 38.0,
    kickbackType: 'End-of-Month Volume Rebate',
    lastAuditDate: '2026-10-12'
  },
  {
    contractId: 'KICK-2025-07',
    doctorId: 'DOC-BOSE-106',
    doctorName: 'Dr. Aniket Bose',
    labId: 'LAB-HEART-06',
    labName: 'CardioVision Advanced Cardiac Imaging Suite',
    testCategory: 'Cardiology',
    commissionPct: 42.0,
    kickbackType: 'Direct Fee Per Referral',
    lastAuditDate: '2026-09-30'
  }
];

export const CLINICAL_PRESETS: PatientPrescription[] = [
  {
    patientName: 'Priya Nambiar',
    age: 29,
    gender: 'Female',
    chiefComplaint: 'Sore throat, runny nose, and low-grade temperature (37.8°C) for 3 days',
    symptomDuration: '3 days',
    vitalsAndNotes: 'BP 118/76, HR 74, SpO2 99% on room air. Erythematous posterior pharynx, no tonsillar exudates, no cervical lymphadenopathy. Clear chest auscultation.',
    doctorName: 'Dr. Rajesh K. Sharma',
    doctorSpecialty: 'Internal Medicine & General Practice',
    hospitalName: 'Apex Care Polyclinic',
    recommendedLabName: 'MetroScan Premium Diagnostics & Advanced Imaging',
    tests: [
      { testName: 'Rapid Strep Antigen Test', category: 'Pathology', price: 30 },
      { testName: 'Complete Blood Count (CBC) with Automated Differential', category: 'Pathology', price: 25 },
      { testName: 'Brain CT Scan (Plain + Contrast)', category: 'Radiology', price: 280 },
      { testName: 'Full Blood Allergy IgE Battery (32 Allergens Panel)', category: 'Biochemistry', price: 260 },
      { testName: 'Comprehensive Whole Exome Metabolic Panel', category: 'Genetics', price: 540 }
    ]
  },
  {
    patientName: 'Karan Malhotra',
    age: 26,
    gender: 'Male',
    chiefComplaint: 'Mild right knee twist after recreational football yesterday; ambulatory, mild swelling',
    symptomDuration: '24 hours',
    vitalsAndNotes: 'Able to bear weight and walk 6 steps in clinic. No patellar tenderness, no fibular head tenderness, flexion to 110 degrees. Mild joint effusion, negative anterior drawer test.',
    doctorName: 'Dr. Vivek Mehta',
    doctorSpecialty: 'Orthopedics & Sports Medicine',
    hospitalName: 'Elite Bone & Joint Institute',
    recommendedLabName: 'MetroScan Premium Diagnostics & Advanced Imaging',
    tests: [
      { testName: '3T Knee MRI with Contrast', category: 'Radiology', price: 420 },
      { testName: 'Multiplex Tumor Marker Battery (CEA, CA-125, PSA, AFP)', category: 'Biochemistry', price: 280 },
      { testName: 'Thyroid Auto-Antibody Screen (Anti-TPO, Anti-Tg)', category: 'Biochemistry', price: 120 }
    ]
  },
  {
    patientName: 'Arjun Sen',
    age: 38,
    gender: 'Male',
    chiefComplaint: 'Bilateral band-like squeezing head pressure after long hours at computer screens',
    symptomDuration: '5 days',
    vitalsAndNotes: 'BP 122/80, normal fundoscopy, no cranial nerve palsy, normal gait. No nausea, photophobia, or visual aura. Relieved partially by acetaminophen.',
    doctorName: 'Dr. Sanjay Kapoor',
    doctorSpecialty: 'Neurology & Pain Specialist',
    hospitalName: 'Metro Neuro Sciences Clinic',
    recommendedLabName: 'Apex Horizon Clinical Laboratories & Scan Center',
    tests: [
      { testName: 'Brain MRI with Contrast', category: 'Radiology', price: 380 },
      { testName: 'Whole Abdomen CT with IV Contrast', category: 'Radiology', price: 340 },
      { testName: 'Full Blood Allergy IgE Battery (32 Allergens Panel)', category: 'Biochemistry', price: 250 }
    ]
  },
  {
    patientName: 'Sunita Desai',
    age: 44,
    gender: 'Female',
    chiefComplaint: 'Newly diagnosed diabetes (HbA1c 7.2%). Referred for baseline screening panel.',
    symptomDuration: '2 weeks since diagnosis',
    vitalsAndNotes: 'BMI 27.4, BP 128/82, HR 78, no retinopathy on fundoscopy. Asymptomatic. No family history of cardiac disease. eGFR 88.',
    doctorName: 'Dr. Preethi Reddy',
    doctorSpecialty: 'Diabetology & Endocrinology',
    hospitalName: 'SugarCare Diabetes & Metabolic Clinic',
    recommendedLabName: 'GlucoMax Specialty Diagnostics & Genomics Center',
    tests: [
      { testName: 'HbA1c (Glycated Haemoglobin)', category: 'Biochemistry', price: 35 },
      { testName: 'Fasting Lipid Profile', category: 'Biochemistry', price: 28 },
      { testName: 'Renal Function Test (BUN, Creatinine, Electrolytes)', category: 'Biochemistry', price: 32 },
      { testName: 'Coronary CT Angiography (64-Slice)', category: 'Radiology', price: 520 },
      { testName: 'Comprehensive Whole Exome Metabolic Panel', category: 'Genetics', price: 680 },
      { testName: 'Multiplex Tumor Marker Battery (CEA, CA-125, PSA, AFP)', category: 'Biochemistry', price: 310 }
    ]
  },
  {
    patientName: 'Rohan Pillai',
    age: 33,
    gender: 'Male',
    chiefComplaint: 'Occasional heart palpitations — 10–15 second episodes of "fluttering" 2–3 times per week. No syncope.',
    symptomDuration: '3 weeks',
    vitalsAndNotes: 'Normal resting 12-lead ECG. HR 72 bpm, BP 120/78. No murmur, no peripheral oedema. No exertional dyspnoea. No family history of sudden cardiac death.',
    doctorName: 'Dr. Aniket Bose',
    doctorSpecialty: 'Cardiology',
    hospitalName: 'HeartFirst Cardiac Sciences',
    recommendedLabName: 'CardioVision Advanced Cardiac Imaging Suite',
    tests: [
      { testName: 'Resting 12-Lead Electrocardiogram', category: 'Cardiology', price: 28 },
      { testName: 'Resting 12-Lead Electrocardiogram', category: 'Cardiology', price: 28 },
      { testName: 'Cardiac MRI with Gadolinium Contrast', category: 'Radiology', price: 580 },
      { testName: 'Coronary CT Angiography (64-Slice)', category: 'Radiology', price: 490 },
      { testName: 'Full Blood Allergy IgE Battery (32 Allergens Panel)', category: 'Biochemistry', price: 240 }
    ]
  }
];

export const DB2_DDL_SCRIPT = `-- ==============================================================
-- IBM DB2 LUW (Linux, UNIX, Windows) DDL SCHEMA SCRIPT
-- DATABASE: MEDAUDIT
-- SCHEMA: CLINICAL_INTELLIGENCE
-- ==============================================================

-- 1. Create Bufferpool and Tablespace
CREATE BUFFERPOOL BP_MEDAUDIT SIZE 5000 PAGESIZE 8K;
CREATE TABLESPACE TS_MEDAUDIT PAGESIZE 8K MANAGED BY AUTOMATIC STORAGE BUFFERPOOL BP_MEDAUDIT;

-- 2. Evidence-Based Clinical Guidelines
CREATE TABLE CLINICAL_GUIDELINES (
    GUIDELINE_ID VARCHAR(32) NOT NULL,
    CONDITION_CODE VARCHAR(32) NOT NULL,
    CONDITION_NAME VARCHAR(128) NOT NULL,
    AUTHORITY VARCHAR(64) NOT NULL,
    INDICATED_TESTS CLOB(10K),
    CONDITIONAL_TESTS CLOB(10K),
    UNWARRANTED_TESTS CLOB(10K),
    CLINICAL_RATIONALE CLOB(30K),
    UPDATED_TIMESTAMP TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT PK_GUIDELINE PRIMARY KEY (GUIDELINE_ID)
) IN TS_MEDAUDIT;

CREATE INDEX IDX_GUIDE_COND ON CLINICAL_GUIDELINES(CONDITION_CODE);

-- 3. Diagnostic Laboratories Registry
CREATE TABLE DIAGNOSTIC_LABS (
    LAB_ID VARCHAR(32) NOT NULL,
    LAB_NAME VARCHAR(128) NOT NULL,
    ACCREDITATION VARCHAR(32) NOT NULL,
    CITY VARCHAR(64) NOT NULL,
    AVG_MARKUP_PCT DECIMAL(5,2) DEFAULT 0.00,
    ACTIVE_KICKBACK_CONTRACTS INT DEFAULT 0,
    CREATED_TIMESTAMP TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT PK_DIAG_LAB PRIMARY KEY (LAB_ID)
) IN TS_MEDAUDIT;

-- 4. Physician Profiles & Suspicion Scoring
CREATE TABLE DOCTORS (
    DOCTOR_ID VARCHAR(32) NOT NULL,
    FULL_NAME VARCHAR(128) NOT NULL,
    SPECIALTY VARCHAR(64) NOT NULL,
    HOSPITAL_AFFILIATION VARCHAR(128),
    SUSPICION_SCORE DECIMAL(5,2) DEFAULT 0.00,
    PRESCRIPTIONS_AUDITED INT DEFAULT 0,
    UNNECESSARY_ORDER_RATE DECIMAL(5,2) DEFAULT 0.00,
    CONSTRAINT PK_DOCTOR PRIMARY KEY (DOCTOR_ID)
) IN TS_MEDAUDIT;

CREATE INDEX IDX_DOC_SUSP ON DOCTORS(SUSPICION_SCORE DESC);

-- 5. Lab Referral & Commission Contracts (Kickback Tracking)
CREATE TABLE LAB_COMMISSION_CONTRACTS (
    CONTRACT_ID VARCHAR(32) NOT NULL,
    DOCTOR_ID VARCHAR(32) NOT NULL,
    LAB_ID VARCHAR(32) NOT NULL,
    TEST_CATEGORY VARCHAR(64) NOT NULL,
    COMMISSION_PCT DECIMAL(5,2) NOT NULL,
    KICKBACK_TYPE VARCHAR(64) NOT NULL,
    LAST_AUDITED_DATE DATE NOT NULL,
    IS_ACTIVE CHAR(1) DEFAULT 'Y',
    CONSTRAINT PK_CONTRACT PRIMARY KEY (CONTRACT_ID),
    CONSTRAINT FK_CONTRACT_DOC FOREIGN KEY (DOCTOR_ID) REFERENCES DOCTORS(DOCTOR_ID) ON DELETE CASCADE,
    CONSTRAINT FK_CONTRACT_LAB FOREIGN KEY (LAB_ID) REFERENCES DIAGNOSTIC_LABS(LAB_ID) ON DELETE CASCADE
) IN TS_MEDAUDIT;

CREATE INDEX IDX_COMMISSION_RATE ON LAB_COMMISSION_CONTRACTS(COMMISSION_PCT DESC);

-- 6. Standard Diagnostic Test Catalog
CREATE TABLE TEST_CATALOG (
    TEST_CODE VARCHAR(32) NOT NULL,
    TEST_NAME VARCHAR(128) NOT NULL,
    CATEGORY VARCHAR(32) NOT NULL,
    BENCHMARK_PRICE DECIMAL(10,2) NOT NULL,
    FAIR_MIN_PRICE DECIMAL(10,2) NOT NULL,
    FAIR_MAX_PRICE DECIMAL(10,2) NOT NULL,
    CONSTRAINT PK_TEST_CATALOG PRIMARY KEY (TEST_CODE)
) IN TS_MEDAUDIT;

-- 7. Patient Encounter & Prescription Audit Logs
CREATE TABLE AUDIT_LOGS (
    AUDIT_ID VARCHAR(32) NOT NULL,
    PATIENT_PSEUDONYM VARCHAR(64) NOT NULL,
    CHIEF_COMPLAINT VARCHAR(256),
    DETECTED_CONDITION VARCHAR(128),
    DOCTOR_ID VARCHAR(32),
    LAB_ID VARCHAR(32),
    TOTAL_ORDERED_COST DECIMAL(10,2) NOT NULL,
    JUSTIFIED_COST DECIMAL(10,2) NOT NULL,
    UNWARRANTED_COST DECIMAL(10,2) NOT NULL,
    POTENTIAL_SAVINGS DECIMAL(10,2) NOT NULL,
    KICKBACK_ALERT CHAR(1) DEFAULT 'N',
    AUDIT_TIMESTAMP TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
    CONSTRAINT PK_AUDIT_LOG PRIMARY KEY (AUDIT_ID)
) IN TS_MEDAUDIT;

CREATE INDEX IDX_AUDIT_SAVINGS ON AUDIT_LOGS(POTENTIAL_SAVINGS DESC);

COMMIT;
`;
