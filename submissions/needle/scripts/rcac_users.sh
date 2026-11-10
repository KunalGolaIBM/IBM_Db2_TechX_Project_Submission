#!/usr/bin/env bash
# Create the NEEDLE RCAC demo/sweep users as Linux users inside the Db2 container (Db2 uses OS authentication).
# Runs INSIDE the codespace. Reads "NDL_<ROLE>_PASSWORD=<password>" lines on STDIN (from needle/.env),
# so no password is ever on a command line or in a file here.
#   gh codespace cp -c $CS -e scripts/rcac_users.sh remote:/home/codespace/ndl_rcac/rcac_users.sh
#   grep -E '^NDL_[A-Z0-9]+_PASSWORD=' .env | gh codespace ssh -c $CS -- 'bash ~/ndl_rcac/rcac_users.sh'
set -euo pipefail
CONTAINER="${CONTAINER:-db2}"
while IFS='=' read -r key pw; do
  [[ "$key" =~ ^NDL_([A-Z0-9]+)_PASSWORD$ ]] || continue
  user="ndl_$(echo "${BASH_REMATCH[1]}" | tr 'A-Z' 'a-z')"
  if ! docker exec "$CONTAINER" id "$user" >/dev/null 2>&1; then
    docker exec "$CONTAINER" useradd -m "$user"
    echo "created $user"
  else
    echo "exists  $user"
  fi
  printf '%s:%s\n' "$user" "$pw" | docker exec -i "$CONTAINER" chpasswd
  echo "password set for $user"
done
