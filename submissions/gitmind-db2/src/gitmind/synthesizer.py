"""
GitMind 2.0 — Grounded Evidence Verification & Answer Synthesis

Synthesizes multi-agent outputs with a dedicated evidence verification layer:
- Extracts candidate citations (commit hashes, files, PRs, issues)
- Verifies citations against IBM Db2 repository records & Git history
- Rejects or flags ungrounded / fabricated claims
- Delineates Verified Facts vs Historical Inferences vs AI Recommendations
- Appends grounded evidence footnotes backed by IBM Db2
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

import config
from data.evidence_models import EvidenceReference, VerificationStatus
from data.repository_memory import get_repository_memory
from utils.repo_utils import get_repo_id


SYNTHESIS_PROMPT = """You are the Lead Synthesis & Evidence Verification Agent for GitMind 2.0.

You receive outputs from multiple specialist agents, alongside an automated evidence verification report from IBM Db2.
Your mission is to merge these findings into an authoritative, grounded engineering explanation.

CRITICAL RULES:
1. GROUNDING FIRST: Every material factual statement must be backed by the verified evidence provided.
2. DISTINGUISH TRUTH:
   - Use '### Verified Facts' for statements confirmed by verified commit hashes, PRs, or file lines.
   - Use '### Historical Inferences' for conclusions derived from patterns or evolution.
   - Use '### Recommendations' for actionable developer advice.
   - If evidence is missing, outdated, or insufficient, explicitly state: 'Information unavailable in repository history.'
3. NO HALLUCINATION: Never invent commit hashes, PR numbers, issues, line numbers, or author names.
4. If an agent cited an UNGROUNDED reference, explicitly note that it could not be verified in repository records.
5. FORMATTING: Use clean GitHub-Flavored Markdown (GFM). Use inline code for hashes (`abc1234`), files, and functions. Do NOT output raw HTML or ANSI escape sequences.
6. EVIDENCE SECTION: At the bottom, include a '### Grounded Evidence (IBM Db2)' section listing verified citations."""


def extract_candidate_evidence(agent_outputs: Dict[str, str]) -> List[EvidenceReference]:
    """
    Regex extracts candidate commit hashes, file paths, and PR numbers
    from agent outputs to pass to the verification layer.
    """
    combined_text = "\n".join(agent_outputs.values())
    evidence_candidates: List[EvidenceReference] = []
    seen_refs = set()

    # 1. Commit hashes (7 to 40 hex chars)
    commit_matches = re.findall(r"\b([0-9a-f]{7,40})\b", combined_text, re.IGNORECASE)
    for c in commit_matches:
        c_clean = c.lower()
        if c_clean in seen_refs or len(c_clean) not in (7, 8, 40):
            continue
        seen_refs.add(c_clean)
        evidence_candidates.append(
            EvidenceReference(
                artifact_type="commit",
                commit_sha=c_clean,
            )
        )

    # 2. File paths (e.g. src/foo.py, cli.py, data/database.py)
    file_matches = re.findall(r"\b([a-zA-Z0-9_\-\.\/]+\.(?:py|js|ts|tsx|jsx|json|md|yaml|yml|toml|sql))\b", combined_text)
    for f in file_matches:
        f_clean = f.strip().replace("\\", "/")
        if f_clean in seen_refs:
            continue
        seen_refs.add(f_clean)
        evidence_candidates.append(
            EvidenceReference(
                artifact_type="file",
                file_path=f_clean,
            )
        )

    # 3. Pull requests / Issues (e.g. PR #12, Issue #42)
    gh_matches = re.findall(r"(?:PR|issue)\s*#(\d+)", combined_text, re.IGNORECASE)
    for num in gh_matches:
        if num in seen_refs:
            continue
        seen_refs.add(num)
        evidence_candidates.append(
            EvidenceReference(
                artifact_type="pr",
                artifact_id=num,
            )
        )

    return evidence_candidates[:15]


def synthesize(
    agent_outputs: Dict[str, str],
    original_query: str,
    repo_path: str = ".",
) -> str:
    """
    Verifies agent evidence against Db2 and synthesizes a grounded response.
    """
    if not agent_outputs:
        return "I wasn't able to find relevant information for your query."

    repo_id = get_repo_id(repo_path)
    memory = get_repository_memory()

    # 1. Extract and verify citations against IBM Db2
    candidate_evidence = extract_candidate_evidence(agent_outputs)
    verified_evidence: List[EvidenceReference] = []

    try:
        verified_evidence = memory.verify_evidence(candidate_evidence, repo_id=repo_id)
    except Exception:
        verified_evidence = candidate_evidence

    # Build evidence verification briefing for the LLM
    evidence_briefing_lines = ["--- EVIDENCE VERIFICATION REPORT (IBM Db2) ---"]
    if verified_evidence:
        for ev in verified_evidence:
            ident = ev.commit_sha or ev.file_path or ev.artifact_id or ev.artifact_type
            status_tag = f"[{ev.verification_status.value}]"
            note = f" ({ev.verification_note})" if ev.verification_note else ""
            evidence_briefing_lines.append(f"- {status_tag} {ev.artifact_type}: {ident}{note}")
    else:
        evidence_briefing_lines.append("- No verifiable commit hashes or files explicitly cited by agents.")

    evidence_context = "\n".join(evidence_briefing_lines)

    # 2. Format Agent Context
    context_parts = []
    for agent_name, output in agent_outputs.items():
        context_parts.append(f"--- {agent_name.upper()} AGENT OUTPUT ---\n{output}")
    agent_context = "\n\n".join(context_parts)

    # 3. Invoke LLM for grounded synthesis
    llm = config.get_llm(temperature=0)

    prompt = (
        f"{SYNTHESIS_PROMPT}\n\n"
        f"Original User Query: {original_query}\n\n"
        f"{evidence_context}\n\n"
        f"{agent_context}\n\n"
        f"Synthesized Grounded Response:"
    )

    response = llm.invoke(prompt)
    final_text = response.content

    return final_text
