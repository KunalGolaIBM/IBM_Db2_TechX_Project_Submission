"""
Command Line Interface (CLI) for InternScrap.
Provides interactive management of internships and applications powered by IBM Db2.
"""

import sys
import argparse
import csv
import json
from typing import Optional
from tabulate import tabulate
from internscrap.db.connection import get_db_connection
from internscrap.db.schema import initialize_database
from internscrap.db.repository import Db2Repository
from internscrap.scrapers import get_scrapers
from internscrap.config import DB2_HOST, DB2_PORT, DB2_DATABASE, DB_BACKEND


def print_banner():
    banner = r"""
  ___       _                     ____                       
 |_ _|_ __ | |_ ___ _ __ _ __    / ___|  ___ _ __ __ _ _ __  
  | || '_ \| __/ _ \ '__| '_ \   \___ \ / __| '__/ _` | '_ \ 
  | || | | | ||  __/ |  | | | |   ___) | (__| | | (_| | |_) |
 |___|_| |_|\__\___|_|  |_| |_|  |____/ \___|_|  \__,_| .__/ 
                                                      |_|    
    IBM Db2-Powered Internship Aggregator & Lifecycle Tracker
    """
    print(banner)


def cmd_status(args):
    """Checks the database connection status."""
    conn = get_db_connection(force_new=True)
    print("=" * 60)
    print("Database Connection Status:")
    print("=" * 60)
    if conn.is_native_db2:
        print(f"  * Backend         : Native IBM Db2 Driver (ibm_db)")
        print(f"  * Host:Port       : {DB2_HOST}:{DB2_PORT}")
        print(f"  * Database        : {DB2_DATABASE}")
        print(f"  * Connection State: CONNECTED & READY")
    else:
        print(f"  * Backend         : Simulated Db2 Mode (SQLite Fallback)")
        print(f"  * Database File   : internscrap_dev.sqlite3")
        print(f"  * Note            : Start your local IBM Db2 container or set credentials")
        print(f"                      in .env to switch to live IBM Db2 LUW / Cloud.")
    print("=" * 60)


def cmd_init_db(args):
    """Initializes tables, indexes, and views in Db2."""
    initialize_database()


def cmd_scrape(args):
    """Scrapes internship listings and stores them into Db2."""
    repo = Db2Repository()
    scrapers = get_scrapers(args.source)
    print(f"Running scrapers (source: {args.source})...")

    total_added = 0
    total_skills = set()

    for scraper in scrapers:
        print(f" -> Scraping from '{scraper.name}'...")
        try:
            items = scraper.scrape()
            print(f"    Found {len(items)} postings.")
            for item in items:
                repo.upsert_internship(item)
                total_added += 1
                for s in item.get("skills", []):
                    total_skills.add(s)
        except Exception as e:
            print(f"    [Warning] Failed scraping from {scraper.name}: {e}")

    print("=" * 60)
    print(f"[Done] Ingested {total_added} internship postings into IBM Db2.")
    print(f"[Done] Associated {len(total_skills)} distinct skills in Db2 master catalog.")
    print("=" * 60)


def cmd_list(args):
    """Lists internships stored in IBM Db2."""
    repo = Db2Repository()
    rows = repo.list_internships(
        remote_only=args.remote,
        keyword=args.keyword,
        limit=args.limit
    )

    if not rows:
        print("\nNo internships found. Try running `python -m internscrap scrape` first!\n")
        return

    table_data = []
    for r in rows:
        stipend = "Unspecified"
        if r.get("STIPEND_MIN") and r.get("STIPEND_MAX"):
            stipend = f"${r['STIPEND_MIN']:.0f} - ${r['STIPEND_MAX']:.0f}/hr"
        elif r.get("STIPEND_MIN"):
            stipend = f"${r['STIPEND_MIN']:.0f}/hr"

        skills_str = ", ".join(r.get("SKILLS", [])[:3])
        if len(r.get("SKILLS", [])) > 3:
            skills_str += "..."

        table_data.append([
            r["ID"],
            r["COMPANY"][:20],
            r["TITLE"][:32],
            "Remote" if r["IS_REMOTE"] else r["LOCATION"][:16],
            stipend,
            skills_str,
            r.get("DEADLINE") or "Rolling"
        ])

    headers = ["ID", "Company", "Role Title", "Location", "Stipend", "Skills", "Deadline"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="grid") + "\n")


def cmd_show(args):
    """Shows full details of a specific internship."""
    repo = Db2Repository()
    item = repo.get_internship_by_id(args.id)
    if not item:
        print(f"Internship with ID #{args.id} not found in Db2.")
        return

    print("=" * 65)
    print(f"[{item['ID']}] {item['TITLE']} @ {item['COMPANY']}")
    print("=" * 65)
    print(f"Company Tier : {item.get('COMPANY_TIER', 'N/A')}")
    print(f"Location     : {item['LOCATION']} ({'Remote' if item['IS_REMOTE'] else 'On-site/Hybrid'})")
    if item.get("STIPEND_MIN") or item.get("STIPEND_MAX"):
        print(f"Stipend      : ${item.get('STIPEND_MIN', 0):.2f} - ${item.get('STIPEND_MAX', 0):.2f} {item.get('CURRENCY', 'USD')}")
    print(f"Deadline     : {item.get('DEADLINE') or 'Rolling'}")
    print(f"Source       : {item.get('SOURCE')}")
    print(f"Skills       : {', '.join(item.get('SKILLS', []))}")
    print(f"Apply URL    : {item['APPLY_URL']}")
    print("=" * 65)


def cmd_track(args):
    """Tracks an internship application in Db2."""
    repo = Db2Repository()
    repo.track_application(
        internship_id=args.id,
        status=args.status.upper(),
        notes=args.notes or "",
        applied_date=args.applied_date,
        follow_up_date=args.follow_up
    )
    print(f"[Success] Application for Internship #{args.id} recorded with status '{args.status.upper()}' in IBM Db2.")


def cmd_applications(args):
    """Lists tracked applications from Db2."""
    repo = Db2Repository()
    rows = repo.list_applications()
    if not rows:
        print("\nNo applications tracked yet! Track one using: `python -m internscrap track <id>`\n")
        return

    table_data = []
    for r in rows:
        table_data.append([
            r["APPLICATION_ID"],
            r["INTERNSHIP_ID"],
            r["COMPANY"][:20],
            r["ROLE"][:30],
            r["STATUS"],
            r.get("APPLIED_DATE") or "Today",
            r.get("FOLLOW_UP_DATE") or "None",
            (r.get("NOTES") or "")[:25]
        ])

    headers = ["App ID", "Job ID", "Company", "Role", "Status", "Applied On", "Follow Up", "Notes"]
    print("\n" + tabulate(table_data, headers=headers, tablefmt="grid") + "\n")


def cmd_stats(args):
    """Displays analytical insights computed via IBM Db2 views."""
    repo = Db2Repository()
    analytics = repo.get_analytics()

    print("\n" + "=" * 60)
    print(f"IBM Db2 System Telemetry & Aggregation Metrics")
    print("=" * 60)
    print(f"  * Total Internships Ingested : {analytics['total_internships']}")
    print(f"  * Total Companies Tracked    : {analytics['total_companies']}")
    print("=" * 60)

    print("\n[Application Lifecycle Funnel (from V_APPLICATION_FUNNEL)]")
    if analytics["funnel"]:
        funnel_data = [[r["STAGE"], r["TOTAL_COUNT"]] for r in analytics["funnel"]]
        print(tabulate(funnel_data, headers=["Pipeline Stage", "Count"], tablefmt="simple"))
    else:
        print("  No applications recorded in funnel yet.")

    print("\n[Top In-Demand Technical Skills (from Db2 Relational Index)]")
    if analytics["top_skills"]:
        skills_data = [[r["SKILL_NAME"], r["LISTING_COUNT"]] for r in analytics["top_skills"]]
        print(tabulate(skills_data, headers=["Skill", "Job Postings Requiring It"], tablefmt="simple"))
    print()


def cmd_export(args):
    """Exports tracked applications from Db2 to CSV or JSON."""
    repo = Db2Repository()
    rows = repo.list_applications()
    out_file = args.output

    if args.format == "csv":
        if not out_file.endswith(".csv"):
            out_file += ".csv"
        with open(out_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["App ID", "Internship ID", "Company", "Role", "Status", "Applied Date", "Follow Up", "Notes"])
            for r in rows:
                writer.writerow([
                    r["APPLICATION_ID"], r["INTERNSHIP_ID"], r["COMPANY"], r["ROLE"],
                    r["STATUS"], r.get("APPLIED_DATE"), r.get("FOLLOW_UP_DATE"), r.get("NOTES")
                ])
        print(f"[Done] Exported {len(rows)} application records to {out_file}")
    else:
        if not out_file.endswith(".json"):
            out_file += ".json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=2, default=str)
        print(f"[Done] Exported {len(rows)} application records to {out_file}")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="internscrap",
        description="InternScrap - Internship Aggregator & Application Tracker powered by IBM Db2"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # status
    p_status = subparsers.add_parser("status", help="Check IBM Db2 database connection status")
    p_status.set_defaults(func=cmd_status)

    # init-db
    p_init = subparsers.add_parser("init-db", help="Initialize tables, indexes, and views in IBM Db2")
    p_init.set_defaults(func=cmd_init_db)

    # scrape
    p_scrape = subparsers.add_parser("scrape", help="Scrape latest tech internships into IBM Db2")
    p_scrape.add_argument(
        "--source", 
        choices=["sample", "remoteok", "github", "all"], 
        default="all", 
        help="Source to scrape from (default: all)"
    )
    p_scrape.set_defaults(func=cmd_scrape)

    # list
    p_list = subparsers.add_parser("list", help="List active internships from IBM Db2")
    p_list.add_argument("--remote", action="store_true", help="Filter for remote roles only")
    p_list.add_argument("--keyword", type=str, help="Filter by title or company keyword")
    p_list.add_argument("--limit", type=int, default=20, help="Maximum number of rows to return (default: 20)")
    p_list.set_defaults(func=cmd_list)

    # show
    p_show = subparsers.add_parser("show", help="View full details for an internship by ID")
    p_show.add_argument("id", type=int, help="Internship ID")
    p_show.set_defaults(func=cmd_show)

    # track
    p_track = subparsers.add_parser("track", help="Track an application stage for an internship")
    p_track.add_argument("id", type=int, help="Internship ID")
    p_track.add_argument(
        "--status",
        choices=["WISHLIST", "APPLIED", "ONLINE_ASSESSMENT", "INTERVIEWING", "OFFER", "REJECTED"],
        default="APPLIED",
        help="Application status"
    )
    p_track.add_argument("--notes", type=str, help="Application notes / interview prep")
    p_track.add_argument("--applied-date", type=str, help="Date applied (YYYY-MM-DD)")
    p_track.add_argument("--follow-up", type=str, help="Next follow-up date (YYYY-MM-DD)")
    p_track.set_defaults(func=cmd_track)

    # applications
    p_apps = subparsers.add_parser("applications", help="View all tracked applications in IBM Db2")
    p_apps.set_defaults(func=cmd_applications)

    # stats
    p_stats = subparsers.add_parser("stats", help="Display analytics via IBM Db2 views")
    p_stats.set_defaults(func=cmd_stats)

    # export
    p_exp = subparsers.add_parser("export", help="Export tracked applications to CSV/JSON")
    p_exp.add_argument("--output", "-o", default="applications_export", help="Output filename")
    p_exp.add_argument("--format", choices=["csv", "json"], default="csv", help="Export format")
    p_exp.set_defaults(func=cmd_export)

    return parser


def main():
    parser = build_parser()
    if len(sys.argv) == 1:
        print_banner()
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
