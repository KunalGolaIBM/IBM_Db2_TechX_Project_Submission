# Connection test fails with SQL30081N communication error (connection refused)

## Description
On Windows, the Db2 Developer Extension log shows: sql30081n communication error, connection refused, generic error.

> **Evidence boundary:** The log confirms the events quoted under 'Relevant log excerpts'. It does not by itself establish the underlying cause; possible causes are listed separately as unconfirmed hypotheses.

## Environment
| Field | Value |
|---|---|
| IBM Db2 Developer Extension | 1.2.1 |
| Visual Studio Code | 1.105.1 |
| Operating system | Windows |
| Architecture | x64 |

## Steps to reproduce
1. Create or open a Db2 connection profile in the extension.
2. Run the connection test for that profile.
3. Review the error reported in the Db2 Extension output channel.

_Steps inferred from the log; please confirm or correct before posting._

## Actual behavior
- SQL30081N communication error (log line 4).
- Connection refused (log line 5).

## Expected behavior
- The connection test explains whether the host was unreachable, the port was closed, or the database was not ready.
- It points to the next diagnostic step (container status, port mapping, host name).

## Relevant log excerpts
```text
2026-11-06 09:21:33.520 [error] [IBM][CLI Driver] SQL30081N  A communication error has been detected. Communication protocol being used: "TCP/IP".  Communication API being used: "SOCKETS".  Location where the error was detected: "<REDACTED:IP>".  Communication function detecting the error: "connect".  Protocol specific error code(s): "10061", "*", "*".  SQLSTATE=08001
2026-11-06 09:21:33.521 [error] connect ECONNREFUSED <REDACTED:IP>:50000
```

## Hypotheses (unconfirmed)
- Nothing may have been listening on the configured host and port when the test ran.
- The profile host may not resolve to the machine running the Db2 container.

## Reproducibility
- Happens every time / intermittently: Not yet confirmed

## Impact and question for maintainers
A refused connection gives users little guidance. Could the maintainers confirm which checks the extension performs before reporting this error, and whether the message could suggest next steps?

## Attachments
- Complete sanitised Db2 Extension log (5 sensitive value(s) redacted automatically).

---
_Drafted with IssueSmith (Db2-backed agentic issue assistant), incident #1003. Reviewed by a human before posting._
