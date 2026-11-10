"""The repair models.

Two LangChain ``LLM`` implementations are provided:

* :class:`RuleRepairLLM` -- **not a language model.** It is a small deterministic
  rewrite engine covering the dialect gaps PortProof has actually measured
  against Db2 12.1.5. It is the default (``LLM_PROVIDER=mock``) so the whole
  project runs with no API key and so tests are reproducible. Every rule here
  was derived from a real SQLCODE observed on a real Db2, and each one is
  re-verified by Db2 after it fires -- a rule that produces invalid SQL is
  rejected exactly like a model's output would be.
* :class:`HttpRepairLLM` -- any OpenAI-compatible chat endpoint (Groq, Gemini's
  compatibility layer, watsonx, a local server). Used when ``LLM_PROVIDER=http``.

Both are plugged into the same LangChain chain in :mod:`src.repair`, so the
pipeline does not know or care which one answered.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Callable

from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.llms import LLM

from .config import LlmConfig, llm_config

# --------------------------------------------------------------------------
# deterministic rewrite rules
# --------------------------------------------------------------------------
Rule = tuple[str, Callable[[str], str]]

_STRFTIME_TO_DB2 = [
    ("%Y", "YYYY"), ("%m", "MM"), ("%d", "DD"),
    ("%H", "HH24"), ("%M", "MI"), ("%S", "SS"),
]


def _balanced_args(text: str, start: int) -> tuple[list[str], int] | None:
    """Split the argument list of a call whose '(' is at ``start``."""
    if start >= len(text) or text[start] != "(":
        return None
    depth, current, args, in_str = 0, [], [], False
    for index in range(start, len(text)):
        char = text[index]
        if char == "'" and text[index - 1 : index] != "\\":
            in_str = not in_str
            current.append(char)
            continue
        if in_str:
            current.append(char)
            continue
        if char == "(":
            depth += 1
            if depth == 1:
                continue
        elif char == ")":
            depth -= 1
            if depth == 0:
                args.append("".join(current).strip())
                return args, index + 1
        if depth == 1 and char == ",":
            args.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    return None


def _rewrite_calls(sql: str, func: str, build: Callable[[list[str]], str | None]) -> str:
    """Rewrite every call to ``func`` using ``build(args)``."""
    pattern = re.compile(rf"\b{func}\s*\(", re.IGNORECASE)
    out, cursor = [], 0
    while True:
        match = pattern.search(sql, cursor)
        if not match:
            out.append(sql[cursor:])
            return "".join(out)
        parsed = _balanced_args(sql, match.end() - 1)
        if parsed is None:
            out.append(sql[cursor : match.end()])
            cursor = match.end()
            continue
        args, after = parsed
        replacement = build(args)
        if replacement is None:
            out.append(sql[cursor:after])
        else:
            out.append(sql[cursor : match.start()])
            out.append(replacement)
        cursor = after


def _fix_group_concat(sql: str) -> str:
    """GROUP_CONCAT is MySQL's. Db2 spells it LISTAGG ... WITHIN GROUP."""

    def build(args: list[str]) -> str | None:
        if not args:
            return None
        head = args[0]
        separator = args[1] if len(args) > 1 else "','"
        order_by = ""
        inline = re.search(r"\bORDER\s+BY\b(.*)$", head, re.IGNORECASE | re.DOTALL)
        if inline:
            order_by = f" WITHIN GROUP (ORDER BY {inline.group(1).strip()})"
            head = head[: inline.start()].strip()
        if not separator.startswith("'"):
            head, separator = head, "','"
        return f"LISTAGG({head}, {separator}){order_by}"

    return _rewrite_calls(sql, "GROUP_CONCAT", build)


def _fix_array_agg(sql: str) -> str:
    """Db2 has no array type in this context; aggregate to a string instead."""

    def build(args: list[str]) -> str | None:
        if not args:
            return None
        return f"LISTAGG(CAST({args[0]} AS VARCHAR(200)), ',')"

    return _rewrite_calls(sql, "ARRAY_AGG", build)


def _fix_concat(sql: str) -> str:
    """Db2's CONCAT takes exactly two arguments; || takes any number."""

    def build(args: list[str]) -> str | None:
        if len(args) <= 2:
            return None
        return "(" + " || ".join(args) + ")"

    return _rewrite_calls(sql, "CONCAT", build)


def _fix_timestamp_trunc(sql: str) -> str:
    def build(args: list[str]) -> str | None:
        if len(args) != 2:
            return None
        unit = args[1].strip().strip("'").upper()
        return f"TRUNC_TIMESTAMP({args[0]}, '{unit}')"

    return _rewrite_calls(sql, "TIMESTAMP_TRUNC", build)


def _fix_json_extract(sql: str) -> str:
    def build(args: list[str]) -> str | None:
        if len(args) != 2:
            return None
        return f"JSON_VALUE({args[0]}, {args[1]})"

    return _rewrite_calls(sql, "JSON_EXTRACT_SCALAR", build)


def _fix_regexp_i_like(sql: str) -> str:
    def build(args: list[str]) -> str | None:
        if len(args) < 2:
            return None
        return f"REGEXP_LIKE({args[0]}, {args[1]}, 'i')"

    return _rewrite_calls(sql, "REGEXP_I_LIKE", build)


def _fix_count_filter(sql: str) -> str:
    """``agg(x) FILTER (WHERE p)`` becomes ``agg(CASE WHEN p THEN x END)``."""
    pattern = re.compile(
        r"\b(COUNT|SUM|AVG|MIN|MAX)\s*\(\s*(\*|[^()]*?)\s*\)\s*FILTER\s*\(",
        re.IGNORECASE,
    )
    while True:
        match = pattern.search(sql)
        if not match:
            return sql
        # match.end() - 1 is the '(' that opens the FILTER clause.
        parsed = _balanced_args(sql, match.end() - 1)
        if parsed is None:
            return sql
        args, after = parsed
        predicate = re.sub(r"^\s*WHERE\s+", "", args[0], flags=re.IGNORECASE)
        agg, target = match.group(1), match.group(2).strip()
        inner = "1" if target == "*" else target
        sql = sql[: match.start()] + f"{agg}(CASE WHEN {predicate} THEN {inner} END)" + sql[after:]


def _fix_with_recursive(sql: str) -> str:
    """Db2 infers recursion; the RECURSIVE keyword is a syntax error."""
    return re.sub(r"\bWITH\s+RECURSIVE\b", "WITH", sql, flags=re.IGNORECASE)


def _fix_lowercase_quoted_identifiers(sql: str) -> str:
    """Db2 folds unquoted names to upper case.

    MySQL backticks become double quotes, which makes the name
    case-*sensitive* and lower case -- so it no longer matches the table Db2
    actually created. Dropping the quotes restores the intent.
    """
    return re.sub(r'"([a-z_][a-z0-9_]*)"', r"\1", sql)


def _fix_strftime_format(sql: str) -> str:
    def replace(match: re.Match[str]) -> str:
        literal = match.group(0)
        for src, dst in _STRFTIME_TO_DB2:
            literal = literal.replace(src, dst)
        return literal

    return re.sub(r"'[^']*%[A-Za-z][^']*'", replace, sql)


def _select_items(sql: str) -> list[tuple[str, str | None]]:
    """The top-level select list as ``(expression, alias)`` pairs."""
    select = re.search(r"\bSELECT\b(.*?)\bFROM\b", sql, re.IGNORECASE | re.DOTALL)
    if not select:
        return []
    items: list[tuple[str, str | None]] = []
    depth = 0
    buffer: list[str] = []
    for char in select.group(1) + ",":
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            text = "".join(buffer).strip()
            buffer = []
            if not text:
                continue
            alias = re.search(
                r"^(.*?)\s+AS\s+([A-Za-z_][A-Za-z0-9_]*)\s*$", text, re.IGNORECASE | re.DOTALL
            )
            if alias:
                items.append((alias.group(1).strip(), alias.group(2)))
            else:
                items.append((text, None))
            continue
        buffer.append(char)
    return items


def _fix_group_by_ordinal(sql: str) -> str:
    """Db2 does not accept an ordinal in GROUP BY; PostgreSQL and MySQL do."""
    items = _select_items(sql)
    if not items:
        return sql

    def rewrite(match: re.Match[str]) -> str:
        parts = [p.strip() for p in match.group(2).split(",")]
        if not any(p.isdigit() for p in parts):
            return match.group(0)
        resolved = []
        for part in parts:
            if part.isdigit() and 1 <= int(part) <= len(items):
                resolved.append(items[int(part) - 1][0])
            else:
                resolved.append(part)
        return match.group(1) + ", ".join(resolved) + " "

    return re.sub(
        r"(\bGROUP\s+BY\s+)([0-9,\s]+?)(?=\bORDER\b|\bHAVING\b|\bFETCH\b|$)",
        rewrite,
        sql,
        flags=re.IGNORECASE,
    )


def _fix_group_by_alias(sql: str) -> str:
    """Db2 cannot GROUP BY a select-list alias; inline the expression."""
    aliases = {
        alias.upper(): expression
        for expression, alias in _select_items(sql)
        if alias and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", expression)
    }
    if not aliases:
        return sql

    def rewrite_group_by(match: re.Match[str]) -> str:
        body = match.group(2)
        parts = [p.strip() for p in body.split(",")]
        new_parts = [aliases.get(p.upper(), p) for p in parts]
        # Keep a trailing space: the lookahead consumes none, so without it the
        # next keyword would be glued on ("GROUP BY 1ORDER BY 1").
        return match.group(1) + ", ".join(new_parts) + " "

    return re.sub(
        r"(\bGROUP\s+BY\s+)([A-Za-z0-9_,\s]+?)(?=\bORDER\b|\bHAVING\b|\bFETCH\b|$)",
        rewrite_group_by,
        sql,
        flags=re.IGNORECASE,
    )


def _fix_untyped_date_arithmetic(sql: str) -> str:
    """``'2026-03-01' - '7' DAY`` needs a real date and an integer count."""
    sql = re.sub(
        r"'(\d{4}-\d{2}-\d{2})'\s*([-+])\s*'(\d+)'\s+(DAY|MONTH|YEAR)S?\b",
        lambda m: f"DATE('{m.group(1)}') {m.group(2)} {m.group(3)} {m.group(4)}",
        sql,
        flags=re.IGNORECASE,
    )
    return re.sub(
        r"([-+])\s*'(\d+)'\s+(DAY|MONTH|YEAR)S?\b",
        lambda m: f"{m.group(1)} {m.group(2)} {m.group(3)}",
        sql,
        flags=re.IGNORECASE,
    )


def _fix_leading_underscore_identifiers(sql: str) -> str:
    """Db2 identifiers may not begin with an underscore.

    sqlglot names its generated helpers ``_t`` and ``_row_number``, which Db2
    rejects (SQL20521N) when it meets them.
    """
    return re.sub(r"(?<![A-Za-z0-9_])_([A-Za-z][A-Za-z0-9_]*)", r"pp_\1", sql)


#: Applied in order. Each is named so the ledger can record what fired.
RULES: list[Rule] = [
    ("rename-leading-underscore-identifiers", _fix_leading_underscore_identifiers),
    ("group_concat->listagg", _fix_group_concat),
    ("array_agg->listagg", _fix_array_agg),
    ("concat->||", _fix_concat),
    ("timestamp_trunc->trunc_timestamp", _fix_timestamp_trunc),
    ("json_extract_scalar->json_value", _fix_json_extract),
    ("regexp_i_like->regexp_like", _fix_regexp_i_like),
    ("filter->case", _fix_count_filter),
    ("drop-recursive-keyword", _fix_with_recursive),
    ("unquote-lowercase-identifiers", _fix_lowercase_quoted_identifiers),
    ("strftime->db2-format", _fix_strftime_format),
    ("inline-group-by-alias", _fix_group_by_alias),
    ("resolve-group-by-ordinal", _fix_group_by_ordinal),
    ("typed-date-arithmetic", _fix_untyped_date_arithmetic),
]


def apply_rules(sql: str) -> tuple[str, list[str]]:
    """Apply every rule, reporting which ones changed the statement."""
    fired: list[str] = []
    for name, rule in RULES:
        try:
            candidate = rule(sql)
        except Exception:  # a rule must never crash the pipeline
            continue
        if candidate and candidate != sql:
            fired.append(name)
            sql = candidate
    return sql, fired


# --------------------------------------------------------------------------
# LangChain models
# --------------------------------------------------------------------------
class RuleRepairLLM(LLM):
    """Deterministic repair, exposed through the LangChain ``LLM`` interface."""

    last_rules: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "portproof-rules"

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> str:
        candidate = _extract_tagged(prompt, "FAILING_DB2_SQL")
        if not candidate:
            return ""
        repaired, fired = apply_rules(candidate)
        object.__setattr__(self, "last_rules", fired)
        return repaired


class HttpRepairLLM(LLM):
    """Any OpenAI-compatible chat-completions endpoint."""

    model: str = "llama-3.3-70b-versatile"
    api_key: str = ""
    base_url: str = "https://api.groq.com/openai/v1"
    timeout: int = 60

    @property
    def _llm_type(self) -> str:
        return "portproof-http"

    def _call(
        self,
        prompt: str,
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "temperature": 0,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You rewrite SQL so that IBM Db2 accepts it. "
                            "Reply with the corrected SQL statement only: no prose, "
                            "no markdown fences, no explanation."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:  # pragma: no cover
            raise RuntimeError(f"Unexpected LLM response shape: {body}") from exc


def _extract_tagged(prompt: str, tag: str) -> str:
    match = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", prompt, re.DOTALL)
    return match.group(1).strip() if match else ""


def build_llm(cfg: LlmConfig | None = None) -> LLM:
    cfg = cfg or llm_config()
    if cfg.provider in ("mock", "rules", ""):
        return RuleRepairLLM()
    if cfg.provider == "http":
        if not cfg.api_key:
            raise RuntimeError(
                "LLM_PROVIDER=http needs LLM_API_KEY. Use LLM_PROVIDER=mock to run "
                "without any key."
            )
        return HttpRepairLLM(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url or "https://api.groq.com/openai/v1",
        )
    raise RuntimeError(f"Unknown LLM_PROVIDER {cfg.provider!r} (use 'mock' or 'http')")
