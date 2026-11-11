import datetime as dt

from app.services.risk import classify, compute_risk, load_config

SUMMARY = {"units_produced": 42000, "finished_batches": 7, "warehouses": 6, "distributors": 4, "retailers": 19, "cities": 11,
           "units_at_retail": 28200, "units_in_transit": 1500}
NOW = dt.datetime(2026, 11, 11, 12, 0, 0)


def _r(**kw):
    args = dict(severity="CRITICAL", category="MICROBIAL", impact_summary=SUMMARY, data_gaps=[], discovered_at=NOW, evidence_confirmed=True, now=NOW)
    args.update(kw)
    return compute_risk(**args)


def test_weights_sum_to_100():
    assert sum(load_config()["weights"].values()) == 100


def test_score_bounds_and_explainability():
    r = _r()
    assert 0 <= r["score"] <= 100
    assert {f["factor"] for f in r["factors"]} == {"severity", "quantity", "locations", "distribution", "uncertainty", "time"}
    assert abs(sum(f["contribution"] for f in r["factors"]) - r["score"]) <= 1
    assert all(f["reason"] for f in r["factors"])
    assert "not a scientifically validated probability" in r["disclaimer"]


def test_severity_is_monotonic():
    scores = [_r(severity=s)["score"] for s in ("LOW", "MEDIUM", "HIGH", "CRITICAL")]
    assert scores == sorted(scores) and scores[0] < scores[-1]


def test_missing_records_increase_risk_and_reduce_confidence():
    gaps = [{"severity": "HIGH"}, {"severity": "HIGH"}, {"severity": "MEDIUM"}]
    clean, gappy = _r(), _r(data_gaps=gaps)
    assert gappy["score"] > clean["score"]
    assert gappy["data_completeness_pct"] < clean["data_completeness_pct"]


def test_unconfirmed_evidence_is_conservative():
    assert _r(evidence_confirmed=False)["score"] >= _r()["score"]
    assert _r(evidence_confirmed=False)["confidence"] != "HIGH"


def test_time_since_discovery_raises_score():
    assert _r(discovered_at=NOW - dt.timedelta(hours=48))["score"] > _r()["score"]


def test_classification_thresholds():
    cfg = load_config()
    assert classify(90, cfg) == "CRITICAL" and classify(60, cfg) == "HIGH" and classify(30, cfg) == "MODERATE" and classify(5, cfg) == "LOW"
