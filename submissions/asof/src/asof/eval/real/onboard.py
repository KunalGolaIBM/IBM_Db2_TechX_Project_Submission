"""Load the US DOT refund rules through Policy intake, as SPR was loaded (asof/eval/unseen/onboard.py).

    python -m asof.eval.real.onboard                 # rebuild US-DOT-REFUNDS in schema ASOF_REAL from the records
    python -m asof.eval.real.onboard --upload 2      # replay the records, then upload v2 live for review

Each upload: intake.read_pdf -> intake.propose (the model proposes, intake's checks run) -> intake.store_draft ->
intake.decide (DECIDE_POLICY_DRAFT, APPLY_DRAFT_ITEM) -> policy.apply_change for any recorded correction: the
console's procedures, as the console's Db2 users. The model's proposals are recorded (onboarding/upload_NN_vN.json,
with the SHA-256 of the messages sent) and replayed only for the same messages; the editor's decisions, with a reason
for each item, are in onboarding/decisions.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from langchain_core.embeddings import Embeddings

from ... import db, intake, policy, schema, seed
from ...config import Settings, get_settings
from ...domains import DOT
from ...llm import build_llm
from ..unseen.onboard import INTAKE_DEADLINE_S, INTAKE_MAX_OUTPUT_TOKENS, OnboardError, RecordingLLM, ReplayLLM
from . import text

HERE = Path(__file__).resolve().parent
RECORDS = HERE / "onboarding"
DECISIONS = RECORDS / "decisions.json"
DOC_ID = DOT.doc_id
DEFAULT_SCHEMA = "ASOF_REAL"
DOCUMENT = (DOC_ID, "US DOT airline refund rules: 14 CFR 259.5(b)(5), 260.6, 260.9 and 260.10 (excerpt)",
            "US Department of Transportation (public domain)",
            "eCFR point-in-time API; see asof/eval/real/PROVENANCE.md. A demonstration, not legal advice")
SQL_CLAUSES = "SELECT COUNT(*) FROM POLICY_CLAUSE WHERE DOC_ID = ?"
SQL_DOC_EXISTS = "SELECT COUNT(*) FROM POLICY_DOC WHERE DOC_ID = ?"


def recording_path(n: int, version: int) -> Path:
    return RECORDS / f"upload_{n:02d}_v{version}.json"


def load_decisions() -> list[dict[str, Any]]:
    if not DECISIONS.exists():
        return []
    uploads: list[dict[str, Any]] = json.loads(DECISIONS.read_text(encoding="utf-8"))["uploads"]
    if [d["upload"] for d in uploads] != list(range(1, len(uploads) + 1)):
        raise OnboardError("decisions.json: uploads must be numbered 1, 2, ... in order")
    return uploads


def prepare(settings: Settings, target: str, embeddings: Embeddings) -> None:
    """A fresh schema (never ASOF): setup's DDL, chain head, grants and the POLICY_DOC row; no other domain's data."""
    if target == db.SCHEMA:
        raise OnboardError("the regulation demonstration has its own schema; it never touches ASOF")
    with db.connection(settings, "admin") as conn:
        schema.drop(conn, target)
        schema.install(conn, target)
        seed.seed_chain_head(conn, target)
        seed.seed_faq(conn, embeddings, target)  # the grants name the FAQ table
        schema.apply_grants(conn, settings.asof_app_user, settings.asof_editor_user, target,
                            analyst_user=settings.asof_analyst_user, mart_user=settings.asof_mart_user,
                            review_user=settings.asof_review_user)
        db.use_schema(conn, target)
        db.execute(conn, seed.SQL_INSERT_DOC, DOCUMENT)
        conn.commit()


def propose(settings: Settings, target: str, version: text.Version, llm: Any) -> tuple[int, list[intake.Proposal]]:
    path = text.pdf_path(version)
    source = intake.read_pdf(path.read_bytes(), path.name)
    with db.connection(settings, "app") as conn:
        proposals, _, model = intake.propose(llm, source, DOC_ID, conn, target)
    with db.connection(settings, "editor") as editor:
        draft_id = intake.store_draft(editor, source, DOC_ID, model, proposals, None, target)
    return draft_id, proposals


def decide(settings: Settings, target: str, draft_id: int, proposals: list[intake.Proposal], d: dict[str, Any],
           embeddings: Embeddings) -> dict[str, Any]:
    by_no = {p.item_no: p.clause_id for p in proposals}
    if {int(k): v for k, v in d["items"].items()} != by_no:
        raise OnboardError(f"upload {d['upload']}: the decision was made on other items than the draft holds")
    with db.connection(settings, "editor") as editor:
        out: dict[str, Any] = intake.decide(editor, draft_id, bool(d["accept"]), d["accept"], embeddings, None, False,
                                            target)
        for c in d.get("changes", []):
            policy.apply_change(editor, policy.PolicyChange(**{k: v for k, v in c.items() if k != "why"}),
                                embeddings, target)
    return out


def rebuild(settings: Settings, target: str, embeddings: Embeddings, upload: int | None = None,
            log: Any = print) -> list[intake.Proposal]:
    """Replay every recorded upload and decision; with `upload`, then upload that version live and leave it pending.
    Returns the live upload's proposals (empty without one)."""
    versions = {v.number: v for v in text.VERSIONS}
    prepare(settings, target, embeddings)
    decisions = load_decisions()
    for d in decisions:
        record = json.loads(recording_path(d["upload"], d["version"]).read_text(encoding="utf-8"))
        draft_id, proposals = propose(settings, target, versions[d["version"]], ReplayLLM(record))
        out = decide(settings, target, draft_id, proposals, d, embeddings)
        log(f"upload {d['upload']} (v{d['version']}): {len(proposals)} proposals, {len(out['applied'])} accepted")
    if upload is None:
        return []
    llm = RecordingLLM(build_llm(settings, fallback=False, max_output_tokens=INTAKE_MAX_OUTPUT_TOKENS,
                                 deadline_s=INTAKE_DEADLINE_S))
    n = len(decisions) + 1
    draft_id, proposals = propose(settings, target, versions[upload], llm)
    pdf = text.pdf_path(versions[upload])
    record = (llm.record or {}) | {"upload": n, "version": upload,
                                  "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()}
    RECORDS.mkdir(exist_ok=True)
    recording_path(n, upload).write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"upload {n} (v{upload}): recorded, draft {draft_id} awaits review")
    return proposals


def complete() -> bool:
    return {d["version"] for d in load_decisions()} >= {v.number for v in text.VERSIONS}


def main(argv: list[str] | None = None) -> int:
    from ...embeddings import get_embeddings
    from ..unseen.onboard import describe

    p = argparse.ArgumentParser(prog="python -m asof.eval.real.onboard", description=__doc__.split("\n\n")[0])
    p.add_argument("--schema", default=DEFAULT_SCHEMA)
    p.add_argument("--upload", type=int, choices=[v.number for v in text.VERSIONS])
    args = p.parse_args(argv)
    settings = get_settings()
    try:
        proposals = rebuild(settings, db.validate_schema(args.schema), get_embeddings(settings.embedding_model),
                            args.upload)
    except (OnboardError, intake.IntakeError, db.DatabaseError) as exc:
        print(f"ONBOARDING FAILED: {exc}")
        return 1
    for prop in proposals:
        print(describe(prop))
    return 0 if complete() or args.upload else 1


if __name__ == "__main__":
    sys.exit(main())
