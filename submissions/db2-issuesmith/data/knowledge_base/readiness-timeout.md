title: Readiness-message timeout while the Db2 instance later becomes accessible
category: RESTART

The Db2 Community Edition container prints a readiness message (such as "Setup has completed") once instance setup is done. First start-up, slow disks, low WSL memory or Podman 3.x log handling can delay or hide this message, so a readiness wait can time out even though a later connection check succeeds.
To diagnose: compare timestamps of the timeout and the first successful connection, run `podman logs db2server | tail -50`, and check WSL memory (Db2 needs several GB). Give the container more memory through .wslconfig if needed.
When reporting, state both facts: the readiness wait timed out AND the later accessibility check succeeded. Do not describe the restart as failed if the log shows success afterwards.
