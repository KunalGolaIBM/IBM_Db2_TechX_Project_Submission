"""Intake accuracy for SPR: what Policy intake proposed for each upload, scored against GPT's policy text.

The reference is the text itself, split into its numbered sections (P-01 to P-09, E1 to E5). For each section of
the uploaded version: did a proposal copy it whole, copy only part of it, merge it with another, or miss it? For
each proposal: is its text in the document, which section is it, are its dates the version's dates, and are the
values in its rule parameters stated in the text? Nothing here calls a model or Db2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from ... import intake
from . import pdfs

HEAD = re.compile(r"^(P-\d\d|E\d)\.\s+(.*)$")
# The dates each version applies to, as AsOf stores them: the end is the first day the version no longer applies.
STARTS = {1: date(2026, 1, 1), 2: date(2026, 5, 1), 3: date(2026, 9, 1)}
ENDS: dict[int, date | None] = {1: date(2026, 5, 1), 2: date(2026, 9, 1), 3: None}
# The one sentence of the document that only says when the policy applies (intake's prompt leaves such sentences out).
_PERIOD_SENTENCE = re.compile(r"This policy governs bookings made from \S+ through \S+\. ?")
# A value the text states with its unit: INR 240, 50%, 48 h, 4 hours, 180 minutes, 7 calendar days, 3 passengers.
_VALUE = re.compile(r"INR (\d+)|(\d+)%|(\d+) ?(?:h|hours?)\b|(\d+)[- ]minutes?\b|(\d+) calendar days|"
                    r"(\d+) passengers?\b")


@dataclass(frozen=True)
class Section:
    ref: str
    title: str
    text: str  # normalised as intake normalises the document

    @property
    def values(self) -> set[float]:
        return {float(next(g for g in m.groups() if g)) for m in _VALUE.finditer(self.text)}


def sections(version: int) -> list[Section]:
    """The version's numbered sections, in order, from the .txt file. A heading line in capitals is a title; one
    with lower-case words (E5) starts the section's text."""
    out: list[tuple[str, str, list[str]]] = []
    for line in pdfs.text_path(version).read_text(encoding="utf-8").split("\n"):
        m = HEAD.match(line)
        if m:
            rest = m.group(2)
            out.append((m.group(1), "", [rest]) if re.search(r"[a-z]", rest) else (m.group(1), rest, []))
        elif out and line.strip():
            out[-1][2].append(line)
    return [Section(ref, intake.normalize(title), intake.normalize(" ".join(body))) for ref, title, body in out]


def _fold(text: str) -> str:
    return intake.normalize(text).casefold()


def section_of(text: str, secs: list[Section]) -> list[str]:
    """The sections a proposal's text comes from: the one it lies within, or every one it spans."""
    t = _fold(text)
    inside = [s.ref for s in secs if t and t in _fold(s.text)]
    if inside:
        return inside[:1]
    return [s.ref for s in secs if _fold(s.text) and _fold(s.text) in t]


def coverage(section: Section, text: str) -> str:
    """complete, partial or merged: how a proposal's text relates to one section."""
    t, s = _fold(text), _fold(section.text)
    if t == s or t == _fold(_PERIOD_SENTENCE.sub("", section.text)):
        return "complete"
    if t in s:
        return "partial"
    return "merged" if s in t else "none"


def _numbers(rule: dict[str, Any]) -> set[float]:
    return {float(v) for v in rule.values() if isinstance(v, (int, float)) and not isinstance(v, bool)}


def score_upload(version: int, proposals: list[intake.Proposal], discarded: list[intake.Discarded],
                 already: set[str] | None = None) -> dict[str, Any]:
    """One upload against its version's sections. `already`: sections an earlier upload of this version put in force."""
    secs = sections(version)
    by_ref = {s.ref: s for s in secs}
    rows: list[dict[str, Any]] = []
    found: dict[str, str] = {}
    for p in proposals:
        refs = section_of(p.clause_text, secs)
        verbatim = not any(c.check == "verbatim text" and c.status == "fail" for c in p.checks)
        kinds = [coverage(by_ref[r], p.clause_text) for r in refs]
        for r, k in zip(refs, kinds, strict=True):
            if found.get(r) != "complete":
                found[r] = k
        end_ok = p.effective_to is None or p.effective_to == ENDS[version]
        version_end = ENDS[version]
        rule_checks = [c for c in p.checks if c.check in ("rule values", "rule keys")]
        stated = set().union(*(by_ref[r].values for r in refs)) if refs else set()
        rows.append({
            "item_no": p.item_no, "kind": p.kind, "clause_id": p.clause_id, "area": p.area, "title": p.title,
            "sections": refs, "coverage": kinds, "verbatim": verbatim, "invented": not refs and not verbatim,
            "from": p.effective_from.isoformat(), "to": p.effective_to.isoformat() if p.effective_to else None,
            "from_ok": p.effective_from == STARTS[version], "to_ok": end_ok,
            "to_gap": p.effective_to is not None and version_end is not None and p.effective_to < version_end,
            "params": len(p.rule),
            "params_pass": sum(c.status == "pass" for c in rule_checks if c.detail.split(" ")[0].rstrip(":") in p.rule),
            "params_warn": sum(c.status == "warn" for c in rule_checks if c.detail.split(" ")[0].rstrip(":") in p.rule),
            "params_fail": sum(c.status == "fail" for c in rule_checks),
            "values_in_text": len(stated), "values_captured": len(stated & _numbers(p.rule)),
            "values_not_in_text": sorted(_numbers(p.rule) - stated),
            "blocked": p.blocked, "failures": [f"{c.check}: {c.detail}" for c in p.checks if c.status == "fail"],
        })
    already = already or set()
    per_section: list[dict[str, Any]] = [{"section": s.ref, "title": s.title, "outcome": found.get(s.ref) or
                    ("in force from an earlier upload" if s.ref in already else "missed"),
                    "values_in_text": len(s.values)} for s in secs]
    return {"version": version, "sections": per_section, "proposals": rows,
            "discarded": [{"title": d.title, "reason": d.reason} for d in discarded],
            "summary": {"sections": len(secs), "proposed": len(proposals),
                        "complete": sum(r["outcome"] == "complete" for r in per_section),
                        "partial": sum(r["outcome"] == "partial" for r in per_section),
                        "merged": sum(r["outcome"] == "merged" for r in per_section),
                        "missed": sum(r["outcome"] == "missed" for r in per_section),
                        "invented": sum(r["invented"] for r in rows),
                        "blocked": sum(r["blocked"] for r in rows),
                        "wrong_start": sum(not r["from_ok"] for r in rows),
                        "wrong_end": sum(not r["to_ok"] for r in rows),
                        "values_in_text": sum(r["values_in_text"] for r in per_section),
                        "values_captured": sum(r["values_captured"] for r in rows),
                        "values_not_in_text": sum(len(r["values_not_in_text"]) for r in rows)}}


# ---------- the editor's review, as a rule ----------
# The editor's decision on each upload follows one written rule, so it is the same for every upload and can be
# checked against the record (tests/test_unseen_onboarding.py):
#   accept an item when intake's checks let it through, its text is one whole section of the document, and it is
#   filed under the right clause: a CHANGE must be a new version of the clause that holds that section, and a NEW
#   clause must be for a section no clause holds yet;
#   reject everything else, with the reason; a draft with nothing to accept is rejected.
# "Whole" allows one thing: E5 in v1 and v2 opens with the words "NOT IN FORCE -", which read as its heading, and a
# proposal may leave them out.
MAX_LEAD_WORDS = 4


def ref_of_clause(text: str) -> str | None:
    """The section a clause's text is, looked up in every version (the section numbers are the same in all three)."""
    for v in pdfs.VERSIONS:
        refs = section_of(text, sections(v))
        if len(refs) == 1:
            return refs[0]
    return None


def _whole(section: Section, text: str) -> bool:
    if coverage(section, text) == "complete":
        return True
    s, t = _fold(section.text).split(), _fold(text).split()
    return 0 < len(s) - len(t) <= MAX_LEAD_WORDS and s[len(s) - len(t):] == t


def review(version: int, proposals: list[intake.Proposal],
           existing: dict[str, intake.ExistingClause]) -> tuple[list[int], dict[str, str]]:
    """The items to accept and a reason for every item, under the rule above."""
    secs = sections(version)
    by_ref = {s.ref: s for s in secs}
    held = {cid: ref_of_clause(c.latest.text) for cid, c in existing.items()}
    taken = {ref for ref in held.values() if ref}
    accept: list[int] = []
    reasons: dict[str, str] = {}
    for p in proposals:
        refs = section_of(p.clause_text, secs)
        ref = refs[0] if len(refs) == 1 else None
        if p.blocked:
            why = "blocked by intake's checks: " + "; ".join(f"{c.check}: {c.detail}" for c in p.checks
                                                             if c.status == "fail")
        elif p.kind == "UNCHANGED":
            why = f"restates {p.clause_id} word for word; nothing to apply"
        elif ref is None:
            why = "its text is not one section of the document" + (f" (it spans {', '.join(refs)})" if refs else "")
        elif not _whole(by_ref[ref], p.clause_text):
            why = f"cuts {ref} short"
        elif p.kind == "CHANGE" and held.get(p.clause_id) != ref:
            why = f"wrong clause: the text is {ref}, but {p.clause_id} holds {held.get(p.clause_id) or 'another text'}"
        elif p.kind == "NEW" and ref in taken:
            why = f"{ref} is already in force under another clause"
        else:
            accept.append(p.item_no)
            taken.add(ref)
            why = f"accepted: {ref}" + (" (without its opening words 'NOT IN FORCE -')"
                                        if coverage(by_ref[ref], p.clause_text) != "complete" else "")
        reasons[str(p.item_no)] = why
    return accept, reasons
