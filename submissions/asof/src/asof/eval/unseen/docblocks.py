"""Generated blocks in hand-written documents, and the generated part of docs/eval/unseen-intake.md.

A document is written by hand around blocks marked <!-- generated:NAME --> ... <!-- /generated:NAME -->; only the
blocks are rewritten, from the records, so every number in them comes from a record and the notes around them
survive a re-render.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ...config import PROJECT_ROOT

INTAKE_REPORT = PROJECT_ROOT / "docs" / "eval" / "unseen-intake.md"


def _block(name: str, body: str) -> str:
    return f"<!-- generated:{name} -->\n{body.rstrip()}\n<!-- /generated:{name} -->"


def replace_blocks(path: Path, blocks: dict[str, str], skeleton: str) -> None:
    """Rewrite each named block of the document (creating it from `skeleton` if missing)."""
    text = path.read_text(encoding="utf-8") if path.exists() else skeleton
    for name, body in blocks.items():
        pattern = re.compile(rf"<!-- generated:{name} -->.*?<!-- /generated:{name} -->", re.S)
        if not pattern.search(text):
            text = text.rstrip() + "\n\n" + _block(name, "") + "\n"
        replacement = _block(name, body)
        text = pattern.sub(lambda _m: replacement, text)  # noqa: B023 - used at once, inside this iteration
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


INTAKE_SKELETON = """# Onboarding SPR through Policy intake

<!-- generated:uploads -->
<!-- /generated:uploads -->
"""


def intake_block(uploads: list[Any]) -> str:
    """One row per upload, then the editor's reason for every item."""
    lines = ["| Upload | Version | Sections missing before | Proposed | Whole sections | Cut short | Not in the document "
             "| Blocked by checks | Wrong or second clause | Accepted | Dates wrong | Values stated / captured |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for u in uploads:
        a = u.accuracy["summary"]
        notes = u.decision["notes"].values() if u.decision else []
        wrong_clause = sum(str(n).startswith("wrong clause") or "already in force under another clause" in str(n)
                           for n in notes)
        missing = ", ".join(u.decision.get("missing_before", [])) if u.decision else ""
        lines.append(f"| {u.upload_no} | v{u.version} | {missing or 'none'} | {a['proposed']} | {a['complete']} | "
                     f"{a['partial']} | {a['invented']} | {a['blocked']} | {wrong_clause} | {len(u.applied)} | "
                     f"{a['wrong_start'] + a['wrong_end']} | {a['values_in_text']} / {a['values_captured']} |")
    lines += ["", "The editor's reason for every item, by upload:", ""]
    for u in uploads:
        if not u.decision:
            continue
        lines.append(f"- Upload {u.upload_no} (v{u.version}), draft {u.draft_id}:")
        for no, why in u.decision["notes"].items():
            lines.append(f"  - #{no} {u.decision['items'].get(no, '')}: {why}")
        for c in u.decision.get("changes", []):
            lines.append(f"  - correction {c['clause_id']} from {c['effective_from']}: {c['why']}")
    return "\n".join(lines)


def write_intake(uploads: list[Any]) -> None:
    replace_blocks(INTAKE_REPORT, {"uploads": intake_block(uploads)}, INTAKE_SKELETON)
