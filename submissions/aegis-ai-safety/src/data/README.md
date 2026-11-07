# Data and Samples

## Synthetic evidence

`synthetic_solarcell_study.txt` and `synthetic_research_text.txt` are fictional
SolarCell-X materials created for AEGIS testing. Every document says it is synthetic.
They are not derived from a real study.

## Paper demo

`paper_demo_response.txt` is an AI-generated-style summary written for the
demonstration. Its claims are constructed to exercise four outcomes:

- supported
- contradicted
- contradicted with a numeric discrepancy
- insufficient evidence

The evidence for this demo is two real arXiv papers:

- *Attention Is All You Need* — https://arxiv.org/abs/1706.03762
- *BERT: Pre-training of Deep Bidirectional Transformers* — https://arxiv.org/abs/1810.04805

The PDFs are **not redistributed** in this repository. `make demo-papers` downloads
them into `data/samples/papers/`, which is gitignored, and ingests them into Db2.
Review each paper's arXiv license/terms before redistributing the PDFs.

## Dataset policy

- Demo/synthetic content is clearly labelled.
- No benchmark labels are used as verifier inputs.
- SciFact (CC BY-NC 2.0) is not bundled; see `experiments/scifact_manifest.json`.
- No benchmark score is claimed unless a real evaluation file exists under
  `experiments/results/`.
