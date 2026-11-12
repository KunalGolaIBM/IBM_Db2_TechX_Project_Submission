"""Background scan jobs with live progress for the web UI."""

import logging
import threading
import time
import uuid
from collections import OrderedDict, deque
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Deque, Dict, Optional

from ..config import ShipSafeConfig
from ..db2.pool import ConnectionPool, Db2Unavailable
from ..orchestration import AssessmentOrchestrator

log = logging.getLogger("shipsafe.jobs")

STEPS = ["discover", "secrets", "sast", "dependencies", "quality", "tests", "gate", "policies", "persist", "done"]


class RateLimiter:
    """Sliding one-minute window per principal."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] > 60:
                q.popleft()
            if len(q) >= self.per_minute:
                return False
            q.append(now)
            return True


class JobManager:
    def __init__(self, config: ShipSafeConfig, pool: ConnectionPool, kb_factory: Callable[[Any], Any],
                 audit: Callable[..., None], keep: int = 200):
        self.config = config
        self.pool = pool
        self.kb_factory = kb_factory
        self.audit = audit
        self.executor = ThreadPoolExecutor(max_workers=config.max_concurrent_scans, thread_name_prefix="scan")
        self.jobs: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self.keep = keep
        self._lock = threading.Lock()

    def submit(self, target: str, profile: str, actor: str) -> Dict[str, Any]:
        job_id = "job_" + uuid.uuid4().hex[:12]
        job = {
            "job_id": job_id, "status": "queued", "target": target, "profile": profile, "actor": actor,
            "created_at": int(time.time() * 1000), "finished_at": None, "steps": [], "current_step": None,
            "assessment_id": None, "gate": None, "summary": None, "warnings": [], "error": None,
        }
        with self._lock:
            self.jobs[job_id] = job
            while len(self.jobs) > self.keep:
                self.jobs.popitem(last=False)
        self.executor.submit(self._run, job_id)
        return dict(job)

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self.jobs.get(job_id)
            return None if job is None else {**job, "steps": list(job["steps"])}

    def recent(self, limit: int = 20):
        with self._lock:
            return [{k: v for k, v in j.items() if k != "steps"} for j in list(self.jobs.values())[-limit:]][::-1]

    def _progress(self, job_id: str):
        def cb(key: str, msg: str) -> None:
            with self._lock:
                job = self.jobs[job_id]
                job["current_step"] = key
                job["steps"].append({"key": key, "message": msg, "ts": int(time.time() * 1000)})
        return cb

    def _run(self, job_id: str) -> None:
        job = self.jobs[job_id]
        job["status"] = "running"
        progress = self._progress(job_id)
        try:
            try:
                with self.pool.repository() as repo:
                    kb = self._safe_kb(repo)
                    result = AssessmentOrchestrator(self.config, repo, kb).run_assessment(
                        job["target"], profile=job["profile"], progress=progress)
            except Db2Unavailable as exc:
                log.warning("Db2 unavailable, running scan in degraded mode: %s", exc)
                result = AssessmentOrchestrator(self.config, None, None).run_assessment(
                    job["target"], profile=job["profile"], progress=progress)
                result.warnings.insert(0, "IBM Db2 is unavailable: results are shown but were not saved.")
            asm = result.assessment
            job.update({
                "status": "done", "assessment_id": asm.assessment_id, "gate": result.gate.status.value,
                "persisted": result.persisted, "warnings": result.warnings,
                "summary": {"findings": asm.findings_count, "critical": asm.critical_count, "high": asm.high_count,
                            "medium": asm.medium_count, "low": asm.low_count, "reason": result.gate.reason,
                            "project": result.discovery.repo_name},
                "result": result.to_dict() if not result.persisted else None,
            })
            self.audit(job["actor"], "scan.completed", "success", target=job["target"],
                       detail=f"{asm.assessment_id} {result.gate.status.value} findings={asm.findings_count}")
        except Exception as exc:
            log.exception("scan job %s failed", job_id)
            job.update({"status": "failed", "error": str(exc)[:500]})
            self.audit(job["actor"], "scan.failed", "error", target=job["target"], detail=str(exc)[:500])
        finally:
            job["finished_at"] = int(time.time() * 1000)

    def _safe_kb(self, repo):
        try:
            return self.kb_factory(repo)
        except Exception as exc:
            log.warning("policy knowledge base unavailable: %s", exc)
            return None

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
