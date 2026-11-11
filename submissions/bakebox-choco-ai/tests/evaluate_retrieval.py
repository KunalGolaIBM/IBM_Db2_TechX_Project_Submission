"""
Automated 4-Channel Retrieval Ablation & Evaluation Benchmark for BAKEBOX Choco AI.

Evaluates 30 curated ground-truth queries across 4 categories:
1. Natural Flavor & Celebration Cravings (10 queries)
2. Exact SKU & Product Title Lookups (8 queries)
3. Dietary Constraints & Base Customizations (6 queries)
4. Store Policies & Snack Advisories (6 queries)

Strictly verifies retrieved document/SKU IDs against `expected_ids` across ALL 30 queries
(no heuristic auto-passes) and measures Hit@1, Hit@3, MRR, Precision@3, and CPU latency
across 4 modes: Dense Vector Only, BM25 Only, TF-IDF Only, and 3-Way Hybrid RRF + CRAG.
"""
import os
import sys
import time
from typing import Dict, List, Optional

import numpy as np

_pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

from src.query_engine import ChocoQueryEngine
from src.vector_store import _matches_metadata_filters

BENCHMARK_TEST_SUITE = [
    # Category 1: Natural Flavor & Celebration Cravings (10 Queries)
    {"query": "I want to order a red velvet cake for anniversary celebration", "expected_ids": ["BB-RED-02-1kg", "BB-RED-01-1kg", "BB-RED-05-1kg"], "category": "Semantic Craving"},
    {"query": "Suggest something romantic heart shaped with chocolate or red velvet", "expected_ids": ["BB-RED-02-1kg"], "category": "Semantic Craving"},
    {"query": "Classic chocolate cake with dark cocoa and sweet cherry syrup", "expected_ids": ["BB-BLK-01-05kg", "BB-BLK-02-05kg", "BB-BLK-03-05kg"], "category": "Semantic Craving"},
    {"query": "Pineapple fruity cake with real fruit chunks for birthday", "expected_ids": ["BB-PIN-01-05kg"], "category": "Semantic Craving"},
    {"query": "Dark cocoa sponge with Belgian chocolate curls and cherries", "expected_ids": ["BB-BLK-01-05kg", "BB-BLK-03-05kg"], "category": "Semantic Craving"},
    {"query": "Crimson cocoa cake with cream cheese frosting", "expected_ids": ["BB-RED-01-1kg", "BB-RED-02-1kg"], "category": "Semantic Craving"},
    {"query": "Golden yellow mirror cake with caramelized fruit", "expected_ids": ["BB-PIN-01-05kg"], "category": "Semantic Craving"},
    {"query": "Multi layered velvet sponge with wild berry compote", "expected_ids": ["BB-RED-05-1kg"], "category": "Semantic Craving"},
    {"query": "Hand piped lattice chocolate grid cake", "expected_ids": ["BB-BLK-02-05kg"], "category": "Semantic Craving"},
    {"query": "Light refreshing fruit flavor cake under Rs 300", "expected_ids": ["BB-PIN-01-05kg", "BB-BLK-01-05kg"], "category": "Semantic Craving"},
    # Category 2: Exact SKU & Product Title Lookups (8 Queries)
    {"query": "BB-RED-01-1kg", "expected_ids": ["BB-RED-01-1kg"], "category": "Exact SKU"},
    {"query": "BB-RED-02-1kg", "expected_ids": ["BB-RED-02-1kg"], "category": "Exact SKU"},
    {"query": "BB-BLK-01-05kg", "expected_ids": ["BB-BLK-01-05kg"], "category": "Exact SKU"},
    {"query": "BB-PIN-01-05kg", "expected_ids": ["BB-PIN-01-05kg"], "category": "Exact SKU"},
    {"query": "Red Velvet Crimson Crumb Crown", "expected_ids": ["BB-RED-01-1kg"], "category": "Product Title"},
    {"query": "Red Velvet Heart Love Affair", "expected_ids": ["BB-RED-02-1kg"], "category": "Product Title"},
    {"query": "Black Forest Classic Cherry Gateau", "expected_ids": ["BB-BLK-01-05kg"], "category": "Product Title"},
    {"query": "Pineapple Classic Spiral Mirror", "expected_ids": ["BB-PIN-01-05kg"], "category": "Product Title"},
    # Category 3: Dietary Constraints & Bilingual Hinglish Base Queries (6 Queries)
    {"query": "bina ande wala red velvet cake in ek kilo size", "expected_ids": ["BB-RED-01-1kg", "BB-RED-02-1kg"], "category": "Dietary / Hinglish"},
    {"query": "100% pure veg eggless pineapple cake aadha kilo", "expected_ids": ["BB-PIN-01-05kg"], "category": "Dietary / Hinglish"},
    {"query": "Pure veg eggless black forest gateau 0.5kg", "expected_ids": ["BB-BLK-01-05kg", "BB-BLK-02-05kg"], "category": "Dietary / Base"},
    {"query": "Khoaa eggless heart cake for saal girah celebration", "expected_ids": ["BB-RED-02-1kg"], "category": "Dietary / Hinglish"},
    {"query": "Vegetarian chocolate cake with eggless base", "expected_ids": ["BB-BLK-01-05kg", "BB-BLK-02-05kg", "BB-BLK-03-05kg"], "category": "Dietary / Base"},
    {"query": "Berry cake with pure veg eggless sponge", "expected_ids": ["BB-RED-05-1kg"], "category": "Dietary / Base"},
    # Category 4: Store Policies & Snack Advisories (Strict ID match verified!) (6 Queries)
    {"query": "Patties ko reheat kaise karna chahiye?", "expected_ids": ["POLICY_PATTY_REHEATING"], "category": "Store Advisory"},
    {"query": "Can I microwave the fresh puff patties?", "expected_ids": ["POLICY_PATTY_REHEATING"], "category": "Store Advisory"},
    {"query": "What is the fresh baking wait time for live cakes?", "expected_ids": ["POLICY_WAIT_TIME"], "category": "Store Policy"},
    {"query": "Where are your bakery branch locations in Mathura?", "expected_ids": ["POLICY_LOCATIONS"], "category": "Store Info"},
    {"query": "What are the store opening and dispatch hours?", "expected_ids": ["POLICY_HOURS"], "category": "Store Info"},
    {"query": "What is the celebration happiness guarantee on damaged orders?", "expected_ids": ["POLICY_HAPPINESS_GUARANTEE"], "category": "Store Policy"},
]


def _extract_doc_key(node) -> str:
    meta = getattr(node, "metadata", {}) or {}
    return meta.get("sku_id") or getattr(node, "id_", "")


def _query_filter(category: str) -> Dict[str, object]:
    if "Policy" in category or "Advisory" in category or "Info" in category:
        return {"type": ["policy", "advisory", "store_info"]}
    return {"type": "cake"}


def _eval_channel(name: str, retrieve_fn) -> Dict[str, float]:
    total = len(BENCHMARK_TEST_SUITE)
    hits_1 = 0
    hits_3 = 0
    rr_sum = 0.0
    prec3_sum = 0.0
    latencies: List[float] = []

    for item in BENCHMARK_TEST_SUITE:
        q = item["query"]
        expected = set(item["expected_ids"])
        flt = _query_filter(item["category"])
        t0 = time.perf_counter()
        top_keys = retrieve_fn(q, flt)[:3]
        latencies.append((time.perf_counter() - t0) * 1000.0)

        first_rank: Optional[int] = None
        relevant_in_top3 = 0
        for r_idx, key in enumerate(top_keys, start=1):
            if key in expected:
                relevant_in_top3 += 1
                if first_rank is None:
                    first_rank = r_idx

        if first_rank == 1:
            hits_1 += 1
        if first_rank is not None:
            hits_3 += 1
            rr_sum += 1.0 / first_rank
        prec3_sum += relevant_in_top3 / 3.0

    return {
        "name": name,
        "hit1": (hits_1 / total) * 100.0,
        "hit3": (hits_3 / total) * 100.0,
        "mrr": rr_sum / total,
        "p3": (prec3_sum / total) * 100.0,
        "latency_ms": sum(latencies) / total,
    }


def run_benchmark() -> List[Dict[str, float]]:
    print("==========================================================================")
    print("BAKEBOX CHOCO AI — 4-CHANNEL RETRIEVAL ABLATION & ACCURACY BENCHMARK (N=30)")
    print("Strict ID Matching Across Semantic, SKU, Hinglish & Policy Ground Truth")
    print("==========================================================================\n")

    engine = ChocoQueryEngine(use_llm=False)
    retriever = engine.retriever

    def _dense_only(q: str, flt: Dict[str, object]) -> List[str]:
        if retriever.vector_store is None:
            return []
        q_emb = retriever.embed_func(q)
        pushed = engine._build_metadata_filter(flt)
        res = retriever.vector_store.query(query_embedding=q_emb, top_k=3, filters=pushed)
        return [_extract_doc_key(n) for n in (res.nodes or [])]

    def _bm25_only(q: str, flt: Dict[str, object]) -> List[str]:
        pushed = engine._build_metadata_filter(flt)
        scores = retriever.bm25.score(q)
        ranked = sorted(
            [
                (scores[i], _extract_doc_key(retriever.corpus_nodes[i]))
                for i in range(len(scores))
                if scores[i] > 0 and _matches_metadata_filters(retriever.corpus_nodes[i].metadata or {}, pushed)
            ],
            reverse=True,
        )
        return [k for _, k in ranked[:3]]

    def _tfidf_only(q: str, flt: Dict[str, object]) -> List[str]:
        pushed = engine._build_metadata_filter(flt)
        q_vec = retriever.tfidf.transform([q])
        sims = (retriever.tfidf_matrix * q_vec.T).toarray().flatten()
        ranked = sorted(
            [
                (float(sims[i]), _extract_doc_key(retriever.corpus_nodes[i]))
                for i in range(len(sims))
                if sims[i] > 0 and _matches_metadata_filters(retriever.corpus_nodes[i].metadata or {}, pushed)
            ],
            reverse=True,
        )
        return [k for _, k in ranked[:3]]

    def _hybrid_rrf_crag(q: str, flt: Dict[str, object]) -> List[str]:
        pushed = engine._build_metadata_filter(flt)
        nodes = retriever.hybrid_retrieve(q, top_k=3, filters=pushed)
        return [_extract_doc_key(n.node) for n in nodes]

    results = [
        _eval_channel("Dense Vector Only (Cosine)", _dense_only),
        _eval_channel("Sparse BM25 Only", _bm25_only),
        _eval_channel("Sparse TF-IDF Only", _tfidf_only),
        _eval_channel("3-Way Hybrid RRF + CRAG", _hybrid_rrf_crag),
    ]

    print(f"{'Channel':<28} | {'Hit@1':>7} | {'Hit@3':>7} | {'MRR':>6} | {'Avg Latency':>11}")
    print("-" * 74)
    for r in results:
        print(f"{r['name']:<28} | {r['hit1']:6.1f}% | {r['hit3']:6.1f}% | {r['mrr']:6.2f} | {r['latency_ms']:8.2f} ms")

    hybrid = results[-1]
    assert hybrid["hit3"] >= 90.0, f"Expected Hit@3 >= 90%, got {hybrid['hit3']:.1f}%"
    print("\n[PASSED] Empirical 4-channel ablation benchmark verified strictly against ground-truth IDs!")
    return results


if __name__ == "__main__":
    run_benchmark()
