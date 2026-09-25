"""
Zero-dependency HTTP Web Server and Harm Reduction Dashboard for Erowid SafeDB.
Serves a responsive single-page application and RESTful JSON API with master catalog access.
"""

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

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
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
                    self.wfile.write(json.dumps({"error": f"Experience {exp_id} could not be retrieved from Erowid archive."}).encode("utf-8"))
            except ValueError:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Invalid ID format"}).encode("utf-8"))
            return

        elif path == "/api/check-dose":
            sub_name = query.get("substance", [""])[0]
            amount_str = query.get("amount", ["0"])[0]
            unit = query.get("unit", ["mg"])[0]
            route = query.get("route", ["Oral"])[0]
            try:
                amt = float(amount_str)
                result = self.engine.evaluate_dosage(sub_name, amt, unit=unit, route=route)
                self._set_headers(200)
                self.wfile.write(json.dumps(result).encode("utf-8"))
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
            res = self.scraper.scrape_harvested_batch(self.db, substance_slug=sub_slug, limit=limit, max_workers=workers)
            self._set_headers(200)
            self.wfile.write(json.dumps(res).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))


def start_server(db: Database, port: int = 8080):
    """Starts the Erowid SafeDB web interface and REST API."""
    SafeDBRequestHandler.db = db
    SafeDBRequestHandler.engine = HarmReductionEngine(db)
    SafeDBRequestHandler.scraper = ErowidScraper()

    # Ensure catalog is indexed
    if db.get_catalog_stats()["total_catalog_substances"] == 0:
        try:
            SafeDBRequestHandler.scraper.index_catalog(db)
        except Exception:
            pass

    server = http.server.HTTPServer(("0.0.0.0", port), SafeDBRequestHandler)
    print(f"\n🌐 Erowid SafeDB Web Interface running at: http://localhost:{port}")
    print("Press Ctrl+C to stop the server.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Erowid SafeDB - Systematic Harm Reduction & Universal Archive</title>
  <link rel="icon" type="image/png" href="/app_icon.png">
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #131b2e;
      --card-hover: #18223a;
      --card-border: #1e293b;
      --border-accent: rgba(56, 189, 248, 0.3);
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --accent-glow: rgba(56, 189, 248, 0.15);
      --deadly: #ef4444;
      --deadly-bg: rgba(239, 68, 68, 0.15);
      --dangerous: #f97316;
      --dangerous-bg: rgba(249, 115, 22, 0.15);
      --caution: #f59e0b;
      --caution-bg: rgba(245, 158, 11, 0.15);
      --safe: #10b981;
      --safe-bg: rgba(16, 185, 129, 0.15);
      --radius: 10px;
      --radius-sm: 6px;
      --font-stack: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", system-ui, sans-serif;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: var(--font-stack); }
    body { background-color: var(--bg); color: var(--text); line-height: 1.6; overflow-x: hidden; -webkit-font-smoothing: antialiased; }

    /* Top Glass App Bar */
    header {
      position: sticky; top: 0; z-index: 100;
      background: rgba(9, 13, 22, 0.85);
      backdrop-filter: blur(20px);
      -webkit-backdrop-filter: blur(20px);
      border-bottom: 1px solid var(--card-border);
      padding: 0.9rem 1.8rem;
      display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;
    }
    .brand-wrap { display: flex; align-items: center; gap: 0.8rem; }
    .brand-logo { font-size: 1.6rem; }
    .brand-title { font-size: 1.25rem; font-weight: 700; color: #fff; letter-spacing: -0.02em; display: flex; align-items: center; gap: 0.4rem; }
    .brand-version { font-size: 0.65rem; background: rgba(56, 189, 248, 0.15); color: var(--accent); border: 1px solid var(--border-accent); padding: 0.15rem 0.4rem; border-radius: 4px; font-weight: 600; text-transform: uppercase; }
    .brand-subtitle { font-size: 0.78rem; color: var(--text-muted); }
    
    .status-pill {
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.25);
      color: #34d399;
      font-size: 0.75rem;
      padding: 0.35rem 0.75rem;
      border-radius: 20px;
      display: flex; align-items: center; gap: 0.4rem; font-weight: 500;
    }
    .pulse-dot { width: 7px; height: 7px; border-radius: 50%; background: #34d399; animation: pulse 2s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(1.2); } }

    /* Emergency Alert Button in Header */
    .btn-emergency-top {
      background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%);
      color: #fff;
      font-weight: 700;
      font-size: 0.82rem;
      border: none;
      padding: 0.5rem 1rem;
      border-radius: 20px;
      cursor: pointer;
      display: flex; align-items: center; gap: 0.4rem;
      box-shadow: 0 0 15px rgba(239, 68, 68, 0.4);
      transition: all 0.2s;
    }
    .btn-emergency-top:hover { transform: translateY(-1px); box-shadow: 0 0 20px rgba(239, 68, 68, 0.6); }

    /* Tab Navigation */
    nav.tab-nav {
      background: #0d1322;
      border-bottom: 1px solid var(--card-border);
      padding: 0.5rem 1.8rem;
      display: flex; gap: 0.4rem; overflow-x: auto;
    }
    nav.tab-nav button {
      background: transparent;
      border: 1px solid transparent;
      color: var(--text-muted);
      padding: 0.55rem 0.95rem;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-size: 0.86rem;
      font-weight: 600;
      display: flex; align-items: center; gap: 0.45rem;
      transition: all 0.15s ease-in-out;
      white-space: nowrap;
    }
    nav.tab-nav button:hover { background: rgba(255, 255, 255, 0.04); color: #fff; }
    nav.tab-nav button.active {
      background: var(--card-bg);
      color: var(--accent);
      border-color: var(--border-accent);
      box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    }

    /* Layout & Containers */
    main { max-width: 1300px; margin: 1.5rem auto; padding: 0 1.5rem; }
    .tab-content { display: none; }
    .tab-content.active { display: block; animation: fadeIn 0.2s ease-in-out; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      padding: 1.4rem;
      margin-bottom: 1.4rem;
      box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    }
    .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid var(--card-border); padding-bottom: 0.6rem; }
    .card-title { font-size: 1.2rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 0.5rem; }
    .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 1.2rem; }
    .grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 1rem; }

    /* Inputs, Selects, Buttons */
    input, select, textarea {
      background: #090e1a;
      border: 1px solid var(--card-border);
      color: #fff;
      padding: 0.65rem 0.85rem;
      border-radius: var(--radius-sm);
      font-size: 0.9rem;
      width: 100%;
      outline: none;
      transition: border 0.15s, box-shadow 0.15s;
    }
    input:focus, select:focus, textarea:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 2px var(--accent-glow);
    }
    button.btn-primary {
      background: linear-gradient(135deg, var(--accent) 0%, #0284c7 100%);
      color: #090e1a;
      font-weight: 700;
      border: none;
      padding: 0.65rem 1.3rem;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-size: 0.88rem;
      display: inline-flex; align-items: center; justify-content: center; gap: 0.4rem;
      transition: all 0.15s;
    }
    button.btn-primary:hover { filter: brightness(1.1); transform: translateY(-1px); }
    button.btn-secondary {
      background: #1e293b;
      color: #e2e8f0;
      border: 1px solid rgba(255,255,255,0.06);
      padding: 0.45rem 0.85rem;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-size: 0.8rem;
      font-weight: 500;
      transition: all 0.15s;
    }
    button.btn-secondary:hover { background: #334155; color: #fff; }

    /* Chips & Pills */
    .chip {
      display: inline-flex; align-items: center; gap: 0.35rem;
      background: #18223a;
      border: 1px solid var(--card-border);
      color: #cbd5e1;
      padding: 0.35rem 0.75rem;
      border-radius: 20px;
      font-size: 0.8rem;
      cursor: pointer;
      user-select: none;
      transition: all 0.15s;
    }
    .chip:hover { background: #223254; color: #fff; border-color: var(--border-accent); }
    .chip.active { background: rgba(56, 189, 248, 0.2); color: var(--accent); border-color: var(--accent); font-weight: 600; }
    .chip .chip-remove { margin-left: 0.2rem; cursor: pointer; color: #94a3b8; }
    .chip .chip-remove:hover { color: var(--deadly); }

    /* Risk Badges & Meters */
    .badge {
      display: inline-flex; align-items: center; gap: 0.3rem;
      padding: 0.25rem 0.6rem;
      border-radius: 4px;
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }
    .badge-deadly { background: var(--deadly-bg); color: var(--deadly); border: 1px solid var(--deadly); }
    .badge-dangerous { background: var(--dangerous-bg); color: var(--dangerous); border: 1px solid var(--dangerous); }
    .badge-caution { background: var(--caution-bg); color: var(--caution); border: 1px solid var(--caution); }
    .badge-safe { background: var(--safe-bg); color: var(--safe); border: 1px solid var(--safe); }
    .badge-cat { background: #1e293b; color: #94a3b8; font-size: 0.7rem; font-weight: 500; border-radius: 12px; padding: 0.15rem 0.5rem; }

    /* Risk Gauge Display */
    .risk-gauge-box {
      border-radius: var(--radius);
      padding: 1.4rem;
      margin: 1.2rem 0;
      display: flex; flex-direction: column; gap: 0.8rem;
      position: relative; overflow: hidden;
    }
    .risk-gauge-bar {
      display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 4px;
      height: 10px; border-radius: 5px; overflow: hidden; background: #090e1a;
    }
    .gauge-segment { height: 100%; opacity: 0.25; transition: opacity 0.3s; }
    .gauge-segment.active { opacity: 1; box-shadow: 0 0 10px currentColor; }
    .gauge-safe { background: var(--safe); color: var(--safe); }
    .gauge-caution { background: var(--caution); color: var(--caution); }
    .gauge-dangerous { background: var(--dangerous); color: var(--dangerous); }
    .gauge-deadly { background: var(--deadly); color: var(--deadly); }

    /* Dosage Ladder Scale Bar */
    .dosage-ladder-container {
      background: #090e1a;
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      padding: 1.2rem;
      margin: 1rem 0;
    }
    .ladder-bar {
      position: relative;
      height: 24px;
      border-radius: 12px;
      background: linear-gradient(to right, #38bdf8 0%, #10b981 25%, #84cc16 50%, #f59e0b 75%, #ef4444 100%);
      margin: 1.5rem 0 1rem 0;
    }
    .ladder-pointer {
      position: absolute;
      top: -12px;
      transform: translateX(-50%);
      width: 0; height: 0;
      border-left: 8px solid transparent;
      border-right: 8px solid transparent;
      border-top: 10px solid #fff;
      filter: drop-shadow(0 2px 4px rgba(0,0,0,0.8));
      transition: left 0.3s ease;
    }
    .ladder-labels {
      display: flex; justify-content: space-between; font-size: 0.74rem; color: var(--text-muted); font-weight: 600;
    }

    /* Experience Card */
    .exp-item {
      background: #101726;
      border: 1px solid var(--card-border);
      border-left: 4px solid var(--accent);
      border-radius: var(--radius-sm);
      padding: 1rem 1.2rem;
      margin-bottom: 0.9rem;
      cursor: pointer;
      transition: all 0.15s;
    }
    .exp-item:hover { background: #162033; transform: translateX(3px); border-color: var(--border-accent); }
    .exp-meta { font-size: 0.8rem; color: var(--text-muted); margin: 0.3rem 0; }
    .exp-snippet { font-size: 0.87rem; color: #cbd5e1; line-height: 1.5; }

    /* Modals */
    .modal {
      display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(0, 0, 0, 0.8); backdrop-filter: blur(8px);
      z-index: 1000; justify-content: center; align-items: center; padding: 1.5rem;
    }
    .modal.active { display: flex; animation: fadeIn 0.2s; }
    .modal-content {
      background: #111827;
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      max-width: 900px; width: 100%; max-height: 90vh;
      overflow-y: auto; padding: 2rem; position: relative;
      box-shadow: 0 20px 50px rgba(0,0,0,0.7);
    }
    .modal-close {
      position: absolute; top: 1.2rem; right: 1.2rem;
      background: #1e293b; color: #fff; border: none;
      width: 32px; height: 32px; border-radius: 50%;
      font-size: 1.1rem; cursor: pointer; display: flex; align-items: center; justify-content: center;
      transition: background 0.15s;
    }
    .modal-close:hover { background: #334155; }

    /* Tables */
    table.data-table { width: 100%; border-collapse: collapse; margin-top: 0.8rem; font-size: 0.88rem; }
    table.data-table th, table.data-table td { padding: 0.7rem; text-align: left; border-bottom: 1px solid var(--card-border); }
    table.data-table th { background: #090e1a; color: var(--accent); font-weight: 600; }
  </style>
</head>
<body>

  <!-- Top Application Bar -->
  <header>
    <div class="brand-wrap">
      <div class="brand-logo"><img src="/app_icon.png" style="width: 38px; height: 38px; border-radius: 9px; box-shadow: 0 0 12px rgba(56, 189, 248, 0.4); display: block;" onerror="this.onerror=null; this.parentElement.innerText='🛡️'"></div>
      <div>
        <div class="brand-title">Erowid SafeDB <span class="brand-version">v2.0 Native</span></div>
        <div class="brand-subtitle">Clinical Harm Reduction, Pharmacological Interaction Radar & Master Vault</div>
      </div>
    </div>

    <div style="display: flex; align-items: center; gap: 0.8rem;">
      <div class="status-pill" id="statusBarPill">
        <span class="pulse-dot"></span>
        <span id="statusBarText">561 Substances Indexed • Offline Ready</span>
      </div>
      <button class="btn-emergency-top" onclick="openEmergencyModal()">
        <span>🚨</span> Emergency Protocol
      </button>
    </div>
  </header>

  <!-- Modern Navigation Tabs -->
  <nav class="tab-nav">
    <button class="active" onclick="switchNav('dossiers')">💊 Dossiers & Dosage</button>
    <button onclick="switchNav('radar')">⚡ Combo Risk Radar</button>
    <button onclick="switchNav('catalog')">📚 Master Catalog (560+)</button>
    <button onclick="switchNav('vault')">📖 Trip Vault</button>
    <button onclick="switchNav('reagents')">🧪 Reagents & Test Strips</button>
    <button onclick="switchNav('harvester')">📥 Archive Harvester</button>
  </nav>

  <main>
    <!-- TAB 1: DOSSIERS & INTERACTIVE DOSAGE SAFETY LADDER -->
    <div id="tab-dossiers" class="tab-content active">
      <!-- Interactive Dosage Evaluator -->
      <div class="card" style="border-top: 3px solid var(--accent);">
        <div class="card-header">
          <div class="card-title">⚖️ Interactive Dosage Safety Ladder & Weight Calculator</div>
          <span style="font-size: 0.8rem; color: var(--text-muted);">Compare intended dose against verified clinical safety thresholds</span>
        </div>

        <!-- Quick Select Pills -->
        <div style="margin-bottom: 1rem;">
          <div style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.4rem; font-weight: 600;">QUICK PICK SUBSTANCE:</div>
          <div style="display: flex; flex-wrap: wrap; gap: 0.4rem;" id="quickDosePills">
            <span class="chip" onclick="setDoseSubstance('MDMA', 120, 'mg', 'Oral')">MDMA (Molly)</span>
            <span class="chip" onclick="setDoseSubstance('Ketamine', 60, 'mg', 'Insufflated')">Ketamine</span>
            <span class="chip" onclick="setDoseSubstance('Psilocybin Mushrooms', 2.0, 'g', 'Oral')">Psilocybin (Shrooms)</span>
            <span class="chip" onclick="setDoseSubstance('LSD', 100, 'ug', 'Oral')">LSD (Acid)</span>
            <span class="chip" onclick="setDoseSubstance('Alprazolam', 0.5, 'mg', 'Oral')">Alprazolam (Xanax)</span>
            <span class="chip" onclick="setDoseSubstance('Cocaine', 50, 'mg', 'Insufflated')">Cocaine</span>
            <span class="chip" onclick="setDoseSubstance('DXM', 250, 'mg', 'Oral')">DXM</span>
            <span class="chip" onclick="setDoseSubstance('2C-B', 15, 'mg', 'Oral')">2C-B</span>
            <span class="chip" onclick="setDoseSubstance('Alcohol', 2, 'standard drinks', 'Oral')">Alcohol</span>
          </div>
        </div>

        <!-- Input row -->
        <div class="grid-2" style="margin-bottom: 1rem;">
          <div>
            <label style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600;">SUBSTANCE NAME:</label>
            <input type="text" id="doseSubInput" placeholder="e.g. MDMA, Ketamine, Psilocybin, Xanax..." value="MDMA" oninput="runDoseCalculation()">
          </div>
          <div style="display: grid; grid-template-columns: 1fr 100px 140px; gap: 0.5rem;">
            <div>
              <label style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600;">AMOUNT:</label>
              <input type="number" id="doseAmtInput" placeholder="Amount" value="120" step="any" oninput="runDoseCalculation()">
            </div>
            <div>
              <label style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600;">UNIT:</label>
              <select id="doseUnitSelect" onchange="runDoseCalculation()">
                <option value="mg">mg</option>
                <option value="g">g</option>
                <option value="ug">ug / mcg</option>
                <option value="ml">ml</option>
              </select>
            </div>
            <div>
              <label style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600;">ROUTE:</label>
              <select id="doseRouteSelect" onchange="runDoseCalculation()">
                <option value="Oral">Oral</option>
                <option value="Insufflated">Insufflated</option>
                <option value="Sublingual">Sublingual</option>
                <option value="Inhalation">Inhalation</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Body Weight Calculator Option -->
        <div style="background: #090e1a; border: 1px solid var(--card-border); border-radius: var(--radius-sm); padding: 0.8rem 1rem; margin-bottom: 1rem; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.8rem;">
          <div style="display: flex; align-items: center; gap: 0.6rem;">
            <span style="font-size: 1.1rem;">⚖️</span>
            <div>
              <div style="font-size: 0.85rem; font-weight: 600;">Harm Reduction Body Weight Calculator</div>
              <div style="font-size: 0.75rem; color: var(--text-muted);">Standard clinical recommendation for empathogens: 1.5 mg/kg body weight</div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <input type="number" id="userWeightInput" placeholder="Weight" value="70" style="width: 80px; margin-bottom: 0;" oninput="runDoseCalculation()">
            <select id="userWeightUnit" style="width: 80px; margin-bottom: 0;" onchange="runDoseCalculation()">
              <option value="kg">kg</option>
              <option value="lbs">lbs</option>
            </select>
            <span id="weightDoseCalcOutput" style="font-size: 0.82rem; color: var(--accent); font-weight: 600; margin-left: 0.4rem;">Guideline: ~105 mg</span>
          </div>
        </div>

        <!-- Visual Dosage Ladder Box -->
        <div class="dosage-ladder-container" id="doseLadderBox">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="font-size: 0.88rem; font-weight: 700; color: #fff;">VISUAL DOSAGE BRACKET SPECTRUM:</div>
            <div id="doseStatusBadge" class="badge badge-safe">COMMON / TYPICAL</div>
          </div>

          <div class="ladder-bar">
            <div id="doseLadderPointer" class="ladder-pointer" style="left: 50%;"></div>
          </div>

          <div class="ladder-labels">
            <span>Threshold</span>
            <span>Light</span>
            <span>Common</span>
            <span>Strong</span>
            <span>Heavy / Danger</span>
          </div>

          <!-- Brackets & Duration Details -->
          <div id="doseDetailsGrid" style="margin-top: 1.2rem; display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.8rem;">
            <!-- Populated via JS -->
          </div>
        </div>
      </div>

      <!-- Clinical Monographs Explorer -->
      <div class="card">
        <div class="card-header">
          <div class="card-title">📖 Curated Clinical Substance Monographs</div>
          <input type="text" id="subSearch" placeholder="Filter clinical dossiers (e.g. MDMA, Psilocybin, Ketamine, Xanax)..." style="width: 300px; margin-bottom: 0;" onkeyup="filterSubstances()">
        </div>
        <div id="substancesList" class="grid-3"></div>
      </div>
    </div>

    <!-- TAB 2: COMBO RISK RADAR (MULTI-DRUG INTERACTION CHECKER) -->
    <div id="tab-radar" class="tab-content">
      <div class="card" style="border-top: 3px solid var(--dangerous);">
        <div class="card-header">
          <div class="card-title">⚡ Multi-Drug Synergistic Risk & Contraindication Radar</div>
          <span style="font-size: 0.8rem; color: var(--text-muted);">Select or search substances to detect lethal synergies (respiratory arrest, serotonin syndrome, cardiac strain)</span>
        </div>

        <!-- Quick Pick Chips for Interaction Checker -->
        <div style="margin-bottom: 1.2rem;">
          <div style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600; margin-bottom: 0.5rem;">QUICK ADD TO COMBINATION:</div>
          <div style="display: flex; flex-wrap: wrap; gap: 0.45rem;">
            <span class="chip" onclick="addComboSubstance('Alcohol')">+ Alcohol</span>
            <span class="chip" onclick="addComboSubstance('MDMA')">+ MDMA (Molly)</span>
            <span class="chip" onclick="addComboSubstance('Cannabis')">+ Cannabis / THC</span>
            <span class="chip" onclick="addComboSubstance('Cocaine')">+ Cocaine</span>
            <span class="chip" onclick="addComboSubstance('Ketamine')">+ Ketamine</span>
            <span class="chip" onclick="addComboSubstance('Alprazolam')">+ Xanax / Benzos</span>
            <span class="chip" onclick="addComboSubstance('Oxycodone')">+ Oxycodone / Opioids</span>
            <span class="chip" onclick="addComboSubstance('LSD')">+ LSD</span>
            <span class="chip" onclick="addComboSubstance('Psilocybin')">+ Psilocybin</span>
            <span class="chip" onclick="addComboSubstance('Amphetamine')">+ Adderall / Speed</span>
            <span class="chip" onclick="addComboSubstance('DXM')">+ DXM</span>
            <span class="chip" onclick="addComboSubstance('SSRI')">+ SSRI Antidepressants</span>
            <span class="chip" onclick="addComboSubstance('Kratom')">+ Kratom</span>
            <span class="chip" onclick="addComboSubstance('GHB')">+ GHB / GBL</span>
            <span class="chip" onclick="addComboSubstance('Caffeine')">+ Caffeine</span>
            <span class="chip" onclick="addComboSubstance('Tramadol')">+ Tramadol</span>
          </div>
        </div>

        <!-- Searchable input for adding ANY substance from 560+ catalog -->
        <div style="display: flex; gap: 0.5rem; margin-bottom: 1.2rem;">
          <input type="text" id="comboSearchAdd" placeholder="Search & add ANY of 560+ catalog substances (e.g. Fentanyl, 2C-B, MAOIs, Methadone)..." style="margin-bottom: 0;" onkeydown="handleComboSearchKey(event)">
          <button class="btn-secondary" onclick="addSearchedComboSubstance()" style="white-space: nowrap;">+ Add to Radar</button>
        </div>

        <!-- Active Substance Tray -->
        <div style="background: #090e1a; border: 1px solid var(--card-border); border-radius: var(--radius-sm); padding: 0.9rem; margin-bottom: 1.2rem;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
            <div style="font-size: 0.8rem; font-weight: 700; color: #fff;">ACTIVE SUBSTANCES ON RADAR (<span id="comboCount">0</span>):</div>
            <button class="btn-secondary" onclick="clearComboSubstances()" style="padding: 0.2rem 0.6rem; font-size: 0.72rem;">Clear All</button>
          </div>
          <div id="comboActiveChips" style="display: flex; flex-wrap: wrap; gap: 0.5rem; min-height: 36px; align-items: center;">
            <span style="font-size: 0.82rem; color: var(--text-dim);">No substances selected yet. Click any quick-add chip above or search.</span>
          </div>
        </div>

        <!-- Dynamic Visual Risk Meter & Pair Breakdown -->
        <div id="comboResultsArea"></div>
      </div>
    </div>

    <!-- TAB 3: MASTER CATALOG (560+ SUBSTANCES) -->
    <div id="tab-catalog" class="tab-content">
      <div class="card">
        <div class="card-header">
          <div class="card-title">📚 Erowid Master Archive Catalog (560+ Substances)</div>
          <span style="font-size: 0.8rem; color: var(--accent);" id="catalogHeaderStats">561 Substances Indexed</span>
        </div>

        <!-- Category Filter Pills -->
        <div style="margin-bottom: 1rem;">
          <div style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.4rem; font-weight: 600;">BROWSE TAXONOMY CATEGORIES:</div>
          <div style="display: flex; flex-wrap: wrap; gap: 0.4rem;" id="catalogCatPills">
            <span class="chip active" onclick="filterCatalogByCat('', this)">All (560+)</span>
            <span class="chip" onclick="filterCatalogByCat('psychedelic', this)">Psychedelics</span>
            <span class="chip" onclick="filterCatalogByCat('stimulant', this)">Stimulants</span>
            <span class="chip" onclick="filterCatalogByCat('depressant', this)">Depressants & Benzos</span>
            <span class="chip" onclick="filterCatalogByCat('dissociative', this)">Dissociatives</span>
            <span class="chip" onclick="filterCatalogByCat('opioid', this)">Opioids</span>
            <span class="chip" onclick="filterCatalogByCat('plant', this)">Botanicals & Plants</span>
            <span class="chip" onclick="filterCatalogByCat('synthetic', this)">Nootropics & Synthetics</span>
          </div>
        </div>

        <!-- Live Search -->
        <div style="display: flex; gap: 0.5rem; margin-bottom: 1.2rem;">
          <input type="text" id="catalogSearch" placeholder="Instant search 560+ substances by name, slug, or chemical formula..." oninput="debounceCatalogSearch()">
        </div>

        <div id="catalogList" class="grid-3"></div>
      </div>
    </div>

    <!-- TAB 4: TRIP VAULT (EXPERIENCES & LIVE READER) -->
    <div id="tab-vault" class="tab-content">
      <div class="card">
        <div class="card-header">
          <div class="card-title">📖 Experience Vault & Universal Live Reader</div>
          <span style="font-size: 0.8rem; color: var(--text-muted);">Full-text search indexed reports & retrieve any archive ID on demand</span>
        </div>

        <!-- Universal Live Reader Bar -->
        <div style="background: #090e1a; border: 1px solid var(--border-accent); border-radius: var(--radius-sm); padding: 1rem; margin-bottom: 1.4rem; display: flex; gap: 0.8rem; align-items: center; flex-wrap: wrap;">
          <span style="font-weight: 700; color: var(--accent); display: flex; align-items: center; gap: 0.3rem;">⚡ Live Archive Reader:</span>
          <span style="font-size: 0.82rem; color: var(--text-muted);">Enter any Erowid Report ID (1 - 150,000) to fetch, decompress, and read instantly:</span>
          <div style="display: flex; gap: 0.4rem; margin-left: auto;">
            <input type="number" id="quickExpId" placeholder="Exp ID (e.g. 10000)" style="width: 160px; margin-bottom: 0;">
            <button class="btn-primary" onclick="quickFetchExp()">⚡ Read Report</button>
          </div>
        </div>

        <!-- Curated Filter Pills -->
        <div style="margin-bottom: 1rem;">
          <div style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.4rem; font-weight: 600;">QUICK FILTER VAULT BY OUTCOME:</div>
          <div style="display: flex; flex-wrap: wrap; gap: 0.4rem;" id="vaultFilterPills">
            <span class="chip active" onclick="filterVaultTag('', this)">All Reports</span>
            <span class="chip" onclick="filterVaultTag('Overdose', this)">🚨 Overdose</span>
            <span class="chip" onclick="filterVaultTag('Hospital', this)">🏥 Hospital / Medical Emergency</span>
            <span class="chip" onclick="filterVaultTag('Bad Trips', this)">🌀 Bad Trips & Trainwrecks</span>
            <span class="chip" onclick="filterVaultTag('First Times', this)">✨ First Times</span>
            <span class="chip" onclick="filterVaultTag('Combinations', this)">🧬 Multi-Drug Combos</span>
          </div>
        </div>

        <div style="display: flex; gap: 0.5rem; margin-bottom: 1.2rem;">
          <input type="text" id="expSearchQ" placeholder="Keyword query in local vault (e.g. 'respiratory', 'seizure', 'panic', 'recovery')..." onkeydown="if(event.key==='Enter') loadExperiences()">
          <button class="btn-primary" onclick="loadExperiences()">Search Vault</button>
        </div>

        <div id="expResultsList"></div>
      </div>
    </div>

    <!-- TAB 5: REAGENTS & TEST STRIPS -->
    <div id="tab-reagents" class="tab-content">
      <div class="grid-2">
        <div class="card">
          <div class="card-header">
            <div class="card-title">🧪 Chemical Reagent Testing Matrix</div>
          </div>
          <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">Chemical reagents allow presumptive identification of substances and reveal dangerous adulterants (e.g. PMA, bath salts, NBOMe compounds).</p>
          <div id="testingProtocols"></div>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-title">⚠️ Fentanyl Test Strips (Life-Saving Guide)</div>
          </div>
          <div style="background: rgba(239, 68, 68, 0.15); border-left: 4px solid var(--deadly); padding: 0.8rem; border-radius: 4px; margin-bottom: 1rem;">
            <div style="font-size: 0.88rem; font-weight: 700; color: #f87171;">The "Chocolate Chip Cookie" Effect</div>
            <div style="font-size: 0.8rem; color: #fca5a5;">A lethal dose of fentanyl can fit on the tip of a pencil. It does not mix evenly in powders or pressed pills. Testing only a small scraping can produce a FALSE NEGATIVE. Dissolve the entire sample in water for testing before consumption!</div>
          </div>

          <ol style="margin-left: 1.2rem; font-size: 0.86rem; color: #cbd5e1; display: flex; flex-direction: column; gap: 0.6rem;">
            <li><strong>1. Measure Water:</strong> 10 mg of powder per 1 teaspoon (5 ml) of clean water. For MDMA or meth, use 10 ml per 10 mg to avoid false positives.</li>
            <li><strong>2. Dip the Strip:</strong> Insert test strip into liquid for 15 seconds up to the wavy line. Do not submerge past the MAX line.</li>
            <li><strong>3. Wait 2 Minutes:</strong> Lay strip flat on a clean surface.</li>
            <li><strong>4. Interpret Lines:</strong><br>
              <div style="margin-top: 0.3rem;">
                <span class="badge badge-safe" style="margin-right: 6px;">TWO LINES = NEGATIVE (No fentanyl detected)</span><br>
                <span class="badge badge-deadly" style="margin-top: 4px;">ONE LINE = POSITIVE (DANGER - Fentanyl detected! Do not consume!)</span>
              </div>
            </li>
          </ol>
        </div>
      </div>
    </div>

    <!-- TAB 6: ARCHIVE INGESTION CONSOLE -->
    <div id="tab-harvester" class="tab-content">
      <div class="card">
        <div class="card-header">
          <div class="card-title">📥 Archive Harvester & Parallel Batch Queue</div>
        </div>
        <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 1.2rem;">
          Control mass ingestion of Erowid experience reports. Harvest report IDs from category index pages and batch scrape full reports in parallel.
        </p>

        <div class="grid-2" style="margin-bottom: 1.2rem;">
          <div style="background: #090e1a; padding: 1.2rem; border-radius: var(--radius-sm); border: 1px solid var(--card-border);">
            <div style="font-size: 0.95rem; font-weight: 700; color: #fff; margin-bottom: 0.4rem;">Quick Harvest by Substance</div>
            <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.8rem;">Harvest all published report IDs for any substance across all its sub-categories.</p>
            <div style="display: flex; gap: 0.4rem;">
              <input type="text" id="harvestSubInput" placeholder="Substance slug (e.g. ketamine, dmt, 2cb, salvia)" style="margin-bottom: 0;">
              <button class="btn-primary" onclick="triggerSubHarvest()" style="white-space: nowrap;">Harvest IDs</button>
            </div>
          </div>

          <div style="background: #090e1a; padding: 1.2rem; border-radius: var(--radius-sm); border: 1px solid var(--card-border);">
            <div style="font-size: 0.95rem; font-weight: 700; color: #fff; margin-bottom: 0.4rem;">Batch Ingestion Worker Pool</div>
            <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.8rem;">Scrape harvested IDs in parallel (3 worker threads with automatic retry & decompression).</p>
            <button class="btn-primary" onclick="triggerBatchScrape()">⚡ Scrape Next 15 Queued Reports</button>
          </div>
        </div>

        <div id="scraperLog" style="font-family: monospace; font-size: 0.82rem; background: #060a12; border: 1px solid var(--card-border); padding: 1rem; border-radius: var(--radius-sm); min-height: 90px; color: #94a3b8; line-height: 1.6;">
          System ready. Ingestion queue online.
        </div>
      </div>
    </div>
  </main>

  <!-- EMERGENCY PROTOCOL MODAL (PERSISTENT) -->
  <div id="emergencyModal" class="modal">
    <div class="modal-content" style="border: 2px solid var(--deadly); box-shadow: 0 0 50px rgba(239, 68, 68, 0.4);">
      <button class="modal-close" onclick="closeEmergencyModal()">&times;</button>
      
      <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 1rem;">
        <span style="font-size: 2rem;">🚨</span>
        <div>
          <h2 style="color: var(--deadly); font-size: 1.5rem; font-weight: 800;">EMERGENCY OVERDOSE PROTOCOL</h2>
          <div style="font-size: 0.85rem; color: #fca5a5;">Immediate Life-Saving Steps & 24/7 Crisis Spotters</div>
        </div>
      </div>

      <div style="background: rgba(239, 68, 68, 0.15); border-left: 4px solid var(--deadly); padding: 1rem; border-radius: 4px; margin-bottom: 1.4rem;">
        <div style="font-weight: 700; color: #fff;">GOOD SAMARITAN LAW NOTICE:</div>
        <div style="font-size: 0.85rem; color: #cbd5e1;">Most US states and many international jurisdictions have Good Samaritan laws that legally shield you from drug possession charges when calling 911 for an overdose. DO NOT HESITATE TO CALL.</div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; margin-bottom: 1.5rem;">
        <div style="background: #090e1a; padding: 1rem; border-radius: 6px; border: 1px solid var(--card-border);">
          <div style="color: var(--accent); font-weight: 700; margin-bottom: 0.4rem;">STEP 1: CHECK & CALL 911</div>
          <div style="font-size: 0.85rem; color: #cbd5e1;">Rub knuckles firmly on center of chest (sternum rub). If unresponsive or breathing slowly (&lt;10/min), call 911 immediately. State: <em>"A person is unresponsive and not breathing."</em></div>
        </div>

        <div style="background: #090e1a; padding: 1rem; border-radius: 6px; border: 1px solid var(--card-border);">
          <div style="color: var(--accent); font-weight: 700; margin-bottom: 0.4rem;">STEP 2: ADMINISTER NARCAN</div>
          <div style="font-size: 0.85rem; color: #cbd5e1;">Peel package, place tip in one nostril, press plunger firmly. If person does not awaken within 2 to 3 minutes, give a second dose in the other nostril.</div>
        </div>

        <div style="background: #090e1a; padding: 1rem; border-radius: 6px; border: 1px solid var(--card-border);">
          <div style="color: var(--accent); font-weight: 700; margin-bottom: 0.4rem;">STEP 3: RESCUE BREATHING</div>
          <div style="font-size: 0.85rem; color: #cbd5e1;">If not breathing: tilt head back, pinch nose, deliver 1 breath every 5 seconds. If no heartbeat, begin chest compressions (100-120 bpm).</div>
        </div>

        <div style="background: #090e1a; padding: 1rem; border-radius: 6px; border: 1px solid var(--card-border);">
          <div style="color: var(--accent); font-weight: 700; margin-bottom: 0.4rem;">STEP 4: RECOVERY POSITION</div>
          <div style="font-size: 0.85rem; color: #cbd5e1;">Roll person onto their side, bend top knee forward to balance them, and rest head on arm. This prevents asphyxiation on vomit if unconscious.</div>
        </div>
      </div>

      <h3 style="color: #fff; font-size: 1.1rem; margin-bottom: 0.8rem; border-bottom: 1px solid var(--card-border); padding-bottom: 0.4rem;">Free 24/7 Crisis Helplines & Virtual Spotters</h3>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 0.8rem;">
        <div style="background: #090e1a; padding: 0.8rem 1rem; border-radius: 6px;">
          <div style="font-weight: 700; color: #fff;">📞 Never Use Alone (US)</div>
          <div style="font-size: 0.8rem; color: var(--text-muted);">Toll-free virtual buddy; stays on the line and calls EMS if you stop responding.</div>
          <a href="tel:18776961996" style="color: var(--accent); font-weight: 700; font-size: 1.05rem; text-decoration: none; display: inline-block; margin-top: 0.3rem;">1-877-696-1996</a>
        </div>

        <div style="background: #090e1a; padding: 0.8rem 1rem; border-radius: 6px;">
          <div style="font-weight: 700; color: #fff;">📞 SAMHSA Helpline (US)</div>
          <div style="font-size: 0.8rem; color: var(--text-muted);">Free, confidential 24/7 treatment referral and support.</div>
          <a href="tel:18006624357" style="color: var(--accent); font-weight: 700; font-size: 1.05rem; text-decoration: none; display: inline-block; margin-top: 0.3rem;">1-800-662-4357</a>
        </div>

        <div style="background: #090e1a; padding: 0.8rem 1rem; border-radius: 6px;">
          <div style="font-weight: 700; color: #fff;">💬 Crisis Text Line</div>
          <div style="font-size: 0.8rem; color: var(--text-muted);">24/7 free emotional crisis support via text message.</div>
          <div style="color: var(--safe); font-weight: 700; font-size: 1.05rem; margin-top: 0.3rem;">Text HOME to 741741</div>
        </div>

        <div style="background: #090e1a; padding: 0.8rem 1rem; border-radius: 6px;">
          <div style="font-weight: 700; color: #fff;">🇬🇧 FRANK Helpline (UK)</div>
          <div style="font-size: 0.8rem; color: var(--text-muted);">Confidential drug info and harm reduction advice.</div>
          <a href="tel:03001236600" style="color: var(--accent); font-weight: 700; font-size: 1.05rem; text-decoration: none; display: inline-block; margin-top: 0.3rem;">0300 123 6600</a>
        </div>
      </div>
    </div>
  </div>

  <!-- EXPERIENCE REPORT READER MODAL -->
  <div id="reportModal" class="modal">
    <div class="modal-content">
      <button class="modal-close" onclick="closeModal()">&times;</button>
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
        <h2 id="modalTitle" style="color: var(--accent); font-size: 1.4rem;"></h2>
      </div>
      <div id="modalMeta" class="exp-meta" style="margin-bottom: 0.8rem;"></div>
      <div id="modalFlags" style="margin-bottom: 0.8rem;"></div>
      <div id="modalDoses" style="margin-bottom: 1rem;"></div>
      <div style="border-top: 1px solid var(--card-border); padding-top: 1rem;">
        <h4 style="color: #fff; margin-bottom: 0.6rem; font-size: 0.95rem;">Experience Narrative:</h4>
        <div id="modalBody" style="white-space: pre-wrap; color: #cbd5e1; font-size: 0.94rem; line-height: 1.7; max-height: 55vh; overflow-y: auto; padding-right: 0.5rem;"></div>
      </div>
    </div>
  </div>

  <script>
    let activeNav = 'dossiers';
    let substancesData = [];
    let catalogData = [];
    let allSubstanceNames = [];
    let activeComboList = [];
    let catalogDebounceTimer = null;

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

    // Keyboard shortcuts (Cmd+E / Escape)
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeEmergencyModal();
        closeModal();
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'e') {
        e.preventDefault();
        openEmergencyModal();
      }
    });

    // --- TAB 1: DOSSIERS & DOSAGE SAFETY LADDER ---
    async function loadSubstances() {
      const res = await fetch('/api/substances');
      substancesData = await res.json();
      renderSubstances(substancesData);
      runDoseCalculation();
    }

    function renderSubstances(list) {
      const container = document.getElementById('substancesList');
      container.innerHTML = list.map(sub => `
        <div class="card" style="margin-bottom: 0; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.4rem;">
              <h3 style="color: #fff; font-size: 1.05rem;">${sub.name}</h3>
              <span class="badge badge-safe">${sub.category}</span>
            </div>
            <p style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.5rem;">Aliases: ${(sub.common_names || []).join(', ') || 'N/A'}</p>
            <p style="font-size: 0.83rem; color: #cbd5e1; margin-bottom: 0.8rem; line-height: 1.5;">${sub.harm_summary}</p>
          </div>
          <div>
            ${sub.dosages && sub.dosages.length > 0 ? `
              <div style="background: #090e1a; padding: 0.6rem; border-radius: 4px; font-size: 0.75rem; margin-bottom: 0.6rem;">
                <strong>${sub.dosages[0].route} Dosage:</strong><br>
                Thresh: ${sub.dosages[0].threshold || 'N/A'} | Common: ${sub.dosages[0].common || 'N/A'} | Heavy: ${sub.dosages[0].heavy || 'N/A'}
              </div>
            ` : ''}
            <button class="btn-secondary" style="width: 100%;" onclick="setDoseSubstance('${sub.name}', ${sub.dosages && sub.dosages[0] ? (parseFloat(sub.dosages[0].common) || 100) : 100}, 'mg', '${sub.dosages && sub.dosages[0] ? sub.dosages[0].route : 'Oral'}')">Assess in Dose Ladder</button>
          </div>
        </div>
      `).join('');
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

    function setDoseSubstance(name, amt, unit, route) {
      document.getElementById('doseSubInput').value = name;
      document.getElementById('doseAmtInput').value = amt;
      document.getElementById('doseUnitSelect').value = unit;
      document.getElementById('doseRouteSelect').value = route;
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

      // Calculate kg
      const weightKg = weightUnit === 'lbs' ? weight * 0.453592 : weight;
      const weightMdmaGuide = Math.round(weightKg * 1.5);
      document.getElementById('weightDoseCalcOutput').innerText = `Guideline: ~${weightMdmaGuide} mg (for ${Math.round(weightKg)}kg)`;

      if (!sub || !amt) return;

      try {
        const res = await fetch(`/api/check-dose?substance=${encodeURIComponent(sub)}&amount=${encodeURIComponent(amt)}&unit=${encodeURIComponent(unit)}&route=${encodeURIComponent(route)}`);
        const data = await res.json();
        renderDoseEvaluation(data, parseFloat(amt));
      } catch (err) {
        console.error(err);
      }
    }

    function renderDoseEvaluation(data, amt) {
      const badge = document.getElementById('doseStatusBadge');
      const pointer = document.getElementById('doseLadderPointer');
      const grid = document.getElementById('doseDetailsGrid');

      if (!data.found) {
        badge.className = 'badge badge-caution';
        badge.innerText = 'NOT FOUND IN CLINICAL DATABASE';
        pointer.style.left = '50%';
        grid.innerHTML = `<div style="grid-column: 1 / -1; color: var(--text-muted);">${data.message || 'No dosage benchmarks available.'}</div>`;
        return;
      }

      const status = data.status || 'COMMON';
      let leftPct = 50;
      let badgeClass = 'badge-safe';

      if (status.includes('HEAVY') || status.includes('OVERDOSE') || status.includes('DANGEROUS')) {
        badgeClass = 'badge-deadly';
        leftPct = 90;
      } else if (status.includes('STRONG')) {
        badgeClass = 'badge-dangerous';
        leftPct = 75;
      } else if (status.includes('COMMON')) {
        badgeClass = 'badge-safe';
        leftPct = 50;
      } else if (status.includes('LIGHT')) {
        badgeClass = 'badge-caution';
        leftPct = 25;
      } else {
        badgeClass = 'badge-cat';
        leftPct = 8;
      }

      badge.className = `badge ${badgeClass}`;
      badge.innerText = status;
      pointer.style.left = `${leftPct}%`;

      // Build bracket summary
      grid.innerHTML = `
        <div style="background: #111827; padding: 0.8rem; border-radius: 4px; font-size: 0.8rem;">
          <div style="color: var(--accent); font-weight: 700; margin-bottom: 0.3rem;">THRESHOLD / LIGHT</div>
          <div>Threshold: <strong>${data.threshold || 'N/A'}</strong></div>
          <div>Light: <strong>${data.light || 'N/A'}</strong></div>
        </div>
        <div style="background: #111827; padding: 0.8rem; border-radius: 4px; font-size: 0.8rem;">
          <div style="color: var(--safe); font-weight: 700; margin-bottom: 0.3rem;">COMMON RANGE</div>
          <div>Common: <strong>${data.common || 'N/A'}</strong></div>
          <div>Strong: <strong>${data.strong || 'N/A'}</strong></div>
        </div>
        <div style="background: #111827; padding: 0.8rem; border-radius: 4px; font-size: 0.8rem;">
          <div style="color: var(--deadly); font-weight: 700; margin-bottom: 0.3rem;">HEAVY BOUNDARY</div>
          <div>Heavy / Toxic: <strong>${data.heavy || 'N/A'}</strong></div>
          <div style="font-size: 0.72rem; color: var(--text-muted);">${data.notes || ''}</div>
        </div>
        ${(data.durations && data.durations.length > 0) ? `
          <div style="background: #111827; padding: 0.8rem; border-radius: 4px; font-size: 0.8rem;">
            <div style="color: #cbd5e1; font-weight: 700; margin-bottom: 0.3rem;">TIMELINE (${data.durations[0].route})</div>
            <div>Onset: <strong>${data.durations[0].onset || 'N/A'}</strong></div>
            <div>Peak: <strong>${data.durations[0].peak || 'N/A'}</strong></div>
            <div>Duration: <strong>${data.durations[0].total_duration || 'N/A'}</strong></div>
          </div>
        ` : ''}
      `;
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
      }
    }

    function updateComboUI() {
      document.getElementById('comboCount').innerText = activeComboList.length;
      const chipsTray = document.getElementById('comboActiveChips');
      
      if (activeComboList.length === 0) {
        chipsTray.innerHTML = `<span style="font-size: 0.82rem; color: var(--text-dim);">No substances selected yet. Click any quick-add chip above or search.</span>`;
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
          <div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.9rem;">
            Please select at least 2 substances to evaluate combination risks.
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
      
      let gaugeClass = 'gauge-safe';
      let badgeClass = 'badge-safe';
      let titleColor = 'var(--safe)';
      let boxBg = 'rgba(16, 185, 129, 0.08)';
      let boxBorder = 'var(--safe)';

      if (risk === 'DEADLY') {
        gaugeClass = 'gauge-deadly';
        badgeClass = 'badge-deadly';
        titleColor = 'var(--deadly)';
        boxBg = 'rgba(239, 68, 68, 0.12)';
        boxBorder = 'var(--deadly)';
      } else if (risk === 'DANGEROUS') {
        gaugeClass = 'gauge-dangerous';
        badgeClass = 'badge-dangerous';
        titleColor = 'var(--dangerous)';
        boxBg = 'rgba(249, 115, 22, 0.12)';
        boxBorder = 'var(--dangerous)';
      } else if (risk === 'CAUTION') {
        gaugeClass = 'gauge-caution';
        badgeClass = 'badge-caution';
        titleColor = 'var(--caution)';
        boxBg = 'rgba(245, 158, 11, 0.12)';
        boxBorder = 'var(--caution)';
      }

      container.innerHTML = `
        <div class="risk-gauge-box" style="background: ${boxBg}; border: 1px solid ${boxBorder};">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
              <div style="font-size: 0.75rem; color: var(--text-muted); font-weight: 700;">SYNERGISTIC RISK LEVEL:</div>
              <h2 style="color: ${titleColor}; font-size: 1.4rem; font-weight: 800;">${risk}</h2>
            </div>
            <span class="badge ${badgeClass}" style="font-size: 0.85rem; padding: 0.4rem 0.8rem;">${risk}</span>
          </div>

          <div class="risk-gauge-bar">
            <div class="gauge-segment gauge-safe ${risk === 'LOW_OR_UNKNOWN' ? 'active' : ''}"></div>
            <div class="gauge-segment gauge-caution ${risk === 'CAUTION' ? 'active' : ''}"></div>
            <div class="gauge-segment gauge-dangerous ${risk === 'DANGEROUS' ? 'active' : ''}"></div>
            <div class="gauge-segment gauge-deadly ${risk === 'DEADLY' ? 'active' : ''}"></div>
          </div>
        </div>

        <h3 style="color: #fff; font-size: 1.05rem; margin: 1.2rem 0 0.8rem 0;">Pairwise Pharmacological Breakdown:</h3>
        ${(data.interactions || []).length === 0 ? `
          <div style="background: #090e1a; padding: 1.2rem; border-radius: var(--radius-sm); border: 1px solid var(--card-border); color: #cbd5e1;">
            ✓ No critical physiological contraindications identified in the matrix for this specific combination.<br>
            <span style="font-size: 0.8rem; color: var(--text-muted);">Note: Subjective intensity or psychological effects may still be potentiated. Always start low and go slow.</span>
          </div>
        ` : ''}

        ${(data.interactions || []).map(it => `
          <div style="background: #090e1a; border-left: 4px solid ${it.risk_level === 'DEADLY' ? 'var(--deadly)' : (it.risk_level === 'DANGEROUS' ? 'var(--dangerous)' : 'var(--caution)')}; border-radius: 0 var(--radius-sm) var(--radius-sm) 0; padding: 1rem 1.2rem; margin-bottom: 0.8rem; border-top: 1px solid var(--card-border); border-right: 1px solid var(--card-border); border-bottom: 1px solid var(--card-border);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
              <h4 style="color: #fff; font-size: 1.1rem;">⚡ ${it.substance_a.toUpperCase()} + ${it.substance_b.toUpperCase()}</h4>
              <span class="badge ${it.risk_level === 'DEADLY' ? 'badge-deadly' : (it.risk_level === 'DANGEROUS' ? 'badge-dangerous' : 'badge-caution')}">${it.risk_level}</span>
            </div>
            <p style="font-size: 0.88rem; color: #fca5a5; margin-bottom: 0.4rem; line-height: 1.5;"><strong>Mechanism:</strong> ${it.mechanism}</p>
            <p style="font-size: 0.85rem; color: #cbd5e1; line-height: 1.5;"><strong>Harm Reduction Action:</strong> ${it.harm_reduction_advice}</p>
          </div>
        `).join('')}
      `;
    }

    // --- TAB 3: MASTER CATALOG (560+ SUBSTANCES) ---
    async function loadCatalog(query = '', category = '') {
      let url = `/api/catalog?limit=60&q=${encodeURIComponent(query)}`;
      if (category) url += `&category=${encodeURIComponent(category)}`;
      const res = await fetch(url);
      catalogData = await res.json();
      renderCatalog(catalogData);

      const statsRes = await fetch('/api/catalog-stats');
      const stats = await statsRes.json();
      document.getElementById('catalogHeaderStats').innerText = `${stats.total_catalog_substances} Substances Indexed • ${stats.total_indexed_reports} Harvested IDs`;
    }

    function renderCatalog(list) {
      const container = document.getElementById('catalogList');
      if (list.length === 0) {
        container.innerHTML = '<div style="grid-column: 1 / -1; color: var(--text-muted); padding: 2rem; text-align: center;">No catalog entries found matching search query.</div>';
        return;
      }
      container.innerHTML = list.map(item => {
        const catKeys = Object.keys(item.categories || {});
        return `
          <div class="card" style="margin-bottom: 0; display: flex; flex-direction: column; justify-content: space-between;">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.3rem;">
                <h3 style="color: #fff; font-size: 1.05rem;">${item.name}</h3>
                <span class="badge" style="background: #090e1a; color: var(--accent); border: 1px solid var(--card-border);">${item.slug}</span>
              </div>
              <p style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.4rem;">${item.description || 'Erowid Taxonomy Entry'}</p>
              <div style="margin: 0.4rem 0;">
                ${catKeys.slice(0, 3).map(c => `<span class="badge badge-cat">${c}</span>`).join('')}
                ${catKeys.length > 3 ? `<span class="badge badge-cat">+${catKeys.length - 3}</span>` : ''}
              </div>
            </div>
            <div style="margin-top: 0.8rem; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--card-border); padding-top: 0.6rem;">
              <span style="font-size: 0.75rem; color: var(--accent); font-weight: 600;">${item.total_reports > 0 ? item.total_reports + ' reports' : ''}</span>
              <div style="display: flex; gap: 0.3rem;">
                <button class="btn-secondary" onclick="addComboSubstance('${item.name}'); switchNav('radar');">+ Radar</button>
                <button class="btn-secondary" onclick="harvestSubFromCatalog('${item.slug}')">Harvest</button>
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

    function debounceCatalogSearch() {
      clearTimeout(catalogDebounceTimer);
      catalogDebounceTimer = setTimeout(() => {
        const q = document.getElementById('catalogSearch').value;
        const activeChip = document.querySelector('#catalogCatPills .chip.active');
        const cat = activeChip ? activeChip.innerText.toLowerCase().replace(/[^a-z]/g, '') : '';
        loadCatalog(q, cat === 'all560' ? '' : cat);
      }, 250);
    }

    function harvestSubFromCatalog(slug) {
      switchNav('harvester');
      document.getElementById('harvestSubInput').value = slug;
      triggerSubHarvest();
    }

    // --- TAB 4: TRIP VAULT ---
    let currentVaultTag = '';
    async function loadExperiences() {
      const q = document.getElementById('expSearchQ').value;
      let url = '/api/experiences?limit=25';
      if (q) url += '&q=' + encodeURIComponent(q);
      if (currentVaultTag) url += '&tag=' + encodeURIComponent(currentVaultTag);

      const res = await fetch(url);
      const reports = await res.json();
      const container = document.getElementById('expResultsList');

      if (reports.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); padding: 2rem; text-align: center;">No experience reports found matching query in local database.</div>';
        return;
      }

      container.innerHTML = reports.map(r => `
        <div class="exp-item" onclick="openReportModal(${r.id})">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <h4 style="color: #fff; font-size: 1.05rem;">Exp #${r.id}: ${r.title}</h4>
            <span style="font-size: 0.78rem; color: var(--text-muted);">${r.exp_year || ''}</span>
          </div>
          <div class="exp-meta">
            Substance: <strong>${r.substance_summary}</strong> | Author: ${r.author} | Weight: ${r.body_weight || 'N/A'}
          </div>
          <div style="margin-bottom: 0.4rem;">
            ${(r.harm_flags || []).map(f => `<span class="badge badge-deadly" style="margin-right: 4px;">${f}</span>`).join('')}
          </div>
          <div class="exp-snippet">${r.snippet}</div>
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
      document.getElementById('modalBody').innerText = "Connecting to Erowid Wayback Archive. Please wait...";
      document.getElementById('reportModal').classList.add('active');

      try {
        const res = await fetch('/api/experience?id=' + id);
        const exp = await res.json();
        if (exp.error) {
          document.getElementById('modalTitle').innerText = `Exp #${id}: Error`;
          document.getElementById('modalBody').innerText = exp.error;
          return;
        }

        document.getElementById('modalTitle').innerText = `Exp #${exp.id}: ${exp.title}`;
        document.getElementById('modalMeta').innerText = `Substance: ${exp.substance_summary} | Author: ${exp.author} | Year: ${exp.exp_year || 'N/A'} | Weight: ${exp.body_weight || 'N/A'} | Words: ${exp.word_count || 'N/A'}`;
        
        document.getElementById('modalFlags').innerHTML = (exp.harm_flags || []).map(f => 
          `<span class="badge badge-deadly" style="margin-right: 6px;">${f}</span>`
        ).join('');

        document.getElementById('modalDoses').innerHTML = (exp.doses || []).length > 0 ? `
          <div style="background: #090e1a; padding: 0.8rem; border-radius: 4px; font-size: 0.82rem; border: 1px solid var(--card-border);">
            <strong style="color: var(--accent);">Reported Dosages:</strong><br>
            ${exp.doses.map(d => `• ${d.substance}: ${d.amount || ''} ${d.unit || ''} (${d.method || 'Oral'})`).join('<br>')}
          </div>
        ` : '';

        document.getElementById('modalBody').innerText = exp.narrative;
      } catch (err) {
        document.getElementById('modalTitle').innerText = `Exp #${id}: Retrieval Failed`;
        document.getElementById('modalBody').innerText = "Network or parsing error: " + err.message;
      }
    }

    // --- TAB 5: REAGENTS & HARVESTER ---
    async function loadTestingProtocols() {
      const res = await fetch('/api/testing-guide');
      const data = await res.json();
      const div = document.getElementById('testingProtocols');
      div.innerHTML = `
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

    async function triggerSubHarvest() {
      const sub = document.getElementById('harvestSubInput').value.trim();
      if (!sub) return;
      const log = document.getElementById('scraperLog');
      log.innerHTML = `<span style="color: var(--accent);">Harvesting report IDs for '${sub}' from category index pages...</span>`;

      const res = await fetch('/api/harvest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ substance: sub })
      });
      const data = await res.json();
      if (data.success) {
        log.innerHTML = `<span style="color: var(--safe);">✓ Harvested ${data.count} report IDs for '${sub}' into the indexing queue!</span>`;
      } else {
        log.innerHTML = `<span style="color: var(--deadly);">✗ Harvesting failed: ${data.error}</span>`;
      }
    }

    async function triggerBatchScrape() {
      const log = document.getElementById('scraperLog');
      log.innerHTML = `<span style="color: var(--accent);">⚡ Worker pool starting: downloading up to 15 queued reports in parallel...</span>`;

      const res = await fetch('/api/batch-scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 15, workers: 3 })
      });
      const data = await res.json();
      log.innerHTML = `<span style="color: var(--safe);">✓ Batch completed: ${data.success} saved to SQLite out of ${data.total} attempted!</span>`;
      loadExperiences();
    }

    // Initialize on page load
    loadSubstances();
    loadTestingProtocols();
  </script>
</body>
</html>
"""
