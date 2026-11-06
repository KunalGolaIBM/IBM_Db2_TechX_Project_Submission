# IBM Db2 Community Edition with one fix for Apple Silicon hosts.
#
# Problem: under Rosetta (Colima --vz-rosetta, binfmt flags without "P"), argv[0] is
# not preserved, so `su - db2inst1 -c ...` starts bash without the leading "-" that
# marks a login shell. bash then skips ~/.bash_profile, db2profile is never sourced,
# every `db2` call in IBM's setup script fails with "command not found", and the
# container still prints "Setup has completed" with no running engine and no database.
#
# Fix: give the Db2 users a login shell that forces login mode explicitly. On hosts
# that already preserve argv[0] (native x86, QEMU with "P"), this changes nothing.
#
# The platform is pinned here, not only in docker-compose.yml, because Docker's classic
# builder (used when the buildx plugin is missing) ignores the service platform and would
# look for an arm64 image that IBM does not publish.
FROM --platform=linux/amd64 icr.io/db2_community/db2:12.1.5.0

RUN printf '%s\n' '#!/bin/bash' 'exec /bin/bash --login "$@"' > /usr/local/bin/db2-login-shell \
 && chmod 0755 /usr/local/bin/db2-login-shell \
 && echo /usr/local/bin/db2-login-shell >> /etc/shells \
 && grep -q -- '-s /bin/bash' /var/db2_setup/include/db2_common_functions \
 && sed -i 's#-s /bin/bash#-s /usr/local/bin/db2-login-shell#g' /var/db2_setup/include/db2_common_functions

# Clear the setup-complete marker at every start so the compose healthcheck cannot pass
# on a marker left over from the previous boot.
COPY entrypoint.sh /usr/local/bin/asof-db2-entrypoint
RUN chmod 0755 /usr/local/bin/asof-db2-entrypoint
ENTRYPOINT ["/usr/local/bin/asof-db2-entrypoint"]
