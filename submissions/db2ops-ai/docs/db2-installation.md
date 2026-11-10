# IBM Db2 Community Edition setup on this Windows 11 machine

## Machine check

At project setup: Windows 11 Home Single Language 64-bit; Python 3.14.10; VS Code is available; IBM Db2 Developer Extension 1.2.1 is installed; Docker CLI/Desktop and a running Db2 service are not available; WSL is not installed. Therefore there is no Db2 endpoint to connect to yet.

IBM currently documents its extension's Create Db2 instance workflow for Windows through WSL 2 with a supported Ubuntu distribution and Docker integration. The extension is already installed, so no extra Db2 VS Code extension is needed. Setting up WSL, virtualization, and a container runtime requires Windows system changes and may require administrator interaction; those steps were not run automatically.

## Recommended route: installed IBM Db2 Developer Extension

1. In Windows PowerShell opened **as Administrator**, install and update WSL 2:

   ```powershell
   wsl --install
   wsl --update
   wsl --set-default-version 2
   ```

2. Restart if Windows asks. Complete the Ubuntu first-run username/password prompts.
3. Install Docker Desktop from [Docker's official Windows download and install guide](https://docs.docker.com/desktop/setup/install/windows-install/). Start it, select the WSL 2 engine, and enable integration for the Ubuntu distribution under **Settings → Resources → WSL Integration**.
4. Open VS Code in the Ubuntu WSL environment (install the official Remote WSL extension if VS Code prompts). In the IBM Db2 Developer Extension's **Db2 Connections** panel, choose **Create Db2 instance**.
5. Create the database as `DB2OPS`. Choose a strong local password and note the host/port displayed by the extension. The current IBM extension guide says its setup creates the chosen database and SAMPLE database; its WSL guide lists port 50001 as externally accessible. Use the actual connection panel values in `.env` if they differ from the application's 50000 default.
6. Wait for the extension checklist and Db2 initialization to complete. The initial image pull and database setup can take several minutes and uses substantial disk space.
7. In the app `.env`, set the verified host, port, database, user, and password. Then run from `submissions/db2ops-ai`:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   python scripts/test_connection.py
   python scripts/setup_db.py
   python scripts/test_connection.py
   ```

8. Run `streamlit run src/app.py`, verify the dashboard uses live Db2 values, and save genuine screenshots into `docs/screenshots/`.

## Why this is pending

WSL and Docker are not installed on this machine, and the app has not completed a live Db2 connectivity check. The app and initialization scripts are ready, but a person with permission to enable Windows virtualization/WSL and install the supported local runtime must finish the interactive system setup. No package, download, or database response is being described as an installed or live Db2 instance.

## Sources

- [IBM Db2 Developer Extension: create a Db2 Community Edition instance](https://ibm.github.io/db2developerextension-about/docs/the-basics/creating-db2-instance.html)
- [IBM Db2 Developer Extension: manual installation notes](https://ibm.github.io/db2developerextension-about/docs/tips-and-tricks/manual-db2-installation.html)
- [Microsoft: install WSL](https://learn.microsoft.com/windows/wsl/install)
- [Docker: install Docker Desktop on Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
