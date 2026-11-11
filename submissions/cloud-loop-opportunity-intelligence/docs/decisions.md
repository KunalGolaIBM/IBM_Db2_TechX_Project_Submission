# Architecture Decisions

## ADR 1: IBM Db2 Dual-Modality Storage
- **Context**: Need unified relational persistence and vector similarity search for student discovery.
- **Decision**: Store structured opportunities, student tracking, and newsletter subscriptions in relational schema `CLOUDLOOP`. Store dense 384-dimensional document vectors in `CLOUDLOOP.OPPORTUNITY_KB` via `IBMDb2DocumentStore` using cosine distance.
- **Consequences**: Single ACID database handles catalog constraints, foreign keys, and semantic vector retrieval.

## ADR 2: Fast Retrieval with Fallback Scoring
- **Context**: Local test and continuous integration environments may not always have live Db2 or LLM instances reachable.
- **Decision**: Provide transparent fallback layers in `session.py` and `match_service.py`. When Ollama is offline or times out, use deterministic skill-overlap scoring with clear provenance (`explanation_mode='deterministic'`).
- **Consequences**: Zero test flakiness, fast execution, full auditability.

## ADR 3: Server-to-Server Internal Security
- **Context**: Web app communicates with Python AI microservice.
- **Decision**: Use shared `INTERNAL_API_KEY` header (`x-internal-key`) for server route handlers. The browser client never interacts directly with the AI service or credentials.
- **Consequences**: Secure boundary, no client-side API key leakage.
