# IBM Db2 Community Edition setup (Docker)

This project targets IBM Db2 Community Edition using IBM's official image `icr.io/db2_community/db2`. IBM documents this container for development/testing and states that it is not intended for production use. See the [official IBM Db2 Community Edition Docker guide](https://www.ibm.com/docs/en/db2/12.1.x?topic=deployments-db2-community-edition-docker) and [Windows installation instructions](https://www.ibm.com/docs/en/db2/12.1.x?topic=system-windows).

## Prerequisites

- Docker Desktop installed and running with Linux containers enabled, or Docker Engine on Linux/WSL2.
- Allocate at least 4 GB RAM to Docker; allow additional disk space for the image and persistent database volume.
- Python 3.11+ and the project dependencies installed.

## Configure the local environment

From `submissions/mediflow-ai`:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and replace `DB2_PASSWORD` with a strong password for this local test instance. The same password is used by the container and the Python application. Never commit `.env`.

## Start Db2

```powershell
docker compose -f docker-compose.db2.yml up -d
docker logs -f mediflow-db2
```

Wait until the logs report that setup has completed. The first initialisation can take several minutes. The database is exposed locally at `127.0.0.1:50000` and the named Docker volume `mediflow-db2-data` persists the database files.

To stop the container without deleting its data:

```powershell
docker compose -f docker-compose.db2.yml stop
```

To start it again:

```powershell
docker compose -f docker-compose.db2.yml start
```

## Create the application schema

Ensure `.env` has these values:

```dotenv
DATA_BACKEND=db2
DB2_HOST=127.0.0.1
DB2_PORT=50000
DB2_DATABASE=MEDIFLOW
DB2_USER=db2inst1
DB2_PASSWORD=<your-local-password>
DB2_SECURITY=false
```

Then run:

```powershell
python -m src.db.init_db
```

## Insert synthetic test data

Connect to the container:

```powershell
docker exec -it mediflow-db2 bash
```

Inside the container, switch to the Db2 instance owner and connect:

```bash
su - db2inst1
db2 connect to MEDIFLOW
```

Run these statements one at a time. The following complete synthetic dataset was used for the local verification (run only once on a fresh database; duplicate-key errors mean rows may already exist):

```sql
INSERT INTO suppliers VALUES ('SUP-01', 'Demo Medical Supply', 7, 95.00);
INSERT INTO suppliers VALUES ('SUP-02', 'HealthCare Distributors', 5, 92.00);

INSERT INTO medicines VALUES ('MED-001', 'Amoxicillin 500 mg', 250, 65.00, 'SUP-01');
INSERT INTO medicines VALUES ('MED-002', 'Paracetamol 500 mg', 600, 90.00, 'SUP-02');
INSERT INTO medicines VALUES ('MED-003', 'ORS Sachet', 200, 28.00, 'SUP-01');

INSERT INTO inventory (medicine_id, on_hand) VALUES ('MED-001', 180);
INSERT INTO inventory (medicine_id, on_hand) VALUES ('MED-002', 1800);
INSERT INTO inventory (medicine_id, on_hand) VALUES ('MED-003', 120);

INSERT INTO batches VALUES ('BATCH-001', 'MED-001', 35, CURRENT DATE + 18 DAYS);
INSERT INTO batches VALUES ('BATCH-002', 'MED-001', 145, CURRENT DATE + 120 DAYS);
INSERT INTO batches VALUES ('BATCH-003', 'MED-002', 1800, CURRENT DATE + 130 DAYS);
INSERT INTO batches VALUES ('BATCH-004', 'MED-003', 70, CURRENT DATE + 12 DAYS);
INSERT INTO batches VALUES ('BATCH-005', 'MED-003', 50, CURRENT DATE + 100 DAYS);

INSERT INTO usage_history (medicine_id, usage_date, quantity_used) VALUES ('MED-001', CURRENT DATE - 1 DAY, 60);
INSERT INTO usage_history (medicine_id, usage_date, quantity_used) VALUES ('MED-002', CURRENT DATE - 1 DAY, 88);
INSERT INTO usage_history (medicine_id, usage_date, quantity_used) VALUES ('MED-003', CURRENT DATE - 1 DAY, 30);
```

Exit the container shell. Start the application with `DATA_BACKEND=db2`. Confirm the UI banner says IBM Db2 and that all three inventory rows are visible. Run a recommendation, approve/reject it, and verify that the recommendation and approval event are present in Db2.

## Windows Python driver note

On the verified Windows/Python 3.11 setup, the bundled IBM CLI driver's runtime folders needed to be added to the current PowerShell process `PATH` before starting Streamlit or Uvicorn. From the project root with `.venv` active, run this in each new terminal:

```powershell
$cli = (Resolve-Path ".\.venv\Lib\site-packages\clidriver\bin").Path
$crt = Join-Path $cli "amd64.VC12.CRT"
$env:PATH = "$crt;$cli;$env:PATH"
$env:PYTHONPATH = (Get-Location).Path
```

This is a process-local setting; repeat it in each terminal session. If your installed `ibm_db` package has a different driver layout, inspect `.venv\Lib\site-packages\clidriver\bin` and adjust the runtime path accordingly.

## Verification status

**Verified locally on 9 Nov 2026:** Db2 Community Edition container reached the operable state; Python 3.11 `ibm_db` connected to `MEDIFLOW`; all seven application tables were created; three inventory rows were read through the application; recommendation generation and review actions succeeded through both the Streamlit workflow and FastAPI endpoints; and Db2 queries confirmed recommendation and approval-event records. A fresh reviewer environment must repeat these steps; this local verification does not imply a hosted or production deployment.
