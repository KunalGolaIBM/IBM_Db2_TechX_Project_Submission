"""Create and seed the Db2 vector knowledge store through LangChain DB2VS."""
from .langchain_db2 import seed_maintenance_knowledge


def main() -> None:
    count = seed_maintenance_knowledge()
    print(f"Inserted {count} maintenance notes into the Db2 vector store ESAI_KNOWLEDGE.")


if __name__ == "__main__":
    main()
