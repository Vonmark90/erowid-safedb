"""
Native Desktop GUI for Erowid SafeDB using CustomTkinter / Tkinter.
Features tabs for clinical monographs, master catalog (560+), drug interactions,
dosage calculator, universal experience reader, and emergency protocols.
"""

import sys
import os
import threading
from typing import Optional, List, Dict, Any

from erowid_safedb.db import Database
from erowid_safedb.harm_reduction import HarmReductionEngine
from erowid_safedb.scraper import ErowidScraper
from erowid_safedb.seed_data import seed_database

try:
    import customtkinter as ctk
    HAS_CUSTOMTKINTER = True
except ImportError:
    import tkinter as ctk
    HAS_CUSTOMTKINTER = False


class SafeDBNativeApp:
    def __init__(self, db_path: str = "data/erowid_safedb.db"):
        self.db = Database(db_path)
        self.engine = HarmReductionEngine(self.db)
        self.scraper = ErowidScraper()

        # Ensure catalog is populated
        if self.db.get_catalog_stats()["total_catalog_substances"] == 0:
            try:
                self.scraper.index_catalog(self.db)
            except Exception:
                pass

        if HAS_CUSTOMTKINTER:
            ctk.set_appearance_mode("Dark")
            ctk.set_default_color_theme("blue")
            self.root = ctk.CTk()
        else:
            self.root = ctk.Tk()

        self.root.title("🛡️ Erowid SafeDB - Systematic Harm Reduction & Universal Archive")
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)

        self._build_ui()

    def _build_ui(self):
        # Grid layout: sidebar (col 0), content (col 1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        # Sidebar Frame
        if HAS_CUSTOMTKINTER:
            self.sidebar = ctk.CTkFrame(self.root, width=220, corner_radius=0)
            self.sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
            self.sidebar.grid_rowconfigure(8, weight=1)

            # Logo / Title
            title_lbl = ctk.CTkLabel(self.sidebar, text="🛡️ Erowid SafeDB", font=ctk.CTkFont(size=20, weight="bold"))
            title_lbl.grid(row=0, column=0, padx=20, pady=(20, 10))

            subtitle_lbl = ctk.CTkLabel(self.sidebar, text="Harm Reduction & Archive", font=ctk.CTkFont(size=12), text_color="#94a3b8")
            subtitle_lbl.grid(row=1, column=0, padx=20, pady=(0, 20))

            # Navigation buttons
            self.btn_substances = ctk.CTkButton(self.sidebar, text="💊 Clinical Dossiers", command=lambda: self.switch_tab("substances"))
            self.btn_substances.grid(row=2, column=0, padx=20, pady=8, sticky="ew")

            self.btn_catalog = ctk.CTkButton(self.sidebar, text="📚 Master Catalog (560+)", command=lambda: self.switch_tab("catalog"))
            self.btn_catalog.grid(row=3, column=0, padx=20, pady=8, sticky="ew")

            self.btn_interactions = ctk.CTkButton(self.sidebar, text="⚠️ Interaction Checker", command=lambda: self.switch_tab("interactions"))
            self.btn_interactions.grid(row=4, column=0, padx=20, pady=8, sticky="ew")

            self.btn_dosage = ctk.CTkButton(self.sidebar, text="⚖️ Dosage Evaluator", command=lambda: self.switch_tab("dosage"))
            self.btn_dosage.grid(row=5, column=0, padx=20, pady=8, sticky="ew")

            self.btn_vault = ctk.CTkButton(self.sidebar, text="📖 Experience Vault", command=lambda: self.switch_tab("vault"))
            self.btn_vault.grid(row=6, column=0, padx=20, pady=8, sticky="ew")

            self.btn_emergency = ctk.CTkButton(self.sidebar, text="🚨 Emergency Protocols", command=lambda: self.switch_tab("emergency"))
            self.btn_emergency.grid(row=7, column=0, padx=20, pady=8, sticky="ew")

            # Bottom stats in sidebar
            self.stats_lbl = ctk.CTkLabel(self.sidebar, text="", font=ctk.CTkFont(size=11), text_color="#64748b", justify="left")
            self.stats_lbl.grid(row=9, column=0, padx=15, pady=15, sticky="s")
            self._update_sidebar_stats()

            # Main Content Container
            self.main_container = ctk.CTkFrame(self.root, corner_radius=0, fg_color="#0f172a")
            self.main_container.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
            self.main_container.grid_columnconfigure(0, weight=1)
            self.main_container.grid_rowconfigure(0, weight=1)

            # Build all views
            self.views: Dict[str, ctk.CTkFrame] = {}
            self._build_substances_view()
            self._build_catalog_view()
            self._build_interactions_view()
            self._build_dosage_view()
            self._build_vault_view()
            self._build_emergency_view()

            # Show initial view
            self.switch_tab("substances")

    def _update_sidebar_stats(self):
        stats = self.db.get_stats()
        cat_stats = self.db.get_catalog_stats()
        txt = (
            f"Catalog Subs: {cat_stats['total_catalog_substances']}\n"
            f"Harvested IDs: {cat_stats['total_indexed_reports']}\n"
            f"Local Vault: {stats['total_experiences']} reports\n"
            f"Interactions: {stats['total_interactions']}"
        )
        self.stats_lbl.configure(text=txt)

    def switch_tab(self, name: str):
        for vname, frame in self.views.items():
            if vname == name:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()
        self._update_sidebar_stats()

    # --- 1. Clinical Monographs View ---
    def _build_substances_view(self):
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.views["substances"] = view
        view.grid_columnconfigure(0, weight=1)
        view.grid_columnconfigure(1, weight=3)
        view.grid_rowconfigure(0, weight=1)

        # Left list
        left_box = ctk.CTkFrame(view, fg_color="#1e293b")
        left_box.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        left_box.grid_rowconfigure(1, weight=1)

        lbl = ctk.CTkLabel(left_box, text="Clinical Monographs", font=ctk.CTkFont(size=16, weight="bold"))
        lbl.grid(row=0, column=0, padx=10, pady=10)

        self.sub_scroll = ctk.CTkScrollableFrame(left_box, fg_color="transparent")
        self.sub_scroll.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Right detail frame
        self.sub_detail = ctk.CTkScrollableFrame(view, fg_color="#1e293b")
        self.sub_detail.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        # Populate substances list
        subs = self.db.get_all_substances()
        for s in subs:
            btn = ctk.CTkButton(
                self.sub_scroll,
                text=s.name,
                fg_color="#334155",
                hover_color="#0284c7",
                command=lambda slug=s.slug: self._display_substance_detail(slug)
            )
            btn.pack(fill="x", padx=5, pady=4)

        if subs:
            self._display_substance_detail(subs[0].slug)

    def _display_substance_detail(self, slug: str):
        # Clear detail
        for w in self.sub_detail.winfo_children():
            w.destroy()

        sub = self.db.get_substance(slug)
        if not sub:
            return

        title = ctk.CTkLabel(self.sub_detail, text=f"{sub.name.upper()} ({sub.category})", font=ctk.CTkFont(size=20, weight="bold"), text_color="#38bdf8")
        title.pack(anchor="w", padx=15, pady=(15, 5))

        meta_txt = f"Aliases / Slang: {', '.join(sub.common_names) if sub.common_names else 'N/A'} | Addiction: {sub.addiction_potential} | Status: {sub.legal_status}"
        meta = ctk.CTkLabel(self.sub_detail, text=meta_txt, font=ctk.CTkFont(size=12), text_color="#94a3b8")
        meta.pack(anchor="w", padx=15, pady=(0, 10))

        # Harm summary box
        harm_box = ctk.CTkFrame(self.sub_detail, fg_color="#0f172a", border_width=1, border_color="#ef4444")
        harm_box.pack(fill="x", padx=15, pady=8)
        ctk.CTkLabel(harm_box, text="⚠️ Harm Summary & Prevention", font=ctk.CTkFont(size=14, weight="bold"), text_color="#ef4444").pack(anchor="w", padx=10, pady=(8, 4))
        ctk.CTkLabel(harm_box, text=sub.harm_summary, font=ctk.CTkFont(size=13), wraplength=550, justify="left", text_color="#f8fafc").pack(anchor="w", padx=10, pady=(0, 8))

        # Toxicity box
        tox_box = ctk.CTkFrame(self.sub_detail, fg_color="#0f172a")
        tox_box.pack(fill="x", padx=15, pady=8)
        ctk.CTkLabel(tox_box, text="🧬 Toxicity & Physiological Risks", font=ctk.CTkFont(size=14, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=10, pady=(8, 4))
        ctk.CTkLabel(tox_box, text=sub.toxicity_notes, font=ctk.CTkFont(size=13), wraplength=550, justify="left", text_color="#cbd5e1").pack(anchor="w", padx=10, pady=(0, 8))

        # Dosages
        if sub.dosages:
            dose_box = ctk.CTkFrame(self.sub_detail, fg_color="#0f172a")
            dose_box.pack(fill="x", padx=15, pady=8)
            ctk.CTkLabel(dose_box, text="⚖️ Standard Dosage Brackets", font=ctk.CTkFont(size=14, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=10, pady=(8, 4))
            for d in sub.dosages:
                dose_txt = (
                    f"Route: {d.route}\n"
                    f" • Threshold: {d.threshold or 'N/A'}\n"
                    f" • Light:     {d.light or 'N/A'}\n"
                    f" • Common:    {d.common or 'N/A'}\n"
                    f" • Strong:    {d.strong or 'N/A'}\n"
                    f" • Heavy:     {d.heavy or 'N/A'}\n"
                    f" Notes: {d.notes or 'None'}"
                )
                ctk.CTkLabel(dose_box, text=dose_txt, font=ctk.CTkFont(size=12, family="Courier"), justify="left").pack(anchor="w", padx=10, pady=(0, 8))

        # Reagents
        if sub.testing_reagents:
            reag_box = ctk.CTkFrame(self.sub_detail, fg_color="#0f172a")
            reag_box.pack(fill="x", padx=15, pady=8)
            ctk.CTkLabel(reag_box, text="🧪 Chemical Reagent Testing Reactions", font=ctk.CTkFont(size=14, weight="bold"), text_color="#22c55e").pack(anchor="w", padx=10, pady=(8, 4))
            reag_txt = "\n".join([f" • {k}: {v}" for k, v in sub.testing_reagents.items()])
            ctk.CTkLabel(reag_box, text=reag_txt, font=ctk.CTkFont(size=12), justify="left", text_color="#cbd5e1").pack(anchor="w", padx=10, pady=(0, 8))

    # --- 2. Master Catalog View (560+) ---
    def _build_catalog_view(self):
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.views["catalog"] = view
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=1)

        # Header & search
        hdr = ctk.CTkLabel(view, text="📚 Master Erowid Catalog (560+ Substances)", font=ctk.CTkFont(size=18, weight="bold"))
        hdr.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="w")

        search_frame = ctk.CTkFrame(view, fg_color="transparent")
        search_frame.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        search_frame.grid_columnconfigure(0, weight=1)

        self.cat_search_entry = ctk.CTkEntry(search_frame, placeholder_text="Search 560+ substances (e.g. DMT, 2C-B, Ketamine, Salvia, Spice)...")
        self.cat_search_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.cat_search_entry.bind("<Return>", lambda e: self._do_catalog_search())

        btn_search = ctk.CTkButton(search_frame, text="Search Catalog", command=self._do_catalog_search)
        btn_search.grid(row=0, column=1)

        # Scrollable list
        self.cat_scroll = ctk.CTkScrollableFrame(view, fg_color="#1e293b")
        self.cat_scroll.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")

        self._do_catalog_search()

    def _do_catalog_search(self):
        for w in self.cat_scroll.winfo_children():
            w.destroy()

        q = self.cat_search_entry.get().strip() if hasattr(self, "cat_search_entry") else ""
        results = self.db.search_catalog(q, limit=40)

        if not results:
            ctk.CTkLabel(self.cat_scroll, text="No substances found matching query.", text_color="#94a3b8").pack(pady=20)
            return

        for r in results:
            card = ctk.CTkFrame(self.cat_scroll, fg_color="#0f172a")
            card.pack(fill="x", padx=10, pady=6)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(8, 2))

            ctk.CTkLabel(top_row, text=r["name"], font=ctk.CTkFont(size=15, weight="bold"), text_color="#38bdf8").pack(side="left")
            ctk.CTkLabel(top_row, text=f"slug: {r['slug']}", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="right")

            if r["description"]:
                ctk.CTkLabel(card, text=r["description"], font=ctk.CTkFont(size=12), text_color="#cbd5e1", wraplength=700, justify="left").pack(anchor="w", padx=10, pady=(0, 4))

            # Category badges
            cats = list(r["categories"].keys())
            cat_summary = f"Categories ({len(cats)}): {', '.join(cats[:6])}" + (f" (+{len(cats)-6} more)" if len(cats) > 6 else "")
            ctk.CTkLabel(card, text=cat_summary, font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w", padx=10, pady=(0, 6))

            # Action button
            btn_harvest = ctk.CTkButton(
                card,
                text=f"Harvest Report IDs ({r['slug']})",
                height=26,
                fg_color="#334155",
                hover_color="#0284c7",
                command=lambda s=r["slug"]: self._harvest_substance(s)
            )
            btn_harvest.pack(anchor="e", padx=10, pady=(0, 8))

    def _harvest_substance(self, slug: str):
        def _bg():
            count = self.scraper.harvest_substance_reports(slug, self.db)
            self._update_sidebar_stats()
            # Show popup or update UI
            print(f"Harvested {count} report IDs for {slug}")
        threading.Thread(target=_bg, daemon=True).start()

    # --- 3. Interaction Checker View ---
    def _build_interactions_view(self):
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.views["interactions"] = view
        view.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(view, text="⚠️ Multi-Drug Interaction & Lethality Evaluator", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(view, text="Evaluate dangerous or lethal synergistic risks (e.g. respiratory arrest, Serotonin Syndrome, cocaethylene).", text_color="#94a3b8").pack(anchor="w", padx=20, pady=(0, 15))

        input_box = ctk.CTkFrame(view, fg_color="#1e293b")
        input_box.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(input_box, text="Enter 2 or more substances (comma-separated):", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", padx=15, pady=(12, 4))
        # Quick add chips row
        quick_frame = ctk.CTkFrame(input_box, fg_color="transparent")
        quick_frame.pack(fill="x", padx=15, pady=(8, 4))
        ctk.CTkLabel(quick_frame, text="Quick Add:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8").pack(side="left", padx=(0, 6))

        quick_subs = ["Alcohol", "MDMA", "Cannabis", "Cocaine", "Ketamine", "Alprazolam", "Oxycodone", "LSD", "Psilocybin", "Amphetamine", "DXM", "SSRI"]
        for qs in quick_subs:
            btn_q = ctk.CTkButton(
                quick_frame, text=f"+ {qs}", width=70, height=22, fg_color="#334155", hover_color="#0284c7",
                command=lambda s=qs: self._append_combo_sub(s)
            )
            btn_q.pack(side="left", padx=3)

        btn_row = ctk.CTkFrame(input_box, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(8, 15))

        btn_eval = ctk.CTkButton(btn_row, text="⚡ Check Combination Risks", fg_color="#0284c7", command=self._check_combo)
        btn_eval.pack(side="left", padx=(0, 10))

        btn_clear = ctk.CTkButton(btn_row, text="Clear All", width=80, fg_color="#334155", hover_color="#ef4444", command=self._clear_combo)
        btn_clear.pack(side="left")

        self.combo_result_frame = ctk.CTkScrollableFrame(view, fg_color="#1e293b", height=350)
        self.combo_result_frame.pack(fill="both", expand=True, padx=20, pady=10)

    def _append_combo_sub(self, name: str):
        cur = self.combo_entry.get().strip()
        items = [s.strip() for s in cur.split(",") if s.strip()]
        if name not in items:
            items.append(name)
            self.combo_entry.delete(0, "end")
            self.combo_entry.insert(0, ", ".join(items))
            if len(items) >= 2:
                self._check_combo()

    def _clear_combo(self):
        self.combo_entry.delete(0, "end")
        for w in self.combo_result_frame.winfo_children():
            w.destroy()

    def _check_combo(self):
        for w in self.combo_result_frame.winfo_children():
            w.destroy()

        val = self.combo_entry.get().strip()
        subs = [s.strip() for s in val.split(",") if s.strip()]
        if len(subs) < 2:
            ctk.CTkLabel(self.combo_result_frame, text="Please enter at least 2 substances separated by commas (e.g. Alcohol, Xanax)", text_color="#f87171").pack(pady=20)
            return

        res = self.engine.evaluate_combination(subs)
        risk = res["overall_risk"]

        color_map = {"DEADLY": "#ef4444", "DANGEROUS": "#f97316", "CAUTION": "#eab308", "LOW_OR_UNKNOWN": "#22c55e"}
        badge_color = color_map.get(risk, "#38bdf8")

        risk_hdr = ctk.CTkFrame(self.combo_result_frame, fg_color="#0f172a")
        risk_hdr.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(risk_hdr, text=f"OVERALL RISK LEVEL: {risk}", font=ctk.CTkFont(size=18, weight="bold"), text_color=badge_color).pack(padx=15, pady=10)

        if not res["interactions"]:
            ctk.CTkLabel(self.combo_result_frame, text="No critical contraindications recorded for this specific pairing in the database.\nAlways exercise caution when combining psychoactive substances.", text_color="#94a3b8").pack(pady=10)
            return

        for inter in res["interactions"]:
            ibox = ctk.CTkFrame(self.combo_result_frame, fg_color="#0f172a", border_width=1, border_color=badge_color)
            ibox.pack(fill="x", padx=10, pady=8)

            pair_title = f"⚡ {inter['substance_a'].upper()} + {inter['substance_b'].upper()} [{inter['risk_level']}]"
            ctk.CTkLabel(ibox, text=pair_title, font=ctk.CTkFont(size=14, weight="bold"), text_color=badge_color).pack(anchor="w", padx=10, pady=(8, 2))
            ctk.CTkLabel(ibox, text=f"Mechanism: {inter['mechanism']}", font=ctk.CTkFont(size=12), text_color="#fca5a5", wraplength=700, justify="left").pack(anchor="w", padx=10, pady=2)
            ctk.CTkLabel(ibox, text=f"Advice: {inter['harm_reduction_advice']}", font=ctk.CTkFont(size=12), text_color="#cbd5e1", wraplength=700, justify="left").pack(anchor="w", padx=10, pady=(2, 8))

    # --- 4. Dosage Evaluator View ---
    def _build_dosage_view(self):
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.views["dosage"] = view
        view.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(view, text="⚖️ Dosage Safety Calculator", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=20, pady=(15, 5))
        ctk.CTkLabel(view, text="Compare intended dose amount against established Erowid clinical thresholds and overdose boundaries.", text_color="#94a3b8").pack(anchor="w", padx=20, pady=(0, 15))

        calc_box = ctk.CTkFrame(view, fg_color="#1e293b")
        calc_box.pack(fill="x", padx=20, pady=10)

        # Quick dose presets
        quick_dose_row = ctk.CTkFrame(calc_box, fg_color="transparent")
        quick_dose_row.pack(fill="x", padx=15, pady=(8, 0))
        ctk.CTkLabel(quick_dose_row, text="Quick Select:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#38bdf8").pack(side="left", padx=(0, 6))

        presets = [
            ("MDMA", "120", "mg"),
            ("Ketamine", "60", "mg"),
            ("Psilocybin Mushrooms", "2.0", "g"),
            ("LSD", "100", "ug"),
            ("Alprazolam", "0.5", "mg"),
            ("Cocaine", "50", "mg"),
            ("DXM", "250", "mg"),
            ("2C-B", "15", "mg"),
        ]
        for pname, pamt, punit in presets:
            btn_p = ctk.CTkButton(
                quick_dose_row, text=f"{pname.split()[0]} ({pamt}{punit})", width=95, height=22, fg_color="#334155", hover_color="#0284c7",
                command=lambda n=pname, a=pamt, u=punit: self._set_dose_preset(n, a, u)
            )
            btn_p.pack(side="left", padx=3)

        # Fields
        f_row = ctk.CTkFrame(calc_box, fg_color="transparent")
        f_row.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(f_row, text="Substance:").pack(side="left", padx=5)
        self.dose_sub_entry = ctk.CTkEntry(f_row, width=150, placeholder_text="e.g. mdma, ketamine")
        self.dose_sub_entry.pack(side="left", padx=5)

        ctk.CTkLabel(f_row, text="Amount:").pack(side="left", padx=5)
        self.dose_amt_entry = ctk.CTkEntry(f_row, width=80, placeholder_text="e.g. 200")
        self.dose_amt_entry.pack(side="left", padx=5)

        ctk.CTkLabel(f_row, text="Unit:").pack(side="left", padx=5)
        self.dose_unit_menu = ctk.CTkOptionMenu(f_row, values=["mg", "g", "ug", "ml"], width=80)
        self.dose_unit_menu.pack(side="left", padx=5)

        btn_calc = ctk.CTkButton(f_row, text="Assess Safety", command=self._eval_dose)
        btn_calc.pack(side="left", padx=15)

        self.dose_res_box = ctk.CTkFrame(view, fg_color="#1e293b", height=300)
        self.dose_res_box.pack(fill="both", expand=True, padx=20, pady=10)

    def _set_dose_preset(self, name: str, amt: str, unit: str):
        self.dose_sub_entry.delete(0, "end")
        self.dose_sub_entry.insert(0, name)
        self.dose_amt_entry.delete(0, "end")
        self.dose_amt_entry.insert(0, amt)
        self.dose_unit_menu.set(unit)
        self._eval_dose()

    def _eval_dose(self):
        for w in self.dose_res_box.winfo_children():
            w.destroy()

        sub = self.dose_sub_entry.get().strip()
        amt_str = self.dose_amt_entry.get().strip()
        unit = self.dose_unit_menu.get()

        try:
            amt = float(amt_str)
        except ValueError:
            ctk.CTkLabel(self.dose_res_box, text="Please enter a valid numeric dose amount.", text_color="#f87171").pack(pady=20)
            return

        res = self.engine.evaluate_dosage(sub, amt, unit=unit)
        if not res.get("found"):
            ctk.CTkLabel(self.dose_res_box, text=res.get("message", "Substance not found."), text_color="#f87171").pack(pady=20)
            return

        status = res["status"]
        color = "#ef4444" if "OVERDOSE" in status or "HEAVY" in status else ("#eab308" if "STRONG" in status else "#22c55e")

        card = ctk.CTkFrame(self.dose_res_box, fg_color="#0f172a", border_width=1, border_color=color)
        card.pack(fill="x", padx=15, pady=15)

        ctk.CTkLabel(card, text=f"DOSAGE ASSESSMENT: {status}", font=ctk.CTkFont(size=16, weight="bold"), text_color=color).pack(anchor="w", padx=15, pady=(10, 4))
        bounds_txt = (
            f"Input: {res['input_dose']} ({res['route']})\n"
            f" • Threshold: {res.get('threshold') or 'N/A'}\n"
            f" • Light:     {res.get('light') or 'N/A'}\n"
            f" • Common:    {res.get('common') or 'N/A'}\n"
            f" • Heavy:     {res.get('heavy') or 'N/A'}\n"
            f" Notes: {res.get('notes') or 'N/A'}"
        )
        ctk.CTkLabel(card, text=bounds_txt, font=ctk.CTkFont(size=12, family="Courier"), justify="left").pack(anchor="w", padx=15, pady=4)
        if res.get("harm_summary"):
            ctk.CTkLabel(card, text=f"Safety Tips: {res['harm_summary']}", font=ctk.CTkFont(size=12), text_color="#cbd5e1", wraplength=650, justify="left").pack(anchor="w", padx=15, pady=(4, 10))

    # --- 5. Experience Reports Vault View ---
    def _build_vault_view(self):
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.views["vault"] = view
        view.grid_columnconfigure(0, weight=1)
        view.grid_rowconfigure(2, weight=1)

        # Top On-Demand Reader Frame
        top_fetch = ctk.CTkFrame(view, fg_color="#1e293b")
        top_fetch.grid(row=0, column=0, padx=20, pady=(15, 5), sticky="ew")

        ctk.CTkLabel(top_fetch, text="⚡ Universal Live Reader (Fetch ANY Erowid ID 1 - 150,000):", font=ctk.CTkFont(size=13, weight="bold"), text_color="#38bdf8").pack(side="left", padx=10, pady=8)
        self.quick_id_entry = ctk.CTkEntry(top_fetch, width=110, placeholder_text="e.g. 10000")
        self.quick_id_entry.pack(side="left", padx=5, pady=8)
        btn_quick = ctk.CTkButton(top_fetch, text="Fetch & Read Live", command=self._quick_fetch)
        btn_quick.pack(side="left", padx=10, pady=8)

        # Search Bar
        search_bar = ctk.CTkFrame(view, fg_color="transparent")
        search_bar.grid(row=1, column=0, padx=20, pady=5, sticky="ew")
        search_bar.grid_columnconfigure(0, weight=1)

        self.vault_q_entry = ctk.CTkEntry(search_bar, placeholder_text="Keyword query in local vault (e.g. 'overdose', 'seizure', 'recovery')...")
        self.vault_q_entry.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.vault_q_entry.bind("<Return>", lambda e: self._do_vault_search())

        btn_search = ctk.CTkButton(search_bar, text="Search Vault", command=self._do_vault_search)
        btn_search.grid(row=0, column=1)

        # Results area
        self.vault_scroll = ctk.CTkScrollableFrame(view, fg_color="#1e293b")
        self.vault_scroll.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")

        self._do_vault_search()

    def _do_vault_search(self):
        for w in self.vault_scroll.winfo_children():
            w.destroy()

        q = self.vault_q_entry.get().strip() if hasattr(self, "vault_q_entry") else ""
        results = self.db.search_experiences(query=q, limit=25)

        if not results:
            ctk.CTkLabel(self.vault_scroll, text="No reports found matching query in local database.", text_color="#94a3b8").pack(pady=20)
            return

        for r in results:
            card = ctk.CTkFrame(self.vault_scroll, fg_color="#0f172a")
            card.pack(fill="x", padx=10, pady=6)

            hdr = ctk.CTkFrame(card, fg_color="transparent")
            hdr.pack(fill="x", padx=10, pady=(6, 2))
            ctk.CTkLabel(hdr, text=f"Exp #{r['id']}: {r['title']}", font=ctk.CTkFont(size=14, weight="bold"), text_color="#fff").pack(side="left")
            ctk.CTkLabel(hdr, text=f"Year: {r['exp_year'] or 'Unknown'}", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(side="right")

            meta = f"Substance: {r['substance_summary']} | Author: {r['author']} | Weight: {r['body_weight'] or 'N/A'}"
            ctk.CTkLabel(card, text=meta, font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(anchor="w", padx=10)

            if r.get("harm_flags"):
                ctk.CTkLabel(card, text=f"Harm Flags: {', '.join(r['harm_flags'])}", font=ctk.CTkFont(size=11, weight="bold"), text_color="#ef4444").pack(anchor="w", padx=10, pady=2)

            ctk.CTkLabel(card, text=r["snippet"][:150] + "...", font=ctk.CTkFont(size=12), text_color="#cbd5e1", wraplength=700, justify="left").pack(anchor="w", padx=10, pady=(2, 6))

            btn_read = ctk.CTkButton(card, text="Read Full Report", height=24, fg_color="#334155", hover_color="#0284c7", command=lambda eid=r["id"]: self._open_report_popup(eid))
            btn_read.pack(anchor="e", padx=10, pady=(0, 6))

    def _quick_fetch(self):
        id_str = self.quick_id_entry.get().strip()
        try:
            eid = int(id_str)
            self._open_report_popup(eid)
        except ValueError:
            pass

    def _open_report_popup(self, exp_id: int):
        # Open separate Toplevel window
        pop = ctk.CTkToplevel(self.root)
        pop.title(f"Exp #{exp_id} - Erowid Experience Reader")
        pop.geometry("800x650")

        scroll = ctk.CTkScrollableFrame(pop, fg_color="#0f172a")
        scroll.pack(fill="both", expand=True, padx=15, pady=15)

        loading = ctk.CTkLabel(scroll, text=f"Retrieving Exp #{exp_id} from archive...", font=ctk.CTkFont(size=14))
        loading.pack(pady=20)
        pop.update()

        def _fetch_thread():
            exp = self.db.get_experience(exp_id)
            if not exp:
                exp = self.scraper.fetch_and_save_experience(exp_id, self.db)
                self._update_sidebar_stats()

            loading.destroy()
            if not exp:
                ctk.CTkLabel(scroll, text=f"Could not retrieve Exp #{exp_id}. Verify ID exists on Erowid.", text_color="#ef4444").pack(pady=20)
                return

            ctk.CTkLabel(scroll, text=f"Exp #{exp.id}: {exp.title}", font=ctk.CTkFont(size=18, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=10, pady=(10, 4))
            meta = f"Substance: {exp.substance_summary} | Author: {exp.author} | Year: {exp.exp_year or 'N/A'} | Weight: {exp.body_weight or 'N/A'}"
            ctk.CTkLabel(scroll, text=meta, font=ctk.CTkFont(size=12), text_color="#94a3b8").pack(anchor="w", padx=10, pady=(0, 10))

            if exp.harm_flags:
                ctk.CTkLabel(scroll, text=f"⚠️ Harm Flags: {', '.join(exp.harm_flags)}", font=ctk.CTkFont(size=12, weight="bold"), text_color="#ef4444").pack(anchor="w", padx=10, pady=4)

            if exp.doses:
                dose_txt = "Reported Doses:\n" + "\n".join([f" • {d.substance}: {d.amount or ''} {d.unit or ''} ({d.method or 'Oral'})" for d in exp.doses])
                ctk.CTkLabel(scroll, text=dose_txt, font=ctk.CTkFont(size=11, family="Courier"), justify="left").pack(anchor="w", padx=10, pady=4)

            ctk.CTkLabel(scroll, text="[ Report Narrative ]", font=ctk.CTkFont(size=14, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=10, pady=(10, 4))
            ctk.CTkLabel(scroll, text=exp.narrative, font=ctk.CTkFont(size=13), text_color="#f8fafc", wraplength=720, justify="left").pack(anchor="w", padx=10, pady=(0, 20))

        threading.Thread(target=_fetch_thread, daemon=True).start()

    # --- 6. Emergency Protocols View ---
    def _build_emergency_view(self):
        view = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        self.views["emergency"] = view

        ctk.CTkLabel(view, text="🚨 Overdose Emergency & Testing Protocols", font=ctk.CTkFont(size=18, weight="bold"), text_color="#ef4444").pack(anchor="w", padx=20, pady=(15, 5))

        banner = ctk.CTkFrame(view, fg_color="#450a0a", border_width=1, border_color="#ef4444")
        banner.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(banner, text="OVERDOSE EMERGENCY: CALL 911 / 999 IMMEDIATELY", font=ctk.CTkFont(size=15, weight="bold"), text_color="#f87171").pack(anchor="w", padx=15, pady=(10, 4))
        ctk.CTkLabel(banner, text="Good Samaritan laws shield callers from drug possession charges in most jurisdictions.\nIf opioids are suspected, administer Naloxone (Narcan) nasal spray immediately.", font=ctk.CTkFont(size=12), text_color="#fecaca", justify="left").pack(anchor="w", padx=15, pady=(0, 10))

        # 4 steps
        steps_box = ctk.CTkFrame(view, fg_color="#1e293b")
        steps_box.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(steps_box, text="4-Step Life-Saving Overdose Protocol", font=ctk.CTkFont(size=15, weight="bold"), text_color="#38bdf8").pack(anchor="w", padx=15, pady=(10, 4))
        steps_txt = (
            "1. Call 911 / 999: State clearly: 'A person is unresponsive and not breathing.'\n\n"
            "2. Administer Naloxone (Narcan): Spray into one nostril. If no response after 2-3 mins, give a second dose.\n\n"
            "3. Rescue Breathing / CPR: If not breathing, tilt head back, pinch nose, and deliver 1 breath every 5 seconds. If no pulse, start chest compressions.\n\n"
            "4. Recovery Position: Roll person onto their side with knee bent to prevent choking on vomit if unconscious."
        )
        ctk.CTkLabel(steps_box, text=steps_txt, font=ctk.CTkFont(size=12), text_color="#cbd5e1", wraplength=700, justify="left").pack(anchor="w", padx=15, pady=(0, 15))

    def run(self):
        self.root.mainloop()


def launch_native_gui(db_path: str = "data/erowid_safedb.db"):
    app = SafeDBNativeApp(db_path)
    app.run()


if __name__ == "__main__":
    launch_native_gui()
