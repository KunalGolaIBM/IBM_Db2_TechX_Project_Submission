# LinkedIn project summary (factual draft)

Every number and claim below was verified by a check that was actually run (see `PHASE_02_RELEASE_REPORT.md`). Edit freely, but keep the honesty about the LLM: no real language model was run, and nothing in the demo was produced by one. Add the pull-request link when it exists; do not add a live-demo link, because nothing is deployed.

## Post (about 200 words)

**CivicLens AI: my IBM Db2 TechX Summit 2026 hackathon project**

City teams drown in infrastructure complaints: potholes, water leaks, broken streetlights. Duplicates hide the real picture, and clusters are invisible one ticket at a time. I built CivicLens AI, an investigation platform where IBM Db2 is both the system of record and the analytics engine.

What it does
• Finds duplicate complaints (great-circle distance computed in SQL) and geographic hotspots (`GROUP BY` grid cell and category) inside Db2.
• Lets an investigator use only four audited, read-only, parameterized Db2 tools, then propose recommendations that must cite real evidence. A person approves or rejects each one; the decision, the reviewer and the time are written in one atomic Db2 transaction, with an append-only audit log.
• A React dashboard (map, investigation workspace, review queue, agent-transparency page) labels every recommendation with who actually wrote it: a real LLM, a rule-based fallback, or an analyst.

Honest status
I tested it against a live Db2 with no database mocks: 149 backend tests and 63 browser tests. I did **not** verify it with a real LLM: no provider credentials were available, so every recommendation in the demo is labelled "Rule-based · no LLM". All data is synthetic.

Stack: IBM Db2 12.1 (`ibm_db`), Python and FastAPI, LangChain, React and TypeScript, Playwright. Built with an AI coding assistant; every claim above was checked by running the tests.

#IBMDb2 #Db2Hack #FastAPI #LangChain #React

## Short version (about 60 words)

Built CivicLens AI for the IBM Db2 TechX Summit hackathon: duplicate and hotspot detection computed in IBM Db2, an investigator limited to audited read-only SQL tools, and human approval for every recommendation, with the author of each one (LLM, rule-based or analyst) always labelled. Tested on live Db2. Real-LLM run not verified (no credentials). Synthetic data only.

## What not to claim

* Do not say a language model produced any recommendation, insight or demo output.
* Do not say it is deployed, "production-ready" or secure for public use (public read endpoints, static tokens and no rate limiting remain).
* Do not quote results that are not in `docs/evidence/` (for example latency or accuracy numbers: none were measured).
