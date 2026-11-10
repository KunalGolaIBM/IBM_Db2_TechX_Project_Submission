"""Deterministic verifier for the LLM triage memo (owner: app agent).

The memo is untrusted model output. The verifier keeps a sentence only when the SQL results support it.
Units are bullets and sentences; a bullet with several sentences loses only the failing sentences.
No model is involved; the same input gives the same output.

Normalization (review M1): NFKC (fullwidth letters -> ASCII), every Unicode dash -> '-'. Names match with
case, spaces, '_' and '-' ignored ("payments api" = "payments-api"; "python_multipart" = "python-multipart").

A sentence is removed when:
1. ids      it names an advisory id (strict or loose form, e.g. "CVE 2099 12345") whose canonical form is not
            a retrieved advisory or alias;
2. entities it names a known package or service that is not in the SQL results;
3. negative it makes a negative / safety claim (safe, not affected, isn't vulnerable, does not need a patch,
            no action needed, can be ignored, ...). NEEDLE confirms only AFFECTED; nothing is ever "safe".
            The remediation phrase "upgrade to a version not vulnerable" is rewritten first and stays allowed;
4. status   it names a service and the status it asserts for that service (the nearest claim word:
            AFFECTED / vulnerable / exposed -> AFFECTED; NOT_CONFIRMED; PREVIOUSLY_AFFECTED / was affected ->
            PREVIOUSLY_AFFECTED; no longer exposed -> previously and not now) disagrees with the SQL status,
            or it names a service without any status claim (cannot be grounded) (review H1);
5. payload  it contains a URL, a shell or package-manager command, or a package-like token that is not in
            the evidence (pinned "name==1.2" or a typosquat of a known package such as "pyyaml-secure-loader")
            (review M2);
6. numbers  it states a duration ("2,448 days", "over 900 days", "6 years", "18 months") that does not match a
            DAYS_EXPOSED value of the services it names (or of any exposure row when it names none). Days must
            match within 1 day; weeks within 1 week; months and years within 1 unit. A memo once said "over 900
            days" for a 2,448-day exposure; that sentence is now removed.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Iterable

from needle.sbom import SERVICES, UPGRADE_PATHS, normalize_pkg

# --- normalization -------------------------------------------------------------------------------------------
_DASHES = re.compile(r"[‐‑‒–—―−⁃﹘﹣－­]")


def normalize_text(text: str) -> str:
    """NFKC + ASCII hyphen for every Unicode dash (fullwidth letters and look-alike dashes cannot hide ids)."""
    return _DASHES.sub("-", unicodedata.normalize("NFKC", text or ""))


def name_key(name: str) -> str:
    """Comparison key for service/package names: lower case, no spaces, '_', '-' or '.'."""
    return re.sub(r"[\s_.\-]+", "", name.lower())


def _name_regex(name: str) -> re.Pattern:
    """Match ``name`` with any run of space/_/-/. between its parts, case-insensitive, as a whole word."""
    parts = [re.escape(p) for p in re.split(r"[\s_.\-]+", name.lower()) if p]
    return re.compile(r"(?<![A-Za-z0-9])" + r"[\s_.\-]*".join(parts) + r"(?![A-Za-z0-9])", re.IGNORECASE)


# --- advisory ids --------------------------------------------------------------------------------------------
# Strict: GHSA 4-4-4 (loose charset also catches fabricated ids such as GHSA-fake-1234-abcd) and PREFIX-YYYY-N.
ADV_ID_RE = re.compile(
    r"\b(?:GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}|[A-Z][A-Z0-9]{1,9}-\d{4}-[0-9A-Za-z][0-9A-Za-z.-]*[0-9A-Za-z])\b",
    re.IGNORECASE,
)
# Loose: known prefixes with any separator run (space, '_', '-', '.'), e.g. "CVE 2099 12345", "GHSA aaaa_bbbb cccc".
LOOSE_ID_RE = re.compile(
    r"\b(GHSA|CVE|PYSEC|OSV|MAL|GSD)[\s_.\-]+(?:([0-9a-z]{4})[\s_.\-]+([0-9a-z]{4})[\s_.\-]+([0-9a-z]{4})"
    r"|(\d{4})[\s_.\-]+(\d+))\b",
    re.IGNORECASE,
)
SERVICE_ID_RE = re.compile(r"\bSVC[\s_\-]*\d{1,4}\b", re.IGNORECASE)


def _ids_in(unit: str) -> dict[str, str]:
    """canonical id (upper case, '-' separators) -> the text as written."""
    ids = {m.group(0).upper(): m.group(0) for m in ADV_ID_RE.finditer(unit)}
    for m in LOOSE_ID_RE.finditer(unit):
        pre = m.group(1).upper()
        canon = (f"{pre}-{m.group(2)}-{m.group(3)}-{m.group(4)}".upper() if m.group(2)
                 else f"{pre}-{m.group(5)}-{m.group(6)}")
        ids.setdefault(canon, m.group(0))
    return {k: v for k, v in ids.items() if not k.startswith("SVC-")}


# --- claims --------------------------------------------------------------------------------------------------
_CUE = r"(?:affected|vulnerable|exposed|impacted|at\s+risk|susceptible|exploitable|compromised)"
_REMEDIATION = re.compile(  # "upgrade ... to a version not vulnerable to X" is advice, not a safety claim
    r"\b(?:a|an|the)?\s*(?:newer\s+|fixed\s+|patched\s+|later\s+|safer\s+)?(?:version|release)s?\s+"
    r"(?:that\s+(?:is|are)\s+)?(?:not|no\s+longer)\s+" + _CUE + r"(?:\s+(?:to|by)\s+[^.;:]*)?",
    re.IGNORECASE)
_MARKERS: list[tuple[str, re.Pattern]] = [  # applied in order; each match becomes one claim marker
    ("PAST", re.compile(r"\bPREVIOUSLY[\s_]+AFFECTED\b", re.IGNORECASE)),
    ("UC", re.compile(r"\bUNKNOWN[\s_]+COVERAGE\b", re.IGNORECASE)),
    ("NC", re.compile(r"\bNOT[\s_]+CONFIRMED\b|\bunconfirmed\b", re.IGNORECASE)),
    ("PASTONLY", re.compile(r"\bno\s+longer\s+(?:\w+\s+)?" + _CUE + r"\b", re.IGNORECASE)),
    ("NEG", re.compile(
        r"(?:\b(?:not|never|no|nor|neither)|n['’]t)\s+(?:\w+\s+){0,2}?" + _CUE + r"\b"
        r"|\bunaffected\b|\bsafe\b|\bimmune\b|\bin\s+the\s+clear\b"
        r"|\b(?:is|are|remains?|stays?|considered|deemed)\s+(?:now\s+|still\s+|fully\s+)?(?:secure|clean)\b"
        r"|(?:\b(?:does|do|did)\s+not|\b(?:does|do|did)n['’]t|\bneed\s+not|\bneedn['’]t)\s+"
        r"(?:\w+\s+){0,2}?(?:need|require)"
        r"|\bno\s+(?:action|patch|fix|upgrade|update|remediation)s?\s+(?:is\s+|are\s+)?"
        r"(?:needed|required|necessary)"
        r"|\b(?:can|may)\s+(?:be\s+)?(?:safely\s+)?ignored?\b|\bnothing\s+to\s+(?:do|fix|patch)\b",
        re.IGNORECASE)),
    ("PAST", re.compile(r"\b(?:was|were|previously|formerly|had\s+been)\s+(?:\w+\s+)?" + _CUE + r"\b"
                        r"|\b(?:was|were|been|got)\s+(?:fixed|patched|remediated|upgraded)\b", re.IGNORECASE)),
    ("AFF", re.compile(r"\b" + _CUE + r"\b", re.IGNORECASE)),
]
CLAIM_WORD = {"AFF": "AFFECTED", "NC": "NOT_CONFIRMED", "UC": "UNKNOWN_COVERAGE", "PAST": "PREVIOUSLY_AFFECTED",
              "PASTONLY": "no longer affected", "NEG": "not affected / safe"}


def claim_markers(unit: str) -> list[tuple[int, str]]:
    """(position, claim) for every status claim in ``unit``, after the remediation rewrite."""
    # same-length rewrite keeps marker positions aligned with the service positions in ``unit``
    s = _REMEDIATION.sub(lambda m: ("a fixed version" + " " * len(m.group(0)))[:len(m.group(0))], unit)
    spans: list[tuple[int, int, str]] = []
    for kind, rx in _MARKERS:
        for m in rx.finditer(s):
            if not any(a < m.end() and m.start() < b for a, b, _ in spans):
                spans.append((m.start(), m.end(), kind))
    return sorted((a, k) for a, _, k in spans)


def _fmt(statuses: set[str]) -> str:
    return "/".join(sorted(x for x in statuses if x)) or "unknown"


def _supports(claim: str, statuses: set[str]) -> bool:
    if claim == "AFF":
        return "AFFECTED" in statuses
    if claim == "NC":
        return "NOT_CONFIRMED" in statuses
    if claim == "UC":
        return "UNKNOWN_COVERAGE" in statuses
    if claim == "PAST":
        return "PREVIOUSLY_AFFECTED" in statuses
    if claim == "PASTONLY":
        return "PREVIOUSLY_AFFECTED" in statuses and "AFFECTED" not in statuses
    return False  # NEG is never supported


# --- payloads (M2) -------------------------------------------------------------------------------------------
URL_RE = re.compile(r"https?://|\bwww\.|\b[a-z0-9-]+\.(?:com|net|org|io|dev|xyz|ru|cn|example)(?:/|\b)", re.I)
COMMAND_RE = re.compile(
    r"\b(?:pip3?|pipx|curl|wget|bash|zsh|sh|npm|npx|yarn|pnpm|apt(?:-get)?|brew|conda|choco|powershell|iex|"
    r"sudo|chmod|python3?\s+-m\s+pip|uv\s+pip)\b\s+\S|\binstall\b|`[^`]*\b(?:rm|curl|wget|pip)\b[^`]*`", re.I)
PINNED_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9._-]*)\s*(?:==|>=|<=|~=|!=)\s*\d")
VERSION_PART_RE = re.compile(r"^v?\d[\d.]*[a-z0-9]*$")
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9]|[A-Za-z0-9]")

# --- durations (rule 6) --------------------------------------------------------------------------------------
DURATION_RE = re.compile(
    r"(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*\+?\s*-?\s*(days?|weeks?|months?|years?|yrs?)\b", re.I)


def _duration_matches(n: float, unit_word: str, days: int) -> bool:
    if unit_word.startswith("day"):
        return abs(n - days) <= 1
    if unit_word.startswith("week"):
        return abs(n * 7 - days) <= 7
    if unit_word.startswith("month"):
        return abs(n - days / 30.44) < 1
    return abs(n - days / 365.25) < 1  # years


@dataclass
class Evidence:
    """What the SQL results contain. ids upper case; packages PEP 503; service keys from ``name_key``."""
    adv_ids: set[str] = field(default_factory=set)
    packages: set[str] = field(default_factory=set)
    services: dict[str, set[str]] = field(default_factory=dict)  # name_key(name or id) -> statuses
    rel: dict[tuple[str, str], set[str]] = field(default_factory=dict)  # (service key, ADV_ID) -> statuses
    pkg_rel: dict[tuple[str, str], set[str]] = field(default_factory=dict)  # (service key, package) -> statuses
    alias_ids: dict[str, set[str]] = field(default_factory=dict)  # id or alias (upper) -> retrieved ADV_IDs
    known_packages: set[str] = field(default_factory=set)
    known_services: set[str] = field(default_factory=set)  # display names and ids (lower case)
    days: dict[str, set[int]] = field(default_factory=dict)  # service key -> DAYS_EXPOSED values
    all_days: set[int] = field(default_factory=set)
    _svc_rx: list[tuple[str, re.Pattern]] = field(default_factory=list, repr=False)
    _pkg_rx: list[tuple[str, re.Pattern]] = field(default_factory=list, repr=False)

    def compile(self) -> "Evidence":
        self._svc_rx = [(s, _name_regex(s)) for s in sorted(self.known_services, key=len, reverse=True)]
        self._pkg_rx = [(p, _name_regex(p)) for p in sorted(self.known_packages, key=len, reverse=True)]
        return self


@dataclass
class Removed:
    text: str
    reasons: list[str]


@dataclass
class VerifyResult:
    text: str
    removed: list[Removed]
    kept: int

    @property
    def removed_count(self) -> int:
        return len(self.removed)


def _pkg_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        value = re.split(r"[\s,;]+", value)
    return [normalize_pkg(v) for v in value if v and v.strip()]


def build_evidence(advisories: Iterable[dict], exposure_rows: Iterable[dict],
                   known_packages: Iterable[str] = (), known_services: Iterable[str] = ()) -> Evidence:
    """Collect the allowed entities from retrieved advisories and exposure rows.

    advisories: dicts with adv_id, optional aliases (list), optional packages (list or str).
    exposure_rows: dicts with SERVICE, SERVICE_ID, PACKAGE, STATUS, ADV_ID (sbom.EXPOSURE_COLUMNS).
    known_*: the detection universe; the fleet and the upgrade-path packages are always included.
    """
    ev = Evidence()
    for a in advisories:
        if not a.get("adv_id"):
            continue
        aid = normalize_text(a["adv_id"]).upper()
        ev.adv_ids.add(aid)
        ev.alias_ids.setdefault(aid, set()).add(aid)
        for al in a.get("aliases") or []:
            al = normalize_text(str(al)).upper()
            ev.adv_ids.add(al)
            ev.alias_ids.setdefault(al, set()).add(aid)
        ev.packages.update(_pkg_list(a.get("packages")))
    names: set[str] = set()
    for r in exposure_rows:
        rid = normalize_text(r["ADV_ID"]).upper() if r.get("ADV_ID") else None
        if rid:
            ev.adv_ids.add(rid)
            ev.alias_ids.setdefault(rid, set()).add(rid)
        pkg = normalize_pkg(r["PACKAGE"]) if r.get("PACKAGE") else None
        if pkg:
            ev.packages.add(pkg)
        status = r.get("STATUS") or ""
        try:
            days = int(r["DAYS_EXPOSED"]) if r.get("DAYS_EXPOSED") is not None else None
        except (TypeError, ValueError):
            days = None
        if days is not None:
            ev.all_days.add(days)
        for key in ("SERVICE", "SERVICE_ID"):
            if r.get(key):
                names.add(str(r[key]).lower())
                sk = name_key(str(r[key]))
                ev.services.setdefault(sk, set()).add(status)
                if days is not None:
                    ev.days.setdefault(sk, set()).add(days)
                if rid:
                    ev.rel.setdefault((sk, rid), set()).add(status)
                if pkg:
                    ev.pkg_rel.setdefault((sk, pkg), set()).add(status)
    ev.known_packages = ({normalize_pkg(p) for p in known_packages} | set(UPGRADE_PATHS) | ev.packages)
    ev.known_services = ({s.lower() for s in known_services} | {s.name.lower() for s in SERVICES}
                         | {s.service_id.lower() for s in SERVICES} | names)
    return ev.compile()


def _find(unit: str, rx_list: list[tuple[str, re.Pattern]]) -> list[tuple[int, int, str]]:
    """Non-overlapping (start, end, name) matches, longest names first."""
    out: list[tuple[int, int, str]] = []
    for name, rx in rx_list:
        for m in rx.finditer(unit):
            if not any(a < m.end() and m.start() < b for a, b, _ in out):
                out.append((m.start(), m.end(), name))
    return sorted(out)


def check_unit(unit: str, ev: Evidence) -> list[str]:
    """Reasons to remove ``unit`` (empty list = keep). ``unit`` must already be normalize_text()-ed."""
    if not ev._svc_rx:
        ev.compile()
    reasons: list[str] = []

    # 1. advisory ids (strict + loose forms, canonicalized)
    for aid, shown in sorted(_ids_in(unit).items()):
        if aid not in ev.adv_ids:
            reasons.append(f"advisory id {shown} is not in the SQL results" + ("" if shown == aid else f" ({aid})"))

    # 2. entities
    svc_hits = _find(unit, ev._svc_rx)
    for m in SERVICE_ID_RE.finditer(unit):
        if not any(a <= m.start() < b for a, b, _ in svc_hits):
            svc_hits.append((m.start(), m.end(), m.group(0)))
    svc_hits.sort()
    svc_spans = [(a, b) for a, b, _ in svc_hits]
    pkg_hits = [h for h in _find(unit, ev._pkg_rx) if not any(a < h[1] and h[0] < b for a, b in svc_spans)]
    for _, _, s in svc_hits:
        if name_key(s) not in ev.services:
            reasons.append(f"service {s.lower()} is not in the exposure results")
    for _, _, p in pkg_hits:
        if normalize_pkg(p) not in ev.packages:
            reasons.append(f"package {normalize_pkg(p)} is not in the SQL results")

    # 3 + 4. claims
    markers = claim_markers(unit)
    if any(k == "NEG" for _, k in markers):
        reasons.append("negative or safety claim: NEEDLE confirms only AFFECTED; others are NOT_CONFIRMED, "
                       "never safe")
    ids_here = [(c, shown) for c, shown in sorted(_ids_in(unit).items()) if c in ev.adv_ids]
    pkgs_here = sorted({normalize_pkg(p) for _, _, p in pkg_hits if normalize_pkg(p) in ev.packages})
    for start, end, s in svc_hits:
        sk = name_key(s)
        statuses = ev.services.get(sk)
        if statuses is None:
            continue  # already reported as unknown
        after = [k for pos, k in markers if pos >= end]
        before = [k for pos, k in markers if pos < start]
        claim = after[0] if after else (before[-1] if before else None)
        if claim is None:
            reasons.append(f"names {s.lower()} without a status claim (cannot be grounded; SQL status is "
                           f"{_fmt(statuses)})")
            continue
        if claim == "NEG":
            continue  # already reported
        if not _supports(claim, statuses):
            reasons.append(f"says {s.lower()} is {CLAIM_WORD[claim]} but its SQL status is {_fmt(statuses)}")
            continue
        # Relationships (review B): the claim must hold for the exact (service, advisory) and (service, package)
        # rows, not just for the service in general.
        for canon, shown in ids_here:
            rel = set().union(*(ev.rel.get((sk, r), set()) for r in ev.alias_ids.get(canon, {canon})))
            if not _supports(claim, rel):
                reasons.append(f"says {s.lower()} is {CLAIM_WORD[claim]} for {shown} but the SQL row for that pair "
                               f"is {_fmt(rel) if rel else 'absent'}")
        for p in pkgs_here:
            rel = ev.pkg_rel.get((sk, p), set())
            if not _supports(claim, rel):
                reasons.append(f"says {s.lower()} is {CLAIM_WORD[claim]} via {p} but the SQL row for that pair "
                               f"is {_fmt(rel) if rel else 'absent'}")

    # 6. durations must match the SQL day counts
    named = {name_key(s) for _, _, s in svc_hits if name_key(s) in ev.days}
    allowed = set().union(*(ev.days[k] for k in named)) if named else ev.all_days
    for m in DURATION_RE.finditer(unit):
        n = float(m.group(1).replace(",", ""))
        unit_word = m.group(2).lower()
        if not any(_duration_matches(n, unit_word, d) for d in allowed):
            reasons.append(f"states {m.group(0).strip()} but the SQL day count is "
                           + (", ".join(f"{d:,} days" for d in sorted(allowed)) if allowed else "absent"))

    # 5. payloads from untrusted advisory text
    if URL_RE.search(unit):
        reasons.append("contains a URL (untrusted advisory text)")
    if COMMAND_RE.search(unit):
        reasons.append("contains a shell or package-manager command (untrusted advisory text)")
    known_keys = {name_key(p) for p in ev.known_packages} | {name_key(s) for s in ev.known_services}
    flagged: set[str] = set()
    for m in PINNED_RE.finditer(unit):
        if normalize_pkg(m.group(1)) not in ev.packages:
            flagged.add(normalize_pkg(m.group(1)))
    for m in TOKEN_RE.finditer(unit):
        tok = m.group(0)
        if "-" not in tok and "_" not in tok:
            continue  # dotted module paths (django.contrib.admin) are not package names
        parts = [p for p in re.split(r"[_\-]+", tok.lower()) if p]
        while parts and VERSION_PART_RE.match(parts[-1]):
            parts.pop()  # "PyYAML-5.3" is a package plus a version
        if len(parts) < 2 or name_key("-".join(parts)) in known_keys or normalize_pkg("-".join(parts)) in ev.packages:
            continue
        if any(normalize_pkg("-".join(parts[i:j])) in ev.known_packages
               for i in range(len(parts)) for j in range(i + 1, len(parts) + 1) if (i, j) != (0, len(parts))):
            flagged.add(normalize_pkg("-".join(parts)))  # typosquat shape: a known package plus extra parts
    for f in sorted(flagged):
        reasons.append(f"package-like token {f} is not in the SQL results")
    return reasons


BULLET_RE = re.compile(r"^(\s*(?:[-*•]|\d+[.)])\s+)(.*)$")
SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[(`*\"'])")


def verify_memo(memo: str, ev: Evidence) -> VerifyResult:
    """Remove unsupported sentences/bullets from ``memo``; report each removal with its reasons."""
    kept_lines: list[str] = []
    removed: list[Removed] = []
    kept = 0
    for line in normalize_text(memo).splitlines():
        if not line.strip():
            if kept_lines and kept_lines[-1] != "":
                kept_lines.append("")
            continue
        m = BULLET_RE.match(line)
        prefix, body = (m.group(1), m.group(2)) if m else ("", line)
        good: list[str] = []
        for sent in SENT_SPLIT_RE.split(body.strip()):
            if not sent.strip():
                continue
            reasons = check_unit(sent, ev)
            if reasons:
                removed.append(Removed(sent.strip(), reasons))
            else:
                good.append(sent.strip())
                kept += 1
        if good:
            kept_lines.append(prefix + " ".join(good))
    return VerifyResult(text="\n".join(kept_lines).strip(), removed=removed, kept=kept)
