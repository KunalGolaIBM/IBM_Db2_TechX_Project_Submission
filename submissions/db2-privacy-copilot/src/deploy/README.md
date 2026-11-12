# Public demo deployment

This Compose stack is intended for synthetic demo data only. It is not suitable
for real personal or health data: the current UI uses demo role selection and
the API uses development tokens. Use a properly authenticated deployment and
managed database before handling real data.

## Required GitHub configuration

Set the repository variable `DEPLOY_ENABLED` to `true` only after the VM,
secrets, and production environment below are ready. The deployment workflow is
disabled by default.

Create these repository secrets:

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | VM public IP or hostname |
| `DEPLOY_USER` | SSH deploy account |
| `DEPLOY_SSH_KEY` | Private key for that account |
| `DEPLOY_KNOWN_HOSTS` | Verified `ssh-keyscan -H <VM>` output |
| `DOMAIN` | DNS name pointing to the VM |

Create a protected GitHub environment named `production` with a required
reviewer. Give the deploy account read-only access to the private GHCR packages.
Keep Db2 credentials in `/opt/copilot/.env` on the VM, not in GitHub.

## VM initialization

Use Ubuntu 22.04/24.04 with at least 8 GB RAM (16 GB recommended), Docker Engine,
and the Compose plugin. Allow inbound SSH, HTTP, and HTTPS only in both the host
firewall and cloud security group; Db2 port 50000 is not published.
Use Db2 12.1.2 or newer for the LangChain DB2VS taxonomy-vector search. The API
downloads its sentence-transformer model on first vector classification unless
the model is already present in the Hugging Face cache, so allow outbound access
to the model host during first use.

Create the deploy account and `/opt/copilot/deploy`, install the CI public key
in the account's `authorized_keys`, and authenticate that account to GHCR with a
read-only token. Copy `deploy/.env.example` to `/opt/copilot/.env`, then set a
real domain, lowercase GHCR owner, strong unique Db2 password, random API
secret, and distinct random `VIEWER_TOKEN`, `ANALYST_TOKEN`, and `DPO_TOKEN`
values. `CORS_ORIGINS` should contain only the site's HTTPS origin. The UI
connects to both the API and Db2 over private Compose networks; neither service
publishes a host port. For this demo image, `DB2_USER=db2inst1` is used to
bootstrap the sample schema; do not reuse this setup for real data.

## First deployment and updates

Push to `main` and wait for CI to pass. The first successful CI run builds the
API and Streamlit images, tags them with the commit SHA, scans them, then pauses
at the protected `production` environment for approval. Approve the deploy job.
After the first successful deployment, each subsequent deployment stores the
previous commit SHA and can roll back automatically if the API health check
fails.

The public health endpoint is `https://<DOMAIN>/api/healthz`. `deploy.sh` also
supports a manual rollback by passing a known-good 40-character commit SHA.

On the first deployment, initialize and seed the demo database once from the
project directory on the VM:

```bash
docker compose -f deploy/docker-compose.prod.yml --env-file .env exec api \
  python -m app.bootstrap
docker compose -f deploy/docker-compose.prod.yml --env-file .env exec api \
  python -m eval.seed
```

The API health check verifies Db2 connectivity; it does not assert that the
application schema has been bootstrapped. Back up the seeded synthetic data
before a presentation.

## Backups

Run `bash /opt/copilot/deploy/backup.sh` on the VM. Backups are saved under
`/opt/copilot/backups` and local archives older than seven days are removed.
Copy backups off the VM for disaster recovery.

See [DEPLOYMENT.md](../DEPLOYMENT.md) for local development setup.
