#!/bin/bash
# Runs inside the Db2 container after setup (mounted at /var/custom).
# Db2 authenticates against operating-system users, so the least-privileged
# AI agent identity is created as an OS user here. Its database privileges
# are granted by src/sql/03_security.sql (role HOTELOPS_AGENT).
set -e
AGENT_USER="${AGENT_USER:-opsagent}"
if [ -z "${AGENT_PASSWORD}" ]; then
  echo "[hotelops] AGENT_PASSWORD not set - skipping agent user creation"
  exit 0
fi
if ! id "${AGENT_USER}" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "${AGENT_USER}"
  echo "[hotelops] created OS user ${AGENT_USER}"
fi
echo "${AGENT_USER}:${AGENT_PASSWORD}" | chpasswd
echo "[hotelops] agent user ${AGENT_USER} ready"
# A separate security administrator for label-based access control (LBAC): Db2 does not let an
# authorization ID grant security labels to itself, so the instance owner cannot hold both roles.
SECADM_USER="${SECADM_USER:-hotelsec}"
if [ -n "${SECADM_PASSWORD}" ]; then
  id "${SECADM_USER}" >/dev/null 2>&1 || useradd -m -s /bin/bash "${SECADM_USER}"
  echo "${SECADM_USER}:${SECADM_PASSWORD}" | chpasswd
  echo "[hotelops] security administrator ${SECADM_USER} ready"
fi
