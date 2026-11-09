import json
import requests

BASE_URL = "http://127.0.0.1:8000"
TOKEN = "GLtWRU3gWNfGYzxpMFm9vt7yytyxKer8"
HEADERS = {"X-Service-Token": TOKEN, "Content-Type": "application/json"}
DEMO_USER = "usr_demo_synthetic_01"

QUERIES = [
    {
        "id": 1,
        "query": "grocery shopping vegetables supermarket staples",
        "expected_domain": ["Groceries & Supermarket", "Food & Dining"]
    },
    {
        "id": 2,
        "query": "restaurant dining takeout lunch and dinner meals",
        "expected_domain": ["Dining & Takeout", "Groceries & Supermarket"]
    },
    {
        "id": 3,
        "query": "cabs rides daily travel commute airport taxi",
        "expected_domain": ["Commute & Travel"]
    },
    {
        "id": 4,
        "query": "streaming entertainment subscriptions music and movies",
        "expected_domain": ["Entertainment & Media", "Software & Subscriptions"]
    },
    {
        "id": 5,
        "query": "cloud infrastructure hosting software licenses and developer tools",
        "expected_domain": ["Software & Cloud", "Software & Subscriptions"]
    },
    {
        "id": 6,
        "query": "monthly apartment rent payment and housing maintenance",
        "expected_domain": ["Housing & Rent"]
    },
    {
        "id": 7,
        "query": "monthly salary direct deposit payroll credit inflow",
        "expected_domain": ["Salary & Wages", "Income & Salary"]
    },
    {
        "id": 8,
        "query": "shopping retail apparel electronics and gadgets",
        "expected_domain": ["Electronics & Shopping", "Shopping & Retail"]
    },
    {
        "id": 9,
        "query": "electricity water broadband and utility bills",
        "expected_domain": ["Utilities & Internet", "Utilities & Bills"]
    },
    {
        "id": 10,
        "query": "hospital clinic pharmacy medicines and health checkup",
        "expected_domain": ["Healthcare & Medical", "Health & Wellness", "Groceries & Supermarket"]
    },
    {
        "id": 11,
        "query": "recurring monthly payments active memberships autopay charges",
        "expected_domain": ["Software & Subscriptions", "Housing & Rent", "Utilities & Internet"]
    },
    {
        "id": 12,
        "query": "duplicate identical debit charges repeated on the same day",
        "expected_domain": ["Electronics & Shopping", "Software & Subscriptions", "Dining & Takeout"]
    }
]

def main():
    print("=" * 80)
    print("  FinSight AI — Semantic Retrieval Evaluation on Real Db2 Embeddings")
    print("  Model: BAAI/bge-small-en-v1.5 (dim=384, native VECTOR_DISTANCE cosine)")
    print("=" * 80)

    total_queries = len(QUERIES)
    top1_relevant = 0
    top5_relevant = 0

    for item in QUERIES:
        qid = item["id"]
        q = item["query"]
        expected = item["expected_domain"]

        res = requests.post(
            f"{BASE_URL}/api/ai/search",
            json={"query": q, "user_id": DEMO_USER, "limit": 5},
            headers=HEADERS,
            timeout=10
        )
        assert res.status_code == 200, f"Query {qid} failed: {res.text}"
        data = res.json()
        results = data.get("results", [])

        print(f"\n[QUERY {qid:02d}]: \"{q}\"")
        if not results:
            print("   [!] No results returned.")
            continue

        top1 = results[0]
        top1_match = any(e.lower() in top1["category"].lower() for e in expected)
        if top1_match:
            top1_relevant += 1

        any_top5_match = any(
            any(e.lower() in r["category"].lower() for e in expected)
            for r in results
        )
        if any_top5_match:
            top5_relevant += 1

        match_icon = "[RELEVANT]" if top1_match else "[MARGINAL]"
        print(f"   Top-1: {top1['merchant']} | Cat: {top1['category']} | INR {top1['amount']:.2f} | Dist: {top1['distance']:.4f} | Sim: {top1['similarity_score']:.2f} -> {match_icon}")
        print("   Top-5 Breakdown:")
        for rank, r in enumerate(results, 1):
            is_m = any(e.lower() in r["category"].lower() for e in expected)
            flag = "*" if is_m else " "
            print(f"     {rank}. {flag} {r['merchant']:<28} | {r['category']:<24} | INR {r['amount']:>9.2f} | Sim: {r['similarity_score']:.2f}")

    print("\n" + "=" * 80)
    print("  SUMMARY EVALUATION METRICS:")
    print(f"  Precision@1 (Top result directly in target domain): {top1_relevant}/{total_queries} ({top1_relevant/total_queries*100:.1f}%)")
    print(f"  Recall@5 (Target domain present in Top-5 results): {top5_relevant}/{total_queries} ({top5_relevant/total_queries*100:.1f}%)")
    print("=" * 80)

if __name__ == "__main__":
    main()
