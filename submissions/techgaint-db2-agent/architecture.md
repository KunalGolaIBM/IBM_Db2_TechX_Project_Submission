# Architecture: TechGaint Multi-Agent Recruiter and Governed RAG

## Components
1. **IBM Db2 Database**: Stores candidate profiles, evaluation records, and vector embeddings with role-based metadata tags.
2. **CrewAI Agents**:
   - Sourcing Agent
   - Screening & Evaluation Agent
   - Governance & Audit Agent
3. **Metadata Filtration Layer**: Filters retrieval results prior to LLM synthesis to ensure zero data leakage.
