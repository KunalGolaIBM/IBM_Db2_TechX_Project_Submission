"""Indian Railways refunds: the third public demo domain, a summary of public rules in AsOf's own words.

    python -m asof.indianrail            # load it into schema ASOF if it is missing (replays the recorded intake)
    python -m asof.indianrail --schema X # the same, into schema X
    python -m asof.indianrail pdfs       # rewrite the PDFs from data/indian_rail.json

Summary of public rules, not an official IRCTC or Indian Railways statement. Every number is in one data file,
data/indian_rail.json: each version's summary text, its sources and its time bands. The domain goes into Db2 the way a
customer's policy does: a text-layer PDF per version through Policy intake (v1 as a new document, v2 as a dated new
version), the editor accepting each proposal that is a whole section of the document, then one editor correction per
version through APPLY_POLICY_CHANGE that adds the fare table's time bands to RULE_JSON (rules.band_check reads them)
and puts the version's sources in the row's CHANGE_NOTE, so the clause text and its quotes stay the summary's.

The model's intake proposals come from the shipped recording (data/replay.json), whatever LLM_PROVIDER is, so every
database gets the same clauses: the public demo, which runs in replay mode, a developer's, and CI's. `python -m
asof.replay record --only indian-rail` records them (and the two playground scenarios) with a live model.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from langchain_core.embeddings import Embeddings

from . import db, intake, policy, seed
from .config import Settings

DATA = "indian_rail.json"
SAMPLES = Path(__file__).with_name("data") / "samples"
# Intake and APPLY_POLICY_CHANGE store no date before 2020-01-01 (intake.MIN_DATE): a version in force from earlier
# is loaded as in force from then, and its PDF says so.
FLOOR = date(2020, 1, 1)
SQL_CLAUSES = "SELECT COUNT(*) FROM POLICY_CLAUSE WHERE DOC_ID = ?"
SQL_DOC = "SELECT COUNT(*) FROM POLICY_DOC WHERE DOC_ID = ?"


class LoadError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def data() -> dict[str, Any]:
    out: dict[str, Any] = json.loads((resources.files("asof") / "data" / DATA).read_text(encoding="utf-8"))
    return out


def doc_id() -> str:
    return str(data()["doc"]["doc_id"])


def start(version: dict[str, Any]) -> date:
    return max(date.fromisoformat(version["effective"]), FLOOR)


def document(version: dict[str, Any]) -> str:
    """One version's PDF text: the label, the dates, the basis and sources, then the summary's sections."""
    loaded = start(version)
    lines = [f"Indian Railways ticket cancellation refunds, version {version['version']}.",
             data()["label"],
             f"In force from {version['effective_words']}. Loaded into AsOf as in force from {loaded.isoformat()}"
             + (", the earliest date AsOf stores." if loaded != date.fromisoformat(version["effective"]) else "."),
             f"Basis: {version['basis']}", "Sources: " + " ".join(version["sources"]), ""]
    for s in version["sections"]:
        lines += [s["heading"], s["text"], ""]
    return "\n".join(lines).rstrip() + "\n"


def pdf_path(version: dict[str, Any]) -> Path:
    return SAMPLES / f"indian-rail-refunds-v{version['version']}.pdf"


def build_pdf(version: dict[str, Any]) -> bytes:
    from .eval.unseen.pdfs import make_pdf

    return make_pdf(document(version), f"Indian Railways refunds v{version['version']} (summary)")


def write_pdfs() -> list[Path]:
    out = []
    for v in data()["versions"]:
        pdf_path(v).write_bytes(build_pdf(v))
        out.append(pdf_path(v))
    return out


def accept(proposals: list[intake.Proposal], version: dict[str, Any]) -> tuple[list[int], dict[int, str]]:
    """The editor's rule: accept an item intake's checks let through whose text is one whole section of this version
    and that changes something; reject anything else, with the reason. Returns the items and each section's clause."""
    sections = {intake.normalize(s["text"]): s["heading"] for s in version["sections"]}
    taken: dict[int, str] = {}
    accepted = []
    for p in proposals:
        heading = sections.get(intake.normalize(p.clause_text))
        if p.blocked or p.kind == "UNCHANGED" or heading is None or heading in taken.values():
            continue
        accepted.append(p.item_no)
        taken[p.item_no] = heading
    return accepted, taken


def table_rule(proposed: dict[str, Any], bands: list[dict[str, Any]]) -> dict[str, Any]:
    """The editor's RULE_JSON for the fare table: its time bands, plus intake's yes/no and list parameters. Intake's
    numbers are dropped: a single hour limit, percentage or amount cannot say which band it belongs to, and the rule
    check would compare every claim with it (a "less than 8 hours" claim against a 72-hour "minimum", for one)."""
    keep = {k: v for k, v in proposed.items() if isinstance(v, (bool, list, str))}
    return keep | {"time_bands": bands}


def _change_note(version: dict[str, Any]) -> str:
    return (f"Summary of public rules, version {version['version']}, not official. Sources: "
            + " ".join(version["sources"]) + ". Time bands added by the editor from data/indian_rail.json.")[:400]


def load(settings: Settings, target: str, llm: Any, embeddings: Embeddings, log: Any = print) -> dict[str, Any]:
    """Load the domain into `target` unless its clauses are there already. `llm` answers intake's extraction (the
    shipped recording, or a Recorder around a live model when recording). Returns what was done."""
    from .domains import domain_for

    doc = data()["doc"]
    with db.connection(settings, "admin") as conn:
        db.use_schema(conn, target)
        if db.query(conn, SQL_CLAUSES, (doc["doc_id"],))[0][0]:
            return {"loaded": False, "reason": "already loaded"}
        if not db.query(conn, SQL_DOC, (doc["doc_id"],))[0][0]:
            db.execute(conn, seed.SQL_INSERT_DOC, (doc["doc_id"], doc["title"], doc["owner_team"], doc["source_note"]))
            conn.commit()
    max_items = domain_for(doc["doc_id"]).intake_max_items
    summary: dict[str, Any] = {"loaded": True, "versions": []}
    versions = data()["versions"]
    for i, v in enumerate(versions):
        path = pdf_path(v)
        source = intake.read_pdf(path.read_bytes(), path.name)
        with db.connection(settings, "app") as conn:
            existing = intake.existing_clauses(conn, doc["doc_id"], target)
            extracted, model = intake.extract(llm, source, doc["doc_id"], existing)
        proposals, _ = intake.check_items(extracted, source, existing, max_items)
        items, sections = accept(proposals, v)
        if len(sections) != len(v["sections"]):
            raise LoadError(f"version {v['version']}: intake proposed {len(sections)} of its {len(v['sections'])} "
                            "sections as whole, unblocked items; nothing loaded beyond this version")
        with db.connection(settings, "editor") as editor:
            draft = intake.store_draft(editor, source, doc["doc_id"], model, proposals, None, target)
            intake.decide(editor, draft, True, items, embeddings, None, False, target)
        by_heading = {h: p.clause_id for p in proposals for no, h in sections.items() if p.item_no == no}
        end = start(versions[i + 1]) if i + 1 < len(versions) else None
        with db.connection(settings, "app") as reader:  # the editor holds no SELECT on the timeline view
            timeline = {c["clause_id"]: c["versions"] for c in policy.timeline(reader, target, doc["doc_id"])}
        with db.connection(settings, "editor") as editor:
            for s in v["sections"]:
                clause_id = by_heading[s["heading"]]
                row = next(x for x in timeline[clause_id] if x["from"] <= start(v) < x["to"])
                label = f"v{max(int(x['version'][1:]) for x in timeline[clause_id]) + 1}"
                policy.apply_change(editor, policy.PolicyChange(
                    clause_id=clause_id, effective_from=start(v), effective_to=end, version_label=label,
                    clause_text=row["text"], rule=table_rule(row["rule"], v["time_bands"]),
                    change_note=_change_note(v)), embeddings, target)
        summary["versions"].append({"version": v["version"], "draft_id": draft, "items": items,
                                    "clauses": sorted(by_heading.values())})
        log(f"  {doc['doc_id']} v{v['version']}: draft {draft}, accepted {items}, time bands added")
    return summary


def ensure(settings: Settings, target: str, embeddings: Embeddings, log: Any = print) -> dict[str, Any]:
    """Load the domain from the shipped recording if it is missing (setup and the demo call this)."""
    from .replay import Recording, ReplayLLM, ReplayMiss

    try:
        return load(settings, target, ReplayLLM(Recording.load()), embeddings, log)
    except ReplayMiss:
        log(f"  {doc_id()}: the shipped recording has no intake for these PDFs yet; not loaded "
            "(python -m asof.replay record --only indian-rail)")
        return {"loaded": False, "reason": "not recorded"}


def main(argv: list[str] | None = None) -> int:
    from .config import get_settings
    from .embeddings import get_embeddings

    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["pdfs"]:
        for p in write_pdfs():
            print(f"wrote {p.name}")
        return 0
    target = db.validate_schema(args[args.index("--schema") + 1]) if "--schema" in args else db.SCHEMA
    settings = get_settings()
    out = ensure(settings, target, get_embeddings(settings.embedding_model))
    print(out)
    return 0 if out.get("loaded") or out.get("reason") == "already loaded" else 1


if __name__ == "__main__":
    sys.exit(main())
