"""Small, dependency-free NLU helpers: slot extraction, slot-aware cache adaptation, domain gate."""
import re

CITIES = ["Hyderabad", "Mumbai", "Delhi", "Chennai", "Kolkata", "Pune", "Bengaluru", "Jaipur"]
REGIONS = ["NORTH", "SOUTH", "EAST", "WEST"]
_WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
            "ten": 10, "fifteen": 15, "twenty": 20}
ENTITY = re.compile(r"\b(customers?|clients?|accounts?|balances?|transactions?|txns?|loans?|branch(?:es)?|fraud\w*|"
                    r"flagged|defaults?|defaulted|npa|merchants?|channels?|volume|payments?|spend\w*|deposits?|upi|"
                    r"card|netbank|atm|regions?|segments?|bank\w*|borrowers?|amount)\b", re.I)
FOLLOWUP = re.compile(r"\b(them|those|these|that|same|again|instead|also|only|filter|narrow|but|what about|how about|and for|and in)\b", re.I)
PREP_SLOT = re.compile(r"\s*(in|for|at|from)\s+[A-Za-z]+\s*\??\s*$", re.I)  # e.g. "in Jaipur"


def extract(q: str) -> dict:
    """Pull constraints (N, cities, regions) out of a question."""
    ql = q.lower()
    n = None
    words = "|".join(_WORDNUM)
    m = (re.search(rf"\b(?:top|first|best|bottom|last|highest|lowest|worst)\s+(\d{{1,3}}|{words})\b", ql)
         or re.search(r"\b(\d{1,3})\s+(?:customers?|accounts?|branch(?:es)?|loans?|transactions?|merchants?|rows|results|categories)\b", ql))
    if m:
        t = m.group(1)
        n = int(t) if t.isdigit() else _WORDNUM[t]
        if not 1 <= n <= 200:
            n = None
    return {"n": n,
            "cities": [c for c in CITIES if re.search(rf"\b{c.lower()}\b", ql)],
            "regions": [r for r in REGIONS if re.search(rf"\b{r.lower()}\b", ql)]}


def adapt(sql: str, cached_q: str, new_q: str):
    """Reuse cached SQL only if the new question's constraints can be applied safely; else None (cache miss)."""
    a, b = extract(cached_q), extract(new_q)
    if a == b:
        return sql
    out = sql
    if a["n"] != b["n"]:
        if a["n"] is None or b["n"] is None or not re.search(r"FETCH FIRST \d+ ROWS ONLY", out):
            return None
        out = re.sub(r"FETCH FIRST \d+ ROWS ONLY", f"FETCH FIRST {b['n']} ROWS ONLY", out, count=1)
    if a["cities"] != b["cities"]:
        if len(a["cities"]) == 1 and len(b["cities"]) == 1 and f"'{a['cities'][0]}'" in out:
            out = out.replace(f"'{a['cities'][0]}'", f"'{b['cities'][0]}'")
        else:
            return None
    if a["regions"] != b["regions"]:
        if len(a["regions"]) == 1 and len(b["regions"]) == 1 and f"'{a['regions'][0]}'" in out:
            out = out.replace(f"'{a['regions'][0]}'", f"'{b['regions'][0]}'")
        else:
            return None
    return out


def _has_slot(q):
    s = extract(q)
    return bool(s["n"] or s["cities"] or s["regions"])


def is_followup(q: str, has_history: bool) -> bool:
    """A context-dependent turn such as 'Filter them by Jaipur'."""
    # a city/number alone is NOT enough ("weather in Delhi"): we need an explicit follow-up cue
    return has_history and not ENTITY.search(q) and bool(FOLLOWUP.search(q) or (PREP_SLOT.fullmatch(q) and _has_slot(q)))


def in_domain(q: str, has_history: bool = False) -> bool:
    """Proactive out-of-domain gate: needs a banking-data entity, or be a follow-up to a previous data question."""
    return bool(ENTITY.search(q)) or is_followup(q, has_history)
