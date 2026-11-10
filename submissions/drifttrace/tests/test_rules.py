"""Pure-logic tests (no Db2, no network)."""
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from intake import EXAMPLES, parse_iso_utc, validate  # noqa: E402
from models import (CROSSES, INSUFFICIENT_DATA, OUTSIDE_SCOPE, REVIEW_SCOPE, WITHIN,  # noqa: E402
                    EvidenceQuote, InspectionFact, NoticeExtraction, Scope, Shipment)
from trace import aggregate, build_findings, classify, fingerprint  # noqa: E402

D = Decimal
SCOPE = Scope("CAL-017", "external_diameter", datetime(2026, 11, 2, 8), datetime(2026, 11, 9, 10))
KNOWN = ["CAL-017", "CAL-018"]


def fact(iid="I-1", inst="CAL-017", lot="L-1", at=datetime(2026, 11, 3, 12), value="25.040", qty=60, unit="mm"):
    return InspectionFact(iid, inst, "caliper", lot, "spacer", qty, at, "external_diameter", unit,
                          D(value) if value else None, D("24.950"), D("25.050"), "ACCEPTED")


def ship(sid, lot, q):
    return Shipment(sid, lot, "Fictional Co", q, datetime(2026, 11, 6))


def test_exact_instrument_match_never_fuzzy():
    assert classify(fact(inst="CAL-018"), SCOPE)[0] == OUTSIDE_SCOPE
    assert classify(fact(inst="CAL-0170"), SCOPE)[0] == OUTSIDE_SCOPE
    assert classify(fact(inst="CAL-017"), SCOPE)[0] == REVIEW_SCOPE


def test_inclusive_window_edges():
    assert classify(fact(at=SCOPE.review_start), SCOPE)[0] == REVIEW_SCOPE
    assert classify(fact(at=SCOPE.review_end), SCOPE)[0] == REVIEW_SCOPE
    assert classify(fact(at=datetime(2026, 11, 2, 7, 59, 59)), SCOPE)[0] == OUTSIDE_SCOPE
    assert classify(fact(at=datetime(2026, 11, 9, 10, 0, 1)), SCOPE)[0] == OUTSIDE_SCOPE


def test_timezone_aware_timestamps_compare_in_utc():
    aware = datetime(2026, 11, 2, 3, 30, tzinfo=timezone.utc).astimezone()  # 03:30Z, before start
    assert classify(fact(at=aware), SCOPE)[0] == OUTSIDE_SCOPE


def test_missing_date_and_fields_go_to_insufficient_bucket():
    cls, reason = classify(fact(at=None), SCOPE)
    assert cls == INSUFFICIENT_DATA and "timestamp is missing" in reason
    assert classify(fact(value=None), SCOPE)[0] == INSUFFICIENT_DATA
    assert classify(fact(unit=None), SCOPE)[0] == INSUFFICIENT_DATA
    assert classify(fact(unit="in"), SCOPE)[0] == INSUFFICIENT_DATA


def test_bound_decimal_equality_is_within_and_crossing_detected():
    facts = [fact("I-a", value="25.010"), fact("I-b", value="25.011"), fact("I-c", value="24.990")]
    f = {x.fact.inspection_id: x for x in build_findings(facts, [], SCOPE, D("0.040"))}
    assert f["I-a"].hypothetical == WITHIN          # 25.050 exactly == upper limit
    assert f["I-b"].hypothetical == CROSSES
    assert f["I-c"].hypothetical == WITHIN          # 24.950 exactly == lower limit


def test_bound_never_changes_review_scope():
    facts = [fact("I-101", value="25.040"), fact("I-102", value="25.000"), fact("I-103", value="24.960"),
             fact("I-104", at=datetime(2026, 11, 1, 12))]
    base = [(x.fact.inspection_id, x.classification) for x in build_findings(facts, [], SCOPE, None)]
    for b in ("0", "0.040", "0.060", "5"):
        assert [(x.fact.inspection_id, x.classification) for x in build_findings(facts, [], SCOPE, D(b))] == base
    r = {x.fact.inspection_id: x.hypothetical for x in build_findings(facts, [], SCOPE, D("0.040"))}
    assert r == {"I-101": CROSSES, "I-102": WITHIN, "I-103": CROSSES, "I-104": None}
    r = {x.fact.inspection_id: x.hypothetical for x in build_findings(facts, [], SCOPE, D("0.060"))}
    assert [r[k] for k in ("I-101", "I-102", "I-103")] == [CROSSES] * 3


def test_aggregation_counts_distinct_lots_and_shipments():
    facts = [fact("I-1", lot="L-1", qty=60), fact("I-2", lot="L-1", qty=60), fact("I-3", lot="L-2", qty=20)]
    ships = [ship("S-1", "L-1", 25), ship("S-2", "L-1", 15)]
    t = aggregate(build_findings(facts, ships, SCOPE))
    assert t.review_lots == ["L-1", "L-2"]
    assert t.review_shipments == ["S-1", "S-2"]
    assert t.review_shipped_units == 40
    assert t.review_produced_units == 80
    assert t.review_unshipped_units == 20 + 20


def test_insufficient_shipments_reported_separately():
    facts = [fact("I-1", lot="L-1"), fact("I-2", lot="L-9", at=None, qty=10)]
    t = aggregate(build_findings(facts, [ship("S-1", "L-1", 40), ship("S-9", "L-9", 10)], SCOPE))
    assert t.review_shipped_units == 40 and t.insufficient_shipped_units == 10
    assert t.insufficient_lots == ["L-9"]


def test_fingerprint_changes_with_data():
    a = fingerprint([fact()], [ship("S-1", "L-1", 40)])
    assert a == fingerprint([fact()], [ship("S-1", "L-1", 40)])
    assert a != fingerprint([fact()], [ship("S-1", "L-1", 41)])


def _ex(**kw):
    base = dict(instrument_id="CAL-017", function_code="external_diameter", detected_at="2026-11-09T10:00:00Z",
                observed_direction="low", evidence=[
                    EvidenceQuote(field="instrument_id", quote="Instrument CAL-017 failed its as-found"),
                    EvidenceQuote(field="function_code", quote="external diameter check"),
                    EvidenceQuote(field="detected_at", quote="9 November 2026 at 10:00 UTC")])
    base.update(kw)
    return NoticeExtraction(**base)


NOTICE = list(EXAMPLES.values())[0]


def test_quote_validation_accepts_verbatim_and_rejects_invented():
    v = validate(_ex(), NOTICE, KNOWN)
    assert v.ok_to_trace and v.resolved_instrument == "CAL-017"
    assert all(q.exact for q in v.quotes)
    v = validate(_ex(evidence=[EvidenceQuote(field="instrument_id", quote="CAL-017 passed")]), NOTICE, KNOWN)
    assert not v.ok_to_trace


def test_unknown_or_near_miss_instrument_blocks():
    assert not validate(_ex(instrument_id="CAL-0l7"), NOTICE, KNOWN).ok_to_trace
    assert not validate(_ex(instrument_id="CAL-018"), NOTICE, KNOWN).ok_to_trace  # not written in notice
    assert not validate(_ex(instrument_id=None), NOTICE, KNOWN).ok_to_trace


def test_unsupported_function_and_limitations_need_review():
    assert not validate(_ex(function_code="unsupported"), NOTICE, KNOWN).ok_to_trace
    v = validate(_ex(scope_limitations=["only 100-150 mm test points"]), NOTICE, KNOWN)
    assert any("scope limitations" in m for m in v.review)


def test_injection_text_is_flagged_and_does_not_resolve():
    adv = EXAMPLES["Adversarial notice"]
    v = validate(_ex(instrument_id="CAL-0l7", detected_at=None, evidence=[]), adv, KNOWN)
    assert not v.ok_to_trace
    assert any("instructions aimed at the system" in m for m in v.review)


def test_parse_iso_requires_timezone():
    assert parse_iso_utc("2026-11-09T10:00:00Z") == datetime(2026, 11, 9, 10)
    assert parse_iso_utc("2026-11-09T10:00:00") is None
    assert parse_iso_utc("9 Nov") is None


# ---------- review dispositions ----------
import pytest  # noqa: E402

from trace import InputError, validate_disposition  # noqa: E402

LO, HI = D("24.950"), D("25.050")


def test_remeasured_verdict_must_match_limits():
    validate_disposition("REMEASURED_CONFORMS", D("25.050"), LO, HI, "ok", "QM")        # inclusive edge
    validate_disposition("REMEASURED_NONCONFORMING", D("25.051"), LO, HI, "bad", "QM")
    with pytest.raises(InputError):
        validate_disposition("REMEASURED_CONFORMS", D("25.051"), LO, HI, "x", "QM")
    with pytest.raises(InputError):
        validate_disposition("REMEASURED_NONCONFORMING", D("25.000"), LO, HI, "x", "QM")


def test_value_required_only_for_remeasure_and_inputs_bounded():
    with pytest.raises(InputError):
        validate_disposition("REMEASURED_CONFORMS", None, LO, HI, "x", "QM")
    with pytest.raises(InputError):
        validate_disposition("NOT_AVAILABLE_FOR_REMEASURE", D("25"), LO, HI, "x", "QM")
    with pytest.raises(InputError):
        validate_disposition("REVIEWED_NO_FURTHER_ACTION", None, LO, HI, " ", "QM")
    with pytest.raises(InputError):
        validate_disposition("REVIEWED_NO_FURTHER_ACTION", None, LO, HI, "x" * 501, "QM")
    with pytest.raises(InputError):
        validate_disposition("MARK_SAFE", None, LO, HI, "x", "QM")
    with pytest.raises(InputError):  # missing limits cannot support a measured verdict
        validate_disposition("REMEASURED_CONFORMS", D("25"), None, None, "x", "QM")
