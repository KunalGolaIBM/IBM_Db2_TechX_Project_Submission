#!/bin/bash
# Runs inside the Db2 container after the instance is created (and again from deploy/codespace_start.sh, so an
# existing container gets new users). Db2 Community authenticates against OS users:
#   aqreader  the read-only question box (SELECT on two views)
#   aqapp     the web app (SELECT, plus INSERT on the explanation and question logs; no DELETE/UPDATE/ALTER)
id aqreader >/dev/null 2>&1 || useradd -M aqreader
echo "aqreader:${DB2_READER_PASSWORD}" | chpasswd
if [ -n "${DB2_APP_PASSWORD:-}" ]; then
  id aqapp >/dev/null 2>&1 || useradd -M aqapp
  echo "aqapp:${DB2_APP_PASSWORD}" | chpasswd
fi
