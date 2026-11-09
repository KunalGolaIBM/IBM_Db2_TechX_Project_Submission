# IBM Db2 setup and synthetic seed data

Use a disposable IBM Db2 Community Edition or compatible instance. The live adapter uses the Python `ibm_db` driver; on some platforms its IBM client runtime prerequisites must be installed first.

1. Copy `.env.example` to `.env`, set `DATA_BACKEND=db2`, and provide the connection values. Keep `.env` local.
2. Create the database (or use an existing disposable database) and run `python -m src.db.init_db`.
3. Insert synthetic test rows with the SQL below. It is illustrative test data, not clinical or real-facility data.
4. Start the UI and confirm its data-source banner says `IBM Db2`.

```sql
INSERT INTO suppliers (supplier_id, supplier_name, lead_days, reliability_score)
VALUES ('SUP-01', 'Demo Medical Supply', 7, 95.00);

INSERT INTO medicines (medicine_id, medicine_name, reorder_level, avg_daily_use, supplier_id)
VALUES ('MED-001', 'Amoxicillin 500 mg', 250, 65.00, 'SUP-01');

INSERT INTO inventory (medicine_id, on_hand) VALUES ('MED-001', 180);
INSERT INTO batches (batch_id, medicine_id, quantity, expiry_date)
VALUES ('BATCH-001', 'MED-001', 35, CURRENT DATE + 18 DAYS);
INSERT INTO usage_history (medicine_id, usage_date, quantity_used)
VALUES ('MED-001', CURRENT DATE - 1 DAY, 60);
```

The schema and adapter are included, but a live Db2 connection has not yet been validated in this generated package. Run the setup above and verify inventory reads, recommendation inserts, and approval-event writes before claiming a live Db2-backed demo.
