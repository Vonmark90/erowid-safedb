# 🛡️ Drug Harm Reduction Codex and Overdose Radar

**Drug Harm Reduction Codex and Overdose Radar** is an evidence-based clinical harm reduction system, multi-drug interaction engine, and systematic offline/online archive built to index and access the complete breadth of clinical monographs and psychoactive harm-reduction knowledge.

The project enables open access to clinical monographs, lethal drug combination contraindications, dosing brackets, and thousands of real-world disaster and recovery case studies to reduce drug-related harm and prevent accidental deaths.

---

## 🚀 Download Standalone Apps (No Python Required)

Pre-built, self-contained standalone desktop applications are available directly from the **[GitHub Releases Page](https://github.com/Vonmark90/drug-harm-reduction-codex-and-overdose-radar/releases/tag/v2.5.0)**:

| Platform | Download | Launch Instructions |
| :--- | :--- | :--- |
| 🍏 **macOS** | [**`DrugHarmReductionCodex-macOS.zip`**](https://github.com/Vonmark90/drug-harm-reduction-codex-and-overdose-radar/releases/download/v2.5.0/DrugHarmReductionCodex-macOS.zip) | Unzip and launch **`Drug Harm Reduction Codex and Overdose Radar.app`** |
| 🪟 **Windows** | [**`DrugHarmReductionCodex-Windows-x64.zip`**](https://github.com/Vonmark90/drug-harm-reduction-codex-and-overdose-radar/releases/download/v2.5.0/DrugHarmReductionCodex-Windows-x64.zip) | Unzip and double-click **`DrugHarmReductionCodex.exe`** |
| 🐧 **Linux** | [**`DrugHarmReductionCodex-Linux-x64.tar.gz`**](https://github.com/Vonmark90/drug-harm-reduction-codex-and-overdose-radar/releases/download/v2.5.0/DrugHarmReductionCodex-Linux-x64.tar.gz) | `tar -xvf DrugHarmReductionCodex-Linux-x64.tar.gz && ./DrugHarmReductionCodex` |

---

## ⚡ Key Capabilities

1. **Master Erowid Archive Catalog (560+ Substances)**
   - Complete indexed library extracted from Erowid's master directories (`exp_list.shtml` and `psychoactives.shtml`).
   - Mapped category trees for every substance (*Health Problems*, *Bad Trips*, *Train Wrecks & Trip Disasters*, *Combinations*, *First Times*, *General*, etc.).
   - Instant search across chemicals, research chemicals, botanicals, pharmaceuticals, and street analogs.

2. **Transparent On-Demand Fetching ("Access Any Report on Erowid")**
   - Querying or viewing any Experience Report ID (from 1 to 150,000+) automatically fetches it live from the archive if not locally present, decompresses, extracts adverse symptoms, saves it into SQLite with FTS5, and displays it immediately.

3. **Multi-Drug Interaction & Lethality Checker**
   - Direct database lookup for documented lethal and dangerous combinations (e.g. Alcohol + Xanax, MDMA + Tramadol, Cocaine + Alcohol cocaethylene toxicity).
   - Pharmacological fallback heuristics by mechanism (e.g. CNS depressant + depressant = synergistic respiratory arrest; MAOI + serotonergic = lethal serotonin syndrome; stimulant + stimulant = cardiovascular crisis).

4. **Dosage Safety Evaluation**
   - Real-time quantitative assessment of intended dose amounts against established threshold, common, strong, and overdose boundaries.

5. **Experience Vault & Full-Text Search (SQLite FTS5)**
   - High-performance SQLite FTS5 search across thousands of words of real trip reports.
   - Automated adverse clinical symptom extraction (`respiratory_depression`, `serotonin_syndrome`, `seizure`, `overdose`, `naloxone_administered`, `hospitalization`, `tachycardia`, `panic_attack`).

6. **Harvester & High-Performance Parallel Scraper**
   - Harvests all report IDs for any substance or high-risk category into the indexing queue.
   - Parallel multi-threaded batch downloader with polite rate-limiting, gzip/deflate auto-decompression, and disk caching.
   - Automatic Wayback Machine archive fallback to bypass Cloudflare bot restrictions on direct Erowid endpoints.

7. **Desktop GUI Application & Dual Interfaces**
   - **Clickable macOS Desktop App**: Double-click [`Erowid SafeDB.app`](file:///Users/marksadler/erowid_safedb/Erowid%20SafeDB.app) or [`Launch_GUI.command`](file:///Users/marksadler/erowid_safedb/Launch_GUI.command).
   - **Interactive Desktop App**: Launch via `python3 gui.py` or `python3 run.py gui` with automatic browser popup.
   - **Native CustomTkinter Desktop Window**: Launch with `python3 gui.py --native`.
   - **Terminal CLI**: Fast headless ANSI colorized commands for scripting and terminal power-users.

---

## 🖥️ Launching the Desktop GUI

You can launch the GUI app in three convenient ways:

1. **Double-Click Desktop App (macOS)**:
   - Double-click **`Erowid SafeDB.app`** or **`Launch_GUI.command`** in Finder!
2. **Terminal Launcher (Auto-opens browser window)**:
   ```bash
   python3 gui.py
   # or
   python3 run.py gui
   ```
3. **Native CustomTkinter Cocoa Window**:
   ```bash
   python3 gui.py --native
   ```

---

## 🚀 Quick Command Reference

All commands run through [`run.py`](file:///Users/marksadler/erowid_safedb/run.py) from `/Users/marksadler/erowid_safedb`:

### 1. Initialize & Seed Master Catalog
```bash
python3 run.py init
```

### 2. Search Master Erowid Catalog (560+ Substances)
```bash
# Search by keyword, chemical name, or slang
python3 run.py catalog "dmt"
python3 run.py catalog "ketamine"
python3 run.py catalog "2c"
```

### 3. View Substance Profiles
```bash
# View clinical monograph or master catalog profile
python3 run.py substance mdma
python3 run.py substance 2cb
python3 run.py substance dmt
```

### 4. Check Multi-Drug Interactions
```bash
# Lethal depressant synergy (fatal breathing failure)
python3 run.py check-combo alcohol xanax

# Fatal Serotonin Syndrome & seizure risk
python3 run.py check-combo mdma tramadol

# Toxic Cocaethylene cardiotoxicity
python3 run.py check-combo alcohol cocaine
```

### 5. Check Dosage Safety
```bash
python3 run.py check-dose mdma 220
python3 run.py check-dose psilocybin 2.0 --unit g
```

### 6. Universal Report Viewer (On-Demand Fetching)
```bash
# View any report by ID (fetches live if not already in local database)
python3 run.py view 71809
python3 run.py view 10000
python3 run.py view 100
```

### 7. Harvest & Batch Scrape Experience Reports
```bash
# Harvest all report IDs for a substance into the queue
python3 run.py harvest --substance 2cb
python3 run.py harvest --substance ketamine

# Harvest priority safety reports (Health Problems, Bad Trips, Train Wrecks)
python3 run.py harvest --priority

# Batch download queued reports in parallel
python3 run.py scrape --substance 2cb --limit 20 --workers 3
python3 run.py scrape --priority --limit 20
```

### 8. Search Local Vault with Full-Text Search
```bash
python3 run.py search "overdose"
python3 run.py search --symptom respiratory_depression
python3 run.py search "seizure" --substance tramadol
```

### 9. Launch Web Dashboard & REST API
```bash
python3 run.py web --port 8080
```
Navigate to **http://localhost:8080** for:
- **Master Catalog (560+)**: Browse, search, and trigger report harvests.
- **Universal Live Reader**: Enter any Erowid Report ID to read immediately.
- **Interaction Checker**: Multi-substance combination calculator.
- **Experience Vault**: Fast FTS5 search with modal reader.
- **Emergency Protocols**: Actionable overdose protocols & reagent testing guides.
- **Offline Database**: Real-time batch ingestion console and local storage manager.

---

## 🧪 Running Tests

The test suite covers database CRUD, FTS5 searching, catalog indexing, harvester queues, HTTP decompression, symptom extraction, dosage assessment, and interaction logic:

```bash
python3 -m unittest discover tests
```

---

## 📁 Project Architecture

```
erowid_safedb/
├── run.py                       # CLI and Web launcher
├── README.md                    # Project documentation & reference
├── data/
│   ├── erowid_safedb.db         # SQLite database with FTS5, WAL mode & catalog
│   └── cache/                   # Local raw HTML disk cache (reports & index pages)
├── erowid_safedb/
│   ├── models.py                # Dataclasses (Substance, CatalogEntry, ReportIndexItem, etc.)
│   ├── db.py                    # SQLite schema, FTS5 full-text queries & catalog tables
│   ├── parsers.py               # Erowid HTML extraction & clinical NLP regexes
│   ├── scraper.py               # Resilient scraper, catalog harvester & worker pool
│   ├── harm_reduction.py        # Interaction matrix, dosage bounds & emergency protocol
│   ├── seed_data.py             # Authoritative clinical monographs and case reports
│   ├── cli.py                   # Argument parser & ANSI colorized terminal interface
│   └── web.py                   # Zero-dependency HTTP server, SPA frontend & REST API
└── tests/
    ├── test_db.py               # Database & FTS5 tests
    ├── test_parsers.py          # HTML & adverse symptom parser tests
    ├── test_harm_reduction.py   # Interaction and dosage evaluation tests
    └── test_catalog.py          # Master catalog, harvester & decompression tests
```
