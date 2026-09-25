"""
Command-Line Interface (CLI) for Erowid Harm Reduction & Master Archive Database.
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
        description="Erowid Harm Reduction & Comprehensive Master Archive CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 run.py init                                # Initialize DB & seed clinical data
  python3 run.py catalog "dmt"                       # Search 560+ substances in Erowid catalog
  python3 run.py substance 2cb                       # View dosing, safety profile, or catalog entry
  python3 run.py check-combo alcohol xanax           # Check multi-drug interactions & lethality
  python3 run.py check-dose mdma 220                 # Assess dosage safety against brackets
  python3 run.py search "overdose"                   # Search local vault with SQLite FTS5
  python3 run.py view 71809                          # View report (auto-fetches live if not local)
  python3 run.py harvest --substance ketamine        # Index all report IDs for a substance
  python3 run.py harvest --priority                  # Index safety-critical report IDs
  python3 run.py scrape --substance 2cb --limit 10   # Batch scrape harvested reports
  python3 run.py web --port 8080                     # Launch interactive web UI & API
        """
    )
    parser.add_argument("--db", default="data/erowid_safedb.db", help="Path to SQLite database file")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Command: init
    subparsers.add_parser("init", help="Initialize SQLite DB and seed with harm-reduction data")

    # Command: catalog
    catalog_parser = subparsers.add_parser("catalog", help="Browse or search the 560+ substance master Erowid catalog")
    catalog_parser.add_argument("query", nargs="?", default="", help="Search query (e.g. ketamine, 2c, spice, dmt)")
    catalog_parser.add_argument("--limit", type=int, default=20, help="Max results to display (default: 20)")
    catalog_parser.add_argument("--reindex", action="store_true", help="Re-index master catalog from exp_list.shtml")

    # Command: substance
    sub_parser = subparsers.add_parser("substance", help="Look up substance dosing, safety profile, or catalog entry")
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
    view_parser = subparsers.add_parser("view", help="View full details of an experience report (fetches live if needed)")
    view_parser.add_argument("id", type=int, help="Erowid Experience ID (e.g. 71809)")

    # Command: harvest
    harvest_parser = subparsers.add_parser("harvest", help="Discover and index experience report IDs from Erowid")
    harvest_parser.add_argument("--substance", help="Harvest all report IDs for a specific substance")
    harvest_parser.add_argument("--priority", action="store_true", help="Harvest high-risk reports (Health Problems, Bad Trips, Train Wrecks)")
    harvest_parser.add_argument("--limit", type=int, default=30, help="Max substances to check for priority harvest")

    # Command: scrape
    scrape_parser = subparsers.add_parser("scrape", help="Scrape experience reports from Erowid/Wayback")
    scrape_parser.add_argument("--id", type=int, help="Single Experience ID to scrape")
    scrape_parser.add_argument("--range", nargs=2, type=int, metavar=("START", "END"), help="Scrape ID range (inclusive)")
    scrape_parser.add_argument("--substance", help="Batch scrape harvested reports for a specific substance")
    scrape_parser.add_argument("--priority", action="store_true", help="Batch scrape harvested high-risk reports")
    scrape_parser.add_argument("--limit", type=int, default=20, help="Max harvested reports to scrape (default: 20)")
    scrape_parser.add_argument("--workers", type=int, default=3, help="Concurrent download threads (default: 3)")
    scrape_parser.add_argument("--delay", type=float, default=1.5, help="Polite delay between requests in seconds")

    # Command: import
    import_parser = subparsers.add_parser("import", help="Import local HTML files into database")
    import_parser.add_argument("path", help="Path to .html file or directory containing files")

    # Command: stats
    subparsers.add_parser("stats", help="Show database and catalog statistics")

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

    # Ensure catalog table is populated if initialized
    if db.get_catalog_stats()["total_catalog_substances"] == 0:
        try:
            scraper.index_catalog(db)
        except Exception:
            pass

    if args.command == "init":
        print(f"📦 Initializing database at '{args.db}'...")
        res = seed_database(db)
        print(f"✓ Seeded {res['substances_seeded']} clinical substance monographs")
        print(f"✓ Seeded {res['interactions_seeded']} interaction rules")
        print(f"✓ Seeded {res['reports_seeded']} annotated harm-reduction reports")
        cat_count = scraper.index_catalog(db)
        print(f"✓ Indexed {cat_count} substances in Master Erowid Catalog")
        print("Database ready for comprehensive harm reduction queries and crawling.")

    elif args.command == "catalog":
        if args.reindex:
            print("Re-indexing master catalog...")
            count = scraper.index_catalog(db)
            print(f"✓ Indexed {count} substances in catalog.")

        results = db.search_catalog(args.query, limit=args.limit)
        print(f"\nFound {len(results)} substances matching '{args.query}' in Master Erowid Catalog:")
        print("=" * 80)
        for r in results:
            desc = f" - {r['description']}" if r["description"] else ""
            cat_list = ", ".join(list(r["categories"].keys())[:5])
            if len(r["categories"]) > 5:
                cat_list += f" (+{len(r['categories']) - 5} more)"
            print(f"• {r['name']} [slug: {r['slug']}]{desc}")
            print(f"  Categories ({len(r['categories'])}): {cat_list or 'General'}")
            if r["total_reports"] > 0:
                print(f"  Harvested Reports: {r['total_reports']}")
            print()
        print("=" * 80)
        print("To harvest reports: python3 run.py harvest --substance <slug>")
        print("To view profile:    python3 run.py substance <slug>\n")

    elif args.command == "substance":
        sub = db.get_substance(args.name)
        if sub:
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
        else:
            # Check Erowid Master Catalog
            cat_entry = db.get_catalog_entry(args.name)
            if cat_entry:
                print("\n" + "="*70)
                print(f"  {cat_entry.name.upper()} (Erowid Master Catalog Profile)")
                print("="*70)
                if cat_entry.description:
                    print(f"Description / Chemistry: {cat_entry.description}")
                if cat_entry.synonyms:
                    print(f"Synonyms: {', '.join(cat_entry.synonyms)}")
                if cat_entry.master_url:
                    print(f"Erowid Vault URL: https://www.erowid.org/experiences/{cat_entry.master_url}")
                print(f"\nAvailable Report Categories ({len(cat_entry.categories)}):")
                for cname in sorted(cat_entry.categories.keys()):
                    print(f" • {cname}")
                if cat_entry.total_reports > 0:
                    print(f"\nHarvested Report IDs: {cat_entry.total_reports}")
                print(f"\nTo harvest all report IDs for this substance: python3 run.py harvest --substance {cat_entry.slug}")
                print(f"To scrape reports for this substance:       python3 run.py scrape --substance {cat_entry.slug} --limit 10")
                print("="*70 + "\n")
            else:
                print(f"Substance '{args.name}' not found. Run 'catalog {args.name}' to search the 560+ Erowid catalog.")
                sys.exit(1)

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
            print(f"Experience #{args.id} not in local database. Fetching on-the-fly from Erowid/Wayback...")
            exp = scraper.fetch_and_save_experience(args.id, db)

        if not exp:
            print(f"Could not retrieve or parse Experience #{args.id}. Verify ID exists on Erowid.")
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

    elif args.command == "harvest":
        if args.substance:
            print(f"Harvesting report IDs for substance '{args.substance}'...")
            count = scraper.harvest_substance_reports(
                args.substance,
                db,
                callback=lambda cat, n: print(f" • Category '{cat}': found {n} report links")
            )
            print(f"✓ Total {count} report IDs harvested for {args.substance}.")
        elif args.priority:
            print("Harvesting safety-critical report IDs (Health Problems, Bad Trips, Train Wrecks)...")
            count = scraper.harvest_priority_reports(
                db,
                max_substances=args.limit,
                callback=lambda sub, cat, n: print(f" • [{sub}] {cat}: {n} reports")
            )
            print(f"✓ Total {count} priority report IDs harvested into index.")
        else:
            print("Please specify --substance <NAME> or --priority")

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
        elif args.substance or args.priority:
            sub = args.substance if args.substance else None
            cat_filter = "Health Problems" if args.priority else None
            print(f"Scraping up to {args.limit} harvested reports (substance: {sub or 'all'}, workers: {args.workers})...")
            res = scraper.scrape_harvested_batch(
                db,
                substance_slug=sub,
                category=cat_filter,
                limit=args.limit,
                max_workers=args.workers,
                delay=args.delay,
                callback=lambda eid, ok, msg: print(f"[{'OK' if ok else 'FAIL'}] Exp #{eid}: {msg}")
            )
            print(f"\nBatch Complete: {res['success']}/{res['total']} saved successfully.")
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
            print("Specify --id <ID>, --range <START> <END>, or --substance <NAME>")

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
        cat_stats = db.get_catalog_stats()
        print("\n" + "="*55)
        print("         EROWID SAFEDB & ARCHIVE STATISTICS")
        print("="*55)
        print(f"Clinical Substance Dossiers: {stats['total_substances']}")
        print(f"Erowid Master Catalog Subs:  {cat_stats['total_catalog_substances']}")
        print(f"Harvested Erowid Report IDs: {cat_stats['total_indexed_reports']}")
        print(f"Local Full Experience Vault: {stats['total_experiences']}")
        print(f"Multi-Drug Interaction Rules:{stats['total_interactions']}")
        print("\nTop Reported Tags in Vault:")
        for t in stats["top_tags"]:
            print(f" • {t['tag']}: {t['count']} reports")
        print("\nTop Adverse Symptoms Extracted:")
        for s in stats["top_adverse_symptoms"]:
            print(f" • {s['symptom']} ({s['severity']}): {s['count']} reports")
        print("="*55 + "\n")

    elif args.command == "web":
        start_server(db, port=args.port)


if __name__ == "__main__":
    main()
