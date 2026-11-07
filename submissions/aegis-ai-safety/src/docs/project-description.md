# AEGIS — Short Project Description

AEGIS is an evidence-grounding system for research claims. A user uploads a paper or
pastes source text, submits a draft claim set, and receives a classification with the
exact page-level passage that supports, contradicts, or fails to establish each claim.

The differentiator is abstention and auditability. A relevant-looking paragraph is not
treated as proof; cited passage IDs are validated, boilerplate is rejected, comparable
conflicting findings are surfaced instead of silently resolved, and absent or
out-of-scope evidence becomes `INSUFFICIENT_EVIDENCE`. Every document, passage, claim,
result, and evidence link is stored in IBM Db2, and the session can be exported as JSON
or Markdown.

IBM Db2 is the primary store and retrieval source. LangChain provides the model boundary:
claim extraction and evidence-grounded verification over Db2-retrieved passages, with a
local Ollama `qwen2.5:7b-instruct` model in the reported runs. The app is a Next.js
dashboard over a FastAPI backend and runs locally; no public deployment is claimed.

Reported results: macro F1 0.678 on a 100-claim SciFact development subset (not the
hidden test split), 40/40 on a small controlled paper suite (not general accuracy), and
10/10 on a controlled hallucination suite. The main limitations are contradiction recall,
a small local model, and the absence of hosted Db2/infrastructure.
