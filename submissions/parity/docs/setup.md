# Setup

This document tells you how to run Parity on your machine.

## What you need

- Python 3.11 or later.
- Docker Desktop, running. The databases run in containers.
- Git.
- Optional: an API key for a model provider. You can also use a local model through Ollama. Replay mode needs no key at all.

## Steps

1. Clone the repo.

   ```bash
   git clone https://github.com/Amitk003/Parity.git
   cd Parity
   ```

2. Create a virtual environment.

   Windows PowerShell:

   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

   macOS or Linux:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install the project in dev mode. The `db` extra adds the database drivers.

   ```bash
   pip install -e ".[dev,db]"
   ```

4. Start the databases.

   ```bash
   docker compose up -d
   ```

   This starts PostgreSQL and IBM Db2. First start can take a few minutes because Db2 is a large image.

5. Check the CLI.

   ```bash
   parity run --help
   ```

6. Run tests.

   ```bash
   pytest
   ```

## Config

Copy the example config and fill in values for your setup.

```bash
cp .env.example .env
```

Set at least the database hosts, ports, user names, and passwords for the local containers. Never commit a real `.env` file.

## Stop and clean up

```bash
docker compose down -v
```

The `-v` flag removes container data volumes. Use it when you want a fully clean run.

## Troubleshooting

- **Docker is not running.** Open Docker Desktop and wait until it says the engine is running. Then retry the command.
- **Port already in use.** Stop the other service or change the port in `docker-compose.yml` and in `.env`.
- **Db2 takes long on first start.** This is normal. Wait for the health check to pass before you run Parity.
- **Python version error.** Parity needs Python 3.11 or later. Check with `python --version`.
