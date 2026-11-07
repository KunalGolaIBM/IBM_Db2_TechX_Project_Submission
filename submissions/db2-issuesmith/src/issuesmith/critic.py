"""Critic agent. Reviews each draft against the community issue guide.

Deterministic checks are used deliberately: a reviewer that is itself an LLM
can hallucinate approval. Blocking failures send the draft back to the writer.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .sanitizer import find_secrets

REQUIRED_SECTIONS = [
    "## Description", "## Environment", "## Steps to reproduce", "## Actual behavior",
    "## Expected behavior", "## Relevant log excerpts", "## Reproducibility", "Evidence boundary",
]
OVERCLAIM = re.compile(
    r"\b(root cause is|is caused by|was caused by|this proves|proves that|definitely|certainly|"
    r"the bug is in|clearly (?:a|the) bug|undoubtedly)\b",
    re.IGNORECASE,
)
QUOTE = re.compile(r"[\"“`]([^\"”`\n]{12,})[\"”`]")
GENERIC_TITLES = {"error", "bug", "issue", "help", "not working", "problem"}
PLACEHOLDER = re.compile(r"\[(?:insert|todo|fill)[^\]]*\]|\bTODO\b|lorem ipsum", re.IGNORECASE)


@dataclass
class Check:
    name: str
    passed: bool
    blocking: bool
    message: str


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def review(title: str, body: str, narrative: dict, sanitized_log: str, env: dict) -> dict:
    checks: list[Check] = []
    log_norm = _norm(sanitized_log)

    missing = [s for s in REQUIRED_SECTIONS if s not in body]
    checks.append(Check("template_sections", not missing, True,
                        "All template sections present." if not missing else f"Missing sections: {', '.join(missing)}"))

    t = title.strip()
    title_ok = 20 <= len(t) <= 120 and t.lower() not in GENERIC_TITLES
    checks.append(Check("title_format", title_ok, True,
                        "Title names the action and component." if title_ok
                        else "Title must be 20-120 characters and name the failing action and component."))

    secrets = find_secrets(title + "\n" + body)
    checks.append(Check("no_secrets", not secrets, True,
                        "No sensitive values detected." if not secrets
                        else f"Possible sensitive data still present: {', '.join(secrets)}"))

    narrative_text = " ".join(
        [narrative.get("title", ""), narrative.get("description", ""), narrative.get("impact", ""),
         narrative.get("evidence_boundary", "")]
        + list(narrative.get("actual", [])) + list(narrative.get("expected", []))
    )
    claims = sorted({m.group(0) for m in OVERCLAIM.finditer(narrative_text)})
    checks.append(Check("evidence_boundary", not claims, True,
                        "No unconfirmed root-cause claims outside hypotheses." if not claims
                        else f"Certainty language outside hypotheses: {', '.join(claims)}. Move it to hypotheses and hedge it."))

    ungrounded = [q for q in (m.group(1) for m in QUOTE.finditer(narrative_text)) if _norm(q) not in log_norm]
    checks.append(Check("quotes_grounded", not ungrounded, True,
                        "Every quoted message exists in the log." if not ungrounded
                        else "Quoted text not found in the log: " + "; ".join(f'"{q[:60]}"' for q in ungrounded[:3])))

    block = re.search(r"## Relevant log excerpts\s*```text\n(.*?)```", body, re.S)
    excerpt_lines = [ln for ln in (block.group(1).splitlines() if block else []) if ln.strip()]
    bad = [ln for ln in excerpt_lines if _norm(ln) not in log_norm]
    checks.append(Check("excerpts_verbatim", bool(excerpt_lines) and not bad, True,
                        f"{len(excerpt_lines)} excerpt line(s) verified against the log." if excerpt_lines and not bad
                        else "Log excerpts are missing or do not match the log."))

    env_fields = len([v for v in env.values() if v])
    checks.append(Check("environment_complete", env_fields >= 3, False,
                        f"{env_fields} environment field(s) detected." if env_fields >= 3
                        else "Few environment details found; ask the user for extension, OS and runtime versions."))

    steps = re.findall(r"^\d+\. ", body, re.M)
    checks.append(Check("numbered_steps", len(steps) >= 2, False,
                        f"{len(steps)} numbered step(s)." if len(steps) >= 2 else "Add at least two numbered reproduction steps."))

    ph = PLACEHOLDER.findall(body)
    checks.append(Check("no_placeholders", not ph, False,
                        "No unfilled placeholders." if not ph else f"Unfilled placeholders: {', '.join(ph[:3])}"))

    blocking_failed = [c for c in checks if c.blocking and not c.passed]
    warnings = [c for c in checks if not c.blocking and not c.passed]
    score = max(0.0, 100.0 - 25.0 * len(blocking_failed) - 5.0 * len(warnings))
    return {
        "passed": not blocking_failed,
        "score": score,
        "checks": [asdict(c) for c in checks],
        "feedback": [c.message for c in blocking_failed],
    }
