"""
SQLite database engine with FTS5 full-text search for Erowid Harm Reduction DB.
"""

import json
import sqlite3
import os
from typing import List, Optional, Dict, Any, Tuple
from erowid_safedb.models import (
    Substance,
    DosageInfo,
    DurationInfo,
    DrugInteraction,
    ExperienceReport,
    ExperienceDoseItem,
    AdverseEvent,
    CatalogEntry,
    ReportIndexItem,
)


class Database:
    def __init__(self, db_path: str = "erowid_harm_reduction.db"):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            cur = conn.cursor()

            # Substances table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS substances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                common_names_json TEXT,
                category TEXT,
                description TEXT,
                harm_summary TEXT,
                addiction_potential TEXT,
                toxicity_notes TEXT,
                legal_status TEXT,
                testing_reagents_json TEXT
            );
            """)

            # Dosages table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS dosages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                substance_id INTEGER NOT NULL,
                route TEXT NOT NULL,
                threshold TEXT,
                light TEXT,
                common TEXT,
                strong TEXT,
                heavy TEXT,
                unit TEXT DEFAULT 'mg',
                notes TEXT,
                FOREIGN KEY (substance_id) REFERENCES substances(id) ON DELETE CASCADE
            );
            """)

            # Durations table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS durations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                substance_id INTEGER NOT NULL,
                route TEXT NOT NULL,
                onset TEXT,
                coming_up TEXT,
                peak TEXT,
                plateau TEXT,
                coming_down TEXT,
                after_effects TEXT,
                total_duration TEXT,
                FOREIGN KEY (substance_id) REFERENCES substances(id) ON DELETE CASCADE
            );
            """)

            # Interactions table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                substance_a TEXT NOT NULL,
                substance_b TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                mechanism TEXT,
                harm_reduction_advice TEXT,
                UNIQUE(substance_a, substance_b)
            );
            """)

            # Experiences table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS experiences (
                id INTEGER PRIMARY KEY,
                title TEXT,
                author TEXT,
                substance_summary TEXT,
                exp_year INTEGER,
                published_date TEXT,
                gender TEXT,
                age TEXT,
                body_weight TEXT,
                narrative TEXT,
                harm_flags_json TEXT,
                word_count INTEGER,
                url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Experience Substances
            cur.execute("""
            CREATE TABLE IF NOT EXISTS experience_substances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experience_id INTEGER NOT NULL,
                substance_name TEXT NOT NULL,
                amount TEXT,
                unit TEXT,
                method TEXT,
                form TEXT,
                FOREIGN KEY (experience_id) REFERENCES experiences(id) ON DELETE CASCADE
            );
            """)

            # Experience Tags
            cur.execute("""
            CREATE TABLE IF NOT EXISTS experience_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experience_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                FOREIGN KEY (experience_id) REFERENCES experiences(id) ON DELETE CASCADE
            );
            """)

            # Adverse Events
            cur.execute("""
            CREATE TABLE IF NOT EXISTS adverse_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experience_id INTEGER NOT NULL,
                symptom TEXT NOT NULL,
                severity TEXT,
                excerpt TEXT,
                FOREIGN KEY (experience_id) REFERENCES experiences(id) ON DELETE CASCADE
            );
            """)

            # FTS5 virtual table for full-text search
            cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS experiences_fts USING fts5(
                experience_id UNINDEXED,
                title,
                substance_summary,
                narrative,
                tags,
                symptoms
            );
            """)

            # Erowid Master Catalog table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS erowid_catalog (
                slug TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                synonyms_json TEXT,
                master_url TEXT,
                categories_json TEXT,
                vault_url TEXT,
                total_reports INTEGER DEFAULT 0
            );
            """)

            # Erowid Report Index table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS erowid_report_index (
                id INTEGER PRIMARY KEY,
                substance_slug TEXT NOT NULL,
                category TEXT,
                title TEXT,
                author TEXT,
                status TEXT DEFAULT 'pending',
                scraped_at TIMESTAMP
            );
            """)

            # Indexes
            cur.execute("CREATE INDEX IF NOT EXISTS idx_substances_slug ON substances(slug);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_exp_sub_expid ON experience_substances(experience_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_exp_sub_name ON experience_substances(substance_name);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_exp_tags_tag ON experience_tags(tag);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_adv_events_symptom ON adverse_events(symptom);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rep_idx_slug ON erowid_report_index(substance_slug);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rep_idx_status ON erowid_report_index(status);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_catalog_name ON erowid_catalog(name);")
            conn.commit()

    # --- Substances Operations ---

    def save_substance(self, substance: Substance) -> int:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO substances (slug, name, common_names_json, category, description, harm_summary,
                                   addiction_potential, toxicity_notes, legal_status, testing_reagents_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name=excluded.name,
                common_names_json=excluded.common_names_json,
                category=excluded.category,
                description=excluded.description,
                harm_summary=excluded.harm_summary,
                addiction_potential=excluded.addiction_potential,
                toxicity_notes=excluded.toxicity_notes,
                legal_status=excluded.legal_status,
                testing_reagents_json=excluded.testing_reagents_json;
            """, (
                substance.slug.lower(),
                substance.name,
                json.dumps(substance.common_names),
                substance.category,
                substance.description,
                substance.harm_summary,
                substance.addiction_potential,
                substance.toxicity_notes,
                substance.legal_status,
                json.dumps(substance.testing_reagents)
            ))
            substance_id = cur.lastrowid
            if not substance_id:
                cur.execute("SELECT id FROM substances WHERE slug = ?", (substance.slug.lower(),))
                row = cur.fetchone()
                substance_id = row["id"]

            # Replace dosages
            cur.execute("DELETE FROM dosages WHERE substance_id = ?", (substance_id,))
            for dose in substance.dosages:
                cur.execute("""
                INSERT INTO dosages (substance_id, route, threshold, light, common, strong, heavy, unit, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    substance_id, dose.route, dose.threshold, dose.light, dose.common,
                    dose.strong, dose.heavy, dose.unit, dose.notes
                ))

            # Replace durations
            cur.execute("DELETE FROM durations WHERE substance_id = ?", (substance_id,))
            for dur in substance.durations:
                cur.execute("""
                INSERT INTO durations (substance_id, route, onset, coming_up, peak, plateau, coming_down, after_effects, total_duration)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    substance_id, dur.route, dur.onset, dur.coming_up, dur.peak, dur.plateau,
                    dur.coming_down, dur.after_effects, dur.total_duration
                ))

            conn.commit()
            return substance_id

    def get_substance(self, identifier: str) -> Optional[Substance]:
        ident = identifier.strip().lower()
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            SELECT * FROM substances
            WHERE slug = ? OR lower(name) = ?
            """, (ident, ident))
            row = cur.fetchone()
            if not row:
                # Try finding in common_names_json
                cur.execute("SELECT * FROM substances")
                for r in cur.fetchall():
                    c_names = [n.lower() for n in json.loads(r["common_names_json"] or "[]")]
                    if ident in c_names:
                        row = r
                        break
            if not row:
                return None

            sub_id = row["id"]
            # Fetch dosages
            cur.execute("SELECT * FROM dosages WHERE substance_id = ?", (sub_id,))
            dosages = [
                DosageInfo(
                    route=d["route"],
                    threshold=d["threshold"],
                    light=d["light"],
                    common=d["common"],
                    strong=d["strong"],
                    heavy=d["heavy"],
                    unit=d["unit"],
                    notes=d["notes"]
                ) for d in cur.fetchall()
            ]

            # Fetch durations
            cur.execute("SELECT * FROM durations WHERE substance_id = ?", (sub_id,))
            durations = [
                DurationInfo(
                    route=du["route"],
                    onset=du["onset"],
                    coming_up=du["coming_up"],
                    peak=du["peak"],
                    plateau=du["plateau"],
                    coming_down=du["coming_down"],
                    after_effects=du["after_effects"],
                    total_duration=du["total_duration"]
                ) for du in cur.fetchall()
            ]

            return Substance(
                id=row["id"],
                slug=row["slug"],
                name=row["name"],
                common_names=json.loads(row["common_names_json"] or "[]"),
                category=row["category"],
                description=row["description"],
                harm_summary=row["harm_summary"],
                addiction_potential=row["addiction_potential"],
                toxicity_notes=row["toxicity_notes"],
                legal_status=row["legal_status"],
                testing_reagents=json.loads(row["testing_reagents_json"] or "{}"),
                dosages=dosages,
                durations=durations
            )

    def get_all_substances(self) -> List[Substance]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT slug FROM substances ORDER BY name ASC")
            slugs = [r["slug"] for r in cur.fetchall()]
        return [self.get_substance(s) for s in slugs if s]

    # --- Interactions Operations ---

    def save_interaction(self, inter: DrugInteraction):
        # Canonical order: substance_a and substance_b sorted alphabetically for symmetric lookup
        sub_a, sub_b = sorted([inter.substance_a.strip().lower(), inter.substance_b.strip().lower()])
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO interactions (substance_a, substance_b, risk_level, mechanism, harm_reduction_advice)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(substance_a, substance_b) DO UPDATE SET
                risk_level=excluded.risk_level,
                mechanism=excluded.mechanism,
                harm_reduction_advice=excluded.harm_reduction_advice;
            """, (sub_a, sub_b, inter.risk_level.upper(), inter.mechanism, inter.harm_reduction_advice))
            conn.commit()

    def get_interaction(self, sub_1: str, sub_2: str) -> Optional[DrugInteraction]:
        sub_a, sub_b = sorted([sub_1.strip().lower(), sub_2.strip().lower()])
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            SELECT * FROM interactions
            WHERE (substance_a = ? AND substance_b = ?)
               OR (substance_a LIKE ? AND substance_b LIKE ?)
            """, (sub_a, sub_b, f"%{sub_a}%", f"%{sub_b}%"))
            row = cur.fetchone()
            if row:
                return DrugInteraction(
                    substance_a=row["substance_a"],
                    substance_b=row["substance_b"],
                    risk_level=row["risk_level"],
                    mechanism=row["mechanism"],
                    harm_reduction_advice=row["harm_reduction_advice"]
                )
        return None

    def get_all_interactions(self) -> List[DrugInteraction]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM interactions ORDER BY risk_level DESC, substance_a ASC")
            return [
                DrugInteraction(
                    substance_a=r["substance_a"],
                    substance_b=r["substance_b"],
                    risk_level=r["risk_level"],
                    mechanism=r["mechanism"],
                    harm_reduction_advice=r["harm_reduction_advice"]
                ) for r in cur.fetchall()
            ]

    # --- Experience Reports Operations ---

    def save_experience(self, exp: ExperienceReport) -> bool:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO experiences (id, title, author, substance_summary, exp_year, published_date,
                                    gender, age, body_weight, narrative, harm_flags_json, word_count, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,
                author=excluded.author,
                substance_summary=excluded.substance_summary,
                exp_year=excluded.exp_year,
                published_date=excluded.published_date,
                gender=excluded.gender,
                age=excluded.age,
                body_weight=excluded.body_weight,
                narrative=excluded.narrative,
                harm_flags_json=excluded.harm_flags_json,
                word_count=excluded.word_count,
                url=excluded.url;
            """, (
                exp.id, exp.title, exp.author, exp.substance_summary, exp.exp_year, exp.published_date,
                exp.gender, exp.age, exp.body_weight, exp.narrative, json.dumps(exp.harm_flags),
                exp.word_count or len(exp.narrative.split()), exp.url
            ))

            # Replace experience substances
            cur.execute("DELETE FROM experience_substances WHERE experience_id = ?", (exp.id,))
            for d in exp.doses:
                cur.execute("""
                INSERT INTO experience_substances (experience_id, substance_name, amount, unit, method, form)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (exp.id, d.substance, d.amount, d.unit, d.method, d.form))

            # Replace tags
            cur.execute("DELETE FROM experience_tags WHERE experience_id = ?", (exp.id,))
            for tag in exp.tags:
                cur.execute("""
                INSERT INTO experience_tags (experience_id, tag)
                VALUES (?, ?)
                """, (exp.id, tag))

            # Replace adverse events
            cur.execute("DELETE FROM adverse_events WHERE experience_id = ?", (exp.id,))
            for adv in exp.adverse_events:
                cur.execute("""
                INSERT INTO adverse_events (experience_id, symptom, severity, excerpt)
                VALUES (?, ?, ?, ?)
                """, (exp.id, adv.symptom, adv.severity, adv.excerpt))

            # Update FTS5 index
            cur.execute("DELETE FROM experiences_fts WHERE experience_id = ?", (str(exp.id),))
            symptoms_str = " ".join([a.symptom for a in exp.adverse_events])
            tags_str = " ".join(exp.tags)
            cur.execute("""
            INSERT INTO experiences_fts (experience_id, title, substance_summary, narrative, tags, symptoms)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (str(exp.id), exp.title or "", exp.substance_summary or "", exp.narrative or "", tags_str, symptoms_str))

            conn.commit()
            return True

    def get_experience(self, exp_id: int) -> Optional[ExperienceReport]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM experiences WHERE id = ?", (exp_id,))
            row = cur.fetchone()
            if not row:
                return None

            # Doses
            cur.execute("SELECT * FROM experience_substances WHERE experience_id = ?", (exp_id,))
            doses = [
                ExperienceDoseItem(
                    substance=r["substance_name"],
                    amount=r["amount"],
                    unit=r["unit"],
                    method=r["method"],
                    form=r["form"]
                ) for r in cur.fetchall()
            ]

            # Tags
            cur.execute("SELECT tag FROM experience_tags WHERE experience_id = ?", (exp_id,))
            tags = [r["tag"] for r in cur.fetchall()]

            # Adverse events
            cur.execute("SELECT * FROM adverse_events WHERE experience_id = ?", (exp_id,))
            adverse = [
                AdverseEvent(
                    symptom=r["symptom"],
                    severity=r["severity"],
                    excerpt=r["excerpt"]
                ) for r in cur.fetchall()
            ]

            return ExperienceReport(
                id=row["id"],
                title=row["title"],
                author=row["author"],
                substance_summary=row["substance_summary"],
                exp_year=row["exp_year"],
                published_date=row["published_date"],
                gender=row["gender"],
                age=row["age"],
                body_weight=row["body_weight"],
                narrative=row["narrative"],
                harm_flags=json.loads(row["harm_flags_json"] or "[]"),
                word_count=row["word_count"],
                url=row["url"],
                doses=doses,
                tags=tags,
                adverse_events=adverse
            )

    def search_experiences(
        self,
        query: Optional[str] = None,
        substance: Optional[str] = None,
        tag: Optional[str] = None,
        symptom: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            params = []
            where_clauses = []

            if query and query.strip():
                # Clean query for FTS5 syntax
                clean_q = "".join([c if c.isalnum() or c.isspace() else " " for c in query.strip()])
                where_clauses.append("e.id IN (SELECT experience_id FROM experiences_fts WHERE experiences_fts MATCH ?)")
                params.append(clean_q)

            if substance and substance.strip():
                where_clauses.append("e.id IN (SELECT experience_id FROM experience_substances WHERE lower(substance_name) LIKE ?)")
                params.append(f"%{substance.strip().lower()}%")

            if tag and tag.strip():
                where_clauses.append("e.id IN (SELECT experience_id FROM experience_tags WHERE lower(tag) LIKE ?)")
                params.append(f"%{tag.strip().lower()}%")

            if symptom and symptom.strip():
                where_clauses.append("e.id IN (SELECT experience_id FROM adverse_events WHERE lower(symptom) LIKE ?)")
                params.append(f"%{symptom.strip().lower()}%")

            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            sql = f"""
            SELECT e.id, e.title, e.author, e.substance_summary, e.exp_year, e.gender,
                   e.body_weight, e.harm_flags_json, e.word_count, substr(e.narrative, 1, 300) AS snippet
            FROM experiences e
            {where_sql}
            ORDER BY e.id DESC
            LIMIT ? OFFSET ?;
            """
            params.extend([limit, offset])
            cur.execute(sql, params)

            results = []
            for r in cur.fetchall():
                results.append({
                    "id": r["id"],
                    "title": r["title"],
                    "author": r["author"],
                    "substance_summary": r["substance_summary"],
                    "exp_year": r["exp_year"],
                    "gender": r["gender"],
                    "body_weight": r["body_weight"],
                    "harm_flags": json.loads(r["harm_flags_json"] or "[]"),
                    "word_count": r["word_count"],
                    "snippet": (r["snippet"] or "").strip() + "..."
                })
            return results

    def get_stats(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) AS total_substances FROM substances")
            total_substances = cur.fetchone()["total_substances"]

            cur.execute("SELECT count(*) AS total_experiences FROM experiences")
            total_experiences = cur.fetchone()["total_experiences"]

            cur.execute("SELECT count(*) AS total_interactions FROM interactions")
            total_interactions = cur.fetchone()["total_interactions"]

            cur.execute("""
            SELECT tag, count(*) AS count
            FROM experience_tags
            GROUP BY tag
            ORDER BY count DESC
            LIMIT 10
            """)
            top_tags = [dict(r) for r in cur.fetchall()]

            cur.execute("""
            SELECT symptom, severity, count(*) AS count
            FROM adverse_events
            GROUP BY symptom, severity
            ORDER BY count DESC
            LIMIT 10
            """)
            top_symptoms = [dict(r) for r in cur.fetchall()]

            cur.execute("""
            SELECT substance_name, count(DISTINCT experience_id) AS report_count
            FROM experience_substances
            GROUP BY lower(substance_name)
            ORDER BY report_count DESC
            LIMIT 10
            """)
            top_substances = [dict(r) for r in cur.fetchall()]

            return {
                "total_substances": total_substances,
                "total_experiences": total_experiences,
                "total_interactions": total_interactions,
                "top_tags": top_tags,
                "top_adverse_symptoms": top_symptoms,
                "top_reported_substances": top_substances
            }

    # --- Erowid Master Catalog Operations ---

    def save_catalog_entry(self, entry: CatalogEntry):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO erowid_catalog (slug, name, description, synonyms_json, master_url, categories_json, vault_url, total_reports)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                synonyms_json=excluded.synonyms_json,
                master_url=excluded.master_url,
                categories_json=excluded.categories_json,
                vault_url=excluded.vault_url,
                total_reports=excluded.total_reports;
            """, (
                entry.slug,
                entry.name,
                entry.description,
                json.dumps(entry.synonyms),
                entry.master_url,
                json.dumps(entry.categories),
                entry.vault_url,
                entry.total_reports
            ))
            conn.commit()

    def bulk_save_catalog_entries(self, entries: List[CatalogEntry]) -> int:
        with self.get_connection() as conn:
            cur = conn.cursor()
            data = [
                (
                    e.slug,
                    e.name,
                    e.description,
                    json.dumps(e.synonyms),
                    e.master_url,
                    json.dumps(e.categories),
                    e.vault_url,
                    e.total_reports
                ) for e in entries
            ]
            cur.executemany("""
            INSERT INTO erowid_catalog (slug, name, description, synonyms_json, master_url, categories_json, vault_url, total_reports)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                name=excluded.name,
                description=excluded.description,
                synonyms_json=excluded.synonyms_json,
                master_url=excluded.master_url,
                categories_json=excluded.categories_json,
                vault_url=excluded.vault_url,
                total_reports=excluded.total_reports;
            """, data)
            conn.commit()
            return len(entries)

    def get_catalog_entry(self, slug_or_name: str) -> Optional[CatalogEntry]:
        norm = slug_or_name.strip().lower()
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            SELECT * FROM erowid_catalog
            WHERE lower(slug) = ? OR lower(name) = ?
            LIMIT 1;
            """, (norm, norm))
            row = cur.fetchone()
            if not row:
                # Try finding in synonyms
                cur.execute("""
                SELECT * FROM erowid_catalog
                WHERE lower(synonyms_json) LIKE ?
                LIMIT 1;
                """, (f"%{norm}%",))
                row = cur.fetchone()

            if not row:
                return None

            return CatalogEntry(
                slug=row["slug"],
                name=row["name"],
                description=row["description"] or "",
                synonyms=json.loads(row["synonyms_json"] or "[]"),
                master_url=row["master_url"] or "",
                categories=json.loads(row["categories_json"] or "{}"),
                vault_url=row["vault_url"],
                total_reports=row["total_reports"] or 0
            )

    def search_catalog(self, query: str = "", limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        norm = query.strip().lower() if query else ""
        with self.get_connection() as conn:
            cur = conn.cursor()
            if norm:
                cur.execute("""
                SELECT * FROM erowid_catalog
                WHERE lower(name) LIKE ? OR lower(slug) LIKE ? OR lower(description) LIKE ? OR lower(synonyms_json) LIKE ?
                ORDER BY total_reports DESC, name ASC
                LIMIT ? OFFSET ?;
                """, (f"%{norm}%", f"%{norm}%", f"%{norm}%", f"%{norm}%", limit, offset))
            else:
                cur.execute("""
                SELECT * FROM erowid_catalog
                ORDER BY total_reports DESC, name ASC
                LIMIT ? OFFSET ?;
                """, (limit, offset))

            rows = cur.fetchall()
            results = []
            for r in rows:
                results.append({
                    "slug": r["slug"],
                    "name": r["name"],
                    "description": r["description"] or "",
                    "synonyms": json.loads(r["synonyms_json"] or "[]"),
                    "master_url": r["master_url"] or "",
                    "categories": json.loads(r["categories_json"] or "{}"),
                    "vault_url": r["vault_url"],
                    "total_reports": r["total_reports"] or 0
                })
            return results

    def get_all_catalog_entries(self) -> List[CatalogEntry]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM erowid_catalog ORDER BY name ASC;")
            rows = cur.fetchall()
            return [
                CatalogEntry(
                    slug=r["slug"],
                    name=r["name"],
                    description=r["description"] or "",
                    synonyms=json.loads(r["synonyms_json"] or "[]"),
                    master_url=r["master_url"] or "",
                    categories=json.loads(r["categories_json"] or "{}"),
                    vault_url=r["vault_url"],
                    total_reports=r["total_reports"] or 0
                ) for r in rows
            ]

    # --- Report Index Operations ---

    def save_report_index_items(self, items: List[ReportIndexItem]) -> int:
        with self.get_connection() as conn:
            cur = conn.cursor()
            data = [
                (it.id, it.substance_slug, it.category, it.title, it.author, it.status, it.scraped_at)
                for it in items
            ]
            cur.executemany("""
            INSERT INTO erowid_report_index (id, substance_slug, category, title, author, status, scraped_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                substance_slug=excluded.substance_slug,
                category=COALESCE(excluded.category, erowid_report_index.category),
                title=COALESCE(excluded.title, erowid_report_index.title),
                author=COALESCE(excluded.author, erowid_report_index.author);
            """, data)
            conn.commit()
            return len(items)

    def get_unscraped_reports(
        self,
        substance_slug: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50
    ) -> List[ReportIndexItem]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            query = "SELECT * FROM erowid_report_index WHERE status = 'pending'"
            params: List[Any] = []
            if substance_slug:
                query += " AND lower(substance_slug) = ?"
                params.append(substance_slug.lower())
            if category:
                query += " AND lower(category) = ?"
                params.append(category.lower())
            query += " ORDER BY id ASC LIMIT ?"
            params.append(limit)

            cur.execute(query, params)
            rows = cur.fetchall()
            return [
                ReportIndexItem(
                    id=r["id"],
                    substance_slug=r["substance_slug"],
                    category=r["category"] or "General",
                    title=r["title"] or "",
                    author=r["author"] or "",
                    status=r["status"] or "pending",
                    scraped_at=r["scraped_at"]
                ) for r in rows
            ]

    def mark_report_scraped(self, report_id: int):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
            UPDATE erowid_report_index
            SET status = 'scraped', scraped_at = CURRENT_TIMESTAMP
            WHERE id = ?;
            """, (report_id,))
            conn.commit()

    def get_catalog_stats(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT count(*) AS total_catalog_substances FROM erowid_catalog;")
            total_cat = cur.fetchone()["total_catalog_substances"]

            cur.execute("SELECT count(*) AS total_indexed_reports FROM erowid_report_index;")
            total_indexed = cur.fetchone()["total_indexed_reports"]

            cur.execute("SELECT count(*) AS total_scraped_reports FROM erowid_report_index WHERE status = 'scraped';")
            total_scraped = cur.fetchone()["total_scraped_reports"]

            cur.execute("""
            SELECT category, count(*) AS count
            FROM erowid_report_index
            GROUP BY category
            ORDER BY count DESC
            LIMIT 10;
            """)
            top_cats = [dict(r) for r in cur.fetchall()]

            return {
                "total_catalog_substances": total_cat,
                "total_indexed_reports": total_indexed,
                "total_scraped_reports": total_scraped,
                "top_categories": top_cats
            }

