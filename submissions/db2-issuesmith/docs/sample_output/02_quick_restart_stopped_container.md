# Quick restart fails when the existing Db2 container is stopped in WSL

## Description
On Ubuntu 22.04.5 LTS with Podman 3.4.4, the Db2 Developer Extension log shows: exec on stopped container, quick restart failed, readiness timeout. Later log entries report that the Db2 instance became accessible.

> **Evidence boundary:** The log confirms the events quoted under 'Relevant log excerpts'. It does not by itself establish the underlying cause; possible causes are listed separately as unconfirmed hypotheses.

## Environment
| Field | Value |
|---|---|
| IBM Db2 Developer Extension | 1.2.1 |
| Operating system | Windows with WSL |
| Linux distribution | Ubuntu 22.04.5 LTS |
| Architecture | x86_64 |
| Container runtime | Podman 3.4.4 |
| Container image | icr.io/db2_community/db2:latest |
| Container name | db2server |
| Db2 version (as reported) | 12.1.5.0 |

## Steps to reproduce
1. Use the environment shown above with the container runtime available.
2. Make sure the existing Db2 container is in the state shown in the log (e.g. stopped).
3. Trigger the extension's restart workflow for that container.
4. Review the restart result and the log entries that follow.

_Steps inferred from the log; please confirm or correct before posting._

## Actual behavior
- Container is stopped (log line 4).
- Exec on stopped container (log line 6).
- Quick restart failed (log line 7).
- Readiness timeout (log line 11).
- Db2 accessible (log line 14).
- Startup success (log line 15).

## Expected behavior
- The extension checks the container state before choosing a restart path and picks one that works for that state.
- Readiness checks distinguish a delayed readiness message from a real start-up failure.
- The user gets one clear final status for the container and the Db2 instance.

## Relevant log excerpts
```text
2026-11-05 11:02:40.902 [info] Podman version 3.4.4 detected
2026-11-05 11:02:41.115 [info] Found existing container named db2server (image icr.io/db2_community/db2:latest), state: exited
2026-11-05 11:02:41.522 [error] Error: can only create exec sessions on running containers: container state improper
2026-11-05 11:02:41.523 [warn] Quick restart failed, full restart required
2026-11-05 11:02:44.950 [info] Waiting for Db2 readiness message "Setup has completed"
2026-11-05 11:07:45.002 [warn] Readiness-message timeout after 300 s, continuing with accessibility checks
2026-11-05 11:07:49.878 [info] Db2 instance accessible
2026-11-05 11:07:49.880 [info] Restart completed: startup success
```

## Hypotheses (unconfirmed)
- The quick-restart path may assume a running container because it relies on an exec session.
- The readiness timeout may be shorter than start-up time on this machine.

## Reproducibility
- Happens every time / intermittently: Not yet confirmed

## Impact and question for maintainers
Users may see a restart failure even when a later step succeeds, which makes the final state unclear. Could the maintainers review the stopped-container branch and the handling of readiness timeouts?

## Attachments
- Complete sanitised Db2 Extension log (2 sensitive value(s) redacted automatically).

---
_Drafted with IssueSmith (Db2-backed agentic issue assistant), incident #1002. Reviewed by a human before posting._
