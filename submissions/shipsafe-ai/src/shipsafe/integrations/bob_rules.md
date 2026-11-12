# ShipSafe: keep every change production-ready

ShipSafe is connected as an MCP server. Use it on every coding task:

1. **Start of a task:** call `shipsafe_recall` with a short description of the task and follow any
   decisions or conventions it returns.
2. **Before writing or editing a source file:** call `shipsafe_check_code` with the complete new
   file content and the file path.
   - `block`: do not write the file. Fix the listed issues yourself or call `shipsafe_fix_code`,
     then check again. Only use `fixed_code` when `verified` is true.
   - `warn`: write the file and mention the warnings in your summary.
3. **SQL for IBM Db2:** call `shipsafe_db2_schema` to see the real tables, and validate every
   statement with `shipsafe_check_sql` before using it. Always use `?` parameter markers.
4. **Team rules:** when unsure how something must be done here, call `shipsafe_ask_standards`.
5. **Decisions:** when the user decides something that should hold for later work (a library choice,
   a naming rule, an API contract), save it with `shipsafe_remember`.
6. **Before you say the task is done:** call `shipsafe_readiness_check` with profile `quick` and
   report the verdict.

Never hardcode secrets; read them from environment variables.
