#!/usr/bin/env bash
# One-command hosted demo on a fresh Ubuntu 22.04/24.04 VM (8 GB RAM, 30 GB disk, ports 80/443 open).
# Usage:  curl -fsSL https://raw.githubusercontent.com/debi910/aqi-truth/main/deploy/vm_setup.sh | sudo DOMAIN=<vm-dns-name> bash
# DOMAIN is the VM's public DNS name (Azure: <label>.<region>.cloudapp.azure.com); Caddy gets an HTTPS certificate for it.
set -euo pipefail
: "${DOMAIN:?set DOMAIN to the public DNS name of the VM}"
FULL="${FULL:-1}"            # 1 = load all 34 stations, Sep-Dec 2025 (about 10 min extra); 0 = 3-station sample only

apt-get update -qq
apt-get install -y -qq docker.io docker-compose-v2 git openssl >/dev/null
systemctl enable --now docker

cd /opt
[ -d aqi-truth ] || git clone -q https://github.com/debi910/aqi-truth
cd aqi-truth && git pull -q

if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s/^DB2_PASSWORD=.*/DB2_PASSWORD=$(openssl rand -hex 12)/; s/^DB2_READER_PASSWORD=.*/DB2_READER_PASSWORD=$(openssl rand -hex 12)/" .env
  chmod 600 .env
fi
grep -q '^DOMAIN=' .env || echo "DOMAIN=$DOMAIN" >> .env
grep -q '^ALLOWED_ORIGINS=' .env || echo "ALLOWED_ORIGINS=https://debi910.github.io,https://$DOMAIN" >> .env

docker compose --profile public up -d --build
echo "Waiting for Db2 to create its database and for the sample audit (first start: 10-15 min)..."
until [ "$(docker compose ps -a setup --format '{{.State}}')" = "exited" ]; do sleep 20; done
docker compose logs setup | tail -5

if [ "$FULL" = "1" ]; then
  echo "Loading the full dataset from the OpenAQ public archive..."
  docker compose run --rm -v "$PWD/data/raw:/app/data/raw" setup sh -c \
    "python scripts/fetch_openaq.py data/raw 2025 09,10,11,12 && python src/load.py data/raw 2025-09-01 2025-12-31"
fi
docker compose restart app
echo "Done. Live at https://$DOMAIN"
