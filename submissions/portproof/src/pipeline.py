"""The end-to-end migration pipeline.

For each statement:

1. **translate** with IBM's ``db2-sqlglot-dialect``
2. **prove it compiles** -- Db2 ``PREPARE``, server-side
3. **repair** if it does not, in a bounded LangGraph loop grounded in the Db2
   vector fix-memory, re-verifying with Db2 after every attempt
4. **prove meaning** by differential execution over adversarial datasets
5. **record** the outcome and a Db2-computed SHA-256 certificate through SQL PL
6. **learn** -- a repair that Db2 accepted *and* that proved equivalent is
   embedded into the fix-memory for next time

Two Db2 identities are used on purpose. Ledger writes go through the
least-privilege runtime user, which can only ``CALL`` the procedures. Creating
and loading adversarial fixtures is a privileged operation and uses the owner.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Sequence

from . import db, physical, translate
from .config import llm_config, setup_config
from .corpus import BASE, FIXTURE_TABLES, VARIANTS, Statement, Variant, statements_for
from .counterexample import (
    Db2Target,
    SemanticVerdict,
    SourceEngine,
    activate,
    available_sources,
    ensure_fixture_schema,
    go_home,
    prove_semantics,
)
from .datasets import DatasetAgent, QueryFeatures
from .llm import METER
from .federation import Corroboration, corroborate
from .fixmemory import FixMemory
from .repair import RepairLoop, RepairOutcome
from .semantic_repair import SemanticRepairLoop, SemanticRepairOutcome


@dataclass
class StatementResult:
    statement: Statement
    status: str
    db2_sql: str | None
    translator_raised: bool
    silent_failure: bool
    first_sqlcode: int | None = None
    first_error: str = ""
    repair: RepairOutcome | None = None
    semantic: SemanticVerdict | None = None
    #: The second repair loop: the one that runs when the SQL compiled and
    #: still meant something else.
    semantic_repair: SemanticRepairOutcome | None = None
    #: The verdict that *found* the divergence, kept after a semantic repair
    #: replaces `semantic` with the proof that the rewrite agrees. Without it
    #: a repaired statement would be indistinguishable from one that was never
    #: wrong, which is the most useful fact about it.
    original_semantic: SemanticVerdict | None = None
    #: Db2's own opinion, through federation, on whether the two engines were
    #: even looking at the same rows. Only asked for when a divergence survived
    #: repair, because that is the only time the answer changes anything.
    federation: Corroboration | None = None
    stmt_id: int | None = None
    compile_cert: str | None = None
    semantic_cert: str | None = None
    learned: bool = False
    #: How many datasets the proof ran on, and whether the dataset agent had to
    #: fetch more because the first proof was vacuous or weak.
    datasets_used: int = 0
    escalated: bool = False
    rescued: bool = False
    model_calls: int = 0

    @property
    def case_name(self) -> str:
        return self.statement.case_name

    @property
    def repaired(self) -> bool:
        return bool(self.repair and self.repair.repaired)

    @property
    def semantically_repaired(self) -> bool:
        return bool(self.semantic_repair and self.semantic_repair.repaired)


@dataclass
class MigrationReport:
    results: list[StatementResult] = field(default_factory=list)
    source_engine: str = ""
    #: How many adversarial datasets were *available*. Not a claim about how
    #: many any given statement was actually checked on -- that is per
    #: statement, and it is :attr:`instances_proved` below. Reporting
    #: ``len(VARIANTS)`` as the evidence for every verdict was a claim the run
    #: had not earned.
    variants: int = 0
    seconds: float = 0.0
    #: Dataset loads the engines actually performed, all engines together.
    loads: int = 0
    agent_lines: list[str] = field(default_factory=list)
    repair_policy: str = ""

    # -- who fixed what --------------------------------------------------
    def fixed_by(self, tier: str) -> int:
        """Compile repairs Db2 accepted from one tier: memory | rules | model."""
        return sum(1 for r in self.results if r.repair and r.repair.fixed_by == tier)

    def semantic_fixed_by(self, tier: str) -> int:
        return sum(
            1 for r in self.results
            if r.semantic_repair and r.semantic_repair.repaired and r.semantic_repair.tier == tier
        )

    @property
    def model_calls(self) -> int:
        return sum(r.model_calls for r in self.results)

    def by_dialect(self) -> list[str]:
        lines = []
        dialects = list(dict.fromkeys(r.statement.dialect for r in self.results))
        for dialect in dialects:
            rows = [r for r in self.results if r.statement.dialect == dialect]
            lines.append(
                f"  {dialect:9} {len(rows):3} statements | "
                f"silent compile failures {sum(1 for r in rows if r.silent_failure):2} | "
                f"wrong rows {sum(1 for r in rows if r.status == 'PROVEN_DIFFERENT' or r.semantically_repaired):2} "
                f"(repaired {sum(1 for r in rows if r.semantically_repaired)}) | "
                f"proven equivalent {sum(1 for r in rows if r.status == 'PROVEN_EQUIVALENT'):2}"
            )
        return lines

    # -- the numbers the README quotes -----------------------------------
    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def translator_errors(self) -> int:
        return sum(1 for r in self.results if r.translator_raised)

    @property
    def silent_failures(self) -> int:
        """Translated without complaint, then rejected by Db2. The headline."""
        return sum(1 for r in self.results if r.silent_failure)

    @property
    def repaired(self) -> int:
        return sum(1 for r in self.results if r.repaired)

    @property
    def unrepaired(self) -> int:
        return sum(1 for r in self.results if r.status in ("COMPILE_FAIL", "TRANSLATE_FAIL"))

    @property
    def proven_equivalent(self) -> int:
        return sum(1 for r in self.results if r.status == "PROVEN_EQUIVALENT")

    @property
    def proven_different(self) -> int:
        return sum(1 for r in self.results if r.status == "PROVEN_DIFFERENT")

    @property
    def inconclusive(self) -> int:
        return sum(1 for r in self.results if r.status == "COMPILES")

    @property
    def vacuous(self) -> int:
        """Agreed on nothing: both engines returned no rows every time."""
        return sum(1 for r in self.results if r.status == "VACUOUS")

    @property
    def unstable(self) -> int:
        """Statements whose own ORDER BY does not determine their result."""
        return sum(1 for r in self.results if r.status == "UNSTABLE")

    @property
    def federation_note(self) -> str:
        """What federation added to the divergences this run found, if anything."""
        asked = [r.federation for r in self.results if r.federation is not None]
        if not asked:
            return ""
        if any(f.undermines_proof for f in asked):
            return "Db2 federation says the two engines did not hold the same rows"
        if any(f.strengthens_proof for f in asked):
            return "Db2 federation confirmed both engines held identical rows"
        return asked[0].note or "federation was not available"

    @property
    def semantic_divergences(self) -> int:
        """Statements that compiled on Db2 and returned the wrong rows."""
        return sum(
            1
            for r in self.results
            if r.status == "PROVEN_DIFFERENT" or r.semantically_repaired
        )

    @property
    def semantically_repaired(self) -> int:
        """...of which the meaning was fixed and re-proved."""
        return sum(1 for r in self.results if r.semantically_repaired)

    @property
    def instances_proved(self) -> int:
        """Adversarial instances that actually contributed to an EQUIVALENT."""
        return sum(
            r.semantic.substantive_instances
            for r in self.results
            if r.status == "PROVEN_EQUIVALENT" and r.semantic is not None
        )

    @property
    def strong_proofs(self) -> int:
        return sum(
            1
            for r in self.results
            if r.status == "PROVEN_EQUIVALENT"
            and r.semantic is not None
            and r.semantic.strength == "STRONG"
        )

    def summary_lines(self) -> list[str]:
        equivalent = self.proven_equivalent
        mean = f"{self.instances_proved / equivalent:.1f}" if equivalent else "0"
        return [
            f"statements migrated      : {self.total}",
            f"translator reported errors: {self.translator_errors}",
            f"SILENT failures (clean translate, rejected by Db2): {self.silent_failures}",
            f"repaired and re-verified : {self.repaired} "
            f"(by fix memory {self.fixed_by('memory')}, by rules {self.fixed_by('rules')}, "
            f"by the model {self.fixed_by('model')})",
            f"still failing to compile : {self.unrepaired}",
            f"proven equivalent        : {equivalent} "
            f"(mean {mean} of {self.variants} adversarial datasets returned rows; "
            f"source engines: {self.source_engine})",
            f"  of those, evidence STRONG: {self.strong_proofs}",
            f"semantic divergences found: {self.semantic_divergences} "
            f"(compiled on Db2, wrong rows)",
            f"  of those, repaired and re-proved: {self.semantically_repaired} "
            f"(by fix memory {self.semantic_fixed_by('memory')}, "
            f"by rules {self.semantic_fixed_by('rules')}, by the model "
            f"{self.semantic_fixed_by('model')})",
            f"PROVEN DIFFERENT         : {self.proven_different}",
            f"order not determined by the SQL: {self.unstable}",
            f"vacuous (agreed on nothing): {self.vacuous}",
            f"inconclusive             : {self.inconclusive}",
        ] + (
            [f"divergence cross-checked : {self.federation_note}"]
            if self.federation_note
            else []
        ) + [
            f"model calls, all stages  : {len(METER.calls)} "
            f"({METER.total_tokens} tokens)",
            f"wall time                : {self.seconds:.1f}s for {self.total} statements "
            f"({self.loads} dataset loads across all engines)",
        ]


class Pipeline:
    def __init__(
        self,
        *,
        app_conn,
        owner_conn,
        source: SourceEngine | None = None,
        sources: dict[str, SourceEngine] | None = None,
        memory: FixMemory | None = None,
        repair_loop: RepairLoop | None = None,
        learn: bool = True,
        semantic_repair: bool = True,
        dataset_agent: DatasetAgent | None = None,
        variants: Sequence[Variant] | None = None,
    ):
        self.app_conn = app_conn
        self.owner_conn = owner_conn
        ensure_fixture_schema(owner_conn)
        self.target = Db2Target(owner_conn)
        # One engine per source dialect. A statement is judged by the engine for
        # *its own* dialect or by nothing at all -- see the dialect guard in
        # prove_semantics, and the comment on DuckDbSource explaining the false
        # EQUIVALENT that the one-engine-for-everything arrangement produced.
        if sources is not None:
            self.sources = dict(sources)
        elif source is not None:
            self.sources = {getattr(source, "dialect", "postgres"): source}
        else:
            self.sources = available_sources()
        self.memory = memory
        self.repair_loop = repair_loop or RepairLoop(owner_conn, memory=memory)
        self.learn = learn
        self.semantic_repair = semantic_repair
        #: Chooses and builds the datasets per statement. Without one, every
        #: statement is proved on ``variants`` (default: all the hand-built ones).
        self.dataset_agent = dataset_agent
        self.variants = list(variants) if variants is not None else list(VARIANTS)
        self._federation: dict[str, Corroboration] = {}

    def _flush_model_calls(self) -> None:
        """Write this statement's model calls to the Db2 ledger."""
        for call in METER.unflushed():
            try:
                db.call_proc(
                    self.app_conn,
                    "PORTPROOF.RECORD_LLM_CALL",
                    (call.stage, call.model[:80], call.case_name[:80] or None,
                     call.prompt_tokens, call.completion_tokens, call.latency_ms, int(call.ok)),
                )
            except db.Db2Error:  # the cost ledger is optional on an old schema
                return

    def _corroborate(self, dialect: str) -> Corroboration:
        """Db2's federated opinion on the inputs, asked once per dialect.

        The same dataset is loaded into both engines first. That is not a
        formality. By the time a statement has been proved, the order stability
        probe has reloaded the *witness* dataset into the source engine while
        Db2 still holds the last one the variant loop used, so comparing the two
        at that moment asks about two different points in time and reliably
        reports a difference that means nothing. Reloading is safe here because
        the proof for this statement has already finished, and the next
        statement's proof reloads both engines for every variant anyway.

        Cached per dialect: every statement reads the same fixture tables, so
        the answer cannot differ between them, and the comparison crosses the
        network twice for each table.
        """
        if dialect in self._federation:
            return self._federation[dialect]

        result = Corroboration("UNAVAILABLE", note="federation was not reachable")
        probe = None
        try:
            engine = self.sources.get(dialect)
            if engine is not None:
                engine.load(BASE)
                self.target.load(BASE)
            # A connection of its own, closed straight afterwards. Reading a
            # nickname opens a unit of work that spans the remote data source,
            # and until it is committed, DDL on that same connection is
            # refused. Sharing the owner connection meant the next statement's
            # `DROP TABLE` silently failed and its `CREATE TABLE` came back
            # SQL0601N, which looked like a prover bug and was not one.
            probe = db.connect(setup_config(), role="setup")
            result = corroborate(probe, FIXTURE_TABLES, dialect)
        except Exception as exc:  # federation is optional, never fatal
            result = Corroboration("UNAVAILABLE", note=str(exc)[:160])
        finally:
            if probe is not None:
                db.close(probe)
        self._federation[dialect] = result
        return result

    @property
    def source_engines(self) -> str:
        """Which engines the verdicts in this run were measured against."""
        if not self.sources:
            return "none"
        return ", ".join(f"{d}={s.name}" for d, s in sorted(self.sources.items()))

    # -- ledger ----------------------------------------------------------
    def _record_translation(self, result: StatementResult) -> None:
        meta = json.dumps(
            {
                "translator_raised": result.translator_raised,
                "silent_failure": result.silent_failure,
                "attempts": result.repair.attempt_count if result.repair else 0,
                # Who produced the accepted repair: memory | rules | model.
                "fixed_by": result.repair.fixed_by if result.repair else "",
                "tiers": [a.tier for a in result.repair.attempts] if result.repair else [],
                "datasets": result.datasets_used,
                "dataset_escalated": result.escalated,
                "rules": sorted(
                    {r for a in (result.repair.attempts if result.repair else []) for r in a.rules_fired}
                ),
                "semantic_strength": (
                    result.semantic.strength if result.semantic else None
                ),
                "semantic_repair": (
                    {
                        "rule": result.semantic_repair.rule,
                        "tier": result.semantic_repair.tier,
                        "repaired": result.semantic_repair.repaired,
                        "tried": [a.rule for a in result.semantic_repair.attempts],
                    }
                    if result.semantic_repair
                    else None
                ),
            }
        )[:2000]
        out = db.call_proc(
            self.app_conn,
            "PORTPROOF.RECORD_TRANSLATION",
            (
                result.case_name,
                result.statement.dialect,
                result.statement.sql[:4000],
                (result.db2_sql or "")[:4000] or None,
                result.status,
                result.first_sqlcode,
                (result.first_error or "")[:1200] or None,
                meta,
                # The real number of times Db2 was asked about this statement:
                # the compile-repair attempts plus any semantic-repair ones.
                (result.repair.attempt_count if result.repair else 1)
                + (result.semantic_repair.attempt_count if result.semantic_repair else 0),
                0,
            ),
        )
        result.stmt_id = int(out[-1])

    def _record_verdict(
        self, result: StatementResult, kind: str, outcome: str, instances: int, detail: dict
    ) -> str | None:
        if result.stmt_id is None:
            return None
        out = db.call_proc(
            self.app_conn,
            "PORTPROOF.RECORD_VERDICT",
            (result.stmt_id, kind, outcome, int(instances), json.dumps(detail)[:8000], ""),
        )
        return str(out[-1])

    # -- one statement ---------------------------------------------------
    def run_statement(self, statement: Statement, *, prove_meaning: bool = True) -> StatementResult:
        calls_before = len(METER.calls)
        try:
            result = self._run_statement(statement, prove_meaning=prove_meaning)
        finally:
            # Back to PPTEST, so nothing after this statement compiles against
            # a dataset's private schema.
            go_home(self.target)
        result.model_calls = len(METER.calls) - calls_before
        self._flush_model_calls()
        return result

    def _datasets_for(
        self, statement: Statement, source: SourceEngine | None
    ) -> tuple[list[Variant], QueryFeatures | None]:
        if self.dataset_agent is None:
            return list(self.variants), None
        return self.dataset_agent.plan(statement, source, self.target if source else None)

    def _strengthen(
        self, statement: Statement, result: StatementResult, verdict: SemanticVerdict,
        variants: list[Variant], source: SourceEngine,
    ) -> tuple[SemanticVerdict, list[Variant]]:
        """Fetch more datasets for a proof that is vacuous or weak.

        Agreement on nothing is not a proof. Before settling for VACUOUS or
        WEAK, the dataset agent is asked for data this query actually selects:
        a cached model dataset if one exists for the schema, and a model call
        only if none does. The proof is then run again over everything.
        """
        agent = self.dataset_agent
        if agent is None or not agent.needs_more(verdict):
            return verdict, variants
        result.escalated = True
        extra = agent.escalate(statement, verdict, variants, source, self.target)
        if not extra:
            return verdict, variants
        variants = list(variants) + extra
        again = prove_semantics(
            source_sql=statement.sql,
            db2_sql=result.db2_sql or "",
            source=source,
            target=self.target,
            variants=variants,
            dialect=statement.dialect,
        )
        order = ("NONE", "WEAK", "MODERATE", "STRONG")
        if order.index(again.strength) > order.index(verdict.strength):
            result.rescued = True
            agent.stats.rescued += 1
        result.datasets_used = len(variants)
        return again, variants

    def _run_statement(self, statement: Statement, *, prove_meaning: bool = True) -> StatementResult:
        source = self.sources.get(statement.dialect)
        variants, feats = self._datasets_for(statement, source)
        if variants:
            # PREPARE resolves names against the live catalogue, so the tables
            # the statement reads have to exist before Db2 is asked about it.
            # For the fixture that is PPTEST; for a discovered schema it is the
            # first dataset built for that schema.
            activate(self.target, variants[0])
        attempt = translate.translate(statement.sql, statement.dialect)
        if not attempt.ok:
            result = StatementResult(
                statement=statement,
                status="TRANSLATE_FAIL",
                db2_sql=None,
                translator_raised=True,
                silent_failure=False,
                first_error=attempt.error or "",
            )
            self._record_translation(result)
            self._record_verdict(result, "COMPILE", "FAIL", 0, {"translate_error": attempt.error})
            return result

        first = db.compile_check(self.owner_conn, attempt.db2_sql or "")
        result = StatementResult(
            statement=statement,
            status="COMPILES" if first.ok else "COMPILE_FAIL",
            db2_sql=attempt.db2_sql,
            translator_raised=False,
            # The measured failure mode: clean translation, rejected by Db2.
            silent_failure=not first.ok,
            first_sqlcode=first.sqlcode,
            first_error=first.message,
        )

        if not first.ok:
            result.repair = self.repair_loop.run(
                source_sql=statement.sql,
                db2_sql=attempt.db2_sql or "",
                dialect=statement.dialect,
                case_name=statement.case_name,
            )
            if result.repair.attempts and result.repair.attempts[-1].ok:
                result.db2_sql = result.repair.final_sql
                result.status = "REPAIRED"
            else:
                result.status = "COMPILE_FAIL"

        compiles_now = result.status in ("COMPILES", "REPAIRED")
        pre_semantic_sql = ""

        if compiles_now and prove_meaning:
            if source is None:
                result.semantic = SemanticVerdict(
                    outcome="INCONCLUSIVE",
                    instances_checked=0,
                    instances_agreed=0,
                    source_engine="none",
                    notes=[
                        f"no {statement.dialect} source engine is reachable, so "
                        "meaning was not checked"
                    ],
                )
                result.status = "COMPILES"
            else:
                verdict = prove_semantics(
                    source_sql=statement.sql,
                    db2_sql=result.db2_sql or "",
                    source=source,
                    target=self.target,
                    variants=variants,
                    dialect=statement.dialect,
                )
                result.datasets_used = len(variants)

                agent = self.dataset_agent
                verdict, variants = self._strengthen(statement, result, verdict, variants, source)
                if agent is not None and feats is not None:
                    # Logged before any repair: the first verdict is the one
                    # that says which datasets expose divergences.
                    agent.observe(statement, feats, verdict)
                result.semantic = verdict

                # A compiling statement that returns the wrong rows is the
                # failure nothing else in the toolchain can see, so it is worth
                # trying to fix rather than merely reporting. Every candidate is
                # re-proved by the same differential test that caught it.
                if verdict.outcome == "DIFFERENT" and self.semantic_repair:
                    pre_semantic_sql = result.db2_sql or ""
                    loop = SemanticRepairLoop(
                        self.owner_conn, source=source, target=self.target,
                        model=self.repair_loop.model, case_name=statement.case_name,
                        memory=self.memory if "memory" in self.repair_loop.tiers else None,
                    )
                    fix = loop.run(
                        source_sql=statement.sql,
                        db2_sql=result.db2_sql or "",
                        dialect=statement.dialect,
                        variants=variants,
                        before=verdict,
                    )
                    if fix.attempts:
                        result.semantic_repair = fix
                    if fix.repaired and fix.verdict is not None:
                        result.original_semantic = verdict
                        result.db2_sql = fix.final_sql
                        # A repair is only as good as the proof behind it, so a
                        # repaired statement whose proof is thin gets the same
                        # second look as any other.
                        verdict, variants = self._strengthen(
                            statement, result, fix.verdict, variants, source
                        )
                        result.semantic = verdict

                # Only once no rewrite worked is instability the useful answer.
                # A statement that is both unstable and fixable gets the fix; a
                # statement that is unstable and unfixable gets the diagnosis,
                # which is itself actionable ("add a tiebreaker") and is not a
                # Db2 defect.
                if verdict.outcome == "DIFFERENT" and verdict.order_unstable:
                    verdict.outcome = "UNSTABLE"

                # A surviving divergence is worth a second opinion from the
                # engine itself. If Db2 can read the source tables directly, it
                # can say whether the two engines held the same rows to begin
                # with, which separates a translation bug from a loading one.
                # When federation is not configured this is a no-op.
                # Only for the fixture: the nicknames point at its tables, and
                # corroborating reloads the source's home namespace, which for
                # a discovered schema is the application's own data.
                if verdict.outcome in ("DIFFERENT", "UNSTABLE") and not statement.schema:
                    result.federation = self._corroborate(statement.dialect)

                result.status = {
                    "EQUIVALENT": "PROVEN_EQUIVALENT",
                    "DIFFERENT": "PROVEN_DIFFERENT",
                    "UNSTABLE": "UNSTABLE",
                    "VACUOUS": "VACUOUS",
                }.get(verdict.outcome, "COMPILES")

        self._record_translation(result)
        result.compile_cert = self._record_verdict(
            result,
            "COMPILE",
            "PASS" if compiles_now else "FAIL",
            result.repair.attempt_count if result.repair else 1,
            {
                "first_sqlcode": result.first_sqlcode,
                "first_error": result.first_error[:400],
                "repaired": result.repaired,
                "rules": sorted(
                    {r for a in (result.repair.attempts if result.repair else []) for r in a.rules_fired}
                ),
            },
        )
        if result.semantic is not None:
            # The certificate hashes DETAIL, so DETAIL has to be the evidence.
            # It used to be two integers and a witness, which made a vacuous
            # proof and a substantive one hash identically -- a certificate over
            # a conclusion rather than over what the conclusion rests on.
            detail = {
                "source_engine": result.semantic.source_engine,
                "witness": result.semantic.witness_table(),
                "witness_variant": result.semantic.witness.variant
                if result.semantic.witness
                else None,
                "notes": result.semantic.notes,
                **result.semantic.evidence(),
            }
            if result.semantically_repaired and result.semantic_repair is not None:
                detail["semantic_repair"] = {
                    "rule": result.semantic_repair.rule,
                    "because": result.semantic_repair.because,
                    "was": result.original_semantic.outcome
                    if result.original_semantic
                    else None,
                    "witness_before": result.original_semantic.witness_table()
                    if result.original_semantic
                    else None,
                }
            if result.federation is not None:
                detail["federation"] = {
                    "verdict": result.federation.verdict,
                    "says": result.federation.headline(),
                }
            result.semantic_cert = self._record_verdict(
                result,
                "SEMANTIC",
                result.semantic.outcome,
                result.semantic.instances_agreed,
                detail,
            )

        # Learn only from repairs Db2 accepted *and* that proved equivalent.
        if (
            self.learn
            and self.memory is not None
            and result.repaired
            and result.status == "PROVEN_EQUIVALENT"
        ):
            try:
                self.memory.remember(
                    bad_sql=attempt.db2_sql or "",
                    fixed_sql=result.db2_sql or "",
                    sqlcode=result.first_sqlcode,
                    error_text=result.first_error,
                    dialect=statement.dialect,
                    case_name=statement.case_name,
                )
                result.learned = True
            except Exception:
                result.learned = False

        # The same for a rewrite that changed the statement's *meaning* back to
        # the source's. What is remembered is the pair (the SQL that compiled
        # and was wrong, the SQL that was proved), so the next run replays the
        # proved rewrite instead of asking a rule or a model to find it again.
        if (
            self.learn
            and self.memory is not None
            and pre_semantic_sql
            and result.semantically_repaired
            and result.semantic_repair is not None
            and not result.semantic_repair.partial
            and result.status == "PROVEN_EQUIVALENT"
        ):
            try:
                self.memory.remember(
                    bad_sql=pre_semantic_sql,
                    fixed_sql=result.db2_sql or "",
                    sqlcode=0,
                    error_text="SEMANTIC: compiled on Db2 and returned different rows",
                    dialect=statement.dialect,
                    case_name=statement.case_name,
                )
                result.learned = True
            except Exception:
                pass

        return result

    # -- the whole corpus ------------------------------------------------
    def run(
        self,
        *,
        dialect: str | None = None,
        prove_meaning: bool = True,
        limit: int | None = None,
        statements: Sequence[Statement] | None = None,
    ) -> MigrationReport:
        statements = list(statements) if statements is not None else statements_for(dialect)
        if limit:
            statements = statements[:limit]
        report = MigrationReport(
            source_engine=self.source_engines,
            variants=len(self.variants),
            repair_policy=" then ".join(
                {"chain": "model" if self.repair_loop.model else "rules"}.get(t, t)
                for t in self.repair_loop.tiers
            ),
        )
        started = time.monotonic()
        loads_before = self._loads()
        for statement in statements:
            report.results.append(self.run_statement(statement, prove_meaning=prove_meaning))
        report.seconds = time.monotonic() - started
        report.loads = self._loads() - loads_before
        if self.dataset_agent is not None:
            report.agent_lines = self.dataset_agent.stats.lines()
        return report

    def _loads(self) -> int:
        engines = list(self.sources.values()) + [self.target]
        return sum(int(getattr(e, "loads", 0) or 0) for e in engines)

    def escalate_stalled(self, *, max_attempts: int | None = None) -> int:
        """Hand the statements the machine could not finish to a human.

        The decision is made *in the engine*, by a SQL PL cursor loop with an
        explicit ``CONTINUE HANDLER FOR NOT FOUND``, under the least-privilege
        identity that cannot UPDATE the ledger itself. That matters more than it
        sounds: "the AI gave up on these N statements" is the one output of an
        automated migration that must not be something the automation can
        quietly rewrite.
        """
        budget = max_attempts if max_attempts is not None else llm_config().max_repair_attempts
        out = db.call_proc(
            self.app_conn, "PORTPROOF.ESCALATE_STALLED", (int(budget), 0)
        )
        return int(out[-1])

    def physical_advice(self) -> dict:
        """Measured physical-design advice, recorded as a verdict like any other.

        The advice is written to the ledger under ``KIND = 'PHYSICAL'`` with
        ``OUTCOME = 'ADVICE'`` -- the two values the schema has always allowed
        and that nothing ever wrote. An advisory number that is not in the
        ledger is not reproducible, and the whole claim here is that it was
        measured rather than asserted.
        """
        advice = {
            "compression": physical.measure_compression(self.owner_conn),
            "columnar": physical.check_columnar(self.owner_conn),
            "hotspots": physical.workload_hotspots(self.owner_conn),
        }
        try:
            self._record_physical(advice)
        except db.Db2Error:  # pragma: no cover - advisory, never fatal
            pass
        return advice

    def _record_physical(self, advice: dict) -> str | None:
        """Attach the physical measurement to the first statement in the ledger.

        The VERDICT table hangs off STATEMENT, so the measurement needs a row to
        belong to; it is a property of the run, and the run's first statement is
        the stable anchor for it.
        """
        row = db.fetch_one(
            self.app_conn,
            "SELECT MIN(STMT_ID) FROM PORTPROOF.STATEMENT",
        )
        if not row or row[0] is None:
            return None
        compression = advice["compression"]
        detail = json.dumps(
            {
                "compression": compression.headline,
                "pages_saved_percent": getattr(compression, "percent_saved", None),
                "adaptive_percent_saved": getattr(
                    compression, "adaptive_percent_saved", None
                ),
                "columnar": advice["columnar"].headline,
                "hotspots": [
                    {"statement": text[:120], "executions": int(n)}
                    for text, n, _cpu in advice["hotspots"][:5]
                ],
            },
            default=str,
        )[:8000]
        out = db.call_proc(
            self.app_conn,
            "PORTPROOF.RECORD_VERDICT",
            (int(row[0]), "PHYSICAL", "ADVICE", len(advice["hotspots"]), detail, ""),
        )
        return str(out[-1])

    def close(self) -> None:
        try:
            self.target.close()
        except Exception:  # pragma: no cover
            pass
        for source in self.sources.values():
            try:
                source.close()
            except Exception:  # pragma: no cover
                pass
