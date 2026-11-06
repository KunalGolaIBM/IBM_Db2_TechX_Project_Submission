"""
CLI Entrypoint for Db2 Sentinel AI.
Demonstrates end-to-end multi-agent financial surveillance, Db2 vector queries,
circular routing detection, and automated SAR drafting.
"""

import sys
from pathlib import Path

# Ensure UTF-8 output encoding on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.db.connection import get_db_manager
from src.db.schema import initialize_schema
from src.db.seed_data import seed_database
from src.db.queries import get_pending_alerts, get_recent_audit_trail
from src.agents.workflow import SentinelWorkflow

console = Console(highlight=False)


def print_banner():
    banner_text = """
 ===========================================================================
   IBM Db2 Sentinel AI: Autonomous Financial Crime Surveillance Suite
   Multi-Agent AML Intelligence | Db2 Vector Search | Regulatory SARs
 ===========================================================================
    """
    console.print(f"[bold cyan]{banner_text}[/bold cyan]")


def run_pipeline():
    print_banner()

    # 1. Initialize and Seed Db2 Database
    with console.status("[bold green]Connecting to IBM Db2 and verifying schema...[/bold green]"):
        initialize_schema()
        seed_database()

    db = get_db_manager()
    engine_desc = (
        "[bold green]Connected to Live IBM Db2 12.1+ (Native VECTOR & ACID)[/bold green]"
        if db.active_mode == "live"
        else "[bold yellow]Db2 High-Fidelity Local Engine (Zero-Setup Emulation Active)[/bold yellow]"
    )
    console.print(Panel(f"Database Status: {engine_desc}\nDual-Mode Architecture Active: Ready for hackathon evaluation.", title="[bold]System Health[/bold]"))

    # 2. Display Pending Alerts
    alerts = get_pending_alerts()
    table = Table(title="Pending Intercepted AML Alerts (IBM Db2)", header_style="bold magenta")
    table.add_column("Alert ID", style="cyan")
    table.add_column("TX ID", style="white")
    table.add_column("Sender -> Receiver", style="yellow")
    table.add_column("Amount", justify="right", style="green")
    table.add_column("Triggered Rule", style="white")
    table.add_column("Risk Score", justify="center", style="bold red")

    for alt in alerts:
        table.add_row(
            alt["ALERT_ID"],
            alt["TX_ID"],
            f"{alt['SENDER_ID']} -> {alt['RECEIVER_ID']}",
            f"${float(alt['AMOUNT']):,.2f} {alt['CURRENCY']}",
            alt["RULE_TRIGGERED"],
            f"{alt['RISK_SCORE']}/100",
        )
    console.print(table)
    console.print()

    # 3. Execute Autonomous Multi-Agent Investigation on Case 1 (Structuring)
    sample_tx = "TX-STRUCT-01"
    console.print(f"[bold cyan]>> Launching LangGraph Multi-Agent Investigation on Suspicious Wire {sample_tx}...[/bold cyan]\n")

    workflow = SentinelWorkflow()
    result = workflow.run_investigation(sample_tx, auto_approve=True)

    # 4. Display Agent Execution Trace
    agent_trace_table = Table(title=f"Multi-Agent Execution Trace (Thread: {result['thread_id']})", header_style="bold blue")
    agent_trace_table.add_column("Agent Node", style="cyan")
    agent_trace_table.add_column("Action & Db2 Findings", style="white")
    agent_trace_table.add_column("Timestamp", style="dim")

    for log in result["agent_logs"]:
        agent_trace_table.add_row(log["agent"], log["message"], log["timestamp"])
    console.print(agent_trace_table)
    console.print()

    # 5. Display Case Summary Panel
    summary_md = f"""
**Transaction Intercepted:** {result['tx_id']} (${result['transaction_data']['AMOUNT']:,.2f} USD)
**Final Risk Score:** [bold red]{result['risk_score']} / 100[/bold red]
**Matched AML Typologies (Db2 Vector Search):** {[t['TITLE'] for t in result['matched_typologies']]}
**Structuring Detected:** {result['structuring_evidence'].get('is_structuring_suspect')}
**Supervisor Enforcement:** [bold green]{result['supervisor_decision']}[/bold green] ({result['supervisor_notes']})
**Cryptographic Audit Signature:** `[bold yellow]{result['audit_signature']}[/bold yellow]`
    """
    console.print(Panel(summary_md.strip(), title="[bold]Investigation Disposition[/bold]", border_style="green"))

    # 6. Show Audit Trail from Db2
    recent_audits = get_recent_audit_trail(limit=5)
    audit_table = Table(title="Immutable Db2 Cryptographic Audit Trail", header_style="bold yellow")
    audit_table.add_column("Audit ID", style="cyan")
    audit_table.add_column("Actor", style="white")
    audit_table.add_column("Action", style="green")
    audit_table.add_column("Signature Hash (SHA-256)", style="dim")

    for aud in recent_audits:
        audit_table.add_row(str(aud["AUDIT_ID"]), aud["ACTOR"], aud["ACTION"], aud["SIGNATURE_HASH"][:16] + "...")
    console.print(audit_table)

    console.print("\n[bold green]✓ Pipeline executed successfully![/bold green]")
    console.print("[white]To launch the interactive Web Dashboard: [bold cyan]streamlit run src/app.py[/bold cyan][/white]")
    console.print("[white]To run automated verification tests:   [bold cyan]pytest tests/[/bold cyan][/white]\n")


if __name__ == "__main__":
    run_pipeline()
