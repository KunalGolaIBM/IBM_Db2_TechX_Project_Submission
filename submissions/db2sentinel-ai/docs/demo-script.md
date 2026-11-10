# Db2Sentinel AI — 3-Minute Video Demonstration Script

**Event:** IBM Db2 TechX Summit 2026 Hackathon (Db2Hack Round 2)  
**Project:** Db2Sentinel AI — Agentic AI-Powered Enterprise Database Security, Anomaly Detection & Incident Response  
**Target Duration:** 2 minutes 50 seconds (strictly within the 3:00 competition limit)

---

## Video Outline & Production Cues

| Timestamp | Visual Focus | Screen Action | Voiceover Audio Narrative |
| :--- | :--- | :--- | :--- |
| **0:00 – 0:25** | Slide 1 / Executive Overview | Show Db2Sentinel AI dashboard logo & problem statement: Silent database intrusions & slow SOC triage. | *"Enterprise databases power our most critical financial and customer data, yet modern database attacks unfold silently. Traditional SOC dashboards bury analysts under thousands of generic events, while static rules fail to understand query context. Meet Db2Sentinel AI — an autonomous, multi-agent security platform built on IBM Db2, LangChain, and LangGraph."* |
| **0:25 – 0:50** | Architecture & Db2 Telemetry | Cut to Architecture diagram & IBM Db2 schema. Highlight `SENTINEL_EVENTS` table and `ibm_db` connector. | *"Db2Sentinel AI does not treat IBM Db2 as a passive store. IBM Db2 is the single source of truth for all enterprise audit telemetry. Using IBM's native `ibm_db` driver with parameterized queries and TLS encryption, our engine continuously captures connection attempts, privileged role usage, and query syntax across six dedicated enterprise schema tables."* |
| **0:50 – 1:30** | Live Security Simulation | Click 'Generate Security Demo' in UI. Show failed logins (SQL30082N RC 24) followed by privileged elevation. | *"Let's simulate a live cyberattack. An external adversary from IP 198.51.100.42 launches a credential brute-force attack against database account DB2INST1, followed by a lateral privilege escalation. Our deterministic detection engine instantly flags the threshold breach and emits high-severity alerts directly into IBM Db2."* |
| **1:30 – 2:10** | LangGraph Multi-Agent Investigation | Navigate to 'AI Investigation' view. Show the 6 LangGraph nodes executing in sequence. | *"This is where Agentic AI transforms SOC operations. Rather than sending a raw alert to an engineer, LangGraph spins up a stateful multi-agent workflow: the Detection Agent isolates the attack vector; the Evidence Agent correlates Db2 telemetry history; the Threat Intel Agent maps the attacker to MITRE ATT&CK T1110; and the Risk Agent computes our 4-factor risk score — 88 out of 100, Critical."* |
| **2:10 – 2:35** | Human-in-the-Loop Approval | Navigate to 'Human Approvals' view. Review recommended action: `FORCE APPLICATION (APP_HANDLE)` and revoke user access. Click 'Approve Action'. | *"Crucially, Db2Sentinel AI is built for enterprise governance. Autonomous agents should never unilaterally alter production database state without human oversight. The Response Agent crafts targeted Db2 commands, and LangGraph halts at a human-in-the-loop checkpoint. As a certified Security DBA, I review the evidence, verify the query diff, and approve the remediation with one click."* |
| **2:35 – 2:50** | Verified Audit Trail & Wrap-up | Show incident status updated to 'Resolved' and full cryptographic audit record in `SENTINEL_AUDIT_LOG`. | *"The containment command is executed, and a complete audit log is committed back to IBM Db2. Db2Sentinel AI bridges the gap between raw database telemetry and explainable, governed incident response. Built for IBM Db2. Powered by LangChain and LangGraph. Thank you."* |

---

## Recording Checklist for Presenter

1. **Prerequisites Check:**
   - [ ] Backend running: `python -m uvicorn src.backend.app.main:app --port 8000`
   - [ ] Frontend running: `npm run dev` (serving at `http://localhost:5173`)
   - [ ] Browser window sized to clean 1920x1080 (16:9) display.
   - [ ] Database seeded with initial state: `python scripts/seed_demo_data.py`
2. **Demo Click Sequence:**
   - Start on **Overview** tab (`/`). Show metrics: Total Events, Active Alerts, Critical Incidents.
   - Click **Generate Security Demo** button in header to populate real-time attack events.
   - Click **Database Events** (`/events`) to show captured SQL syntax and `SQL30082N` failure codes.
   - Switch to **Security Alerts** (`/alerts`) to show rule firing.
   - Switch to **Incidents** (`/incidents`), click on `INC-2026-001` to view details.
   - Click **AI Investigation** (`/investigation`), show the 6-agent LangGraph workflow execution with risk gauge.
   - Click **Human Approvals** (`/approvals`), click **Approve Action**, note status changing to `APPROVED`.
3. **Pacing Guidelines:**
   - Speak with steady confidence and authoritative cybersecurity cadence.
   - Allow UI transitions 1-2 seconds to visually settle so judges can absorb the charts.
   - Keep screen cursor smooth and avoid erratic movements.
