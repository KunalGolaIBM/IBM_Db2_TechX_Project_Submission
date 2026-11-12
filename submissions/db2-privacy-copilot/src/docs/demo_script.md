# Demo Script for Db2 Privacy Copilot

**Duration:** 15 minutes  
**Audience:** Hackathon judges, technical evaluators  
**Goal:** Demonstrate end-to-end DPDP compliance workflow with Db2-specific features

---

## Pre-Demo Checklist (5 minutes before)

- [ ] Db2 container running: `docker compose ps`
- [ ] Data seeded: `SELECT COUNT(*) FROM PATIENT` shows 100+ rows
- [ ] Streamlit UI running: `streamlit run ui/app.py`
- [ ] Browser open to http://localhost:8501
- [ ] Terminal ready for SQL demos
- [ ] DBeaver or Db2 CLI ready (optional)

---

# Demo Script for Db2 Privacy Copilot

## Setup (5 minutes before demo)

1. Ensure Db2 container is running:
   ```bash
   docker compose up -d
   docker compose logs db2  # Wait for "Setup has completed"
   ```

2. Verify database is ready:
   ```bash
   python -c "from app.db import conn; c = conn(); print('✓ Connected'); c.close()"
   ```

3. Ensure data is seeded (if not already done):
   ```bash
   python eval/seed.py
   ```

## Demo Flow (10-15 minutes)

### Part 1: Discovery and Classification (3-4 min)

**Goal:** Show how the system discovers and classifies personal data

1. Show the raw database schema
   - Open DBeaver or use CLI: `db2 connect to clinic; db2 describe table PATIENT`
   - Point out the ugly column names: `CUST_MAIL_ID`, `PH_NO`, `GOVT_ID`

2. Run discovery
   - Execute: `python -m app.discovery`
   - Show FK graph visualization
   - Show safe deletion order

3. Run classification
   - Execute: `python -m app.classify`
   - Show PII map with confidence scores
   - Highlight challenging cases:
     * Phone stored as BIGINT
     * Email with ugly name `CUST_MAIL_ID`
     * Hidden PAN in NOTES field
     * `TICKET_REF_NO` correctly NOT flagged (despite being 10 digits)

4. Show evaluation metrics
   - Execute: `python eval/run_eval.py`
   - Compare to regex-only baseline
   - Show per-type precision/recall

### Part 2: Consent Management (2-3 min)

**Goal:** Demonstrate bitemporal consent tracking

1. Grant consent for marketing
   ```python
   from app.consent import grant
   grant(patient_id=1, purpose="MARKETING", start="2026-01-01")
   ```

2. Withdraw consent
   ```python
   from app.consent import withdraw
   withdraw(patient_id=1, purpose="MARKETING", effective="2026-06-01")
   ```

3. Query "as of" dates
   ```python
   from app.consent import valid_on
   # Was consent valid on May 1?
   valid_on(1, "MARKETING", on="2026-05-01")  # True
   # Was it valid on July 1?
   valid_on(1, "MARKETING", on="2026-07-01")  # False
   ```

4. Show temporal queries in SQL
   ```sql
   -- Show current consent
   SELECT * FROM CONSENT WHERE PATIENT_ID = 1;
   
   -- Show all history
   SELECT * FROM CONSENT_HISTORY WHERE PATIENT_ID = 1;
   
   -- As of a specific date
   SELECT * FROM CONSENT 
   FOR BUSINESS_TIME AS OF '2026-05-01'
   WHERE PATIENT_ID = 1;
   ```

### Part 3: Rights Request - Erasure (5-6 min)

**Goal:** Show safe, audited erasure with human approval

1. Create an erasure request
   - UI: Click "New Request" → "Erasure" → Select patient
   - OR via API/CLI

2. View the dry-run plan
   - Show tables to ERASE (PRESCRIPTION, LAB_REPORT, MARKETING_LIST)
   - Show tables to ANONYMISE (PATIENT, APPOINTMENT, SUPPORT_TICKET)
   - Show table to RETAIN (BILLING - its foreign keys still reference the patient and appointment)
   - Display row count estimates
   - Show retention rule verification badges (unverified warning)

3. Review the guardrail
   - Show generated SQL statements
   - Demonstrate blocked attempts:
     * Try `DROP TABLE` → Blocked
     * Try statement without WHERE → Blocked
     * Try SQL injection → Blocked

4. Approve and execute
   - Human clicks "Approve"
   - Watch execution status (real-time if possible)
   - Show completion receipt

5. Verify results
   - Check PATIENT and APPOINTMENT: rows remain, personal/health fields are NULL
   - Check BILLING: patient's records still there (RETAINED)
   - Check SUPPORT_TICKET: PII fields are NULL (ANONYMISED)
   - Check AUDIT_LOG: execution is recorded

6. Verify audit chain
   - Run audit verification
   - Show "chain intact" message
   - (Optional) Tamper with a row and show detection

### Part 4: Db2 Capabilities Showcase (2 min)

**Goal:** Explicitly show why Db2 is essential

1. **Catalog Views**
   ```sql
   -- Discovery uses SYSCAT
   SELECT * FROM SYSCAT.REFERENCES WHERE TABSCHEMA = 'DB2INST1';
   ```

2. **Vector Similarity** (if working)
   ```sql
   -- Show PII_TAXONOMY table
   SELECT * FROM PII_TAXONOMY;
   -- Show a similarity search (if langchain-db2 is working)
   ```

3. **Temporal Tables**
   ```sql
   -- Show CONSENT with BUSINESS_TIME and SYSTEM_TIME periods
   SELECT * FROM CONSENT FOR SYSTEM_TIME AS OF CURRENT TIMESTAMP - 1 DAY;
   ```

4. **Transactions**
   - Show rollback behavior
   - Inject an error mid-execution → nothing changes

5. **(Stretch) RCAC**
   - Show a column mask example from `sql/03_rcac_examples.sql`

## Key Points to Emphasize

1. **Agents propose, humans approve, Db2 executes**
   - No agent has an execute tool
   - Every destructive action requires approval

2. **Db2 is not just storage**
   - Catalog for discovery
   - Vectors for classification
   - Temporal tables for consent history
   - ACID transactions for safe erasure
   - (Stretch) RCAC for enforcement

3. **Transparency and auditability**
   - Every classification shows method and confidence
   - Every erasure plan shows reasons
   - Hash-chained audit log
   - Retention rules flagged if unverified

4. **Fail-safe design**
   - Guardrail is deterministic, not LLM-based
   - FK-aware deletion order
   - Transactions roll back on any error
   - Approval bound to plan hash

5. **Practical usability**
   - Scan completes in < 1 minute
   - Human review only for uncertain cases
   - Plain-language explanations
   - DPDP compliance "decision support, not legal advice"

## Backup Plans

### If Db2 vector support unavailable
- Live name-based classification reports an error instead of silently claiming
  vector results; use Db2 12.1.2 or newer to enable DB2VS.
- Mock mode uses keyword heuristics for database-free demos.
- Emphasize that other Db2 features still work, but do not describe mock
  heuristics as vector search.

### If LLM times out
- Classification and erasure are deterministic
- Agents are assistive, not required
- Core path still demonstrates all features

### If network fails
- Everything runs locally
- No external dependencies for core features

## Questions to Anticipate

1. **"Is this legal advice?"**
   - No, it's decision support. Rules must be verified against the Act.

2. **"What about backups?"**
   - Out of scope for this tool. Must be handled separately.

3. **"How accurate is classification?"**
   - Show the evaluation metrics. Compare to baseline. Discuss edge cases.

4. **"What if the LLM hallucinates?"**
   - Guardrail is deterministic. LLM only suggests, never executes.

5. **"Why Db2 specifically?"**
   - (Point to the capabilities table in the README and demo each one)

6. **"Can this work with other databases?"**
   - Architecture is portable, but loses Db2-specific features (vectors, temporal, RCAC).

## Success Criteria

By the end of the demo, judges should:
- ✓ See PII discovered and classified accurately
- ✓ See temporal consent queries answering "what was true when"
- ✓ See a complete erasure with retention rules respected
- ✓ See the audit trail and verification
- ✓ Understand why each Db2 feature matters
- ✓ Believe the system is safe (human control, rollback, guardrail)
