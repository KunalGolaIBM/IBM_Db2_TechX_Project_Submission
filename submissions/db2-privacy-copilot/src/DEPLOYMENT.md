# Deployment Guide - Db2 Privacy Copilot

> The current public demo deployment is defined in [`deploy/`](deploy/README.md).
> Follow that guide for CI/CD, HTTPS, health checks, and rollback. The older
> manual production examples later in this document are retained for reference.

## Quick Start (Local Development)

### Prerequisites

- **Docker** (for Db2 Community Edition)
- **Python 3.11+**
- **4GB+ RAM** for Db2 container
- **Git**

### 1. Clone and Setup (5 minutes)

```bash
# Clone repository
git clone <your-repo>
cd db2-privacy-copilot

# Copy environment template
cp .env.example .env

# Edit .env and set a strong password
# DB2_PASSWORD=YourStrongPassword123
nano .env  # or your preferred editor
```

### 2. Start Db2 (10 minutes first time)

```bash
# Start Db2 container
docker compose up -d

# Watch logs (wait for "Setup has completed")
docker compose logs -f db2

# This takes 5-10 minutes on first run
# Press Ctrl+C when you see "Setup has completed"
```

### 3. Setup Python Environment (5 minutes)

```bash
# Create virtual environment
python3.11 -m venv .venv

# Activate
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate.bat  # Windows

# Install dependencies
pip install --upgrade pip
pip install -e ".[dev,ui]"
```

### 4. Initialize Database (2 minutes)

```bash
# Run bootstrap script
python app/bootstrap.py

# Seed synthetic data
python eval/seed.py

# Verify setup
pytest tests/test_db.py -v
```

### 5. Run the Application

**Option A: Web UI (Recommended for Demo)**

```bash
streamlit run ui/app.py
```

Visit: http://localhost:8501

**Option B: REST API**

```bash
python -m app.api
```

Visit: http://localhost:8000/docs

**Option C: Individual Modules**

```bash
# Discovery
python -m app.discovery

# Classification
python -m app.classify

# Evaluation
python eval/run_eval.py

# Consent demo
python -m app.consent

# Guardrail security tests
python -m app.guardrail

# Audit chain demo
python -m app.audit

# Erasure planner
python -m app.erasure

# Agent tools
python -m app.agents
```

---

## Production Deployment

### Environment Variables

Required variables in `.env`:

```bash
# Database
DB2_HOST=your-db2-host
DB2_PORT=50000
DB2_DB=clinic
DB2_USER=copilot_app
DB2_PASSWORD=<strong-password>
DB2_SCHEMA=<schema-name>

# API
API_SECRET_KEY=<random-64-char-hex>
VIEWER_TOKEN=<unique-random-token>
ANALYST_TOKEN=<unique-random-token>
DPO_TOKEN=<unique-random-token>
API_HOST=0.0.0.0
API_PORT=8000

# Classification
PII_VALUE_THRESHOLD=0.30
PII_NAME_THRESHOLD=0.35

# Requests
DEFAULT_REQUEST_DEADLINE_DAYS=30
```

### Database Setup

#### 1. Create Separate Users

```sql
-- Connect as DBADM
CONNECT TO clinic;

-- Reader user (for discovery and sampling)
CREATE USER copilot_reader;
GRANT CONNECT ON DATABASE TO USER copilot_reader;
GRANT SELECT ON SYSCAT.TABLES TO USER copilot_reader;
GRANT SELECT ON SYSCAT.COLUMNS TO USER copilot_reader;
GRANT SELECT ON SYSCAT.REFERENCES TO USER copilot_reader;
GRANT SELECT ON SCHEMA <app-schema> TO USER copilot_reader;

-- App user (for copilot tables)
CREATE USER copilot_app;
GRANT CONNECT ON DATABASE TO USER copilot_app;
GRANT CREATETAB, BINDADD ON DATABASE TO USER copilot_app;
GRANT USE OF TABLESPACE USERSPACE1 TO USER copilot_app;

-- Grant on copilot tables
GRANT ALL ON PII_MAP TO USER copilot_app;
GRANT ALL ON RETENTION_RULES TO USER copilot_app;
GRANT ALL ON REQUESTS TO USER copilot_app;
GRANT ALL ON CONSENT TO USER copilot_app;
GRANT INSERT ON AUDIT_LOG TO USER copilot_app;  -- Insert only!

-- Executor user (for approved erasure only)
CREATE USER copilot_executor;
GRANT CONNECT ON DATABASE TO USER copilot_executor;
GRANT DELETE, UPDATE ON <app-schema>.PATIENT TO USER copilot_executor;
GRANT DELETE, UPDATE ON <app-schema>.APPOINTMENT TO USER copilot_executor;
-- Add grants for other tables as needed
```

#### 2. Enable TLS

```yaml
# docker-compose.yml (production)
services:
  db2:
    environment:
      DB2_SSL: "YES"
      DB2_KEYSTORE_PASSWORD: <password>
    volumes:
      - ./certs:/certs:ro
```

### API Deployment

#### Using Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[ui]"

COPY app/ ./app/
COPY ui/ ./ui/
COPY eval/ ./eval/

EXPOSE 8000

CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build and run
docker build -t db2-privacy-copilot .
docker run -p 8000:8000 --env-file .env db2-privacy-copilot
```

#### Using systemd (Linux)

```ini
# /etc/systemd/system/db2-copilot-api.service
[Unit]
Description=Db2 Privacy Copilot API
After=network.target

[Service]
Type=simple
User=copilot
WorkingDirectory=/opt/db2-privacy-copilot
Environment="PATH=/opt/db2-privacy-copilot/.venv/bin"
EnvironmentFile=/opt/db2-privacy-copilot/.env
ExecStart=/opt/db2-privacy-copilot/.venv/bin/uvicorn app.api:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable db2-copilot-api
sudo systemctl start db2-copilot-api
sudo systemctl status db2-copilot-api
```

### UI Deployment

#### Streamlit Cloud

1. Push to GitHub
2. Visit https://streamlit.io/cloud
3. Connect repository
4. Set secrets (environment variables)
5. Deploy

#### Self-Hosted with Nginx

```nginx
# /etc/nginx/sites-available/db2-copilot
server {
    listen 80;
    server_name copilot.yourcompany.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## Security Hardening

### 1. Authentication

**Production: Replace token-based auth with OAuth2/JWT**

```python
# app/api.py - Upgrade to OAuth2
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Verify credentials against database
    # Return JWT token
    pass
```

### 2. Database Security

- Use separate DB users with minimal privileges
- Enable TLS for Db2 connections
- Rotate passwords regularly
- Never commit `.env` to git
- Use secrets manager (AWS Secrets Manager, HashiCorp Vault)

### 3. API Security

```python
# Add to app/api.py
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

# Force HTTPS in production
app.add_middleware(HTTPSRedirectMiddleware)

# Restrict hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["copilot.yourcompany.com"]
)

# Add rate limiting
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/requests/{id}/approve")
@limiter.limit("5/minute")  # Rate limit critical endpoints
async def approve_request(...):
    pass
```

### 4. Audit Log Protection

```sql
-- Revoke UPDATE/DELETE on AUDIT_LOG
REVOKE UPDATE, DELETE ON AUDIT_LOG FROM PUBLIC;
GRANT INSERT ON AUDIT_LOG TO copilot_app;
GRANT SELECT ON AUDIT_LOG TO copilot_app;

-- Create verification job (cron)
-- Runs hourly to verify chain and alert on tampering
```

---

## Monitoring

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# Database connectivity
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/discovery/<schema>

# Audit chain integrity
curl -H "Authorization: Bearer $DPO_TOKEN" \
     http://localhost:8000/audit/verify
```

### Logging

```python
# Add to app/config.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('copilot.log'),
        logging.StreamHandler()
    ]
)

# Never log PII values!
```

### Metrics to Track

- Requests created/completed
- Classification runs
- Consent changes
- Audit records per day
- API response times
- Error rates

---

## Backup and Recovery

### Database Backup

```bash
# Backup Db2 database
db2 backup database clinic to /backup

# Backup audit log specifically (append-only)
db2 "EXPORT TO audit_log_$(date +%Y%m%d).csv OF DEL
     SELECT * FROM AUDIT_LOG"

# Verify audit chain before backup
python -c "from app.audit import verify_chain; \
           v, e = verify_chain(); \
           assert v, f'Chain broken: {e}'"
```

### Restore

```bash
# Restore Db2 database
db2 restore database clinic from /backup

# Verify audit chain after restore
python -c "from app.audit import verify_chain; print(verify_chain())"
```

---

## Troubleshooting

### Db2 Container Won't Start

```bash
# Check logs
docker compose logs db2

# Common issues:
# 1. Not enough memory (needs 4GB+)
docker stats

# 2. Port 50000 in use
lsof -i :50000

# 3. Permission issues on db2data folder
sudo chown -R 1000:1000 db2data/
```

### Connection Refused

```bash
# Check Db2 is running
docker compose ps

# Wait for full initialization
docker compose logs db2 | grep "Setup has completed"

# Test connection
python -c "from app.db import conn; c = conn(); print('OK'); c.close()"
```

### Classification Taking Too Long

```python
# Reduce sample size in app/classify.py
def sample_values(..., limit: int = 50):  # Default was 200
    pass
```

### Audit Chain Verification Fails

```bash
# Check for tampering
python -c "from app.audit import verify_chain; \
           v, e = verify_chain(); \
           print('Valid' if v else f'ERROR: {e}')"

# If chain is broken, investigate:
# 1. Check AUDIT_LOG for direct modifications
# 2. Review database logs
# 3. Check who has UPDATE privileges on AUDIT_LOG
```

### API Returns 401 Unauthorized

```bash
# Check token
curl -H "Authorization: Bearer $VIEWER_TOKEN" \
     http://localhost:8000/health

# Valid tokens in development:
# Set VIEWER_TOKEN, ANALYST_TOKEN, and DPO_TOKEN in the deployment environment.

# Production: Use proper OAuth2 tokens
```

---

## Performance Tuning

### Database Indexes

```sql
-- Already created in schema, but verify:
CREATE INDEX IDX_PII_MAP_LABEL ON PII_MAP(LABEL);
CREATE INDEX IDX_REQUESTS_STATUS ON REQUESTS(STATUS);
CREATE INDEX IDX_AUDIT_CREATED ON AUDIT_LOG(CREATED_AT);
```

### Caching

```python
# Add caching to expensive operations
from functools import lru_cache

@lru_cache(maxsize=128)
def get_retention_rules():
    # Cache retention rules (rarely change)
    pass
```

### Connection Pooling

```python
# Add to app/db.py
from contextlib import contextmanager

# Use connection pool for production
# (ibm_db doesn't have built-in pooling, consider sqlalchemy)
```

---

## Maintenance

### Daily Tasks

- [ ] Verify audit chain integrity
- [ ] Check for overdue requests
- [ ] Review error logs

### Weekly Tasks

- [ ] Backup database
- [ ] Run security scans (`bandit`, `pip-audit`)
- [ ] Review classification accuracy on new data
- [ ] Check for schema changes

### Monthly Tasks

- [ ] Review and verify retention rules against Act/Rules
- [ ] Update dependencies
- [ ] Performance review
- [ ] Access audit (who has what permissions)

---

## Scaling Considerations

### For Large Databases

1. **Partition PII_MAP by table**
2. **Use batch processing for classification**
3. **Implement async job queue** (Celery, Redis)
4. **Add read replicas** for reporting

### For High Traffic

1. **Load balancer** in front of API
2. **Redis cache** for frequent queries
3. **CDN** for static UI assets
4. **Horizontal scaling** of API instances

---

## Support

### Documentation

- `README.md` - Project overview
- `QUICKSTART.md` - Quick setup
- This file - Deployment details

### Getting Help

1. Check documentation
2. Review error logs
3. Run health checks
4. Verify Db2 connectivity
5. Check audit chain integrity

### Common Commands

```bash
# Status checks
docker compose ps
pytest -v
python -m app.audit  # Verify chain

# Restart services
docker compose restart
systemctl restart db2-copilot-api

# View logs
docker compose logs db2
tail -f copilot.log

# Run specific tests
pytest tests/test_guardrail.py -v
pytest tests/test_audit.py::test_verify_chain -v
```

---

## License and Compliance

**IMPORTANT DISCLAIMERS:**

1. **Not Legal Advice**: This is decision support software, not legal advice
2. **Verify Rules**: All retention rules must be verified against the DPDP Act and Rules
3. **Synthetic Data**: Demo uses synthetic data only
4. **Production Review**: Requires legal, security, and compliance review before production use
5. **Audit Requirements**: Maintain audit logs as required by applicable law

---

**Version:** 0.1.0  
**Last Updated:** 2026-11-10  
**Support:** See README.md
