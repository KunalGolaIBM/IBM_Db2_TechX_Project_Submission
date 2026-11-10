"""The headline banner: the two strongest measured results, each read from the published result files.

    python -m asof.headline        # regenerate src/asof/data/headline.json after an evaluation run

1. The frozen test splits (asof/eval FROZEN): wrong drafts released and correct drafts held, summed over the latest
   run of each split. "Latest" is the newest `started_at` among docs/eval/*.json runs of that split whose case file
   matches its pinned SHA-256, so a new run is picked up without naming any file.
2. The unseen railway policy (docs/eval/unseen): AsOf against the plain LLM judge on the first, final run, scored by the
   runner's own pre-registered metrics (asof/eval/unseen/run.py `score`) with the hand grades in grades.json.

A source checkout reads the files at startup; an installed package has no docs/ folder and reads the copy generated
into the package (data/headline.json, which a test keeps equal to the files). A missing or unreadable file drops only
the number it feeds: the banner never shows a figure it could not compute.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT

log = logging.getLogger(__name__)

EVAL_DIR = PROJECT_ROOT / "docs" / "eval"
GENERATED = Path(__file__).with_name("data") / "headline.json"
DOCS_URL = "https://github.com/JustJay7/asof/blob/main/docs/"
FROZEN_HREF = DOCS_URL + "evaluation.md#the-frozen-test-splits"
UNSEEN_HREF = DOCS_URL + "eval/unseen-results.md"
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}


def frozen_runs(eval_dir: Path = EVAL_DIR) -> dict[str, dict[str, Any]]:
    """The latest run of each frozen split: split -> {file, started_at, git_commit, overall summary, false blocks}."""
    from .eval import FROZEN

    latest: dict[str, dict[str, Any]] = {}
    for path in sorted(eval_dir.glob("*.json")):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            log.warning("headline: skipped unreadable %s", path.name)
            continue
        split = run.get("split") if isinstance(run, dict) else None
        if split not in FROZEN or run.get("cases_sha256") != FROZEN[split]:
            continue
        if split not in latest or run["started_at"] > latest[split]["started_at"]:
            latest[split] = {"file": path.name, "started_at": run["started_at"], "git_commit": run.get("git_commit"),
                             "overall": run["summary"]["overall"],
                             "false_block_decisions": sorted({r["decision"] for r in run["records"] if r["false_block"]})}
    return latest


def frozen_result(eval_dir: Path = EVAL_DIR) -> dict[str, Any] | None:
    """Totals over the latest run of every frozen split, or None unless every split has one."""
    from .eval import FROZEN

    runs = frozen_runs(eval_dir)
    if set(runs) != set(FROZEN):
        log.warning("headline: no frozen-split total (no run for %s)", ", ".join(sorted(set(FROZEN) - set(runs))))
        return None
    total = {k: sum(int(r["overall"][k]) for r in runs.values())
             for k in ("false_allows", "wrong_drafts", "false_blocks", "correct_drafts")}
    held = "held" if all(d == "ESCALATED" for r in runs.values() for d in r["false_block_decisions"]) else "stopped"
    n = len(runs)
    text = (f"{WORDS.get(n, str(n)).capitalize()} frozen test splits: {total['false_allows']} of "
            f"{total['wrong_drafts']} wrong drafts released, {total['false_blocks']} of {total['correct_drafts']} "
            f"correct ones {held}")
    short = (f"{n} frozen splits: {total['false_allows']}/{total['wrong_drafts']} wrong released, "
             f"{total['false_blocks']}/{total['correct_drafts']} correct {held}")
    return {"id": "frozen", "text": text, "short": short, "href": FROZEN_HREF, "splits": n, **total,
            "runs": {s: r["file"] for s, r in sorted(runs.items())}}


def unseen_result(eval_dir: Path = EVAL_DIR) -> dict[str, Any] | None:
    """AsOf against the plain LLM judge on the unseen policy's first run, or None if a file or a grade is missing."""
    from .eval.unseen.run import score

    folder = eval_dir / "unseen"
    try:
        runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("run-*.json"))]
        first = next(r for r in runs if r.get("first_run"))
        grades = json.loads((folder / "grades.json").read_text(encoding="utf-8")).get(f"run-{first['run']}", {})
        asof, plain = score(first["records"], grades, "asof"), score(first["records"], grades, "plain_judge")
    except (OSError, ValueError, StopIteration, KeyError) as exc:
        log.warning("headline: no unseen-domain result (%s)", type(exc).__name__)
        return None
    if asof["pending_grades"]:
        log.warning("headline: no unseen-domain result (%d rewrites not graded yet)", asof["pending_grades"])
        return None
    fa, fb, pfa, pfb = asof["false_allow"], asof["false_block"], plain["false_allow"], plain["false_block"]
    # A false block is a correct draft not sent as written: held, or (AsOf only) rewritten.
    held = "held" if asof["outcomes"]["correct"]["rewritten"] == 0 else "stopped"
    both = (f"both released {fa['k']} of {fa['n']} wrong ones" if (fa["k"], fa["n"]) == (pfa["k"], pfa["n"]) else
            f"AsOf released {fa['k']} of {fa['n']} wrong ones, the plain judge {pfa['k']} of {pfa['n']}")
    text = (f"Unseen railway policy: AsOf {held} {fb['k']} of {fb['n']} correct drafts, a plain LLM judge "
            f"{pfb['k']} of {pfb['n']}; {both}")
    short = f"Unseen policy: {fb['k']}/{fb['n']} correct {held}, plain LLM judge {pfb['k']}/{pfb['n']}"
    return {"id": "unseen", "text": text, "short": short, "href": UNSEEN_HREF, "run": first["run"],
            "git_commit": first.get("git_commit"),
            "asof": {"false_allows": fa["k"], "wrong_drafts": fa["n"], "false_blocks": fb["k"], "correct_drafts": fb["n"]},
            "plain_judge": {"false_allows": pfa["k"], "wrong_drafts": pfa["n"], "false_blocks": pfb["k"],
                            "correct_drafts": pfb["n"]}}


def compute(eval_dir: Path = EVAL_DIR) -> list[dict[str, Any]]:
    """Every banner item the files support, in banner order."""
    items = []
    makers: tuple[Callable[[Path], dict[str, Any] | None], ...] = (frozen_result, unseen_result)
    for make in makers:
        try:
            item = make(eval_dir)
        except Exception as exc:  # noqa: BLE001 - a malformed file drops its number, never the page
            log.warning("headline: %s failed (%s)", make.__name__, type(exc).__name__)
            item = None
        if item:
            items.append(item)
    return items


@lru_cache(maxsize=1)
def banner() -> list[dict[str, str]]:
    """What /healthz serves: [{id, text, short, href}], from the result files if this is a source checkout, else from the
    copy generated into the package. Read once per process."""
    if EVAL_DIR.is_dir():
        items = compute(EVAL_DIR)
    else:
        try:
            items = json.loads(GENERATED.read_text(encoding="utf-8"))["items"]
        except (OSError, ValueError, KeyError):
            log.warning("headline: no result files and no %s", GENERATED.name)
            items = []
    return [{"id": i["id"], "text": i["text"], "short": i["short"], "href": i["href"]} for i in items]


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    items = compute()
    GENERATED.write_text(json.dumps({"note": "Generated by `python -m asof.headline` from docs/eval; do not edit.",
                                     "items": items}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for i in items:
        print(f"{i['id']}: {i['text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
