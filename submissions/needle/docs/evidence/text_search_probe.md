# Db2 Text Search probe (time-boxed, 10 min)

Date: 2026-11-09 ~19:20-19:27 CST. Container `db2` in Codespace `db2hack-needle-jj7gxr4xqg4vhw95`.
Db2 level: `DB2 v12.1.5.0`, `special_85816`, `DYN2606252315AMD64_85816`, Fix Pack 0.

## What ran (inside the container)

```
su - db2inst1 -c 'db2ts START FOR TEXT'
```

Result (identical on two attempts):

```
SQL20427N  An error occurred during a text search administration procedure or command. The error message is
"CIE0774E The DB2 Text Search configuration could not be found. More diagnostic information is available in the
db2diag log files. ". SQLSTATE=38H14
```

## Observed state

- `/opt/ibm/db2/V12.1/db2tss` is installed (adminTool, configTool, dumpIndex, richtextTool, setup.sh).
- `~db2inst1/sqllib/db2tss/config` exists (configuration.xml, constructors.xml, ecmts_*.properties, ...).
- `configTool printAll -configPath ~/sqllib/db2tss/config` works: build 5.6.0.0, `adminHTTPPort 55000`,
  `defaultDataDirectory /collections`.
- `db2 get dbm cfg` shows no text-search entries. `db2set -all` shows only `DB2COMM=TCPIP`, `DB2SYSTEM`.
- `db2diag.log` repeats `CIE0774E` for each attempt.

## Conclusion

Db2 Text Search is installed but not configured for the instance in this container image. Enabling it would need an
instance-level reconfiguration (assumption: `db2iupdt` with the text-search option and an instance restart), which is
high-impact on the shared hackathon database. Not attempted.

Decision: NEEDLE uses keyword BM25 in plain SQL over `NEEDLE.POSTING` / `NEEDLE.TERM_DF` / `NEEDLE.CORPUS_STATS`
(see `sql/02_bm25.sql`). This also keeps the keyword leg under the same RCAC row permission as the vector leg.
