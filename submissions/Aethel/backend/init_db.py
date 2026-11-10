from pathlib import Path

from dotenv import load_dotenv

from backend.companion.db import Db2Store


if __name__ == "__main__":
    load_dotenv(Path(__file__).resolve().parent / ".env")
    Db2Store().initialize()
    print("Aethel Db2 tables are ready.")
