"""SciFact loading interface for reproducible evaluation.

SciFact is distributed under CC BY-NC 2.0; it is not bundled with AEGIS.
Download the dataset from the official release archive:

    https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz

or through HuggingFace: https://huggingface.co/datasets/allenai/scifact

The loader accepts either the official JSONL files or an exported JSON list.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

LABELS = ("SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE")
SCIFACT_TO_AEGIS = {
    "SUPPORT": "SUPPORTED",
    "CONTRADICT": "CONTRADICTED",
    "NEI": "INSUFFICIENT_EVIDENCE",
    "": "INSUFFICIENT_EVIDENCE",
}


@dataclass(frozen=True, slots=True)
class ScifactClaim:
    claim_id: str
    claim: str
    gold_label: str
    cited_doc_ids: tuple[int, ...]
    evidence_doc_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class ScifactDocument:
    doc_id: int
    title: str
    text: str


def _records(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    value = json.loads(text)
    if isinstance(value, dict):
        for key in ("claims", "data", "records"):
            if isinstance(value.get(key), list):
                return value[key]
        raise ValueError("JSON object does not contain a claims array")
    if not isinstance(value, list):
        raise ValueError("Dataset file must contain a JSON array or JSONL records")
    return value


def _derive_label(record: dict) -> str:
    explicit = record.get("gold_label") or record.get("label")
    if explicit:
        return SCIFACT_TO_AEGIS.get(str(explicit).upper(), str(explicit).upper())

    evidence_label = record.get("evidence_label")
    if isinstance(evidence_label, str) and evidence_label.strip():
        return SCIFACT_TO_AEGIS.get(evidence_label.strip().upper(), evidence_label.strip().upper())

    evidence = record.get("evidence")
    if isinstance(evidence, dict):
        labels = set()
        for entries in evidence.values():
            for entry in entries or []:
                if isinstance(entry, dict) and entry.get("label"):
                    labels.add(str(entry["label"]).upper())
        if "CONTRADICT" in labels:
            return "CONTRADICTED"
        if "SUPPORT" in labels:
            return "SUPPORTED"
    return "INSUFFICIENT_EVIDENCE"


def load_scifact_claims(path: str | Path) -> list[ScifactClaim]:
    """Load the claims split. Raises FileNotFoundError if the dataset is absent."""
    claims_path = Path(path)
    if not claims_path.exists():
        raise FileNotFoundError(
            f"SciFact claims file not found: {claims_path}. "
            "Download SciFact from https://github.com/allenai/scifact."
        )
    claims: list[ScifactClaim] = []
    for record in _records(claims_path):
        claim_text = str(record.get("claim") or "").strip()
        if not claim_text:
            continue
        evidence = record.get("evidence")
        evidence_doc_ids: set[int] = set()
        if isinstance(evidence, dict):
            for doc_id in evidence:
                try:
                    evidence_doc_ids.add(int(doc_id))
                except (TypeError, ValueError):
                    continue
        if record.get("evidence_doc_id"):
            try:
                evidence_doc_ids.add(int(record["evidence_doc_id"]))
            except (TypeError, ValueError):
                pass
        cited = record.get("cited_doc_ids") or []
        claims.append(
            ScifactClaim(
                claim_id=str(record.get("id") or record.get("claim_id")),
                claim=claim_text,
                gold_label=_derive_label(record),
                cited_doc_ids=tuple(int(value) for value in cited if str(value).isdigit()),
                evidence_doc_ids=tuple(sorted(evidence_doc_ids)),
            )
        )
    return claims


def load_scifact_corpus(path: str | Path) -> list[ScifactDocument]:
    """Load the SciFact corpus JSONL (title + abstract sentences)."""
    corpus_path = Path(path)
    if not corpus_path.exists():
        raise FileNotFoundError(
            f"SciFact corpus file not found: {corpus_path}. "
            "Download the SciFact data archive from https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
        )
    documents: list[ScifactDocument] = []
    for record in _records(corpus_path):
        try:
            doc_id = int(record["doc_id"])
        except (KeyError, TypeError, ValueError):
            continue
        title = str(record.get("title") or "").strip()
        abstract = record.get("abstract") or []
        if isinstance(abstract, list):
            abstract_text = " ".join(str(sentence).strip() for sentence in abstract)
        else:
            abstract_text = str(abstract).strip()
        if not title and not abstract_text:
            continue
        text = f"{title}\n\n{abstract_text}".strip()
        documents.append(ScifactDocument(doc_id=doc_id, title=title or f"SciFact {doc_id}", text=text))
    return documents


def load_predictions(path: str | Path) -> dict[str, dict]:
    """Load AEGIS predictions keyed by SciFact claim id.

    Expected record:
    {"claim_id": "3", "predicted_label": "SUPPORTED",
     "retrieved_doc_ids": [14717500], "latency_ms": 812.5}
    """
    predictions_path = Path(path)
    if not predictions_path.exists():
        raise FileNotFoundError(f"Predictions file not found: {predictions_path}")
    records = _records(predictions_path)
    predictions: dict[str, dict] = {}
    for record in records:
        claim_id = str(record.get("claim_id") or record.get("id") or "")
        if not claim_id:
            continue
        predictions[claim_id] = record
    return predictions
