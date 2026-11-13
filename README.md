# IBM Db2 TechX Summit 2026 — Project Submissions

Welcome to the official hackathon project submissions repository for the **IBM Db2 TechX Summit 2026** and the **Db2Hack 24-Hour Challenge**, hosted at **GL Bajaj Group of Institutions, Mathura**, in association with **IBM**, **Institution's Innovation Council (IIC)**, and **NexaSphere**.

This repository is the central showcase for all hackathon projects built with **IBM Db2**. Participants submit their projects by opening a Pull Request (PR) containing their self-contained project folder.

> **CRITICAL REQUIREMENT:** Opening a GitHub pull request is **Step 1**. After opening your PR, you must submit the PR URL through the official Google Form: **[GOOGLE_FORM_LINK_TO_BE_ADDED]** to complete your submission.

---

## Table of Contents
- [Important Dates & Deadlines](#important-dates--deadlines)
- [Who It's For & Project Requirements](#who-its-for--project-requirements)
- [Repository Structure](#repository-structure)
- [Step-by-Step Submission Guide](#step-by-step-submission-guide)
- [Naming & Branch Conventions](#naming--branch-conventions)
- [Judging & Evaluation](#judging--evaluation)
- [Security & License Guidelines](#security--license-guidelines)
- [Support & Community Channels](#support--community-channels)
- [Documentation Index](#documentation-index)

---

## Important Dates & Deadlines

| Phase / Milestone | Date & Time (IST) | Status / Notes |
|---|---|---|
| **Db2Hack Kick-off & Submissions Open** | 28 October 2026, 7:00 PM IST | Pull Requests & Form Open |
| **Db2Hack Submission Deadline** | 29 October 2026, 7:00 PM IST | Hard Deadline — PRs & Google Form |
| **IBM Db2 TechX Summit Finale & Demos** | 30 October 2026, 9:00 AM – 5:00 PM IST | Live at GL Bajaj Group of Institutions, Mathura |

> *Note: If any deadline adjustments are made by the organizing committee, updates will be announced in the official community channels.*

---

## Who It's For & Project Requirements

The hackathon is open to student developers, data engineers, AI builders, and open-source contributors.

### Core Technical Requirements:
1. **Meaningful IBM Db2 Usage:** Your solution must interact with IBM Db2 (e.g. Db2 Community Edition via Docker, Db2 on Cloud, or watsonx.data Db2). Simply referencing Db2 in documentation without functional integration in code is ineligible.
2. **Framework & Connector Integration:** You are encouraged to use standard connectors and frameworks such as `ibm_db`, `ibm_db_sa` / SQLAlchemy, LangChain, CrewAI, LlamaIndex, Haystack, or native drivers across Python, TypeScript/Node.js, Java, Go, Rust, or other languages.
3. **AI / LLMs (Optional but Encouraged):** Projects may incorporate AI/LLM workflows (e.g. RAG, text-to-SQL, agents) using IBM watsonx.ai, OpenAI, Google Gemini, OpenRouter, or local Ollama models.
4. **Complete Documentation:** Submissions must provide `README.md`, `architecture.md`, `submission.json`, and `.env.example`.

---

## Repository Structure

```text
IBM_Db2_TechX_Project_Submission/
├── .github/
│   ├── ISSUE_TEMPLATE/             # Issue templates for help and questions
│   ├── workflows/                  # CI validation workflow for submissions
│   ├── CODEOWNERS                  # Repository maintainers
│   └── PULL_REQUEST_TEMPLATE.md    # Mandatory PR template
├── docs/
│   ├── submission-guide.md         # Detailed submission walkthrough
│   ├── judging-criteria.md         # Detailed 100-point judging rubric
│   ├── db2-setup-guide.md          # Fast setup for Db2 Community Edition & drivers
│   └── faq.md                      # Frequently asked questions
├── scripts/
│   └── validate_submission.py      # Local and CI automated submission validator
├── submissions/
│   ├── README.md                   # Rules for submissions directory
│   ├── _template/                  # Baseline template folder for participants
│   │   ├── README.md
│   │   ├── architecture.md
│   │   ├── submission.json
│   │   ├── .env.example
│   │   ├── src/
│   │   └── docs/screenshots/
│   └── <project-slug>/             # Your project folder (copied from _template)
├── .editorconfig
├── .gitattributes
├── .gitignore
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── README.md
└── SECURITY.md
```

---

## Step-by-Step Submission Guide

### 1. Fork & Clone
Fork this repository to your GitHub account and clone your fork locally:
```bash
git clone https://github.com/<your-username>/IBM_Db2_TechX_Project_Submission.git
cd IBM_Db2_TechX_Project_Submission
git remote add upstream https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission.git
```

### 2. Create Your Feature Branch
```bash
git fetch upstream main
git checkout -b submission/<project-slug> upstream/main
```

### 3. Copy the Project Template
```bash
cp -r submissions/_template submissions/<project-slug>
```

### 4. Build, Test, and Document
- Add your source code inside `submissions/<project-slug>/src/`.
- Fill out `submissions/<project-slug>/submission.json` with your project and team information.
- Write clear instructions in `submissions/<project-slug>/README.md` and document your design in `submissions/<project-slug>/architecture.md`.
- Populate `submissions/<project-slug>/.env.example` with dummy keys (never commit secrets!).
- Validate locally:
  ```bash
  python scripts/validate_submission.py submissions/<project-slug>
  ```

### 5. Commit and Push
```bash
git add submissions/<project-slug>
git commit -m "feat(<project-slug>): add hackathon submission"
git push -u origin submission/<project-slug>
```

### 6. Open a Pull Request
- Open a PR against `KunalGolaIBM/IBM_Db2_TechX_Project_Submission` (`main` branch).
- Title: `[Submission] <project-slug>: <Short Project Title>`
- Fill out all sections and checklists in the PR template.

### 7. Fill the Official Google Form
Copy your PR URL and submit it via the official Google Form: **[GOOGLE_FORM_LINK_TO_BE_ADDED]**.

---

## Naming & Branch Conventions

| Asset | Format Requirement | Example |
|---|---|---|
| **Branch** | `submission/<project-slug>` | `submission/db2-support-rag` |
| **Directory** | `submissions/<project-slug>/` | `submissions/db2-support-rag/` |
| **PR Title** | `[Submission] <project-slug>: <Project Title>` | `[Submission] db2-support-rag: Db2 Support RAG Agent` |
| **Commit** | `feat(<project-slug>): <message>` | `feat(db2-support-rag): implement vector search chain` |

---

## Judging & Evaluation

Submissions are evaluated on a 100-point scale across five criteria:
1. **IBM Db2 Integration & Depth (30%)**
2. **Innovation & Real-World Impact (25%)**
3. **Technical Architecture & AI Integration (20%)**
4. **Reproducibility & Code Quality (15%)**
5. **Documentation & Presentation (10%)**

For details on scoring and penalty triggers, see [Judging Criteria](docs/judging-criteria.md).

---

## Security & License Guidelines

- **Zero Secrets Policy:** Never commit API keys, database passwords, or private access tokens. Use `.env.example` and keep real keys in local `.env` (enforced by `.gitignore`).
- **Code of Conduct:** All participants must follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- **License Hygiene:** Declare open-source licensing for third-party libraries and assets.

---

## Support & Community Channels

- **Issue Tracker:** For submission help, open a [Submission Help Issue](https://github.com/KunalGolaIBM/IBM_Db2_TechX_Project_Submission/issues/new/choose).
- **Official Summit Website:** [IBM Db2 TechX Summit 2026](https://ibmdb2techx.com)
- **WhatsApp Community:** [Join Hackathon WhatsApp Group](https://chat.whatsapp.com/COMMUNITY_LINK_PLACEHOLDER)
- **Event Lead & SPOC:** Dhruv Chaturvedi, Db2 Software Engineer, IBM Lucknow · Kunal Gola, IBM

---

## Documentation Index

- 🏗️ [Repository Architecture & MVP](docs/architecture.md)
- 📖 [Submission Guide](docs/submission-guide.md)
- ⚖️ [Judging Criteria](docs/judging-criteria.md)
- 🛠️ [Db2 Setup & Connector Guide](docs/db2-setup-guide.md)
- ❓ [Frequently Asked Questions (FAQ)](docs/faq.md)
- 🤝 [Contributing Guidelines](CONTRIBUTING.md)
- 🔒 [Security Policy](SECURITY.md)
- 📜 [Code of Conduct](CODE_OF_CONDUCT.md)
