"""End-to-end self-check against a live Db2. Run:  python verify.py [--submit]
Exits non-zero if anything fails, so it is safe to use as a pre-push gate."""
import os
import sys
import glob
import db
import guard
from agents import GRAPH
from embeddings import embed

R = []


def check(name, fn):
    try:
        ok, note = fn()
    except Exception as e:
        ok, note = False, f"{type(e).__name__}: {str(e)[:160]}"
    R.append((ok, name, note))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{note}]" if note else ""))


def ask(q, role="analyst", session="verify"):
    return GRAPH.invoke({"question": q, "role": role, "session": session})


def count(t):
    return db.query(f"SELECT COUNT(*) FROM {t}")[1][0][0]


check("Db2 connection", lambda: (True, db.version()))
check("VECTOR + VECTOR_DISTANCE supported (Db2 >= 12.1.2)", lambda: (
    float(db.query("SELECT VECTOR_DISTANCE(VECTOR('[1,0]',2,FLOAT32), VECTOR('[0,1]',2,FLOAT32), COSINE) FROM SYSIBM.SYSDUMMY1")[1][0][0]) > 0.9, ""))
check("Seed data present", lambda: (count("BANKING.CUSTOMERS") == 400 and count("BANKING.TRANSACTIONS") == 15000 and count("CORTEX.SEMANTIC_LAYER") >= 10, "run: python seed.py"))
check("Vector retrieval finds loan context", lambda: (
    any("LOANS" in str(r[1]).upper() or "DEFAULT" in str(r[1]).upper() for r in db.query(
        f"SELECT KIND, NAME, VECTOR_DISTANCE(EMB, {db.vlit(embed('loan default rate by branch'))}, COSINE) D FROM CORTEX.SEMANTIC_LAYER ORDER BY D FETCH FIRST 6 ROWS ONLY")[1]), ""))
o1 = {}


def t_ask():
    o1.update(ask("Which branches have the highest loan default rate?"))
    return (not o1["error"] and len(o1["rows"]) > 0 and bool(o1["audit_hash"]), f"{len(o1.get('rows', []))} rows")


check("Question answered end-to-end", t_ask)
check("Repeat question hits Db2 semantic cache", lambda: (ask("Which branches have the highest loan default rate?").get("cached") is True, ""))
before = count("BANKING.CUSTOMERS")
o2 = {}


def t_block():
    o2.update(ask("Delete all customers"))
    return (bool(o2["error"]) and not o2.get("rows") and count("BANKING.CUSTOMERS") == before, o2["error"][:60])


check("Destructive request blocked, data intact", t_block)
for label, sql, role, want in [
    ("Analyst cannot read PII", "SELECT FULL_NAME FROM BANKING.CUSTOMERS", "analyst", False),
    ("Analyst cannot bypass PII via alias", "SELECT FULL_NAME AS X FROM BANKING.CUSTOMERS", "analyst", False),
    ("Analyst cannot SELECT * on CUSTOMERS", "SELECT * FROM BANKING.CUSTOMERS", "analyst", False),
    ("COUNT(*) allowed for analyst", "SELECT COUNT(*) FROM BANKING.CUSTOMERS", "analyst", True),
    ("Admin may read PII", "SELECT FULL_NAME FROM BANKING.CUSTOMERS FETCH FIRST 3 ROWS ONLY", "admin", True),
    ("System catalog blocked", "SELECT * FROM SYSIBM.SYSDUMMY1", "admin", False),
    ("Stacked statements blocked", "SELECT 1 FROM BANKING.BRANCHES; DROP TABLE BANKING.BRANCHES", "admin", False),
    ("SQL comments blocked", "SELECT 1 FROM BANKING.BRANCHES -- x", "admin", False),
]:
    check(label, lambda s=sql, r=role, w=want: (guard.validate(s, r)[0] is w, ""))
check("Analyst top-customers has no PII", lambda: (lambda o: (not o["error"] and "FULL_NAME" not in o["cols"], ""))(ask("Top 10 customers by balance")))
check("Admin top-customers shows names", lambda: (lambda o: (not o["error"] and "FULL_NAME" in o["cols"] and "•" not in str(o["rows"][0][0]), ""))(ask("Top 10 customers by balance", "admin")))
def t_oos():
    o = ask("What is the weather in Delhi?")
    return (o.get("oos") is True and not o.get("rows") and "banking assistant" in o["error"], o["error"][:50])


check("Out-of-domain question politely refused (no SQL, audited)", t_oos)


def t_slot_n():
    ask("Top 10 customers by balance")
    o = ask("Top 5 customers by balance")
    return (not o["error"] and "FETCH FIRST 5 ROWS ONLY" in o["sql"] and len(o["rows"]) <= 5, f"cached={o.get('cached')}")


check("Cache never overrides constraints (top 5 vs top 10)", t_slot_n)


def t_follow():
    ask("Top 10 customers by balance", session="verify-fu")
    o = ask("Filter them by Jaipur", session="verify-fu")
    return (not o["error"] and "Jaipur" in o["sql"], o.get("sql", "")[:70])


check("Multi-turn follow-up uses previous turn (Filter them by Jaipur)", t_follow)


def t_topics():
    bad = []
    for q in ["Which branches have the highest loan default rate?", "Show monthly transaction volume trend", "Fraud rate by channel",
              "Top 10 customers by balance", "Accounts and balance by region", "Spend by merchant category"]:
        o = ask(q)
        if o["error"] or not o["rows"]:
            bad.append(q[:25] + ": " + (o["error"] or "no rows")[:50])
    return (not bad, "; ".join(bad))


check("All six built-in analytics topics execute on Db2", t_topics)


def t_chain():
    import app
    ok1 = app.verify()
    if not ok1["valid"]:
        return False, str(ok1)
    cur = db.conn().cursor()
    cur.execute("UPDATE CORTEX.AUDIT_LOG SET QUESTION='tampered' WHERE ID=(SELECT MAX(ID) FROM CORTEX.AUDIT_LOG)")
    broken = app.verify()  # reads inside the open transaction
    db.conn().rollback()
    cur.close()
    return (ok1["valid"] and not broken["valid"] and app.verify()["valid"], f"{ok1['checked']} rows; tamper detected")


check("Audit hash-chain valid and tamper-evident", t_chain)


def t_db2vs():
    try:
        return count("CORTEX_GLOSSARY") >= 4, "langchain-db2 DB2VS table"
    except Exception:
        return False, "DB2VS glossary missing - fix langchain-db2 install or drop the DB2VS claim from README"


check("langchain-db2 DB2VS glossary store populated", t_db2vs)


def t_inspect():
    import app
    d = app.inspect()
    return (d["customers"] == 400 and d["semantic_layer"] >= 10 and d["audit_blocks"] >= 1, f"{d['audit_blocks']} audit blocks, {d['cache_hits']} cache hits")


check("Live Db2 inspector reports the stored objects", t_inspect)

if "--submit" in sys.argv:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    shots = glob.glob(os.path.join(root, "docs", "screenshots", "*.png")) + glob.glob(os.path.join(root, "docs", "screenshots", "*.jpg"))
    check("At least 4 screenshots in docs/screenshots", lambda: (len(shots) >= 4, f"found {len(shots)}"))
    readme = open(os.path.join(root, "README.md"), encoding="utf-8").read()
    check("README has real demo video link (no placeholder)", lambda: ("PASTE_VIDEO_LINK" not in readme, ""))
    import subprocess
    repo = os.path.abspath(os.path.join(root, "..", ".."))
    val = os.path.join(repo, "scripts", "validate_submission.py")
    if os.path.exists(val):
        def t_val():
            p = subprocess.run([sys.executable, val, os.path.join("submissions", os.path.basename(root))], cwd=repo, capture_output=True, text=True)
            return p.returncode == 0, (p.stdout + p.stderr).strip().splitlines()[-1][:100]
        check("Organisers' validate_submission.py passes", t_val)
    sj = open(os.path.join(root, "submission.json"), encoding="utf-8").read()
    check("No PASTE_ placeholders left in README / submission.json", lambda: ("PASTE_" not in readme and "PASTE_" not in sj, "fill video link, LinkedIn link, email"))
    check(".env not present in submission folder (validator rejects it)", lambda: (not os.path.exists(os.path.join(root, ".env")), "delete .env before git add"))
    import re
    pat = re.compile(r"sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{30,}|BEGIN (RSA |EC )?PRIVATE KEY")
    secrets = []
    for p in glob.glob(os.path.join(root, "**", "*"), recursive=True):
        if os.path.isfile(p) and p.endswith((".py", ".md", ".json", ".yml", ".html", ".example")) and not p.endswith("verify.py"):
            if pat.search(open(p, encoding="utf-8", errors="ignore").read()):
                secrets.append(os.path.relpath(p, root))
    check("No obvious API keys in files", lambda: (not secrets, str(secrets)))

failed = [r for r in R if not r[0]]
print(f"\n{len(R) - len(failed)}/{len(R)} checks passed")
sys.exit(1 if failed else 0)
