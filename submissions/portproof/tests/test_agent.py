"""The dataset agent, the tiered repair policy, the cost meter and the new engines.

The first half needs no database. Model tiers are exercised with scripted
models, so nothing here spends a token or depends on what a provider returns
today; what is under test is what PortProof does with an answer, good or bad.
"""
from __future__ import annotations

import io
import json
import urllib.error

import pytest

from src import datasets, llm, repair
from src.corpus import CORPUS, DIALECTS, ORIGINAL_VARIANTS, VARIANTS, Statement, Variant
from src.counterexample import SemanticVerdict, InstanceResult, portable_ddl
from src.datasets import (
    DATASET_PROMPT,
    DatasetAgent,
    FIXTURE,
    column_from_type,
    features,
    generate,
    introspect,
    literal_dataset,
    parse_model_dataset,
    profile,
    schema_from_ddl,
)
from src.engines import SqliteSource

BANK = schema_from_ddl(
    "bank",
    [
        "CREATE TABLE accounts (id INTEGER NOT NULL PRIMARY KEY, owner_name VARCHAR(40), "
        "status VARCHAR(10), credit_limit DECIMAL(12,2))",
        "CREATE TABLE transactions (id INTEGER NOT NULL PRIMARY KEY, account_id INTEGER, "
        "amount DECIMAL(12,2), currency VARCHAR(3), memo VARCHAR(80), booked_at TIMESTAMP)",
    ],
)


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------
def test_the_corpus_covers_four_source_dialects():
    assert {s.dialect for s in CORPUS} == set(DIALECTS) == {"postgres", "mysql", "tsql", "sqlite"}
    for dialect in DIALECTS:
        assert sum(1 for s in CORPUS if s.dialect == dialect) >= 12, dialect


def test_there_are_twelve_distinct_hand_built_datasets():
    assert len(VARIANTS) == 12 and len(ORIGINAL_VARIANTS) == 6
    assert len({v.fingerprint for v in VARIANTS}) == 12
    assert len({v.name for v in VARIANTS}) == 12


def test_a_fingerprint_is_content_not_identity():
    base = VARIANTS[0]
    twin = Variant(name="another name", targets="x", rows={t: list(r) for t, r in base.rows.items()})
    assert twin.fingerprint == base.fingerprint
    assert base.shuffled().fingerprint != base.fingerprint


# --------------------------------------------------------------------------
# schema model
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "type_text, kind",
    [
        ("INTEGER", "int"), ("bigint", "int"), ("DECIMAL(10,2)", "decimal"), ("numeric", "decimal"),
        ("money", "decimal"), ("VARCHAR(60)", "text"), ("nvarchar", "text"), ("character varying", "text"),
        ("BOOLEAN", "bool"), ("bit", "bool"), ("tinyint(1)", "bool"), ("datetime2", "timestamp"),
        ("timestamp without time zone", "timestamp"), ("DATE", "date"), ("double precision", "double"),
    ],
)
def test_every_engines_type_names_map_to_one_vocabulary(type_text, kind):
    assert column_from_type("c", type_text).kind == kind


def test_the_fixture_is_read_back_from_its_own_ddl():
    assert FIXTURE.table_names == ("customers", "orders", "order_items", "events")
    amount = FIXTURE.table("orders").column("amount")
    assert (amount.kind, amount.precision, amount.scale) == ("decimal", 10, 2)
    assert FIXTURE.table("customers").column("id").pk


def test_sqlite_schema_is_discovered_from_the_engines_catalogue():
    engine = SqliteSource()
    engine.load(Variant("seed", "", {"accounts": [(1, "A", "ACTIVE", "5.00")]},
                        ddl=(BANK.tables[0].ddl(),), tables=("accounts",)))
    found = introspect(engine, "bank", tables=("accounts",))
    assert found.table_names == ("accounts",)
    assert [c.kind for c in found.tables[0].columns] == ["int", "text", "text", "decimal"]
    assert found.tables[0].column("id").pk
    stats = profile(engine, found)
    assert stats.rows == {"accounts": 1}
    engine.close()


def test_sql_server_ddl_is_adapted_not_rewritten():
    ddl = portable_ddl("CREATE TABLE t (a BOOLEAN, b TIMESTAMP, c VARCHAR(9))", "tsql")
    assert "BIT" in ddl and "DATETIME2" in ddl and "NVARCHAR(9)" in ddl


# --------------------------------------------------------------------------
# query features
# --------------------------------------------------------------------------
def test_features_come_from_the_syntax_tree():
    feats = features(
        "SELECT id, amount / 3 FROM transactions WHERE amount > 10000 AND currency = 'eur' "
        "AND memo LIKE 'rent%' AND booked_at >= '2026-01-01' ORDER BY id",
        "mysql",
    )
    assert {"division", "like", "order_by", "string_eq", "numeric_cmp", "date_cmp"} <= set(feats.tags)
    assert ("currency", "eur") in feats.strings
    assert ("memo", "rent%") in feats.patterns
    assert ("booked_at", "2026-01-01") in feats.dates
    assert any(col == "amount" and int(n) == 10000 for col, n in feats.numbers)


def test_a_word_inside_a_string_is_not_a_feature():
    feats = features("SELECT id FROM accounts WHERE owner_name = 'order by 1 / 2'", "postgres")
    assert "order_by" not in feats.tags and "division" not in feats.tags


def test_unparseable_sql_has_no_features_and_does_not_raise():
    assert features("SELECT FROM WHERE (((", "postgres").tags == ()


# --------------------------------------------------------------------------
# generation
# --------------------------------------------------------------------------
def _check_legal(schema, variant):
    for table in schema.tables:
        rows = variant.rows[table.name]
        keys = [tuple(v for v, c in zip(r, table.columns) if c.pk) for r in rows]
        assert len(keys) == len(set(keys)), f"{variant.name}: duplicate key in {table.name}"
        for row in rows:
            assert len(row) == len(table.columns)
            for value, col in zip(row, table.columns):
                if value is None:
                    assert col.nullable and not col.pk, f"{variant.name}: NULL in {col.name}"
                elif col.kind == "text" and variant.origin == "GENERATED":
                    # Bytes: Db2 counts a VARCHAR's length in bytes.
                    assert len(value.encode("utf-8")) <= col.length, f"{variant.name}: {col.name} too long"


def test_generated_datasets_are_legal_for_the_schema():
    made = generate(BANK)
    assert len(made) >= 10
    assert len({v.fingerprint for v in made}) == len(made)
    for variant in made:
        assert variant.origin == "GENERATED" and variant.ddl == BANK.ddl()
        _check_legal(BANK, variant)


def test_generation_is_deterministic():
    assert [v.fingerprint for v in generate(BANK)] == [v.fingerprint for v in generate(BANK)]


def test_foreign_keys_point_at_rows_that_exist():
    for variant in generate(BANK):
        ids = {r[0] for r in variant.rows["accounts"]}
        for row in variant.rows["transactions"]:
            assert row[1] is None or row[1] in ids, variant.name


def test_the_empty_children_dataset_has_parents_and_no_children():
    variant = next(v for v in generate(BANK) if v.strategy == "empty_groups")
    assert variant.rows["accounts"] and not variant.rows["transactions"]


def test_a_querys_literals_are_planted_in_the_forms_that_split_engines():
    feats = features(
        "SELECT id FROM transactions WHERE amount > 10000 AND currency = 'eur' ORDER BY id", "mysql"
    )
    variant = literal_dataset(BANK, feats, "bank/x")
    _check_legal(BANK, variant)
    currencies = {r[3] for r in variant.rows["transactions"]}
    amounts = {r[2] for r in variant.rows["transactions"]}
    assert {"eur", "EUR", "Eur"} <= currencies
    assert {"10000.00", "10001.00", "9999.00"} <= amounts
    # The first row is the query's own conjunction, so the filter selects something.
    first = variant.rows["transactions"][0]
    assert first[3] == "eur" and first[2] == "10001.00"
    assert literal_dataset(BANK, feats, "bank/x").fingerprint == variant.fingerprint


def test_no_literals_means_no_literal_dataset():
    assert literal_dataset(BANK, features("SELECT id FROM accounts ORDER BY id", "mysql"), "c") is None


# --------------------------------------------------------------------------
# a model's dataset is data, and is checked like data
# --------------------------------------------------------------------------
GOOD_REPLY = json.dumps(
    {
        "accounts": [[1, "Asha", "ACTIVE", "100.00"], [2, "asha", "active", None]],
        "transactions": [[1, 1, "10001.00", "eur", "rent", "2026-01-01 00:00:00"]],
    }
)


def test_a_valid_model_dataset_is_accepted_and_fitted_to_the_schema():
    variant = parse_model_dataset(BANK, "```json\n" + GOOD_REPLY + "\n```", "n", "t")
    assert variant.origin == "LLM"
    assert variant.rows["accounts"][1] == (2, "asha", "active", None)
    _check_legal(BANK, variant)


@pytest.mark.parametrize(
    "reply, why",
    [
        ("DROP TABLE accounts", "no JSON"),
        ("{not json}", "not valid JSON"),
        (json.dumps({"accounts": [[1, "A"]]}), "values for 4 columns"),
        (json.dumps({"accounts": [[1, "A", "X", "1"], [1, "B", "Y", "2"]]}), "duplicate primary key"),
        (json.dumps({"accounts": [[None, "A", "X", "1"]]}), "NOT NULL"),
        (json.dumps({"accounts": [[1, {"$ne": 1}, "X", "1"]]}), "nested"),
        (json.dumps({"accounts": [[1, "A", "X", "not a number"]]}), "is not a decimal"),
        (json.dumps({"accounts": [], "transactions": []}), "no rows"),
    ],
)
def test_a_bad_model_dataset_is_refused_with_a_reason(reply, why):
    with pytest.raises(ValueError, match=why):
        parse_model_dataset(BANK, reply, "n", "t")


def test_a_model_dataset_is_capped():
    many = json.dumps({"accounts": [[i, "A", "X", "1"] for i in range(1, 500)]})
    assert len(parse_model_dataset(BANK, many, "n", "t").rows["accounts"]) == 8


# --------------------------------------------------------------------------
# the agent: cache first, model last
# --------------------------------------------------------------------------
class FakeStore:
    def __init__(self, cached=(), yields=None):
        self._cached = list(cached)
        self._yields = yields or {}
        self.saved, self.logged = [], []

    def cached(self, schema_fp, origin=None):
        return [v for v in self._cached if origin is None or v.origin == origin]

    def save(self, schema_fp, variant):
        self.saved.append(variant)

    def log(self, *args):
        self.logged.append(args)

    def yields(self, dialect):
        return self._yields


class ScriptedModel:
    """Answers from a script and counts how often it was asked."""

    model = "scripted"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def ask(self, system, user, *, stage, case_name=""):
        self.prompts.append(user)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def _vacuous():
    return SemanticVerdict(
        outcome="VACUOUS", instances_checked=1, instances_agreed=1, source_engine="x",
        instances=[InstanceResult("v", "t", True)],
    )


STMT = Statement("mysql", "bank.large", "SELECT id FROM transactions WHERE amount > 10000", schema="bank")


def test_schema_datasets_are_generated_once_then_served_from_the_cache():
    store = FakeStore()
    first = DatasetAgent(store=store)
    first.register("bank", "mysql", BANK)
    planned, _ = first.plan(STMT)
    assert first.stats.generated >= 10 and first.stats.cache_hits == 0
    assert {v.fingerprint for v in store.saved} >= {v.fingerprint for v in planned}

    second = DatasetAgent(store=FakeStore(cached=[v for v in store.saved if v.strategy != "literal_boundaries"]))
    second.register("bank", "mysql", BANK)
    second.plan(STMT)
    assert second.stats.generated == 0 and second.stats.cache_hits >= 10


def test_a_cached_model_dataset_is_reused_instead_of_calling_the_model():
    cached = parse_model_dataset(BANK, GOOD_REPLY, "bank:model_earlier", "t")
    model = ScriptedModel(GOOD_REPLY)
    agent = DatasetAgent(store=FakeStore(cached=[cached]), model=model)
    agent.register("bank", "mysql", BANK)
    extra = agent.escalate(STMT, _vacuous(), used=[])
    assert [v.fingerprint for v in extra] == [cached.fingerprint]
    assert model.prompts == [] and agent.stats.model_calls == 0 and agent.stats.model_reused == 1


def test_the_model_is_called_only_when_nothing_cached_helps():
    model = ScriptedModel(GOOD_REPLY)
    store = FakeStore()
    agent = DatasetAgent(store=store, model=model)
    agent.register("bank", "mysql", BANK)
    extra = agent.escalate(STMT, _vacuous(), used=[])
    assert len(extra) == 1 and extra[0].origin == "LLM"
    assert agent.stats.model_calls == 1 and agent.stats.model_accepted == 1
    assert store.saved and store.saved[-1].origin == "LLM"  # kept for the next query


def test_a_useless_model_reply_costs_one_call_and_changes_nothing():
    agent = DatasetAgent(store=FakeStore(), model=ScriptedModel("I cannot help with that."))
    agent.register("bank", "mysql", BANK)
    assert agent.escalate(STMT, _vacuous(), used=[]) == []
    assert agent.stats.model_calls == 1 and agent.stats.model_rejected == 1


def test_no_model_means_no_escalation_and_no_error():
    agent = DatasetAgent(store=FakeStore())
    agent.register("bank", "mysql", BANK)
    assert agent.escalate(STMT, _vacuous(), used=[]) == []


def test_only_thin_proofs_are_escalated():
    agent = DatasetAgent()
    assert agent.needs_more(_vacuous())
    strong = SemanticVerdict("DIFFERENT", 1, 0, "x", instances=[InstanceResult("v", "t", False)])
    assert not agent.needs_more(strong)


def test_the_budget_keeps_the_datasets_the_log_says_find_things():
    division = Statement("mysql", "div", "SELECT id, amount / quantity AS u FROM orders ORDER BY id")
    learned = {"like_wildcards": (10, 10, 9)}  # runs, substantive, kills
    untaught, _ = DatasetAgent(max_datasets=3).plan(division)
    taught, _ = DatasetAgent(store=FakeStore(yields=learned), max_datasets=3).plan(division)
    assert len(untaught) == len(taught) == 3
    assert "division_and_rounding" in [v.name for v in untaught]
    assert "like_wildcards" not in [v.name for v in untaught]
    assert "like_wildcards" in [v.name for v in taught]


def test_what_the_model_is_shown_does_not_depend_on_how_much_data_there_is():
    """The cost claim, as a test: same schema, 5 rows or 5000, same prompt."""
    prompts = []
    for rows in (5, 5000):
        engine = SqliteSource()
        engine.load(
            Variant("seed", "", {
                "accounts": [(i, f"Owner {i}", "ACTIVE", "100.00") for i in range(1, rows + 1)],
                "transactions": [(i, i, "50.00", "EUR", "memo", "2026-01-01 00:00:00")
                                 for i in range(1, rows + 1)],
            }, ddl=BANK.ddl(), tables=BANK.table_names)
        )
        schema = introspect(engine, "bank", tables=BANK.table_names)
        stats = profile(engine, schema)
        assert stats.total_rows == rows * 2
        model = ScriptedModel(GOOD_REPLY)
        agent = DatasetAgent(model=model)
        agent.register("bank", "sqlite", schema, stats)
        agent.escalate(Statement("sqlite", "bank.large", STMT.sql, schema="bank"), _vacuous(), used=[])
        prompts.append(model.prompts[0])
        engine.close()
    assert prompts[0] == prompts[1]
    assert "Owner" not in prompts[0]  # and no row of the source is in it


# --------------------------------------------------------------------------
# SQLite: the real engine, loaded once per dataset
# --------------------------------------------------------------------------
def test_use_loads_a_dataset_once_and_switches_back_to_it():
    engine = SqliteSource()
    a, b = VARIANTS[0], VARIANTS[1]
    for _ in range(3):
        engine.use(a)
        assert len(engine.run("SELECT id FROM customers").rows) == 4
        engine.use(b)
        assert len(engine.run("SELECT id FROM customers").rows) == 3
    assert engine.loads == 2
    engine.close()


def test_a_dataset_in_a_namespace_never_touches_the_home_tables():
    engine = SqliteSource()
    engine.load(VARIANTS[0])
    engine.use(VARIANTS[5])  # one customer
    engine.home()
    assert len(engine.run("SELECT id FROM customers").rows) == 4
    engine.close()


def test_sqlite_really_divides_integers_where_db2_would_not():
    engine = SqliteSource()
    engine.use(VARIANTS[4])
    rows = dict(engine.run("SELECT id, amount / quantity FROM orders WHERE quantity <> 0").rows)
    assert rows[50] == 3  # 7.00 / 2: the DECIMAL column stored the integer 7
    engine.close()


# --------------------------------------------------------------------------
# the tiered repair loop
# --------------------------------------------------------------------------
class FakeMemory:
    def __init__(self, known=None):
        self.known = dict(known or {})

    def exact(self, *, bad_sql, dialect):
        return self.known.get((dialect, bad_sql))

    def recall(self, **_):
        return []


@pytest.fixture
def db2_accepts(monkeypatch):
    """Stand in for PREPARE: only the listed statements compile."""
    accepted: set[str] = set()
    asked: list[str] = []

    def check(conn, sql):
        from src.db import CompileResult

        asked.append(sql)
        return CompileResult(ok=True) if sql in accepted else CompileResult(
            ok=False, sqlcode=-104, message="unexpected token")

    monkeypatch.setattr(repair.db, "compile_check", check)
    return accepted, asked


BAD = "SELECT GROUP_CONCAT(sku) FROM order_items"
RULE_FIX = "SELECT LISTAGG(sku, ',') FROM order_items"


def _loop(model=None, memory=None, tiers=("memory", "rules", "chain")):
    loop = repair.RepairLoop(None, memory=memory, llm=model or llm.RuleRepairLLM(), tiers=tiers,
                             max_attempts=3)
    return loop


def test_memory_answers_first_and_nothing_else_is_asked(db2_accepts):
    accepted, _ = db2_accepts
    accepted.add("SELECT 'remembered' FROM sysibm.sysdummy1")
    model = _Chat("SELECT 1 FROM sysibm.sysdummy1")
    outcome = _loop(model, FakeMemory({("mysql", BAD): "SELECT 'remembered' FROM sysibm.sysdummy1"})).run(
        source_sql=BAD, db2_sql=BAD, dialect="mysql")
    assert outcome.repaired and outcome.fixed_by == "memory"
    assert model.calls == 0 and outcome.model_calls == 0


def test_rules_answer_second_without_a_model_call(db2_accepts):
    accepted, _ = db2_accepts
    accepted.add(RULE_FIX)
    model = _Chat("SELECT 1 FROM sysibm.sysdummy1")
    outcome = _loop(model, FakeMemory()).run(source_sql=BAD, db2_sql=BAD, dialect="mysql")
    assert outcome.fixed_by == "rules" and model.calls == 0
    assert [a.tier for a in outcome.attempts] == ["translator", "rules"]


def test_the_model_is_asked_only_after_db2_rejects_the_rules(db2_accepts):
    accepted, _ = db2_accepts
    accepted.add("SELECT 'model' FROM sysibm.sysdummy1")
    model = _Chat("SELECT 'model' FROM sysibm.sysdummy1")
    outcome = _loop(model, FakeMemory()).run(source_sql=BAD, db2_sql=BAD, dialect="mysql")
    assert outcome.fixed_by == "model" and model.calls == 1
    assert [a.tier for a in outcome.attempts] == ["translator", "rules", "model"]


def test_a_destructive_proposal_never_reaches_db2(db2_accepts):
    _, asked = db2_accepts
    model = _Chat("DROP TABLE orders")
    outcome = _loop(model, tiers=("chain",)).run(source_sql=BAD, db2_sql=BAD, dialect="mysql")
    assert not outcome.repaired
    assert "DROP TABLE orders" not in asked


def test_the_loop_stops_at_its_budget_however_wrong_the_model_is(db2_accepts):
    replies = [f"SELECT {i} FROM nowhere" for i in range(50)]
    model = _Chat(*replies)
    outcome = _loop(model, tiers=("chain",)).run(source_sql=BAD, db2_sql=BAD, dialect="mysql")
    assert not outcome.repaired
    assert model.calls == 3 and outcome.attempt_count == 4  # the translator's, then three


class _Chat(llm.LLM):
    """A LangChain LLM that replays a script: the model tier without a model."""

    script: list = []
    calls: int = 0

    def __init__(self, *replies):
        super().__init__()
        object.__setattr__(self, "script", list(replies))
        object.__setattr__(self, "calls", 0)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _call(self, prompt, stop=None, run_manager=None, **kwargs) -> str:
        object.__setattr__(self, "calls", self.calls + 1)
        return self.script[min(self.calls - 1, len(self.script) - 1)]


# --------------------------------------------------------------------------
# metering and the spending cap
# --------------------------------------------------------------------------
class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _reply(content="SELECT 1", usage=None):
    body = {"choices": [{"message": {"content": content}}]}
    if usage is not None:
        body["usage"] = usage
    return _Response(json.dumps(body).encode())


@pytest.fixture
def meter(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-real")
    llm.METER.reset()
    yield llm.METER
    llm.METER.reset()


def test_every_call_is_metered_with_the_providers_own_counts(meter, monkeypatch):
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda *a, **k: _reply(
        usage={"prompt_tokens": 300, "completion_tokens": 40, "total_tokens": 900}))
    model = llm.HttpRepairLLM(model="m", api_key="k", base_url="http://x")
    assert model.ask("s", "u", stage="DATASET", case_name="c") == "SELECT 1"
    (call,) = meter.calls
    # total - prompt, so reasoning tokens the provider bills for are counted.
    assert (call.stage, call.prompt_tokens, call.completion_tokens, call.estimated) == ("DATASET", 300, 600, False)
    assert meter.by_stage() == {"DATASET": (1, 300, 600)}


def test_a_missing_usage_block_is_an_estimate_and_says_so(meter, monkeypatch):
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda *a, **k: _reply())
    llm.HttpRepairLLM(model="m", api_key="k", base_url="http://x").ask("s" * 400, "u" * 400, stage="DATASET")
    assert meter.calls[0].estimated and meter.calls[0].prompt_tokens == 200


def test_the_call_budget_is_a_hard_stop(meter, monkeypatch):
    monkeypatch.setenv("LLM_CALL_BUDGET", "2")
    monkeypatch.setattr(llm.urllib.request, "urlopen", lambda *a, **k: _reply(usage={"prompt_tokens": 1}))
    model = llm.HttpRepairLLM(model="m", api_key="k", base_url="http://x")
    model.ask("s", "u", stage="DATASET")
    model.ask("s", "u", stage="DATASET")
    with pytest.raises(RuntimeError, match="budget of 2 is spent"):
        model.ask("s", "u", stage="DATASET")
    assert len(meter.calls) == 2


def test_a_rate_limit_is_waited_out_not_reported_as_failure(meter, monkeypatch):
    seen = []

    def flaky(*a, **k):
        seen.append(1)
        if len(seen) == 1:
            raise urllib.error.HTTPError("http://x", 429, "slow down", {}, None)
        return _reply(usage={"prompt_tokens": 5, "completion_tokens": 5})

    monkeypatch.setattr(llm.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    assert llm.HttpRepairLLM(model="m", api_key="k", base_url="http://x").ask("s", "u", stage="DATASET")
    assert len(seen) == 2 and len(meter.calls) == 1 and meter.calls[0].ok


def test_the_request_caps_output_and_asks_for_little_reasoning(meter, monkeypatch):
    sent = {}

    def capture(request, **k):
        sent.update(json.loads(request.data))
        return _reply(usage={"prompt_tokens": 1})

    monkeypatch.setattr(llm.urllib.request, "urlopen", capture)
    llm.HttpRepairLLM(model="m", api_key="k", base_url="http://x").ask("s", "u", stage="DATASET")
    assert sent["max_tokens"] == 3000 and sent["reasoning_effort"] == "low" and sent["temperature"] == 0


def test_tiered_without_a_key_is_memory_and_rules(monkeypatch):
    for name in ("LLM_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "tiered")
    from src.config import llm_config

    cfg = llm_config()
    assert cfg.is_tiered and cfg.is_mock and not cfg.has_model
    assert llm.build_model(cfg) is None
    assert repair.RepairLoop(None).tiers == ("memory", "rules")


def test_tiered_with_a_key_adds_the_model_as_the_last_tier(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "tiered")
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-real")
    loop = repair.RepairLoop(None)
    assert loop.tiers == ("memory", "rules", "chain") and loop.model is not None


# --------------------------------------------------------------------------
# live Db2
# --------------------------------------------------------------------------
pytestmark_db2 = pytest.mark.db2


@pytestmark_db2
def test_the_dataset_cache_round_trips_and_is_idempotent(app_conn, owner_conn):
    from src import db
    from src.datasets import DatasetStore

    variant = parse_model_dataset(BANK, GOOD_REPLY, "bank:test_roundtrip", "test")
    store = DatasetStore(app_conn)
    try:
        store.save("testfp0000000001", variant)
        DatasetStore(app_conn).save("testfp0000000001", variant)  # a second process
        back = store.cached("testfp0000000001")
        assert len(back) == 1 and back[0].fingerprint == variant.fingerprint
        assert back[0].origin == "LLM" and back[0].rows == variant.rows

        store.log(variant.fingerprint, "t/case", "mysql", ("like",), 3, False, False, True)
        assert store.yields("mysql")["model_proposed"][2] >= 1
    finally:
        db.execute(owner_conn, "DELETE FROM PORTPROOF.DATASET WHERE SCHEMA_FP = 'testfp0000000001'")


@pytestmark_db2
def test_the_runtime_user_cannot_write_the_cache_except_through_the_procedures(app_conn):
    from src import db

    for sql in (
        "INSERT INTO PORTPROOF.DATASET_RUN (DATASET_ID, CASE_NAME, SRC_DIALECT) VALUES (1, 'a', 'b')",
        "DELETE FROM PORTPROOF.DATASET",
        "UPDATE PORTPROOF.LLM_CALL SET PROMPT_TOKENS = 0",
    ):
        with pytest.raises(db.Db2Error) as refused:
            db.execute(app_conn, sql)
        assert refused.value.sqlcode == -551, sql


@pytestmark_db2
def test_db2_itself_refuses_a_payload_that_is_not_a_dataset(app_conn):
    from src import db

    with pytest.raises(db.Db2Error) as refused:
        db.call_proc(app_conn, "PORTPROOF.RECORD_DATASET",
                     ("testfp0000000002", "n", "LLM", "s", "t", "not json at all", "sha-x", 0))
    assert refused.value.sqlstate == "75001"


@pytestmark_db2
def test_model_calls_are_ledgered_and_summed_by_the_engine(app_conn, owner_conn):
    from src import db

    try:
        db.call_proc(app_conn, "PORTPROOF.RECORD_LLM_CALL",
                     ("DATASET", "test-model-xyz", "t/case", 310, 420, 900, 1))
        db.call_proc(app_conn, "PORTPROOF.RECORD_LLM_CALL",
                     ("DATASET", "test-model-xyz", "t/case", 290, 380, 700, 1))
        row = db.fetch_one(
            app_conn,
            "SELECT CALLS, PROMPT_TOKENS, COMPLETION_TOKENS FROM PORTPROOF.LLM_COST "
            "WHERE MODEL = 'test-model-xyz'")
        assert tuple(int(x) for x in row) == (2, 600, 800)
    finally:
        db.execute(owner_conn, "DELETE FROM PORTPROOF.LLM_CALL WHERE MODEL = 'test-model-xyz'")


def _sqlite_pipeline(app_conn, owner_conn, agent, **kw):
    from src.pipeline import Pipeline

    return Pipeline(app_conn=app_conn, owner_conn=owner_conn, sources={"sqlite": SqliteSource()},
                    dataset_agent=agent, learn=False, **kw)


@pytestmark_db2
def test_a_schema_nobody_wrote_datasets_for_is_proved_end_to_end(app_conn, owner_conn):
    """Seed, discover from the catalogue, generate, prove: on SQLite, no fixture."""
    from src import db, samples
    from src.counterexample import FIXTURE_SCHEMA

    before = db.fetch_one(owner_conn, "SELECT COUNT(*) FROM SYSCAT.TABLES WHERE TABSCHEMA LIKE 'PPV\\_%' ESCAPE '\\'")
    agent = DatasetAgent()
    pipeline = _sqlite_pipeline(app_conn, owner_conn, agent)
    try:
        found = samples.discover(pipeline.sources, agent)
        assert set(found) == {("hr", "sqlite"), ("bank", "sqlite")}
        results = {s.name: pipeline.run_statement(s) for s in samples.statements(("sqlite",))}
    finally:
        pipeline.close()

    assert all(r.datasets_used >= 10 for r in results.values())
    # SQLite's LIKE ignores case and Db2's does not: found on generated data,
    # and closed by the rule that was written from the model's own repairs.
    search = results["hr.name_search"]
    assert search.original_semantic.outcome == "DIFFERENT"
    assert search.original_semantic.witness.strategy in ("literal_boundaries", "mixed_case", "like_wildcards")
    assert search.status == "PROVEN_EQUIVALENT"
    assert search.semantic_repair.rule == "sqlite-case-insensitive-like"
    # Same answer on both engines, with rows to show for it.
    assert results["bank.balance_per_account"].status == "PROVEN_EQUIVALENT"
    assert results["bank.balance_per_account"].semantic.strength == "STRONG"
    # ...and the connection is back where every other caller expects it.
    assert db.fetch_one(owner_conn, "VALUES CURRENT SCHEMA")[0].strip() == FIXTURE_SCHEMA
    left = db.fetch_one(owner_conn, "SELECT COUNT(*) FROM SYSCAT.TABLES WHERE TABSCHEMA LIKE 'PPV\\_%' ESCAPE '\\'")
    assert int(left[0]) == int(before[0])


@pytestmark_db2
def test_twelve_datasets_find_what_six_did_not(app_conn, owner_conn):
    """One statement, proved on the first six datasets and then on all twelve."""
    from src.pipeline import Pipeline

    statement = next(s for s in CORPUS if s.case_name == "sqlite/substr_instr")
    outcomes = {}
    for label, variants in (("six", ORIGINAL_VARIANTS), ("twelve", VARIANTS)):
        pipeline = Pipeline(app_conn=app_conn, owner_conn=owner_conn, sources={"sqlite": SqliteSource()},
                            learn=False, semantic_repair=False, variants=variants)
        try:
            outcomes[label] = pipeline.run_statement(statement)
        finally:
            pipeline.close()
    assert outcomes["six"].status == "PROVEN_EQUIVALENT"
    assert outcomes["twelve"].status == "PROVEN_DIFFERENT"
    # Db2's INSTR counted bytes; SQLite's counted characters.
    assert outcomes["twelve"].semantic.witness.variant == "accents_and_unicode"


@pytestmark_db2
def test_a_model_rewrite_is_accepted_only_because_the_proof_agrees(owner_conn):
    from src.counterexample import Db2Target, ensure_fixture_schema, prove_semantics
    from src.semantic_repair import SemanticRepairLoop

    ensure_fixture_schema(owner_conn)
    target, source = Db2Target(owner_conn), SqliteSource()
    sql = "SELECT id FROM customers WHERE name LIKE '%SMITH%' ORDER BY id"
    right = "SELECT id FROM customers WHERE UPPER(name) LIKE '%SMITH%' ORDER BY id"
    wrong = "SELECT id FROM customers WHERE name LIKE '%Smith%' ORDER BY id"
    try:
        before = prove_semantics(source_sql=sql, db2_sql=sql, source=source, target=target, dialect="sqlite")
        assert before.outcome == "DIFFERENT"

        def run(*replies):
            model = ScriptedModel(*replies)
            fix = SemanticRepairLoop(owner_conn, source=source, target=target, model=model, rules=[]).run(
                source_sql=sql, db2_sql=sql, dialect="sqlite", before=before)
            return fix, model

        fix, model = run(right)
        assert fix.repaired and fix.tier == "model" and fix.final_sql == right
        assert fix.verdict.outcome == "EQUIVALENT" and fix.verdict.strength == "STRONG"
        # The model saw the counterexample, and no more than five rows of it.
        assert "returned (first rows)" in model.prompts[0]

        fix, model = run(wrong, wrong)
        assert not fix.repaired and len(model.prompts) == 2  # confidently wrong, twice, and refused

        fix, model = run("DELETE FROM customers")
        assert not fix.repaired
        assert "rejected before execution" in fix.attempts[-1].message
        assert len(target.run("SELECT id FROM customers").rows) > 0

        fix, _ = run("SELECT id FROM no_such_table", right)
        assert fix.repaired and [a.compiled for a in fix.attempts] == [False, True]
    finally:
        target.close()
        source.close()


@pytestmark_db2
def test_a_proved_rewrite_is_replayed_from_memory_with_no_model_call(owner_conn):
    from src.counterexample import Db2Target, ensure_fixture_schema, prove_semantics
    from src.semantic_repair import SemanticRepairLoop

    ensure_fixture_schema(owner_conn)
    target, source = Db2Target(owner_conn), SqliteSource()
    sql = "SELECT id FROM customers WHERE name LIKE '%SMITH%' ORDER BY id"
    right = "SELECT id FROM customers WHERE UPPER(name) LIKE '%SMITH%' ORDER BY id"
    try:
        before = prove_semantics(source_sql=sql, db2_sql=sql, source=source, target=target, dialect="sqlite")
        model = ScriptedModel("never asked")
        fix = SemanticRepairLoop(
            owner_conn, source=source, target=target, model=model,
            memory=FakeMemory({("sqlite", sql): right}),
        ).run(source_sql=sql, db2_sql=sql, dialect="sqlite", before=before)
        assert fix.repaired and fix.tier == "memory" and model.prompts == []
    finally:
        target.close()
        source.close()


@pytestmark_db2
def test_sql_server_is_judged_by_a_real_sql_server(owner_conn):
    from src.counterexample import Db2Target, ensure_fixture_schema, prove_semantics
    from src.engines import SqlServerSource

    try:
        source = SqlServerSource()
    except Exception as exc:  # pragma: no cover - no SQL Server on this machine
        pytest.skip(f"no SQL Server reachable: {str(exc)[:80]}")
    ensure_fixture_schema(owner_conn)
    target = Db2Target(owner_conn)
    try:
        # LEN ignores trailing blanks; Db2's LENGTH counts them.
        verdict = prove_semantics(
            source_sql="SELECT id, LEN(name) AS n FROM customers ORDER BY id",
            db2_sql="SELECT id, LENGTH(name) AS n FROM customers ORDER BY id",
            source=source, target=target, dialect="tsql")
        assert verdict.outcome == "DIFFERENT"
        assert verdict.witness.variant == "trailing_spaces"
        refused = prove_semantics(source_sql="SELECT 1", db2_sql="SELECT 1", source=source,
                                  target=target, dialect="mysql")
        assert refused.outcome == "INCONCLUSIVE"  # never judges another engine's dialect
    finally:
        target.close()
        source.close()


# --------------------------------------------------------------------------
# dead ends: the model is not paid twice to fail at the same question
# --------------------------------------------------------------------------
class FakeDeadEnds:
    def __init__(self):
        self.seen: set[tuple] = set()
        self.skipped = 0

    def known(self, stage, model, *parts):
        hit = (stage, model, parts) in self.seen
        self.skipped += int(hit)
        return hit

    def record(self, stage, model, case_name, attempts, *parts):
        self.seen.add((stage, model, parts))


def test_a_dataset_the_model_could_not_write_is_not_asked_for_again():
    dead = FakeDeadEnds()
    first = DatasetAgent(store=FakeStore(), model=ScriptedModel("I cannot help with that."))
    first.dead_ends = dead
    first.register("bank", "mysql", BANK)
    assert first.escalate(STMT, _vacuous(), used=[]) == []
    assert first.stats.model_calls == 1 and len(dead.seen) == 1

    model = ScriptedModel(GOOD_REPLY)
    second = DatasetAgent(store=FakeStore(), model=model)
    second.dead_ends = dead
    second.register("bank", "mysql", BANK)
    assert second.escalate(STMT, _vacuous(), used=[]) == []
    assert model.prompts == [] and second.stats.model_calls == 0 and dead.skipped == 1


def test_a_model_that_never_answered_is_not_a_dead_end():
    dead = FakeDeadEnds()
    agent = DatasetAgent(store=FakeStore(), model=ScriptedModel(TimeoutError("no answer")))
    agent.dead_ends = dead
    agent.register("bank", "mysql", BANK)
    assert agent.escalate(STMT, _vacuous(), used=[]) == []
    assert dead.seen == set()  # a timeout says nothing about the question


@pytestmark_db2
def test_a_statement_the_model_failed_to_repair_is_not_sent_to_it_again(owner_conn):
    from src.counterexample import Db2Target, ensure_fixture_schema, prove_semantics
    from src.semantic_repair import SemanticRepairLoop

    ensure_fixture_schema(owner_conn)
    target, source = Db2Target(owner_conn), SqliteSource()
    sql = "SELECT id FROM customers WHERE name LIKE '%SMITH%' ORDER BY id"
    wrong = "SELECT id FROM customers WHERE name LIKE '%SMITH%' ORDER BY id DESC"
    dead = FakeDeadEnds()
    try:
        before = prove_semantics(source_sql=sql, db2_sql=sql, source=source, target=target, dialect="sqlite")
        first = ScriptedModel(wrong, wrong)
        fix = SemanticRepairLoop(owner_conn, source=source, target=target, model=first, rules=[],
                                 dead_ends=dead).run(
            source_sql=sql, db2_sql=sql, dialect="sqlite", before=before)
        assert not fix.repaired and len(first.prompts) == 2 and len(dead.seen) == 1

        second = ScriptedModel("never asked")
        again = SemanticRepairLoop(owner_conn, source=source, target=target, model=second, rules=[],
                                   dead_ends=dead).run(
            source_sql=sql, db2_sql=sql, dialect="sqlite", before=before)
        assert not again.repaired and again.model_skipped and second.prompts == []

        # A statement that changed is a new question.
        other = sql.replace("SMITH", "STONE")
        before_other = prove_semantics(source_sql=other, db2_sql=other, source=source,
                                       target=target, dialect="sqlite")
        third = ScriptedModel(wrong, wrong)
        SemanticRepairLoop(owner_conn, source=source, target=target, model=third, rules=[],
                           dead_ends=dead).run(
            source_sql=other, db2_sql=other, dialect="sqlite", before=before_other)
        assert third.prompts
    finally:
        target.close()
        source.close()


@pytestmark_db2
def test_dead_ends_live_in_db2_and_only_the_procedure_can_write_them(app_conn, owner_conn):
    from src import db
    from src.llm import METER, DeadEnds

    dead = DeadEnds(app_conn)
    dead.retry = False
    parts = ("sqlite", "SELECT 'dead-end-test'", "SELECT 'dead-end-test'")
    avoided = METER.avoided
    try:
        assert not dead.known("SEMANTIC_REPAIR", "test-model-xyz", *parts)
        dead.record("SEMANTIC_REPAIR", "test-model-xyz", "t/case", 2, *parts)
        dead.record("SEMANTIC_REPAIR", "test-model-xyz", "t/case", 2, *parts)  # idempotent
        assert dead.known("SEMANTIC_REPAIR", "test-model-xyz", *parts)
        assert METER.avoided == avoided + 1
        assert not dead.known("SEMANTIC_REPAIR", "another-model", *parts)
        assert not dead.known("DATASET", "test-model-xyz", *parts)
        row = db.fetch_one(app_conn, "SELECT COUNT(*), SUM(ATTEMPTS) FROM PORTPROOF.MODEL_DEAD_END "
                                     "WHERE MODEL = 'test-model-xyz'")
        assert tuple(int(x) for x in row) == (1, 4)
        with pytest.raises(db.Db2Error) as refused:
            db.execute(app_conn, "DELETE FROM PORTPROOF.MODEL_DEAD_END")
        assert refused.value.sqlcode == -551
    finally:
        METER.avoided = avoided
        db.execute(owner_conn, "DELETE FROM PORTPROOF.MODEL_DEAD_END WHERE MODEL = 'test-model-xyz'")


# --------------------------------------------------------------------------
# rules written from what the model kept rediscovering
# --------------------------------------------------------------------------
def test_blank_sensitive_equality_adds_a_length_check_to_every_form():
    from src.semantic_repair import _blank_sensitive_equality as rewrite

    assert rewrite("SELECT 1 FROM t WHERE name = 'a'") == (
        "SELECT 1 FROM t WHERE (name = 'a' AND LENGTH(name) = LENGTH('a'))")
    assert rewrite("SELECT 1 FROM t WHERE name <> 'a'") == (
        "SELECT 1 FROM t WHERE (name <> 'a' OR LENGTH(name) <> LENGTH('a'))")
    # IN is a list of equalities, and its own output is not rewritten twice.
    assert rewrite("SELECT 1 FROM t WHERE s IN ('x', 'y')") == (
        "SELECT 1 FROM t WHERE ((s = 'x' AND LENGTH(s) = LENGTH('x')) OR "
        "(s = 'y' AND LENGTH(s) = LENGTH('y')))")
    assert rewrite("SELECT 1 FROM t WHERE s NOT IN ('x')") == (
        "SELECT 1 FROM t WHERE ((s <> 'x' OR LENGTH(s) <> LENGTH('x')))")
    assert rewrite("SELECT 1 FROM t WHERE n = 5") == "SELECT 1 FROM t WHERE n = 5"


def test_the_new_rules_fire_only_for_the_dialects_they_were_measured_on():
    from src.semantic_repair import SEMANTIC_RULES

    by_name = {r.name: r.dialect for r in SEMANTIC_RULES}
    assert by_name["postgres-blank-sensitive-equality"] == "postgres"
    assert by_name["sqlite-blank-sensitive-equality"] == "sqlite"
    # PostgreSQL's LIKE is case-sensitive, like Db2's: it must get no LIKE rule.
    assert not [n for n, d in by_name.items() if d == "postgres" and "like" in n]
    assert {d for n, d in by_name.items() if n.endswith("case-insensitive-like")} == {
        "mysql", "tsql", "sqlite"}


def test_case_insensitive_like_folds_both_sides():
    from src.semantic_repair import _case_insensitive_like as rewrite

    assert rewrite("SELECT id FROM t WHERE memo LIKE 'rent%' AND x NOT LIKE '%a'") == (
        "SELECT id FROM t WHERE UPPER(memo) LIKE UPPER('rent%') AND UPPER(x) NOT LIKE UPPER('%a')")
