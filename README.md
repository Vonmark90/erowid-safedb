# 🛡️ Erowid SafeDB: Systematic Harm Reduction & Experience Database

**Erowid SafeDB** is an open-source, evidence-based harm reduction system, clinical drug interaction engine, and systematic database built from Erowid's experience vault and pharmacological literature.

The project exists to make critical substance safety data, dangerous drug combination alerts, safe dosing guidelines, and real-world disaster case studies instantly accessible to reduce harm and prevent accidental drug-related deaths.

---

## ⚡ Key Capabilities

1. **Systematic Substance Monographs & Vaults**
   - Clinical pharmacology profiles, common/street slang names, addiction potential, and legal scheduling.
   - Route-specific dosing brackets (*Threshold*, *Light*, *Common*, *Strong*, *Heavy*).
   - Time-course curves (*Onset*, *Peak*, *Duration*, *After-effects*).
   - Chemical reagent testing color references (*Marquis*, *Mecke*, *Simon's*, *Ehrlich*, *Hofmann*).

2. **Multi-Drug Interaction & Lethality Checker**
   - Direct database lookup for documented lethal and dangerous combinations (e.g. Alcohol + Xanax, MDMA + Tramadol, Cocaine + Alcohol cocaethylene toxicity).
   - Pharmacological fallback heuristics by mechanism (e.g. CNS depressant + depressant = synergistic respiratory arrest; MAOI + serotonergic = lethal serotonin syndrome; stimulant + stimulant = cardiovascular crisis).

3. **Dosage Safety Evaluation**
   - Real-time quantitative assessment of intended dose amounts against established threshold and overdose boundaries.

4. **Experience Vault & Full-Text Search (FTS5)**
   - High-performance SQLite FTS5 search across thousands of words of real trip reports.
   - Automated adverse clinical symptom extraction (`respiratory_depression`, `serotonin_syndrome`, `seizure`, `overdose`, `naloxone_administered`, `hospitalization`, `tachycardia`, `panic_attack`).

5. **Archive-Resilient Scraper & Local Ingestion**
   - Polite rate-limited scraping engine.
   - Built-in local disk caching in `data/cache/experiences/`.
   - Automatic Internet Archive Wayback Machine fallback to bypass Cloudflare bot restrictions on direct Erowid endpoints.
   - Local HTML and directory batch import capabilities.

6. **Dual Interface: Terminal CLI & Zero-Dependency Web App**
   - Full command-line interface with ANSI color-coded danger alerts.
   - Responsive web dashboard and REST API served with Python standard library (`http.server`).

---

## 🚀 Quick Start

### 1. Initialize Database & Seed Baseline Monograph Data
```bash
python3 run.py init
```
This prepares SQLite with WAL journaling, builds FTS5 search tables, and seeds initial substance monographs, high-risk drug interaction rules, and verified case studies.

### 2. Substance Dossier Lookup
```bash
python3 run.py substance mdma
python3 run.py substance ketamine
python3 run.py substance lsd
```

### 3. Check Multi-Drug Combinations
```bash
# Lethal depressant synergy
python3 run.py check-combo alcohol xanax

# Fatal Serotonin Syndrome & seizure risk
python3 run.py check-combo mdma tramadol

# Toxic Cocaethylene cardiotoxicity
python3 run.py check-combo alcohol cocaine
```

### 4. Check Dosage Safety
```bash
python3 run.py check-dose mdma 100
python3 run.py check-dose mdma 250
```

### 5. Search the Experience Reports Vault
```bash
# Keyword search with FTS5
python3 run.py search "overdose"
python3 run.py search "seizure" --substance tramadol
python3 run.py search --symptom respiratory_depression

# View full report narrative and clinical extraction
python3 run.py view 71809
```

### 6. Scrape Live / Archived Experience Reports
```bash
# Fetch single experience by ID (auto-caches to disk)
python3 run.py scrape --id 100

# Batch scrape a range of IDs with polite delays
python3 run.py scrape --range 100 110 --delay 2.0
```

### 7. Launch Interactive Web UI & REST API
```bash
python3 run.py web --port 8080
```
Open [http://localhost:8080](http://localhost:8080) in any web browser to access:
- Substance Catalog & Dosage Matrix
- Interactive Multi-Drug Combination Calculator
- Searchable Experience Vault with modal reader
- Emergency Life-Saving Overdose Protocols & Reagent Testing Charts
- Live Scraper Ingestion Console

---

## 🧪 Running Tests

The test suite covers database CRUD, FTS5 searching, HTML regex parsing, symptom extraction, dosage assessment, and interaction logic:

```bash
python3 -m unittest discover tests
```

---

## 📁 Project Architecture

```
erowid_safedb/
├── run.py                       # CLI and Web launcher
├── README.md                    # Documentation & guide
├── data/
│   ├── erowid_safedb.db         # SQLite database with FTS5 and WAL mode
│   └── cache/                   # Local raw HTML disk cache
├── erowid_safedb/
│   ├── models.py                # Strongly-typed Dataclasses
│   ├── db.py                    # SQLite schema, FTS5 full-text queries & indices
│   ├── parsers.py               # Erowid HTML extraction & clinical NLP regexes
│   ├── scraper.py               # Rate-limited scraper with Wayback Machine fallback
│   ├── harm_reduction.py        # Interaction matrix, dosage bounds & emergency protocol
│   ├── seed_data.py             # Authoritative clinical monographs and case reports
│   ├── cli.py                   # Argument parser & ANSI colorized terminal interface
│   └── web.py                   # Zero-dependency HTTP server, SPA frontend & REST API
└── tests/
    ├── test_db.py               # Database tests
    ├── test_parsers.py          # HTML & adverse symptom parser tests
    └── test_harm_reduction.py   # Interaction and dosage evaluation tests
```
