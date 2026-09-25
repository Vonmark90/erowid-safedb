"""
Harm Reduction & Clinical Risk Analytics Engine.
Evaluates multi-drug interactions, analyzes dosage safety, and provides emergency protocols.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from erowid_safedb.models import DrugInteraction, Substance, DosageInfo
from erowid_safedb.db import Database


class HarmReductionEngine:
    """Core harm-reduction decision support and safety analysis engine."""

    RISK_SEVERITY_ORDER = {
        "DEADLY": 5,
        "DANGEROUS": 4,
        "UNSAFE": 3,
        "CAUTION": 2,
        "LOW_RISK_SYNERGY": 1,
        "LOW_RISK_NO_SYNERGY": 0
    }

    RISK_COLORS = {
        "DEADLY": "\033[91m",        # Bright Red
        "DANGEROUS": "\033[31m",     # Red
        "UNSAFE": "\033[33m",        # Yellow/Orange
        "CAUTION": "\033[93m",       # Light Yellow
        "LOW_RISK_SYNERGY": "\033[94m", # Blue
        "LOW_RISK_NO_SYNERGY": "\033[92m", # Green
    }
    RESET_COLOR = "\033[0m"

    def __init__(self, db: Database):
        self.db = db

    def evaluate_combination(self, substances: List[str]) -> Dict[str, Any]:
        """
        Analyzes pairwise interactions across all input substances.
        Returns highest overall risk tier, detailed pairs, and action items.
        """
        clean_subs = [s.strip() for s in substances if s.strip()]
        if len(clean_subs) < 2:
            return {
                "substances": clean_subs,
                "overall_risk": "INSUFFICIENT_SUBSTANCES",
                "max_severity": 0,
                "interactions": [],
                "warnings": ["Please provide at least 2 substances to evaluate combination risks."]
            }

        interactions = []
        max_severity = 0
        overall_risk = "UNKNOWN"

        for i in range(len(clean_subs)):
            for j in range(i + 1, len(clean_subs)):
                sub_a = clean_subs[i]
                sub_b = clean_subs[j]

                # Check database
                inter = self.db.get_interaction(sub_a, sub_b)
                if inter:
                    sev = self.RISK_SEVERITY_ORDER.get(inter.risk_level.upper(), 0)
                    if sev > max_severity:
                        max_severity = sev
                        overall_risk = inter.risk_level.upper()
                    interactions.append(inter)
                else:
                    # Generic heuristic based on categories
                    sub_a_obj = self.db.get_substance(sub_a)
                    sub_b_obj = self.db.get_substance(sub_b)
                    heur_inter = self._heuristic_interaction(sub_a, sub_b, sub_a_obj, sub_b_obj)
                    if heur_inter:
                        sev = self.RISK_SEVERITY_ORDER.get(heur_inter.risk_level.upper(), 0)
                        if sev > max_severity:
                            max_severity = sev
                            overall_risk = heur_inter.risk_level.upper()
                        interactions.append(heur_inter)

        return {
            "substances": clean_subs,
            "overall_risk": overall_risk if interactions else "LOW_OR_UNKNOWN",
            "max_severity": max_severity,
            "interactions": [
                {
                    "substance_a": inter.substance_a,
                    "substance_b": inter.substance_b,
                    "risk_level": inter.risk_level,
                    "mechanism": inter.mechanism,
                    "harm_reduction_advice": inter.harm_reduction_advice
                } for inter in interactions
            ],
            "is_emergency_risk": max_severity >= 4
        }

    def _heuristic_interaction(
        self,
        name_a: str,
        name_b: str,
        obj_a: Optional[Substance],
        obj_b: Optional[Substance]
    ) -> Optional[DrugInteraction]:
        """Provides pharmacological fallbacks if exact pair isn't hardcoded."""
        cat_a = (obj_a.category if obj_a else "").lower()
        cat_b = (obj_b.category if obj_b else "").lower()

        # Both CNS Depressants (e.g. Alcohol, Benzos, Opioids, GHB)
        depressant_terms = ["depressant", "benzodiazepine", "opioid", "barbiturate", "alcohol", "ghb"]
        is_a_dep = any(t in cat_a or t in name_a.lower() for t in depressant_terms)
        is_b_dep = any(t in cat_b or t in name_b.lower() for t in depressant_terms)

        if is_a_dep and is_b_dep:
            return DrugInteraction(
                substance_a=name_a,
                substance_b=name_b,
                risk_level="DEADLY",
                mechanism="Additive central nervous system depression. Synergistically suppresses respiratory drive, leading to respiratory arrest and fatal overdose.",
                harm_reduction_advice="DO NOT COMBINE. Keep Naloxone on hand if opioids are involved. If someone becomes unresponsive or starts snoring unusually, call emergency services immediately."
            )

        # Stimulant + Stimulant
        stim_terms = ["stimulant", "amphetamine", "cocaine", "caffeine"]
        is_a_stim = any(t in cat_a or t in name_a.lower() for t in stim_terms)
        is_b_stim = any(t in cat_b or t in name_b.lower() for t in stim_terms)

        if is_a_stim and is_b_stim:
            return DrugInteraction(
                substance_a=name_a,
                substance_b=name_b,
                risk_level="DANGEROUS",
                mechanism="Compounded cardiovascular strain: severe tachycardia, hypertension, vasoconstriction, and elevated risk of cardiac arrhythmias or stroke.",
                harm_reduction_advice="Avoid combining stimulants. Monitor heart rate and temperature. Stay hydrated with electrolyte fluids."
            )

        # MAOI + Serotonergic
        maoi_terms = ["maoi", "ayahuasca", "harmine", "harmaline", "syrian rue", "selegiline"]
        serotonergic_terms = ["mdma", "mda", "dxm", "tramadol", "ssri", "snri"]
        is_a_maoi = any(t in cat_a or t in name_a.lower() for t in maoi_terms)
        is_b_maoi = any(t in cat_b or t in name_b.lower() for t in maoi_terms)
        is_a_sero = any(t in cat_a or t in name_a.lower() for t in serotonergic_terms)
        is_b_sero = any(t in cat_b or t in name_b.lower() for t in serotonergic_terms)

        if (is_a_maoi and is_b_sero) or (is_b_maoi and is_a_sero):
            return DrugInteraction(
                substance_a=name_a,
                substance_b=name_b,
                risk_level="DEADLY",
                mechanism="Extreme Serotonin Syndrome. MAO inhibition blocks serotonin breakdown while the other agent floods serotonin synapses, inducing lethal hyperthermia and seizures.",
                harm_reduction_advice="NEVER COMBINE. This combination can be rapidly fatal. Requires emergency medical hospitalization if ingested."
            )

        return None

    def evaluate_dosage(
        self,
        substance_name: str,
        amount_val: float,
        unit: str = "mg",
        route: str = "Oral"
    ) -> Dict[str, Any]:
        """
        Compares an input dose against Erowid standard dosage boundaries.
        Returns safety assessment, guideline brackets, and warning indicators.
        """
        sub = self.db.get_substance(substance_name)
        if not sub:
            return {
                "substance": substance_name,
                "found": False,
                "message": f"Substance '{substance_name}' not found in database."
            }

        # Find dosage for route
        matching_dose = None
        for d in sub.dosages:
            if d.route.lower() == route.lower():
                matching_dose = d
                break
        if not matching_dose and sub.dosages:
            matching_dose = sub.dosages[0]

        if not matching_dose:
            return {
                "substance": sub.name,
                "found": True,
                "has_dose_chart": False,
                "message": "No dosage guidelines documented for this route."
            }

        # Parse numerical bounds from strings (e.g. "75 - 125 mg", "200 + mg")
        def parse_numbers(s: Optional[str]) -> List[float]:
            if not s:
                return []
            nums = []
            for token in re.findall(r"([0-9]+(?:\.[0-9]+)?)", s):
                try:
                    nums.append(float(token))
                except ValueError:
                    pass
            return nums

        thresh_nums = parse_numbers(matching_dose.threshold)
        common_nums = parse_numbers(matching_dose.common)
        heavy_nums = parse_numbers(matching_dose.heavy)

        status = "COMMON"
        risk_flag = "NORMAL"

        if heavy_nums and amount_val >= max(heavy_nums):
            status = "HEAVY / OVERDOSE HAZARD"
            risk_flag = "DANGEROUS"
        elif common_nums and amount_val > max(common_nums):
            status = "STRONG"
            risk_flag = "ELEVATED"
        elif common_nums and min(common_nums) <= amount_val <= max(common_nums):
            status = "COMMON / TYPICAL"
            risk_flag = "STANDARD"
        elif thresh_nums and amount_val < min(thresh_nums):
            status = "SUB-THRESHOLD"
            risk_flag = "LOW"
        else:
            status = "LIGHT"
            risk_flag = "STANDARD"

        return {
            "substance": sub.name,
            "found": True,
            "route": matching_dose.route,
            "input_dose": f"{amount_val} {unit}",
            "status": status,
            "risk_flag": risk_flag,
            "threshold": matching_dose.threshold,
            "light": matching_dose.light,
            "common": matching_dose.common,
            "strong": matching_dose.strong,
            "heavy": matching_dose.heavy,
            "notes": matching_dose.notes,
            "harm_summary": sub.harm_summary,
            "toxicity_notes": sub.toxicity_notes
        }

    @staticmethod
    def get_emergency_protocol() -> Dict[str, Any]:
        """Provides life-saving overdose response and crisis intervention steps."""
        return {
            "overdose_signs": [
                "Slow, shallow, or stopped breathing (under 10 breaths/min)",
                "Choking, gurgling, or 'snoring' sounds ('death rattle')",
                "Blue, grey, or ashen lips, skin, or fingernails",
                "Pinpoint pupils (opioids) or extremely dilated pupils",
                "Unresponsive to sternum rub or yelling",
                "Seizures, uncontrolled jerking, or extreme overheating (104°F+)"
            ],
            "action_steps": [
                {
                    "step": 1,
                    "title": "Call 911 / Emergency Services Immediately",
                    "instruction": "Tell the dispatcher: 'Someone is unresponsive and not breathing.' You do not have to confess to crimes over the phone. Most US states and many countries have Good Samaritan Laws protecting callers from drug possession charges."
                },
                {
                    "step": 2,
                    "title": "Administer Naloxone (Narcan) if Opioids are Suspected",
                    "instruction": "Spray Narcan into one nostril. If no response after 2 to 3 minutes, administer a second dose in the other nostril. Naloxone only reverses opioids, but it is harmless if opioids are not present."
                },
                {
                    "step": 3,
                    "title": "Perform Rescue Breathing / CPR",
                    "instruction": "If breathing has stopped or is gasping: tilt head back, pinch nose, give 1 breath every 5 seconds. If no pulse, perform chest compressions (100-120 bpm to the rhythm of 'Stayin Alive')."
                },
                {
                    "step": 4,
                    "title": "Place in the Recovery Position",
                    "instruction": "Roll the person onto their side with top knee bent to support them, and rest their head on their arm. This prevents choking on vomit if they are unconscious."
                }
            ],
            "helplines": [
                {"name": "SAMHSA National Helpline", "contact": "1-800-662-4357", "details": "Free, confidential 24/7 treatment referral and support (US)"},
                {"name": "Never Use Alone", "contact": "1-877-696-1996", "details": "Toll-free virtual spotter service across the US; will dispatch EMS if you become unresponsive"},
                {"name": "Crisis Text Line", "contact": "Text HOME to 741741", "details": "Free 24/7 crisis support via text"},
                {"name": "Substance Abuse and Mental Health (Canada)", "contact": "1-866-585-0445", "details": "Wellness Together Canada, 24/7 free support"},
                {"name": "FRANK (UK)", "contact": "0300 123 6600", "details": "Honest, confidential drug info and helpline (UK)"}
            ]
        }

    @staticmethod
    def get_testing_guide() -> Dict[str, Any]:
        """Provides instructions on reagent test kits and fentanyl test strips."""
        return {
            "reagent_kits": [
                {"name": "Marquis Reagent", "primary_use": "MDMA, Amphetamine, Meth, 2C-B, Opiates", "notes": "Turns dark purple/black for MDMA; orange/brown for amphetamines; green for 2C-B."},
                {"name": "Mecke Reagent", "primary_use": "MDMA, Opiates, DXM", "notes": "Turns blue-green to dark blue for MDMA; yellow to dark green for DXM."},
                {"name": "Simon's Reagent (A+B)", "primary_use": "Distinguishes secondary amines (MDMA vs MDA, Meth vs Amphetamine)", "notes": "Turns bright cobalt blue for MDMA/Meth; no reaction for MDA/Amphetamine."},
                {"name": "Ehrlich Reagent", "primary_use": "Indoles (LSD, DMT, Psilocybin)", "notes": "Turns purple/pink for real LSD. NBOMe compounds DO NOT react with Ehrlich (if it doesn't turn purple, do not ingest)."},
                {"name": "Froehde Reagent", "primary_use": "Benzos, Opioids, 2C compounds", "notes": "Useful confirmation test for MDMA, 2C-B, and distinguishing morphine from other opiates."}
            ],
            "fentanyl_strip_protocol": [
                "Dissolve the ENTIRE sample in water before consumption (the chocolate chip cookie effect means fentanyl can be hidden in one small spot).",
                "Dilution ratio: 10 mg of powder per 1 teaspoon (5 ml) of water. For meth or MDMA, dilute further (1 mg per ml) to avoid false positives.",
                "Dip strip into the liquid for 15 seconds up to the MAX line (do not submerge past line).",
                "Place flat on non-absorbent surface for 2 to 5 minutes.",
                "Result: TWO LINES = NEGATIVE (safe). ONE LINE = POSITIVE (DANGER - Fentanyl detected! Do not consume)."
            ]
        }
