"""Run the red-team scoreboard against the live Db2 and write docs/redteam_results.md (no LLM needed).

    python src/redteam.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hotelops.redteam import run_redteam  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "redteam_results.md"


def main() -> None:
    res = run_redteam(lambda a: print(f"  [{'BLOCKED' if a.blocked else 'NOT BLOCKED'}] #{a.id} {a.attack} "
                                       f"-> {a.layer}: {a.evidence}"))
    lines = [
        "# Red-team scoreboard",
        "",
        f"**{res['blocked']}/{res['total']} attacks blocked** · run {res['run_at']} · no LLM involved · "
        "every attack runs in a transaction that is rolled back.",
        "",
        "Most attacks bypass the application on purpose and use the agent's own Db2 credentials, to show that "
        "the guarantees come from Db2 (privileges, RCAC, SQL PL guardrails), not from Python or the prompt. "
        "Reproduce with `python src/redteam.py`, or the 🛡️ Red team tab in the app.",
        "",
        "| Blocked by | Attacks |",
        "|---|---|",
        *[f"| {layer} | {count} |" for layer, count in sorted(res["by_layer"].items(), key=lambda x: -x[1])],
        "",
        "| # | Category | Attack | Result | Stopped by | Evidence |",
        "|---|---|---|---|---|---|",
        *[f"| {a['id']} | {a['category']} | {a['attack']} | {'🛡️ blocked' if a['blocked'] else '❌ NOT blocked'} | "
          f"{a['layer']} | `{a['evidence'].replace('|', '/')}` |" for a in res["attacks"]],
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)  # docs/ is not shipped in the Docker image
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    OUT.with_suffix(".json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"\n{res['blocked']}/{res['total']} attacks blocked -> {OUT}")
    sys.exit(0 if res["blocked"] == res["total"] else 1)


if __name__ == "__main__":
    main()
