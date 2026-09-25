#!/usr/bin/env python3
"""
Script to build the ultra-professional web.py for Erowid SafeDB.
"""

import os

header_part = '''"""
Zero-dependency HTTP Web Server and Harm Reduction Dashboard for Erowid SafeDB.
Serves a responsive single-page application and RESTful JSON API with master catalog access.
"""

import os
import http.server
import json
import urllib.parse
from typing import Dict, Any
from erowid_safedb.db import Database
from erowid_safedb.harm_reduction import HarmReductionEngine
from erowid_safedb.scraper import ErowidScraper


class SafeDBRequestHandler(http.server.BaseHTTPRequestHandler):
    db: Database = None
    engine: HarmReductionEngine = None
    scraper: ErowidScraper = None

    def log_message(self, format, *args):
        # Silence default stderr logging to prevent BrokenPipeError in headless mode
        pass

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Connection", "close")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        try:
            self._handle_get()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _handle_get(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Serve static UI
        if path in ["/", "/index.html"]:
            self._set_headers(200, "text/html")
            self.wfile.write(HTML_TEMPLATE.encode("utf-8"))
            return

        if path in ["/app_icon.png", "/assets/app_icon.png"]:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "app_icon.png")
            if os.path.exists(icon_path):
                self._set_headers(200, "image/png")
                with open(icon_path, "rb") as f:
                    self.wfile.write(f.read())
                return

        # API Endpoints
        if path == "/api/stats":
            stats = self.db.get_stats()
            self._set_headers(200)
            self.wfile.write(json.dumps(stats).encode("utf-8"))
            return

        elif path == "/api/catalog-stats":
            cat_stats = self.db.get_catalog_stats()
            self._set_headers(200)
            self.wfile.write(json.dumps(cat_stats).encode("utf-8"))
            return

        elif path == "/api/catalog":
            q = query.get("q", [""])[0]
            cat = query.get("category", [""])[0]
            limit = int(query.get("limit", [50])[0])
            offset = int(query.get("offset", [0])[0])
            entries = self.db.search_catalog(query=q, category=cat, limit=limit, offset=offset)
            self._set_headers(200)
            self.wfile.write(json.dumps(entries).encode("utf-8"))
            return

        elif path == "/api/substance-names":
            subs = self.db.get_all_substances()
            cat_entries = self.db.search_catalog(limit=600)
            names = [{"name": s.name, "slug": s.slug, "type": "clinical", "category": s.category} for s in subs]
            existing_slugs = {s.slug.lower() for s in subs}
            for c in cat_entries:
                if c["slug"].lower() not in existing_slugs:
                    names.append({"name": c["name"], "slug": c["slug"], "type": "catalog", "category": "Catalog"})
            self._set_headers(200)
            self.wfile.write(json.dumps(names).encode("utf-8"))
            return

        elif path == "/api/catalog-substance":
            slug = query.get("slug", [""])[0]
            entry = self.db.get_catalog_entry(slug)
            if entry:
                self._set_headers(200)
                self.wfile.write(json.dumps(entry.to_dict()).encode("utf-8"))
            else:
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": "Catalog entry not found"}).encode("utf-8"))
            return

        elif path == "/api/substances":
            subs = self.db.get_all_substances()
            self._set_headers(200)
            self.wfile.write(json.dumps([s.to_dict() for s in subs]).encode("utf-8"))
            return

        elif path == "/api/substance":
            name = query.get("name", [""])[0]
            sub = self.db.get_substance(name)
            if sub:
                self._set_headers(200)
                self.wfile.write(json.dumps(sub.to_dict()).encode("utf-8"))
            else:
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": "Substance not found"}).encode("utf-8"))
            return

        elif path == "/api/experiences":
            q = query.get("q", [None])[0]
            sub = query.get("substance", [None])[0]
            tag = query.get("tag", [None])[0]
            sym = query.get("symptom", [None])[0]
            limit = int(query.get("limit", [30])[0])
            offset = int(query.get("offset", [0])[0])

            results = self.db.search_experiences(query=q, substance=sub, tag=tag, symptom=sym, limit=limit, offset=offset)
            self._set_headers(200)
            self.wfile.write(json.dumps(results).encode("utf-8"))
            return

        elif path == "/api/experience":
            exp_id_str = query.get("id", [""])[0]
            try:
                exp_id = int(exp_id_str)
                exp = self.db.get_experience(exp_id)
                # Auto-fetch on the fly from archive if not found locally
                if not exp:
                    exp = self.scraper.fetch_and_save_experience(exp_id, self.db)

                if exp:
                    self._set_headers(200)
                    self.wfile.write(json.dumps(exp.to_dict()).encode("utf-8"))
                else:
                    self._set_headers(404)
                    self.wfile.write(json.dumps({"error": f"Experience report #{exp_id} could not be retrieved from Erowid archive."}).encode("utf-8"))
            except ValueError:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid Experience ID"}).encode("utf-8"))
            return

        elif path == "/api/interactions":
            sub = query.get("substance", [""])[0]
            if sub:
                inters = self.db.get_interactions_for_substance(sub)
                self._set_headers(200)
                self.wfile.write(json.dumps([
                    {
                        "substance_a": i.substance_a,
                        "substance_b": i.substance_b,
                        "risk_level": i.risk_level,
                        "mechanism": i.mechanism,
                        "harm_reduction_advice": i.harm_reduction_advice
                    } for i in inters
                ]).encode("utf-8"))
            else:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing substance parameter"}).encode("utf-8"))
            return

        elif path == "/api/check-dose":
            sub = query.get("substance", [""])[0]
            amt_str = query.get("amount", [""])[0]
            unit = query.get("unit", ["mg"])[0]
            route = query.get("route", ["Oral"])[0]
            try:
                amt = float(amt_str)
                eval_result = self.engine.analyze_dose(sub, amt, unit=unit, route=route)
                self._set_headers(200)
                self.wfile.write(json.dumps(eval_result).encode("utf-8"))
            except ValueError:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid amount number"}).encode("utf-8"))
            return

        elif path == "/api/emergency-protocol":
            self._set_headers(200)
            self.wfile.write(json.dumps(self.engine.get_emergency_protocol()).encode("utf-8"))
            return

        elif path == "/api/testing-guide":
            self._set_headers(200)
            self.wfile.write(json.dumps(self.engine.get_testing_guide()).encode("utf-8"))
            return

        # 404
        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

    def do_POST(self):
        try:
            self._handle_post()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _handle_post(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"

        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if path == "/api/check-combo":
            substances = payload.get("substances", [])
            result = self.engine.evaluate_combination(substances)
            self._set_headers(200)
            self.wfile.write(json.dumps(result).encode("utf-8"))
            return

        elif path == "/api/scrape":
            exp_id = payload.get("exp_id")
            if not exp_id:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Missing exp_id"}).encode("utf-8"))
                return
            try:
                exp_id = int(exp_id)
                report = self.scraper.fetch_and_save_experience(exp_id, self.db)
                if report:
                    self._set_headers(200)
                    self.wfile.write(json.dumps({"success": True, "report": report.to_dict()}).encode("utf-8"))
                else:
                    self._set_headers(404)
                    self.wfile.write(json.dumps({"success": False, "message": "Failed to fetch or parse report."}).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        elif path == "/api/harvest":
            sub_slug = payload.get("substance")
            is_priority = payload.get("priority", False)
            if sub_slug:
                count = self.scraper.harvest_substance_reports(sub_slug, self.db)
                self._set_headers(200)
                self.wfile.write(json.dumps({"success": True, "count": count, "substance": sub_slug}).encode("utf-8"))
                return
            elif is_priority:
                count = self.scraper.harvest_priority_reports(self.db, max_substances=20)
                self._set_headers(200)
                self.wfile.write(json.dumps({"success": True, "count": count}).encode("utf-8"))
                return
            else:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Specify substance or priority"}).encode("utf-8"))
                return

        elif path == "/api/batch-scrape":
            sub_slug = payload.get("substance")
            limit = int(payload.get("limit", 15))
            workers = int(payload.get("workers", 3))
            scraped = self.scraper.batch_scrape_substance_queue(self.db, sub_slug=sub_slug, limit=limit, max_workers=workers)
            self._set_headers(200)
            self.wfile.write(json.dumps({"success": len(scraped), "total": limit}).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Unknown POST route"}).encode("utf-8"))


def launch_server(db_path: str = "data/erowid_safedb.db", port: int = 8080):
    db = Database(db_path)
    SafeDBRequestHandler.db = db
    SafeDBRequestHandler.engine = HarmReductionEngine(db)
    SafeDBRequestHandler.scraper = ErowidScraper()

    # Index catalog if empty
    if db.get_catalog_stats()["total_catalog_substances"] == 0:
        try:
            SafeDBRequestHandler.scraper.index_catalog(db)
        except Exception:
            pass

    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), SafeDBRequestHandler)
    print(f"\\n🌐 Erowid SafeDB Web Interface running at: http://localhost:{port}")
    print("Press Ctrl+C to stop the server.\\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\\nStopping server...")
        server.server_close()
'''

print("Header ready. Creating HTML template...")
