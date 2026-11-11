# Demo Script (2–3 minutes)

Before recording: Db2 container healthy, `init-db` done, `demo_setup.sql` run, dashboard open on
**Overview**, two terminals ready (A and B, both connected with `db2 connect to testdb`). Do a dry run once.
Speak the **bold** lines; text in *italics* is what to do on screen.

---

**[0:00 – Problem, 20 s]**
"In any busy database, one forgotten open transaction can freeze other applications. The classic
symptom is 'the app is slow', and the DBA has to work out *who* is blocking *whom*, and *why*. That is
what Db2 LockLens answers, using Db2's own monitoring data."

**[0:20 – Architecture, 25 s]** *(show the diagram in architecture.md or the README)*
"LockLens connects to IBM Db2 with ibm_db and reads the native monitoring functions MON_GET_LOCKS,
MON_GET_APPL_LOCKWAIT, MON_GET_CONNECTION and MON_FORMAT_LOCK_NAME. A LangChain pipeline turns that
snapshot into findings. The diagnosis itself is deterministic rules, so it works with no API key. An
optional local model can summarise the findings, but it never changes them. Important incidents are stored
in Db2 itself."

**[0:45 – Create the problem, 25 s]** *(Terminal A)*
"Session A starts a transaction and updates one account row — and deliberately never commits."
*(run `db2 +c -tvf /tmp/locklens/demo_session_a.sql`)*
"Session B, a different application, tries to update the same row."
*(Terminal B: run `db2 -tvf /tmp/locklens/demo_session_b.sql`; it hangs)*
"B is now stuck waiting."

**[1:10 – Detect it, 40 s]** *(dashboard → Refresh now → Live Lock Monitor)*
"Here is the waiting application, the application blocking it, the lock type, the table it is on, and how
long it has waited. Next, the relationship view:" *(Blocking Relationships)*
"The holder, the locked row, and the waiter. If Db2 doesn't tell us who the holder is, LockLens shows
'holder unknown' rather than guessing."

**[1:50 – Explain it, 30 s]** *(Diagnostics)*
"Each finding has a severity, the evidence, an explanation and recommended next steps. Because Db2 reports
that session A is idle inside an open transaction, LockLens says the pattern is *consistent with* an
uncommitted transaction — it does not claim to know the cause. And note: this is a lock wait, not a
deadlock. LockLens never calls something a deadlock without evidence, and it never kills sessions; it only
advises."
*(Incident History)* "The incident is stored in Db2, and refreshing does not create duplicates."

**[2:20 – Resolve, 15 s]** *(Terminal A: `db2 rollback`)*
"Session A rolls back. Session B completes, the wait disappears, and the incident is marked resolved."

**[2:35 – Limits and impact, 20 s]**
"Honest limits: it shows a snapshot, not history; it doesn't yet show SQL text or confirm deadlocks, which
needs a deadlock event monitor — that is the next step. The impact: a DBA or developer can go from 'something
is stuck' to 'this application is holding this lock, and here is what to check' in seconds, with every claim
tied to evidence from Db2."

---
### Recording tips
- Keep the sidebar *Auto-refresh* off during narration; press *Refresh now* when you say so.
- If a table name shows "not resolved", say: "the blocking relationship is still established by Db2".
- Do not say "AI agent" or "autonomous"; say "explainable diagnostics" and "optional local model".
- Capture screenshots for `docs/screenshots/` at these moments: Live Lock Monitor with the wait,
  Blocking Relationships graph, a WARNING finding expanded, Incident History with one OPEN row.
