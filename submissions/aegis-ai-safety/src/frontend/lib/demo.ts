// Clearly labelled synthetic demonstration. Fictional data only.
// The demo exercises the real extraction -> retrieval -> verification pipeline.

export const DEMO_EVIDENCE_TITLE = "Synthetic demo — SolarCell-X trial (fictional)";

export const DEMO_RESEARCH_TEXT =
  "SolarCell-X achieved a conversion efficiency of 92% under standard test conditions. " +
  "The dual-layer anti-reflective coating reduced manufacturing cost by 40% compared with the baseline production process. " +
  "SolarCell-X cells retained 95% of their initial efficiency after five years of outdoor operation.";

export const DEMO_EVIDENCE_TEXT = `AEGIS SYNTHETIC EVALUATION DOCUMENT
FICTIONAL DATA — created for pipeline demonstration only. Not a real study.

Title: SolarCell-X Controlled Efficiency Trial (2024)

In the 2024 controlled trial, SolarCell-X achieved a photovoltaic conversion efficiency of 92% under standard test conditions (AM1.5G spectrum, 25 degrees Celsius). The measurement covered 40 independent cells, and the reported value is the median of those measurements. The trial was conducted indoors with a calibrated solar simulator.

The dual-layer anti-reflective coating reduced manufacturing cost by 15% compared with the baseline production process. The coating did not change the measured conversion efficiency. Cost figures cover materials and deposition steps only; installation and maintenance costs were outside the scope of the trial.

The trial did not evaluate performance under high-humidity or desert conditions. No field deployment data were collected, and no long-term degradation testing was performed. The authors state that outdoor performance remains unknown.

A separate thermal stability test measured a 2% efficiency loss after 500 hours at 60 degrees Celsius. That test used a different cell batch and is not directly comparable to the main efficiency result.`;

// Real-paper demonstration. The evidence documents are the actual arXiv PDFs,
// downloaded and ingested with `make demo-papers`; these claims are synthetic.
export const PAPER_DEMO_TITLES = [
  "Attention Is All You Need",
  "BERT: Pre-training of Deep Bidirectional Transformers",
];

export const PAPER_DEMO_RESPONSE =
  "The Transformer achieved 28.4 BLEU on the WMT 2014 English-to-German translation task. " +
  "The Transformer encoder consists of 8 identical layers. " +
  "BERT is pre-trained with a unidirectional language model rather than a bidirectional one. " +
  "The Transformer reduced inference latency on mobile devices by 50%.";
