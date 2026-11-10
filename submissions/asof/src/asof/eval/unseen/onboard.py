"""Onboard SPR (a fictional railway, written by GPT) the way a new customer's policy reaches Db2: through Policy intake.

    python -m asof.eval.unseen.onboard                  # rebuild SPR in schema ASOF_UNSEEN from the records
    python -m asof.eval.unseen.onboard --schema ASOF    # the same, added to an existing AsOf schema
    python -m asof.eval.unseen.onboard --upload 2       # replay the records, then upload v2 live for review

Each policy version is one PDF (pdf/, made from GPT's .txt files without changing a word). Each upload, in order:

    intake.read_pdf -> intake.propose (the model proposes clause versions; deterministic checks run on them)
    -> intake.store_draft (ADD_POLICY_DRAFT, ADD_POLICY_DRAFT_ITEM, as the editor)
    -> intake.decide (DECIDE_POLICY_DRAFT, then APPLY_DRAFT_ITEM per accepted item, as the editor)
    -> policy.apply_change (APPLY_POLICY_CHANGE, as the editor) for every recorded correction

These are the functions the console's upload, approval and policy-change routes call (api.py), on the same Db2
users. Every upload's model proposal was recorded once, live (onboarding/upload_<nn>_v<n>.json, with the SHA-256
of the exact messages sent), and the editor's decision on it is in onboarding/decisions.json with a reason for
every rejection and correction. A rebuild replays each recorded proposal instead of calling the model, after
checking that intake would send exactly the recorded messages, so the same PDFs and records always give the same
clauses in Db2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.embeddings import Embeddings
from pydantic import BaseModel

from ... import db, intake, policy, schema, seed
from ...config import Settings, get_settings
from ...domains import RAIL
from ...llm import LLMResult, ModelClient, build_llm
from . import pdfs

HERE = Path(__file__).resolve().parent
RECORDS = HERE / "onboarding"
DECISIONS = RECORDS / "decisions.json"
DOC_ID = RAIL.doc_id
DEFAULT_SCHEMA = "ASOF_UNSEEN"
DOCUMENT = (DOC_ID, "Suryapath Railways passenger cancellation and refund policy (fictional)",
            "SPR passenger services (fictional)",
            "Written by GPT as an unseen test set (asof/eval/unseen/PROVENANCE.md); loaded through Policy intake")
# Policy intake copies every clause word for word: 14 sections need more output than one check.
INTAKE_MAX_OUTPUT_TOKENS = 12000
INTAKE_DEADLINE_S = 300.0
SQL_SPR_CLAUSES = "SELECT COUNT(*) FROM POLICY_CLAUSE WHERE DOC_ID = ?"
SQL_DOC_EXISTS = "SELECT COUNT(*) FROM POLICY_DOC WHERE DOC_ID = ?"


class OnboardError(RuntimeError):
    pass


def recording_path(upload_no: int, version: int) -> Path:
    return RECORDS / f"upload_{upload_no:02d}_v{version}.json"


def messages_sha256(messages: list[tuple[str, str]]) -> str:
    return hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode("utf-8")).hexdigest()


class RecordingLLM:
    """Passes intake's one structured call to the real model and keeps what was sent and what came back."""

    def __init__(self, inner: ModelClient) -> None:
        self.inner = inner
        self.record: dict[str, Any] | None = None

    @property
    def info(self) -> str:
        return self.inner.info

    def structured(self, schema: type[BaseModel], messages: list[tuple[str, str]],
                   choices: dict[str, list[str]] | None = None, max_chars: int | None = None) -> LLMResult[Any]:
        result = self.inner.structured(schema, messages, choices, max_chars=max_chars)
        self.record = {"model": self.inner.info, "messages_sha256": messages_sha256(messages),
                       "latency_ms": result.latency_ms, "input_tokens": result.input_tokens,
                       "output_tokens": result.output_tokens, "result": result.value.model_dump(mode="json")}
        return result

    def tool_round(self, messages: list[Any], tools: list[Any]) -> Any:
        raise NotImplementedError("policy intake makes no tool calls")

    def run(self, fn: Any) -> Any:
        return self.inner.run(fn)


class ReplayLLM:
    """Returns the recorded proposal, and only for exactly the recorded messages."""

    def __init__(self, record: dict[str, Any]) -> None:
        self.record = record

    @property
    def info(self) -> str:
        return str(self.record["model"])

    def structured(self, schema: type[BaseModel], messages: list[tuple[str, str]],
                   choices: dict[str, list[str]] | None = None, max_chars: int | None = None) -> LLMResult[Any]:
        if messages_sha256(messages) != self.record["messages_sha256"]:
            raise OnboardError("intake would send the model different messages than were recorded (the PDF, the "
                               "prompt or the clauses already in Db2 differ); record a new live upload")
        return LLMResult(schema.model_validate(self.record["result"]), 0, None, None, 1)

    def tool_round(self, messages: list[Any], tools: list[Any]) -> Any:
        raise NotImplementedError("policy intake makes no tool calls")

    def run(self, fn: Any) -> Any:
        return fn()


@dataclass
class Upload:
    upload_no: int
    version: int
    draft_id: int
    model: str
    proposals: list[intake.Proposal]
    discarded: list[intake.Discarded]
    record: dict[str, Any]
    decision: dict[str, Any] | None = None
    applied: list[dict[str, Any]] = field(default_factory=list)
    changes: list[dict[str, Any]] = field(default_factory=list)
    accuracy: dict[str, Any] = field(default_factory=dict)  # accuracy.score_upload, against the policy text


def current_clauses(settings: Settings, target: str) -> dict[str, intake.ExistingClause]:
    with db.connection(settings, "app") as conn:
        return intake.existing_clauses(conn, DOC_ID, target)


def load_decisions() -> list[dict[str, Any]]:
    """The editor's decisions, one per upload, in upload order."""
    if not DECISIONS.exists():
        return []
    uploads: list[dict[str, Any]] = json.loads(DECISIONS.read_text(encoding="utf-8"))["uploads"]
    for i, d in enumerate(uploads, start=1):
        if d["upload"] != i:
            raise OnboardError(f"decisions.json: entry {i} is for upload {d['upload']}")
    return uploads


def prepare(settings: Settings, target: str, fresh: bool, embeddings: Embeddings) -> None:
    """The schema SPR goes into. Fresh: dropped and rebuilt with setup's DDL, chain head and grants, empty ledger
    (and the demo assistant's FAQ table, which the grants name; no airline or bank clauses).
    Otherwise (an existing AsOf schema such as ASOF): only the POLICY_DOC row is added, and an SPR already there
    is refused, since loading it twice would give it two sets of clauses."""
    with db.connection(settings, "admin") as conn:
        if fresh:
            schema.drop(conn, target)
            schema.install(conn, target)
            seed.seed_chain_head(conn, target)
            seed.seed_faq(conn, embeddings, target)
            schema.apply_grants(conn, settings.asof_app_user, settings.asof_editor_user, target,
                                analyst_user=settings.asof_analyst_user, mart_user=settings.asof_mart_user,
                                review_user=settings.asof_review_user)
        db.use_schema(conn, target)
        if db.query(conn, SQL_SPR_CLAUSES, (DOC_ID,))[0][0]:
            raise OnboardError(f"{target} already has SPR clauses; onboard into a fresh schema instead")
        if not db.query(conn, SQL_DOC_EXISTS, (DOC_ID,))[0][0]:
            db.execute(conn, seed.SQL_INSERT_DOC, DOCUMENT)
            conn.commit()


def propose_version(settings: Settings, target: str, version: int, llm: ModelClient) -> tuple[
        int, str, list[intake.Proposal], list[intake.Discarded]]:
    """Read the PDF, let the model propose (through `llm`), check, and store the draft: the console's upload."""
    data = pdfs.pdf_path(version).read_bytes()
    source = intake.read_pdf(data, pdfs.pdf_path(version).name)
    with db.connection(settings, "app") as conn:
        proposals, discarded, model = intake.propose(llm, source, DOC_ID, conn, target)
    with db.connection(settings, "editor") as editor:
        draft_id = intake.store_draft(editor, source, DOC_ID, model, proposals, None, target)
    return draft_id, model, proposals, discarded


def decide_upload(settings: Settings, target: str, upload: Upload, decision: dict[str, Any],
                  embeddings: Embeddings) -> None:
    """The editor's recorded decision: accept the listed items (DECIDE_POLICY_DRAFT, APPLY_DRAFT_ITEM) or reject
    the draft, then apply each recorded correction (APPLY_POLICY_CHANGE). Every item the decision names must be the
    item it was made on, so a decision can never land on a different proposal."""
    by_no = {p.item_no: p for p in upload.proposals}
    for no, clause_id in decision["items"].items():
        p = by_no.get(int(no))
        if p is None or p.clause_id != clause_id:
            raise OnboardError(f"upload {upload.upload_no} item {no}: the decision was made on {clause_id}, the draft "
                               f"has {p.clause_id if p else 'no such item'}")
    if set(map(int, decision["items"])) != set(by_no):
        raise OnboardError(f"upload {upload.upload_no}: the decision must name every item of the draft")
    accept = [int(n) for n in decision["accept"]]
    with db.connection(settings, "editor") as editor:
        out = intake.decide(editor, upload.draft_id, bool(accept), accept, embeddings, None, False, target)
        for c in decision.get("changes", []):
            change = policy.PolicyChange(**{k: v for k, v in c.items() if k != "why"})
            upload.changes.append(policy.apply_change(editor, change, embeddings, target) | {"clause_id": change.clause_id})
    upload.decision, upload.applied = decision, out["applied"]


def rebuild(settings: Settings, target: str, embeddings: Embeddings, fresh: bool = True,
            upload_version: int | None = None, log: Any = print) -> list[Upload]:
    """Replay every recorded upload and decision in order. With `upload_version`, then upload that version live,
    record the proposal and leave its draft pending: the editor's review comes next."""
    decisions = load_decisions()
    prepare(settings, target, fresh, embeddings)
    done: list[Upload] = []
    from . import accuracy

    for decision in decisions:
        n, version = decision["upload"], decision["version"]
        record = json.loads(recording_path(n, version).read_text(encoding="utf-8"))
        existing = current_clauses(settings, target)
        draft_id, model, proposals, discarded = propose_version(settings, target, version, ReplayLLM(record))
        upload = Upload(n, version, draft_id, model, proposals, discarded, record)
        upload.accuracy = accuracy.score_upload(version, proposals, discarded)
        accept, reasons = accuracy.review(version, proposals, existing)
        if (accept, reasons) != (decision["accept"], decision["notes"]):
            raise OnboardError(f"upload {n}: the recorded decision is not what the editor's rule gives")
        decide_upload(settings, target, upload, decision, embeddings)
        log(f"upload {n} (v{version}): draft {draft_id}, {len(proposals)} proposals, {len(upload.applied)} accepted, "
            f"{len(upload.changes)} corrections")
        done.append(upload)
    n = len(decisions) + 1
    path = recording_path(n, upload_version or 0)
    if upload_version is not None:
        llm = RecordingLLM(build_llm(settings, fallback=False, max_output_tokens=INTAKE_MAX_OUTPUT_TOKENS,
                                     deadline_s=INTAKE_DEADLINE_S))
        draft_id, model, proposals, discarded = propose_version(settings, target, upload_version, llm)
        record = (llm.record or {}) | {"upload": n, "version": upload_version,
                                      "pdf_sha256": hashlib.sha256(pdfs.pdf_path(upload_version).read_bytes()).hexdigest()}
        RECORDS.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        log(f"upload {n} (v{upload_version}): live proposal recorded in {path.name}; draft {draft_id} awaits review")
        done.append(Upload(n, upload_version, draft_id, model, proposals, discarded, record))
    return done


MAX_UPLOADS_PER_VERSION = 5


def missing_sections(settings: Settings, target: str, version: int) -> list[str]:
    """The sections of `version` whose text is not what SPR has in force on that version's first day."""
    from . import accuracy

    with db.connection(settings, "app") as conn:
        existing = intake.existing_clauses(conn, DOC_ID, target)
    on = accuracy.STARTS[version]
    in_force = {accuracy._fold(v.text) for c in existing.values() if (v := c.in_force(on)) is not None}
    return [s.ref for s in accuracy.sections(version)
            if not any(accuracy._whole(s, t) for t in in_force) and accuracy._fold(s.text) not in in_force]


def drive(settings: Settings, target: str, embeddings: Embeddings, log: Any = print) -> None:
    """Replay the records, then upload each version live until every one of its sections is in force or it has had
    MAX_UPLOADS_PER_VERSION uploads, deciding each upload by the editor's rule (accuracy.review) and recording it."""
    from . import accuracy

    rebuild(settings, target, embeddings, fresh=True, log=log)
    decisions = load_decisions()
    for version in pdfs.VERSIONS:
        while (missing := missing_sections(settings, target, version)) and \
                sum(d["version"] == version for d in decisions) < MAX_UPLOADS_PER_VERSION:
            n = len(decisions) + 1
            with db.connection(settings, "app") as conn:
                existing = intake.existing_clauses(conn, DOC_ID, target)
            llm = RecordingLLM(build_llm(settings, fallback=False, max_output_tokens=INTAKE_MAX_OUTPUT_TOKENS,
                                         deadline_s=INTAKE_DEADLINE_S))
            draft_id, model, proposals, discarded = propose_version(settings, target, version, llm)
            record = (llm.record or {}) | {"upload": n, "version": version, "pdf_sha256": hashlib.sha256(
                pdfs.pdf_path(version).read_bytes()).hexdigest()}
            recording_path(n, version).write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n",
                                                  encoding="utf-8")
            accept, reasons = accuracy.review(version, proposals, existing)
            decision = {"upload": n, "version": version, "items": {str(p.item_no): p.clause_id for p in proposals},
                        "accept": accept, "missing_before": missing, "notes": reasons, "changes": []}
            upload = Upload(n, version, draft_id, model, proposals, discarded, record)
            decide_upload(settings, target, upload, decision, embeddings)
            decisions.append(decision)
            DECISIONS.write_text(json.dumps({"uploads": decisions}, indent=1, ensure_ascii=False) + "\n",
                                 encoding="utf-8")
            log(f"upload {n} (v{version}): {len(proposals)} proposals, accepted {accept}; missing before: "
                f"{', '.join(missing)}")
        log(f"v{version}: still missing {missing_sections(settings, target, version) or 'nothing'}")


def describe(p: intake.Proposal) -> str:
    """One proposal as the editor reviews it."""
    flags = [f"{c.status.upper()} {c.check}: {c.detail}" for c in p.checks if c.status != "pass"]
    end = p.effective_to.isoformat() if p.effective_to else "open"
    lines = [f"#{p.item_no} {p.kind} {p.clause_id} [{p.area}] {p.title!r} {p.effective_from}..{end}"
             f"{' BLOCKED' if p.blocked else ''}",
             f"   rule {json.dumps(p.rule, sort_keys=True)}",
             f"   text {p.clause_text[:300]}{'...' if len(p.clause_text) > 300 else ''}"]
    lines += [f"   {f}" for f in flags]
    return "\n".join(lines)


def complete() -> bool:
    """Every version has at least one decided upload."""
    return {d["version"] for d in load_decisions()} >= set(pdfs.VERSIONS)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m asof.eval.unseen.onboard", description=__doc__.split("\n\n")[0])
    p.add_argument("--schema", default=DEFAULT_SCHEMA,
                   help=f"target schema (default {DEFAULT_SCHEMA}, dropped and rebuilt; ASOF is added to, never dropped)")
    p.add_argument("--upload", type=int, choices=pdfs.VERSIONS,
                   help="after replaying the records, upload this version live and record the model's proposal")
    p.add_argument("--drive", action="store_true",
                   help="after replaying the records, upload live and decide by the editor's rule until every version "
                        f"is in force or has had {MAX_UPLOADS_PER_VERSION} uploads (records every upload)")
    args = p.parse_args(argv)
    from ...embeddings import get_embeddings

    target = db.validate_schema(args.schema)
    settings = get_settings()
    fresh = target != db.SCHEMA  # never drop the main schema
    if args.drive:
        if not fresh:
            p.error("--drive rebuilds its schema from scratch; use the default schema")
        drive(settings, target, get_embeddings(settings.embedding_model), log=lambda m: print(m, flush=True))
        return 0
    try:
        uploads = rebuild(settings, target, get_embeddings(settings.embedding_model), fresh=fresh,
                          upload_version=args.upload)
    except (OnboardError, intake.IntakeError, db.DatabaseError) as exc:
        print(f"ONBOARDING FAILED: {exc}")
        return 1
    for u in uploads:
        if u.decision is None:
            print(f"\nupload {u.upload_no} (v{u.version}) proposals ({u.model}):")
            for prop in u.proposals:
                print(describe(prop))
            for d in u.discarded:
                print(f"discarded: {d.title!r}: {d.reason}")
    print(f"\nSPR in {target}: {len([u for u in uploads if u.decision])} uploads replayed and decided"
          + ("" if complete() else "; not every version is loaded yet"))
    if complete() and not args.upload:
        from .docblocks import INTAKE_REPORT, write_intake

        write_intake(uploads)
        print(f"wrote {INTAKE_REPORT.name}")
    return 0 if complete() or args.upload else 1


if __name__ == "__main__":
    sys.exit(main())
