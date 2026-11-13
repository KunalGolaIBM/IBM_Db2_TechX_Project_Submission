#!/bin/bash
# IBM's setup writes this marker on the data volume when it finishes. On a restart the
# old marker would still be there while setup runs again (and briefly takes the database
# offline), so clear it first. The healthcheck then only passes once setup has finished
# in this boot.
set -euo pipefail
rm -f /database/config/.shared-data/setup_complete
exec /var/db2_setup/lib/setup_db2_instance.sh "$@"
