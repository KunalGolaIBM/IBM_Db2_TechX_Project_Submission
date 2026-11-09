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

Run these statements one at a time:

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

Exit the container shell. Start the application with `DATA_BACKEND=db2`. Confirm the UI banner says IBM Db2 and that the inventory row is visible. Run a recommendation, approve/reject it, and verify that the recommendation and approval event are present in Db2.

## Verification status

The Docker Compose configuration and instructions are committed as setup support. The actual container must still be started on the developer machine and the connection, DDL, inventory read, recommendation insert and review audit write must be exercised. Do not describe live Db2 connectivity as verified until those steps succeed.
