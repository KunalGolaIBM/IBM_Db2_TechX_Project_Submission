import json
import logging
from typing import List, Dict, Any, Optional
from app.config import settings
from app.db import db_manager
from app.services.embeddings import embedding_provider

logger = logging.getLogger("finsight.vector_store")

class FinSightVectorStore:
    """
    Dual-engine Db2 Vector Store:
    1. Native Hybrid Db2 Vector Engine: Direct SQL with strict tenant scoping (WHERE e.user_id = ?),
       native VECTOR_DISTANCE cosine distance, and multi-table financial ledger joins.
    2. LangChain Official DB2VS Engine: Official langchain_db2.DB2VS vector store interface.
    """
    def __init__(self):
        self.dimension = settings.embedding_dimension
        self.table_name = "FINSIGHT.TRANSACTION_EMBEDDINGS"
        self._db2vs_instance = None

    def _get_db2vs(self):
        """Initializes official langchain_db2.DB2VS instance using ibm_db_dbi client."""
        if self._db2vs_instance is None:
            try:
                import ibm_db_dbi
                from langchain_db2 import DB2VS
                conn_str = (
                    f"DATABASE={settings.db2_database};hostname={settings.db2_host};port={settings.db2_port};"
                    f"uid={settings.db2_user};pwd={settings.db2_password};"
                )
                client = ibm_db_dbi.connect(conn_str, "", "")
                self._db2vs_instance = DB2VS(
                    embedding_function=embedding_provider,
                    table_name="FINSIGHT.LANGCHAIN_DB2_STORE",
                    client=client
                )
                logger.info("Initialized official langchain_db2.DB2VS on FINSIGHT.LANGCHAIN_DB2_STORE")
            except Exception as e:
                logger.error("Failed to initialize official langchain_db2.DB2VS: %s", e)
                self._db2vs_instance = None
        return self._db2vs_instance

    def index_user_transactions(self, user_id: str) -> Dict[str, Any]:
        """
        Extracts all transactions for a user, generates genuine 384-dim semantic embeddings
        using the pretrained model (no fallbacks), and indexes them into:
          1. FINSIGHT.TRANSACTION_EMBEDDINGS (Native ledger vector store with cascading FKs)
          2. FINSIGHT.LANGCHAIN_DB2_STORE (Official langchain_db2.DB2VS store)
        """
        sql = """
        SELECT 
            t.transaction_id,
            t.user_id,
            t.merchant,
            t.description,
            t.amount,
            t.transaction_type,
            t.transaction_date,
            COALESCE(c.category_name, 'Uncategorized') AS category_name
        FROM FINSIGHT.TRANSACTIONS t
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE t.user_id = ?
        """
        transactions = db_manager.execute_query(sql, (user_id,))
        if not transactions:
            logger.info("No transactions found for user %s to index.", user_id)
            return {"indexed_count": 0, "dimension": self.dimension, "model": embedding_provider.model_name}

        # Clear existing embeddings for user to ensure zero duplicate rows
        del_sql = "DELETE FROM FINSIGHT.TRANSACTION_EMBEDDINGS WHERE user_id = ?"
        db_manager.execute_statement(del_sql, (user_id,))

        documents = []
        metadatas = []
        ids = []
        for tx in transactions:
            content = (
                f"Merchant: {tx['merchant']}. "
                f"Category: {tx['category_name']}. "
                f"Description: {tx.get('description') or ''}. "
                f"Amount: INR {float(tx['amount']):.2f}. "
                f"Type: {tx['transaction_type']}. "
                f"Date: {tx['transaction_date']}."
            )
            documents.append((tx['transaction_id'], content))
            metadatas.append({
                "transaction_id": tx["transaction_id"],
                "user_id": tx["user_id"],
                "merchant": tx["merchant"],
                "category": tx["category_name"],
                "amount": float(tx["amount"]),
                "date": str(tx["transaction_date"])
            })
            ids.append(tx["transaction_id"])

        texts = [doc[1] for doc in documents]
        vectors = embedding_provider.embed_documents(texts)

        # Validate that all vectors have genuine 384 dimensions
        for v in vectors:
            if len(v) != self.dimension:
                raise ValueError(f"Vector dimension mismatch! Expected {self.dimension}, got {len(v)}")

        # 1. Insert into Native FINSIGHT.TRANSACTION_EMBEDDINGS
        insert_sql = """
        INSERT INTO FINSIGHT.TRANSACTION_EMBEDDINGS 
            (embedding_id, user_id, transaction_id, content, embedding)
        VALUES (?, ?, ?, ?, VECTOR(?, 384, FLOAT32))
        """

        native_indexed = 0
        for (tx_id, content), vec in zip(documents, vectors):
            emb_id = f"emb_{tx_id}"
            vec_json = json.dumps(vec)
            try:
                db_manager.execute_statement(insert_sql, (emb_id, user_id, tx_id, content, vec_json))
                native_indexed += 1
            except Exception as e:
                logger.error("Failed to insert native embedding for %s: %s", tx_id, e)

        # 2. Also index into official LangChain DB2VS
        langchain_indexed = 0
        db2vs = self._get_db2vs()
        if db2vs is not None:
            try:
                # Add texts in batches of 50 to LangChain DB2VS
                batch_size = 50
                for i in range(0, len(texts), batch_size):
                    batch_texts = texts[i:i + batch_size]
                    batch_meta = metadatas[i:i + batch_size]
                    batch_ids = ids[i:i + batch_size]
                    db2vs.add_texts(texts=batch_texts, metadatas=batch_meta, ids=batch_ids)
                    langchain_indexed += len(batch_texts)
                logger.info("Successfully indexed %d texts into LangChain DB2VS", langchain_indexed)
            except Exception as e:
                logger.warning("LangChain DB2VS add_texts warning: %s", e)

        logger.info("Indexed %d transactions for user %s into Db2 vector store (dim=%d, model=%s).",
                    native_indexed, user_id, self.dimension, embedding_provider.model_name)
        return {
            "indexed_count": native_indexed,
            "langchain_db2vs_count": langchain_indexed,
            "dimension": self.dimension,
            "model_name": embedding_provider.model_name
        }

    def index_specific_transactions(self, user_id: str, transaction_ids: List[str]) -> Dict[str, Any]:
        """
        Indexes a specific list of transactions for a user without wiping out other embeddings.
        Used for incremental indexing after CSV transaction imports.
        """
        if not transaction_ids:
            return {"indexed_count": 0, "status": "COMPLETED"}

        placeholders = ", ".join(["?"] * len(transaction_ids))
        sql = f"""
        SELECT 
            t.transaction_id,
            t.user_id,
            t.merchant,
            t.description,
            t.amount,
            t.transaction_type,
            t.transaction_date,
            COALESCE(c.category_name, 'Uncategorized') AS category_name
        FROM FINSIGHT.TRANSACTIONS t
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE t.user_id = ? AND t.transaction_id IN ({placeholders})
        """
        params = [user_id] + list(transaction_ids)
        transactions = db_manager.execute_query(sql, tuple(params))
        if not transactions:
            return {"indexed_count": 0, "status": "COMPLETED"}

        documents = []
        metadatas = []
        ids = []
        for tx in transactions:
            content = (
                f"Merchant: {tx['merchant']}. "
                f"Category: {tx['category_name']}. "
                f"Description: {tx.get('description') or ''}. "
                f"Amount: INR {float(tx['amount']):.2f}. "
                f"Type: {tx['transaction_type']}. "
                f"Date: {tx['transaction_date']}."
            )
            documents.append((tx['transaction_id'], content))
            metadatas.append({
                "transaction_id": tx["transaction_id"],
                "user_id": tx["user_id"],
                "merchant": tx["merchant"],
                "category": tx["category_name"],
                "amount": float(tx["amount"]),
                "date": str(tx["transaction_date"])
            })
            ids.append(tx["transaction_id"])

        texts = [doc[1] for doc in documents]
        vectors = embedding_provider.embed_documents(texts)

        # Delete any existing embeddings for these transaction IDs to prevent duplicates
        del_sql = f"DELETE FROM FINSIGHT.TRANSACTION_EMBEDDINGS WHERE user_id = ? AND transaction_id IN ({placeholders})"
        try:
            db_manager.execute_statement(del_sql, tuple(params))
        except Exception as e:
            logger.warning("Failed to delete old embeddings before re-indexing: %s", e)

        insert_sql = """
        INSERT INTO FINSIGHT.TRANSACTION_EMBEDDINGS 
            (embedding_id, user_id, transaction_id, content, embedding)
        VALUES (?, ?, ?, ?, VECTOR(?, 384, FLOAT32))
        """
        native_indexed = 0
        for (tx_id, content), vec in zip(documents, vectors):
            emb_id = f"emb_{tx_id}"
            vec_json = json.dumps(vec)
            try:
                db_manager.execute_statement(insert_sql, (emb_id, user_id, tx_id, content, vec_json))
                native_indexed += 1
            except Exception as e:
                logger.error("Failed to insert native embedding for %s: %s", tx_id, e)

        db2vs = self._get_db2vs()
        if db2vs is not None:
            try:
                db2vs.add_texts(texts=texts, metadatas=metadatas, ids=ids)
            except Exception as e:
                logger.warning("LangChain DB2VS incremental add_texts warning: %s", e)

        return {
            "indexed_count": native_indexed,
            "status": "COMPLETED" if native_indexed == len(transaction_ids) else "PARTIAL",
            "dimension": self.dimension,
            "model_name": embedding_provider.model_name
        }

    def similarity_search(self, query: str, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Executes a vector similarity search in Db2 using native VECTOR_DISTANCE cosine metric.
        Strictly enforces tenant isolation via WHERE e.user_id = ?.
        """
        query_vec = embedding_provider.embed_query(query)
        vec_json = json.dumps(query_vec)

        sql = """
        SELECT 
            t.transaction_id,
            t.merchant,
            COALESCE(c.category_name, 'Uncategorized') AS category_name,
            t.amount,
            t.currency,
            t.transaction_date,
            t.transaction_status,
            t.description,
            ROUND(VECTOR_DISTANCE(e.embedding, VECTOR(?, 384, FLOAT32), COSINE), 4) AS distance
        FROM FINSIGHT.TRANSACTION_EMBEDDINGS e
        JOIN FINSIGHT.TRANSACTIONS t ON e.transaction_id = t.transaction_id
        LEFT JOIN FINSIGHT.CATEGORIES c ON t.category_id = c.category_id
        WHERE e.user_id = ?
        ORDER BY distance ASC
        FETCH FIRST ? ROWS ONLY
        """
        rows = db_manager.execute_query(sql, (vec_json, user_id, limit))

        results = []
        for r in rows:
            dist = float(r.get("distance", 1.0))
            # Cosine similarity in range [0, 1]
            similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
            sim_score = round(similarity, 4)
            if sim_score >= 0.80:
                rel_label = "High Match"
            elif sim_score >= 0.65:
                rel_label = "Strong Match"
            elif sim_score >= 0.50:
                rel_label = "Moderate Match"
            else:
                rel_label = "Contextual Match"

            desc_snip = f": '{r.get('description')}'" if r.get('description') else ""
            explanation = f"Semantically matched '{query}' against {r['merchant']} ({r['category_name']}){desc_snip}."

            results.append({
                "transaction_id": r["transaction_id"],
                "merchant": r["merchant"],
                "category": r["category_name"],
                "amount": float(r["amount"]),
                "currency": r.get("currency") or "INR",
                "date": str(r["transaction_date"]),
                "transaction_status": r.get("transaction_status") or "POSTED",
                "description": r.get("description"),
                "distance": dist,
                "similarity_score": sim_score,
                "relevance_label": rel_label,
                "explanation": explanation,
                "engine": "db2_native_vector_cosine"
            })

        return results

    def similarity_search_langchain_db2(self, query: str, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Executes search using the official langchain_db2.DB2VS interface with post-filtering for user tenant.
        """
        db2vs = self._get_db2vs()
        if db2vs is None:
            return []

        docs_and_scores = db2vs.similarity_search_by_vector_with_relevance_scores(
            embedding=embedding_provider.embed_query(query),
            k=limit * 2
        )

        results = []
        for doc, dist in docs_and_scores:
            meta = doc.metadata or {}
            if meta.get("user_id") == user_id:
                d_val = float(dist)
                sim_score = round(max(0.0, min(1.0, 1.0 - (d_val / 2.0))), 4)
                if sim_score >= 0.80:
                    rel_label = "High Match"
                elif sim_score >= 0.65:
                    rel_label = "Strong Match"
                elif sim_score >= 0.50:
                    rel_label = "Moderate Match"
                else:
                    rel_label = "Contextual Match"

                merchant = meta.get("merchant", "Unknown Merchant")
                category = meta.get("category", "General")
                results.append({
                    "transaction_id": meta.get("transaction_id"),
                    "merchant": merchant,
                    "category": category,
                    "amount": float(meta.get("amount", 0.0)),
                    "currency": "INR",
                    "date": str(meta.get("date")),
                    "transaction_status": "POSTED",
                    "description": doc.page_content,
                    "distance": round(d_val, 4),
                    "similarity_score": sim_score,
                    "relevance_label": rel_label,
                    "explanation": f"LangChain DB2VS match for '{query}' against {merchant} ({category}).",
                    "engine": "langchain_db2.DB2VS"
                })
                if len(results) >= limit:
                    break

        return results

vector_store_service = FinSightVectorStore()
vector_store = vector_store_service
