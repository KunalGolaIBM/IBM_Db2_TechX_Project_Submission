# AEGIS Demonstration

## Two demos

| Demo | Evidence | Purpose |
| --- | --- | --- |
| **Paper demo** | Real arXiv PDFs: *Attention Is All You Need* and *BERT* | Default P0 demonstration with actual source text, page numbers, and a numeric discrepancy |
| **Synthetic demo** | Fictional SolarCell-X study | Offline/fallback demonstration with clearly synthetic evidence |

The paper demo is the primary controlled example. The research response is an
AI-generated-style summary written for the demo; the evidence is the real published
paper text. No classification is hardcoded, and the same pipeline accepts new inputs.

## Prepare the paper demo

```bash
make demo-papers
```

This downloads:

- https://arxiv.org/pdf/1706.03762v7
- https://arxiv.org/pdf/1810.04805v2

into `data/samples/papers/` and ingests them into Db2 with PyMuPDF. The PDFs are not
committed to the repository.

You can also upload the two PDFs through the UI. Then click **Paper demo** to select
the matching documents in the library.

## Controlled claims

| # | Claim | Expected outcome | Evidence |
| --- | --- | --- | --- |
| 1 | The Transformer achieved 28.4 BLEU on WMT 2014 English-to-German. | `SUPPORTED` | Attention paper, p. 8 |
| 2 | The Transformer encoder consists of 8 identical layers. | `CONTRADICTED` + numerical conflict (source: 6) | Attention paper, p. 3 |
| 3 | BERT is pre-trained with a unidirectional language model rather than a bidirectional one. | `CONTRADICTED` | BERT paper, p. 1 |
| 4 | The Transformer reduced inference latency on mobile devices by 50%. | `INSUFFICIENT_EVIDENCE` | No supporting passage in either paper |

The deterministic numeric checker compares simple literal quantities. For claim 2 it
reports that the claim states 8 layers while the cited passage states 6, and AEGIS
records that conflict in the explanation and numerical-analysis field.

## Verified local run

On 2026-11-05, the paper demo was executed through the real UI → FastAPI → LangChain →
Db2 path using `qwen2.5:7b-instruct` served by Ollama at temperature 0. The session
completed with:

- 4 claims total
- 1 supported
- 2 contradicted
- 1 insufficient evidence
- 0 verification errors
- approximately 145 seconds of verification time

The session and evidence links were persisted in Db2 and reopened from the history
panel. This is a synthetic demonstration, **not** a SciFact benchmark result.

## Synthetic demo

The **Synthetic** button loads fictional SolarCell-X claims and evidence without
requiring the arXiv downloads. It exercises supported, contradicted, and
insufficient-evidence outcomes. The evidence document is clearly labelled as
fictional.

## What to inspect in the UI

- **Overview:** totals, classifications, duration, and model/provider.
- **Claim inspector:** each claim, classification, evidence passage, page, passage ID,
  relationship, retrieval score, explanation, limitations, and numeric check.
- **Export:** download the session as JSON or Markdown from the claim inspector.
- **History:** reopen the session from Db2.
- **Evaluation:** clearly labelled empty state until a real SciFact run exists.

Synthetic/demo output is never presented as SciFact benchmark performance.
