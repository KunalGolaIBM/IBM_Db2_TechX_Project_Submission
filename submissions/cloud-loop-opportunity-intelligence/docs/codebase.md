# Codebase Tour

## Repository Structure

```
├── architecture.md           # System architecture, data flow, Db2 DDL and queries
├── docker-compose.yml        # Multi-container orchestration (Db2, ai-service, web)
├── LICENSE                   # MIT License
├── README.md                 # Project documentation and reproduction guide
├── submission.json           # Hackathon submission metadata
├── docs/
│   ├── codebase.md           # This document
│   ├── decisions.md          # Architectural Decision Records (ADRs)
│   └── screenshots/          # Platform visual references
├── scripts/
│   ├── package_submission.py # Packaging and secret scanner script
│   ├── check_links.mjs       # Internal and external route validator
│   └── compress_images.mjs   # WebP / AVIF image optimizer
└── src/
    ├── ai-service/           # FastAPI + Haystack + IBM Db2 backend service
    │   ├── app/
    │   │   ├── api/v1/       # REST endpoints (health, opportunities, search, match, tracking, stats)
    │   │   ├── core/         # Settings, logging, security, error handling
    │   │   ├── database/     # Db2 connection manager and schema migrations
    │   │   ├── repositories/ # Data access layer (Db2 SQL parameterization)
    │   │   ├── schemas/      # Pydantic v2 data models
    │   │   └── services/     # Haystack vector retriever and candidate matcher
    │   ├── data/seed/        # Curated normalized opportunity JSON datasets
    │   ├── scripts/          # seed_db2.py database loader
    │   └── tests/            # Pytest test suite (schemas, filters, API, SQL builders)
    └── web/                  # Next.js 16 + React 19 + Tailwind CSS v4 frontend
```
