"""Fix-and-verify: a CrewAI crew proposes a fix, ShipSafe's real checks decide.

Round structure (at most `max_rounds`):

1. **Security Analyst** (Granite) reads the code, the exact issues found by the
   deterministic checks and the team standard retrieved from Db2, and writes a
   short, concrete fix plan.
2. **Fix Engineer** (Granite) applies the plan and returns the complete
   corrected file.
3. **Verification** is not an LLM: the corrected code is checked again with the
   same rules, secret patterns, syntax check and Bandit. A fix is accepted only
   if every targeted issue is gone and no new blocking issue appeared. Anything
   left over is fed into the next round.

The model can be wrong; the verdict cannot be talked into passing.
"""

import difflib
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..config import LlmConfig
from ..guard import GuardIssue, check_code, language_for
from ..llm.granite import crew_llm, require_models

_FENCE = re.compile(r"```[a-zA-Z0-9_+-]*\s*\n(.*?)```", re.S)


@dataclass
class FixResult:
    filename: str
    verified: bool
    fixed_code: Optional[str]
    diff: str
    rounds: int
    issues_before: List[Dict[str, Any]]
    issues_after: List[Dict[str, Any]]
    plan: str
    model: str
    duration_ms: int
    message: str
    fix_id: Optional[str] = None
    policies: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def extract_code(text: str) -> str:
    """Take the largest fenced code block from a model answer, or the whole answer if there is none."""
    blocks = _FENCE.findall(text or "")
    if blocks:
        return max(blocks, key=len).strip("\n") + "\n"
    return (text or "").strip() + "\n"


def _issue_key(issue: GuardIssue) -> str:
    return issue.rule_id


def _issue_brief(issues: List[GuardIssue]) -> str:
    return "\n".join(f"- line {i.line}: [{i.severity}] {i.rule_id} {i.title}. Why: {i.why} Fix: {i.fix}"
                     for i in issues)


def _blocking(issues: List[GuardIssue]) -> List[GuardIssue]:
    return [i for i in issues if i.severity in ("critical", "high")]


class FixCrew:
    """Builds and runs the two-agent crew; verification is deterministic."""

    def __init__(self, llm_config: LlmConfig, policy_lookup: Optional[Callable[[str, str], List[Dict[str, Any]]]] = None,
                 use_bandit: bool = True, max_rounds: int = 3):
        self.cfg = llm_config
        self.policy_lookup = policy_lookup
        self.use_bandit = use_bandit
        self.max_rounds = max(1, max_rounds)

    def _crew(self, language: str):
        from crewai import Agent, Crew, Process, Task

        llm = crew_llm(self.cfg)
        analyst = Agent(
            role="Application Security Analyst",
            goal="Explain precisely how to remove each reported vulnerability without changing what the code does.",
            backstory="You review code written by AI assistants before it reaches production. You follow the "
                      "team's written engineering standards and you are concise.",
            llm=llm, allow_delegation=False, verbose=False, max_iter=2)
        engineer = Agent(
            role=f"Senior {language.title()} Engineer",
            goal="Rewrite the file so every reported issue is fixed, keeping behaviour, names and structure.",
            backstory="You make minimal, production-quality changes and always return the complete file.",
            llm=llm, allow_delegation=False, verbose=False, max_iter=2)
        plan = Task(
            description=(
                "File: {filename} ({language}).\n\nIssues found by ShipSafe's checks:\n{issues}\n\n"
                "Team standards retrieved from IBM Db2:\n{standards}\n\nCode:\n```{language}\n{code}\n```\n\n"
                "Write a numbered fix plan: one step per issue, naming the exact line and the replacement."),
            expected_output="A short numbered fix plan, one step per issue.",
            agent=analyst)
        fix = Task(
            description=(
                "Apply the fix plan to the code of {filename}. Fix every listed issue. Do not add new features, "
                "do not remove functionality, keep function names and signatures. Read secrets from environment "
                "variables (os.environ / process.env) instead of hardcoding them. For SQL use `?` parameter markers. "
                "With ibm_db, bind values like this: `stmt = ibm_db.prepare(conn, sql)` then "
                "`ibm_db.execute(stmt, (value,))`, then fetch rows from the statement: `ibm_db.fetch_assoc(stmt)` "
                "(execute returns True/False; exec_immediate cannot take parameters). With a DB-API "
                "cursor use `cursor.execute(sql, (value,))`. Keep every import the code needs.\n\n"
                "Code:\n```{language}\n{code}\n```"),
            expected_output="The complete corrected file in one fenced code block, and nothing else.",
            agent=engineer, context=[plan])
        return Crew(agents=[analyst, engineer], tasks=[plan, fix], process=Process.sequential, verbose=False,
                    tracing=False)

    def _standards(self, issues: List[GuardIssue]) -> (str, List[Dict[str, Any]]):
        if not self.policy_lookup:
            return "(none available)", []
        seen, cited = set(), []
        for issue in issues[:5]:
            for hit in self.policy_lookup(f"{issue.title}. {issue.why}", issue.category)[:1]:
                if hit["doc_id"] not in seen:
                    seen.add(hit["doc_id"])
                    cited.append(hit)
        text = "\n\n".join(f"[{h['doc_id']}] {h['title']} / {h['section']}:\n{h['content'][:900]}" for h in cited)
        return text or "(none matched)", cited

    def fix(self, code: str, filename: str = "snippet.py", issues: Optional[List[GuardIssue]] = None) -> FixResult:
        started = time.perf_counter()
        language = language_for(filename)
        before = check_code(code, filename, use_bandit=self.use_bandit)
        targets = issues if issues is not None else before.issues
        if not targets:
            return FixResult(filename, True, code, "", 0, [], [], "", self.cfg.chat_model,
                             int((time.perf_counter() - started) * 1000), "Nothing to fix: the code passes every check.")
        require_models(self.cfg, chat=True)
        standards, cited = self._standards(targets)
        target_rules = {_issue_key(i) for i in targets}

        current, remaining, plan_text, rounds = code, targets, "", 0
        candidate_result = before
        while rounds < self.max_rounds:
            rounds += 1
            out = self._crew(language).kickoff(inputs={
                "filename": filename, "language": language, "code": current,
                "issues": _issue_brief(remaining), "standards": standards})
            plan_text = (out.tasks_output[0].raw if getattr(out, "tasks_output", None) else "") or plan_text
            candidate = extract_code(out.raw)
            candidate_result = check_code(candidate, filename, use_bandit=self.use_bandit)
            still = [i for i in candidate_result.issues if _issue_key(i) in target_rules]
            new_blocking = [i for i in _blocking(candidate_result.issues) if _issue_key(i) not in target_rules]
            current = candidate
            if not still and not new_blocking:
                break
            remaining = still + new_blocking

        verified = not [i for i in candidate_result.issues if _issue_key(i) in target_rules] \
            and not _blocking(candidate_result.issues)
        diff = "".join(difflib.unified_diff(code.splitlines(True), current.splitlines(True),
                                            fromfile=f"a/{filename}", tofile=f"b/{filename}"))
        message = ("Verified: every targeted issue is gone and no blocking issue remains."
                   if verified else "Not verified: the proposed code still fails ShipSafe's checks. Review before use.")
        return FixResult(
            filename=filename, verified=verified, fixed_code=current, diff=diff, rounds=rounds,
            issues_before=[asdict(i) for i in before.issues], issues_after=[asdict(i) for i in candidate_result.issues],
            plan=plan_text.strip(), model=self.cfg.chat_model, duration_ms=int((time.perf_counter() - started) * 1000),
            message=message, policies=[{k: h[k] for k in ("doc_id", "title", "section", "source")} for h in cited])
