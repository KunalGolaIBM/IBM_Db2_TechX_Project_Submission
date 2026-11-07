# Container runtime detection and automatic installation fail in WSL when no runtime is available

## Description
On Ubuntu 22.04.5 LTS, the Db2 Developer Extension log shows: no container runtime, package fetch failed, connection timed out.

> **Evidence boundary:** The log confirms the events quoted under 'Relevant log excerpts'. It does not by itself establish the underlying cause; possible causes are listed separately as unconfirmed hypotheses.

## Environment
| Field | Value |
|---|---|
| IBM Db2 Developer Extension | 1.2.1 |
| Visual Studio Code | 1.105.1 |
| Operating system | Windows with WSL |
| Linux distribution | Ubuntu 22.04.5 LTS |
| Architecture | x86_64 |
| Container runtime | None detected at the time of the log |

## Steps to reproduce
1. Open the environment shown above with no container runtime installed.
2. Start the Db2 Developer Extension workflow that checks for or installs a container runtime.
3. Let the extension attempt automatic runtime installation.
4. Review the Db2 Extension output channel and installation log.

_Steps inferred from the log; please confirm or correct before posting._

## Actual behavior
- No container runtime (log line 8).
- Package fetch failed (log line 11).
- Connection timed out (log line 12).
- Package fetch failed (log line 13).
- Package fetch failed (log line 14).
- Runtime install failed (log line 15).
- Connection timed out (log line 17).
- Runtime install failed (log line 18).

## Expected behavior
- The extension clearly reports that runtime installation could not complete because required endpoints were unreachable.
- It suggests recovery steps, such as checking network or proxy access, or installing a supported runtime manually.
- It keeps the specific failure reason instead of only a generic installation failure.

## Relevant log excerpts
```text
2026-11-05 10:14:03.005 [error] No container runtimes found
2026-11-05 10:15:05.901 [error] Err:1 http://archive.ubuntu.com/ubuntu jammy InRelease Could not connect to archive.ubuntu.com:80 (<REDACTED:IP>), connection timed out
2026-11-05 10:16:07.233 [error] Err:2 http://security.ubuntu.com/ubuntu jammy-security InRelease Could not connect to security.ubuntu.com:80 (<REDACTED:IP>), connection timed out
2026-11-05 10:16:07.240 [warn] W: Failed to fetch http://archive.ubuntu.com/ubuntu/dists/jammy/InRelease  Could not connect to archive.ubuntu.com:80
2026-11-05 10:16:07.402 [error] E: Unable to locate package podman
2026-11-05 10:16:07.403 [error] Podman installation failed (exit code 100)
2026-11-05 10:18:18.771 [error] curl: (28) Failed to connect to download.docker.com port 443 after 131072 ms: Connection timed out
2026-11-05 10:18:18.772 [error] Docker installation failed (exit code 28)
2026-11-05 10:18:18.773 [error] All runtime installations failed
2026-11-05 10:18:18.774 [info] Proxy settings: HTTPS_PROXY=http://<REDACTED:USER>:<REDACTED:PASSWORD>@<REDACTED:HOST>:3128
```

## Hypotheses (unconfirmed)
- Outbound access from WSL to package mirrors or download.docker.com may be blocked by a proxy, firewall or DNS configuration.
- Proxy variables set on Windows may not be visible inside the WSL distribution.

## Reproducibility
- Happens every time / intermittently: Not yet confirmed

## Impact and question for maintainers
Users on restricted, proxied or offline networks may be unable to finish initial setup. Could the maintainers confirm the supported recovery path, and whether runtime installation errors can include clearer network or proxy diagnostics?

## Attachments
- Complete sanitised Db2 Extension log (4 sensitive value(s) redacted automatically).

---
_Drafted with IssueSmith (Db2-backed agentic issue assistant), incident #1001. Reviewed by a human before posting._
