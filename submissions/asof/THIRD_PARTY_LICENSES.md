# Third-party licences

AsOf itself is licensed under the Apache License 2.0 (see [LICENSE](LICENSE)).

It uses the following third-party software. No third-party code is copied into this repository; packages are installed from PyPI and container images are pulled from their registries. Licence identifiers come from each package's published metadata for the exact versions in [requirements.txt](requirements.txt).

## Python packages (direct dependencies)

| Package | Version | Licence |
|---|---|---|
| ibm_db | 3.3.0 | Apache-2.0 |
| langchain-db2 | 1.0.0 | MIT |
| ibm-db-sa | 0.4.4 | Apache-2.0 |
| SQLAlchemy | 2.1.8 | MIT |
| sqlglot | 30.30.0 | MIT |
| db2-sqlglot-dialect (IBM) | 1.1.0 | Apache-2.0 |
| ibm-dbt-db2 (IBM, dbt adapter; own environment, [dbt/requirements-dbt.txt](dbt/requirements-dbt.txt)) | 1.0.0 | Apache-2.0 |
| dbt-core (own environment) | 1.11.17 | Apache-2.0 |
| apache-airflow (own environment, [airflow/requirements-airflow.txt](airflow/requirements-airflow.txt)) | 3.4.0 | Apache-2.0 |
| apache-airflow-providers-ibm-db2 (own environment) | 0.1.0 | Apache-2.0 |
| lfx (Langflow executor; own environment, [langflow/requirements-langflow.txt](langflow/requirements-langflow.txt)) | 1.13.1 | MIT |
| lfx-ibm (IBM's Langflow bundle; own environment) | 0.3.2 | MIT |
| langchain | 1.4.9 | MIT |
| langchain-core | 1.7.6 | MIT |
| langchain-community | 0.4.2 | MIT |
| langchain-openai | 1.7.4 | MIT |
| langchain-ollama | 1.1.0 | MIT |
| langchain-huggingface | 1.2.3 | MIT |
| langgraph | 1.2.20 | MIT |
| sentence-transformers | 6.2.0 | Apache-2.0 |
| torch | 2.15.0 | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND ISC AND MIT AND Zlib |
| fastapi | 0.162.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| pydantic | 2.14.3 | MIT |
| pydantic-settings | 2.16.2 | MIT |
| python-dotenv | 1.2.4 | BSD-3-Clause |
| jinja2 | 3.1.6 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| pypdf (policy intake: text from uploaded PDFs) | 6.21.4 | BSD-3-Clause |
| pytest | 9.2.0 | MIT |

`ibm_db` downloads the IBM Data Server Driver (clidriver) at install time, which is distributed under IBM's own licence terms.

## Models

| Model | Use | Licence |
|---|---|---|
| sentence-transformers/all-MiniLM-L6-v2 | Local embeddings, downloaded from Hugging Face on first use | Apache-2.0 |
| qwen2.5:7b-instruct (Ollama, optional) | Local LLM for the no-key path | Apache-2.0 (Qwen2.5-7B-Instruct) |
| Hosted models via OpenRouter (optional) | LLM calls | Governed by the provider's terms of service |

## Container images

| Image | Use | Licence |
|---|---|---|
| icr.io/db2_community/db2:12.1.5.0 | IBM Db2 Community Edition, base of `docker/db2/Dockerfile` | IBM Db2 Community Edition licence (accepted with `LICENSE=accept`) |

## Slide deck (`docs/slides/AsOf_slides.pdf`)

| Asset | Use | Licence or terms |
|---|---|---|
| IBM Plex Sans, IBM Plex Mono | Typefaces, embedded in the PDF | SIL Open Font License 1.1 |
| Carbon icons (`@carbon/icons` 11.92.0) | Slide icons and the faint icon pattern in the slide backgrounds | Apache-2.0 |
| LangChain and LangGraph logos | "Built with" strip and feature labels, unmodified | LangChain brand guidelines (langchain.com/brand-assets) |
| dbt logo | "Built with" strip only, same size as the other logos | dbt Labs trademark policy; dbt and the dbt logo are trademarks of dbt Labs, LLC; AsOf is not affiliated with dbt Labs |
| Apache Airflow logo | "Built with" strip and next to the Airflow feature, unmodified | ASF trademark policy; Apache Airflow, Apache, Airflow and the Airflow logo are either registered trademarks or trademarks of The Apache Software Foundation; no endorsement is implied |
| IBM Db2, Langflow, SQLGlot | Named in text only (no logo) | IBM and Db2 are trademarks of International Business Machines Corporation, registered in many jurisdictions worldwide |

The deck follows IBM's Carbon Design System (colour tokens, 2x grid, light and g100 dark themes); the AsOf mark and backgrounds were made for this project. On dark slides, third-party logos sit unmodified on a light chip.

## Data

All policies, FAQ entries and help-centre answers are fictional and were written for this project. The case *Moffatt v. Air Canada*, 2024 BCCRT 149, is cited as background only.
