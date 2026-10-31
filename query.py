"""Run a Db2 Support RAG retrieval query."""

import argparse
import ibm_db

from db2_support import connection_string, search


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--category", choices=["transactions", "vectors", "connectivity", "performance"])
    args = parser.parse_args()
    db2 = ibm_db.connect(connection_string(), "", "")
    try:
        for row in search(db2, "DB2SUPPORT.SUPPORT_ARTICLES", args.question, args.category):
            print(f"[{row['CATEGORY']}] {row['TITLE']} (distance={row['DISTANCE']:.4f})")
            print(row["BODY"])
    finally:
        ibm_db.close(db2)


if __name__ == "__main__":
    main()
