"""
Zero-dependency HTTP Web Server and Harm Reduction Dashboard for Erowid SafeDB.
Serves a responsive single-page application and RESTful JSON API.
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
                if exp:
                    self._set_headers(200)
                    self.wfile.write(json.dumps(exp.to_dict()).encode("utf-8"))
                else:
                    self._set_headers(404)
                    self.wfile.write(json.dumps({"error": f"Experience {exp_id} not found"}).encode("utf-8"))
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

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))


def start_server(db: Database, port: int = 8080):
    """Starts the Erowid SafeDB web interface and REST API."""
    SafeDBRequestHandler.db = db
    SafeDBRequestHandler.engine = HarmReductionEngine(db)
    SafeDBRequestHandler.scraper = ErowidScraper()

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
  <title>Erowid Harm Reduction & Drug Education Database</title>
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
    nav { display: flex; gap: 0.5rem; }
    nav button { background: transparent; border: 1px solid var(--card-border); color: var(--text-muted); padding: 0.5rem 1rem; border-radius: var(--radius); cursor: pointer; font-weight: 500; transition: all 0.2s; }
    nav button.active, nav button:hover { background: var(--card-bg); color: var(--accent); border-color: var(--accent); }
    main { max-width: 1200px; margin: 2rem auto; padding: 0 1.5rem; }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .card { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius); padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { font-size: 1.3rem; margin-bottom: 0.75rem; color: #fff; border-bottom: 1px solid var(--card-border); padding-bottom: 0.5rem; }
    .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem; }
    .grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }
    
    /* Risk Badges */
    .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }
    .badge-deadly { background: rgba(239, 68, 68, 0.2); color: var(--deadly); border: 1px solid var(--deadly); }
    .badge-dangerous { background: rgba(249, 115, 22, 0.2); color: var(--dangerous); border: 1px solid var(--dangerous); }
    .badge-caution { background: rgba(234, 179, 8, 0.2); color: var(--caution); border: 1px solid var(--caution); }
    .badge-safe { background: rgba(34, 197, 94, 0.2); color: var(--safe); border: 1px solid var(--safe); }
    
    /* Inputs & Buttons */
    input, select, textarea { background: #0f172a; border: 1px solid var(--card-border); color: #fff; padding: 0.6rem 0.8rem; border-radius: var(--radius); width: 100%; margin-bottom: 0.8rem; }
    input:focus, select:focus { outline: none; border-color: var(--accent); }
    button.btn-primary { background: var(--accent); color: #0f172a; font-weight: bold; border: none; padding: 0.6rem 1.2rem; border-radius: var(--radius); cursor: pointer; transition: background 0.2s; }
    button.btn-primary:hover { background: var(--accent-hover); }
    
    /* Dose Table */
    table.data-table { width: 100%; border-collapse: collapse; margin-top: 0.8rem; font-size: 0.9rem; }
    table.data-table th, table.data-table td { padding: 0.6rem; text-align: left; border-bottom: 1px solid var(--card-border); }
    table.data-table th { background: #0f172a; color: var(--accent); }
    
    /* Overdose Protocol Banner */
    .alert-banner { background: rgba(239, 68, 68, 0.15); border-left: 4px solid var(--deadly); padding: 1rem; border-radius: 4px; margin-bottom: 1.5rem; }
    .alert-banner h3 { color: var(--deadly); margin-bottom: 0.3rem; }
    
    .exp-item { border-left: 3px solid var(--accent); padding: 1rem; margin-bottom: 1rem; background: #162032; border-radius: 0 6px 6px 0; cursor: pointer; transition: background 0.2s; }
    .exp-item:hover { background: #1a273e; }
    .exp-item h4 { color: #fff; font-size: 1.1rem; }
    .exp-meta { font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem; }
    .exp-snippet { font-size: 0.88rem; color: #cbd5e1; }
    
    .modal { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 1000; justify-content: center; align-items: center; }
    .modal.active { display: flex; }
    .modal-content { background: var(--card-bg); border: 1px solid var(--card-border); border-radius: var(--radius); max-width: 800px; width: 90%; max-height: 85vh; overflow-y: auto; padding: 2rem; position: relative; }
    .close-btn { position: absolute; top: 1rem; right: 1rem; font-size: 1.5rem; cursor: pointer; color: var(--text-muted); }
  </style>
</head>
<body>

  <header>
    <div>
      <h1>🛡️ Erowid SafeDB</h1>
      <div class="subtitle">Evidence-based Harm Reduction, Clinical Drug Interactions & Experience Database</div>
    </div>
    <nav>
      <button class="active" onclick="showTab('substances')">Substances</button>
      <button onclick="showTab('interactions')">Interaction Checker</button>
      <button onclick="showTab('experiences')">Experience Vault</button>
      <button onclick="showTab('emergency')">Emergency & Testing</button>
      <button onclick="showTab('scraper')">Scraper Console</button>
    </nav>
  </header>

  <main>
    <!-- TAB 1: SUBSTANCE BROWSER -->
    <div id="tab-substances" class="tab-content active">
      <div class="card">
        <h2>Substance Directory & Safe Dosing Guidelines</h2>
        <input type="text" id="subSearch" placeholder="Search substance by name, category, or slang (e.g. MDMA, Psilocybin, Ketamine, Shrooms)..." onkeyup="filterSubstances()">
        <div id="substancesList" class="grid-3" style="margin-top: 1rem;">
          <!-- Dynamically populated -->
        </div>
      </div>
    </div>

    <!-- TAB 2: INTERACTION CHECKER -->
    <div id="tab-interactions" class="tab-content">
      <div class="card">
        <h2>Multi-Drug Combo & Interaction Checker</h2>
        <p style="color: var(--text-muted); margin-bottom: 1rem;">Select or enter 2 or more substances to evaluate lethal or dangerous synergistic risks (e.g. respiratory arrest, serotonin syndrome, cardiac toxicity).</p>
        <div style="display: flex; gap: 0.5rem; margin-bottom: 1rem;">
          <input type="text" id="comboInput" placeholder="Enter comma-separated substances (e.g., MDMA, Tramadol or Alcohol, Xanax, Oxycodone)">
          <button class="btn-primary" onclick="checkCombination()" style="white-space: nowrap;">Check Risk</button>
        </div>
        <div id="comboResults"></div>
      </div>
    </div>

    <!-- TAB 3: EXPERIENCE VAULT -->
    <div id="tab-experiences" class="tab-content">
      <div class="card">
        <h2>Erowid Experience Reports Vault (Full-Text Search)</h2>
        <div class="grid-2">
          <input type="text" id="expSearchQ" placeholder="Keyword query (e.g. 'seizure', 'panic', 'overdose', 'recovery')...">
          <select id="expFilterTag" onchange="loadExperiences()">
            <option value="">All Tags / Outcomes</option>
            <option value="Overdose">Overdose</option>
            <option value="Hospital">Hospital / Medical Emergency</option>
            <option value="Bad Trips">Bad Trips</option>
            <option value="First Times">First Times</option>
          </select>
        </div>
        <button class="btn-primary" onclick="loadExperiences()">Search Vault</button>
        <div id="expResultsList" style="margin-top: 1.5rem;">
          <!-- Dynamically populated -->
        </div>
      </div>
    </div>

    <!-- TAB 4: EMERGENCY & TESTING PROTOCOLS -->
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
            <li><strong>4. Recovery Position:</strong> Roll the person onto their side with knee bent to prevent choking on vomit if they lose consciousness.</li>
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

    <!-- TAB 5: SCRAPER CONSOLE -->
    <div id="tab-scraper" class="tab-content">
      <div class="card">
        <h2>Live Erowid Experience Ingestion Console</h2>
        <p style="color: var(--text-muted); margin-bottom: 1rem;">
          Ingest Erowid Experience Reports directly by ExpID. The scraper uses disk caching and automatic Wayback Machine fallback to bypass bot filters and preserve server resources.
        </p>
        <div style="display: flex; gap: 0.5rem; max-width: 400px; margin-bottom: 1rem;">
          <input type="number" id="scrapeExpId" placeholder="Erowid Exp ID (e.g. 71809)">
          <button class="btn-primary" onclick="triggerScrape()">Ingest Report</button>
        </div>
        <div id="scrapeResultMsg" style="font-family: monospace; font-size: 0.85rem;"></div>
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

    function showTab(tabName) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('nav button').forEach(el => el.classList.remove('active'));
      document.getElementById('tab-' + tabName).classList.add('active');
      event.target.classList.add('active');
      if (tabName === 'experiences') loadExperiences();
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
      let url = '/api/experiences?limit=20';
      if (q) url += '&q=' + encodeURIComponent(q);
      if (tag) url += '&tag=' + encodeURIComponent(tag);

      const res = await fetch(url);
      const reports = await res.json();
      const container = document.getElementById('expResultsList');

      if (reports.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted);">No reports found matching your query.</p>';
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

    async function openReportModal(id) {
      const res = await fetch('/api/experience?id=' + id);
      const exp = await res.json();
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
      document.getElementById('reportModal').classList.add('active');
    }

    function closeModal() {
      document.getElementById('reportModal').classList.remove('active');
    }

    async function triggerScrape() {
      const id = document.getElementById('scrapeExpId').value;
      if (!id) return;
      const statusDiv = document.getElementById('scrapeResultMsg');
      statusDiv.innerHTML = '<span style="color: var(--accent);">Fetching report ' + id + ' (checking cache & Wayback)...</span>';

      const res = await fetch('/api/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exp_id: id })
      });
      const data = await res.json();
      if (data.success) {
        statusDiv.innerHTML = `<span style="color: var(--safe);">✓ Successfully ingested Exp #${data.report.id}: "${data.report.title}" (${data.report.substance_summary})!</span>`;
      } else {
        statusDiv.innerHTML = `<span style="color: var(--deadly);">✗ Ingestion failed: ${data.message || data.error}</span>`;
      }
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
