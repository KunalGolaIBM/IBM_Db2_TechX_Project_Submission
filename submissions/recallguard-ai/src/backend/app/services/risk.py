"""Explainable, configurable recall risk scoring.

Score 0-100 = sum of six weighted factor contributions. Each factor reports its
raw input, normalised value (0-1), weight, contribution and a plain-language
reason. Missing records INCREASE the score (conservative): an item is never
treated as lower-risk because its links could not be established.

DISCLAIMER: this is a prioritisation index for recall operations, not a
scientifically validated probability of consumer illness.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from functools import lru_cache
from typing import Any

from app.core.config import get_settings

DISCLAIMER = ("Risk score is an operational prioritisation index derived from traceability data. "
              "It is not a scientifically validated probability of illness and does not replace "
              "regulatory or food-safety expert judgement.")


@lru_cache
def load_config(path: str | None = None) -> dict[str, Any]:
    with open(path or get_settings().risk_config_path, encoding="utf-8") as f:
        cfg = json.load(f)
    total = sum(cfg["weights"].values())
    if total != 100:
        raise ValueError(f"risk weights must sum to 100, got {total}")
    return cfg


def classify(score: int, cfg: dict[str, Any]) -> str:
    for threshold, label in cfg["classes"]:
        if score >= threshold:
            return label
    return "LOW"


def compute_risk(
    *,
    severity: str,
    category: str,
    impact_summary: dict[str, Any],
    data_gaps: list[dict[str, Any]],
    discovered_at: str | dt.datetime,
    evidence_confirmed: bool,
    now: dt.datetime | None = None,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    w = cfg["weights"]
    now = now or dt.datetime.now()
    if isinstance(discovered_at, str):
        discovered_at = dt.datetime.fromisoformat(discovered_at.replace(" ", "T")[:19])

    factors: list[dict[str, Any]] = []

    def add(name: str, raw: Any, norm: float, reason: str) -> None:
        norm = max(0.0, min(1.0, norm))
        factors.append({"factor": name, "weight": w[name], "raw_value": raw, "normalized": round(norm, 3),
                        "contribution": round(w[name] * norm, 2), "reason": reason})

    sev = cfg["severity_map"].get(severity.upper(), 1.0)
    mod = cfg["category_modifier"].get(category.upper(), 1.0)
    add("severity", f"{severity}/{category}", sev * mod,
        f"Reported severity {severity} ({sev}) x {category.lower()} hazard modifier {mod}.")

    units = int(impact_summary.get("units_produced", 0))
    sat = cfg["quantity_saturation_units"]
    add("quantity", units, math.log10(1 + units) / math.log10(1 + sat),
        f"{units:,} finished units across {impact_summary.get('finished_batches', 0)} batches (log-scaled, saturates at {sat:,}).")

    n_loc = sum(int(impact_summary.get(k, 0)) for k in ("warehouses", "distributors", "retailers"))
    lsat = cfg["locations_saturation"]
    add("locations", n_loc, n_loc / lsat,
        f"{n_loc} downstream locations ({impact_summary.get('retailers', 0)} retailers) in {impact_summary.get('cities', 0)} cities.")

    at_retail = int(impact_summary.get("units_at_retail", 0))
    share = (at_retail / units) if units else 1.0
    add("distribution", f"{round(share * 100, 1)}% at retail", share,
        f"{at_retail:,} of {units:,} units already delivered to retail/foodservice; "
        f"{impact_summary.get('units_in_transit', 0):,} in transit.")

    gap_w = cfg["gap_weight"]
    gap_load = sum(gap_w.get(g.get("severity", "MEDIUM"), 0.15) for g in data_gaps)
    if not evidence_confirmed:
        gap_load += 0.25
    add("uncertainty", f"{len(data_gaps)} gaps", gap_load,
        f"{len(data_gaps)} traceability gaps"
        + ("" if evidence_confirmed else " and no confirmed laboratory result")
        + " — missing records raise risk (conservative handling).")

    hours = max(0.0, (now - discovered_at).total_seconds() / 3600)
    tsat = cfg["time_saturation_hours"]
    add("time", f"{round(hours, 1)} h", hours / tsat,
        f"{round(hours, 1)} hours since discovery (exposure grows with time; saturates at {tsat} h).")

    score = int(round(sum(f["contribution"] for f in factors)))
    score = max(0, min(100, score))
    pen = cfg["completeness_penalty"]
    completeness = max(0, 100 - sum(pen.get(g.get("severity", "MEDIUM"), 4) for g in data_gaps))
    if completeness >= 85 and evidence_confirmed:
        confidence = "HIGH"
    elif completeness >= 60:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"
    risk_class = classify(score, cfg)
    top = sorted(factors, key=lambda f: f["contribution"], reverse=True)[:3]
    reasoning = (f"Score {score}/100 ({risk_class}). Largest drivers: "
                 + "; ".join(f"{f['factor']} +{f['contribution']}" for f in top)
                 + f". Data completeness {completeness}% -> confidence {confidence}.")
    return {
        "score": score,
        "classification": risk_class,
        "factors": factors,
        "reasoning": reasoning,
        "data_completeness_pct": completeness,
        "confidence": confidence,
        "evidence_confirmed": evidence_confirmed,
        "disclaimer": DISCLAIMER,
        "model_version": "rg-risk-1.0",
    }


def recall_class_for(score: int, category: str, severity: str) -> str:
    if severity.upper() == "CRITICAL" or (category.upper() in ("MICROBIAL", "ALLERGEN") and score >= 50):
        return "CLASS_I"
    if score >= 25:
        return "CLASS_II"
    return "CLASS_III"
