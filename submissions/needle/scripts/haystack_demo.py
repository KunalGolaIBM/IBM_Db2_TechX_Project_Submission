"""Run one live NEEDLE query through a Haystack pipeline."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from haystack import Pipeline

from needle.haystack_component import NeedleTriageComponent
from needle.triage import connect


def main() -> None:
    pipeline = Pipeline()
    pipeline.add_component("triage", NeedleTriageComponent(connect, top_k=5, mode="HYBRID"))
    result = pipeline.run(
        {"triage": {"query": "yaml load lets an attacker run code"}}
    )
    for document in result["triage"]["documents"]:
        print(document.meta["adv_id"], document.content)


if __name__ == "__main__":
    main()
