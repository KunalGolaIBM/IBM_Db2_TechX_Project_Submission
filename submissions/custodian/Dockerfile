# Db2 Community Edition 12.1.5 plus two extra OS users. Db2 authenticates OS users, so
# PRIYA and ARJUN become real Db2 authorization IDs: the agent's SQL runs as the human.
FROM icr.io/db2_community/db2:12.1.5.0
ARG PRIYA_PASSWORD
ARG ARJUN_PASSWORD
RUN useradd -m priya && echo "priya:${PRIYA_PASSWORD}" | chpasswd \
 && useradd -m arjun && echo "arjun:${ARJUN_PASSWORD}" | chpasswd
