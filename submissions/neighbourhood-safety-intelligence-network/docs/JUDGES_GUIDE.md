# Judge's guide: evaluate NSIN in 5 minutes

Every claim below links to something you can click, run or read. Nothing is mocked.

## The 5-minute path
| Minute | Do this | What you'll see |
|---|---|---|
| 1 | Open the **[live site](https://ibm-db2-tech-x-project-submission-n.vercel.app)**. | The real NSIN web app running in a phone frame. The pill says **LIVE · Db2 12.01** when the backend is up. |
| 2 | In the phone, tap **Resident** (one-click demo login). | A real JWT login against Db2, then Priya Sharma's dashboard loaded from Db2. |
| 3 | Go to **Report Hazard**, type *"My elderly neighbour has not answered her door or phone since last night"*, and tap **Analyze with AI Triage**. | IBM Granite (local, via Ollama) sets **P2 High** and cites the elder-care protocol it found in Db2 with `VECTOR_DISTANCE` + BM25. |
| 4 | Scroll to **Proof** and click **Run live** on each scenario. | Raw JSON from the real API: the Granite crew briefing, hybrid search, Db2 SQL analytics, `/health` with the Db2 version. |
| 5 | Open **[TESTING.md](TESTING.md)** and **[SECURITY.md](SECURITY.md)**. | 78 tests against a real Db2 (96% coverage), Bandit 0 issues, npm audit 0. |

If the pill says **offline**, the demo machine is off. The Proof section then shows **recorded real responses**, labelled with their date and Db2 version. You can also run everything yourself in three commands (see the README).

## Judging criteria → evidence
| Criterion | Where it is proven |
|---|---|
| **Use of IBM Db2** | `VECTOR(768)` columns and `VECTOR_DISTANCE` search, `MEDIAN` / `PERCENTILE_CONT` / `RANK() OVER` analytics, `JSON_VALUE` metadata filters, and a least-privilege role. See [DB2_DEEP_DIVE.md](DB2_DEEP_DIVE.md) and `tests/test_db2_features.py`. |
| **AI integration** | Three IBM Db2 AI packages in production code: `ibm-db-haystack`, `crewai-tools` (DB2VectorSearchTool) and `langchain-db2` (DB2VS), with IBM Granite models running locally. See [AI_DESIGN.md](AI_DESIGN.md), `tests/test_crew.py` and `tests/test_retrieval.py`. |
| **Innovation** | Db2 as the engine, an AI that cites its source, duplicate detection, privacy by design, and a live hosted demo of the real system. See [INNOVATION.md](INNOVATION.md). |
| **Architecture** | Components, data flow, schema and deployment diagrams. See [../architecture.md](../architecture.md) and [LIVE_DEMO.md](LIVE_DEMO.md). |
| **Security** | Threat model, JWT and roles, bcrypt, explicit CORS, append-only audit, no DDL at runtime, and scans. See [SECURITY.md](SECURITY.md) and `tests/test_security.py`. |
| **Quality and testing** | 78 passed, 5 skipped, 96% line coverage on a real Db2 and real models; the suite also passes as the least-privilege Db2 login. See [TESTING.md](TESTING.md). |
| **Impact** | Women walking home, elders living alone, parents and volunteer responders. See the "Who benefits" table in [INNOVATION.md](INNOVATION.md). |
| **Completeness** | A web app, an Android app (APK on the site), a backend, Docker Compose, docs, a live demo and a film. |

## Verify it yourself
```bash
# from submissions/neighbourhood-safety-intelligence-network
python -m pytest tests -q --cov=src/backend/app          # 78 passed, ~96%  (needs Db2 + Ollama)
bandit -r src/backend/app                                # No issues identified
curl -s localhost:8000/health                            # Db2 version, vector + hybrid search enabled
```

Query Db2 directly to see the vectors:
```sql
SELECT VARCHAR(TABNAME,30), VARCHAR(COLNAME,20), TYPENAME, LENGTH
FROM SYSCAT.COLUMNS WHERE TYPENAME = 'VECTOR';
```
