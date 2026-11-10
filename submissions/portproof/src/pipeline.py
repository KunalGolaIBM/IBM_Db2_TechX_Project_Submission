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
from dataclasses import dataclass, field

from . import db, physical, translate
from .corpus import VARIANTS, Statement, statements_for
from .counterexample import (
    Db2Target,
    DuckDbSource,
    SemanticVerdict,
    SourceEngine,
    ensure_fixture_schema,
    prove_semantics,
)
from .fixmemory import FixMemory
from .repair import RepairLoop, RepairOutcome


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
    stmt_id: int | None = None
    compile_cert: str | None = None
    semantic_cert: str | None = None
    learned: bool = False

    @property
    def case_name(self) -> str:
        return self.statement.case_name

    @property
    def repaired(self) -> bool:
        return bool(self.repair and self.repair.repaired)


@dataclass
class MigrationReport:
    results: list[StatementResult] = field(default_factory=list)
    source_engine: str = ""
    variants: int = 0

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

    def summary_lines(self) -> list[str]:
        return [
            f"statements migrated      : {self.total}",
            f"translator reported errors: {self.translator_errors}",
            f"SILENT failures (clean translate, rejected by Db2): {self.silent_failures}",
            f"repaired and re-verified : {self.repaired}",
            f"still failing to compile : {self.unrepaired}",
            f"proven equivalent        : {self.proven_equivalent} "
            f"(on {self.variants} adversarial datasets vs {self.source_engine})",
            f"PROVEN DIFFERENT         : {self.proven_different}",
            f"inconclusive             : {self.inconclusive}",
        ]


class Pipeline:
    def __init__(
        self,
        *,
        app_conn,
        owner_conn,
        source: SourceEngine | None = None,
        memory: FixMemory | None = None,
        repair_loop: RepairLoop | None = None,
        learn: bool = True,
    ):
        self.app_conn = app_conn
        self.owner_conn = owner_conn
        ensure_fixture_schema(owner_conn)
        self.target = Db2Target(owner_conn)
        self.source = source if source is not None else DuckDbSource()
        self.memory = memory
        self.repair_loop = repair_loop or RepairLoop(owner_conn, memory=memory)
        self.learn = learn

    # -- ledger ----------------------------------------------------------
    def _record_translation(self, result: StatementResult) -> None:
        meta = json.dumps(
            {
                "translator_raised": result.translator_raised,
                "silent_failure": result.silent_failure,
                "attempts": result.repair.attempt_count if result.repair else 0,
                "rules": sorted(
                    {r for a in (result.repair.attempts if result.repair else []) for r in a.rules_fired}
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
            )
            if result.repair.attempts and result.repair.attempts[-1].ok:
                result.db2_sql = result.repair.final_sql
                result.status = "REPAIRED"
            else:
                result.status = "COMPILE_FAIL"

        compiles_now = result.status in ("COMPILES", "REPAIRED")

        if compiles_now and prove_meaning:
            verdict = prove_semantics(
                source_sql=statement.sql,
                db2_sql=result.db2_sql or "",
                source=self.source,
                target=self.target,
            )
            result.semantic = verdict
            if verdict.outcome == "EQUIVALENT":
                result.status = "PROVEN_EQUIVALENT"
            elif verdict.outcome == "DIFFERENT":
                result.status = "PROVEN_DIFFERENT"
            else:
                result.status = "COMPILES"

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
            result.semantic_cert = self._record_verdict(
                result,
                "SEMANTIC",
                result.semantic.outcome,
                result.semantic.instances_agreed,
                {
                    "source_engine": result.semantic.source_engine,
                    "instances_checked": result.semantic.instances_checked,
                    "witness": result.semantic.witness_table(),
                    "witness_variant": result.semantic.witness.variant
                    if result.semantic.witness
                    else None,
                    "notes": result.semantic.notes,
                },
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

        return result

    # -- the whole corpus ------------------------------------------------
    def run(
        self, *, dialect: str | None = None, prove_meaning: bool = True, limit: int | None = None
    ) -> MigrationReport:
        statements = statements_for(dialect)
        if limit:
            statements = statements[:limit]
        report = MigrationReport(source_engine=self.source.name, variants=len(VARIANTS))
        for statement in statements:
            report.results.append(self.run_statement(statement, prove_meaning=prove_meaning))
        return report

    def physical_advice(self) -> dict:
        return {
            "compression": physical.measure_compression(self.owner_conn),
            "columnar": physical.check_columnar(self.owner_conn),
            "hotspots": physical.workload_hotspots(self.owner_conn),
        }

    def close(self) -> None:
        try:
            self.source.close()
        except Exception:  # pragma: no cover
            pass
