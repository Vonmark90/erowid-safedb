"""
Command-Line Interface (CLI) for Erowid Harm Reduction & Experience Database.
"""

import sys
import argparse
import json
from erowid_safedb.db import Database
from erowid_safedb.seed_data import seed_database
from erowid_safedb.harm_reduction import HarmReductionEngine
from erowid_safedb.scraper import ErowidScraper
from erowid_safedb.web import start_server


def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}\033[0m"


def main():
    parser = argparse.ArgumentParser(
        description="Erowid Harm Reduction & Drug Education Systematic Database CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 -m erowid_safedb init
  python3 -m erowid_safedb search "overdose"
  python3 -m erowid_safedb substance mdma
  python3 -m erowid_safedb check-combo alcohol xanax
  python3 -m erowid_safedb check-dose mdma 250
  python3 -m erowid_safedb scrape --id 71809
  python3 -m erowid_safedb web --port 8080
        """
    )
    parser.add_argument("--db", default="data/erowid_safedb.db", help="Path to SQLite database file")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Command: init
    subparsers.add_parser("init", help="Initialize SQLite DB and seed with harm-reduction data")

    # Command: substance
    sub_parser = subparsers.add_parser("substance", help="Look up substance dosing and harm reduction profile")
    sub_parser.add_argument("name", help="Substance name, slug, or slang (e.g. mdma, ketamine, shrooms)")

    # Command: check-combo
    combo_parser = subparsers.add_parser("check-combo", help="Check dangerous interactions between 2+ substances")
    combo_parser.add_argument("substances", nargs="+", help="Substances to combine (e.g. alcohol xanax oxycodone)")

    # Command: check-dose
    dose_parser = subparsers.add_parser("check-dose", help="Check if an intended dose is in safe or dangerous range")
    dose_parser.add_argument("substance", help="Substance name")
    dose_parser.add_argument("amount", type=float, help="Numeric dose amount")
    dose_parser.add_argument("--unit", default="mg", help="Unit of measurement (default: mg)")
    dose_parser.add_argument("--route", default="Oral", help="Route of administration (default: Oral)")

    # Command: search
    search_parser = subparsers.add_parser("search", help="Search experience vault with full-text search (FTS5)")
    search_parser.add_argument("query", nargs="?", default="", help="Keyword search query")
    search_parser.add_argument("--substance", help="Filter by substance")
    search_parser.add_argument("--tag", help="Filter by tag (e.g. Overdose, Hospital, Bad Trips)")
    search_parser.add_argument("--symptom", help="Filter by adverse clinical symptom (e.g. seizure, tachycardia)")
    search_parser.add_argument("--limit", type=int, default=15, help="Number of results to display")

    # Command: view
    view_parser = subparsers.add_parser("view", help="View full details of an experience report")
    view_parser.add_argument("id", type=int, help="Erowid Experience ID (e.g. 71809)")

    # Command: scrape
    scrape_parser = subparsers.add_parser("scrape", help="Scrape experience reports from Erowid/Wayback")
    scrape_parser.add_argument("--id", type=int, help="Single Experience ID to scrape")
    scrape_parser.add_argument("--range", nargs=2, type=int, metavar=("START", "END"), help="Scrape ID range (inclusive)")
    scrape_parser.add_argument("--delay", type=float, default=2.0, help="Polite delay between requests in seconds")

    # Command: import
    import_parser = subparsers.add_parser("import", help="Import local HTML files into database")
    import_parser.add_argument("path", help="Path to .html file or directory containing files")

    # Command: stats
    subparsers.add_parser("stats", help="Show database overview statistics")

    # Command: web
    web_parser = subparsers.add_parser("web", help="Launch interactive Web Dashboard & API")
    web_parser.add_argument("--port", type=int, default=8080, help="Port to bind web server (default: 8080)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    db = Database(args.db)
    engine = HarmReductionEngine(db)
    scraper = ErowidScraper()

    if args.command == "init":
        print(f"📦 Initializing database at '{args.db}'...")
        res = seed_database(db)
        print(f"✓ Seeded {res['substances_seeded']} substances")
        print(f"✓ Seeded {res['interactions_seeded']} interaction rules")
        print(f"✓ Seeded {res['reports_seeded']} annotated harm-reduction reports")
        print("Database ready for harm reduction queries and ingestion.")

    elif args.command == "substance":
        sub = db.get_substance(args.name)
        if not sub:
            print(f"Substance '{args.name}' not found. Run 'init' or check spelling.")
            sys.exit(1)

        print("\n" + "="*70)
        print(f"  {sub.name.upper()} ({sub.category})")
        print("="*70)
        if sub.common_names:
            print(f"Aliases / Slang: {', '.join(sub.common_names)}")
        print(f"Addiction Potential: {sub.addiction_potential} | Legal Status: {sub.legal_status}")
        print("\n[ Harm Summary & Prevention ]")
        print(f"{sub.harm_summary}")
        print("\n[ Toxicity & Physiological Risks ]")
        print(f"{sub.toxicity_notes}")

        if sub.dosages:
            print("\n[ Standard Dosage Guidelines ]")
            for d in sub.dosages:
                print(f"Route: {d.route}")
                print(f" • Threshold: {d.threshold or 'N/A'}")
                print(f" • Light:     {d.light or 'N/A'}")
                print(f" • Common:    {d.common or 'N/A'}")
                print(f" • Strong:    {d.strong or 'N/A'}")
                print(f" • Heavy:     {d.heavy or 'N/A'}")
                if d.notes:
                    print(f"   Notes: {d.notes}")

        if sub.durations:
            print("\n[ Duration Timeline ]")
            for du in sub.durations:
                print(f"Route: {du.route}")
                print(f" • Onset: {du.onset} | Peak: {du.peak} | Total: {du.total_duration} | After effects: {du.after_effects}")

        if sub.testing_reagents:
            print("\n[ Chemical Reagent Testing Colors ]")
            for r_name, r_color in sub.testing_reagents.items():
                print(f" • {r_name}: {r_color}")
        print("="*70 + "\n")

    elif args.command == "check-combo":
        res = engine.evaluate_combination(args.substances)
        print("\n" + "="*70)
        print(f"  COMBINATION RISK EVALUATION: {' + '.join(args.substances).upper()}")
        print("="*70)
        risk = res["overall_risk"]
        color = HarmReductionEngine.RISK_COLORS.get(risk, "\033[0m")
        print(f"OVERALL RISK LEVEL: {color_text(risk, color)}")

        if res["interactions"]:
            print("\nIdentified Interactions:")
            for inter in res["interactions"]:
                print(f"\n⚡ {inter['substance_a'].upper()} + {inter['substance_b'].upper()} [{inter['risk_level']}]")
                print(f"  Mechanism: {inter['mechanism']}")
                print(f"  Harm Reduction Advice: {inter['harm_reduction_advice']}")
        else:
            print("\nNo critical contraindications documented in database for this specific pairing.")
            print("Note: Always exercise caution when mixing substances.")
        print("="*70 + "\n")

    elif args.command == "check-dose":
        res = engine.evaluate_dosage(args.substance, args.amount, unit=args.unit, route=args.route)
        if not res.get("found"):
            print(res.get("message"))
            sys.exit(1)

        print("\n" + "="*70)
        print(f"  DOSAGE ASSESSMENT: {res['substance'].upper()} ({res['input_dose']} {res['route']})")
        print("="*70)
        status = res["status"]
        if "OVERDOSE" in status or "HEAVY" in status:
            color = "\033[91m"
        elif "STRONG" in status:
            color = "\033[33m"
        else:
            color = "\033[92m"
        print(f"STATUS: {color_text(status, color)}")
        print(f"\nReference Bounds ({res['route']}):")
        print(f" • Threshold: {res.get('threshold') or 'N/A'}")
        print(f" • Light:     {res.get('light') or 'N/A'}")
        print(f" • Common:    {res.get('common') or 'N/A'}")
        print(f" • Heavy:     {res.get('heavy') or 'N/A'}")
        if res.get("notes"):
            print(f"Notes: {res['notes']}")
        print(f"\nSafety Summary:\n{res.get('harm_summary')}")
        print("="*70 + "\n")

    elif args.command == "search":
        results = db.search_experiences(
            query=args.query,
            substance=args.substance,
            tag=args.tag,
            symptom=args.symptom,
            limit=args.limit
        )
        print(f"\nFound {len(results)} reports matching criteria:")
        print("-" * 75)
        for r in results:
            flags = f" [{', '.join(r['harm_flags'])}]" if r["harm_flags"] else ""
            print(f"Exp #{r['id']} | {r['title']} | {r['substance_summary']} ({r['exp_year'] or 'Unknown'}){flags}")
            print(f"  Author: {r['author']} | Weight: {r['body_weight'] or 'N/A'} | Words: {r['word_count']}")
            print(f"  Snippet: {r['snippet'][:120]}...\n")

    elif args.command == "view":
        exp = db.get_experience(args.id)
        if not exp:
            print(f"Experience #{args.id} not found in database. Try running 'scrape --id {args.id}' first.")
            sys.exit(1)

        print("\n" + "="*75)
        print(f"Exp #{exp.id}: {exp.title}")
        print(f"Substance: {exp.substance_summary} | Author: {exp.author} | Year: {exp.exp_year or 'N/A'}")
        print(f"Gender: {exp.gender or 'N/A'} | Age: {exp.age or 'N/A'} | Weight: {exp.body_weight or 'N/A'}")
        if exp.harm_flags:
            print(f"Harm Flags: {', '.join(exp.harm_flags)}")
        if exp.doses:
            print("Reported Doses:")
            for d in exp.doses:
                print(f" • {d.substance}: {d.amount or ''} {d.unit or ''} ({d.method or 'Oral'})")
        print("\n[ Report Narrative ]\n")
        print(exp.narrative)
        print("="*75 + "\n")

    elif args.command == "scrape":
        if args.id:
            print(f"Fetching Exp #{args.id} (checking cache and Wayback)...")
            report = scraper.fetch_and_save_experience(args.id, db)
            if report:
                print(f"✓ Successfully saved Exp #{report.id}: '{report.title}' ({report.substance_summary})")
                if report.harm_flags:
                    print(f"  Harm Flags Detected: {', '.join(report.harm_flags)}")
            else:
                print(f"✗ Failed to retrieve or parse Exp #{args.id}")
        elif args.range:
            start_id, end_id = args.range
            ids = list(range(start_id, end_id + 1))
            print(f"Batch scraping {len(ids)} reports from ID {start_id} to {end_id}...")
            res = scraper.batch_scrape(
                ids,
                db,
                min_delay=args.delay,
                max_delay=args.delay * 1.5,
                callback=lambda eid, ok, msg: print(f"[{'OK' if ok else 'FAIL'}] Exp #{eid}: {msg}")
            )
            print(f"\nFinished: {res['success']} saved ({res['skipped_cached']} from cache), {res['failed']} failed.")
        else:
            print("Please specify --id <ID> or --range <START> <END>")

    elif args.command == "import":
        import os
        if os.path.isdir(args.path):
            count = scraper.import_local_directory(
                args.path,
                db,
                callback=lambda name, ok, msg: print(f"[{'OK' if ok else 'FAIL'}] {name}: {msg}")
            )
            print(f"Imported {count} reports from directory.")
        elif os.path.isfile(args.path):
            rep = scraper.import_local_html(args.path, db)
            if rep:
                print(f"✓ Imported Exp #{rep.id}: {rep.title}")
            else:
                print(f"✗ Failed to import file: {args.path}")
        else:
            print(f"Path not found: {args.path}")

    elif args.command == "stats":
        stats = db.get_stats()
        print("\n" + "="*50)
        print("      EROWID SAFEDB DATABASE STATISTICS")
        print("="*50)
        print(f"Total Substances:        {stats['total_substances']}")
        print(f"Total Experience Reports:{stats['total_experiences']}")
        print(f"Interaction Rules:       {stats['total_interactions']}")
        print("\nTop Reported Tags:")
        for t in stats["top_tags"]:
            print(f" • {t['tag']}: {t['count']} reports")
        print("\nTop Adverse Symptoms Extracted:")
        for s in stats["top_adverse_symptoms"]:
            print(f" • {s['symptom']} ({s['severity']}): {s['count']} reports")
        print("="*50 + "\n")

    elif args.command == "web":
        start_server(db, port=args.port)


if __name__ == "__main__":
    main()
