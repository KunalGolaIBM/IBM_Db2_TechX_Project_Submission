# What is new in ShipSafe

AI coding assistants such as IBM Bob write code quickly, but the checks that keep code safe
usually run later, in CI or in review. By then the assistant has moved on, and a person has to
explain the problem back to it. ShipSafe moves those checks into the assistant's own loop and
keeps every result in IBM Db2.

Each item below says what is new, why it matters, and how it was proved.

---

## 1. Checks that run before the code exists

**What.** The assistant sends the file it is *about to write* to `shipsafe_check_code`. ShipSafe
checks the text, not the disk, and answers `clean`, `warn` or `block`. A rules file tells Bob not
to write a file while the verdict is `block`.

**Why it matters.** A problem fixed before the file is written never shows up in a diff, a review
or a pipeline. The assistant can correct itself in the same turn.

**Proof.** A typical file is checked in about 0.4 s with Bandit. Every check is recorded in the Db2
table `GUARD_EVENTS` with the name of the IDE that made it, so a team can see what was caught in Bob
versus VS Code.

## 2. Rules that read code, not text

**What.** Python rules work on the parsed syntax tree. Comments, docstrings and string literals can
never trigger a rule, and a small data-flow pass follows SQL that is built in one variable and run
later (`sql = f"..."; q = sql; cur.execute(q)`). Findings are reported on the line where the SQL is
built, which is where the fix goes, and are merged with Bandit's finding for the same line.

**Why it matters.** Text-matching scanners raise alarms on code that only *mentions* `eval()` or
`shell=True`. Assistants then learn to ignore the tool.

**Proof.** We ran the old pattern rules and the new ones on real projects: OWASP PyGoat, another
Db2Hack project and ShipSafe itself. Every false alarm we had found earlier (docstrings, URLs
containing "update", JSON strings in tests) disappeared, and every real vulnerability was still
found. 48 rule tests pin this behaviour.

## 3. Db2-aware rules learned from the model's own mistakes

**What.** Rule `DB2-API-MISUSE` catches two `ibm_db` errors that fail at runtime:
`exec_immediate` called with `?` markers or a parameter tuple, and rows fetched from the
True/False result of `ibm_db.execute()` instead of from the statement.

**Why it matters.** We found both mistakes in code Granite wrote while fixing a SQL injection.
The original checks passed that code, because it was *secure*. It just did not work. Adding the rule
turned a silent failure into a rejected fix and a second, correct attempt.

## 4. AI fixes that must pass the same checks

**What.** `shipsafe_fix_code` runs a CrewAI crew on local Granite: a security analyst writes a plan
from the exact findings and the team policy retrieved from Db2, and an engineer returns the full
corrected file. Verification is deterministic: the new code goes through the same checks, and the fix
is accepted only if every targeted issue is gone and nothing new is blocking. Otherwise the remaining
issues go back for another round (up to three).

**Why it matters.** The model can propose; it cannot argue its way to a pass.

**Proof.** An automated test runs the vulnerable function against a real `ORDERS` table in Db2 and
shows the injection returns data. It then asks the crew for a fix, runs the *fixed* function
against the same table, and shows it still returns the right order while the injection returns
nothing. The secret moved to an environment variable. Each attempt is stored in `FIX_ATTEMPTS`.

## 5. SQL checked by the database that will run it

**What.** `shipsafe_check_sql` asks Db2 to `PREPARE` the statement with deferred prepare turned off.
Db2 reports syntax errors (SQL0104N), unknown tables (SQL0204N) and unknown columns (SQL0206N), and
describes the result columns. Nothing is executed and the transaction is rolled back. Unknown names
get "did you mean" suggestions from the live catalog, read through SQLAlchemy's inspector on
`ibm_db_sa`. Valid but risky SQL (UPDATE/DELETE without WHERE, Python `%s` placeholders, several
statements in one string) is flagged on top.

**Why it matters.** Assistants guess table and column names. Here the real database corrects them
before the query ships, with no test data and no side effects.

## 6. Memory that outlives the chat

**What.** `shipsafe_remember` stores decisions, conventions and gotchas as Granite embeddings in the
Db2 vector table `MEMORY_VECTORS` through Haystack's `ibm-db-haystack` store; `shipsafe_recall` finds
them at the start of the next task, filtered by project and kind inside Db2. Saving the same decision
twice updates it instead of duplicating it.

**Why it matters.** Every new chat starts from zero. Team decisions like "money is DECIMAL(15,2)" or
"writes to LEDGER go through a procedure" get lost unless something remembers them.

## 7. Answers that cite real policies, and are checked

**What.** `shipsafe_ask_standards` answers from team policies retrieved with
`VECTOR_DISTANCE(..., COSINE)` in Db2 (LangChain `DB2VS`). Every policy id in the answer is compared
with the ids Db2 actually returned. Near-misses are corrected and unknown ids are marked
`(unverified)`.

**Why it matters.** Small local models sometimes invent references. We saw Granite write
`SEC-POL-001` for `POL-DB2-001`; the answer now shows the correct id.

## 8. One database for everything, with logic inside it

Relational records, two vector stores and three SQL PL procedures share one Db2 schema:

- `SP_PROJECT_RISK` computes risk, the change since the last run and a trend label with OUT parameters.
- `SP_GUARD_SUMMARY` returns a dynamic result set of what was caught per IDE.
- `SP_PURGE_HISTORY` validates input with `SIGNAL SQLSTATE`, counts with `GET DIAGNOSTICS` and relies
  on `ON DELETE CASCADE` for retention.

## 9. One server for every AI IDE

ShipSafe is a standard MCP server. `shipsafe connect bob|claude|cursor|vscode` writes the right
config file for each editor, merging with existing servers and keeping user options. The VS Code /
Bob extension is an MCP client of the same server, so the Problems panel and the agent always agree.
A git pre-commit hook uses the same checks for code written without an assistant.

## 10. Local by design

Granite runs in Ollama on the developer's machine, Db2 runs locally or on the team's server, and the
usage telemetry that CrewAI, LiteLLM and Haystack send by default is switched off. Code never leaves
the machine.

## 11. Enforced, not requested: a pre-write hook

**What.** `shipsafe connect claude` also installs a Claude Code `PreToolUse` hook. Before every Write, Edit or
MultiEdit, the hook rebuilds the file as it would look after the edit and checks it; a blocking verdict cancels
the write and tells the model why.

**Why it matters.** Rules files and "skills" ask the model to call a checker. A hook makes skipping it impossible.

**Proof.** Asked to write `os.system(cmd)`, Claude Code answered that "the ShipSafe pre-write hook blocked it as a
high-severity command-injection risk", and no file was created (see [testing.md](testing.md)).

## 12. Shippy: setup, safety net and per-agent accountability

**What.** The extension's sidebar guide installs the engine, connects Db2 and Granite and wires Bob, checks every
file an agent writes to disk even if the agent skipped ShipSafe, and shows from Db2's `SP_GUARD_SUMMARY` how often
each AI agent (Bob, Claude Code, VS Code agent mode) was checked and blocked.
