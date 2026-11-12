# Workspaces

Put (or clone) the projects you want ShipSafe to scan in this folder. With Docker Compose it is
mounted read-only at `/workspaces`, and every sub-folder that looks like a project appears in the
web UI's project picker. Nothing outside the allowed roots can be scanned.
