# Knowledge base review

## What it does

Agents add new knowledge as unverified candidates. Search never returns a candidate. A human approves or rejects each one. This is the review surface.

## Usage

```bash
parity kb-review --action list
parity kb-review --action approve --title "ILIKE upper like"
parity kb-review --action reject --title "candidate only"
parity kb-review --action list --store db2
```

- `--action list` shows unverified candidates. The title sits on its own line, so it can be copied into an approve or reject command.
- `--action approve` marks one candidate verified. Verified entries cannot be rejected later.
- `--action reject` removes one unverified candidate.
- `--store memory` is the default. `--store db2` writes to the Db2 knowledge base tables. On Windows the Db2 side goes through the bridge container, because the Windows ibm_db driver fails with SQL1042C. The bridge binds the parameters, so the values never become part of the SQL text. See docs/bridge-admin.md.

Exit codes: 0 on success, 2 on any error such as an unknown title or a rejected attempt on a verified entry.

## Rules

- Unknown titles fail with a clear error.
- Approving an entry that is already verified fails with a clear error.
- Verified entries cannot be rejected.
- Approve makes the entry searchable on the next search.
- Reject removes the candidate with no trace, because it was never shared.

## How a lesson gets here

A run that matched a rewritten query proves that the rewrite works. The capture step stores it as a candidate. See docs/kb-capture.md.

## Where the code lives

- `src/parity/kb/review.py` holds the action logic. It is store agnostic and returns text, so tests cover it without a CLI.
- `src/parity/cli.py` wires the `kb-review` command and maps errors to exit code 2.
- `src/parity/kb/store.py` holds the stores. The Db2 store works with either admin client.
- `list_candidates()` was added to the `KbStore` interface, `InMemoryKb`, and `Db2Kb`.
