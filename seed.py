"""Seed a small, fictional Db2 support knowledge base."""

from db2_support import Article, connection_string, create_schema, insert_articles


ARTICLES = [
    Article("SQLCODE -911", "A deadlock or timeout rolled back the unit of work. Inspect the lock wait chain and retry with bounded backoff.", "transactions"),
    Article("VECTOR_DISTANCE basics", "Use VECTOR_DISTANCE with COSINE to rank embeddings. Keep the query embedding dimension equal to the VECTOR column.", "vectors"),
    Article("Connection troubleshooting", "Check hostname, TCP port, database name, TLS settings, and credentials before retrying an ibm_db connection.", "connectivity"),
    Article("Index maintenance", "Review access plans and run statistics after bulk loads so Db2 can choose an efficient access path.", "performance"),
]


def main() -> None:
    import ibm_db

    table = "DB2SUPPORT.SUPPORT_ARTICLES"
    db2 = ibm_db.connect(connection_string(), "", "")
    try:
        try:
            create_schema(db2, table)
        except Exception as exc:  # Db2 returns an error when the table already exists.
            if "42710" not in str(exc):
                raise
        print(f"Inserted {insert_articles(db2, table, ARTICLES)} support articles")
    finally:
        ibm_db.close(db2)


if __name__ == "__main__":
    main()
