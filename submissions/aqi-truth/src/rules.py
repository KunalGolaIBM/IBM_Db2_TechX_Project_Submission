"""Embed rule paragraphs with IBM Granite embeddings (local Ollama) and store them in Db2 VECTOR columns."""
import json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from db import connect

OLLAMA = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "granite-embed")

def embed(texts):
    req = urllib.request.Request(f"{OLLAMA}/api/embed", data=json.dumps({"model": EMBED_MODEL, "input": texts}).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))["embeddings"]

def vec_literal(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"

def load_rules(path):
    rules = json.load(open(path, encoding="utf-8"))
    vecs = embed([r["body"] for r in rules])
    conn = connect(); cur = conn.cursor()
    cur.execute("DELETE FROM AQ.RULE_TEXT")
    for r, v in zip(rules, vecs):
        cur.execute("INSERT INTO AQ.RULE_TEXT (RULE_REF, SOURCE, URL, BODY, EMBEDDING) VALUES (?,?,?,?, VECTOR(?, 768, FLOAT32))",
                    (r["ref"], r["source"], r["url"], r["body"], vec_literal(v)))
    conn.commit(); print(f"{len(rules)} rules embedded into AQ.RULE_TEXT")

def nearest_rules(conn, text, k=3):
    """Rule paragraphs closest to `text` by cosine distance, computed inside Db2."""
    q = vec_literal(embed([text])[0])
    cur = conn.cursor()
    cur.execute("""SELECT RULE_REF, BODY, SOURCE, URL, VECTOR_DISTANCE(EMBEDDING, VECTOR(?, 768, FLOAT32), COSINE) AS D
                     FROM AQ.RULE_TEXT ORDER BY D FETCH FIRST ? ROWS ONLY""", (q, k))
    return cur.fetchall()

if __name__ == "__main__":
    load_rules(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "data", "rules.json"))
