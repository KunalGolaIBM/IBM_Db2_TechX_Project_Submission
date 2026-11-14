"""Register the language model inside Db2, so the engine makes the calls.

    python -m src.setup_model            # register, compile ASK_MODEL, probe it
    python -m src.setup_model --drop     # remove the model and the procedure

After this, ``LLM_TRANSPORT=db2`` routes every model call through
``PORTPROOF.ASK_MODEL``. What that changes:

* The API key is given to Db2 once, here, by the schema owner. It is stored in
  the catalogue and no catalogue view returns it. The application's runtime
  identity never holds it.
* The runtime identity holds no USAGE on the model. Its only road to a model is
  the procedure, and the procedure writes the cost ledger in the same breath,
  so an unrecorded model call is not something the application can make.
* The call budget is enforced by the engine counting its own ledger.

The key is read from the environment and bound into one DDL statement. It is
never printed and never written to a file.
"""
from __future__ import annotations

import argparse

from . import db
from .config import llm_config, setup_config
from .setup_db import SQL_DIR

MODEL = "PORTPROOF.PP_MODEL"
_PROBE = "Reply with the single word OK."


def _quote(value: str) -> str:
    """A SQL string constant. CREATE EXTERNAL MODEL takes no parameter markers."""
    if "\x00" in value:
        raise ValueError("NUL byte in a model setting")
    return "'" + value.replace("'", "''") + "'"


def _drop(conn) -> None:
    for sql in ("DROP PROCEDURE PORTPROOF.ASK_MODEL", f"DROP EXTERNAL MODEL {MODEL}"):
        try:
            db.execute(conn, sql)
        except db.Db2Error as exc:
            if exc.sqlcode != -204:
                raise


def _create(conn, cfg, options: str) -> None:
    url = cfg.base_url.rstrip("/") + "/chat/completions"
    db.execute(
        conn,
        f"CREATE EXTERNAL MODEL {MODEL} PROVIDER OPENAI ID {_quote(cfg.model)} "
        f"URL {_quote(url)} TYPE TEXT_GENERATION RETURNING CLOB(32K) "
        f"{options} KEY {_quote(cfg.api_key)}",
    )


def register(conn, cfg) -> str:
    """Create the model with the tightest options the provider accepts.

    Db2 does not validate a model when it is created, so each candidate is
    probed with one call. Measured against Gemini's OpenAI-compatible endpoint,
    REASONING_EFFORT makes every call fail with SQL16402N (the provider rejects
    the request and Db2 cannot parse the error as a completion), so the options
    fall back to the ones that work.
    """
    ceiling = f"MAX_COMPLETION_TOKENS {int(cfg.max_output_tokens)} TEMPERATURE 0.0"
    candidates = [ceiling]
    if cfg.reasoning_effort:
        candidates.insert(0, f"{ceiling} REASONING_EFFORT {cfg.reasoning_effort.upper()}")
    last: db.Db2Error | None = None
    for options in candidates:
        _drop(conn)
        _create(conn, cfg, options)
        try:
            db.fetch_one(conn, f"VALUES TEXT_GENERATION({_quote(_PROBE)} USING {MODEL})")
            return options
        except db.Db2Error as exc:
            last = exc
    _drop(conn)
    raise RuntimeError(
        f"Db2 could not reach the model: SQLCODE={last.sqlcode if last else '?'}. "
        "Check the key, the endpoint, and that the Db2 server has outbound network access."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="portproof-setup-model", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--drop", action="store_true", help="remove the model and ASK_MODEL")
    args = parser.parse_args(argv)

    conn = db.connect(setup_config(), role="setup")
    if args.drop:
        _drop(conn)
        print("removed PORTPROOF.PP_MODEL and PORTPROOF.ASK_MODEL")
        return 0
    cfg = llm_config()
    if not cfg.api_key:
        print("No API key in the environment (GEMINI_API_KEY or LLM_API_KEY). Nothing registered.")
        return 1
    options = register(conn, cfg)
    print(f"registered {MODEL}: {cfg.model}, options [{options}]")
    for statement in db.split_script((SQL_DIR / "07_in_db_model.sql").read_text(encoding="utf-8")):
        try:
            db.execute(conn, statement)
        except db.Db2Error as exc:
            # -204: nothing to drop.  -612: the column is already there.
            if exc.sqlcode not in (-204, -612):
                raise
    print("compiled PORTPROOF.ASK_MODEL and granted EXECUTE to the runtime identity")
    print("set LLM_TRANSPORT=db2 to route model calls through Db2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
