"""Builds the GitHub issue.

Split of responsibilities (this is what keeps drafts honest):
* Facts (environment table, log excerpts, related incidents) are rendered
  deterministically from extracted evidence, so they are always real.
* The LLM only writes narrative: title, description, expected behaviour,
  hypotheses and the question for maintainers. If no LLM is configured or the
  reply cannot be parsed, a rule-based narrative is used instead.
"""
from __future__ import annotations

import json

from .llm import BaseLLM, LLMUnavailable, extract_json
from .log_parser import CATEGORIES

ENV_LABELS = [
    ("extension_version", "IBM Db2 Developer Extension"),
    ("vscode_version", "Visual Studio Code"),
    ("operating_system", "Operating system"),
    ("linux_distribution", "Linux distribution"),
    ("architecture", "Architecture"),
    ("container_runtime", "Container runtime"),
    ("container_image", "Container image"),
    ("container_name", "Container name"),
    ("db2_version", "Db2 version (as reported)"),
]

DEFAULT_STEPS = {
    "RUNTIME_INSTALL": [
        "Open the environment shown above with no container runtime installed.",
        "Start the Db2 Developer Extension workflow that checks for or installs a container runtime.",
        "Let the extension attempt automatic runtime installation.",
        "Review the Db2 Extension output channel and installation log.",
    ],
    "RESTART": [
        "Use the environment shown above with the container runtime available.",
        "Make sure the existing Db2 container is in the state shown in the log (e.g. stopped).",
        "Trigger the extension's restart workflow for that container.",
        "Review the restart result and the log entries that follow.",
    ],
    "CONNECTION": [
        "Create or open a Db2 connection profile in the extension.",
        "Run the connection test for that profile.",
        "Review the error reported in the Db2 Extension output channel.",
    ],
}
DEFAULT_STEPS["NETWORK"] = DEFAULT_STEPS["RUNTIME_INSTALL"]
DEFAULT_STEPS["AUTHENTICATION"] = DEFAULT_STEPS["CONNECTION"]

FALLBACK = {
    "RUNTIME_INSTALL": {
        "expected": [
            "The extension clearly reports that runtime installation could not complete because required endpoints were unreachable.",
            "It suggests recovery steps, such as checking network or proxy access, or installing a supported runtime manually.",
            "It keeps the specific failure reason instead of only a generic installation failure.",
        ],
        "hypotheses": [
            "Outbound access from WSL to package mirrors or download.docker.com may be blocked by a proxy, firewall or DNS configuration.",
            "Proxy variables set on Windows may not be visible inside the WSL distribution.",
        ],
        "impact": "Users on restricted, proxied or offline networks may be unable to finish initial setup. Could the maintainers confirm the supported recovery path, and whether runtime installation errors can include clearer network or proxy diagnostics?",
    },
    "RESTART": {
        "expected": [
            "The extension checks the container state before choosing a restart path and picks one that works for that state.",
            "Readiness checks distinguish a delayed readiness message from a real start-up failure.",
            "The user gets one clear final status for the container and the Db2 instance.",
        ],
        "hypotheses": [
            "The quick-restart path may assume a running container because it relies on an exec session.",
            "The readiness timeout may be shorter than start-up time on this machine.",
        ],
        "impact": "Users may see a restart failure even when a later step succeeds, which makes the final state unclear. Could the maintainers review the stopped-container branch and the handling of readiness timeouts?",
    },
    "CONNECTION": {
        "expected": [
            "The connection test explains whether the host was unreachable, the port was closed, or the database was not ready.",
            "It points to the next diagnostic step (container status, port mapping, host name).",
        ],
        "hypotheses": [
            "Nothing may have been listening on the configured host and port when the test ran.",
            "The profile host may not resolve to the machine running the Db2 container.",
        ],
        "impact": "A refused connection gives users little guidance. Could the maintainers confirm which checks the extension performs before reporting this error, and whether the message could suggest next steps?",
    },
}
FALLBACK["NETWORK"] = FALLBACK["RUNTIME_INSTALL"]
FALLBACK["AUTHENTICATION"] = FALLBACK["CONNECTION"]
GENERIC = {
    "expected": ["The operation completes, or the extension reports a specific, actionable reason why it could not."],
    "hypotheses": ["The cause is not established by the log alone."],
    "impact": "Could the maintainers confirm whether this behaviour is expected and what additional information would help?",
}

RELATED_DISTANCE = 0.35  # only mention earlier incidents that are genuinely close

BOUNDARY = (
    "The log confirms the events quoted under 'Relevant log excerpts'. It does not by itself establish the "
    "underlying cause; possible causes are listed separately as unconfirmed hypotheses."
)

SYSTEM_PROMPT = """You write GitHub bug reports for the IBM Db2 Developer Extension maintainers.
Rules you must follow:
1. Use ONLY facts present in the evidence. Never invent versions, error messages or steps.
2. Respect the evidence boundary: describe what the log shows; put any guess about cause ONLY in "hypotheses" and phrase it as a possibility ("may", "might").
3. Never write "the root cause is", "is caused by", "definitely" or similar certainty outside hypotheses.
4. If you quote a log message, copy it exactly from the evidence lines.
5. Title format: short action + component + observed failure, max 100 characters.
6. Reply with ONE JSON object and nothing else."""

USER_TEMPLATE = """Category: {category} ({category_desc})
Environment: {env}
User-provided context: {user_context}

Evidence lines from the sanitised log (kind | label | exact line):
{evidence}

Relevant troubleshooting knowledge (retrieved from Db2):
{kb}

{feedback}
Return JSON with exactly these keys:
{{"title": str, "description": str (2-4 sentences, factual), "evidence_boundary": str (1-2 sentences: what the log confirms and what it does NOT establish),
 "actual": [str, ...] (3-5 bullets of observed behaviour, in log order), "expected": [str, ...] (2-3 bullets),
 "hypotheses": [str, ...] (1-3 possibilities, hedged), "impact": str (impact plus one concrete question for maintainers)}}"""


def fallback_title(category: str, labels: list[str], env: dict) -> str:
    where = " in WSL" if env.get("operating_system") == "Windows with WSL" else ""
    if "Exec on stopped container" in labels or "Quick restart failed" in labels:
        return f"Quick restart fails when the existing Db2 container is stopped{where}"
    if category in {"RUNTIME_INSTALL", "NETWORK"} and "No container runtime" in labels:
        return f"Container runtime detection and automatic installation fail{where} when no runtime is available"
    if "SQL30081N communication error" in labels or "Connection refused" in labels:
        return "Connection test fails with SQL30081N communication error (connection refused)"
    if "Authentication failed" in labels:
        return "Connection fails with a Db2 authentication error"
    main = labels[0] if labels else "Unexpected error"
    return f"{CATEGORIES.get(category, 'Extension')}: {main.lower()}"


def fallback_narrative(category: str, evidence: list[dict], env: dict) -> dict:
    fb = FALLBACK.get(category, GENERIC)
    errors = [e for e in evidence if e["kind"] != "OBSERVATION"]
    labels = [e["label"] for e in errors]
    where = env.get("linux_distribution") or env.get("operating_system") or "the reported environment"
    runtime = env.get("container_runtime")
    desc = f"On {where}" + (f" with {runtime}" if runtime and not runtime.startswith("None") else "") + ", "
    if errors:
        desc += f"the Db2 Developer Extension log shows: {', '.join(dict.fromkeys(l.lower() for l in labels[:4]))}."
    else:
        desc += "the Db2 Developer Extension log shows the behaviour described below."
    if any(e["kind"] == "OBSERVATION" and e["label"] in {"Db2 accessible", "Startup success"} for e in evidence):
        desc += " Later log entries report that the Db2 instance became accessible."
    context_only = {"Generic error", "Runtime detected", "Waiting for readiness"}
    actual = [f"{e['label']} (log line {e['line_no']})." for e in evidence if e["label"] not in context_only][:8]
    if not actual:
        actual = [f"{e['label']} (log line {e['line_no']})." for e in evidence][:8]
    return {
        "title": fallback_title(category, labels, env),
        "description": desc,
        "evidence_boundary": BOUNDARY,
        "actual": actual,
        "expected": fb["expected"],
        "hypotheses": fb["hypotheses"],
        "impact": fb["impact"],
    }


def llm_narrative(
    llm: BaseLLM, category: str, evidence: list[dict], env: dict, kb: list[dict], user_context: str, feedback: list[str]
) -> dict:
    ev_text = "\n".join(f"{e['kind']} | {e['label']} | {e['log_line']}" for e in evidence) or "(none)"
    kb_text = "\n".join(f"- {k['title']}: {k['text'][:500]}" for k in kb) or "(none)"
    fb_text = ""
    if feedback:
        fb_text = "A reviewer rejected your previous draft. Fix these problems:\n- " + "\n- ".join(feedback) + "\n"
    reply = llm.chat(
        SYSTEM_PROMPT,
        USER_TEMPLATE.format(
            category=category, category_desc=CATEGORIES.get(category, ""), env=json.dumps(env),
            user_context=user_context or "(none)", evidence=ev_text, kb=kb_text, feedback=fb_text,
        ),
    )
    data = extract_json(reply)
    required = {"title", "description", "actual", "expected", "hypotheses", "impact"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"LLM JSON missing keys: {sorted(missing)}")
    for key in ("actual", "expected", "hypotheses"):
        if isinstance(data[key], str):
            data[key] = [data[key]]
        data[key] = [str(x).strip() for x in data[key] if str(x).strip()]
    data.setdefault("evidence_boundary", BOUNDARY)
    data["title"] = str(data["title"]).strip().strip('"')[:120]
    return data


def write_narrative(
    llm: BaseLLM, category: str, evidence: list[dict], env: dict, kb: list[dict], user_context: str, feedback: list[str]
) -> tuple[dict, str]:
    """Returns (narrative, generated_by)."""
    if llm.available:
        try:
            return llm_narrative(llm, category, evidence, env, kb, user_context, feedback), llm.name
        except (LLMUnavailable, ValueError, KeyError) as exc:
            fb = fallback_narrative(category, evidence, env)
            fb["_llm_error"] = str(exc)[:300]
            return fb, "rule-based (LLM fallback)"
    return fallback_narrative(category, evidence, env), "rule-based"


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "- (none)"


def render_issue(
    narrative: dict,
    env: dict,
    evidence: list[dict],
    steps: list[str],
    steps_inferred: bool,
    reproducibility: str,
    similar: list[dict],
    github_matches: list[dict],
    redaction_count: int,
    incident_id: int | None,
) -> tuple[str, str]:
    env_rows = "\n".join(f"| {label} | {env[key]} |" for key, label in ENV_LABELS if env.get(key))
    env_block = "| Field | Value |\n|---|---|\n" + (env_rows or "| Environment | Not found in log - please add |")
    step_lines = "\n".join(f"{i}. {s}" for i, s in enumerate(steps, 1))
    if steps_inferred:
        step_lines += "\n\n_Steps inferred from the log; please confirm or correct before posting._"
    excerpts = "\n".join(e["log_line"] for e in evidence if e["label"] != "Generic error") or "\n".join(
        e["log_line"] for e in evidence
    )
    related: list[str] = []
    for s in [x for x in similar if x["DISTANCE"] <= RELATED_DISTANCE][:3]:
        related.append(f"- Similar earlier incident #{s['INCIDENT_ID']} ({s['CATEGORY']}), cosine distance {s['DISTANCE']:.3f}")
    for g in github_matches[:3]:
        related.append(f"- Possibly related GitHub issue #{g['number']} ({g['state']}): [{g['title']}]({g['url']})")

    body = f"""## Description
{narrative['description']}

> **Evidence boundary:** {narrative.get('evidence_boundary') or BOUNDARY}

## Environment
{env_block}

## Steps to reproduce
{step_lines}

## Actual behavior
{_bullets(narrative['actual'])}

## Expected behavior
{_bullets(narrative['expected'])}

## Relevant log excerpts
```text
{excerpts}
```

## Hypotheses (unconfirmed)
{_bullets(narrative['hypotheses'])}

## Reproducibility
- Happens every time / intermittently: {reproducibility or 'Not yet confirmed'}

## Impact and question for maintainers
{narrative['impact']}
"""
    if related:
        body += "\n## Related\n" + "\n".join(related) + "\n"
    body += f"""
## Attachments
- Complete sanitised Db2 Extension log ({redaction_count} sensitive value(s) redacted automatically).

---
_Drafted with IssueSmith (Db2-backed agentic issue assistant){f', incident #{incident_id}' if incident_id else ''}. Reviewed by a human before posting._
"""
    return narrative["title"], body
