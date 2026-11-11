"""Command line interface for ShipSafe AI."""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from .config import ShipSafeConfig
from .discovery import ProjectDiscovery
from .reports import ReportGenerator
from .runtime import build_runtime

LINE = "=" * 64


def _ts(ms) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ms) / 1000))


def cmd_doctor(args) -> int:
    print(LINE + "\nShipSafe AI - environment check\n" + LINE)
    config = ShipSafeConfig.load()
    print(f"Python runtime : {sys.version.split()[0]}")
    print(f"Storage backend: {config.backend}")
    try:
        rt = build_runtime(config)
    except Exception as exc:  # report the real connection error, never pretend
        print(f"[FAIL] IBM Db2 connection: {exc}")
        print("       Check DB2_HOST / DB2_PORT / DB2_DATABASE / DB2_USERNAME / DB2_PASSWORD.")
        return 1
    st = rt.repository.check_connection()
    if rt.repository.is_db2:
        print(f"[OK]   IBM Db2 {st['version']} at {st['host']}:{st['port']} / {st['database']}")
        print(f"       Schema {st['schema']}: {st['tables_in_schema']} tables, {st['views_in_schema']} view(s)")
    else:
        print(f"[WARN] {st['engine']} - use SHIPSAFE_DB_BACKEND=db2 for real persistence")
    if rt.knowledge_base:
        print(f"[OK]   langchain-db2 vector store: {rt.knowledge_base.chunk_count()} policy chunks in POLICY_VECTORS")
    print(f"[OK]   MCP server: {'enabled' if config.enable_mcp else 'disabled'} (python -m shipsafe.mcp_server)")
    print("\nOptional external scanners (built-in rules are used when absent):")
    for name in ("git", "gitleaks", "bandit", "ruff"):
        print(f"  {'[OK]  ' if shutil.which(name) else '[--]  '} {name}")
    return 0


def cmd_init_db(args) -> int:
    """Create the schema. Uses DB2_ADMIN_USERNAME / DB2_ADMIN_PASSWORD when set, so the
    runtime user can be a least-privilege account (see docs/db2-least-privilege.sql)."""
    import os

    from .config import Db2Config
    from .db2 import Db2Repository

    config = ShipSafeConfig.load()
    db2 = Db2Config.from_env("DB2_ADMIN_") if os.getenv("DB2_ADMIN_PASSWORD") else config.db2
    repo = Db2Repository(db2, backend=config.backend, init_schema=False)
    created = repo.initialize_schema(replace_views=True)
    print(f"Schema {repo.schema} ready as {db2.username}. Newly created: {', '.join(created) or 'none (already present)'}")
    return 0


def cmd_serve(args) -> int:
    sys.stdout.reconfigure(line_buffering=True)
    import uvicorn

    from .api import create_app
    from .db2.pool import ConnectionPool
    from .logging_setup import configure_logging

    config = ShipSafeConfig.load()
    if args.host:
        config.api_host = args.host
    if args.port:
        config.api_port = args.port
    problems = config.validate()
    if problems:
        print("Configuration errors:\n  - " + "\n  - ".join(problems))
        return 2
    configure_logging(config.log_format, config.log_level)

    pool = ConnectionPool(config.db2, backend=config.backend, size=config.pool_size)
    try:
        with pool.repository() as repo:
            st = repo.check_connection()
            print(f"[OK] {st['engine']} {st.get('version', '')} · schema {st.get('schema', '-')} · {st['latency_ms']} ms")
            if repo.is_db2:
                from .knowledge import PolicyKnowledgeBase

                PolicyKnowledgeBase(repo, config.embedding_provider, config.embedding_dimension).ensure_ingested(config.policies_dir)
            if config.auth_enabled and repo.count_active_admins() == 0:
                from .security import issue_token

                token_id, token, digest = issue_token()
                repo.create_token(token_id, "bootstrap-admin", "admin", digest)
                repo.audit("system", "token.bootstrap", "success", role="admin", target=token_id)
                print("\n" + LINE + "\nFirst start: an admin API token was created. It is shown ONCE:\n\n"
                      f"    {token}\n\nPaste it into the web UI sign-in. Create more with: shipsafe token create\n" + LINE + "\n")
    except Exception as exc:
        print(f"[WARN] IBM Db2 not reachable yet ({exc}). The UI will start in degraded mode and reconnect automatically.")
    print(f"ShipSafe AI web UI: http://{config.api_host}:{config.api_port}  (API docs: /api/docs)")
    uvicorn.run(create_app(config, pool), host=config.api_host, port=config.api_port,
                log_level=config.log_level.lower(), access_log=False, proxy_headers=True)
    return 0


def cmd_token(args) -> int:
    from .security import issue_token

    rt = build_runtime(with_knowledge=False)
    repo = rt.repository
    if args.token_cmd == "create":
        token_id, token, digest = issue_token()
        repo.create_token(token_id, args.name, args.role, digest)
        repo.audit("cli", "token.created", "success", role="admin", target=token_id, detail=f"name={args.name} role={args.role}")
        print(f"Created {args.role} token {token_id} ({args.name}). Shown once:\n\n    {token}\n")
    elif args.token_cmd == "list":
        for t in repo.list_tokens():
            state = "revoked" if int(t["REVOKED"]) else "active"
            print(f"  {t['TOKEN_ID']:<18} {t['ROLE']:<9} {state:<8} {t['NAME']}")
    elif args.token_cmd == "revoke":
        ok = repo.revoke_token(args.token_id)
        repo.audit("cli", "token.revoked", "success" if ok else "error", target=args.token_id)
        print("Revoked." if ok else "Token not found.")
        return 0 if ok else 1
    return 0


def cmd_audit(args) -> int:
    rt = build_runtime(with_knowledge=False)
    for e in rt.repository.list_audit(limit=args.limit):
        print(f"{_ts(e['TS'])}  {e['OUTCOME']:<8} {e['ACTION']:<20} {e['ACTOR']:<18} {e.get('TARGET') or ''}")
    return 0


def cmd_ingest(args) -> int:
    rt = build_runtime(with_knowledge=False)
    from .knowledge import PolicyKnowledgeBase

    kb = PolicyKnowledgeBase(rt.repository, rt.config.embedding_provider, rt.config.embedding_dimension)
    stats = kb.ingest_directory(args.dir or rt.config.policies_dir)
    print(LINE + "\nPolicy ingestion into IBM Db2 (langchain-db2 DB2VS)\n" + LINE)
    for doc_id, n in stats.items():
        print(f"  {doc_id:<12} {n} chunk(s)")
    print(f"Total vectors in POLICY_VECTORS: {kb.chunk_count()}")
    return 0


def cmd_discover(args) -> int:
    res = ProjectDiscovery(args.target).discover()
    print(LINE + f"\nProject discovery: {res.repo_name}\n" + LINE)
    print(f"Languages        : {', '.join(res.languages) or 'none'}")
    print(f"Manifests        : {', '.join(res.manifests) or 'none'}")
    print(f"Test frameworks  : {', '.join(res.test_frameworks) or 'none'}")
    print(f"Applicable checks: {', '.join(res.applicable_checks)}")
    for k, v in res.skipped_checks.items():
        print(f"  skipped {k}: {v}")
    return 0


def cmd_scan(args) -> int:
    if args.offline:
        # CI mode: no database. Same scanners and gate; nothing is persisted and no policy citations.
        from .orchestration import AssessmentOrchestrator

        orchestrator = AssessmentOrchestrator(ShipSafeConfig.load(), None, None)
        persist = False
    else:
        orchestrator, persist = build_runtime().orchestrator, True
    print(f"Assessing '{args.target}' with profile '{args.profile}'{' (offline)' if args.offline else ''} ...")
    result = orchestrator.run_assessment(args.target, profile=args.profile, persist_to_db2=persist)
    asm, gate = result.assessment, result.gate

    print("\n" + LINE)
    print(f"Assessment   : {asm.assessment_id}")
    print(f"Release gate : {gate.status.value}")
    print(f"Summary      : {gate.reason}")
    print(LINE)
    print(f"Findings: {asm.findings_count}  (critical {asm.critical_count}, high {asm.high_count}, "
          f"medium {asm.medium_count}, low {asm.low_count})")
    for tr in result.tool_runs:
        print(f"  [{tr.status:^7}] {tr.tool_name:<28} {tr.message}")
    if result.findings:
        print("\nFindings (each linked to the policy retrieved from Db2):")
        for i, f in enumerate(result.findings, 1):
            print(f"  {i}. [{f.severity.upper():8}] {f.title}  ({f.file_path}:{f.line_start})")
            policy = next((r for r in f.references if r.startswith("POL-")), None)
            if policy:
                print(f"     policy: {policy}")
    if result.persisted:
        print("\nPersisted to IBM Db2 in one transaction: PROJECTS, ASSESSMENTS, TOOL_RUNS, FINDINGS, DEPENDENCIES")
    for w in result.warnings:
        print(f"[WARN] {w}")
    if args.output:
        out = Path(args.output)
        render = {"json": ReportGenerator.to_json, "sarif": ReportGenerator.to_sarif}.get(args.format, ReportGenerator.to_markdown)
        out.write_text(render(result), encoding="utf-8")
        print(f"Report written to {out.resolve()}")
    return 1 if gate.status.value == "BLOCKED" else 0


def cmd_assessment_show(args) -> int:
    rt = build_runtime(with_knowledge=False)
    asm = rt.repository.get_assessment(args.assessment_id)
    if not asm:
        print(f"Assessment '{args.assessment_id}' not found in Db2.")
        return 1
    data = {"assessment": asm, "tool_runs": rt.repository.get_tool_runs(args.assessment_id),
            "findings": rt.repository.get_findings(args.assessment_id)}
    print(json.dumps(data, indent=2, default=str))
    return 0


def cmd_assessment_compare(args) -> int:
    rt = build_runtime(with_knowledge=False)
    diff = rt.repository.compare_assessments(args.previous_id, args.current_id)
    print(LINE + f"\nRegression diff {args.previous_id} -> {args.current_id}\n" + LINE)
    print(f"New       : {diff['new_count']}")
    for f in diff["new_findings"]:
        print(f"  + [{f['SEVERITY'].upper()}] {f['TITLE']}")
    print(f"Resolved  : {diff['resolved_count']}")
    for f in diff["resolved_findings"]:
        print(f"  - [{f['SEVERITY'].upper()}] {f['TITLE']}")
    print(f"Unchanged : {diff['unchanged_count']}")
    print("Delta stored in Db2 table ASSESSMENT_DIFFS.")
    return 0


def cmd_history(args) -> int:
    rt = build_runtime(with_knowledge=False)
    rows = rt.repository.get_assessment_history(limit=args.limit)
    print(LINE + "\nAssessment history (Db2 view V_RISK_TREND, LAG() window delta)\n" + LINE)
    print(f"{'when':<20} {'project':<22} {'gate':<19} {'C':>2} {'H':>2} {'M':>2} {'risk':>5} {'delta':>6}")
    for r in rows:
        delta = "" if r["RISK_DELTA"] is None else f"{int(r['RISK_DELTA']):+d}"
        print(f"{_ts(r['STARTED_AT']):<20} {str(r['PROJECT_NAME'])[:22]:<22} {r['STATUS']:<19} "
              f"{r['CRITICAL_COUNT']:>2} {r['HIGH_COUNT']:>2} {r['MEDIUM_COUNT']:>2} {r['RISK_SCORE']:>5} {delta:>6}")
    print("\nFindings by category and severity (GROUP BY in Db2):")
    for r in rt.repository.severity_breakdown():
        print(f"  {r['CATEGORY']:<14} {r['SEVERITY']:<9} total={r['TOTAL']:<4} unique={r['UNIQUE_ISSUES']}")
    return 0


def cmd_knowledge_query(args) -> int:
    rt = build_runtime()
    if not rt.knowledge_base:
        print("Policy search requires the IBM Db2 backend.")
        return 1
    hits = rt.knowledge_base.retrieve(args.query, top_k=args.top_k)
    print(LINE + f"\nDb2 vector search (VECTOR_DISTANCE, COSINE): {args.query!r}\n" + LINE)
    for i, h in enumerate(hits, 1):
        print(f"\n{i}. {h['title']} [{h['doc_id']} v{h['version']}] similarity={h['similarity']:.3f}")
        print(f"   section: {h['section']} | source: {h['source']}")
        print("   " + h["content"].replace("\n", "\n   "))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="shipsafe", description="ShipSafe AI - pre-PR production-readiness gate backed by IBM Db2")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("doctor", help="Check Db2 connectivity, vector store and scanners")
    sub.add_parser("init-db", help="Create the ShipSafe schema in IBM Db2")
    p = sub.add_parser("ingest", help="(Re)ingest policy Markdown into the Db2 vector store")
    p.add_argument("--dir", help="Policies directory (default: ./policies)")

    p = sub.add_parser("discover", help="Inspect a workspace")
    p.add_argument("--target", default=".")

    p = sub.add_parser("scan", help="Run a production-readiness assessment")
    p.add_argument("--target", default=".")
    p.add_argument("--profile", choices=["quick", "pre-pr", "deep"], default="pre-pr")
    p.add_argument("--output")
    p.add_argument("--format", choices=["markdown", "json", "sarif"], default="markdown")
    p.add_argument("--offline", action="store_true", help="Run without Db2 (CI): no persistence or policy citations")

    p_asm = sub.add_parser("assessment", help="Inspect stored assessments")
    asm_sub = p_asm.add_subparsers(dest="asm_cmd")
    p = asm_sub.add_parser("show")
    p.add_argument("assessment_id")
    p = asm_sub.add_parser("compare")
    p.add_argument("previous_id")
    p.add_argument("current_id")

    p = sub.add_parser("serve", help="Start the web UI + REST API")
    p.add_argument("--host")
    p.add_argument("--port", type=int)

    p_t = sub.add_parser("token", help="Manage API tokens")
    t_sub = p_t.add_subparsers(dest="token_cmd")
    p = t_sub.add_parser("create")
    p.add_argument("--name", required=True)
    p.add_argument("--role", choices=["viewer", "operator", "admin"], default="viewer")
    t_sub.add_parser("list")
    p = t_sub.add_parser("revoke")
    p.add_argument("token_id")

    p = sub.add_parser("audit", help="Show the Db2 audit log")
    p.add_argument("--limit", type=int, default=30)

    p = sub.add_parser("history", help="Risk trend and severity analytics from Db2")
    p.add_argument("--limit", type=int, default=10)

    p_k = sub.add_parser("knowledge", help="Query the policy knowledge base")
    k_sub = p_k.add_subparsers(dest="k_cmd")
    p = k_sub.add_parser("query")
    p.add_argument("query")
    p.add_argument("--top-k", type=int, default=3)

    args = parser.parse_args()
    handlers = {
        "doctor": cmd_doctor, "init-db": cmd_init_db, "ingest": cmd_ingest, "discover": cmd_discover,
        "scan": cmd_scan, "history": cmd_history, "serve": cmd_serve, "token": cmd_token, "audit": cmd_audit,
    }
    if args.command in handlers:
        sys.exit(handlers[args.command](args))
    if args.command == "assessment" and args.asm_cmd == "show":
        sys.exit(cmd_assessment_show(args))
    if args.command == "assessment" and args.asm_cmd == "compare":
        sys.exit(cmd_assessment_compare(args))
    if args.command == "knowledge" and args.k_cmd == "query":
        sys.exit(cmd_knowledge_query(args))
    parser.print_help()


if __name__ == "__main__":
    main()
