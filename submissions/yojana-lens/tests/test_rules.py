from src.models import RuleRow
from src.rules import classify, gap_hint, readiness, split_parts


def rule(**overrides):
    data = dict(
        scheme_id="s1",
        rule_id=1,
        criterion_code="income_annual",
        rule_op="lte",
        mandatory=1,
        observed_value="180000",
        verdict="PASS",
        clause_ref="Para 2",
        value_num=250000,
    )
    data.update(overrides)
    return RuleRow(**data)


def test_all_pass_is_eligible():
    assert classify([rule(), rule(rule_id=2, criterion_code="age", rule_op="gte")]) == "ELIGIBLE"


def test_single_numeric_failure_is_a_near_miss():
    rows = [rule(), rule(rule_id=2, criterion_code="age", rule_op="gte", verdict="FAIL")]
    assert classify(rows) == "NEAR_MISS"


def test_single_categorical_failure_is_not_a_near_miss():
    rows = [rule(), rule(rule_id=2, criterion_code="category", rule_op="eq",
                         value_num=None, value_text="sc", verdict="FAIL")]
    assert classify(rows) == "NOT_ELIGIBLE"


def test_two_blocking_failures_are_not_a_near_miss():
    rows = [rule(verdict="FAIL"), rule(rule_id=2, rule_op="gte", verdict="FAIL")]
    assert classify(rows) == "NOT_ELIGIBLE"


def test_missing_mandatory_fact_asks_for_clarification():
    rows = [rule(), rule(rule_id=2, criterion_code="bpl_status", rule_op="eq",
                         value_num=None, value_text="yes", verdict="UNKNOWN")]
    assert classify(rows) == "CLARIFY"


def test_advisory_failure_does_not_block_eligibility():
    rows = [rule(), rule(rule_id=2, criterion_code="bpl_status", rule_op="eq",
                         mandatory=0, value_num=None, value_text="yes", verdict="FAIL")]
    assert classify(rows) == "ELIGIBLE"


def test_blocking_failure_outranks_missing_fact():
    rows = [rule(verdict="FAIL"), rule(rule_id=2, criterion_code="bpl_status",
                                       rule_op="eq", verdict="UNKNOWN")]
    assert classify(rows) == "NEAR_MISS"


def test_no_rows_is_clarify():
    assert classify([]) == "CLARIFY"


def test_readiness_counts_passes():
    rows = [rule(), rule(rule_id=2, verdict="FAIL"), rule(rule_id=3), rule(rule_id=4)]
    assert readiness(rows) == 75


def test_split_parts_separates_advisory_and_missing():
    rows = [
        rule(verdict="FAIL"),
        rule(rule_id=2, mandatory=0, verdict="FAIL"),
        rule(rule_id=3, verdict="UNKNOWN"),
    ]
    blocking, advisory, missing = split_parts(rows)
    assert len(blocking) == 1
    assert len(advisory) == 1
    assert len(missing) == 1


def test_gap_hint_reads_like_a_sentence():
    assert gap_hint(rule(verdict="FAIL")) == "income annual must be at most 2.5 lakh"
