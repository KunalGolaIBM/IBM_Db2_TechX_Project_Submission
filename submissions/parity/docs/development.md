# Development guide

Simple rules for working on Parity. Read this before you open a pull request.

## Code style

- Python 3.11 or later.
- Type hints on all public functions.
- Small functions. One job each.
- No em dashes in code or docs. Use a hyphen `-` or a full stop.
- No emojis in code, docs, or commit messages.
- Run `ruff check src tests` and fix all warnings.
- Run `pytest` and keep it green.

## Branches

- `main` is the stable branch. Do not commit to it directly.
- One branch per feature. Use this pattern:

  - `feat/...` for a new feature. Example: `feat/parity-engine`.
  - `fix/...` for a bug fix. Example: `fix/float-tolerance`.
  - `docs/...` for docs only. Example: `docs/setup-guide`.
  - `chore/...` for setup and tooling. Example: `chore/project-setup`.
  - `test/...` for tests only. Example: `test/golden-suite`.

- Do not merge branches yourself during development. The owner merges them.
- Push every branch to the remote so it can be reviewed.
- After a branch is pushed, wait for review confirmation before starting the next branch.

## Commits

- Keep commits small. One clear change per commit.
- Commit message style: `type: short summary`.
- Types: `feat`, `fix`, `docs`, `test`, `chore`, `refactor`.
- Do not use em dashes or emojis in commit messages.
- Do not commit secrets, `.env` files, production data, or generated reports.

## Logs

Keep a log of what you did. Record:

- Commands you ran.
- Packages you installed or uninstalled, with exact versions.
- Files you created or changed, and why.
- Errors you hit and how you fixed them.
- Test results.

The local log lives in the `memory/logs/` folder. That folder is not pushed to GitHub. Update it as you work.

## What never goes in a commit

- Real API keys or passwords.
- Production data rows.
- The local `memory/` folder.
- Generated HTML or JSON reports.
- `__pycache__` folders or virtual environments.

## Before you push

1. Run `ruff check src tests`.
2. Run `pytest`.
3. Check `git status` and review what will be committed.
4. Check docs and README for simple English. No high level words where a plain word works.
