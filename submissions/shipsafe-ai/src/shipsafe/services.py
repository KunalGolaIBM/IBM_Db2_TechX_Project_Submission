"""One place that builds every ShipSafe capability on top of one Db2 connection.

Used by the MCP server (Bob, Claude, Cursor...), the REST API and the CLI so
that every surface behaves identically. Heavy pieces (vector stores, Granite,
CrewAI) are created on first use, so a guard check never waits for them.
"""

import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import ShipSafeConfig
from .db2 import Db2Repository
from .guard import GuardResult, check_code, language_for
from .llm.granite import ollama_status

def _short(exc: Exception) -> str:
    import re

    return re.sub(r"(?i)pwd=[^;]*", "PWD=***", str(exc)).splitlines()[0][:200] if str(exc) else type(exc).__name__


POLICY_CATEGORY = {"secrets": "secrets", "security": "security", "quality": "tests", "dependencies": "dependencies"}
MAX_FILE_BYTES = 400_000


DB2_RETRY_AFTER_S = 30.0
DB2_OFFLINE = ("IBM Db2 is not reachable; code checks still run. Run `shipsafe setup` (or `shipsafe doctor`) "
               "to connect Db2 for policy citations, history, memory and SQL checks.")

class ShipSafeServices:
    def __init__(self, config: Optional[ShipSafeConfig] = None, repository: Optional[Db2Repository] = None,
                 workspace_root: Optional[str] = None):
        self.config = config or ShipSafeConfig.load()
        self._repo = repository
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self._lock = threading.RLock()  # one ibm_db connection: serialise access
        self._kb = self._advisor = self._memory = self._sql = self._orchestrator = None
        self._db2_down_until = 0.0  # after a failed connect, answer at once instead of retrying every call

    # ------------------------------------------------------------- plumbing
    @property
    def repository(self) -> Db2Repository:
        with self._lock:
            if self._repo is None:
                if time.monotonic() < self._db2_down_until:
                    raise ConnectionError(DB2_OFFLINE)
                try:
                    self._repo = Db2Repository(self.config.db2)
                except Exception:
                    self._db2_down_until = time.monotonic() + DB2_RETRY_AFTER_S
                    raise
            return self._repo

    @property
    def knowledge_base(self):
        with self._lock:
            if self._kb is None:
                from .knowledge import PolicyKnowledgeBase

                self._kb = PolicyKnowledgeBase(self.repository, self.config.embedding_provider,
                                               self.config.embedding_dimension, self.config.llm)
                self._kb.ensure_ingested(self.config.policies_dir)
            return self._kb

    @property
    def advisor(self):
        if self._advisor is None:
            from .knowledge.standards import StandardsAdvisor

            self._advisor = StandardsAdvisor(self.knowledge_base, self.config.llm)
        return self._advisor

    @property
    def memory(self):
        with self._lock:
            if self._memory is None:
                from .memory import ProjectMemory

                self._memory = ProjectMemory(self.config)
            return self._memory

    @property
    def sql_checker(self):
        if self._sql is None:
            from .db2sql import Db2SqlChecker

            self._sql = Db2SqlChecker(self.repository)
        return self._sql

    def resolve_in_workspace(self, path: str) -> Path:
        """Resolve a path inside the workspace; refuse anything outside it."""
        candidate = (self.workspace_root / path).resolve()
        try:
            candidate.relative_to(self.workspace_root)
        except ValueError:
            raise PermissionError(f"{path!r} is outside the workspace {self.workspace_root}") from None
        return candidate

    def policies_for(self, query: str, category: str) -> List[Dict[str, Any]]:
        with self._lock:
            return self.knowledge_base.retrieve(query, top_k=1, category=POLICY_CATEGORY.get(category))

    # -------------------------------------------------------------- features
    def check_code(self, code: str, filename: str = "snippet.py", client: str = "unknown",
                   project: Optional[str] = None, cite_policies: Optional[bool] = None, tool: str = "check_code") -> Dict[str, Any]:
        result: GuardResult = check_code(code, filename, use_bandit=self.config.use_bandit)
        notes: List[str] = []
        if cite_policies is None:
            cite_policies = self.config.cite_policies
        # The verdict comes from the code alone. Db2 (policy citations, event log) and the embedding model
        # add context; if either is unavailable the check still answers and says what was skipped.
        if cite_policies and result.issues:
            try:
                for issue in result.issues:
                    hits = self.policies_for(f"{issue.title}. {issue.why}", issue.category)
                    if hits:
                        h = hits[0]
                        issue.policy = {"doc_id": h["doc_id"], "title": h["title"], "section": h["section"],
                                        "excerpt": h["content"][:600], "similarity": h["similarity"]}
            except ConnectionError:
                notes.append(DB2_OFFLINE)
            except Exception as exc:
                notes.append(f"Policy citations skipped: {_short(exc)}")
        try:
            with self._lock:
                self.repository.record_guard_event(
                    client=client, tool=tool, verdict=result.verdict, findings_count=len(result.issues),
                    duration_ms=result.duration_ms, project=project or self.workspace_root.name, file_path=filename,
                    language=result.language, max_severity=result.max_severity,
                    rule_ids=[i.rule_id for i in result.issues])
        except ConnectionError:
            if DB2_OFFLINE not in notes:
                notes.append(DB2_OFFLINE)
        except Exception as exc:
            notes.append(f"Not logged to Db2: {_short(exc)}")
            self._reset_repository()
        out = result.to_dict()
        if notes:
            out["notes"] = notes
        return out

    def _reset_repository(self) -> None:
        """Drop a broken connection so the next call reconnects instead of failing forever."""
        with self._lock:
            if self._repo is not None:
                self._repo.close()
            self._repo = self._kb = self._advisor = self._sql = None

    def check_files(self, paths: List[str], client: str = "unknown") -> Dict[str, Any]:
        files = []
        for p in paths[:50]:
            target = self.resolve_in_workspace(p)
            if not target.is_file():
                files.append({"filename": p, "error": "not a file"})
                continue
            if target.stat().st_size > MAX_FILE_BYTES:
                files.append({"filename": p, "error": "file too large for an inline check; use readiness_check"})
                continue
            rel = target.relative_to(self.workspace_root).as_posix()
            files.append(self.check_code(target.read_text(encoding="utf-8", errors="ignore"), rel, client=client,
                                         tool="check_files"))
        verdicts = [f.get("verdict") for f in files if "verdict" in f]
        overall = "block" if "block" in verdicts else "warn" if "warn" in verdicts else "clean"
        return {"verdict": overall, "files": files}

    def fix_code(self, code: str, filename: str = "snippet.py", client: str = "unknown") -> Dict[str, Any]:
        from .agents import FixCrew

        crew = FixCrew(self.config.llm, policy_lookup=lambda q, c: self.policies_for(q, c),
                       use_bandit=self.config.use_bandit, max_rounds=self.config.fix_max_rounds)
        result = crew.fix(code, filename)
        if result.rounds:
            with self._lock:
                result.fix_id = self.repository.record_fix_attempt(
                    model=result.model, iterations=result.rounds, verified=result.verified,
                    issues_before=len(result.issues_before), issues_after=len(result.issues_after),
                    duration_ms=result.duration_ms, patch=result.diff, file_path=filename,
                    language=language_for(filename), rule_ids=[i["rule_id"] for i in result.issues_before])
        return result.to_dict()

    def check_sql(self, sql: str) -> Dict[str, Any]:
        with self._lock:
            return self.sql_checker.check(sql).to_dict()

    def db2_schema(self, schema: Optional[str] = None, tables: Optional[List[str]] = None) -> Dict[str, Any]:
        return self.sql_checker.schema_overview(schema, tables)

    def ask_standards(self, question: str, category: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            return self.advisor.ask(question, category)

    def search_standards(self, query: str, top_k: int = 3, category: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            return self.knowledge_base.retrieve(query, top_k=top_k, category=category)

    def remember(self, text: str, kind: str = "decision", project: Optional[str] = None,
                 tags: Optional[List[str]] = None, client: str = "unknown") -> Dict[str, Any]:
        return self.memory.remember(text, kind=kind, project=project or self.workspace_root.name,
                                    tags=tags or [], author=client)

    def recall(self, query: str, project: Optional[str] = None, top_k: int = 5,
               kind: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.memory.recall(query, project=project or self.workspace_root.name, top_k=top_k, kind=kind)

    def readiness_check(self, workspace: Optional[str] = None, profile: str = "pre-pr") -> Dict[str, Any]:
        from .orchestration import AssessmentOrchestrator

        root = self.resolve_in_workspace(workspace or ".")
        with self._lock:
            kb = self.knowledge_base
            orchestrator = AssessmentOrchestrator(self.config, self.repository, kb)
            result = orchestrator.run_assessment(str(root), profile=profile)
            risk = self.repository.project_risk(result.assessment.project_id) if result.persisted else None
        top = sorted(result.findings, key=lambda f: ("critical", "high", "medium", "low", "info").index(f.severity))[:15]
        return {
            "assessment_id": result.assessment.assessment_id, "status": result.gate.status.value,
            "reason": result.gate.reason, "persisted_in_db2": result.persisted, "risk": risk,
            "counts": {"critical": result.assessment.critical_count, "high": result.assessment.high_count,
                       "medium": result.assessment.medium_count, "low": result.assessment.low_count},
            "top_findings": [{"rule_id": f.rule_id, "severity": f.severity, "title": f.title, "file": f.file_path,
                              "line": f.line_start, "fix": f.remediation} for f in top],
            "warnings": result.warnings,
        }

    def session_report(self, since_minutes: int = 24 * 60) -> Dict[str, Any]:
        since = int(time.time() * 1000) - int(since_minutes) * 60_000
        with self._lock:
            summary = self.repository.guard_summary(since)
            fixes = self.repository.list_fix_attempts(limit=10)
        return {"since_minutes": since_minutes, "by_client": summary, "recent_fixes": fixes}

    def status(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"workspace": str(self.workspace_root)}
        try:
            with self._lock:
                out["db2"] = self.repository.check_connection()
        except Exception as exc:
            out["db2"] = {"connected": False, "error": str(exc)[:300]}
        out["ollama"] = ollama_status(self.config.llm)
        return out
