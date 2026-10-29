# AI Interview Assistant

> One-line pitch: An AI-powered interview preparation platform that evaluates a candidate against a job description, generates tailored interview questions, and produces a polished resume and interview report for faster hiring readiness.

---

## Problem Statement
The hiring process often struggles with two issues: candidates receive generic preparation advice, and recruiters need a faster way to assess whether a profile is a strong fit for a role. Most tools are either resume generators or mock interview assistants, but not both in one workflow.

This project solves that by combining resume analysis, job-fit scoring, technical and behavioral question generation, and AI-generated interview reports in a single experience.

---

## Solution Overview
The platform accepts:
- candidate resume text
- self-description / profile summary
- target job description

It then:
- matches the profile against the job requirements
- identifies skill gaps and their severity
- generates technical and behavioral interview questions with intentions and answer guidance
- builds a preparation plan by day
- creates a professionally styled resume tailored to the role
- exports a PDF interview report for the candidate or recruiter

---

## IBM Db2 Integration
This submission package is structured for the IBM Db2 TechX hackathon and is designed to map cleanly to a Db2-backed enterprise deployment.

- Db2 Edition & Environment: Db2 Community Edition (Docker) / Db2-ready enterprise schema
- Connector / Driver Used: Db2-compatible relational schema pattern and enterprise deployment model
- Database Schema / Data Models: Candidate profiles, job descriptions, interview reports, and resume metadata can be stored in relational tables with indexing on candidate ID, job ID, and timestamps.
- Key Queries & Operations: Query candidate status, retrieve job-fit analysis, fetch prep-plan history, and maintain report records for audits.

The current prototype uses MongoDB for rapid development, but the data model is intentionally aligned with an IBM Db2 migration path for production-grade persistence.

---

## AI / LLM Architecture
- Framework: Google GenAI with structured JSON output generation
- Model Provider & Model: Google Gemini 2.5 Flash Lite
- Workflow: Resume/job text is passed into an LLM prompt; the model returns a JSON payload with match score, skill gaps, technical questions, behavioral questions, and preparation plan.

---

## Tech Stack
- Backend / Core: Node.js, Express
- Database: MongoDB (prototype), IBM Db2-ready schema design
- Frontend / UI: React + Vite
- AI / PDF: Google Gemini, Puppeteer
- Libraries & Tools: Mongoose, zod, bcryptjs, JWT, multer

---

## Prerequisites
- Node.js 18+
- npm
- MongoDB instance or MongoDB Atlas connection
- Google AI API key
- Optional: IBM Db2 Community Edition for production migration

---

## Setup & Installation

```bash
# Clone the original project
git clone https://github.com/mg6129327-boop/interview-website.git
cd interview-website

# Backend
cd Backend
npm install
cp .env.example .env
npm run dev

# Frontend
cd ../Frontend
npm install
npm run dev
```

---

## Configuration

```bash
cp .env.example .env
```

Populate the variables with your own credentials.

> Security Warning: Never commit `.env` or any real API keys or database passwords.

---

## Running the Project

```bash
# Backend
cd Backend
npm run dev

# Frontend
cd Frontend
npm run dev
```

---

## Testing & Verification

1. Start the backend.
2. Register or log in to the app.
3. Add a resume, candidate summary, and job description.
4. Generate a report.
5. Verify the returned match score, technical/behavioral questions, and PDF export.

---

## Screenshots & Demo
- Live Demo: Not hosted yet
- Demo Video: Not uploaded yet

---

## Known Limitations & Future Roadmap
- Current prototype relies on MongoDB rather than IBM Db2 for persistence.
- PDF generation is browser-based and depends on Puppeteer runtime compatibility.
- AI output quality depends on prompt quality and model configuration.
- Future upgrades: full IBM Db2 integration, candidate history tables, analytics dashboard, enterprise auth.

---

## Team Members & Credits
| Name | GitHub Handle | Role / Contribution |
|---|---|---|
| Mohd Gufran | [@mg6129327-boop](https://github.com/mg6129327-boop) | Full-stack development, AI logic, architecture |

