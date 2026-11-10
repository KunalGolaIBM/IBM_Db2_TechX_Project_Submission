# 3-minute demo script

**0:00–0:25 — Problem**  
A delayed critical component is only one event, but the business impact is distributed across shipment, purchase-order, supplier, inventory, quality and production records.

**0:25–1:10 — Db2 evidence**  
Show the IBM Db2 connected indicator. Trigger `SHIP-1008`. Explain that the investigator performs parameterized relational joins and retrieves source records; the model does not invent the facts.

**1:10–1:50 — Agent workflow**  
Show inventory runway, delay duration, exposed production orders and severity. Explain the LangGraph sequence: Monitor → Investigate → Assess → Plan → Verify → Persist.

**1:50–2:30 — Recovery options**  
Compare the bounded options and their rationales. Emphasize that alternate-source qualification and schedule changes require human and operational checks.

**2:30–3:00 — Governance**  
Select an option and record a human approval. Show the approval audit row in Db2. State clearly that the system does not automatically issue purchase orders or change production schedules.
