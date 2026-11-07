title: Docker Desktop installed on Windows but not detected inside WSL
category: RUNTIME_INSTALL

If Docker Desktop runs on Windows but the extension inside a WSL window reports no runtime, WSL integration for that distribution is probably disabled. In Docker Desktop open Settings, Resources, WSL integration, enable the Ubuntu distribution, apply, then run `docker version` inside WSL. Reload the VS Code window afterwards so the extension re-runs runtime detection.
Include in an issue: output of `docker version` and `podman version` from the WSL terminal, the distribution name and whether VS Code is connected through Remote - WSL.
