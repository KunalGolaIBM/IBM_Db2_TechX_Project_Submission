"""Deterministic, rule-based investigator. It is NOT an LLM and is never presented as one.

It does not read the investigation's free-text question; it analyses Db2 hotspots using the same
audited tools as the LLM path, then applies fixed, documented rules:

  score    = complaint_count * average_severity
  priority = 1 if score >= 25, 2 if >= 15, 3 if >= 9, 4 if >= 5, else 5   (1 = most urgent)
  confidence = count / (count + 4)    # a data-volume heuristic, not a model probability
"""

from __future__ import annotations

from typing import Any

from civiclens.agent.runner import LoopResult, collect_complaint_ids
from civiclens.domain.errors import AgentError
from civiclens.domain.investigation_models import RecommendationDraft, RunRequest

RULE_VERSION = "hotspot-rules-v1"
LABEL = "[RULE-BASED, NO LLM]"


def priority_for(count: int, avg_severity: float) -> int:
    score = count * avg_severity
    for threshold, priority in ((25, 1), (15, 2), (9, 3), (5, 4)):
        if score >= threshold:
            return priority
    return 5


def confidence_for(count: int) -> float:
    return round(count / (count + 4), 3)


def _call(tools: dict[str, Any], name: str, args: dict[str, Any]) -> Any:
    body = tools[name].invoke(args)
    if not body.get("ok"):
        raise AgentError(f"Tool {name} failed.", code="TOOL_FAILED", tool=name)
    return body["data"]


def run_fallback(tools: dict[str, Any], request: RunRequest) -> LoopResult:
    args: dict[str, Any] = {"days": request.days, "min_count": 3, "limit": request.max_hotspots}
    if request.category is not None:
        args["category"] = request.category.value
    hotspots = _call(tools, "hotspot_summary", args)
    calls = 1
    seen: set[int] = set()
    drafts: list[RecommendationDraft] = []
    for spot in hotspots[: request.max_hotspots]:
        complaints = _call(
            tools,
            "search_complaints",
            {
                "category": spot["category"],
                "geo_cell": spot["geo_cell"],
                "days": request.days,
                "limit": 25,
            },
        )
        calls += 1
        ids = sorted(collect_complaint_ids(complaints))
        if not ids:
            continue
        seen |= set(ids)
        count, sev = int(spot["complaint_count"]), float(spot["avg_severity"])
        category = str(spot["category"]).replace("_", " ").lower()
        drafts.append(
            RecommendationDraft(
                summary=f"Inspect {category} cluster in cell {spot['geo_cell']} ({count} complaints)",
                rationale=(
                    f"{LABEL} Rule set {RULE_VERSION}. Db2 aggregation found {count} non-duplicate "
                    f"{category} complaints in geo-cell {spot['geo_cell']} between "
                    f"{spot['first_reported_at']} and {spot['last_reported_at']} "
                    f"(average severity {sev:.2f}/5; score {count * sev:.1f}). "
                    f"Evidence: the {len(ids)} most recent matching complaints "
                    f"({', '.join(map(str, ids[:10]))}{'...' if len(ids) > 10 else ''}). "
                    "Priority and confidence come from fixed thresholds, not a learned model."
                ),
                priority=priority_for(count, sev),
                confidence=confidence_for(count),
                evidence_ids=ids,
            )
        )
    return LoopResult(drafts=drafts, seen_ids=seen, steps=calls, tool_calls=calls)
