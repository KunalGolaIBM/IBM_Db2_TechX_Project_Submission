"""Fuzz the Db2 guardrails with random proposals and write docs/guardrail_fuzz.md (no LLM needed).

    python src/fuzz_guardrails.py            # 10,000 proposals, seed 7
    python src/fuzz_guardrails.py 50000 42   # more proposals, another seed

Every proposal goes to SP_PROPOSE_ACTION with the agent's own credentials, and every decision is compared
with an independent Python oracle of the business rules. One transaction, rolled back: nothing is persisted.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hotelops.fuzz import run_fuzz  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "guardrail_fuzz.md"


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 7
    r = run_fuzz(n, seed)
    lines = [
        "# Guardrail fuzz: Db2 against an independent oracle",
        "",
        f"**{r['agree']:,} / {r['proposals']:,} decisions agree** · seed {r['seed']} · {r['seconds']} s · "
        f"run {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC · no LLM · one transaction, rolled back.",
        "",
        "Random agent proposals (valid ones, near-misses on every boundary: rate exactly at the floor and "
        "ceiling and one paisa outside, today, today+90 and today+91, end before start, unknown room types and "
        "rooms, over-long fields, opted-out guests, inactive reservations, bad priorities, malformed JSON, unknown "
        "action types and exact repeats) are sent to `SP_PROPOSE_ACTION` with the **agent's own Db2 "
        "credentials**. Each Db2 decision (PENDING, REJECTED or DUPLICATE) is compared with a Python oracle "
        "written from the business rules, not from the SQL.",
        "",
        f"| Outcome | Count |\n|---|---|\n| Rejected by Db2 | {r['rejected']:,} |\n"
        f"| Accepted (queued for a human) | {r['accepted']:,} |\n| Duplicate detected | {r['duplicates']:,} |",
        "",
        "| Category | Proposals |",
        "|---|---|",
        *[f"| {k} | {v:,} |" for k, v in sorted(r["by_category"].items(), key=lambda kv: -kv[1])],
        "",
        "**What it found:** the first run crashed the procedure with `SQL0137N` on an over-long field "
        "(`\"to_room_type_code\": \"PENTHOUSE\"`). Db2 failed closed (nothing was created), but the agent got a "
        "raw error instead of a clean `REJECTED`. The procedure now reads fields into wide variables and "
        "validates them; `test_guardrail_rejects_over_long_fields_cleanly` keeps it fixed.",
        "",
        "Reproduce with `python src/fuzz_guardrails.py` (or `python src/verify.py`, which runs 1,000).",
    ]
    if r["mismatches"]:
        lines += ["", "## Disagreements", "", *[f"- `{m}`" for m in r["mismatches"]]]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{r['agree']:,}/{r['proposals']:,} decisions agree in {r['seconds']} s -> {OUT}")
    return 0 if r["agree"] == r["proposals"] else 1


if __name__ == "__main__":
    sys.exit(main())
