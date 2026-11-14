"""Frozen held-out evaluation; never adjusts rules, thresholds or knowledge data."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from adapters.embeddings import LocalHashEmbedder  # noqa: E402
from adapters.memory import MemoryRepository  # noqa: E402
from domain.models import ScreenRequest  # noqa: E402
from domain.scoring import RiskEngine  # noqa: E402
from load_scam_examples import DATA_DIR, load_examples, read_examples  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db2", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    embedder = LocalHashEmbedder(768)
    if args.db2:
        from adapters.db2 import Db2Repository
        repo = Db2Repository()
    else:
        repo = MemoryRepository(embedder)
    try:
        load_examples(repo, embedder)
        heldout = read_examples(DATA_DIR / "heldout_v1.csv")
        assert not {r["text"].strip().casefold() for r in heldout}.intersection(
            r["text"].strip().casefold() for r in read_examples())
        engine = RiskEngine(repo, embedder)
        tp = fp = fn = tn = 0
        rows = []
        for row in heldout:
            result = engine.screen(ScreenRequest(message=row["text"]), persist=False)
            if result.degraded:
                raise RuntimeError(f"Evaluation dependency failed: {result.unavailable}")
            scam, flagged = row["label"] != "safe", result.verdict != "ALLOW"
            tp += int(scam and flagged)
            fn += int(scam and not flagged)
            fp += int(not scam and flagged)
            tn += int(not scam and not flagged)
            rows.append({"label": row["label"], "verdict": result.verdict, "score": result.risk_score})
        out = {"backend": "db2" if args.db2 else "memory", "embedder": embedder.name,
               "matrix_rows": ["actual_scam", "actual_safe"], "matrix_columns": ["flagged", "allowed"],
               "confusion_matrix": [[tp, fn], [fp, tn]],
               "precision": tp / (tp + fp) if tp + fp else 0,
               "recall": tp / (tp + fn) if tp + fn else 0,
               "false_positive_rate": fp / (fp + tn) if fp + tn else 0, "predictions": rows}
        print(json.dumps(out, indent=2))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    finally:
        if args.db2:
            repo.close()


if __name__ == "__main__":
    main()
