"""
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
            if getattr(sys, "frozen", False):
                base_assets = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
            else:
                base_assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
            icon_path = os.path.join(base_assets, "assets", "app_icon.png")
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
                eval_result = self.engine.evaluate_dosage(sub, amt, unit=unit, route=route)
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


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Drug Harm Reduction Codex and Overdose Radar</title>
  <link rel="icon" type="image/png" href="/app_icon.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #07090e;
      --bg-gradient: radial-gradient(circle at 85% 15%, rgba(56, 189, 248, 0.08) 0%, transparent 40%),
                     radial-gradient(circle at 15% 85%, rgba(99, 102, 241, 0.07) 0%, transparent 40%),
                     #07090e;
      --card-bg: rgba(15, 23, 42, 0.72);
      --card-bg-solid: #0d1322;
      --card-border: rgba(148, 163, 184, 0.12);
      --card-border-subtle: rgba(255, 255, 255, 0.06);
      --card-hover: rgba(26, 38, 66, 0.85);
      --border-accent: rgba(56, 189, 248, 0.35);
      
      --text: #f8fafc;
      --text-secondary: #cbd5e1;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      
      --accent: #38bdf8;
      --accent-hover: #0ea5e9;
      --accent-glow: rgba(56, 189, 248, 0.22);
      --indigo: #6366f1;
      --indigo-glow: rgba(99, 102, 241, 0.22);
      
      --deadly: #ef4444;
      --deadly-bg: rgba(239, 68, 68, 0.14);
      --deadly-border: rgba(239, 68, 68, 0.4);
      --deadly-glow: rgba(239, 68, 68, 0.35);
      
      --dangerous: #f97316;
      --dangerous-bg: rgba(249, 115, 22, 0.14);
      --dangerous-border: rgba(249, 115, 22, 0.4);
      
      --caution: #f59e0b;
      --caution-bg: rgba(245, 158, 11, 0.14);
      --caution-border: rgba(245, 158, 11, 0.4);
      
      --safe: #10b981;
      --safe-bg: rgba(16, 185, 129, 0.14);
      --safe-border: rgba(16, 185, 129, 0.4);
      --safe-glow: rgba(16, 185, 129, 0.25);
      
      --radius-xl: 18px;
      --radius-lg: 14px;
      --radius: 10px;
      --radius-sm: 6px;
      
      --font-display: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif;
      --font-sans: "Inter", -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
      --font-mono: "JetBrains Mono", SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    body {
      background: var(--bg-gradient);
      background-attachment: fixed;
      color: var(--text);
      font-family: var(--font-sans);
      line-height: 1.6;
      min-height: 100vh;
      overflow-x: hidden;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
    }

    /* Subtle Glassmorphism App Header */
    header {
      position: sticky; top: 0; z-index: 100;
      background: rgba(7, 9, 14, 0.82);
      backdrop-filter: blur(24px) saturate(180%);
      -webkit-backdrop-filter: blur(24px) saturate(180%);
      border-bottom: 1px solid var(--card-border);
      padding: 0.75rem 2rem;
      display: flex; justify-content: space-between; align-items: center; gap: 1.2rem;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
    }

    .brand-cluster {
      display: flex; align-items: center; gap: 0.9rem;
    }
    .brand-icon-box {
      width: 42px; height: 42px; border-radius: 11px;
      background: linear-gradient(135deg, rgba(56, 189, 248, 0.25) 0%, rgba(99, 102, 241, 0.25) 100%);
      border: 1px solid rgba(56, 189, 248, 0.4);
      box-shadow: 0 0 16px rgba(56, 189, 248, 0.25);
      display: flex; align-items: center; justify-content: center;
      position: relative; overflow: hidden;
    }
    .brand-icon-box img {
      width: 100%; height: 100%; object-fit: cover; display: block;
    }
    .brand-title-wrap {
      display: flex; flex-direction: column;
    }
    .brand-title {
      font-family: var(--font-display);
      font-size: 1.25rem; font-weight: 800;
      letter-spacing: -0.02em; color: #fff;
      display: flex; align-items: center; gap: 0.5rem;
    }
    .brand-badge {
      font-family: var(--font-mono);
      font-size: 0.62rem; font-weight: 700;
      background: linear-gradient(135deg, rgba(56, 189, 248, 0.15) 0%, rgba(99, 102, 241, 0.15) 100%);
      color: var(--accent);
      border: 1px solid var(--border-accent);
      padding: 0.15rem 0.45rem; border-radius: 5px;
      letter-spacing: 0.05em; text-transform: uppercase;
    }
    .brand-subtitle {
      font-size: 0.76rem; color: var(--text-muted);
      letter-spacing: 0.01em; display: flex; align-items: center; gap: 0.4rem;
    }

    /* Header Actions Cluster */
    .header-actions {
      display: flex; align-items: center; gap: 0.75rem;
    }

    .telemetry-pill {
      background: rgba(16, 185, 129, 0.08);
      border: 1px solid rgba(16, 185, 129, 0.25);
      color: #34d399;
      font-family: var(--font-mono);
      font-size: 0.74rem; font-weight: 600;
      padding: 0.4rem 0.85rem; border-radius: 30px;
      display: flex; align-items: center; gap: 0.5rem;
      letter-spacing: -0.01em;
    }
    .pulse-dot {
      width: 7px; height: 7px; border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 10px #10b981;
      animation: beacon 2s infinite;
    }
    @keyframes beacon {
      0%, 100% { transform: scale(1); opacity: 1; }
      50% { transform: scale(1.35); opacity: 0.4; }
    }

    /* Global Spotlight Search Button */
    .btn-spotlight-trigger {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      padding: 0.42rem 0.85rem; border-radius: 20px;
      font-size: 0.78rem; font-weight: 500;
      cursor: pointer; display: flex; align-items: center; gap: 0.5rem;
      transition: all 0.2s ease;
    }
    .btn-spotlight-trigger:hover {
      background: rgba(255, 255, 255, 0.09);
      border-color: var(--border-accent);
      color: #fff;
    }
    .kbd-shortcut {
      font-family: var(--font-mono);
      font-size: 0.65rem; background: rgba(0, 0, 0, 0.4);
      border: 1px solid rgba(255, 255, 255, 0.15);
      padding: 0.1rem 0.35rem; border-radius: 4px;
      color: var(--accent); font-weight: 600;
    }

    /* Emergency Overdose Callout Button */
    .btn-emergency-top {
      background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%);
      color: #fff;
      font-family: var(--font-display);
      font-weight: 700; font-size: 0.82rem;
      border: none; padding: 0.48rem 1.05rem;
      border-radius: 24px; cursor: pointer;
      display: flex; align-items: center; gap: 0.45rem;
      box-shadow: 0 0 20px rgba(239, 68, 68, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.2);
      transition: all 0.2s ease;
      animation: emergencyPulse 2.8s infinite;
    }
    .btn-emergency-top:hover {
      transform: translateY(-1px);
      box-shadow: 0 0 28px rgba(239, 68, 68, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.3);
    }
    @keyframes emergencyPulse {
      0%, 100% { box-shadow: 0 0 18px rgba(239, 68, 68, 0.35); }
      50% { box-shadow: 0 0 32px rgba(239, 68, 68, 0.65); }
    }

    /* Modern Segmented Floating Dock Navigation */
    nav.tab-nav {
      background: rgba(13, 19, 34, 0.75);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--card-border);
      padding: 0.45rem 2rem;
      display: flex; gap: 0.35rem; overflow-x: auto;
      scrollbar-width: none;
    }
    nav.tab-nav::-webkit-scrollbar { display: none; }
    
    nav.tab-nav button {
      background: transparent;
      border: 1px solid transparent;
      color: var(--text-muted);
      padding: 0.55rem 0.95rem;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-family: var(--font-display);
      font-size: 0.85rem; font-weight: 600;
      display: flex; align-items: center; gap: 0.45rem;
      transition: all 0.18s cubic-bezier(0.16, 1, 0.3, 1);
      white-space: nowrap;
      position: relative;
    }
    nav.tab-nav button:hover {
      background: rgba(255, 255, 255, 0.04);
      color: #fff;
    }
    nav.tab-nav button.active {
      background: rgba(30, 41, 59, 0.8);
      color: var(--accent);
      border-color: rgba(56, 189, 248, 0.3);
      box-shadow: 0 2px 14px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    }
    nav.tab-nav button.active::after {
      content: '';
      position: absolute; bottom: -0.45rem; left: 15%; width: 70%; height: 2px;
      background: var(--accent);
      border-radius: 2px;
      box-shadow: 0 0 10px var(--accent);
    }

    /* Main Container Layout */
    main {
      max-width: 1360px;
      margin: 1.4rem auto;
      padding: 0 1.6rem 3rem 1.6rem;
    }
    .tab-content { display: none; }
    .tab-content.active {
      display: block;
      animation: tabFadeIn 0.22s cubic-bezier(0.16, 1, 0.3, 1);
    }
    @keyframes tabFadeIn {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Glass Cards */
    .card {
      background: var(--card-bg);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--card-border);
      border-radius: var(--radius-lg);
      padding: 1.5rem;
      margin-bottom: 1.4rem;
      box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5), inset 0 1px 0 var(--card-border-subtle);
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    .card:hover {
      border-color: rgba(148, 163, 184, 0.22);
    }
    .card-header {
      display: flex; justify-content: space-between; align-items: center;
      margin-bottom: 1.1rem; border-bottom: 1px solid var(--card-border);
      padding-bottom: 0.75rem; flex-wrap: wrap; gap: 0.8rem;
    }
    .card-title {
      font-family: var(--font-display);
      font-size: 1.22rem; font-weight: 700; color: #fff;
      display: flex; align-items: center; gap: 0.55rem;
      letter-spacing: -0.01em;
    }
    .card-subtitle {
      font-size: 0.8rem; color: var(--text-muted);
    }

    .grid-2 {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
      gap: 1.3rem;
    }
    .grid-3 {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(295px, 1fr));
      gap: 1.1rem;
    }

    /* Form Controls & Inputs */
    label.field-label {
      font-family: var(--font-display);
      font-size: 0.74rem; font-weight: 700;
      color: var(--text-muted);
      letter-spacing: 0.04em; text-transform: uppercase;
      margin-bottom: 0.35rem; display: block;
    }
    input, select, textarea {
      background: #090e1a;
      border: 1px solid var(--card-border);
      color: #fff;
      padding: 0.7rem 0.95rem;
      border-radius: var(--radius-sm);
      font-family: var(--font-sans);
      font-size: 0.9rem;
      width: 100%;
      outline: none;
      transition: all 0.15s ease;
    }
    input:focus, select:focus, textarea:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 2px var(--accent-glow);
      background: #0b1222;
    }
    input::placeholder { color: var(--text-dim); }

    button.btn-primary {
      background: linear-gradient(135deg, var(--accent) 0%, #0284c7 100%);
      color: #050b14;
      font-family: var(--font-display);
      font-weight: 700; font-size: 0.88rem;
      border: none; padding: 0.7rem 1.4rem;
      border-radius: var(--radius-sm);
      cursor: pointer; display: inline-flex; align-items: center; justify-content: center; gap: 0.45rem;
      box-shadow: 0 4px 14px rgba(56, 189, 248, 0.25);
      transition: all 0.15s ease;
    }
    button.btn-primary:hover {
      filter: brightness(1.1); transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(56, 189, 248, 0.4);
    }
    button.btn-primary:active { transform: translateY(0); }

    button.btn-secondary {
      background: rgba(30, 41, 59, 0.7);
      color: #e2e8f0;
      border: 1px solid rgba(255, 255, 255, 0.08);
      padding: 0.5rem 0.9rem;
      border-radius: var(--radius-sm);
      cursor: pointer; font-family: var(--font-sans);
      font-size: 0.82rem; font-weight: 600;
      display: inline-flex; align-items: center; justify-content: center; gap: 0.35rem;
      transition: all 0.15s ease;
    }
    button.btn-secondary:hover {
      background: rgba(51, 65, 85, 0.9);
      color: #fff;
      border-color: rgba(255, 255, 255, 0.18);
    }

    /* Chips & Interactive Pills */
    .chip {
      display: inline-flex; align-items: center; gap: 0.4rem;
      background: rgba(24, 34, 58, 0.65);
      border: 1px solid var(--card-border);
      color: #cbd5e1;
      padding: 0.35rem 0.8rem;
      border-radius: 20px;
      font-size: 0.8rem; font-weight: 500;
      cursor: pointer; user-select: none;
      transition: all 0.15s ease;
    }
    .chip:hover {
      background: rgba(34, 50, 84, 0.9);
      color: #fff;
      border-color: var(--border-accent);
      transform: translateY(-1px);
    }
    .chip.active {
      background: rgba(56, 189, 248, 0.18);
      color: var(--accent);
      border-color: var(--accent);
      font-weight: 600;
      box-shadow: 0 0 12px rgba(56, 189, 248, 0.2);
    }
    .chip .chip-remove {
      margin-left: 0.2rem; cursor: pointer; color: #94a3b8;
      font-size: 0.95rem; font-weight: 700;
      transition: color 0.15s;
    }
    .chip .chip-remove:hover { color: var(--deadly); }

    /* Risk Badges & Markers */
    .badge {
      display: inline-flex; align-items: center; gap: 0.35rem;
      padding: 0.28rem 0.65rem;
      border-radius: 6px;
      font-family: var(--font-mono);
      font-size: 0.72rem; font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .badge-deadly {
      background: var(--deadly-bg);
      color: #f87171;
      border: 1px solid var(--deadly-border);
      box-shadow: 0 0 10px rgba(239, 68, 68, 0.2);
    }
    .badge-dangerous {
      background: var(--dangerous-bg);
      color: #fb923c;
      border: 1px solid var(--dangerous-border);
    }
    .badge-caution {
      background: var(--caution-bg);
      color: #fbbf24;
      border: 1px solid var(--caution-border);
    }
    .badge-safe {
      background: var(--safe-bg);
      color: #34d399;
      border: 1px solid var(--safe-border);
      box-shadow: 0 0 10px rgba(16, 185, 129, 0.2);
    }
    .badge-cat {
      background: rgba(30, 41, 59, 0.8);
      color: #94a3b8;
      font-size: 0.7rem; font-weight: 600;
      border-radius: 12px;
      padding: 0.18rem 0.55rem;
      border: 1px solid rgba(255, 255, 255, 0.06);
    }

    /* Scientific Precision Dosage Meter */
    .dosage-gauge-card {
      background: #090e1a;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-lg);
      padding: 1.4rem;
      margin: 1.1rem 0;
      position: relative;
    }
    .dosage-gauge-track {
      position: relative;
      height: 28px;
      border-radius: 14px;
      background: #060a12;
      border: 1px solid rgba(255, 255, 255, 0.06);
      margin: 2.2rem 0 1rem 0;
      overflow: visible;
      display: flex;
    }
    .gauge-zone {
      height: 100%; position: relative;
      transition: opacity 0.2s;
    }
    .gauge-zone-threshold { width: 15%; background: linear-gradient(to right, #0ea5e9, #06b6d4); border-top-left-radius: 14px; border-bottom-left-radius: 14px; }
    .gauge-zone-light { width: 20%; background: linear-gradient(to right, #06b6d4, #10b981); }
    .gauge-zone-common { width: 30%; background: linear-gradient(to right, #10b981, #6366f1); }
    .gauge-zone-strong { width: 20%; background: linear-gradient(to right, #6366f1, #f59e0b); }
    .gauge-zone-heavy { width: 15%; background: linear-gradient(to right, #f59e0b, #ef4444); border-top-right-radius: 14px; border-bottom-right-radius: 14px; }

    /* The Gliding Pointer Needle */
    .dosage-needle {
      position: absolute;
      top: -14px;
      transform: translateX(-50%);
      width: 4px;
      height: 56px;
      background: #fff;
      border-radius: 2px;
      box-shadow: 0 0 16px rgba(255, 255, 255, 0.9), 0 0 24px var(--accent);
      transition: left 0.4s cubic-bezier(0.16, 1, 0.3, 1);
      z-index: 10;
      pointer-events: none;
    }
    .dosage-needle::before {
      content: '';
      position: absolute; top: -8px; left: -6px;
      width: 16px; height: 16px;
      background: #fff; border-radius: 50%;
      box-shadow: 0 0 12px #38bdf8;
    }
    .dosage-needle-val {
      position: absolute; top: -32px; left: 50%;
      transform: translateX(-50%);
      background: #000;
      border: 1px solid var(--accent);
      color: #fff; font-family: var(--font-mono);
      font-size: 0.72rem; font-weight: 700;
      padding: 0.15rem 0.5rem; border-radius: 4px;
      white-space: nowrap; box-shadow: 0 2px 8px rgba(0,0,0,0.6);
    }

    .dosage-labels-bar {
      display: flex; justify-content: space-between;
      font-family: var(--font-mono);
      font-size: 0.72rem; font-weight: 600;
      color: var(--text-muted);
      margin-top: 0.5rem;
    }

    /* Pharmacokinetics Timeline Dashboard Grid */
    .timeline-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 0.65rem;
      margin-top: 1rem;
    }
    .timeline-tile {
      background: rgba(13, 19, 34, 0.85);
      border: 1px solid var(--card-border);
      border-radius: var(--radius-sm);
      padding: 0.75rem 0.85rem;
      display: flex; flex-direction: column; gap: 0.2rem;
    }
    .timeline-label {
      font-family: var(--font-display);
      font-size: 0.68rem; font-weight: 700;
      color: var(--text-dim); text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .timeline-val {
      font-family: var(--font-mono);
      font-size: 0.86rem; font-weight: 700;
      color: #fff;
    }

    /* Synergistic Multi-Drug Risk Alert Box */
    .risk-banner {
      border-radius: var(--radius-lg);
      padding: 1.5rem;
      margin: 1.2rem 0;
      position: relative; overflow: hidden;
      display: flex; flex-direction: column; gap: 0.85rem;
      box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
    }
    .risk-banner-deadly {
      background: linear-gradient(135deg, rgba(239, 68, 68, 0.16) 0%, rgba(185, 28, 28, 0.1) 100%);
      border: 1px solid var(--deadly);
      box-shadow: 0 0 35px rgba(239, 68, 68, 0.25);
    }
    .risk-banner-dangerous {
      background: linear-gradient(135deg, rgba(249, 115, 22, 0.16) 0%, rgba(194, 65, 12, 0.1) 100%);
      border: 1px solid var(--dangerous);
    }
    .risk-banner-caution {
      background: linear-gradient(135deg, rgba(245, 158, 11, 0.16) 0%, rgba(180, 83, 9, 0.1) 100%);
      border: 1px solid var(--caution);
    }
    .risk-banner-safe {
      background: linear-gradient(135deg, rgba(16, 185, 129, 0.16) 0%, rgba(4, 120, 87, 0.1) 100%);
      border: 1px solid var(--safe);
    }

    /* Pairwise Mechanism Breakdown Card */
    .pairwise-card {
      background: #090e1a;
      border: 1px solid var(--card-border);
      border-left-width: 5px;
      border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
      padding: 1.1rem 1.3rem;
      margin-bottom: 0.85rem;
      transition: transform 0.15s ease;
    }
    .pairwise-card:hover {
      transform: translateX(3px);
    }

    /* Alphabetical A-Z Navigation Jump Bar */
    .alphabet-bar {
      display: flex; flex-wrap: wrap; gap: 0.3rem;
      margin-bottom: 1rem;
      padding: 0.5rem;
      background: #090e1a;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-sm);
    }
    .alphabet-btn {
      width: 28px; height: 28px;
      border-radius: 4px; border: 1px solid transparent;
      background: transparent; color: var(--text-muted);
      font-family: var(--font-mono); font-size: 0.76rem; font-weight: 700;
      cursor: pointer; display: flex; align-items: center; justify-content: center;
      transition: all 0.15s;
    }
    .alphabet-btn:hover {
      background: rgba(255, 255, 255, 0.08); color: #fff;
    }
    .alphabet-btn.active {
      background: var(--accent); color: #050b14; font-weight: 800;
      box-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
    }

    /* Reagent Visualizer Grid */
    .reagent-swatch-box {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 0.9rem;
      margin-top: 1rem;
    }
    .reagent-card {
      background: #090e1a;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-sm);
      padding: 1rem;
      display: flex; flex-direction: column; gap: 0.5rem;
    }
    .reagent-swatch {
      height: 22px; border-radius: 4px;
      border: 1px solid rgba(255, 255, 255, 0.15);
      margin: 0.3rem 0;
    }

    /* Modals & Dialogs */
    .modal {
      display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(4, 7, 14, 0.85); backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      z-index: 1000; justify-content: center; align-items: center; padding: 1.5rem;
    }
    .modal.active { display: flex; animation: modalFadeIn 0.2s cubic-bezier(0.16, 1, 0.3, 1); }
    @keyframes modalFadeIn {
      from { opacity: 0; transform: scale(0.96); }
      to { opacity: 1; transform: scale(1); }
    }
    .modal-content {
      background: #0d1322;
      border: 1px solid var(--card-border);
      border-radius: var(--radius-xl);
      max-width: 900px; width: 100%; max-height: 90vh;
      overflow-y: auto; padding: 2.2rem; position: relative;
      box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.85), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    }
    .modal-close {
      position: absolute; top: 1.3rem; right: 1.3rem;
      background: rgba(30, 41, 59, 0.7); color: #fff;
      border: 1px solid rgba(255, 255, 255, 0.1);
      width: 34px; height: 34px; border-radius: 50%;
      font-size: 1.2rem; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      transition: all 0.15s;
    }
    .modal-close:hover {
      background: rgba(51, 65, 85, 1);
      transform: scale(1.05);
    }

    /* Tables */
    table.data-table {
      width: 100%; border-collapse: collapse; margin-top: 0.85rem; font-size: 0.88rem;
    }
    table.data-table th, table.data-table td {
      padding: 0.8rem; text-align: left; border-bottom: 1px solid var(--card-border);
    }
    table.data-table th {
      background: #090e1a; color: var(--accent);
      font-family: var(--font-display); font-weight: 700;
      font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em;
    }

    /* Experience Card */
    .exp-item {
      background: #090e1a;
      border: 1px solid var(--card-border);
      border-left: 4px solid var(--accent);
      border-radius: var(--radius-sm);
      padding: 1.1rem 1.3rem;
      margin-bottom: 0.9rem;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .exp-item:hover {
      background: #111828; transform: translateX(3px);
      border-color: var(--border-accent);
    }

    /* Spotlight Modal */
    #spotlightModal .modal-content {
      max-width: 650px;
      padding: 1.2rem;
      border: 1px solid var(--border-accent);
      box-shadow: 0 0 50px rgba(56, 189, 248, 0.25);
    }
  </style>
</head>
<body>

  <!-- Top Workstation Header -->
  <header>
    <div class="brand-cluster">
      <div class="brand-icon-box">
        <img src="/app_icon.png" alt="Erowid SafeDB" onerror="this.onerror=null; this.parentElement.innerHTML='<span style=\\'font-size:1.5rem;\\'>🛡️</span>';">
      </div>
      <div class="brand-title-wrap">
        <div class="brand-title">
          DRUG HARM REDUCTION CODEX
          <span class="brand-badge">OVERDOSE RADAR</span>
        </div>
        <div class="brand-subtitle">
          Overdose Radar & Clinical Pharmacology Workstation • Master Harm Reduction Vault
        </div>
      </div>
    </div>

    <div class="header-actions">
      <button class="btn-spotlight-trigger" onclick="openSpotlightModal()" title="Global Quick Search (Cmd+K)">
        <span>🔍 Search Vault & Catalog</span>
        <span class="kbd-shortcut">⌘K</span>
      </button>

      <div class="telemetry-pill">
        <span class="pulse-dot"></span>
        <span id="telemetryPillText">561 Substances • Zero-Network Engine</span>
      </div>

      <button class="btn-emergency-top" onclick="openEmergencyModal()" title="Emergency Overdose Protocol (Cmd+E)">
        <span>🚨</span> Emergency Protocol <span class="kbd-shortcut" style="background: rgba(0,0,0,0.3); color:#fff; border-color:rgba(255,255,255,0.3);">⌘E</span>
      </button>
    </div>
  </header>

  <!-- Segmented Dock Navigation -->
  <nav class="tab-nav">
    <button class="active" onclick="switchNav('dossiers')">
      <span>💊</span> Dossiers & Dosage Ladder
    </button>
    <button onclick="switchNav('radar')">
      <span>⚡</span> Combo Risk Radar
    </button>
    <button onclick="switchNav('catalog')">
      <span>📚</span> Master Catalog (560+)
    </button>
    <button onclick="switchNav('vault')">
      <span>📖</span> Experience Vault
    </button>
    <button onclick="switchNav('reagents')">
      <span>🧪</span> Reagents & Test Strips
    </button>
    <button onclick="switchNav('harvester')">
      <span>💾</span> Offline Database
    </button>
  </nav>

  <main>
    <!-- ==================== TAB 1: DOSSIERS & DOSAGE SAFETY LADDER ==================== -->
    <div id="tab-dossiers" class="tab-content active">
      <!-- Interactive Scientific Dosage Evaluator -->
      <div class="card" style="border-top: 3px solid var(--accent);">
        <div class="card-header">
          <div>
            <div class="card-title">⚖️ Interactive Clinical Dosage Safety Ladder</div>
            <div class="card-subtitle">Real-time physiological risk evaluation based on verified clinical thresholds and body weight</div>
          </div>
          <div id="doseHeaderBadge" class="badge badge-safe">COMMON RANGE</div>
        </div>

        <!-- Quick Pick Substances -->
        <div style="margin-bottom: 1.1rem;">
          <div style="font-family: var(--font-display); font-size: 0.74rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.45rem;">
            QUICK CLINICAL PRESETS:
          </div>
          <div style="display: flex; flex-wrap: wrap; gap: 0.45rem;">
            <span class="chip active" onclick="setDoseSubstance('MDMA', 120, 'mg', 'Oral', this)">MDMA (Molly)</span>
            <span class="chip" onclick="setDoseSubstance('Ketamine', 60, 'mg', 'Insufflated', this)">Ketamine</span>
            <span class="chip" onclick="setDoseSubstance('Psilocybin Mushrooms', 2.0, 'g', 'Oral', this)">Psilocybin (Shrooms)</span>
            <span class="chip" onclick="setDoseSubstance('LSD', 100, 'ug', 'Sublingual / Oral', this)">LSD (Acid)</span>
            <span class="chip" onclick="setDoseSubstance('Alprazolam', 0.5, 'mg', 'Oral', this)">Alprazolam (Xanax)</span>
            <span class="chip" onclick="setDoseSubstance('Cocaine', 50, 'mg', 'Insufflated', this)">Cocaine</span>
            <span class="chip" onclick="setDoseSubstance('2C-B', 18, 'mg', 'Oral', this)">2C-B</span>
            <span class="chip" onclick="setDoseSubstance('DXM', 250, 'mg', 'Oral', this)">DXM</span>
            <span class="chip" onclick="setDoseSubstance('Alcohol', 2, 'standard drinks', 'Oral', this)">Alcohol</span>
            <span class="chip" onclick="setDoseSubstance('Fentanyl', 0.02, 'mg', 'Insufflated', this)">Fentanyl</span>
          </div>
        </div>

        <!-- Inputs Row -->
        <div class="grid-2" style="margin-bottom: 1rem;">
          <div>
            <label class="field-label">Substance Name</label>
            <input type="text" id="doseSubInput" placeholder="e.g. MDMA, Ketamine, Psilocybin..." value="MDMA" oninput="runDoseCalculation()">
          </div>

          <div style="display: grid; grid-template-columns: 1fr 110px 140px; gap: 0.55rem;">
            <div>
              <label class="field-label">Intended Amount</label>
              <input type="number" id="doseAmtInput" placeholder="Amount" value="120" step="any" oninput="runDoseCalculation()">
            </div>
            <div>
              <label class="field-label">Unit</label>
              <select id="doseUnitSelect" onchange="runDoseCalculation()">
                <option value="mg">mg</option>
                <option value="g">g</option>
                <option value="ug">ug / mcg</option>
                <option value="ml">ml</option>
                <option value="standard drinks">drinks</option>
              </select>
            </div>
            <div>
              <label class="field-label">Route</label>
              <select id="doseRouteSelect" onchange="runDoseCalculation()">
                <option value="Oral">Oral</option>
                <option value="Insufflated">Insufflated</option>
                <option value="Sublingual">Sublingual</option>
                <option value="Inhalation">Inhalation</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Body Weight Harm Reduction Calculator -->
        <div style="background: #090e1a; border: 1px solid var(--card-border); border-radius: var(--radius-sm); padding: 0.95rem 1.2rem; margin-bottom: 1.2rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <span style="font-size: 1.4rem;">⚖️</span>
            <div>
              <div style="font-family: var(--font-display); font-size: 0.88rem; font-weight: 700; color: #fff;">
                Body Weight Harm Reduction Calculator
              </div>
              <div style="font-size: 0.78rem; color: var(--text-muted);">
                Clinical standard guideline for empathogens: 1.5 mg/kg body weight (Alexander Shulgin / MAPS protocol)
              </div>
            </div>
          </div>

          <div style="display: flex; align-items: center; gap: 0.6rem;">
            <input type="range" id="userWeightSlider" min="40" max="140" value="70" style="width: 130px; accent-color: var(--accent);" oninput="syncWeightSlider(this.value)">
            <input type="number" id="userWeightInput" value="70" style="width: 75px;" oninput="syncWeightInput(this.value)">
            <select id="userWeightUnit" style="width: 75px;" onchange="runDoseCalculation()">
              <option value="kg">kg</option>
              <option value="lbs">lbs</option>
            </select>
            <div id="weightDoseCalcOutput" style="font-family: var(--font-mono); font-size: 0.84rem; color: var(--accent); font-weight: 700; margin-left: 0.4rem; white-space: nowrap;">
              Guideline: ~105 mg
            </div>
          </div>
        </div>

        <!-- Scientific Dosage Meter Track -->
        <div class="dosage-gauge-card">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-family: var(--font-display); font-size: 0.82rem; font-weight: 700; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.04em;">
              Calibrated Safety Bracket Gauge:
            </span>
            <span id="doseStatusBadge" class="badge badge-safe">COMMON DOSE</span>
          </div>

          <div class="dosage-gauge-track">
            <div class="gauge-zone gauge-zone-threshold" title="Threshold (Microdose)"></div>
            <div class="gauge-zone gauge-zone-light" title="Light Dose"></div>
            <div class="gauge-zone gauge-zone-common" title="Common / Typical Dose"></div>
            <div class="gauge-zone gauge-zone-strong" title="Strong Dose"></div>
            <div class="gauge-zone gauge-zone-heavy" title="Heavy / Overdose Danger"></div>

            <!-- Pointer Needle -->
            <div id="doseLadderPointer" class="dosage-needle" style="left: 48%;">
              <div id="doseLadderValBubble" class="dosage-needle-val">120 mg</div>
            </div>
          </div>

          <div class="dosage-labels-bar">
            <span>Threshold (0-15%)</span>
            <span>Light (15-35%)</span>
            <span>Common (35-65%)</span>
            <span>Strong (65-85%)</span>
            <span style="color: var(--deadly);">Heavy / Toxic (85%+)</span>
          </div>

          <!-- Dynamic Bracket Cards Grid -->
          <div id="doseDetailsGrid" style="margin-top: 1.3rem; display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 0.85rem;">
            <!-- Populated via JavaScript -->
          </div>
        </div>
      </div>

      <!-- Curated Clinical Substance Monographs -->
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">📖 Curated Clinical Substance Monographs</div>
            <div class="card-subtitle">In-depth pharmacological profiles, receptor targets, toxicity notes, and duration kinetics</div>
          </div>
          <input type="text" id="subSearch" placeholder="Filter monographs (e.g. MDMA, Ketamine, Psilocybin)..." style="width: 280px;" onkeyup="filterSubstances()">
        </div>

        <div id="substancesList" class="grid-3"></div>
      </div>
    </div>

    <!-- ==================== TAB 2: COMBO RISK RADAR ==================== -->
    <div id="tab-radar" class="tab-content">
      <div class="card" style="border-top: 3px solid var(--dangerous);">
        <div class="card-header">
          <div>
            <div class="card-title">⚡ Multi-Drug Synergistic Risk & Contraindication Radar</div>
            <div class="card-subtitle">Detect lethal synergies (respiratory depression, serotonin toxicity, cardiac stress) across any combination</div>
          </div>
          <span class="badge badge-dangerous">PHARMACOLOGICAL MATRIX</span>
        </div>

        <!-- Categorized Quick Add Presets -->
        <div style="margin-bottom: 1.2rem;">
          <div style="font-family: var(--font-display); font-size: 0.74rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.5rem;">
            QUICK ADD PHARMACOLOGICAL AGENTS:
          </div>
          <div style="display: flex; flex-wrap: wrap; gap: 0.45rem;">
            <span class="chip" onclick="addComboSubstance('Alcohol')">🍺 Alcohol</span>
            <span class="chip" onclick="addComboSubstance('MDMA')">💊 MDMA</span>
            <span class="chip" onclick="addComboSubstance('Ketamine')">🐎 Ketamine</span>
            <span class="chip" onclick="addComboSubstance('Alprazolam')">💤 Alprazolam (Xanax)</span>
            <span class="chip" onclick="addComboSubstance('Oxycodone')">🔴 Oxycodone / Opioids</span>
            <span class="chip" onclick="addComboSubstance('Cocaine')">⚡ Cocaine</span>
            <span class="chip" onclick="addComboSubstance('LSD')">👁️ LSD</span>
            <span class="chip" onclick="addComboSubstance('Psilocybin')">🍄 Psilocybin</span>
            <span class="chip" onclick="addComboSubstance('Cannabis')">🌿 Cannabis (THC)</span>
            <span class="chip" onclick="addComboSubstance('DXM')">🧪 DXM</span>
            <span class="chip" onclick="addComboSubstance('SSRI')">🧠 SSRI Antidepressants</span>
            <span class="chip" onclick="addComboSubstance('MAOI')">⚠️ MAOIs</span>
            <span class="chip" onclick="addComboSubstance('GHB')">💧 GHB / GBL</span>
            <span class="chip" onclick="addComboSubstance('Amphetamine')">⚡ Amphetamine / Adderall</span>
            <span class="chip" onclick="addComboSubstance('Fentanyl')">☠️ Fentanyl</span>
            <span class="chip" onclick="addComboSubstance('Tramadol')">⚠️ Tramadol</span>
          </div>
        </div>

        <!-- Search & Add ANY from 560+ Catalog -->
        <div style="display: flex; gap: 0.6rem; margin-bottom: 1.2rem; position: relative;">
          <input type="text" id="comboSearchAdd" placeholder="Search and add ANY of 560+ substances from Erowid catalog (e.g. 2C-B, Methadone, Kratom)..." onkeydown="handleComboSearchKey(event)" oninput="filterComboSearchSuggestions(this.value)">
          <button class="btn-primary" onclick="addSearchedComboSubstance()" style="white-space: nowrap;">
            + Add to Radar
          </button>
          <div id="comboSuggestionsDropdown" style="display: none; position: absolute; top: 100%; left: 0; width: 85%; max-height: 200px; overflow-y: auto; background: #0b1222; border: 1px solid var(--border-accent); border-radius: 6px; z-index: 50; box-shadow: 0 10px 30px rgba(0,0,0,0.8);"></div>
        </div>

        <!-- Active Substances On Radar Tray -->
        <div style="background: #090e1a; border: 1px solid var(--card-border); border-radius: var(--radius-sm); padding: 1.1rem; margin-bottom: 1.4rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.65rem;">
            <div style="font-family: var(--font-display); font-size: 0.82rem; font-weight: 700; color: #fff; letter-spacing: 0.02em;">
              ACTIVE AGENTS ON RADAR (<span id="comboCount" style="color: var(--accent);">0</span>):
            </div>
            <button class="btn-secondary" onclick="clearComboSubstances()" style="padding: 0.2rem 0.65rem; font-size: 0.72rem;">
              Clear All
            </button>
          </div>
          <div id="comboActiveChips" style="display: flex; flex-wrap: wrap; gap: 0.5rem; min-height: 38px; align-items: center;">
            <span style="font-size: 0.82rem; color: var(--text-dim);">No substances selected yet. Click any quick-add chip above or search the catalog.</span>
          </div>
        </div>

        <!-- Dynamic Results Area -->
        <div id="comboResultsArea"></div>
      </div>
    </div>

    <!-- ==================== TAB 3: MASTER CATALOG (560+) ==================== -->
    <div id="tab-catalog" class="tab-content">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">📚 Master Erowid Taxonomy Archive Catalog</div>
            <div class="card-subtitle">Complete offline-indexed encyclopedia of 561 psychoactive substances and chemical botanicals</div>
          </div>
          <span class="badge" style="background: #090e1a; color: var(--accent); border: 1px solid var(--card-border);" id="catalogHeaderStats">
            561 Substances Indexed
          </span>
        </div>

        <!-- Alphabetical A-Z Jump Bar -->
        <div class="alphabet-bar" id="alphabetJumpBar">
          <button class="alphabet-btn active" onclick="jumpCatalogAlpha('', this)">ALL</button>
          <!-- Populated via JS for A-Z -->
        </div>

        <!-- Category Filter Pills -->
        <div style="margin-bottom: 1rem;">
          <div style="font-family: var(--font-display); font-size: 0.74rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.45rem;">
            TAXONOMY CATEGORIES:
          </div>
          <div style="display: flex; flex-wrap: wrap; gap: 0.4rem;" id="catalogCatPills">
            <span class="chip active" onclick="filterCatalogByCat('', this)">All Categories (561)</span>
            <span class="chip" onclick="filterCatalogByCat('psychedelic', this)">Psychedelics</span>
            <span class="chip" onclick="filterCatalogByCat('stimulant', this)">Stimulants</span>
            <span class="chip" onclick="filterCatalogByCat('depressant', this)">Depressants & Benzos</span>
            <span class="chip" onclick="filterCatalogByCat('dissociative', this)">Dissociatives</span>
            <span class="chip" onclick="filterCatalogByCat('opioid', this)">Opioids</span>
            <span class="chip" onclick="filterCatalogByCat('plant', this)">Botanicals & Herbs</span>
            <span class="chip" onclick="filterCatalogByCat('synthetic', this)">Synthetics & Nootropics</span>
          </div>
        </div>

        <!-- Live Instant Search -->
        <div style="margin-bottom: 1.3rem;">
          <input type="text" id="catalogSearch" placeholder="Search 561 substances by name, chemical formula, or category..." oninput="debounceCatalogSearch()">
        </div>

        <div id="catalogList" class="grid-3"></div>
      </div>
    </div>

    <!-- ==================== TAB 4: TRIP VAULT & UNIVERSAL READER ==================== -->
    <div id="tab-vault" class="tab-content">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">📖 Experience Vault & Universal Live Archive Reader</div>
            <div class="card-subtitle">Full-text query local SQLite reports and stream raw report snapshots directly from Erowid Wayback Archive</div>
          </div>
          <span class="badge badge-safe">FTS5 FULL-TEXT INDEX</span>
        </div>

        <!-- Universal Live Reader Bar -->
        <div style="background: #090e1a; border: 1px solid var(--border-accent); border-radius: var(--radius-sm); padding: 1.1rem; margin-bottom: 1.4rem; display: flex; gap: 1rem; align-items: center; flex-wrap: wrap;">
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span style="font-size: 1.4rem;">⚡</span>
            <div>
              <div style="font-family: var(--font-display); font-size: 0.88rem; font-weight: 700; color: var(--accent);">
                Universal On-Demand Archive Reader
              </div>
              <div style="font-size: 0.76rem; color: var(--text-muted);">
                Enter any Erowid Report ID (1 - 150,000) to fetch, decompress, and parse symptoms instantly:
              </div>
            </div>
          </div>

          <div style="display: flex; gap: 0.5rem; margin-left: auto;">
            <input type="number" id="quickExpId" placeholder="e.g. 10000" style="width: 140px; margin-bottom: 0;">
            <button class="btn-primary" onclick="quickFetchExp()">⚡ Read Report</button>
          </div>
        </div>

        <!-- Curated Landmark Reports Chips -->
        <div style="margin-bottom: 1rem;">
          <div style="font-family: var(--font-display); font-size: 0.74rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.45rem;">
            FEATURED LANDMARK REPORTS:
          </div>
          <div style="display: flex; flex-wrap: wrap; gap: 0.45rem;">
            <span class="chip" onclick="openReportModal(10000)">Exp #10000 (Mescaline)</span>
            <span class="chip" onclick="openReportModal(15243)">Exp #15243 (DMT Breakthrough)</span>
            <span class="chip" onclick="openReportModal(24810)">Exp #24810 (2C-B & Cannabis)</span>
            <span class="chip" onclick="openReportModal(31290)">Exp #31290 (Ketamine Hospitalization)</span>
          </div>
        </div>

        <!-- Outcome Filter Pills -->
        <div style="margin-bottom: 1rem;">
          <div style="font-family: var(--font-display); font-size: 0.74rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.45rem;">
            FILTER LOCAL VAULT BY OUTCOME:
          </div>
          <div style="display: flex; flex-wrap: wrap; gap: 0.4rem;" id="vaultFilterPills">
            <span class="chip active" onclick="filterVaultTag('', this)">All Indexed Reports</span>
            <span class="chip" onclick="filterVaultTag('Overdose', this)">🚨 Overdose Reports</span>
            <span class="chip" onclick="filterVaultTag('Hospital', this)">🏥 Medical Emergency / ER</span>
            <span class="chip" onclick="filterVaultTag('Bad Trips', this)">🌀 Difficult Experiences</span>
            <span class="chip" onclick="filterVaultTag('First Times', this)">✨ First Times</span>
            <span class="chip" onclick="filterVaultTag('Combinations', this)">🧬 Multi-Drug Combos</span>
          </div>
        </div>

        <div style="display: flex; gap: 0.6rem; margin-bottom: 1.3rem;">
          <input type="text" id="expSearchQ" placeholder="Keyword query in vault (e.g. 'respiratory', 'seizure', 'panic', 'naloxone')..." onkeydown="if(event.key==='Enter') loadExperiences()">
          <button class="btn-primary" onclick="loadExperiences()">Search Vault</button>
        </div>

        <div id="expResultsList"></div>
      </div>
    </div>

    <!-- ==================== TAB 5: REAGENTS & TEST STRIPS ==================== -->
    <div id="tab-reagents" class="tab-content">
      <div class="grid-2">
        <!-- Interactive Reagent Matrix Tool -->
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">🧪 Chemical Reagent Testing Matrix</div>
              <div class="card-subtitle">Select a target substance to view expected color changes across primary test kits</div>
            </div>
          </div>

          <label class="field-label">SELECT SUBSTANCE TO PREVIEW REAGENT REACTIONS:</label>
          <select id="reagentSubSelect" onchange="renderReagentReactionDetails()" style="margin-bottom: 1.1rem;">
            <option value="MDMA">MDMA (Molly / Ecstasy)</option>
            <option value="LSD">LSD (Acid)</option>
            <option value="2CB">2C-B</option>
            <option value="Ketamine">Ketamine</option>
            <option value="Cocaine">Cocaine</option>
            <option value="Methamphetamine">Methamphetamine</option>
            <option value="Amphetamine">Amphetamine / Adderall</option>
            <option value="Heroin">Heroin / Morphine</option>
            <option value="DXM">DXM</option>
          </select>

          <div id="reagentReactionsContainer" class="reagent-swatch-box"></div>
          <div id="testingProtocolsTable" style="margin-top: 1.5rem;"></div>
        </div>

        <!-- Fentanyl Test Strip Life-Saving Protocol -->
        <div class="card">
          <div class="card-header">
            <div>
              <div class="card-title">⚠️ Fentanyl Test Strips (Life-Saving Guide)</div>
              <div class="card-subtitle">Zero-tolerance harm reduction for synthetic opioid adulteration</div>
            </div>
            <span class="badge badge-deadly">CRITICAL SAFETY</span>
          </div>

          <!-- The Chocolate Chip Cookie Alert -->
          <div style="background: rgba(239, 68, 68, 0.14); border-left: 4px solid var(--deadly); padding: 1rem; border-radius: var(--radius-sm); margin-bottom: 1.2rem;">
            <div style="font-family: var(--font-display); font-size: 0.92rem; font-weight: 700; color: #f87171; margin-bottom: 0.2rem;">
              The "Chocolate Chip Cookie" Effect
            </div>
            <div style="font-size: 0.83rem; color: #fca5a5; line-height: 1.5;">
              A lethal dose of fentanyl is microscopic (2 mg). It does not mix evenly in powders or pressed counterfeit pills. Testing only a small scraping can yield a <strong>FATAL FALSE NEGATIVE</strong>. Dissolve the <em>entire sample</em> in water before consumption!
            </div>
          </div>

          <!-- Step-by-Step Cards -->
          <div style="display: flex; flex-direction: column; gap: 0.75rem;">
            <div style="background: #090e1a; border: 1px solid var(--card-border); padding: 0.9rem; border-radius: 6px;">
              <strong style="color: var(--accent);">1. Measure Water & Dissolve:</strong><br>
              <span style="font-size: 0.84rem; color: #cbd5e1;">Use 1 teaspoon (5 ml) of clean water per 10 mg of powder. For MDMA or methamphetamine, use 10 ml per 10 mg to prevent false positives.</span>
            </div>

            <div style="background: #090e1a; border: 1px solid var(--card-border); padding: 0.9rem; border-radius: 6px;">
              <strong style="color: var(--accent);">2. Dip the Strip:</strong><br>
              <span style="font-size: 0.84rem; color: #cbd5e1;">Insert test strip into the solution for 15 seconds up to the wavy blue line. Never submerge past the MAX line.</span>
            </div>

            <div style="background: #090e1a; border: 1px solid var(--card-border); padding: 0.9rem; border-radius: 6px;">
              <strong style="color: var(--accent);">3. Wait 2 Minutes:</strong><br>
              <span style="font-size: 0.84rem; color: #cbd5e1;">Lay the test strip flat on a clean non-absorbent surface. Wait 2 minutes for lines to stabilize.</span>
            </div>

            <div style="background: #090e1a; border: 1px solid var(--card-border); padding: 0.9rem; border-radius: 6px;">
              <strong style="color: var(--accent);">4. Interpret Test Lines:</strong>
              <div style="margin-top: 0.5rem; display: flex; flex-direction: column; gap: 0.4rem;">
                <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(16, 185, 129, 0.12); border: 1px solid var(--safe); padding: 0.5rem 0.8rem; border-radius: 4px;">
                  <span style="color: #34d399; font-weight: 700; font-size: 0.82rem;">TWO RED LINES (||)</span>
                  <span class="badge badge-safe">NEGATIVE — NO FENTANYL DETECTED</span>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(239, 68, 68, 0.16); border: 1px solid var(--deadly); padding: 0.5rem 0.8rem; border-radius: 4px;">
                  <span style="color: #f87171; font-weight: 700; font-size: 0.82rem;">ONE RED LINE (|)</span>
                  <span class="badge badge-deadly">POSITIVE — LETHAL DANGER! DO NOT CONSUME</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== TAB 6: OFFLINE HARVESTER CONSOLE ==================== -->
    <div id="tab-harvester" class="tab-content">
      <div class="card">
        <div class="card-header">
          <div>
            <div class="card-title">💾 Offline Ingestion Engine & Storage Telemetry</div>
            <div class="card-subtitle">Manage local SQLite FTS5 database, category ID harvester, and multithreaded report batch ingestion</div>
          </div>
          <span class="badge badge-safe">STANDALONE OFFLINE VAULT</span>
        </div>

        <div class="grid-2" style="margin-bottom: 1.3rem;">
          <div style="background: #090e1a; padding: 1.3rem; border-radius: var(--radius-sm); border: 1px solid var(--card-border);">
            <div style="font-family: var(--font-display); font-size: 0.98rem; font-weight: 700; color: #fff; margin-bottom: 0.4rem;">
              Quick Harvest by Substance Slug
            </div>
            <p style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.9rem;">
              Harvest all published report IDs for any substance across its sub-categories into SQLite.
            </p>
            <div style="display: flex; gap: 0.5rem;">
              <input type="text" id="harvestSubInput" placeholder="e.g. ketamine, dmt, 2cb, salvia" style="margin-bottom: 0;">
              <button class="btn-primary" onclick="triggerSubHarvest()" style="white-space: nowrap;">Harvest IDs</button>
            </div>
          </div>

          <div style="background: #090e1a; padding: 1.3rem; border-radius: var(--radius-sm); border: 1px solid var(--card-border);">
            <div style="font-family: var(--font-display); font-size: 0.98rem; font-weight: 700; color: #fff; margin-bottom: 0.4rem;">
              Worker Pool Ingestion
            </div>
            <p style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.9rem;">
              Download and decompress queued experience reports in parallel (3 worker threads).
            </p>
            <button class="btn-primary" onclick="triggerBatchScrape()">⚡ Scrape Next 15 Queued Reports</button>
          </div>
        </div>

        <div style="font-family: var(--font-mono); font-size: 0.8rem; background: #050811; border: 1px solid var(--card-border); padding: 1.1rem; border-radius: var(--radius-sm); min-height: 110px; color: #94a3b8; line-height: 1.6;" id="scraperLog">
          [System Ready] Offline storage active. Ingestion queue operational.
        </div>
      </div>
    </div>
  </main>

  <!-- ==================== EMERGENCY PROTOCOL MODAL ==================== -->
  <div id="emergencyModal" class="modal">
    <div class="modal-content" style="border: 2px solid var(--deadly); box-shadow: 0 0 60px rgba(239, 68, 68, 0.45);">
      <button class="modal-close" onclick="closeEmergencyModal()">&times;</button>
      
      <div style="display: flex; align-items: center; gap: 0.9rem; margin-bottom: 1.1rem;">
        <span style="font-size: 2.2rem;">🚨</span>
        <div>
          <h2 style="font-family: var(--font-display); color: var(--deadly); font-size: 1.6rem; font-weight: 800; letter-spacing: -0.02em;">
            EMERGENCY OVERDOSE PROTOCOL
          </h2>
          <div style="font-size: 0.86rem; color: #fca5a5;">
            Immediate Life-Saving Resuscitation Protocol & 24/7 Crisis Support
          </div>
        </div>
      </div>

      <!-- Good Samaritan Legal Shield Banner -->
      <div style="background: rgba(239, 68, 68, 0.16); border-left: 4px solid var(--deadly); padding: 0.95rem 1.2rem; border-radius: 4px; margin-bottom: 1.4rem;">
        <div style="font-family: var(--font-display); font-weight: 700; color: #fff; font-size: 0.88rem;">
          GOOD SAMARITAN LAW IMMUNITY:
        </div>
        <div style="font-size: 0.84rem; color: #cbd5e1; line-height: 1.5;">
          Most US states and international jurisdictions have Good Samaritan laws that legally shield you from drug possession charges when calling emergency services for an overdose. DO NOT HESITATE TO CALL 911.
        </div>
      </div>

      <!-- Built-in 2-Minute Naloxone Re-Dose Countdown Timer -->
      <div style="background: #090e1a; border: 1px solid var(--card-border); border-radius: var(--radius-sm); padding: 1rem 1.3rem; margin-bottom: 1.3rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.9rem;">
        <div>
          <div style="font-family: var(--font-display); font-weight: 700; font-size: 0.92rem; color: #fff;">
            ⏱️ Naloxone (Narcan) 2-Minute Re-Dose Timer
          </div>
          <div style="font-size: 0.78rem; color: var(--text-muted);">
            If victim remains unresponsive after 2 to 3 minutes, administer second dose in opposite nostril.
          </div>
        </div>
        <div style="display: flex; align-items: center; gap: 0.8rem;">
          <div id="narcanTimerDisplay" style="font-family: var(--font-mono); font-size: 1.5rem; font-weight: 800; color: var(--accent);">
            02:00
          </div>
          <button class="btn-primary" id="btnNarcanTimer" onclick="toggleNarcanTimer()" style="padding: 0.45rem 0.9rem; font-size: 0.8rem;">
            Start Timer
          </button>
          <button class="btn-secondary" onclick="resetNarcanTimer()" style="padding: 0.45rem 0.7rem; font-size: 0.8rem;">
            Reset
          </button>
        </div>
      </div>

      <!-- 4 Life Saving Steps -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 0.95rem; margin-bottom: 1.4rem;">
        <div style="background: #090e1a; padding: 1rem; border-radius: 6px; border: 1px solid var(--card-border);">
          <div style="color: var(--accent); font-weight: 700; margin-bottom: 0.35rem; font-family: var(--font-display);">
            STEP 1: CHECK & CALL 911
          </div>
          <div style="font-size: 0.83rem; color: #cbd5e1; line-height: 1.5;">
            Rub knuckles firmly on center of chest (sternum rub). If unresponsive or breathing slowly (&lt;10/min), call 911 immediately. State: <em>"A person is unresponsive and not breathing."</em>
          </div>
        </div>

        <div style="background: #090e1a; padding: 1rem; border-radius: 6px; border: 1px solid var(--card-border);">
          <div style="color: var(--accent); font-weight: 700; margin-bottom: 0.35rem; font-family: var(--font-display);">
            STEP 2: ADMINISTER NARCAN
          </div>
          <div style="font-size: 0.83rem; color: #cbd5e1; line-height: 1.5;">
            Peel package, insert tip into one nostril, press plunger firmly. If person does not awaken within 2 to 3 minutes, give a second dose in the other nostril.
          </div>
        </div>

        <div style="background: #090e1a; padding: 1rem; border-radius: 6px; border: 1px solid var(--card-border);">
          <div style="color: var(--accent); font-weight: 700; margin-bottom: 0.35rem; font-family: var(--font-display);">
            STEP 3: RESCUE BREATHING
          </div>
          <div style="font-size: 0.83rem; color: #cbd5e1; line-height: 1.5;">
            Tilt head back, pinch nose, deliver 1 breath every 5 seconds. If no heartbeat, begin chest compressions (100-120 bpm to the rhythm of 'Stayin Alive').
          </div>
        </div>

        <div style="background: #090e1a; padding: 1rem; border-radius: 6px; border: 1px solid var(--card-border);">
          <div style="color: var(--accent); font-weight: 700; margin-bottom: 0.35rem; font-family: var(--font-display);">
            STEP 4: RECOVERY POSITION
          </div>
          <div style="font-size: 0.83rem; color: #cbd5e1; line-height: 1.5;">
            Roll victim onto their side, bend top knee forward to balance them, and rest head on arm. This prevents fatal asphyxiation on vomit if unconscious.
          </div>
        </div>
      </div>

      <!-- Helplines & Spotters -->
      <h3 style="font-family: var(--font-display); color: #fff; font-size: 1.05rem; margin-bottom: 0.8rem; border-bottom: 1px solid var(--card-border); padding-bottom: 0.4rem;">
        Free 24/7 Crisis Helplines & Virtual Spotters
      </h3>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 0.75rem;">
        <div style="background: #090e1a; padding: 0.85rem 1rem; border-radius: 6px; border: 1px solid var(--card-border);">
          <div style="font-weight: 700; color: #fff; font-size: 0.88rem;">📞 Never Use Alone (US)</div>
          <div style="font-size: 0.78rem; color: var(--text-muted);">Toll-free virtual spotter; stays on line and calls EMS if you stop responding.</div>
          <a href="tel:18776961996" style="color: var(--accent); font-family: var(--font-mono); font-weight: 700; font-size: 1.05rem; text-decoration: none; display: inline-block; margin-top: 0.25rem;">1-877-696-1996</a>
        </div>

        <div style="background: #090e1a; padding: 0.85rem 1rem; border-radius: 6px; border: 1px solid var(--card-border);">
          <div style="font-weight: 700; color: #fff; font-size: 0.88rem;">📞 SAMHSA Helpline (US)</div>
          <div style="font-size: 0.78rem; color: var(--text-muted);">Free, confidential 24/7 treatment referral and support.</div>
          <a href="tel:18006624357" style="color: var(--accent); font-family: var(--font-mono); font-weight: 700; font-size: 1.05rem; text-decoration: none; display: inline-block; margin-top: 0.25rem;">1-800-662-4357</a>
        </div>

        <div style="background: #090e1a; padding: 0.85rem 1rem; border-radius: 6px; border: 1px solid var(--card-border);">
          <div style="font-weight: 700; color: #fff; font-size: 0.88rem;">💬 Crisis Text Line</div>
          <div style="font-size: 0.78rem; color: var(--text-muted);">24/7 free emotional crisis support via SMS.</div>
          <div style="color: var(--safe); font-family: var(--font-mono); font-weight: 700; font-size: 1.05rem; margin-top: 0.25rem;">Text HOME to 741741</div>
        </div>

        <div style="background: #090e1a; padding: 0.85rem 1rem; border-radius: 6px; border: 1px solid var(--card-border);">
          <div style="font-weight: 700; color: #fff; font-size: 0.88rem;">🇬🇧 FRANK Helpline (UK)</div>
          <div style="font-size: 0.78rem; color: var(--text-muted);">Confidential drug info and harm reduction advice.</div>
          <a href="tel:03001236600" style="color: var(--accent); font-family: var(--font-mono); font-weight: 700; font-size: 1.05rem; text-decoration: none; display: inline-block; margin-top: 0.25rem;">0300 123 6600</a>
        </div>
      </div>
    </div>
  </div>

  <!-- ==================== EXPERIENCE REPORT READER MODAL ==================== -->
  <div id="reportModal" class="modal">
    <div class="modal-content">
      <button class="modal-close" onclick="closeModal()">&times;</button>
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.4rem;">
        <h2 id="modalTitle" style="font-family: var(--font-display); color: var(--accent); font-size: 1.4rem; letter-spacing: -0.01em;"></h2>
      </div>
      <div id="modalMeta" style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 0.75rem;"></div>
      <div id="modalFlags" style="margin-bottom: 0.75rem;"></div>
      <div id="modalDoses" style="margin-bottom: 1rem;"></div>
      <div style="border-top: 1px solid var(--card-border); padding-top: 1rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.65rem;">
          <h4 style="font-family: var(--font-display); color: #fff; font-size: 0.95rem;">Experience Narrative:</h4>
          <button class="btn-secondary" onclick="copyReportNarrative()" style="padding: 0.25rem 0.65rem; font-size: 0.74rem;">📋 Copy Text</button>
        </div>
        <div id="modalBody" style="white-space: pre-wrap; color: #cbd5e1; font-size: 0.94rem; line-height: 1.7; max-height: 55vh; overflow-y: auto; padding-right: 0.5rem; background: #080c16; padding: 1.1rem; border-radius: 6px; border: 1px solid var(--card-border);"></div>
      </div>
    </div>
  </div>

  <!-- ==================== CLINICAL DOSSIER MODAL ==================== -->
  <div id="dossierModal" class="modal">
    <div class="modal-content" style="max-width: 850px;">
      <button class="modal-close" onclick="closeDossierModal()">&times;</button>
      <div id="dossierModalContent"></div>
    </div>
  </div>

  <!-- ==================== GLOBAL SPOTLIGHT SEARCH MODAL (CMD+K) ==================== -->
  <div id="spotlightModal" class="modal">
    <div class="modal-content">
      <div style="display: flex; align-items: center; gap: 0.6rem; border-bottom: 1px solid var(--border-accent); padding-bottom: 0.75rem; margin-bottom: 0.9rem;">
        <span style="font-size: 1.2rem; color: var(--accent);">🔍</span>
        <input type="text" id="spotlightInput" placeholder="Quick search 561 substances, tools, or emergency protocols..." style="background: transparent; border: none; font-size: 1.05rem; padding: 0.2rem 0; width: 100%; outline: none;" oninput="runSpotlightSearch(this.value)">
        <span class="kbd-shortcut" onclick="closeSpotlightModal()" style="cursor: pointer;">ESC</span>
      </div>
      <div id="spotlightResults" style="max-height: 380px; overflow-y: auto; display: flex; flex-direction: column; gap: 0.4rem;">
        <!-- Filtered results -->
      </div>
    </div>
  </div>

  <!-- ==================== CLIENT JAVASCRIPT ==================== -->
  <script>
    let activeNav = 'dossiers';
    let substancesData = [];
    let catalogData = [];
    let allSubstanceNames = [];
    let activeComboList = [];
    let catalogDebounceTimer = null;
    let narcanTimerInterval = null;
    let narcanTimerSeconds = 120;

    // Alphabet bar letters
    const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
    const alphaContainer = document.getElementById('alphabetJumpBar');
    alphabet.forEach(letter => {
      const btn = document.createElement('button');
      btn.className = 'alphabet-btn';
      btn.innerText = letter;
      btn.onclick = () => jumpCatalogAlpha(letter, btn);
      alphaContainer.appendChild(btn);
    });

    // Navigation Switcher
    function switchNav(tabName) {
      activeNav = tabName;
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('nav.tab-nav button').forEach(el => el.classList.remove('active'));
      
      const target = document.getElementById('tab-' + tabName);
      if (target) target.classList.add('active');
      
      const navButtons = document.querySelectorAll('nav.tab-nav button');
      navButtons.forEach(b => {
        if (b.innerText.toLowerCase().includes(tabName.substring(0, 4))) b.classList.add('active');
      });

      if (tabName === 'catalog' && catalogData.length === 0) loadCatalog();
      if (tabName === 'vault') loadExperiences();
    }

    // Spotlight Quick Search (Cmd+K)
    function openSpotlightModal() {
      document.getElementById('spotlightModal').classList.add('active');
      const input = document.getElementById('spotlightInput');
      input.value = '';
      input.focus();
      runSpotlightSearch('');
    }
    function closeSpotlightModal() {
      document.getElementById('spotlightModal').classList.remove('active');
    }

    // Emergency Modal
    function openEmergencyModal() {
      document.getElementById('emergencyModal').classList.add('active');
    }
    function closeEmergencyModal() {
      document.getElementById('emergencyModal').classList.remove('active');
    }

    // Modal Close
    function closeModal() {
      document.getElementById('reportModal').classList.remove('active');
    }
    function closeDossierModal() {
      document.getElementById('dossierModal').classList.remove('active');
    }

    // Keyboard Shortcuts
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeEmergencyModal();
        closeModal();
        closeDossierModal();
        closeSpotlightModal();
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'e') {
        e.preventDefault();
        openEmergencyModal();
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        openSpotlightModal();
      }
    });

    // Narcan Timer
    function toggleNarcanTimer() {
      const btn = document.getElementById('btnNarcanTimer');
      if (narcanTimerInterval) {
        clearInterval(narcanTimerInterval);
        narcanTimerInterval = null;
        btn.innerText = 'Resume Timer';
        btn.className = 'btn-primary';
      } else {
        btn.innerText = 'Pause Timer';
        btn.className = 'btn-secondary';
        narcanTimerInterval = setInterval(() => {
          narcanTimerSeconds--;
          if (narcanTimerSeconds <= 0) {
            clearInterval(narcanTimerInterval);
            narcanTimerInterval = null;
            document.getElementById('narcanTimerDisplay').innerText = "00:00 (ADMINISTER 2ND DOSE!)";
            document.getElementById('narcanTimerDisplay').style.color = "var(--deadly)";
            btn.innerText = 'Restart Timer';
            return;
          }
          const m = Math.floor(narcanTimerSeconds / 60);
          const s = narcanTimerSeconds % 60;
          document.getElementById('narcanTimerDisplay').innerText = 
            `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
        }, 1000);
      }
    }
    function resetNarcanTimer() {
      if (narcanTimerInterval) clearInterval(narcanTimerInterval);
      narcanTimerInterval = null;
      narcanTimerSeconds = 120;
      document.getElementById('narcanTimerDisplay').innerText = "02:00";
      document.getElementById('narcanTimerDisplay').style.color = "var(--accent)";
      document.getElementById('btnNarcanTimer').innerText = 'Start Timer';
      document.getElementById('btnNarcanTimer').className = 'btn-primary';
    }

    // Weight Slider Synchronization
    function syncWeightSlider(val) {
      document.getElementById('userWeightInput').value = val;
      runDoseCalculation();
    }
    function syncWeightInput(val) {
      document.getElementById('userWeightSlider').value = val;
      runDoseCalculation();
    }

    // --- TAB 1: DOSSIERS & DOSAGE SAFETY LADDER ---
    async function loadSubstances() {
      try {
        const res = await fetch('/api/substances');
        substancesData = await res.json();
        renderSubstances(substancesData);
        runDoseCalculation();
      } catch (e) {
        console.error("Failed to load substances:", e);
      }
    }

    function renderSubstances(list) {
      const container = document.getElementById('substancesList');
      if (!container) return;
      container.innerHTML = list.map(sub => `
        <div class="card" style="margin-bottom: 0; display: flex; flex-direction: column; justify-content: space-between; border-top: 3px solid ${getCategoryColor(sub.category)};">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.4rem;">
              <h3 style="color: #fff; font-family: var(--font-display); font-size: 1.05rem;">${sub.name}</h3>
              <span class="badge" style="background: rgba(255,255,255,0.06); color: ${getCategoryColor(sub.category)}; border: 1px solid rgba(255,255,255,0.1);">${sub.category}</span>
            </div>
            <p style="font-size: 0.77rem; color: var(--text-muted); margin-bottom: 0.45rem;">
              Aliases: ${(sub.common_names || []).join(', ') || 'N/A'}
            </p>
            <p style="font-size: 0.82rem; color: #cbd5e1; margin-bottom: 0.8rem; line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;">
              ${sub.harm_summary}
            </p>
          </div>
          <div>
            ${sub.dosages && sub.dosages.length > 0 ? `
              <div style="background: #090e1a; padding: 0.65rem 0.8rem; border-radius: 6px; font-size: 0.75rem; margin-bottom: 0.65rem; border: 1px solid var(--card-border);">
                <strong style="color: var(--accent);">${sub.dosages[0].route} Standard Range:</strong><br>
                Thresh: <span style="font-family: var(--font-mono);">${sub.dosages[0].threshold || 'N/A'}</span> | 
                Common: <span style="font-family: var(--font-mono); color: #fff; font-weight: 700;">${sub.dosages[0].common || 'N/A'}</span> | 
                Heavy: <span style="font-family: var(--font-mono); color: var(--deadly); font-weight: 700;">${sub.dosages[0].heavy || 'N/A'}</span>
              </div>
            ` : ''}
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem;">
              <button class="btn-primary" style="padding: 0.45rem 0.6rem; font-size: 0.78rem;" onclick="setDoseSubstance('${sub.name}', ${sub.dosages && sub.dosages[0] ? (parseFloat(sub.dosages[0].common) || 100) : 100}, 'mg', '${sub.dosages && sub.dosages[0] ? sub.dosages[0].route : 'Oral'}')">
                Assess Dose
              </button>
              <button class="btn-secondary" style="padding: 0.45rem 0.6rem; font-size: 0.78rem;" onclick="openDossierModal('${sub.name}')">
                Monograph
              </button>
            </div>
          </div>
        </div>
      `).join('');
    }

    function getCategoryColor(cat = '') {
      const c = cat.toLowerCase();
      if (c.includes('psychedelic')) return '#38bdf8';
      if (c.includes('empathogen')) return '#f43f5e';
      if (c.includes('dissociative')) return '#a855f7';
      if (c.includes('stimulant')) return '#f59e0b';
      if (c.includes('depressant') || c.includes('benzo')) return '#3b82f6';
      if (c.includes('opioid')) return '#ef4444';
      return '#10b981';
    }

    function filterSubstances() {
      const q = document.getElementById('subSearch').value.toLowerCase();
      const filtered = substancesData.filter(s => 
        s.name.toLowerCase().includes(q) || 
        s.category.toLowerCase().includes(q) ||
        (s.common_names || []).some(c => c.toLowerCase().includes(q))
      );
      renderSubstances(filtered);
    }

    function setDoseSubstance(name, amt, unit, route, el = null) {
      document.getElementById('doseSubInput').value = name;
      document.getElementById('doseAmtInput').value = amt;
      document.getElementById('doseUnitSelect').value = unit;
      document.getElementById('doseRouteSelect').value = route;
      if (el) {
        document.querySelectorAll('#tab-dossiers .chip').forEach(c => c.classList.remove('active'));
        el.classList.add('active');
      }
      runDoseCalculation();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    async function runDoseCalculation() {
      const sub = document.getElementById('doseSubInput').value.trim();
      const amt = document.getElementById('doseAmtInput').value.trim();
      const unit = document.getElementById('doseUnitSelect').value;
      const route = document.getElementById('doseRouteSelect').value;
      const weight = parseFloat(document.getElementById('userWeightInput').value) || 70;
      const weightUnit = document.getElementById('userWeightUnit').value;

      const weightKg = weightUnit === 'lbs' ? weight * 0.453592 : weight;
      const weightMdmaGuide = Math.round(weightKg * 1.5);
      document.getElementById('weightDoseCalcOutput').innerText = 
        `Guideline: ~${weightMdmaGuide} mg (1.5mg/kg @ ${Math.round(weightKg)}kg)`;

      if (!sub || !amt) return;

      try {
        const res = await fetch(`/api/check-dose?substance=${encodeURIComponent(sub)}&amount=${encodeURIComponent(amt)}&unit=${encodeURIComponent(unit)}&route=${encodeURIComponent(route)}`);
        const data = await res.json();
        renderDoseEvaluation(data, parseFloat(amt), unit);
      } catch (err) {
        console.error("Dose calculation error:", err);
      }
    }

    function renderDoseEvaluation(data, amt, unit) {
      const badge = document.getElementById('doseStatusBadge');
      const headerBadge = document.getElementById('doseHeaderBadge');
      const pointer = document.getElementById('doseLadderPointer');
      const bubble = document.getElementById('doseLadderValBubble');
      const grid = document.getElementById('doseDetailsGrid');

      bubble.innerText = `${amt} ${unit}`;

      if (!data.found) {
        badge.className = 'badge badge-caution';
        badge.innerText = 'NOT INDEXED IN CLINICAL DOSSIERS';
        headerBadge.className = 'badge badge-caution';
        headerBadge.innerText = 'NO CLINICAL BENCHMARK';
        pointer.style.left = '50%';
        grid.innerHTML = `<div style="grid-column: 1 / -1; color: var(--text-muted); background: #090e1a; padding: 1rem; border-radius: 6px;">${data.message || 'No specific clinical dosage brackets indexed for this compound/route.'}</div>`;
        return;
      }

      const status = data.status || 'COMMON';
      let leftPct = 50;
      let badgeClass = 'badge-safe';

      if (status.includes('HEAVY') || status.includes('OVERDOSE') || status.includes('DANGEROUS')) {
        badgeClass = 'badge-deadly';
        leftPct = 92;
      } else if (status.includes('STRONG')) {
        badgeClass = 'badge-dangerous';
        leftPct = 75;
      } else if (status.includes('COMMON')) {
        badgeClass = 'badge-safe';
        leftPct = 48;
      } else if (status.includes('LIGHT')) {
        badgeClass = 'badge-caution';
        leftPct = 25;
      } else {
        badgeClass = 'badge-cat';
        leftPct = 8;
      }

      badge.className = `badge ${badgeClass}`;
      badge.innerText = status;
      headerBadge.className = `badge ${badgeClass}`;
      headerBadge.innerText = status;
      pointer.style.left = `${leftPct}%`;

      grid.innerHTML = `
        <div class="card" style="margin-bottom: 0; background: #090e1a; border-left: 3px solid var(--accent); padding: 1rem;">
          <div style="font-family: var(--font-display); color: var(--accent); font-weight: 700; font-size: 0.78rem; text-transform: uppercase;">THRESHOLD / LIGHT</div>
          <div style="font-size: 0.85rem; margin-top: 0.3rem;">Threshold: <strong>${data.threshold || 'N/A'}</strong></div>
          <div style="font-size: 0.85rem;">Light: <strong>${data.light || 'N/A'}</strong></div>
        </div>
        <div class="card" style="margin-bottom: 0; background: #090e1a; border-left: 3px solid var(--safe); padding: 1rem;">
          <div style="font-family: var(--font-display); color: var(--safe); font-weight: 700; font-size: 0.78rem; text-transform: uppercase;">COMMON RANGE</div>
          <div style="font-size: 0.85rem; margin-top: 0.3rem;">Common: <strong>${data.common || 'N/A'}</strong></div>
          <div style="font-size: 0.85rem;">Strong: <strong>${data.strong || 'N/A'}</strong></div>
        </div>
        <div class="card" style="margin-bottom: 0; background: #090e1a; border-left: 3px solid var(--deadly); padding: 1rem;">
          <div style="font-family: var(--font-display); color: var(--deadly); font-weight: 700; font-size: 0.78rem; text-transform: uppercase;">HEAVY BOUNDARY</div>
          <div style="font-size: 0.85rem; margin-top: 0.3rem;">Heavy / Toxic: <strong>${data.heavy || 'N/A'}</strong></div>
          <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.2rem;">${data.notes || ''}</div>
        </div>
        ${(data.durations && data.durations.length > 0) ? `
          <div class="card" style="margin-bottom: 0; background: #090e1a; border-left: 3px solid var(--indigo); padding: 1rem;">
            <div style="font-family: var(--font-display); color: var(--indigo); font-weight: 700; font-size: 0.78rem; text-transform: uppercase;">TIMELINE (${data.durations[0].route})</div>
            <div style="font-size: 0.85rem; margin-top: 0.3rem;">Onset: <strong>${data.durations[0].onset || 'N/A'}</strong></div>
            <div style="font-size: 0.85rem;">Peak: <strong>${data.durations[0].peak || 'N/A'}</strong></div>
            <div style="font-size: 0.85rem;">Duration: <strong>${data.durations[0].total_duration || 'N/A'}</strong></div>
          </div>
        ` : ''}
      `;
    }

    // Open Full Clinical Monograph Modal
    async function openDossierModal(name) {
      const res = await fetch(`/api/substance?name=${encodeURIComponent(name)}`);
      const sub = await res.json();
      if (sub.error) return;

      const modalContent = document.getElementById('dossierModalContent');
      modalContent.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.6rem;">
          <div>
            <h2 style="font-family: var(--font-display); color: #fff; font-size: 1.5rem;">${sub.name}</h2>
            <div style="font-size: 0.82rem; color: var(--text-muted);">
              Category: <strong style="color: var(--accent);">${sub.category}</strong> | Legal Status: <strong>${sub.legal_status || 'N/A'}</strong>
            </div>
          </div>
          <span class="badge" style="background: rgba(255,255,255,0.06); color: ${getCategoryColor(sub.category)}; border: 1px solid var(--card-border);">${sub.category}</span>
        </div>

        <div style="background: #090e1a; padding: 1rem; border-radius: 8px; margin: 1rem 0; border: 1px solid var(--card-border);">
          <strong style="color: var(--accent); font-family: var(--font-display); font-size: 0.82rem; text-transform: uppercase;">Pharmacological Overview:</strong>
          <p style="font-size: 0.88rem; color: #cbd5e1; margin-top: 0.3rem; line-height: 1.6;">${sub.description}</p>
        </div>

        <div style="background: rgba(239, 68, 68, 0.08); border-left: 4px solid var(--deadly); padding: 1rem; border-radius: 4px; margin-bottom: 1rem;">
          <strong style="color: #f87171; font-family: var(--font-display); font-size: 0.82rem; text-transform: uppercase;">Harm Summary & Clinical Risks:</strong>
          <p style="font-size: 0.86rem; color: #fca5a5; margin-top: 0.3rem; line-height: 1.6;">${sub.harm_summary}</p>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.9rem; margin-bottom: 1.1rem;">
          <div style="background: #090e1a; padding: 0.9rem; border-radius: 6px; border: 1px solid var(--card-border);">
            <strong style="color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase;">Toxicity & Neurotoxicity Notes:</strong>
            <p style="font-size: 0.83rem; color: #cbd5e1; margin-top: 0.3rem; line-height: 1.5;">${sub.toxicity_notes || 'No acute organ damage identified at standard clinical dosage.'}</p>
          </div>
          <div style="background: #090e1a; padding: 0.9rem; border-radius: 6px; border: 1px solid var(--card-border);">
            <strong style="color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase;">Addiction / Dependence Potential:</strong>
            <div style="margin-top: 0.4rem;"><span class="badge ${sub.addiction_potential.toLowerCase().includes('high') ? 'badge-deadly' : 'badge-safe'}">${sub.addiction_potential}</span></div>
          </div>
        </div>

        ${sub.dosages && sub.dosages.length > 0 ? `
          <h4 style="font-family: var(--font-display); color: #fff; margin-bottom: 0.5rem; font-size: 0.92rem;">Verified Dosage Brackets:</h4>
          <table class="data-table" style="margin-bottom: 1rem;">
            <thead>
              <tr><th>Route</th><th>Threshold</th><th>Light</th><th>Common</th><th>Strong</th><th>Heavy</th></tr>
            </thead>
            <tbody>
              ${sub.dosages.map(d => `
                <tr>
                  <td><strong>${d.route}</strong></td>
                  <td>${d.threshold || 'N/A'}</td>
                  <td>${d.light || 'N/A'}</td>
                  <td style="color: #fff; font-weight: 700;">${d.common || 'N/A'}</td>
                  <td>${d.strong || 'N/A'}</td>
                  <td style="color: var(--deadly); font-weight: 700;">${d.heavy || 'N/A'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        ` : ''}

        ${sub.durations && sub.durations.length > 0 ? `
          <h4 style="font-family: var(--font-display); color: #fff; margin-bottom: 0.5rem; font-size: 0.92rem;">Duration & Kinetics Profile:</h4>
          <div class="timeline-grid" style="margin-bottom: 1.2rem;">
            <div class="timeline-tile"><span class="timeline-label">Onset</span><span class="timeline-val">${sub.durations[0].onset || 'N/A'}</span></div>
            <div class="timeline-tile"><span class="timeline-label">Peak</span><span class="timeline-val">${sub.durations[0].peak || 'N/A'}</span></div>
            <div class="timeline-tile"><span class="timeline-label">Comedown</span><span class="timeline-val">${sub.durations[0].coming_down || 'N/A'}</span></div>
            <div class="timeline-tile"><span class="timeline-label">Total Duration</span><span class="timeline-val">${sub.durations[0].total_duration || 'N/A'}</span></div>
            <div class="timeline-tile"><span class="timeline-label">After-Effects</span><span class="timeline-val">${sub.durations[0].after_effects || 'N/A'}</span></div>
          </div>
        ` : ''}

        <div style="display: flex; gap: 0.6rem; justify-content: flex-end; border-top: 1px solid var(--card-border); padding-top: 1rem;">
          <button class="btn-primary" onclick="setDoseSubstance('${sub.name}', ${sub.dosages && sub.dosages[0] ? (parseFloat(sub.dosages[0].common) || 100) : 100}, 'mg', '${sub.dosages && sub.dosages[0] ? sub.dosages[0].route : 'Oral'}'); closeDossierModal();">
            Load into Dosage Ladder
          </button>
          <button class="btn-secondary" onclick="addComboSubstance('${sub.name}'); switchNav('radar'); closeDossierModal();">
            + Add to Combo Radar
          </button>
        </div>
      `;
      document.getElementById('dossierModal').classList.add('active');
    }

    // --- TAB 2: COMBO RISK RADAR ---
    function addComboSubstance(name) {
      if (!activeComboList.includes(name)) {
        activeComboList.push(name);
        updateComboUI();
      }
    }

    function removeComboSubstance(name) {
      activeComboList = activeComboList.filter(s => s !== name);
      updateComboUI();
    }

    function clearComboSubstances() {
      activeComboList = [];
      updateComboUI();
    }

    function handleComboSearchKey(e) {
      if (e.key === 'Enter') addSearchedComboSubstance();
    }

    function addSearchedComboSubstance() {
      const input = document.getElementById('comboSearchAdd');
      const val = input.value.trim();
      if (val) {
        addComboSubstance(val);
        input.value = '';
        document.getElementById('comboSuggestionsDropdown').style.display = 'none';
      }
    }

    async function filterComboSearchSuggestions(q) {
      const dropdown = document.getElementById('comboSuggestionsDropdown');
      if (!q || q.length < 2) {
        dropdown.style.display = 'none';
        return;
      }
      try {
        const res = await fetch(`/api/catalog?limit=10&q=${encodeURIComponent(q)}`);
        const items = await res.json();
        if (items.length === 0) {
          dropdown.style.display = 'none';
          return;
        }
        dropdown.innerHTML = items.map(it => `
          <div style="padding: 0.6rem 0.9rem; cursor: pointer; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 0.85rem;" onmouseover="this.style.background='rgba(56,189,248,0.1)'" onmouseout="this.style.background='transparent'" onclick="addComboSubstance('${it.name}'); document.getElementById('comboSuggestionsDropdown').style.display='none'; document.getElementById('comboSearchAdd').value='';">
            <strong>${it.name}</strong> <span style="font-size:0.75rem; color:var(--text-muted);">(${it.slug})</span>
          </div>
        `).join('');
        dropdown.style.display = 'block';
      } catch (err) {}
    }

    function updateComboUI() {
      document.getElementById('comboCount').innerText = activeComboList.length;
      const chipsTray = document.getElementById('comboActiveChips');
      
      if (activeComboList.length === 0) {
        chipsTray.innerHTML = `<span style="font-size: 0.82rem; color: var(--text-dim);">No substances selected yet. Click any quick-add chip above or search the catalog.</span>`;
        document.getElementById('comboResultsArea').innerHTML = '';
        return;
      }

      chipsTray.innerHTML = activeComboList.map(s => `
        <span class="chip active">
          ${s}
          <span class="chip-remove" onclick="removeComboSubstance('${s}')">&times;</span>
        </span>
      `).join('');

      if (activeComboList.length >= 2) {
        evaluateComboRadar();
      } else {
        document.getElementById('comboResultsArea').innerHTML = `
          <div style="text-align: center; padding: 2.5rem; color: var(--text-muted); font-size: 0.9rem; background: #090e1a; border-radius: var(--radius-sm); border: 1px solid var(--card-border);">
            🔍 Please select at least 2 substances above to evaluate synergistic interactions.
          </div>
        `;
      }
    }

    async function evaluateComboRadar() {
      const res = await fetch('/api/check-combo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ substances: activeComboList })
      });
      const data = await res.json();
      renderComboResults(data);
    }

    function renderComboResults(data) {
      const container = document.getElementById('comboResultsArea');
      const risk = data.overall_risk || 'LOW_OR_UNKNOWN';
      
      let bannerClass = 'risk-banner-safe';
      let badgeClass = 'badge-safe';
      let titleColor = 'var(--safe)';
      let desc = 'No critical physiological contraindications identified in matrix. Subjective intensity may still be elevated.';

      if (risk === 'DEADLY') {
        bannerClass = 'risk-banner-deadly';
        badgeClass = 'badge-deadly';
        titleColor = 'var(--deadly)';
        desc = 'CRITICAL DANGER: High probability of fatal synergy (respiratory arrest, severe serotonin syndrome, or cardiac collapse). Do NOT combine!';
      } else if (risk === 'DANGEROUS') {
        bannerClass = 'risk-banner-dangerous';
        badgeClass = 'badge-dangerous';
        titleColor = 'var(--dangerous)';
        desc = 'SEVERE RISK: Synergistic toxicity, intense physiological strain, or high potential for adverse medical outcomes.';
      } else if (risk === 'CAUTION') {
        bannerClass = 'risk-banner-caution';
        badgeClass = 'badge-caution';
        titleColor = 'var(--caution)';
        desc = 'CAUTION: Unpredictable psychological potentiation, metabolic inhibition, or cross-tolerance. Use extreme care.';
      }

      container.innerHTML = `
        <div class="risk-banner ${bannerClass}">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.8rem;">
            <div>
              <div style="font-family: var(--font-display); font-size: 0.74rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">
                OVERALL SYNERGISTIC RISK LEVEL:
              </div>
              <h2 style="font-family: var(--font-display); color: ${titleColor}; font-size: 1.5rem; font-weight: 800; letter-spacing: -0.01em;">
                ${risk}
              </h2>
            </div>
            <span class="badge ${badgeClass}" style="font-size: 0.9rem; padding: 0.45rem 0.9rem;">
              ${risk}
            </span>
          </div>
          <div style="font-size: 0.88rem; color: #cbd5e1; line-height: 1.5;">
            ${desc}
          </div>
        </div>

        <h3 style="font-family: var(--font-display); color: #fff; font-size: 1.05rem; margin: 1.3rem 0 0.8rem 0;">
          Pairwise Pharmacological Breakdown:
        </h3>
        
        ${(data.interactions || []).length === 0 ? `
          <div style="background: #090e1a; padding: 1.2rem; border-radius: var(--radius-sm); border: 1px solid var(--card-border); color: #cbd5e1; font-size: 0.88rem;">
            ✓ No direct contraindication documented in the clinical matrix for this exact pair combination.<br>
            <span style="font-size: 0.78rem; color: var(--text-muted);">Always titrate slowly and never consume alone.</span>
          </div>
        ` : ''}

        ${(data.interactions || []).map(it => `
          <div class="pairwise-card" style="border-left-color: ${it.risk_level === 'DEADLY' ? 'var(--deadly)' : (it.risk_level === 'DANGEROUS' ? 'var(--dangerous)' : 'var(--caution)')};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.45rem;">
              <h4 style="font-family: var(--font-display); color: #fff; font-size: 1.05rem;">
                ⚡ ${it.substance_a.toUpperCase()} + ${it.substance_b.toUpperCase()}
              </h4>
              <span class="badge ${it.risk_level === 'DEADLY' ? 'badge-deadly' : (it.risk_level === 'DANGEROUS' ? 'badge-dangerous' : 'badge-caution')}">
                ${it.risk_level}
              </span>
            </div>
            <p style="font-size: 0.86rem; color: #fca5a5; margin-bottom: 0.35rem; line-height: 1.5;">
              <strong>Biochemical Mechanism:</strong> ${it.mechanism}
            </p>
            <p style="font-size: 0.84rem; color: #cbd5e1; line-height: 1.5;">
              <strong>Harm Reduction Action:</strong> ${it.harm_reduction_advice}
            </p>
          </div>
        `).join('')}
      `;
    }

    // --- TAB 3: MASTER CATALOG (560+ SUBSTANCES) ---
    async function loadCatalog(query = '', category = '') {
      let url = `/api/catalog?limit=90&q=${encodeURIComponent(query)}`;
      if (category) url += `&category=${encodeURIComponent(category)}`;
      const res = await fetch(url);
      catalogData = await res.json();
      renderCatalog(catalogData);

      const statsRes = await fetch('/api/catalog-stats');
      const stats = await statsRes.json();
      document.getElementById('catalogHeaderStats').innerText = 
        `${stats.total_catalog_substances} Substances Indexed • ${stats.total_indexed_reports} Harvested IDs`;
    }

    function renderCatalog(list) {
      const container = document.getElementById('catalogList');
      if (list.length === 0) {
        container.innerHTML = '<div style="grid-column: 1 / -1; color: var(--text-muted); padding: 2.5rem; text-align: center; background: #090e1a; border-radius: 8px;">No catalog entries found matching search query.</div>';
        return;
      }
      container.innerHTML = list.map(item => {
        const catKeys = Object.keys(item.categories || {});
        return `
          <div class="card" style="margin-bottom: 0; display: flex; flex-direction: column; justify-content: space-between; background: #090e1a;">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.3rem;">
                <h3 style="font-family: var(--font-display); color: #fff; font-size: 1.05rem;">${item.name}</h3>
                <span class="badge" style="background: #060a12; color: var(--accent); border: 1px solid var(--card-border);">${item.slug}</span>
              </div>
              <p style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.45rem;">
                ${item.description || 'Erowid Psychoactive Taxonomy Entry'}
              </p>
              <div style="margin: 0.4rem 0; display: flex; flex-wrap: wrap; gap: 0.3rem;">
                ${catKeys.slice(0, 3).map(c => `<span class="badge badge-cat">${c}</span>`).join('')}
                ${catKeys.length > 3 ? `<span class="badge badge-cat">+${catKeys.length - 3}</span>` : ''}
              </div>
            </div>
            <div style="margin-top: 0.9rem; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--card-border); padding-top: 0.65rem;">
              <span style="font-family: var(--font-mono); font-size: 0.76rem; color: var(--accent); font-weight: 700;">
                ${item.total_reports > 0 ? item.total_reports + ' reports' : ''}
              </span>
              <div style="display: flex; gap: 0.35rem;">
                <button class="btn-secondary" style="font-size: 0.75rem; padding: 0.3rem 0.6rem;" onclick="addComboSubstance('${item.name}'); switchNav('radar');">+ Radar</button>
                <button class="btn-secondary" style="font-size: 0.75rem; padding: 0.3rem 0.6rem;" onclick="setDoseSubstance('${item.name}', 100, 'mg', 'Oral'); switchNav('dossiers');">Dose</button>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    function filterCatalogByCat(cat, el) {
      document.querySelectorAll('#catalogCatPills .chip').forEach(c => c.classList.remove('active'));
      el.classList.add('active');
      const q = document.getElementById('catalogSearch').value;
      loadCatalog(q, cat);
    }

    function jumpCatalogAlpha(letter, el) {
      document.querySelectorAll('#alphabetJumpBar .alphabet-btn').forEach(b => b.classList.remove('active'));
      el.classList.add('active');
      const input = document.getElementById('catalogSearch');
      input.value = letter;
      loadCatalog(letter);
    }

    function debounceCatalogSearch() {
      clearTimeout(catalogDebounceTimer);
      catalogDebounceTimer = setTimeout(() => {
        const q = document.getElementById('catalogSearch').value;
        const activeChip = document.querySelector('#catalogCatPills .chip.active');
        const cat = activeChip ? activeChip.innerText.toLowerCase().replace(/[^a-z]/g, '') : '';
        loadCatalog(q, cat === 'allcategories561' ? '' : cat);
      }, 200);
    }

    // --- TAB 4: TRIP VAULT ---
    let currentVaultTag = '';
    async function loadExperiences() {
      const q = document.getElementById('expSearchQ').value;
      let url = '/api/experiences?limit=30';
      if (q) url += '&q=' + encodeURIComponent(q);
      if (currentVaultTag) url += '&tag=' + encodeURIComponent(currentVaultTag);

      const res = await fetch(url);
      const reports = await res.json();
      const container = document.getElementById('expResultsList');

      if (reports.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); padding: 2.5rem; text-align: center; background: #090e1a; border-radius: 8px;">No experience reports found in local vault matching query.</div>';
        return;
      }

      container.innerHTML = reports.map(r => `
        <div class="exp-item" onclick="openReportModal(${r.id})">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <h4 style="font-family: var(--font-display); color: #fff; font-size: 1.05rem;">Exp #${r.id}: ${r.title}</h4>
            <span style="font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-muted);">${r.exp_year || ''}</span>
          </div>
          <div style="font-size: 0.8rem; color: var(--text-muted); margin: 0.35rem 0;">
            Substance: <strong style="color: var(--accent);">${r.substance_summary}</strong> | Author: ${r.author} | Weight: ${r.body_weight || 'N/A'}
          </div>
          <div style="margin-bottom: 0.4rem;">
            ${(r.harm_flags || []).map(f => `<span class="badge badge-deadly" style="margin-right: 4px;">${f}</span>`).join('')}
          </div>
          <div style="font-size: 0.86rem; color: #cbd5e1; line-height: 1.5;">${r.snippet}</div>
        </div>
      `).join('');
    }

    function filterVaultTag(tag, el) {
      currentVaultTag = tag;
      document.querySelectorAll('#vaultFilterPills .chip').forEach(c => c.classList.remove('active'));
      el.classList.add('active');
      loadExperiences();
    }

    async function quickFetchExp() {
      const id = document.getElementById('quickExpId').value.trim();
      if (!id) return;
      openReportModal(id);
    }

    async function openReportModal(id) {
      document.getElementById('modalTitle').innerText = `Exp #${id}: Loading from Archive...`;
      document.getElementById('modalMeta').innerText = "Retrieving raw snapshot, decompressing, and analyzing symptoms...";
      document.getElementById('modalFlags').innerHTML = "";
      document.getElementById('modalDoses').innerHTML = "";
      document.getElementById('modalBody').innerText = "Connecting to Erowid Archive. Please wait...";
      document.getElementById('reportModal').classList.add('active');

      try {
        const res = await fetch('/api/experience?id=' + id);
        const exp = await res.json();
        if (exp.error) {
          document.getElementById('modalTitle').innerText = `Exp #${id}: Retrieval Notice`;
          document.getElementById('modalBody').innerText = exp.error;
          return;
        }

        document.getElementById('modalTitle').innerText = `Exp #${exp.id}: ${exp.title}`;
        document.getElementById('modalMeta').innerText = 
          `Substance: ${exp.substance_summary} | Author: ${exp.author} | Year: ${exp.exp_year || 'N/A'} | Weight: ${exp.body_weight || 'N/A'} | Words: ${exp.word_count || 'N/A'}`;
        
        document.getElementById('modalFlags').innerHTML = (exp.harm_flags || []).map(f => 
          `<span class="badge badge-deadly" style="margin-right: 6px;">${f}</span>`
        ).join('');

        document.getElementById('modalDoses').innerHTML = (exp.doses || []).length > 0 ? `
          <div style="background: #090e1a; padding: 0.85rem; border-radius: 6px; font-size: 0.82rem; border: 1px solid var(--card-border);">
            <strong style="color: var(--accent);">Reported Dosages:</strong><br>
            ${exp.doses.map(d => `• ${d.substance}: <strong>${d.amount || ''} ${d.unit || ''}</strong> (${d.method || 'Oral'})`).join('<br>')}
          </div>
        ` : '';

        document.getElementById('modalBody').innerText = exp.narrative;
      } catch (err) {
        document.getElementById('modalTitle').innerText = `Exp #${id}: Retrieval Failed`;
        document.getElementById('modalBody').innerText = "Network or parsing error: " + err.message;
      }
    }

    function copyReportNarrative() {
      const text = document.getElementById('modalBody').innerText;
      navigator.clipboard.writeText(text);
      alert('Report narrative copied to clipboard!');
    }

    // --- TAB 5: REAGENTS MATRIX ---
    const reagentDatabase = {
      "MDMA": [
        { name: "Marquis", color: "#111827", label: "Black / Dark Purple (<5s)", status: "Positive" },
        { name: "Mecke", color: "#064e3b", label: "Dark Blue-Green / Black", status: "Positive" },
        { name: "Simon's (A+B)", color: "#1d4ed8", label: "Bright Cobalt Blue (Secondary Amine)", status: "Confirmatory" },
        { name: "Froehde", color: "#0f172a", label: "Black", status: "Positive" }
      ],
      "LSD": [
        { name: "Ehrlich", color: "#7e22ce", label: "Pink / Violet (Indole Confirmed)", status: "Positive" },
        { name: "Hofmann", color: "#2563eb", label: "Blue / Indigo", status: "Confirmatory" },
        { name: "Marquis", color: "#374151", label: "Olive to Black (Slow)", status: "Adulterant Check" }
      ],
      "2CB": [
        { name: "Marquis", color: "#84cc16", label: "Bright Yellow to Green", status: "Positive" },
        { name: "Mecke", color: "#ca8a04", label: "Brownish-Yellow to Dark", status: "Positive" },
        { name: "Froehde", color: "#65a30d", label: "Yellow to Green", status: "Positive" }
      ],
      "Ketamine": [
        { name: "Marquis", color: "#334155", label: "No Reaction / Clear", status: "Expected" },
        { name: "Mecke", color: "#334155", label: "No Reaction / Clear", status: "Expected" },
        { name: "Mandelin", color: "#b45309", label: "Orange to Brownish", status: "Positive" },
        { name: "Morris", color: "#6d28d9", label: "Deep Purple / Violet", status: "Confirmatory" }
      ],
      "Cocaine": [
        { name: "Scott Reagent", color: "#0284c7", label: "Bright Blue Flakes", status: "Positive" },
        { name: "Marquis", color: "#334155", label: "No Reaction (Adulterant Check)", status: "Expected" },
        { name: "Liebermann", color: "#d97706", label: "Orange-Yellow", status: "Positive" }
      ],
      "Methamphetamine": [
        { name: "Marquis", color: "#ea580c", label: "Deep Orange to Reddish-Brown", status: "Positive" },
        { name: "Simon's (A+B)", color: "#2563eb", label: "Bright Cobalt Blue", status: "Positive" },
        { name: "Mecke", color: "#78350f", label: "Yellow-Brown", status: "Positive" }
      ],
      "Amphetamine": [
        { name: "Marquis", color: "#c2410c", label: "Red-Orange to Brown", status: "Positive" },
        { name: "Simon's (A+B)", color: "#334155", label: "NO REACTION (Distinguishes from Meth)", status: "Expected" },
        { name: "Mecke", color: "#a16207", label: "Light Green to Brown", status: "Positive" }
      ],
      "Heroin": [
        { name: "Marquis", color: "#6b21a8", label: "Deep Purple / Violet", status: "Positive" },
        { name: "Mecke", color: "#065f46", label: "Green to Dark Blue", status: "Positive" },
        { name: "Froehde", color: "#581c87", label: "Purple", status: "Positive" }
      ],
      "DXM": [
        { name: "Marquis", color: "#1e293b", label: "Grey to Black", status: "Positive" },
        { name: "Mecke", color: "#047857", label: "Yellow to Dark Green", status: "Positive" }
      ]
    };

    function renderReagentReactionDetails() {
      const sub = document.getElementById('reagentSubSelect').value;
      const reactions = reagentDatabase[sub] || [];
      const container = document.getElementById('reagentReactionsContainer');
      container.innerHTML = reactions.map(r => `
        <div class="reagent-card">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong style="color: var(--accent); font-family: var(--font-display); font-size: 0.9rem;">${r.name}</strong>
            <span class="badge ${r.status === 'Positive' ? 'badge-safe' : 'badge-cat'}">${r.status}</span>
          </div>
          <div class="reagent-swatch" style="background: ${r.color};"></div>
          <div style="font-size: 0.8rem; color: #cbd5e1; font-weight: 600;">${r.label}</div>
        </div>
      `).join('');
    }

    async function loadTestingProtocols() {
      renderReagentReactionDetails();
      const res = await fetch('/api/testing-guide');
      const data = await res.json();
      const div = document.getElementById('testingProtocolsTable');
      div.innerHTML = `
        <h4 style="font-family: var(--font-display); color: #fff; margin-bottom: 0.6rem; font-size: 0.95rem;">Primary Clinical Reagent Kits Reference:</h4>
        <table class="data-table">
          <thead>
            <tr><th>Reagent Kit</th><th>Primary Substances</th><th>Reaction & Notes</th></tr>
          </thead>
          <tbody>
            ${data.reagent_kits.map(k => `
              <tr>
                <td><strong style="color: var(--accent);">${k.name}</strong></td>
                <td>${k.primary_use}</td>
                <td style="font-size: 0.82rem; color: #cbd5e1;">${k.notes}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      `;
    }

    // --- TAB 6: HARVESTER ---
    async function triggerSubHarvest() {
      const sub = document.getElementById('harvestSubInput').value.trim();
      if (!sub) return;
      const log = document.getElementById('scraperLog');
      log.innerHTML = `<span style="color: var(--accent);">[Harvesting] Crawling category index pages for '${sub}'...</span>`;

      const res = await fetch('/api/harvest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ substance: sub })
      });
      const data = await res.json();
      if (data.success) {
        log.innerHTML = `<span style="color: var(--safe);">[Success] Harvested ${data.count} report IDs for '${sub}' into SQLite queue!</span>`;
      } else {
        log.innerHTML = `<span style="color: var(--deadly);">[Error] Harvesting failed: ${data.error}</span>`;
      }
    }

    async function triggerBatchScrape() {
      const log = document.getElementById('scraperLog');
      log.innerHTML = `<span style="color: var(--accent);">[Worker Pool] Downloading up to 15 queued reports in parallel...</span>`;

      const res = await fetch('/api/batch-scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 15, workers: 3 })
      });
      const data = await res.json();
      log.innerHTML = `<span style="color: var(--safe);">[Success] Scraped and indexed ${data.success} full reports out of ${data.total} attempted!</span>`;
      loadExperiences();
    }

    // --- SPOTLIGHT SEARCH (CMD+K) ---
    async function runSpotlightSearch(q) {
      const resultsDiv = document.getElementById('spotlightResults');
      if (!q.trim()) {
        resultsDiv.innerHTML = `
          <div style="font-size: 0.8rem; color: var(--text-muted); padding: 0.5rem;">QUICK SHORTCUTS:</div>
          <div style="padding: 0.6rem 0.8rem; border-radius: 6px; background: rgba(255,255,255,0.03); cursor: pointer; display: flex; justify-content: space-between;" onclick="openEmergencyModal(); closeSpotlightModal();">
            <span>🚨 Emergency Overdose Protocol</span>
            <span class="kbd-shortcut">Cmd+E</span>
          </div>
          <div style="padding: 0.6rem 0.8rem; border-radius: 6px; background: rgba(255,255,255,0.03); cursor: pointer; display: flex; justify-content: space-between;" onclick="switchNav('dossiers'); closeSpotlightModal();">
            <span>⚖️ Dosage Safety Ladder</span>
            <span class="kbd-shortcut">Tab 1</span>
          </div>
          <div style="padding: 0.6rem 0.8rem; border-radius: 6px; background: rgba(255,255,255,0.03); cursor: pointer; display: flex; justify-content: space-between;" onclick="switchNav('radar'); closeSpotlightModal();">
            <span>⚡ Multi-Drug Combo Risk Radar</span>
            <span class="kbd-shortcut">Tab 2</span>
          </div>
        `;
        return;
      }

      try {
        const res = await fetch(`/api/catalog?limit=8&q=${encodeURIComponent(q)}`);
        const items = await res.json();
        if (items.length === 0) {
          resultsDiv.innerHTML = `<div style="color: var(--text-muted); padding: 1rem; text-align: center;">No matching substances found.</div>`;
          return;
        }
        resultsDiv.innerHTML = items.map(item => `
          <div style="padding: 0.6rem 0.8rem; border-radius: 6px; background: rgba(255,255,255,0.04); cursor: pointer; display: flex; justify-content: space-between; align-items: center;" onmouseover="this.style.background='rgba(56,189,248,0.12)'" onmouseout="this.style.background='rgba(255,255,255,0.04)'" onclick="setDoseSubstance('${item.name}', 100, 'mg', 'Oral'); switchNav('dossiers'); closeSpotlightModal();">
            <div>
              <strong style="color: #fff;">${item.name}</strong>
              <span style="font-size: 0.74rem; color: var(--accent); margin-left: 0.4rem;">${item.slug}</span>
            </div>
            <span class="badge badge-cat">Open Dossier</span>
          </div>
        `).join('');
      } catch (err) {}
    }

    // Initialize on page load
    loadSubstances();
    loadTestingProtocols();
  </script>
</body>
</html>
"""
