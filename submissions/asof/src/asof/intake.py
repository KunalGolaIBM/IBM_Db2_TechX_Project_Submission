"""Policy intake: a policy document (PDF) becomes a draft of clause versions that an editor reviews.

    upload PDF -> read_pdf (text, pages, SHA-256)
               -> extract (one structured LLM call: proposed clauses, dates, rule parameters)
               -> check_items (deterministic, per item: verbatim text, quoted date, rule values in the text,
                               unchanged restatements; a failed hard check blocks the item)
               -> store_draft (ADD_POLICY_DRAFT + ADD_POLICY_DRAFT_ITEM, as the editor; nothing is in force)
    editor     -> decide (DECIDE_POLICY_DRAFT, then APPLY_DRAFT_ITEM per accepted item, one transaction;
                          APPLY_DRAFT_ITEM calls APPLY_POLICY_CHANGE for a changed clause)
               -> preview (the same, then CHANGE_IMPACT, then ROLLBACK: nothing is saved)

The model only proposes. Code decides what can be accepted: a clause text that is not in the document word for
word, a date the quoted sentence does not state, or a rule value the clause text does not state blocks the
item, and Db2 refuses to accept a blocked item. An editor chooses what goes into force, and with API users
on, Db2 requires that editor to be someone other than the uploader.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

import ibm_db
import ibm_db_dbi
from langchain_core.embeddings import Embeddings

from . import db, policy, prompts, rules
from .corpus import OPEN_END
from .domains import domain_for
from .embeddings import clause_embedding_text
from .llm import _run_with_deadline
from .schemas import MAX_INTAKE_ITEMS, BankIntakeResult, IntakeClause, IntakeResult

log = logging.getLogger(__name__)

SAMPLE_PDF = Path(__file__).with_name("data") / "samples" / "aurelia-csp-revision-2027-1.pdf"
MAX_PDF_BYTES = 2 * 1024 * 1024
MAX_PAGES = 20
MAX_TEXT_CHARS = 24_000
PARSE_DEADLINE_S = 20.0
MAX_CLAUSE_CHARS = 4000  # POLICY_CLAUSE.CLAUSE_TEXT
MIN_DATE, MAX_DATE = date(2020, 1, 1), date(2035, 12, 31)
KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,59}$")
CLAUSE_ID_RE = re.compile(r"^([A-Z]{3})-([0-9]{3})$")

Kind = Literal["CHANGE", "NEW", "UNCHANGED"]


class IntakeError(ValueError):
    """The document cannot be taken in (not a PDF, too large, encrypted, no text layer...)."""


# ---------- reading the document ----------

@dataclass(frozen=True)
class SourceDocument:
    name: str
    data: bytes
    sha256: str
    pages: list[str]  # normalised text of each page

    @property
    def text(self) -> str:
        return "\n".join(self.pages)


_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                         " ": " ", "­": ""})


def normalize(text: str) -> str:
    """NFKC (which also undoes ligatures such as 'ﬁ'), straight quotes and dashes, one space between words."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).translate(_QUOTES)).strip()


def safe_name(name: str | None) -> str:
    """A display name for the file: its base name, plain characters only, ending in .pdf."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base).strip(" ._")[:120]
    if not base.lower().endswith(".pdf"):
        base = (base or "document") + ".pdf"
    return base


def read_pdf(data: bytes, name: str | None = None) -> SourceDocument:
    """The document's text, page by page, or IntakeError. Parsing runs under a deadline and every limit is
    checked before the text reaches the model."""
    if not data:
        raise IntakeError("the file is empty")
    if len(data) > MAX_PDF_BYTES:
        raise IntakeError(f"the file is larger than {MAX_PDF_BYTES // (1024 * 1024)} MB")
    if b"%PDF-" not in data[:1024]:
        raise IntakeError("the file is not a PDF")

    def parse() -> list[str]:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise IntakeError("the PDF is encrypted; upload an unprotected copy")
        if len(reader.pages) > MAX_PAGES:
            raise IntakeError(f"the PDF has more than {MAX_PAGES} pages; split it into smaller documents")
        return [normalize(page.extract_text() or "") for page in reader.pages]

    try:
        pages = _run_with_deadline(parse, PARSE_DEADLINE_S)
    except IntakeError:
        raise
    except TimeoutError:
        raise IntakeError(f"the PDF could not be read within {PARSE_DEADLINE_S:.0f} s") from None
    except Exception as exc:  # noqa: BLE001 - pypdf raises many types for damaged files
        raise IntakeError(f"the PDF could not be read ({type(exc).__name__})") from None
    total = sum(len(p) for p in pages)
    if not any(pages):
        raise IntakeError("the PDF has no text layer (a scan?); run it through OCR first")
    if total > MAX_TEXT_CHARS:
        raise IntakeError(f"the document has {total} characters of text; the limit for one draft is {MAX_TEXT_CHARS}. "
                          "Split it into smaller documents.")
    return SourceDocument(safe_name(name), data, hashlib.sha256(data).hexdigest(), pages)


# ---------- dates stated in text ----------

_MONTHS = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august",
                                         "september", "october", "november", "december"), start=1)}
_MONTHS.update({k[:3]: v for k, v in list(_MONTHS.items())})
_MONTHS["sept"] = 9
_MON = (r"(january|february|march|april|may|june|july|august|september|october|november|december"
        r"|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)\.?")
_DATE_PATTERNS = (
    (re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MON}\s+(\d{{4}})\b", re.I), lambda m: (m[3], m[2], m[1])),
    (re.compile(rf"\b{_MON}\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I), lambda m: (m[3], m[1], m[2])),
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), lambda m: (m[1], m[2], m[3])),
)


def dates_in(text: str) -> set[date]:
    """Every calendar date written out in the text (1 February 2027, February 1, 2027, 2027-02-01)."""
    found: set[date] = set()
    for pattern, parts in _DATE_PATTERNS:
        for m in pattern.finditer(text):
            y, mo, d = parts(m)
            month = int(mo) if mo.isdigit() else _MONTHS.get(mo.lower().rstrip("."))
            try:
                found.add(date(int(y), int(month), int(d)))
            except (TypeError, ValueError):
                continue
    return found


def _iso(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


# ---------- what the policy has now ----------

@dataclass(frozen=True)
class ExistingVersion:
    version: str
    start: date
    end: date
    text: str
    rule: dict[str, Any]


@dataclass(frozen=True)
class ExistingClause:
    clause_id: str
    area: str
    title: str
    versions: tuple[ExistingVersion, ...]

    def in_force(self, on: date) -> ExistingVersion | None:
        return next((v for v in self.versions if v.start <= on < v.end), None)

    @property
    def latest(self) -> ExistingVersion:
        return max(self.versions, key=lambda v: v.start)

    def later_than(self, on: date) -> list[ExistingVersion]:
        return [v for v in self.versions if v.start > on]


def corpus_clauses(doc_id: str) -> dict[str, ExistingClause]:
    """The policy as seeded, from the shipped corpus, in clause-ID order (the timeline view's order): for the intake
    eval and tests, which need no Db2."""
    from .corpus import load_corpus

    out = {}
    for c in sorted(load_corpus().clauses, key=lambda c: c.clause_id):
        if c.doc_id == doc_id:
            versions = tuple(ExistingVersion(v.version_label, v.bus_start, v.bus_end, v.clause_text, v.rule)
                             for v in c.versions)
            out[c.clause_id] = ExistingClause(c.clause_id, c.area, c.title, versions)
    return out


def existing_clauses(conn: ibm_db_dbi.Connection, doc_id: str, schema: str = db.SCHEMA) -> dict[str, ExistingClause]:
    out = {}
    for c in policy.timeline(conn, schema, doc_id):
        versions = tuple(ExistingVersion(v["version"], v["from"], v["to"], v["text"], v["rule"]) for v in c["versions"])
        out[c["clause_id"]] = ExistingClause(c["clause_id"], c["area"], c["title"], versions)
    return out


# ---------- the model's proposal ----------

def extraction_schema(doc_id: str) -> type[IntakeResult]:
    return BankIntakeResult if domain_for(doc_id).key == "bank" else IntakeResult


def extract(llm, source: SourceDocument, doc_id: str, existing: dict[str, ExistingClause]) -> tuple[IntakeResult, str]:
    """One structured call: the model proposes clause versions. Returns them and the model's name."""
    listed = [(c.clause_id, c.area, c.title, sorted(c.latest.rule)) for c in existing.values()]
    messages = prompts.intake_messages(source.name, source.pages, listed)
    schema = extraction_schema(doc_id)
    result = llm.structured(schema, messages, choices={"existing_clause_id": sorted(existing)}, max_chars=MAX_CLAUSE_CHARS)
    return result.value, llm.info


# ---------- deterministic checks ----------

@dataclass
class Check:
    check: str
    status: Literal["pass", "fail", "warn"]
    detail: str


@dataclass
class Proposal:
    item_no: int
    kind: Kind
    clause_id: str
    area: str
    title: str
    clause_text: str
    rule: dict[str, Any]
    effective_from: date
    effective_to: date | None
    date_quote: str
    source_page: int | None
    checks: list[Check] = field(default_factory=list)
    current: dict[str, Any] | None = None  # the version in force on effective_from, for a CHANGE or UNCHANGED

    @property
    def blocked(self) -> bool:
        return any(c.status == "fail" for c in self.checks)

    @property
    def end(self) -> date:
        return self.effective_to or OPEN_END

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["blocked"] = self.blocked
        return d


@dataclass
class Discarded:
    title: str
    reason: str


def _rule_dict(params) -> tuple[dict[str, Any], list[Check]]:
    rule: dict[str, Any] = {}
    checks: list[Check] = []
    for p in params:
        values = [v for v in (p.number, p.flag, p.items) if v is not None]
        if not KEY_RE.match(p.key or ""):
            checks.append(Check("rule keys", "fail", f"{p.key!r} is not a valid parameter name"))
            continue
        if p.key in rule:
            checks.append(Check("rule keys", "fail", f"{p.key} is given twice"))
            continue
        if len(values) != 1:
            checks.append(Check("rule keys", "fail", f"{p.key} needs exactly one value"))
            continue
        value = values[0]
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        rule[p.key] = value
    if len(json.dumps(rule).encode("utf-8")) > policy.MAX_RULE_BYTES:
        checks.append(Check("rule keys", "fail", f"the parameters exceed {policy.MAX_RULE_BYTES} bytes as JSON"))
    return rule, checks


def rule_checks(text: str, rule: dict[str, Any]) -> list[Check]:
    """Every rule value must be stated in the clause text: numbers with their unit, list items word for word.
    A permission the text states the other way fails; one the checker cannot read is left to the editor."""
    out: list[Check] = []
    quantities = rules.extract_quantities(text)
    lowered = text.casefold()
    for key, value in rule.items():
        if isinstance(value, bool):
            stated = rules.asserted_flag(text, key)
            if stated is None:
                out.append(Check("rule values", "warn", f"{key} = {str(value).lower()}: the text does not state this in a "
                                 "form the rule checker reads; confirm it"))
            elif stated != value:
                out.append(Check("rule values", "fail", f"{key} = {str(value).lower()}, but the text says the opposite"))
            else:
                out.append(Check("rule values", "pass", f"{key} = {str(value).lower()} is what the text says"))
        elif isinstance(value, (int, float)):
            params = rules.rule_params({key: value})
            if not params:
                out.append(Check("rule values", "warn", f"{key} = {value}: the rule checker reads no unit from this "
                                 "name, so it will not check claims against it"))
                continue
            p = params[0]
            if any(u == p.unit and rules._close(v, p.value, u) for q in quantities for u, v in q.forms):
                out.append(Check("rule values", "pass", f"{key} = {value} is stated in the text"))
            else:
                out.append(Check("rule values", "fail", f"{key} = {value} is not stated in the clause text"))
        elif isinstance(value, list):
            missing = [str(x) for x in value if normalize(str(x)).casefold() not in lowered]
            if missing:
                out.append(Check("rule values", "fail", f"{key}: {', '.join(missing)} not in the clause text"))
            else:
                out.append(Check("rule values", "pass", f"{key}: every item is in the text"))
        else:
            out.append(Check("rule values", "warn", f"{key}: a text value the rule checker does not use"))
    return out


def _page_of(snippet: str, source: SourceDocument) -> int | None:
    return next((n for n, page in enumerate(source.pages, start=1) if snippet in page), None)


def _new_id(area: str, existing: dict[str, ExistingClause], taken: set[str]) -> str:
    prefixes = Counter(CLAUSE_ID_RE.match(c.clause_id)[1] for c in existing.values()
                       if c.area == area and CLAUSE_ID_RE.match(c.clause_id))
    prefix = prefixes.most_common(1)[0][0] if prefixes else ("OTH" if area == "other" else area[:3].upper())
    used = [int(m[2]) for cid in [*existing, *taken] if (m := CLAUSE_ID_RE.match(cid)) and m[1] == prefix]
    return f"{prefix}-{(max(used) if used else 0) + 1:03d}"


def check_items(extracted: IntakeResult, source: SourceDocument,
                existing: dict[str, ExistingClause]) -> tuple[list[Proposal], list[Discarded]]:
    """Turn the model's proposal into checked items. Items that cannot even be stored (no usable date, text
    too long) are discarded with a reason; every other failed check is recorded and blocks the item."""
    doc_norm = normalize(source.text)
    doc_dates = dates_in(doc_norm)
    proposals: list[Proposal] = []
    discarded: list[Discarded] = []
    taken: set[str] = set()
    for raw in extracted.clauses[:MAX_INTAKE_ITEMS]:
        proposal = _check_one(raw, source, doc_norm, doc_dates, existing, taken, len(proposals) + 1)
        if isinstance(proposal, Discarded):
            discarded.append(proposal)
            continue
        if proposal.kind == "NEW":
            taken.add(proposal.clause_id)
        proposals.append(proposal)
    for raw in extracted.clauses[MAX_INTAKE_ITEMS:]:
        discarded.append(Discarded(raw.title[:200], f"more than {MAX_INTAKE_ITEMS} proposals in one document"))
    return proposals, discarded


def _check_one(raw: IntakeClause, source: SourceDocument, doc_norm: str, doc_dates: set[date],
               existing: dict[str, ExistingClause], taken: set[str], item_no: int) -> Proposal | Discarded:
    title = normalize(raw.title)[:200] or "Untitled section"
    text = normalize(raw.clause_text)
    start, end = _iso(raw.effective_from), _iso(raw.effective_to)
    if start is None or not MIN_DATE <= start <= MAX_DATE:
        return Discarded(title, f"no usable effective date ({raw.effective_from!r})")
    if raw.effective_to is not None and (end is None or end <= start or end > MAX_DATE):
        return Discarded(title, f"the end date {raw.effective_to!r} is not a date after the start")
    if len(text) < 10 or len(text.encode("utf-8")) > MAX_CLAUSE_CHARS:
        return Discarded(title, "the clause text is empty or longer than 4,000 bytes")

    checks: list[Check] = []
    page = _page_of(text, source)
    if text in doc_norm:
        checks.append(Check("verbatim text", "pass", f"found word for word on page {page}" if page else
                            "found word for word (across a page break)"))
    else:
        checks.append(Check("verbatim text", "fail", "this text is not in the document word for word"))
    if not text.endswith((".", "!", "?", ")", '"')):
        checks.append(Check("verbatim text", "warn", "the text does not end a sentence; it may be cut short"))

    quote = normalize(raw.date_quote)[:1000]
    if not quote or quote not in doc_norm:
        checks.append(Check("effective date", "fail", "the sentence quoted for the date is not in the document"))
    elif start not in dates_in(quote):
        checks.append(Check("effective date", "fail", f"the quoted sentence does not state {start.isoformat()}"))
    else:
        checks.append(Check("effective date", "pass", f"{start.isoformat()} is stated: “{quote[:160]}”"))
    if end is not None:
        # AsOf's periods end on the first day a version no longer applies. "Until 31 August" is stated inclusively,
        # so the right end is 1 September; an end equal to the stated date would drop that last day.
        if end - timedelta(days=1) in doc_dates:
            checks.append(Check("end date", "pass", f"applies through {(end - timedelta(days=1)).isoformat()}, as stated"))
        elif end in doc_dates:
            checks.append(Check("end date", "warn", f"the document states {end.isoformat()}; if that is the last day it "
                                f"applies, the end should be {(end + timedelta(days=1)).isoformat()} (AsOf's end dates "
                                "are exclusive)"))
        else:
            checks.append(Check("end date", "fail", f"the document does not state the end date {end.isoformat()}"))

    rule, key_checks = _rule_dict(raw.rule)
    checks += key_checks + rule_checks(text, rule)
    if not rule:
        checks.append(Check("rule values", "warn", "no checkable parameters: the rule checker will not check this clause"))

    cid = raw.existing_clause_id
    clause = existing.get(cid) if cid else None
    if cid and clause is None:
        checks.append(Check("clause", "warn", f"the model named {cid}, which this policy does not have; "
                            "treated as a new clause"))
    if clause is None:
        new_id = _new_id(raw.area, existing, taken)
        checks.append(Check("clause", "pass", f"a new clause, {new_id}, in {raw.area}"))
        return Proposal(item_no, "NEW", new_id, raw.area, title, text, rule, start, end, quote, page, checks)

    current = clause.in_force(start)
    kind: Kind = "CHANGE"
    if current is not None and normalize(current.text) == text:
        # The policy is the text; the parameters are derived from it. A section restated word for word makes
        # no new version, however the model named its parameters, and the clause keeps the ones it has.
        kind = "UNCHANGED"
        checks = [c for c in checks if c.check not in ("rule keys", "rule values")]
        note = "" if current.rule == rule else " (the model named the parameters differently; the clause keeps its own)"
        checks.append(Check("clause", "pass", f"same text as {clause.clause_id} {current.version} in force on "
                            f"{start.isoformat()}; nothing to apply{note}"))
        rule = current.rule
    else:
        if current is not None:
            # A tier condition ("applies_when": the situation a delay tier covers) cannot be proposed as a flat
            # value; keep the one in force rather than silently losing it, and ask the editor to confirm it.
            for key, value in current.rule.items():
                if isinstance(value, dict) and key not in rule:
                    rule[key] = value
                    checks.append(Check("rule values", "warn", f"{key} kept from {current.version} "
                                        f"({json.dumps(value)}); confirm the new text still describes it"))
            dropped = sorted(set(current.rule) - set(rule))
            if dropped:
                checks.append(Check("rule values", "warn", f"{current.version} had {', '.join(dropped)}; "
                                    "the proposal drops it"))
        later = [v.version for v in clause.later_than(start)] if end is None else []
        if later:
            checks.append(Check("clause", "warn", f"open-ended from {start.isoformat()}, so it also replaces "
                                f"{', '.join(later)}"))
        if raw.area != clause.area:
            checks.append(Check("clause", "warn", f"the model said {raw.area}; the clause is in {clause.area}"))
    cur = None if current is None else {"version": current.version, "from": current.start, "to": current.end,
                                        "text": current.text, "rule": current.rule}
    return Proposal(item_no, kind, clause.clause_id, clause.area, clause.title, text, rule, start, end, quote, page,
                    checks, cur)


def propose(llm, source: SourceDocument, doc_id: str, conn: ibm_db_dbi.Connection,
            schema: str = db.SCHEMA) -> tuple[list[Proposal], list[Discarded], str]:
    """Extract and check. `conn` reads the policy (any user with SELECT on the timeline view)."""
    existing = existing_clauses(conn, doc_id, schema)
    extracted, model = extract(llm, source, doc_id, existing)
    proposals, discarded = check_items(extracted, source, existing)
    return proposals, discarded, model


# ---------- drafts in Db2 ----------

def store_draft(conn: ibm_db_dbi.Connection, source: SourceDocument, doc_id: str, model: str,
                proposals: list[Proposal], user: str | None = None, schema: str = db.SCHEMA) -> int:
    """ADD_POLICY_DRAFT and one ADD_POLICY_DRAFT_ITEM per proposal, as the editor, in one transaction."""
    if not proposals:
        raise IntakeError("the model found no policy sections that could be checked; nothing to review")
    db.use_schema(conn, schema)
    cur = conn.cursor()
    try:
        out = cur.callproc("ADD_POLICY_DRAFT", (doc_id, source.name, source.sha256, source.data, len(source.pages),
                                                source.text, model[:200], user or "", 0))
        draft_id = int(out[8])
        for p in proposals:
            checks = json.dumps([asdict(c) for c in p.checks], default=str)
            while len(checks.encode("utf-8")) > 8000:  # keep the failures; trim passes first
                p.checks.remove(next((c for c in p.checks if c.status == "pass"), p.checks[-1]))
                checks = json.dumps([asdict(c) for c in p.checks], default=str)
            cur.callproc("ADD_POLICY_DRAFT_ITEM", (
                draft_id, p.item_no, p.kind, p.clause_id, p.area, p.title, p.clause_text,
                json.dumps(p.rule, sort_keys=True), p.effective_from, p.end, p.date_quote or "-", p.source_page or 0,
                checks, 1 if p.blocked else 0))
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        raise db.wrap_error(exc, "storing the draft failed") from None
    finally:
        cur.close()
    return draft_id


SQL_DRAFTS = ("SELECT DRAFT_ID, DOC_ID, SOURCE_NAME, SOURCE_SHA256, SOURCE_PAGES, EXTRACTED_BY, STATUS, UPLOADED_BY, "
              "CREATED_AT, DECIDED_AT, DECIDED_BY, DECIDED_BY_USER, "
              "(SELECT COUNT(*) FROM POLICY_DRAFT_ITEM I WHERE I.DRAFT_ID = D.DRAFT_ID), "
              "(SELECT COUNT(*) FROM POLICY_DRAFT_ITEM I WHERE I.DRAFT_ID = D.DRAFT_ID AND I.BLOCKED = 1) "
              "FROM POLICY_DRAFT D ORDER BY DRAFT_ID DESC FETCH FIRST 50 ROWS ONLY")
SQL_DRAFT = ("SELECT DRAFT_ID, DOC_ID, SOURCE_NAME, SOURCE_SHA256, SOURCE_PAGES, EXTRACTED_BY, STATUS, UPLOADED_BY, "
             "CREATED_AT, DECIDED_AT, DECIDED_BY, DECIDED_BY_USER, "
             "(SELECT COUNT(*) FROM POLICY_DRAFT_ITEM I WHERE I.DRAFT_ID = D.DRAFT_ID), "
             "(SELECT COUNT(*) FROM POLICY_DRAFT_ITEM I WHERE I.DRAFT_ID = D.DRAFT_ID AND I.BLOCKED = 1) "
             "FROM POLICY_DRAFT D WHERE DRAFT_ID = ?")
SQL_ITEM_TEXTS = "SELECT ITEM_NO, KIND, CLAUSE_ID, TITLE, CLAUSE_TEXT FROM POLICY_DRAFT_ITEM WHERE DRAFT_ID = ?"
SQL_EMBEDDER_EXISTS = ("SELECT COUNT(*) FROM SYSCAT.EXTERNALMODELS WHERE MODELSCHEMA = CURRENT SCHEMA "
                       "AND MODELNAME = 'EMBEDDER'")
SQL_ITEMS = ("SELECT ITEM_NO, KIND, CLAUSE_ID, AREA, TITLE, CLAUSE_TEXT, RULE_JSON, BUS_START, BUS_END, DATE_QUOTE, "
             "SOURCE_PAGE, CHECKS_JSON, BLOCKED, STATUS, APPLIED_VERSION FROM POLICY_DRAFT_ITEM WHERE DRAFT_ID = ? "
             "ORDER BY ITEM_NO")
SQL_SOURCE = "SELECT SOURCE_NAME, SOURCE_PDF FROM POLICY_DRAFT WHERE DRAFT_ID = ?"
_DRAFT_KEYS = ("draft_id", "doc_id", "source_name", "sha256", "pages", "extracted_by", "status", "uploaded_by",
               "created_at", "decided_at", "decided_by", "decided_by_user", "items", "blocked_items")
_ITEM_KEYS = ("item_no", "kind", "clause_id", "area", "title", "clause_text", "rule", "effective_from", "effective_to",
              "date_quote", "source_page", "checks", "blocked", "status", "applied_version")


def _strip(d: dict[str, Any]) -> dict[str, Any]:
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in d.items()}


def list_drafts(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA) -> list[dict[str, Any]]:
    db.use_schema(conn, schema)
    return [_strip(dict(zip(_DRAFT_KEYS, r, strict=True))) for r in db.query(conn, SQL_DRAFTS)]


def get_draft(conn: ibm_db_dbi.Connection, draft_id: int, schema: str = db.SCHEMA) -> dict[str, Any] | None:
    """The draft and its items, each with the version in force on its date (for a side-by-side view)."""
    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_DRAFT, (draft_id,))
    if not rows:
        return None
    draft = _strip(dict(zip(_DRAFT_KEYS, rows[0], strict=True)))
    existing = existing_clauses(conn, draft["doc_id"], schema)
    items = []
    for r in db.query(conn, SQL_ITEMS, (draft_id,)):
        item = _strip(dict(zip(_ITEM_KEYS, r, strict=True)))
        item["rule"], item["checks"] = json.loads(item["rule"]), json.loads(item["checks"])
        item["blocked"] = bool(item["blocked"])
        if item["effective_to"] and item["effective_to"] >= OPEN_END:
            item["effective_to"] = None
        clause = existing.get(item["clause_id"])
        # What the clause said on that date before this draft: once applied, the draft's own version is in
        # force there, so look for the newest other version that covered the date.
        before = None
        if clause is not None:
            covering = [v for v in clause.versions if v.version != item["applied_version"]
                        and v.start <= item["effective_from"] < v.end]
            older = [v for v in clause.versions if v.version != item["applied_version"]
                     and v.start <= item["effective_from"]]
            pick = covering[0] if covering else (max(older, key=lambda v: v.start) if older else None)
            if item["kind"] != "NEW" and pick is not None:
                before = {"version": pick.version, "from": pick.start, "to": pick.end, "text": pick.text,
                          "rule": pick.rule}
        item["current"] = before
        items.append(item)
    draft["items_detail"] = items
    return draft


def source_pdf(conn: ibm_db_dbi.Connection, draft_id: int, schema: str = db.SCHEMA) -> tuple[str, bytes] | None:
    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_SOURCE, (draft_id,))
    if not rows:
        return None
    name, data = rows[0]
    return name.strip(), bytes(data)


def decide(conn: ibm_db_dbi.Connection, draft_id: int, approve: bool, accept: list[int], embeddings: Embeddings | None,
           user: str | None = None, preview: bool = False, schema: str = db.SCHEMA) -> dict[str, Any]:
    """Approve (accepting the listed items) or reject a draft, as the editor, in one transaction.

    Approval: DECIDE_POLICY_DRAFT claims the draft, then APPLY_DRAFT_ITEM puts each accepted item into force
    (APPLY_POLICY_CHANGE for a changed clause). With preview=True, CHANGE_IMPACT then runs on every changed
    clause and the whole transaction is rolled back: the draft stays pending and the policy is untouched.
    The new versions are embedded by Db2 when the in-database model exists; if it fails, the whole approval
    is retried with local embeddings (never half of it).
    """
    if preview and ibm_db.autocommit(conn.conn_handler):
        raise ValueError("a preview needs a connection without autocommit, or the change would be saved")
    db.use_schema(conn, schema)
    accept = sorted(set(accept))
    if approve and not accept:
        raise ValueError("accept at least one item, or reject the draft")
    if len(",".join(map(str, accept))) > 200:
        raise ValueError("too many items")
    in_db = db.query(conn, SQL_EMBEDDER_EXISTS)[0][0] > 0
    if not in_db and embeddings is None:
        raise ValueError("no in-database embedding model, so a local embeddings model is required")
    try:
        return _decide(conn, draft_id, approve, accept, embeddings, user, preview, in_db, schema)
    except db.DatabaseError as exc:
        if not (approve and in_db and exc.sqlstate == "75014" and embeddings is not None):
            raise
        log.warning("in-database embedding failed for draft %s; retrying the approval with local embeddings", draft_id)
        out = _decide(conn, draft_id, approve, accept, embeddings, user, preview, False, schema)
        out["embedded_in"] = "app (Db2 model unavailable)"
        return out


def _decide(conn, draft_id, approve, accept, embeddings, user, preview, in_db, schema) -> dict[str, Any]:
    cur = conn.cursor()
    applied: list[dict[str, Any]] = []
    try:
        cur.callproc("DECIDE_POLICY_DRAFT", (int(draft_id), 1 if approve else 0, ",".join(map(str, accept)),
                                             user or "", 0))
        if approve:
            items = {r[0]: r for r in db.query(conn, SQL_ITEM_TEXTS, (int(draft_id),))}
            for no in accept:
                _, kind, clause_id, title, text = items[no]
                vector = None if in_db else db.vector_literal(
                    embeddings.embed_query(clause_embedding_text(title.strip(), text)))
                out = cur.callproc("APPLY_DRAFT_ITEM", (int(draft_id), int(no), vector, " " * 20, 0, 0))
                applied.append({"item_no": no, "kind": kind.strip(), "clause_id": clause_id.strip(),
                                "version": str(out[3]).strip(), "rows_changed": int(out[4]),
                                "published_flagged": int(out[5])})
        impact = {}
        if preview:
            for a in applied:
                if a["kind"] == "CHANGE":
                    impact[a["clause_id"]] = policy.change_impact(conn, a["clause_id"], schema)
            conn.rollback()
        else:
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        raise db.wrap_error(exc, "DECIDE_POLICY_DRAFT failed") from None
    finally:
        cur.close()
    return {"draft_id": draft_id, "approved": approve, "preview": preview, "applied": applied,
            "embedded_in": "db2" if in_db else "app", "impact": impact}
