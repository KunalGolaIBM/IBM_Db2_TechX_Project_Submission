# AI design: grounded, local, fail-safe

## Models
Both models are IBM Granite, served locally by **Ollama**. No resident text leaves the machine.

| Model | Used for | Through |
|---|---|---|
| `granite-embedding:278m` (768 dims) | Protocol passages, incident reports, queries | `ollama-haystack` (Haystack), `langchain-ollama` (LangChain), `ollama` client (CrewAI tool) |
| `granite3.3:2b` | The CrewAI agents (Triage Analyst, Protocol Advisor) | CrewAI `LLM("ollama/granite3.3:2b")` |

**Why 278m and not 30m:** both were measured on our protocol corpus. The 30M model put the *child safety* protocol first for "my grandmother is not answering her phone". The 278M model ranks it correctly and separates off-topic questions cleanly.

## Pipelines

### 1. Triage: CrewAI Flow (deterministic)
`intake → assess → router → (critical: escalate | standard) → knowledge`, with typed Pydantic state (`src/backend/app/ai/crewai/agents.py`).
- **Intake:** whole-word keyword rules extract the category, location and missing details.
- **Assess:** sets the priority from `P1_CRITICAL` down to `P4_ADVISORY`, with written reasoning.
- **Router:** critical reports go to an escalation branch that puts "Call 112" first.

This is the **authoritative** priority. It's predictable and covered by 10 regression cases.

### 2. Retrieval: Haystack hybrid on IBM Db2
`src/backend/app/ai/haystack/rag_pipeline.py`
- **Indexing:** `DocumentSplitter` (60-word passages) → `OllamaDocumentEmbedder` → `DocumentWriter` → `IBMDb2DocumentStore`.
- **Query:** `OllamaTextEmbedder` → `IBMDb2EmbeddingRetriever`, alongside `InMemoryBM25Retriever`. The same metadata filters (category, audience) apply to both branches.
- **Fusion:** passages collapse to their protocol, then `DocumentJoiner(reciprocal_rank_fusion)`, then a soft prior for the triaged category.
- **Output:** the protocol, the **exact cited passage**, the source, and which branch matched (`bm25`, `vector` or both).

### 3. Briefing: CrewAI Crew on Granite
`src/backend/app/ai/crewai/crew.py`, exposed as `POST /ai/crew-briefing`.
- **Triage Analyst:** explains what happened and why it matters, and does not change the priority.
- **Protocol Advisor:** writes 3 numbered actions using **IBM's `DB2VectorSearchTool`** (`crewai-tools`) over the Db2 passages, configured with Granite embeddings instead of its OpenAI default.
- **Grounding:** retrieved passages go into the task context. The final answer is checked for a cited protocol title and returned as `grounded: true/false`.

### 4. Related reports: LangChain on IBM Db2
`src/backend/app/ai/semantic/db2_vector_store.py` stores every incident in `langchain-db2` `DB2VS`. `GET /incidents/{id}/similar` returns related reports (verified staff only), with the same address ranked first.

## Trust under uncertainty

| Risk | Mitigation | Evidence |
|---|---|---|
| Hallucinated advice | Advice must come from retrieved passages; a grounding check flags uncited answers | `test_crew.py` |
| Confident answers to off-topic questions | **Calibrated cutoff.** With `granite-embedding:278m` on our passages, relevant top matches score ≤ 0.435 and off-topic ones ≥ 0.488, so the cutoff is 0.46 | `test_semantic_retrieval_rejects_off_topic_queries` |
| Wrong priority from an LLM | The LLM never sets the priority; the rule-based flow does | `test_crew_briefing_runs_granite_agents_over_db2` asserts the rule priority is unchanged |
| Prompt injection in a report | No tool can write data; the LLM output is advisory; the priority is computed without the LLM | design + tests |
| Model or server down | The briefing endpoint returns the rule-based triage plus `briefing_error`; retrieval falls back to BM25; `/health` reports why | `test_crew_briefing_degrades_when_llm_is_unreachable` |
| Data leaving the deployment | Local Ollama; Haystack and CrewAI telemetry disabled | [SECURITY.md](SECURITY.md#4-privacy-by-design) |

## Measured calibration (cosine distance in Db2, `granite-embedding:278m`)

| Query | Top protocol | Distance |
|---|---|---|
| my grandmother is not answering her phone | Elder care | 0.401 |
| child did not reach school on time | Child safety | 0.324 |
| someone is following me home at night | Women's transit safety | 0.430 |
| elderly man fell and needs medicine | Elder care | 0.351 |
| quantum astrophysics spaceship orbit | (rejected) | 0.488 |
| what is the recipe for pasta | (rejected) | 0.515 |
