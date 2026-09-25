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
            limit = int(query.get("limit", [50])[0])
            offset = int(query.get("offset", [0])[0])
            entries = self.db.search_catalog(query=q, limit=limit, offset=offset)
            self._set_headers(200)
            self.wfile.write(json.dumps(entries).encode("utf-8"))
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
  <title>Erowid SafeDB - Systematic Harm Reduction & Master Archive</title>
  <style>
    :root {
      --bg: #0f172a;
      --card-bg: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --accent: #38bdf8;
      --accent-hover: #0284c7;
      --deadly: #ef4444;
      --dangerous: #f97316;
      --caution: #eab308;
      --safe: #22c55e;
      --radius: 8px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background-color: var(--bg); color: var(--text); line-height: 1.6; }
    header { background: #0b1120; border-bottom: 1px solid var(--card-border); padding: 1.2rem 2rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; }
    header h1 { font-size: 1.4rem; color: var(--accent); display: flex; align-items: center; gap: 0.5rem; }
    header .subtitle { font-size: 0.85rem; color: var(--text-muted); }
    nav { display: flex; gap: 0.5rem; flex-wrap: wrap; }
    nav button { background: transparent; border: 1px solid var(--card-border); color: var(--text-muted); padding: 0.5rem 1rem; border-radius: var(--radius); cursor: pointer; font-weight: 500; transition: all 0.2s; }
    nav button.active, nav button:hover { background: var(--card-bg); color: var(--accent); border-color: var(--accent); }
    main { max-width: 1250px; margin: 2rem auto; padding: 0 1.5rem; }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius); padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { font-size: 1.3rem; margin-bottom: 0.75rem; color: #fff; border-bottom: 1px solid var(--card-border); padding-bottom: 0.5rem; }
    .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem; }
    .grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }
    
    /* Badges */
    .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }
    .badge-deadly { background: rgba(239, 68, 68, 0.2); color: var(--deadly); border: 1px solid var(--deadly); }
    .badge-dangerous { background: rgba(249, 115, 22, 0.2); color: var(--dangerous); border: 1px solid var(--dangerous); }
    .badge-caution { background: rgba(234, 179, 8, 0.2); color: var(--caution); border: 1px solid var(--caution); }
    .badge-safe { background: rgba(34, 197, 94, 0.2); color: var(--safe); border: 1px solid var(--safe); }
    .badge-cat { background: #334155; color: #94a3b8; font-size: 0.7rem; font-weight: 500; margin: 2px; }
    
    /* Inputs & Buttons */
    input, select, textarea { background: #0f172a; border: 1px solid var(--card-border); color: #fff; padding: 0.6rem 0.8rem; border-radius: var(--radius); width: 100%; margin-bottom: 0.8rem; }
    input:focus, select:focus { outline: none; border-color: var(--accent); }
    button.btn-primary { background: var(--accent); color: #0f172a; font-weight: bold; border: none; padding: 0.6rem 1.2rem; border-radius: var(--radius); cursor: pointer; transition: background 0.2s; }
    button.btn-primary:hover { background: var(--accent-hover); }
    button.btn-secondary { background: #334155; color: #fff; border: none; padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
    button.btn-secondary:hover { background: #475569; }
    
    /* Dose Table */
    table.data-table { width: 100%; border-collapse: collapse; margin-top: 0.8rem; font-size: 0.9rem; }
    table.data-table th, table.data-table td { padding: 0.6rem; text-align: left; border-bottom: 1px solid var(--card-border); }
    table.data-table th { background: #0f172a; color: var(--accent); }
    
    /* Banners */
    .alert-banner { background: rgba(239, 68, 68, 0.15); border-left: 4px solid var(--deadly); padding: 1rem; border-radius: 4px; margin-bottom: 1.5rem; }
    .alert-banner h3 { color: var(--deadly); margin-bottom: 0.3rem; }
    
    .exp-item { border-left: 3px solid var(--accent); padding: 1rem; margin-bottom: 1rem; background: #162032; border-radius: 0 6px 6px 0; cursor: pointer; transition: background 0.2s; }
    .exp-item:hover { background: #1a273e; }
    .exp-item h4 { color: #fff; font-size: 1.1rem; }
    .exp-meta { font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem; }
    .exp-snippet { font-size: 0.88rem; color: #cbd5e1; }
    
    .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 1000; justify-content: center; align-items: center; }
    .modal.active { display: flex; }
    .modal-content { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius); max-width: 850px; width: 90%; max-height: 85vh; overflow-y: auto; padding: 2rem; position: relative; }
    .close-btn { position: absolute; top: 1rem; right: 1rem; font-size: 1.5rem; cursor: pointer; color: var(--text-muted); }
  </style>
</head>
<body>

  <header>
    <div>
      <h1>🛡️ Erowid SafeDB</h1>
      <div class="subtitle">Evidence-based Harm Reduction, Clinical Drug Interactions & Universal Erowid Archive</div>
    </div>
    <nav>
      <button class="active" onclick="showTab('substances')">Clinical Dossiers</button>
      <button onclick="showTab('catalog')">Master Catalog (560+)</button>
      <button onclick="showTab('interactions')">Interaction Checker</button>
      <button onclick="showTab('experiences')">Experience Vault</button>
      <button onclick="showTab('emergency')">Emergency & Testing</button>
      <button onclick="showTab('scraper')">Archive Harvester</button>
    </nav>
  </header>

  <main>
    <!-- TAB 1: CLINICAL SUBSTANCES -->
    <div id="tab-substances" class="tab-content active">
      <div class="card">
        <h2>Curated Clinical Monographs & Dosage Boundaries</h2>
        <input type="text" id="subSearch" placeholder="Filter clinical dossiers (e.g. MDMA, Psilocybin, Ketamine, Xanax, LSD)..." onkeyup="filterSubstances()">
        <div id="substancesList" class="grid-3" style="margin-top: 1rem;"></div>
      </div>
    </div>

    <!-- TAB 2: MASTER CATALOG (560+ SUBSTANCES) -->
    <div id="tab-catalog" class="tab-content">
      <div class="card">
        <h2>Erowid Master Archive Catalog (560+ Substances)</h2>
        <p style="color: var(--text-muted); margin-bottom: 1rem;">Complete indexed taxonomy of psychoactive substances on Erowid. Search any substance, explore its categories, and trigger automatic report harvesting.</p>
        <div style="display: flex; gap: 0.5rem; margin-bottom: 1rem;">
          <input type="text" id="catalogSearch" placeholder="Search 560+ substances (e.g. DMT, 2C-B, Salvia, GHB, Fentanyl, Mescaline, Kratom)..." onkeyup="filterCatalog()">
        </div>
        <div id="catalogStatsBanner" style="font-size: 0.85rem; color: var(--accent); margin-bottom: 1rem;"></div>
        <div id="catalogList" class="grid-3"></div>
      </div>
    </div>

    <!-- TAB 3: INTERACTION CHECKER -->
    <div id="tab-interactions" class="tab-content">
      <div class="card">
        <h2>Multi-Drug Combo & Interaction Checker</h2>
        <p style="color: var(--text-muted); margin-bottom: 1rem;">Enter 2 or more substances to evaluate lethal or dangerous synergistic risks (e.g. respiratory arrest, serotonin syndrome, cardiac toxicity).</p>
        <div style="display: flex; gap: 0.5rem; margin-bottom: 1rem;">
          <input type="text" id="comboInput" placeholder="Enter comma-separated substances (e.g., MDMA, Tramadol or Alcohol, Xanax, Oxycodone)">
          <button class="btn-primary" onclick="checkCombination()" style="white-space: nowrap;">Check Risk</button>
        </div>
        <div id="comboResults"></div>
      </div>
    </div>

    <!-- TAB 4: EXPERIENCE VAULT -->
    <div id="tab-experiences" class="tab-content">
      <div class="card">
        <h2>Erowid Experience Reports Vault (Full-Text Search & Live Reader)</h2>
        
        <!-- Quick Fetch Box -->
        <div style="background: #111e33; padding: 1rem; border-radius: 6px; margin-bottom: 1.2rem; display: flex; gap: 0.8rem; align-items: center; flex-wrap: wrap;">
          <span style="font-weight: 600; color: var(--accent);">⚡ Universal Live Reader:</span>
          <span style="font-size: 0.85rem; color: var(--text-muted);">Enter ANY Erowid Report ID (1 - 150,000) to fetch live from archive and read:</span>
          <input type="number" id="quickExpId" placeholder="Exp ID (e.g. 10000)" style="width: 160px; margin-bottom: 0;">
          <button class="btn-primary" onclick="quickFetchExp()">Fetch & Read</button>
        </div>

        <div class="grid-2">
          <input type="text" id="expSearchQ" placeholder="Keyword query in local vault (e.g. 'seizure', 'panic', 'overdose', 'recovery')...">
          <select id="expFilterTag" onchange="loadExperiences()">
            <option value="">All Tags / Outcomes</option>
            <option value="Overdose">Overdose</option>
            <option value="Hospital">Hospital / Medical Emergency</option>
            <option value="Bad Trips">Bad Trips</option>
            <option value="First Times">First Times</option>
          </select>
        </div>
        <button class="btn-primary" onclick="loadExperiences()">Search Local Vault</button>
        <div id="expResultsList" style="margin-top: 1.5rem;"></div>
      </div>
    </div>

    <!-- TAB 5: EMERGENCY & TESTING PROTOCOLS -->
    <div id="tab-emergency" class="tab-content">
      <div class="alert-banner">
        <h3>🚨 Overdose Emergency? Call 911 Immediately</h3>
        <p>Most jurisdictions have Good Samaritan laws that shield callers from drug possession charges. If opioids are suspected, administer Naloxone (Narcan) immediately.</p>
      </div>

      <div class="grid-2">
        <div class="card">
          <h2>4-Step Overdose Life-Saving Protocol</h2>
          <ol style="margin-left: 1.2rem; color: #cbd5e1; display: flex; flex-direction: column; gap: 0.8rem;">
            <li><strong>1. Call 911 / 999:</strong> State clearly: <em>"A person is unresponsive and not breathing."</em></li>
            <li><strong>2. Administer Naloxone (Narcan):</strong> Spray into one nostril. If no response after 2-3 minutes, give a second dose in the other nostril.</li>
            <li><strong>3. Rescue Breathing / CPR:</strong> If not breathing, tilt head back, pinch nose, and deliver 1 breath every 5 seconds. If no pulse, start chest compressions.</li>
            <li><strong>4. Recovery Position:</strong> Roll person onto their side with knee bent to prevent choking on vomit if unconscious.</li>
          </ol>
        </div>

        <div class="card">
          <h2>Free 24/7 Helplines & Virtual Spotters</h2>
          <ul style="list-style: none; display: flex; flex-direction: column; gap: 0.8rem;">
            <li>📞 <strong>SAMHSA National Helpline:</strong> <a href="tel:18006624357" style="color: var(--accent);">1-800-662-4357</a> (Free, confidential 24/7 US treatment referral)</li>
            <li>📞 <strong>Never Use Alone:</strong> <a href="tel:18776961996" style="color: var(--accent);">1-877-696-1996</a> (US virtual buddy; calls EMS if you go silent)</li>
            <li>💬 <strong>Crisis Text Line:</strong> Text <strong>HOME</strong> to <strong>741741</strong></li>
            <li>🇬🇧 <strong>FRANK (UK):</strong> <a href="tel:03001236600" style="color: var(--accent);">0300 123 6600</a></li>
          </ul>
        </div>
      </div>

      <div class="card">
        <h2>Chemical Reagent Testing & Fentanyl Strips</h2>
        <div id="testingProtocols"></div>
      </div>
    </div>

    <!-- TAB 6: SCRAPER CONSOLE -->
    <div id="tab-scraper" class="tab-content">
      <div class="card">
        <h2>Archive Harvester & Batch Scraper Console</h2>
        <p style="color: var(--text-muted); margin-bottom: 1rem;">
          Control mass ingestion of Erowid experience reports. Harvest report IDs into the indexing queue or batch scrape with multi-threading and rate limits.
        </p>

        <div class="grid-2" style="margin-bottom: 1.5rem;">
          <div style="background: #111e33; padding: 1rem; border-radius: 6px;">
            <h3>Quick Harvest by Substance</h3>
            <p style="font-size: 0.85rem; color: var(--text-muted); margin: 0.4rem 0 0.8rem 0;">Harvest all available report IDs for any substance across all its Erowid categories.</p>
            <div style="display: flex; gap: 0.5rem;">
              <input type="text" id="harvestSubInput" placeholder="Substance slug or name (e.g. ketamine, dmt, 2cb)" style="margin-bottom: 0;">
              <button class="btn-primary" onclick="triggerSubHarvest()" style="white-space: nowrap;">Harvest IDs</button>
            </div>
          </div>

          <div style="background: #111e33; padding: 1rem; border-radius: 6px;">
            <h3>Batch Scrape Queue</h3>
            <p style="font-size: 0.85rem; color: var(--text-muted); margin: 0.4rem 0 0.8rem 0;">Download harvested report IDs in parallel (3 worker threads with respectful delays).</p>
            <button class="btn-primary" onclick="triggerBatchScrape()">Scrape Next 15 Queue Reports</button>
          </div>
        </div>

        <div id="scraperLog" style="font-family: monospace; font-size: 0.85rem; background: #0b1120; padding: 1rem; border-radius: 6px; min-height: 80px; color: #94a3b8;">
          System ready. Select a harvest or scrape action above.
        </div>
      </div>
    </div>
  </main>

  <!-- MODAL FOR DETAILED REPORT -->
  <div id="reportModal" class="modal">
    <div class="modal-content">
      <span class="close-btn" onclick="closeModal()">&times;</span>
      <h2 id="modalTitle" style="color: var(--accent);"></h2>
      <div id="modalMeta" class="exp-meta" style="margin: 0.5rem 0 1rem 0;"></div>
      <div id="modalFlags" style="margin-bottom: 1rem;"></div>
      <div id="modalDoses" style="margin-bottom: 1rem;"></div>
      <div id="modalBody" style="white-space: pre-wrap; color: #cbd5e1; font-size: 0.95rem; line-height: 1.7;"></div>
    </div>
  </div>

  <script>
    let substancesData = [];
    let catalogData = [];

    function showTab(tabName) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('nav button').forEach(el => el.classList.remove('active'));
      document.getElementById('tab-' + tabName).classList.add('active');
      event.target.classList.add('active');
      if (tabName === 'experiences') loadExperiences();
      if (tabName === 'catalog') loadCatalog();
    }

    async function loadSubstances() {
      const res = await fetch('/api/substances');
      substancesData = await res.json();
      renderSubstances(substancesData);
    }

    function renderSubstances(list) {
      const container = document.getElementById('substancesList');
      container.innerHTML = list.map(sub => `
        <div class="card" style="margin-bottom: 0;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <h3 style="color: #fff; font-size: 1.1rem;">${sub.name}</h3>
            <span class="badge badge-safe">${sub.category}</span>
          </div>
          <p style="font-size: 0.8rem; color: var(--text-muted); margin: 0.4rem 0;">Common: ${sub.common_names.join(', ')}</p>
          <p style="font-size: 0.85rem; color: #cbd5e1; margin-bottom: 0.8rem;">${sub.harm_summary}</p>
          ${sub.dosages.length > 0 ? `
            <div style="background: #0f172a; padding: 0.5rem; border-radius: 4px; font-size: 0.78rem;">
              <strong>${sub.dosages[0].route} Dose:</strong><br>
              Threshold: ${sub.dosages[0].threshold || 'N/A'} | Common: ${sub.dosages[0].common || 'N/A'} | Heavy: ${sub.dosages[0].heavy || 'N/A'}
            </div>
          ` : ''}
        </div>
      `).join('');
    }

    function filterSubstances() {
      const q = document.getElementById('subSearch').value.toLowerCase();
      const filtered = substancesData.filter(s => 
        s.name.toLowerCase().includes(q) || 
        s.category.toLowerCase().includes(q) ||
        s.common_names.some(c => c.toLowerCase().includes(q))
      );
      renderSubstances(filtered);
    }

    async function loadCatalog() {
      const res = await fetch('/api/catalog?limit=60');
      catalogData = await res.json();
      const statsRes = await fetch('/api/catalog-stats');
      const stats = await statsRes.json();
      document.getElementById('catalogStatsBanner').innerHTML = `
        ✓ Indexed <strong>${stats.total_catalog_substances}</strong> total substances | 
        <strong>${stats.total_indexed_reports}</strong> harvested report IDs in queue (${stats.total_scraped_reports} fully scraped locally)
      `;
      renderCatalog(catalogData);
    }

    function renderCatalog(list) {
      const container = document.getElementById('catalogList');
      if (list.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted);">No catalog entries match search.</p>';
        return;
      }
      container.innerHTML = list.map(item => {
        const catKeys = Object.keys(item.categories || {});
        return `
          <div class="card" style="margin-bottom: 0; display: flex; flex-direction: column; justify-content: space-between;">
            <div>
              <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <h3 style="color: #fff; font-size: 1.05rem;">${item.name}</h3>
                <span class="badge" style="background: #0f172a; color: var(--accent);">${item.slug}</span>
              </div>
              <p style="font-size: 0.8rem; color: var(--text-muted); margin: 0.4rem 0;">${item.description || 'Erowid Vault Entry'}</p>
              <div style="margin: 0.5rem 0;">
                ${catKeys.slice(0, 4).map(c => `<span class="badge badge-cat">${c}</span>`).join('')}
                ${catKeys.length > 4 ? `<span class="badge badge-cat">+${catKeys.length - 4} more</span>` : ''}
              </div>
            </div>
            <div style="margin-top: 0.8rem; display: flex; gap: 0.4rem; justify-content: space-between; align-items: center;">
              <span style="font-size: 0.78rem; color: var(--accent);">${item.total_reports > 0 ? item.total_reports + ' reports' : ''}</span>
              <button class="btn-secondary" onclick="harvestAndScrapeSub('${item.slug}')">Harvest IDs</button>
            </div>
          </div>
        `;
      }).join('');
    }

    async function filterCatalog() {
      const q = document.getElementById('catalogSearch').value;
      const res = await fetch('/api/catalog?limit=60&q=' + encodeURIComponent(q));
      catalogData = await res.json();
      renderCatalog(catalogData);
    }

    async function harvestAndScrapeSub(slug) {
      showTab('scraper');
      document.getElementById('harvestSubInput').value = slug;
      triggerSubHarvest();
    }

    async function checkCombination() {
      const val = document.getElementById('comboInput').value;
      const substances = val.split(',').map(s => s.trim()).filter(Boolean);
      if (substances.length < 2) {
        alert('Please enter at least 2 substances separated by commas (e.g. Alcohol, Xanax)');
        return;
      }
      const res = await fetch('/api/check-combo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ substances })
      });
      const data = await res.json();
      const container = document.getElementById('comboResults');
      
      let badgeClass = 'badge-safe';
      if (data.overall_risk === 'DEADLY') badgeClass = 'badge-deadly';
      else if (data.overall_risk === 'DANGEROUS') badgeClass = 'badge-dangerous';
      else if (data.overall_risk === 'CAUTION') badgeClass = 'badge-caution';

      container.innerHTML = `
        <div style="margin-top: 1rem; padding: 1rem; background: #162032; border-radius: 6px;">
          <div style="display: flex; align-items: center; gap: 0.8rem; margin-bottom: 0.8rem;">
            <h3>Evaluation Result:</h3>
            <span class="badge ${badgeClass}" style="font-size: 0.9rem;">${data.overall_risk}</span>
          </div>
          ${data.interactions.length === 0 ? '<p style="color: var(--text-muted);">No severe contraindications recorded for this specific pairing.</p>' : ''}
          ${data.interactions.map(it => `
            <div style="border-left: 3px solid ${it.risk_level === 'DEADLY' ? 'var(--deadly)' : 'var(--dangerous)'}; padding-left: 0.8rem; margin-bottom: 1rem;">
              <h4 style="color: #fff;">${it.substance_a.toUpperCase()} + ${it.substance_b.toUpperCase()}</h4>
              <p style="font-size: 0.9rem; color: #f87171; margin: 0.2rem 0;"><strong>Mechanism:</strong> ${it.mechanism}</p>
              <p style="font-size: 0.85rem; color: #cbd5e1;"><strong>Advice:</strong> ${it.harm_reduction_advice}</p>
            </div>
          `).join('')}
        </div>
      `;
    }

    async function loadExperiences() {
      const q = document.getElementById('expSearchQ').value;
      const tag = document.getElementById('expFilterTag').value;
      let url = '/api/experiences?limit=25';
      if (q) url += '&q=' + encodeURIComponent(q);
      if (tag) url += '&tag=' + encodeURIComponent(tag);

      const res = await fetch(url);
      const reports = await res.json();
      const container = document.getElementById('expResultsList');

      if (reports.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted);">No reports found matching your query in local vault.</p>';
        return;
      }

      container.innerHTML = reports.map(r => `
        <div class="exp-item" onclick="openReportModal(${r.id})">
          <div style="display: flex; justify-content: space-between;">
            <h4>Exp #${r.id}: ${r.title}</h4>
            <span style="font-size: 0.8rem; color: var(--text-muted);">${r.exp_year || ''}</span>
          </div>
          <div class="exp-meta">
            Substance: <strong>${r.substance_summary}</strong> | Author: ${r.author} | Body Weight: ${r.body_weight || 'N/A'}
          </div>
          <div style="margin-bottom: 0.4rem;">
            ${(r.harm_flags || []).map(f => `<span class="badge badge-deadly" style="margin-right: 4px;">${f}</span>`).join('')}
          </div>
          <div class="exp-snippet">${r.snippet}</div>
        </div>
      `).join('');
    }

    async function quickFetchExp() {
      const id = document.getElementById('quickExpId').value;
      if (!id) return;
      openReportModal(id);
    }

    async function openReportModal(id) {
      document.getElementById('modalTitle').innerText = `Exp #${id}: Loading from archive...`;
      document.getElementById('modalMeta').innerText = "Fetching raw snapshot, decompressing and extracting symptoms...";
      document.getElementById('modalFlags').innerHTML = "";
      document.getElementById('modalDoses').innerHTML = "";
      document.getElementById('modalBody').innerText = "Please wait a moment while the report is retrieved and parsed...";
      document.getElementById('reportModal').classList.add('active');

      const res = await fetch('/api/experience?id=' + id);
      const exp = await res.json();
      if (exp.error) {
        document.getElementById('modalTitle').innerText = `Exp #${id}: Error`;
        document.getElementById('modalBody').innerText = exp.error;
        return;
      }

      document.getElementById('modalTitle').innerText = `Exp #${exp.id}: ${exp.title}`;
      document.getElementById('modalMeta').innerText = `Substance: ${exp.substance_summary} | Author: ${exp.author} | Year: ${exp.exp_year || 'N/A'} | Weight: ${exp.body_weight || 'N/A'}`;
      
      document.getElementById('modalFlags').innerHTML = (exp.harm_flags || []).map(f => 
        `<span class="badge badge-deadly" style="margin-right: 6px;">${f}</span>`
      ).join('');

      document.getElementById('modalDoses').innerHTML = (exp.doses || []).length > 0 ? `
        <div style="background: #0f172a; padding: 0.8rem; border-radius: 4px; font-size: 0.85rem;">
          <strong>Reported Dosages:</strong><br>
          ${exp.doses.map(d => `• ${d.substance}: ${d.amount || ''} ${d.unit || ''} (${d.method || 'Oral'})`).join('<br>')}
        </div>
      ` : '';

      document.getElementById('modalBody').innerText = exp.narrative;
    }

    function closeModal() {
      document.getElementById('reportModal').classList.remove('active');
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
      log.innerHTML = `<span style="color: var(--accent);">Downloading up to 15 queued reports in parallel...</span>`;

      const res = await fetch('/api/batch-scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 15, workers: 3 })
      });
      const data = await res.json();
      log.innerHTML = `<span style="color: var(--safe);">✓ Batch completed: ${data.success} saved to SQLite out of ${data.total} attempted!</span>`;
      loadExperiences();
    }

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
                <td><strong>${k.name}</strong></td>
                <td>${k.primary_use}</td>
                <td>${k.notes}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
        <h4 style="margin-top: 1.2rem; color: var(--accent);">Fentanyl Test Strip Best Practices:</h4>
        <ol style="margin-left: 1.2rem; font-size: 0.88rem; color: #cbd5e1; margin-top: 0.5rem; display: flex; flex-direction: column; gap: 0.4rem;">
          ${data.fentanyl_strip_protocol.map(step => `<li>${step}</li>`).join('')}
        </ol>
      `;
    }

    // Initialize
    loadSubstances();
    loadTestingProtocols();
  </script>
</body>
</html>
"""
