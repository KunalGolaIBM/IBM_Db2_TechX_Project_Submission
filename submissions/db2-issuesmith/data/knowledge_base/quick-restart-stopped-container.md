title: Quick restart fails with "container state improper" when the Db2 container is stopped
category: RESTART

Podman and Docker can only open an exec session in a running container. A quick restart that works by exec-ing Db2 commands (for example db2stop/db2start) inside the container therefore fails when the container is in the exited/stopped state, with messages like "can only create exec sessions on running containers: container state improper".
Workaround: start the container first (`podman start db2server` or `docker start db2server`) and wait for Db2 to finish setup, or use the extension's full restart.
Worth reporting to maintainers: whether the extension checks the container state before choosing the quick-restart path, and whether the final status shown to the user matches the later accessibility checks.
