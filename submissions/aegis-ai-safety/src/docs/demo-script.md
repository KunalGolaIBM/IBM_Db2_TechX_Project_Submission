# Five-Minute Demo Script

**Goal:** show that AEGIS verifies claims against the actual paper, links the exact
evidence, abstains when evidence is missing, and exports an auditable report.

**Setup before the demo**

```bash
make db-init
ollama pull qwen2.5:7b-instruct
# backend
cd backend && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
# frontend (second terminal)
cd frontend && npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000`. Have `data/samples/papers/bert-pre-training.pdf` ready.
This exact flow was last verified on 2026-11-07 as session **#741**.

## 0:00–0:40 — Problem framing

“LLM summaries can cite a paper that never says what the summary claims. AEGIS does not
ask whether a claim sounds plausible. It retrieves the actual passage from IBM Db2,
requires a page-level citation, and abstains when the paper does not establish the
claim.”

## 0:40–1:20 — Upload the real paper

1. Use the upload control and choose `bert-pre-training.pdf`.
2. Point out the document card: 69 passages, `READY`, page-level provenance.
3. Explain: PyMuPDF extracts text, AEGIS chunks it, and Db2 stores `DOCUMENTS` and
   `PASSAGES` with page and character offsets.

## 1:20–3:20 — Verify three claims

Paste this text and select the BERT document:

> BERT is pre-trained with masked language modeling. BERT uses a convolutional neural
> network architecture. BERT eliminates hallucinations in all scientific applications.

Click verify. Expected result (verified session #741):

| Claim | Result | Why |
| --- | --- | --- |
| BERT is pre-trained with masked language modeling. | SUPPORTED | BERT paper, page 2, passage 185 |
| BERT uses a convolutional neural network architecture. | CONTRADICTED | BERT paper, page 13, passage 236 |
| BERT eliminates hallucinations in all scientific applications. | INSUFFICIENT_EVIDENCE | Papers do not establish it |

While it runs, explain the pipeline: LangChain extracts atomic claims; Db2 supplies
candidate passages; BM25 ranks them; a second LangChain call returns structured JSON;
deterministic guards validate citations and downgrade unsupported certainty.

## 3:20–4:10 — Inspect the evidence

Open the contradicted claim. Show:

- document title and page number;
- passage ID and exact excerpt;
- explanation and limitations;
- numeric-analysis field when present.

Say: “The key output is not the label alone. It is the evidence link a reviewer can
check.”

## 4:10–4:40 — Export the audit report

Download JSON and Markdown. Open the Markdown report and show the summary table and
per-claim evidence. Mention that both formats are generated from the Db2 session, so the
audit trail is reproducible.

## 4:40–5:00 — Results with honest caveats

“On the reported SciFact development subset of 100 claims, macro F1 is 0.678, accuracy
0.700, contradiction recall 0.500, Recall@5 0.76. That is a development subset, not the
hidden test split or general accuracy. The controlled 40/40 suite is a small engineered
set, not a benchmark. The main open weaknesses are contradiction recall and lack of a
hosted deployment.”

## Fallback if the model is slow

The local 7B model can take 2–4 minutes for three claims. If time is short, open the
already-completed session from **History** (#741) and inspect/export it; the evidence and
report path are identical.
