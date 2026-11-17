"""PortProof -- the UI.

    streamlit run src/app.py

Five tabs:

1. **Translate & Prove** -- IBM's dialect translates, Db2 ``PREPARE`` judges, and
   a bounded repair loop fixes what Db2 rejected, re-verifying every attempt.
2. **Semantic Proof** -- the statement that *compiles* is then run against
   twelve adversarial datasets on both engines. A divergence is shown as a
   witness, shrunk to the fewest rows that still disagree, with Db2's own
   estimate of what the statement costs.
3. **Migrate a Workload** -- a whole workload at once: the corpus, the
   statements the source engine itself recorded, or an uploaded ``.sql`` file.
   Every statement is repaired and proved, the result is held against a gate
   policy, and the verdicts download as the same JSON the command line writes.
4. **Ledger & Engine** -- the Db2 side: the append-only verdict ledger with
   engine-computed SHA-256 certificates, the MQT rollup Db2 maintains itself,
   temporal time travel, the vector fix-memory, and measured physical advice.
5. **Model & Agents** -- what the model tier has cost, read from Db2; whether
   Db2 or this process makes the call; and the MCP tools an agent can use.

Nothing here is a mock. Every number on screen came back from Db2 in this
session.
"""
from __future__ import annotations

import html
import sys
import time
from pathlib import Path

import streamlit as st

# ``streamlit run src/app.py`` executes this file as a top-level script, not as
# a package member, so relative imports would fail. Put the project root on the
# path and import absolutely, which keeps `streamlit run src/app.py` working
# from the project directory without a wrapper script.
#
# Streamlit also puts this file's own directory, src/, first on the path. That
# makes every module in it importable under its bare name, and src/datasets.py
# then shadows the Hugging Face `datasets` package: sentence-transformers fails
# to import, fix-memory recall raises, and the repair loop quietly falls through
# to the model for repairs Db2 already holds. So src/ comes off the path.
_HERE = Path(__file__).resolve().parent
sys.path[:] = [p for p in sys.path if p and Path(p).resolve() != _HERE]
sys.path.insert(0, str(_HERE.parent))

from src import capture, costgate, db, physical, samples, translate  # noqa: E402
from src.config import llm_config, runtime_config, setup_config  # noqa: E402
from src.corpus import BASE, CORPUS, DIALECTS, VARIANTS, Statement, statements_for  # noqa: E402
from src.counterexample import (  # noqa: E402
    FIXTURE_SCHEMA,
    Db2Target,
    available_sources,
    ensure_fixture_schema,
    prove_semantics,
)
from src.datasets import DatasetAgent, DatasetStore  # noqa: E402
from src.llm import METER, build_model  # noqa: E402
from src.minimise import minimise  # noqa: E402
from src.embeddings import LocalEmbeddings  # noqa: E402
from src.fixmemory import FixMemory  # noqa: E402
from src.repair import RepairLoop  # noqa: E402
from src.safety import UnsafeSql, check_read_only  # noqa: E402

st.set_page_config(page_title="PortProof", page_icon="✓", layout="wide")

#: The palette, kept in one place. `.streamlit/config.toml` declares the same
#: values to Streamlit's own widgets; these are for the parts of the page this
#: file draws itself. Changing a colour means changing both.
INK = "#0A0F15"
SURFACE = "#111A24"
RAISED = "#18242F"
BORDER = "#223141"
TEXT = "#E4ECF4"
DIM = "#7E91A5"
AMBER = "#F0A93B"

#: Verdict colours are read as text on a dark background, not as badge fills,
#: so each one is a light tint rather than the saturated version that works on
#: white. The GitHub palette this started from was unreadable here.
VERDICT_COLOUR = {
    "EQUIVALENT": "#3FD894",
    "DIFFERENT": "#FF6B72",
    "UNSTABLE": "#FFA857",
    "VACUOUS": "#B48CFF",
    "INCONCLUSIVE": "#E9C46A",
}

#: "DIFFERENT" understates it: the engines were run and disagreed.
VERDICT_LABEL = {
    "EQUIVALENT": "PROVEN EQUIVALENT",
    "DIFFERENT": "PROVEN DIFFERENT",
    "UNSTABLE": "ORDER NOT DETERMINED",
    "VACUOUS": "VACUOUS, PROVES NOTHING",
    "INCONCLUSIVE": "INCONCLUSIVE",
}

#: How much an EQUIVALENT is actually worth. Shown next to the verdict, because
#: a verdict without its strength invites exactly the over-reading PortProof is
#: supposed to prevent.
STRENGTH_COLOUR = {
    "STRONG": "#3FD894",
    "MODERATE": "#E9C46A",
    "WEAK": "#FFA857",
    "NONE": DIM,
}

#: Injected once, after set_page_config. config.toml colours Streamlit's own
#: widgets; this covers what it cannot reach, which is mostly the tab strip,
#: the metric tiles and the two SQL panels that carry the whole argument of
#: tab 1. Selectors are kept to Streamlit's stable `data-testid` attributes
#: rather than its generated class names, which change between releases.
THEME_CSS = f"""
<style>
:root {{
  --pp-ink: {INK};
  --pp-surface: {SURFACE};
  --pp-raised: {RAISED};
  --pp-border: {BORDER};
  --pp-text: {TEXT};
  --pp-dim: {DIM};
  --pp-amber: {AMBER};
}}

.stApp {{
  background:
    radial-gradient(1100px 500px at 15% -10%, #16242F 0%, rgba(22,36,47,0) 60%),
    radial-gradient(900px 450px at 95% 0%, #1A2030 0%, rgba(26,32,48,0) 55%),
    var(--pp-ink);
}}

/* The title, set as a thin wordmark with a rule under it. */
h1 {{
  font-weight: 300 !important;
  letter-spacing: -0.02em;
  font-size: 2.9rem !important;
  background: linear-gradient(96deg, var(--pp-text) 15%, var(--pp-amber) 112%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  padding-bottom: .1em;
}}
h3, h4 {{ letter-spacing: -0.01em; }}

/* Metric tiles: cards rather than floating numbers. */
div[data-testid="stMetric"] {{
  background: linear-gradient(180deg, var(--pp-surface) 0%, rgba(17,26,36,.55) 100%);
  border: 1px solid var(--pp-border);
  border-radius: .55rem;
  padding: .85rem 1rem;
}}
div[data-testid="stMetric"] label p {{
  color: var(--pp-dim) !important;
  text-transform: uppercase;
  letter-spacing: .09em;
  font-size: .68rem !important;
  font-weight: 600;
}}
div[data-testid="stMetricValue"] {{
  font-size: 1.45rem !important;
  font-weight: 500;
}}
/* The delta line here is a caption, not a movement, so the arrow glyph goes.
   delta_color="off" greys it but Streamlit still draws the triangle. */
div[data-testid="stMetricDelta"] svg {{ display: none; }}
div[data-testid="stMetricDelta"] {{
  font-size: .78rem;
  color: var(--pp-dim) !important;
}}

/* Tabs: an amber underline on the active one, nothing else. */
div[data-testid="stTabs"] button[role="tab"] {{
  color: var(--pp-dim);
  font-weight: 500;
  letter-spacing: .01em;
}}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
  color: var(--pp-text);
  background: var(--pp-raised);
  border-radius: .4rem .4rem 0 0;
}}

/* SQL panels. Tab 1 is an argument made by two code blocks side by side, so
   they get a left rule to separate them from the prose around them. */
div[data-testid="stCode"], pre {{
  border: 1px solid var(--pp-border) !important;
  border-left: 3px solid var(--pp-amber) !important;
  border-radius: .45rem !important;
}}
code {{ font-size: .86em; }}

/* Alerts, toned down. Streamlit's defaults are loud enough to out-shout the
   verdict they are sitting next to. */
div[data-testid="stAlert"] {{
  border: 1px solid var(--pp-border);
  border-left-width: 3px;
  background: var(--pp-surface);
  border-radius: .45rem;
}}

div[data-testid="stExpander"] details {{
  background: var(--pp-surface);
  border: 1px solid var(--pp-border);
  border-radius: .5rem;
}}

div[data-testid="stDataFrame"] {{
  border: 1px solid var(--pp-border);
  border-radius: .5rem;
}}

/* The primary action reads as the one thing to press on each tab. */
button[kind="primary"] {{
  background: linear-gradient(180deg, #F7BC5C 0%, var(--pp-amber) 100%);
  color: #10161E !important;
  font-weight: 650;
  border: 0;
}}
button[kind="primary"]:hover {{ filter: brightness(1.08); }}

div[data-testid="stCaptionContainer"] p {{ color: var(--pp-dim) !important; }}
hr {{ border-color: var(--pp-border); }}

footer, #MainMenu {{ visibility: hidden; }}
</style>
"""


# --------------------------------------------------------------------------
# connections: opened once per session, never per rerun
# --------------------------------------------------------------------------
@st.cache_resource(show_spinner="Connecting to Db2...")
def _connections():
    app_conn = db.connect(runtime_config(), role="app")
    db.execute(app_conn, "SET CURRENT SCHEMA PORTPROOF")
    owner_conn = db.connect(setup_config(), role="setup")
    ensure_fixture_schema(owner_conn)
    return app_conn, owner_conn


@st.cache_resource(show_spinner="Loading the local embedding model...")
def _embeddings():
    return LocalEmbeddings()


@st.cache_resource(show_spinner="Loading the local embedding model...")
def _memory(_app_conn):
    return FixMemory(_app_conn, embeddings=_embeddings())


@st.cache_resource(show_spinner="Starting the source engines...")
def _prover(_owner_conn):
    """The source engines, one per dialect, and the Db2 target.

    MySQL is a real server when one is reachable. If it is not, MySQL
    statements come back INCONCLUSIVE rather than being judged by a
    PostgreSQL-compatible stand-in -- see :class:`DuckDbSource`.
    """
    target = Db2Target(_owner_conn)
    # The compile oracle resolves names against PPTEST, and the proofs now load
    # their datasets into schemas of their own, so nothing else guarantees the
    # fixture tables are there on a fresh database.
    target.load(BASE)
    return available_sources(), target


def _code(sql: str, *, language: str = "sql") -> None:
    st.code(sql.strip() or "--", language=language)


def _show_minimal(smallest) -> None:
    """The fewest rows on which the two engines still disagree."""
    st.markdown("#### The smallest input that still disagrees")
    st.caption(
        f"{smallest.rows_after} row(s), down from {smallest.rows_before}, found by "
        f"deleting rows and re-running both engines {smallest.trials} times. Every row "
        "left is needed: remove any one and the engines agree."
    )
    st.dataframe(
        [{"table": table, **{f"c{i}": v for i, v in enumerate(row)}}
         for table, rows in smallest.rows.items() for row in rows],
        width="stretch",
        hide_index=True,
    )
    ml, mr = st.columns(2)
    with ml:
        _rows_table(smallest.source_rows, "source returns")
    with mr:
        _rows_table(smallest.db2_rows, "Db2 returns")


def _rows_table(rows, caption: str) -> None:
    st.caption(caption)
    if not rows:
        st.write("_no rows_")
        return
    st.dataframe(
        [{f"c{i}": v for i, v in enumerate(row)} for row in rows[:12]],
        width="stretch",
        hide_index=True,
    )


# --------------------------------------------------------------------------
# header
# --------------------------------------------------------------------------
try:
    app_conn, owner_conn = _connections()
except Exception as exc:  # pragma: no cover - UI path
    st.error(f"Db2 is not reachable: {exc}")
    st.info("Start the container, then run `python -m src.setup_db`. See README.md.")
    st.stop()

cfg = llm_config()
st.markdown(THEME_CSS, unsafe_allow_html=True)
st.title("PortProof")
st.markdown(
    "**AI proposes, Db2 proves.** A migration is only done when the engine says so."
)

c1, c2, c3, c4 = st.columns(4)
# delta_color="off" throughout: these are captions, not movements. Streamlit's
# default renders a delta as a green upward arrow, which reads as "this went
# up" and is nonsense next to "least privilege".
c1.metric("Db2", db.server_version(owner_conn), "Community Edition", delta_color="off")
c2.metric(
    "runtime identity",
    db.current_identity(app_conn)[0],
    "least privilege",
    delta_color="off",
)
c3.metric(
    "owner identity", db.current_identity(owner_conn)[0], "DDL only", delta_color="off"
)
c4.metric(
    "repair engine",
    # Not "mock". The provider is named `mock` in the configuration because it
    # substitutes for a model, but what it actually runs is a deterministic
    # rewrite rule set, and calling that a mock on screen understates it: these
    # are the rules that repaired all fourteen rejected statements.
    "tiered" if cfg.is_tiered else ("rules" if cfg.is_mock else cfg.provider),
    cfg.label if cfg.is_tiered else ("deterministic, no API key" if cfg.is_mock else cfg.label),
    delta_color="off",
)

tab_prove, tab_semantic, tab_workload, tab_ledger, tab_model = st.tabs(
    ["1 · Translate & Prove", "2 · Semantic Proof", "3 · Migrate a Workload",
     "4 · Ledger & Engine", "5 · Model & Agents"]
)


# --------------------------------------------------------------------------
# tab 1 -- translate, compile-prove, repair
# --------------------------------------------------------------------------
def _pick_statement(key: str) -> Statement | None:
    """Shared statement chooser: a corpus case, or your own SQL."""
    mode = st.radio(
        "statement",
        ["from the corpus", "paste my own"],
        horizontal=True,
        key=f"{key}_mode",
        label_visibility="collapsed",
    )
    if mode == "from the corpus":
        names = [s.case_name for s in CORPUS]
        chosen = st.selectbox("case", names, key=f"{key}_case")
        return next(s for s in CORPUS if s.case_name == chosen)

    dialect = st.selectbox("source dialect", list(DIALECTS), key=f"{key}_dialect")
    sql = st.text_area(
        "source SQL",
        height=140,
        key=f"{key}_sql",
        placeholder="SELECT customer_id, STRING_AGG(sku, ',') FROM order_items GROUP BY 1",
        help="A single read-only query. The fixture tables are customers, "
        "orders, order_items and events.",
    )
    if not sql.strip():
        return None
    try:
        check_read_only(sql)
    except UnsafeSql as exc:
        st.error(f"rejected before it reached Db2: {exc}")
        return None
    return Statement(dialect=dialect, name="pasted", sql=sql.strip())


with tab_prove:
    st.subheader("IBM's translator is silent. Db2 is not.")
    st.markdown(
        "On the measured workload of 125 statements, `db2-sqlglot-dialect` raised "
        "an error for **none** of them and Db2 then rejected **17**. That gap is the "
        "bug class PortProof exists to close: a *silent* failure, which no linter "
        "catches because nothing complained."
    )

    statement = _pick_statement("prove")
    go = st.button("Translate, then let Db2 judge", type="primary", key="go_prove")

    if go and statement is None:
        st.warning("Give me a statement first.")
    elif go:
        left, right = st.columns(2)
        with left:
            st.markdown(f"**source** · `{statement.dialect}`")
            _code(statement.sql)

        attempt = translate.translate(statement.sql, statement.dialect)
        with right:
            st.markdown("**translated by `db2-sqlglot-dialect`**")
            _code(attempt.db2_sql or "-- translator raised")
            if attempt.raised:
                st.error(f"translator raised: {attempt.error}")
            else:
                st.success("translator reported no problem")

        if attempt.ok:
            with st.spinner("Db2 is compiling it (PREPARE, server-side)..."):
                first = db.compile_check(owner_conn, attempt.db2_sql or "")

            if first.ok:
                st.success("Db2 accepted it on the first try. Nothing to repair.")
                st.session_state["proved_sql"] = attempt.db2_sql
                st.session_state["proved_statement"] = statement
            else:
                st.error(
                    f"**SILENT FAILURE.** The translator was happy; Db2 was not: "
                    f"SQLCODE={first.sqlcode} / SQLSTATE={first.sqlstate}"
                )
                with st.expander("what Db2 actually said", expanded=True):
                    st.code(first.message.strip(), language="text")

                st.markdown("---")
                st.markdown("#### The repair loop")
                st.caption(
                    "LangGraph state machine, bounded attempts. Every proposal is "
                    "re-submitted to Db2. The loop can only exit through the engine."
                )

                memory = None
                try:
                    memory = _memory(app_conn)
                except Exception as exc:
                    st.info(f"fix memory unavailable, repairing without recall ({str(exc)[:80]})")

                with st.spinner("proposing, then re-verifying with Db2..."):
                    started = time.time()
                    outcome = RepairLoop(owner_conn, memory=memory).run(
                        source_sql=statement.sql,
                        db2_sql=attempt.db2_sql or "",
                        dialect=statement.dialect,
                    )
                    elapsed = time.time() - started

                if outcome.recalled_used:
                    st.markdown(
                        f"**grounded in {len(outcome.recalled_used)} verified repair(s) "
                        "recalled from Db2's vector store**"
                    )
                    for fix in outcome.recalled_used:
                        dist = f"{fix.distance:.4f}" if fix.distance is not None else "n/a"
                        st.markdown(
                            f"- SQLCODE `{fix.sqlcode}` · cosine distance `{dist}` · "
                            f"fixed by: `{fix.fixed_sql[:110]}`"
                        )

                for a in outcome.attempts:
                    icon = "✅" if a.ok else "❌"
                    # Attempt 0 is the translator's own output, before any repair
                    # ran, so calling it "attempt 0" misattributes it.
                    # ...and a repair says who proposed it: the fix memory,
                    # a rule, or the model. That is the answer to "is this AI".
                    what = "as translated" if a.n == 0 else f"repair attempt {a.n}, proposed by {a.tier}"
                    label = (
                        f"{icon} {what} · "
                        + ("Db2 accepted" if a.ok else f"Db2 rejected, SQLCODE={a.sqlcode}")
                        + (f" · rules: {', '.join(a.rules_fired)}" if a.rules_fired else "")
                    )
                    with st.expander(label, expanded=a.ok):
                        _code(a.sql)
                        if not a.ok:
                            st.code(a.message.strip()[:600], language="text")

                if outcome.repaired:
                    repairs = max(outcome.attempt_count - 1, 1)
                    st.success(
                        f"Repaired in {repairs} repair attempt(s), {elapsed:.1f}s, "
                        "and **Db2 re-verified it**, which is the only reason "
                        "this says 'repaired'."
                    )
                    st.session_state["proved_sql"] = outcome.final_sql
                    st.session_state["proved_statement"] = statement
                    st.info(
                        "Compiling is not the same as being correct. "
                        "Tab 2 proves the *meaning*."
                    )
                else:
                    st.error(
                        f"Not repaired after {outcome.attempt_count} attempts. "
                        "PortProof reports this as unresolved rather than shipping it."
                    )


# --------------------------------------------------------------------------
# tab 2 -- differential semantic proof
# --------------------------------------------------------------------------
with tab_semantic:
    st.subheader("Compiling proves nothing about the answer")
    st.markdown(
        "Both statements are executed on both engines over "
        f"**{len(VARIANTS)} adversarial datasets** chosen to break translation: "
        + ", ".join(f"`{v.name}`" for v in VARIANTS)
        + ". A disagreement is reported as a **witness**, meaning the dataset and the "
        "two result sets, so you can check the verdict yourself instead of "
        "trusting it."
    )

    carried = st.session_state.get("proved_statement")
    if carried is not None:
        st.caption(f"carried over from tab 1: `{carried.case_name}`")

    statement = _pick_statement("sem")
    use_carried = st.checkbox(
        "use the repaired SQL carried over from tab 1",
        value=carried is not None,
        key="use_carried",
        disabled=carried is None,
    )
    go = st.button("Prove the meaning", type="primary", key="go_sem")

    if go:
        if use_carried and carried is not None:
            statement = carried
            db2_sql = st.session_state.get("proved_sql") or ""
        elif statement is None:
            st.warning("Give me a statement first.")
            db2_sql = ""
        else:
            attempt = translate.translate(statement.sql, statement.dialect)
            db2_sql = attempt.db2_sql or ""
            if attempt.ok and not db.compile_check(owner_conn, db2_sql).ok:
                outcome = RepairLoop(owner_conn).run(
                    source_sql=statement.sql, db2_sql=db2_sql, dialect=statement.dialect
                )
                if outcome.repaired:
                    db2_sql = outcome.final_sql
                    st.caption("repaired first, then proved")

        if statement is not None and db2_sql:
            sources, target = _prover(owner_conn)
            source = sources.get(statement.dialect)
            if source is None:
                st.warning(
                    f"No {statement.dialect} source engine is reachable, so "
                    "meaning cannot be checked. PortProof will not substitute a "
                    "different engine: its agreement with Db2 would be evidence "
                    "about the wrong dialect. See `.env.example` for MySQL."
                )
                st.stop()
            with st.spinner(f"running both statements on {len(VARIANTS)} datasets..."):
                verdict = prove_semantics(
                    source_sql=statement.sql,
                    db2_sql=db2_sql,
                    source=source,
                    target=target,
                    dialect=statement.dialect,
                )

            colour = VERDICT_COLOUR.get(verdict.outcome, DIM)
            strength_colour = STRENGTH_COLOUR.get(verdict.strength, DIM)
            st.markdown(
                f"<h3 style='color:{colour};margin-bottom:0'>"
                f"{VERDICT_LABEL.get(verdict.outcome, verdict.outcome)}"
                f"<span style='color:{strength_colour};font-size:0.6em;"
                f"font-weight:600;margin-left:.6em'>evidence "
                f"{verdict.strength}</span></h3>"
                f"<p style='color:{DIM}'>{html.escape(verdict.headline)}</p>",
                unsafe_allow_html=True,
            )
            for note in verdict.notes:
                st.caption(f"· {note}")

            e1, e2, e3, e4 = st.columns(4)
            e1.metric("instances run", verdict.instances_checked)
            e2.metric("agreed on rows", verdict.substantive_instances)
            e3.metric("rows compared", verdict.rows_compared)
            e4.metric("distinct inputs", verdict.distinct_inputs)

            if verdict.outcome == "UNSTABLE" or verdict.order_unstable:
                st.warning(
                    "The two engines returned different rows, and so did the "
                    "**source engine against itself**, when the same rows were "
                    "inserted in the opposite order. This statement's `ORDER BY` "
                    "has ties, so no engine owes you this order and Db2 is not "
                    "at fault. Add a tiebreaker (for example `, id`) and prove "
                    "it again."
                )
            if verdict.outcome == "VACUOUS":
                st.warning(
                    "Both engines returned **no rows on every dataset**. They "
                    "agreed, and the agreement is empty: `[] == []` is true for "
                    "any two statements that happen to select nothing. PortProof "
                    "used to count this as a proof of equivalence. It is not one."
                )

            left, right = st.columns(2)
            with left:
                st.markdown(f"**source** · `{statement.dialect}` on `{verdict.source_engine}`")
                _code(statement.sql)
            with right:
                st.markdown("**Db2**")
                _code(db2_sql)

            st.markdown("#### Every instance that was run")
            st.dataframe(
                [
                    {
                        "dataset": r.variant,
                        "what it stresses": r.targets,
                        "agreed": "yes" if r.agreed else ("--" if r.inconclusive else "NO"),
                        "evidence": "none (both empty)" if r.vacuous else (
                            f"{r.rows_compared} rows" if r.agreed else r.difference or "--"
                        ),
                        "source rows": len(r.source_rows),
                        "db2 rows": len(r.db2_rows),
                        "note": (r.source_error or r.db2_error or ""),
                    }
                    for r in verdict.instances
                ],
                width="stretch",
                hide_index=True,
                # Every dataset on screen at once: the table is the evidence.
                height=36 * (len(verdict.instances) + 1) + 3,
            )

            if verdict.witness is not None:
                st.markdown("#### The counterexample")
                st.error(
                    f"On dataset `{verdict.witness.variant}` "
                    f"({verdict.witness.targets}) the two engines disagree. "
                    "Both statements compile. One of them is wrong."
                )
                wl, wr = st.columns(2)
                with wl:
                    _rows_table(
                        verdict.witness.source_rows, f"{verdict.source_engine} returned"
                    )
                with wr:
                    _rows_table(verdict.witness.db2_rows, "Db2 returned")

                held = next((v for v in VARIANTS
                             if v.fingerprint == verdict.witness.fingerprint), None)
                if held is not None:
                    with st.spinner("shrinking the dataset to the rows that matter..."):
                        try:
                            smallest = minimise(
                                source_sql=statement.sql, db2_sql=db2_sql, source=source,
                                target=target, witness=held, dialect=statement.dialect,
                            )
                        except Exception as exc:  # the shrink never changes a verdict
                            smallest = None
                            st.caption(f"could not shrink the counterexample: {str(exc)[:120]}")
                    if smallest is not None:
                        _show_minimal(smallest)

            db.execute(owner_conn, f"SET CURRENT SCHEMA {FIXTURE_SCHEMA}")
            cost = costgate.estimate(owner_conn, db2_sql)
            if cost is not None:
                st.caption(
                    f"Db2's optimizer estimates the Db2 statement at **{cost:,.1f} timerons** "
                    "(`EXPLAIN PLAN`, compiled and not executed)."
                )


# --------------------------------------------------------------------------
# tab 3 -- a whole workload, gated
# --------------------------------------------------------------------------
GATE_POLICY = {
    "different": "hold if anything is PROVEN DIFFERENT or does not compile",
    "unproven": "hold unless everything is PROVEN EQUIVALENT",
    "none": "report only",
}


def _run_workload(kind: str, dialect: str, limit: int, tables: tuple[str, ...],
                  top: int, uploaded: str, fail_on: str) -> dict:
    """One migration run, on connections of its own, closed when it ends."""
    from src.main import held_by, verdicts
    from src.pipeline import Pipeline

    cfg = llm_config()
    run_app = db.connect(runtime_config(), role="app")
    db.execute(run_app, "SET CURRENT SCHEMA PORTPROOF")
    run_owner = db.connect(setup_config(), role="setup")
    METER.reset()
    started = time.time()
    taken = None
    try:
        try:
            memory = FixMemory(run_app, embeddings=_embeddings())
            remembered = f"{memory.count()} verified repairs in Db2's fix memory"
        except Exception as exc:
            memory = None
            remembered = f"fix memory unavailable ({str(exc)[:80]})"
        agent = DatasetAgent(store=DatasetStore(run_app), model=build_model(cfg), builtin=VARIANTS)
        pipeline = Pipeline(app_conn=run_app, owner_conn=run_owner, memory=memory,
                            dataset_agent=agent, variants=VARIANTS)
        try:
            if kind == "corpus":
                statements = statements_for(dialect)
            elif kind == "samples":
                samples.discover({dialect: pipeline.sources[dialect]}, agent)
                statements = samples.statements((dialect,))
            else:
                engine = pipeline.sources.get(dialect)
                if engine is None:
                    raise ValueError(f"no {dialect} source engine is reachable")
                if kind == "captured":
                    taken = capture.from_engine(engine, dialect, tables, top=top)
                else:
                    taken = capture.from_text(uploaded, dialect, tables, origin="the uploaded file")
                statements, _, _ = capture.workload(engine, agent, taken, tables)
            report = pipeline.run(statements=statements[: max(1, limit)])
        finally:
            pipeline.close()
    finally:
        for conn in (run_app, run_owner):
            try:
                import ibm_db

                ibm_db.close(conn)
            except Exception:  # pragma: no cover
                pass
    return {
        "report": report,
        "verdicts": verdicts(report),
        "held": held_by(report, fail_on),
        "fail_on": fail_on,
        "captured": taken.summary() if taken is not None else None,
        "remembered": remembered,
        "seconds": time.time() - started,
        "model_calls": len(METER.calls),
    }


def _repaired_by(r) -> str:
    parts = []
    if r.repair and r.repaired:
        parts.append(f"compile: {r.repair.fixed_by}")
    if r.semantic_repair and r.semantic_repair.repaired:
        parts.append(f"meaning: {r.semantic_repair.rule}")
    return ", ".join(parts)


with tab_workload:
    st.subheader("A migration is a workload, not a statement")
    st.markdown(
        "Prove every statement an application sends, then hold the result against a "
        "policy, the way a CI job would. The statements can come from the corpus, from "
        "the record the source engine keeps of what it ran, or from a `.sql` file."
    )

    w1, w2 = st.columns([3, 2])
    with w1:
        kind = st.radio(
            "workload",
            ["corpus", "samples", "captured", "file"],
            format_func={
                "corpus": "the corpus",
                "samples": "a discovered schema (hr, bank)",
                "captured": "captured from the source engine",
                "file": "an uploaded .sql file",
            }.get,
            horizontal=True,
            key="wl_kind",
        )
    with w2:
        wl_dialect = st.selectbox(
            "source dialect",
            [d for d in DIALECTS if not (kind == "captured" and d == "sqlite")],
            key="wl_dialect",
        )

    tables: tuple[str, ...] = ()
    uploaded = ""
    top = 50
    if kind in ("captured", "file"):
        raw = st.text_input(
            "tables being migrated",
            value="customers, orders, order_items, events",
            key="wl_tables",
            help="Only statements that read nothing but these tables are proved.",
        )
        tables = tuple(t.strip() for t in raw.split(",") if t.strip())
    if kind == "captured":
        top = st.slider("most executed statements to take", 5, 200, 50, key="wl_top")
        st.caption(
            {
                "mysql": "Read from `performance_schema.events_statements_summary_by_digest`.",
                "tsql": "Read from `sys.dm_exec_query_stats` and `sys.dm_exec_sql_text`.",
                "postgres": "Read from `pg_stat_statements`. PostgreSQL keeps `$1` in place of "
                "literals, so statements that had literals are counted and set aside.",
            }.get(wl_dialect, "")
        )
    if kind == "file":
        upload = st.file_uploader("SQL file, one statement per `;`", type=["sql", "txt"],
                                  key="wl_upload")
        if upload is not None:
            uploaded = upload.getvalue().decode("utf-8", errors="replace")

    g1, g2 = st.columns([3, 2])
    with g1:
        fail_on = st.radio(
            "gate", list(GATE_POLICY), format_func=GATE_POLICY.get, key="wl_gate",
        )
    with g2:
        limit = st.number_input("at most this many statements", 1, 200, 12, key="wl_limit")

    if st.button("Migrate and prove", type="primary", key="go_workload"):
        if kind == "file" and not uploaded.strip():
            st.warning("Upload a .sql file first.")
        else:
            with st.spinner("translating, compiling, repairing and proving every statement..."):
                try:
                    st.session_state["workload_run"] = _run_workload(
                        kind, wl_dialect, int(limit), tables, int(top), uploaded, fail_on
                    )
                except Exception as exc:
                    st.session_state.pop("workload_run", None)
                    st.error(f"the run did not complete: {str(exc)[:300]}")

    run = st.session_state.get("workload_run")
    if run is not None:
        report = run["report"]
        st.caption(f"repairs: {run['remembered']}, consulted before the rules and the model")
        if run["captured"]:
            st.caption(f"captured: {run['captured']}")
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("statements", report.total)
        m2.metric("silent failures", report.silent_failures)
        m3.metric("proven equivalent", report.proven_equivalent)
        m4.metric("proven different", report.proven_different)
        m5.metric("model calls", run["model_calls"])
        m6.metric("wall time", f"{run['seconds']:.0f}s")

        if run["fail_on"] == "none":
            st.info("Gate: report only. A CI job would exit 0.")
        elif run["held"]:
            st.error(
                f"**Gate holds the migration.** {len(run['held'])} statement(s) fail the "
                f"policy \"{GATE_POLICY[run['fail_on']]}\". A CI job would exit 2."
            )
        else:
            st.success(f"**Gate passes.** Policy: {GATE_POLICY[run['fail_on']]}. Exit 0.")

        st.dataframe(
            [
                {
                    "case": r.case_name,
                    "status": r.status,
                    "repaired by": _repaired_by(r),
                    "evidence": r.semantic.strength if r.semantic else "",
                    "datasets": r.datasets_used,
                    "est. cost before → after": (
                        f"{r.cost_before:,.1f} → {r.cost_after:,.1f}"
                        if r.cost_before is not None and r.cost_after is not None else ""
                    ),
                    "smallest counterexample": (
                        f"{r.minimal.rows_after} of {r.minimal.rows_before} rows" if r.minimal else ""
                    ),
                }
                for r in report.results
            ],
            width="stretch",
            hide_index=True,
            height=36 * (len(report.results) + 1) + 3,
        )

        slower = [r for r in report.results if (r.cost_ratio or 0) >= costgate.SLOWER_RATIO]
        for r in slower:
            st.warning(
                f"`{r.case_name}`: the repair is proved correct and Db2 estimates it at "
                f"{r.cost_ratio:.1f}x the cost ({r.cost_before:,.1f} → {r.cost_after:,.1f} "
                "timerons). Correct and slower is a decision for a person."
            )

        for r in report.results:
            if r.status == "PROVEN_DIFFERENT" and r.minimal is not None:
                with st.expander(f"{r.case_name}: the smallest input that still disagrees"):
                    _code(r.db2_sql or "")
                    _show_minimal(r.minimal)

        import json

        st.download_button(
            "Download the verdicts as JSON",
            json.dumps(run["verdicts"], indent=2, default=str),
            file_name="portproof-verdicts.json",
            mime="application/json",
            key="wl_download",
        )
        st.caption(
            "The same file `python -m src.main --report-json` writes, and the same gate as "
            f"`--fail-on {run['fail_on']}`."
        )


# --------------------------------------------------------------------------
# tab 4 -- the Db2 side
# --------------------------------------------------------------------------
with tab_ledger:
    st.subheader("What Db2 is doing that an app layer could not")

    st.markdown("#### The verdict ledger")
    st.caption(
        "Written only through SQL PL procedures by an identity that holds no "
        "INSERT. Each certificate is a SHA-256 computed **in the engine** by "
        "`HASH(..., 2)` over the verdict's own fields. The application never "
        "gets to choose it."
    )
    rows = db.fetch_all(
        app_conn,
        "SELECT s.CASE_NAME, s.SRC_DIALECT, s.STATUS, s.ATTEMPTS, v.KIND, "
        "       v.OUTCOME, v.INSTANCES, SUBSTR(v.CERT_SHA, 1, 20) "
        "  FROM PORTPROOF.STATEMENT s "
        "  LEFT JOIN PORTPROOF.VERDICT v ON v.STMT_ID = s.STMT_ID "
        " ORDER BY s.CASE_NAME, v.KIND",
    )
    st.dataframe(
        [
            {
                "case": str(r[0]).strip(),
                "dialect": str(r[1]).strip(),
                "status": str(r[2]).strip(),
                "attempts": r[3],
                "kind": str(r[4] or "").strip(),
                "outcome": str(r[5] or "").strip(),
                "n": r[6],
                "certificate (truncated)": str(r[7] or "").strip(),
            }
            for r in rows
        ],
        width="stretch",
        hide_index=True,
        height=320,
    )

    g1, g2 = st.columns(2)

    with g1:
        st.markdown("#### Failure rollup, maintained by the engine")
        st.caption(
            "A materialised query table with `REFRESH IMMEDIATE`. No application "
            "code keeps this current. Db2 does, inside the same transaction."
        )
        st.dataframe(
            [
                {"dialect": str(d).strip(), "SQLCODE": c, "statements": n}
                for d, c, n in db.fetch_all(
                    app_conn,
                    "SELECT SRC_DIALECT, LAST_SQLCODE, N "
                    "  FROM PORTPROOF.MQT_FAILURE_BY_CODE ORDER BY N DESC",
                )
            ],
            width="stretch",
            hide_index=True,
        )

    with g2:
        st.markdown("#### Time travel")
        st.caption(
            "`PORTPROOF.STATEMENT` is a system-versioned temporal table, so the "
            "ledger can be queried as it stood at any past instant."
        )
        seconds = st.slider("seconds ago", 1, 600, 60, key="asof")
        row = db.fetch_one(
            app_conn,
            "SELECT COUNT(*) FROM PORTPROOF.STATEMENT "
            "FOR SYSTEM_TIME AS OF CURRENT TIMESTAMP - ? SECONDS",
            (int(seconds),),
        )
        now = db.fetch_one(app_conn, "SELECT COUNT(*) FROM PORTPROOF.STATEMENT")
        hist = db.fetch_one(app_conn, "SELECT COUNT(*) FROM PORTPROOF.STATEMENT_HIST")
        t1, t2, t3 = st.columns(3)
        t1.metric("now", now[0] if now else 0)
        t2.metric(f"{seconds}s ago", row[0] if row else 0)
        t3.metric("rows Db2 preserved", hist[0] if hist else 0)

    st.markdown("#### The fix memory: Db2 as the vector store")
    st.caption(
        "`VECTOR(384, FLOAT32)` columns and `VECTOR_DISTANCE(..., COSINE)`. The "
        "recall below is **one statement** in which the semantic ranking and the "
        "relational filter are evaluated together, in the engine, which is the part that "
        "would not survive a bolt-on vector database."
    )
    try:
        memory = _memory(app_conn)
        st.metric("verified repairs stored", memory.count())
        probe = st.text_input(
            "recall a fix for a failure",
            value="SQLCODE=-440 no authorized routine named GROUP_CONCAT",
            key="recall_probe",
        )
        dialect = st.selectbox("filter: source dialect", list(DIALECTS), key="recall_dialect")
        if st.button("Recall from Db2", key="go_recall"):
            # Kept in session state so the results survive the rerun caused by
            # any other widget on this tab.
            st.session_state["recall_hits"] = memory.recall_sql(
                bad_sql=probe, sqlcode=None, error_text=probe, dialect=dialect, k=3
            )
        hits = st.session_state.get("recall_hits")
        if hits is not None:
            if not hits:
                st.info("nothing stored for that dialect yet. Run `python -m src.main` first")
            for fix in hits:
                dist = f"{fix.distance:.5f}" if fix.distance is not None else "n/a"
                st.markdown(f"**cosine distance `{dist}`** · SQLCODE `{fix.sqlcode}`")
                _code(fix.fixed_sql)
        with st.expander("the SQL behind that recall"):
            _code(
                """SELECT JSON_VALUE(METADATA, '$.fixed_sql' RETURNING VARCHAR(4000)),
       VECTOR_DISTANCE(EMBEDDING, VECTOR(?, 384, FLOAT32), COSINE) AS DIST
  FROM FIX_MEMORY
 WHERE JSON_VALUE(METADATA, '$.dialect' RETURNING VARCHAR(16)) = ?
 ORDER BY DIST
 FETCH FIRST 3 ROWS ONLY"""
            )
    except Exception as exc:
        st.info(f"fix memory unavailable: {str(exc)[:160]}")

    st.markdown("#### Physical design, measured rather than guessed")
    if st.button("Measure on Db2", key="go_physical"):
        with st.spinner("building the two tables and asking Db2..."):
            comp = physical.measure_compression(owner_conn)
            col = physical.check_columnar(owner_conn)
            hot = physical.workload_hotspots(owner_conn)
        st.success(comp.headline)
        st.success(col.headline)
        if hot:
            st.caption("hottest statements in the package cache (`MON_GET_PKG_CACHE_STMT`)")
            st.dataframe(
                [
                    {"executions": n, "cpu (us)": round(cpu), "statement": text[:110]}
                    for text, n, cpu in hot
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("package cache: nothing monitored is visible to this identity")


# --------------------------------------------------------------------------
# tab 5 -- the model tier and the agent interface
# --------------------------------------------------------------------------
with tab_model:
    st.subheader("The model is the last tier, and Db2 keeps the bill")
    st.markdown(
        "A repair is proposed by the cheapest tier that has one: Db2's fix memory, then "
        "measured rules, then a language model. Every model call is written to "
        "`PORTPROOF.LLM_CALL` through a procedure, by an identity that cannot edit the table."
    )

    registered = db.fetch_one(
        owner_conn,
        "SELECT COUNT(*) FROM SYSCAT.PROCEDURES WHERE PROCSCHEMA = 'PORTPROOF' "
        "AND PROCNAME = 'ASK_MODEL'",
    )
    k1, k2, k3 = st.columns(3)
    k1.metric(
        "who calls the model",
        "Db2" if cfg.in_db2 else "this process",
        "TEXT_GENERATION in ASK_MODEL" if cfg.in_db2 else "HTTP, key in the environment",
        delta_color="off",
    )
    k2.metric("model", cfg.model or "none", cfg.provider, delta_color="off")
    k3.metric(
        "in-engine model",
        "registered" if registered and int(registered[0]) else "not registered",
        "python -m src.setup_model",
        delta_color="off",
    )

    st.markdown("#### What the model has cost, read from Db2")
    spend = db.fetch_all(
        app_conn,
        "SELECT STAGE, TRANSPORT, COUNT(*), SUM(PROMPT_TOKENS), SUM(COMPLETION_TOKENS), "
        "       AVG(LATENCY_MS), MAX(ESTIMATED) "
        "  FROM PORTPROOF.LLM_CALL GROUP BY STAGE, TRANSPORT ORDER BY STAGE, TRANSPORT",
    )
    if spend:
        st.dataframe(
            [
                {
                    "stage": str(stage).strip(),
                    "called by": "Db2" if str(transport).strip() == "DB2" else "application",
                    "calls": int(calls),
                    "tokens in": int(tin or 0),
                    "tokens out": int(tout or 0),
                    "mean latency (ms)": int(latency or 0),
                    "token counts": "estimated" if estimated else "provider's own",
                }
                for stage, transport, calls, tin, tout, latency, estimated in spend
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("No model call has been made yet.")
    dead = db.fetch_one(app_conn, "SELECT COUNT(*) FROM PORTPROOF.MODEL_DEAD_END")
    st.caption(
        f"{int(dead[0]) if dead else 0} question(s) the model was asked and failed are recorded "
        "in `PORTPROOF.MODEL_DEAD_END`, so they are not paid for again."
    )

    with st.expander("how Db2 makes the call", expanded=cfg.in_db2):
        st.markdown(
            "With `LLM_TRANSPORT=db2` the application holds no key. It calls one procedure; "
            "the procedure checks the budget against its own ledger, calls the model, and "
            "writes the ledger row in the same unit of work. The runtime identity has "
            "`EXECUTE` on the procedure and nothing on the model, so calling "
            "`TEXT_GENERATION` directly fails with `SQL0551N`."
        )
        _code(
            """CALL PORTPROOF.ASK_MODEL(stage, case_name, prompt, run_started, budget, ?)

-- inside the procedure
IF (SELECT COUNT(*) FROM PORTPROOF.LLM_CALL WHERE CREATED_AT >= P_SINCE) >= P_BUDGET THEN
  SIGNAL SQLSTATE '75002' SET MESSAGE_TEXT = 'model call budget is spent';
END IF;
SET P_REPLY = TEXT_GENERATION(P_PROMPT USING PORTPROOF.PP_MODEL);
INSERT INTO PORTPROOF.LLM_CALL (...) VALUES (..., 'DB2', 1);"""
        )

    st.markdown("#### Tools for an agent (MCP)")
    st.markdown(
        "`python -m src.mcp_server` gives an agent that writes or converts SQL four questions "
        "it can put to Db2. All four are read only. What an agent sends passes the same "
        "single-query guard as a model's own output before it reaches a connection."
    )
    from src import mcp_server

    st.dataframe(
        [{"tool": tool.__name__, "what it answers": (tool.__doc__ or "").strip().splitlines()[0]}
         for tool in mcp_server.TOOLS],
        width="stretch",
        hide_index=True,
    )
    _code(
        """{ "mcpServers": { "portproof": {
    "command": "python", "args": ["-m", "src.mcp_server"],
    "cwd": "<path to>/portproof" } } }""",
        language="json",
    )

    st.markdown("##### Ask a tool what an agent would")
    tool_name = st.selectbox("tool", ["check_compiles", "estimate_cost"], key="mcp_tool")
    tool_sql = st.text_area(
        "Db2 SQL",
        value="SELECT c.name, COUNT(*) FROM customers c JOIN orders o ON o.customer_id = c.id "
        "GROUP BY c.name",
        height=90,
        key="mcp_sql",
    )
    if st.button("Call the tool", key="go_mcp"):
        st.json(getattr(mcp_server, tool_name)(tool_sql))
