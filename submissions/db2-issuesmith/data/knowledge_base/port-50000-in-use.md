title: Container fails to start because port 50000 is already allocated
category: RESTART

"port is already allocated" or "address already in use" means another process or an old container is bound to the port. List containers with `podman ps -a` / `docker ps -a`, remove the stale one, or publish Db2 on a different host port (for example -p 50001:50000) and update the connection profile.
