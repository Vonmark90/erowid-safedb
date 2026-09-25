#!/usr/bin/env python3
"""
Universal GUI Launcher for Erowid SafeDB.
Starts the server and automatically opens the application interface.

Usage:
    python3 gui.py            # Opens modern web-based desktop application
    python3 gui.py --native   # Opens native CustomTkinter Cocoa window
"""

import sys
import os
import time
import socket
import argparse
import webbrowser
import threading
import http.server

# Add package root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from erowid_safedb.db import Database
from erowid_safedb.harm_reduction import HarmReductionEngine
from erowid_safedb.scraper import ErowidScraper
from erowid_safedb.web import SafeDBRequestHandler
from erowid_safedb.seed_data import seed_database


def find_free_port(start_port: int = 8080, max_attempts: int = 20) -> int:
    """Finds an unused TCP port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port


def launch_web_gui(db_path: str = "data/erowid_safedb.db", port: int = 8080):
    db = Database(db_path)
    scraper = ErowidScraper()

    # Ensure baseline data exists
    if db.get_stats()["total_substances"] == 0:
        print("🌱 Seeding initial clinical monographs and interaction data...")
        seed_database(db)

    # Ensure catalog is indexed
    if db.get_catalog_stats()["total_catalog_substances"] == 0:
        print("📚 Indexing Master Erowid Catalog (560+ substances)...")
        try:
            scraper.index_catalog(db)
        except Exception as e:
            print(f"[Warning] Catalog index notice: {e}")

    actual_port = find_free_port(port)
    url = f"http://localhost:{actual_port}"

    SafeDBRequestHandler.db = db
    SafeDBRequestHandler.engine = HarmReductionEngine(db)
    SafeDBRequestHandler.scraper = scraper

    server = http.server.HTTPServer(("0.0.0.0", actual_port), SafeDBRequestHandler)

    print("\n" + "=" * 65)
    print("  🛡️  EROWID SAFEDB - DESKTOP GUI APPLICATION")
    print("=" * 65)
    print(f"  URL:       {url}")
    print(f"  Database:  {os.path.abspath(db_path)}")
    print("  Features:  560+ Catalog, Universal On-Demand Reader,")
    print("             Drug Interaction Checker, Dosage Evaluator")
    print("=" * 65)
    print("\n🚀 Opening application in your browser...")
    print("Press Ctrl+C in this terminal to quit the application.\n")

    # Automatically open the browser
    def _open_browser():
        time.sleep(0.6)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Erowid SafeDB shutting down. Goodbye!")
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Erowid SafeDB Desktop GUI Launcher")
    parser.add_argument("--native", action="store_true", help="Launch native CustomTkinter window instead of web app")
    parser.add_argument("--port", type=int, default=8080, help="Port to host app (default: 8080)")
    parser.add_argument("--db", default="data/erowid_safedb.db", help="Path to SQLite database")
    args = parser.parse_args()

    if args.native:
        from erowid_safedb.gui_native import launch_native_gui
        print("🖥️ Launching Native CustomTkinter GUI...")
        launch_native_gui(args.db)
    else:
        launch_web_gui(db_path=args.db, port=args.port)


if __name__ == "__main__":
    main()
