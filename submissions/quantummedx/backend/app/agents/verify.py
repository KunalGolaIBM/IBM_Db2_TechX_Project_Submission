"""Guardrail: any number in agent-written text must match a number stored in Db2."""
import re

_NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(%?)")


def allowed_numbers(results: list, extra: dict | None = None) -> set:
    vals = []
    for r in results:
        for k in ("accuracy", "precision_score", "recall", "f1_score", "roc_auc", "train_seconds", "infer_seconds", "experiment_id"):
            if r.get(k) is not None:
                vals.append(float(r[k]))
    vals += [float(v) for v in (extra or {}).values() if isinstance(v, (int, float))]
    out = set()
    for v in vals:
        for d in (0, 1, 2, 3, 4):
            out.add(round(v, d))
            out.add(round(v * 100, d))  # percent form
    return out


def unverified_numbers(text: str, allowed: set) -> list:
    bad = []
    for num, pct in _NUM.findall(text):
        v = float(num)
        if v in allowed or round(v, 2) in allowed or round(v, 3) in allowed:
            continue
        if not pct and v == int(v) and v < 20:  # small counts such as "5 agents", "step 3"
            continue
        bad.append(num + pct)
    return bad
