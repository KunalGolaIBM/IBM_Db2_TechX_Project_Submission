title: SQL30081N communication error / ECONNREFUSED when connecting to Db2
category: CONNECTION

SQL30081N with protocol error code 10061 (Windows) or 111 (Linux) means the TCP connection was refused: nothing was listening on that host and port, or a firewall rejected it. Code 10060/110 means a timeout instead.
Checklist: is the Db2 container running (`podman ps` / `docker ps`) and finished setup; is port 50000 published (`-p 50000:50000`); does the connection profile use the right host (from Windows to WSL usually localhost); is the instance listening (`db2 get dbm cfg | grep SVCENAME` inside the container); any firewall or VPN in between.
Report the SQLSTATE, the protocol-specific error codes and which side (Windows or WSL) VS Code runs on. Remove hostnames, user IDs and passwords from connection strings before attaching logs.
