"""
HTML parsers for Erowid Experience Reports and Substance Vaults.
Extracts structured doses, demographics, narratives, and adverse harm signals.
"""

import re
import html
from typing import List, Dict, Tuple, Optional, Any
from erowid_safedb.models import (
    ExperienceReport,
    ExperienceDoseItem,
    AdverseEvent,
    Substance,
    DosageInfo,
    DurationInfo,
)


class ErowidExperienceParser:
    """Parses raw Erowid Experience HTML pages into structured ExperienceReport models."""

    # Symptom keyword matching table: (Symptom name, Severity, Regex pattern)
    SYMPTOM_PATTERNS = [
        ("respiratory_depression", "Life-Threatening", r"\b(stopped breathing|respiratory depression|respiratory arrest|blue lips|not breathing|shallow breath|gasping for air)\b"),
        ("cardiac_arrest", "Life-Threatening", r"\b(cardiac arrest|heart stopped|cpr|defibrillator|resuscitated)\b"),
        ("seizure", "Severe", r"\b(seizure|convulsions|convulsing|epileptic|tremors uncontrollably)\b"),
        ("serotonin_syndrome", "Severe", r"\b(serotonin syndrome|hyperpyrexia|clonus|hyperreflexia)\b"),
        ("hospitalization", "Severe", r"\b(hospital|emergency room|\ber\b|ambulance|paramedics|911|999|intensive care|icu|stomach pumped|admitted to hospital)\b"),
        ("overdose", "Severe", r"\b(overdose|overdosed|\bod\b|od'd|accidental od|massive overdose)\b"),
        ("naloxone_administered", "Severe", r"\b(naloxone|narcan)\b"),
        ("loss_of_consciousness", "Severe", r"\b(unconscious|blackout|passed out|lost consciousness|unresponsive|comatose|coma)\b"),
        ("psychosis", "Severe", r"\b(psychosis|psychotic break|psych ward|delusional|delusions of reference|schizophrenic episode)\b"),
        ("hyperthermia", "Moderate", r"\b(hyperthermia|overheating|fever|temperature of 10[0-9]|burning up|sweating profusely)\b"),
        ("tachycardia", "Moderate", r"\b(tachycardia|heart racing|pounding heart|arrhythmia|palpitations|heart rate 1[5-9][0-9]|heart rate 200)\b"),
        ("panic_attack", "Moderate", r"\b(panic attack|terror|extreme panic|thought i was dying|feeling of impending doom|freaking out completely)\b"),
        ("severe_vomiting", "Moderate", r"\b(severe vomiting|vomiting blood|dry heaving for hours|projectile vomiting)\b"),
        ("addiction_withdrawal", "Moderate", r"\b(addiction|withdrawal|severe cravings|physical dependence|detox|relapsed)\b"),
        ("paranoia", "Mild", r"\b(paranoia|paranoid|convinced people were watching|persecution)\b"),
        ("depersonalization", "Mild", r"\b(depersonalization|derealization|dissociation from reality|brain fog for weeks|hppd)\b"),
    ]

    @classmethod
    def clean_html_text(cls, text: str) -> str:
        """Strips HTML tags, normalizes whitespace, and unescapes HTML entities."""
        if not text:
            return ""
        # Strip HTML comments
        text = re.sub(r"<!--[\s\S]*?-->", "", text)
        # Replace <br> and <p> with newlines
        text = re.sub(r"<(?:br|br\s*/|p|/p|div|/div)>", "\n", text, flags=re.I)
        # Strip all other HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        # Normalize double/triple empty lines
        lines = [line.strip() for line in text.splitlines()]
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()

    @classmethod
    def parse_html(cls, html_content: str, fallback_id: Optional[int] = None) -> ExperienceReport:
        """Parses Erowid HTML into an ExperienceReport dataclass."""
        # 1. Experience ID
        exp_id = fallback_id or 0
        expid_match = re.search(r"ExpID:\s*(\d+)", html_content, re.I)
        if expid_match:
            exp_id = int(expid_match.group(1))
        elif not exp_id:
            id_url_match = re.search(r"ID=(\d+)", html_content)
            if id_url_match:
                exp_id = int(id_url_match.group(1))

        # 2. Title
        title = ""
        title_match = re.search(r'<div class="title">\s*([^<]+?)\s*</div>', html_content, re.I)
        if title_match:
            title = html.unescape(title_match.group(1).strip())
        else:
            title_meta = re.search(r"<title>\s*([^<]+?)\s*</title>", html_content, re.I)
            if title_meta:
                title = html.unescape(title_meta.group(1).strip())

        # 3. Substance Summary Header
        substance_summary = ""
        sub_match = re.search(r'<div class="substance">\s*([^<]+?)\s*</div>', html_content, re.I)
        if sub_match:
            substance_summary = html.unescape(sub_match.group(1).strip())

        # 4. Author
        author = "Anonymous"
        author_match = re.search(r'<div class="author">\s*by\s*<a[^>]*>([^<]+)</a>', html_content, re.I)
        if author_match:
            author = html.unescape(author_match.group(1).strip())
        else:
            # Check citation div
            citation_match = re.search(r'<div class="ts-citation">Citation:[^<]*?([A-Za-z0-9_\-\.\s]+)\.\s*"', html_content, re.I)
            if citation_match:
                author = html.unescape(citation_match.group(1).strip())

        # 5. Metadata: Exp Year, Gender, Age, Body Weight, Published Date
        exp_year = None
        year_match = re.search(r"Exp Year:\s*(\d{4})", html_content, re.I)
        if year_match:
            exp_year = int(year_match.group(1))

        gender = None
        gender_match = re.search(r"Gender:\s*([A-Za-z]+)", html_content, re.I)
        if gender_match:
            g = gender_match.group(1).strip().capitalize()
            if g in ["Male", "Female", "Other", "Nonbinary"]:
                gender = g

        age = None
        age_match = re.search(r"Age at time of experience:\s*([^<\n]+)", html_content, re.I)
        if age_match:
            age_str = age_match.group(1).strip()
            if "not given" not in age_str.lower():
                age = age_str

        pub_date = None
        pub_match = re.search(r"Published:\s*([A-Za-z0-9,\s]+?)(?:</td>|Views:|<)", html_content, re.I)
        if pub_match:
            pub_date = pub_match.group(1).strip()

        body_weight = None
        bw_match = re.search(r"<td[^>]*class=['\"]bodyweight-amount['\"][^>]*>([^<]+)</td>", html_content, re.I)
        if bw_match:
            body_weight = bw_match.group(1).strip()

        # 6. Doses Table
        doses: List[ExperienceDoseItem] = []
        # Find all rows in dosechart table
        dose_table_match = re.search(r"<table class=['\"]dosechart['\"][^>]*>([\s\S]*?)</table>", html_content, re.I)
        if dose_table_match:
            rows = re.findall(r"<tr[^>]*>([\s\S]*?)</tr>", dose_table_match.group(1), re.I)
            for row in rows:
                amount_m = re.search(r"class=['\"]dosechart-amount['\"][^>]*>([^<]+)", row, re.I)
                method_m = re.search(r"class=['\"]dosechart-method['\"][^>]*>([^<]+)", row, re.I)
                substance_m = re.search(r"class=['\"]dosechart-substance['\"][^>]*>(?:<a[^>]*>)?([^<]+)", row, re.I)
                form_m = re.search(r"class=['\"]dosechart-form['\"][^>]*>([^<]+)", row, re.I)

                if substance_m:
                    sub_name = html.unescape(substance_m.group(1).strip())
                    if sub_name and sub_name.lower() != "substance":
                        amt_str = html.unescape(amount_m.group(1).strip()) if amount_m else ""
                        mth_str = html.unescape(method_m.group(1).strip()) if method_m else ""
                        form_str = html.unescape(form_m.group(1).strip()) if form_m else ""

                        # Extract unit from amt_str (e.g. "120 mg" -> amt="120", unit="mg")
                        amt_clean = amt_str.replace("&nbsp;", "").strip()
                        unit = ""
                        num_part = amt_clean
                        unit_match = re.search(r"([0-9\.\-\–\s]+)\s*([A-Za-zμµ%]+)", amt_clean)
                        if unit_match:
                            num_part = unit_match.group(1).strip()
                            unit = unit_match.group(2).strip()

                        doses.append(ExperienceDoseItem(
                            substance=sub_name,
                            amount=num_part or None,
                            unit=unit or None,
                            method=mth_str.replace("&nbsp;", "").strip() or None,
                            form=form_str.replace("&nbsp;", "").strip() or None,
                        ))

        # If dose amount was missing in the table, try extracting from narrative timeline (e.g. "120mg-130mg lines", "15 mg oral")
        for d in doses:
            if not d.amount and html_content:
                timeline_dose_m = re.search(r"\b([0-9]+(?:\.[0-9]+)?(?:\s*-\s*[0-9]+(?:\.[0-9]+)?)?)\s*(mg|ug|µg|g|ml|drops|hits|pills|caps|lines)\b", html_content, re.I)
                if timeline_dose_m:
                    d.amount = timeline_dose_m.group(1).replace(" ", "")
                    d.unit = timeline_dose_m.group(2)

        # 7. Narrative Text
        narrative = ""
        # Primary container on Erowid is report-text-surround or between BODY comments
        surround_match = re.search(r'<div class="report-text-surround"[^>]*>([\s\S]*?)</div>\s*<!--\s*End\s+report-text-surround', html_content, re.I)
        if surround_match:
            raw_text = surround_match.group(1)
            # Remove text after explicit End Body comment if present
            raw_text = re.split(r"<!--\s*(?:End Body|BODY-STOP)\s*-->", raw_text, flags=re.I)[0]
            # Remove dosechart and footdata if nested inside
            raw_text = re.sub(r"<table[^>]*class=['\"](?:dosechart|bodyweight|footdata)['\"][^>]*>[\s\S]*?</table>", "", raw_text, flags=re.I)
            raw_text = re.sub(r"<!--\s*DoseChart\s*-->[\s\S]*?<!--\s*End DoseChart\s*-->", "", raw_text, flags=re.I)
            narrative = cls.clean_html_text(raw_text)
        else:
            # Fallback to <!-- BODY -->
            body_match = re.search(r'<!--\s*BODY\s*-->([\s\S]*?)<!--\s*(?:BODY-STOP|End Body)\s*-->', html_content, re.I)
            if body_match:
                narrative = cls.clean_html_text(body_match.group(1))
            else:
                # Fallback to cleaning stripped body
                narrative = cls.clean_html_text(html_content)

        # 8. Extract Adverse Events & Harm Flags from Narrative and Title
        adverse_events, harm_flags = cls.extract_harm_signals(f"{title}\n{substance_summary}\n{narrative}")

        # 9. Extract Categories / Tags from page or title
        tags = []
        for tag_candidate in ["Bad Trips", "Hospital", "Overdose", "Addiction & Habituation", "First Times", "Difficult Experiences", "Health Problems", "Train Wrecks & Trip Disasters", "Spiritual Experiences", "Glowing Experiences"]:
            if tag_candidate.lower() in html_content.lower() or tag_candidate.lower() in title.lower():
                tags.append(tag_candidate)

        # Ensure adverse flags map to tags
        for flag in harm_flags:
            if flag not in tags:
                tags.append(flag)

        word_count = len(narrative.split())
        url = f"https://www.erowid.org/experiences/exp.php?ID={exp_id}" if exp_id else None

        return ExperienceReport(
            id=exp_id,
            title=title,
            author=author,
            substance_summary=substance_summary,
            exp_year=exp_year,
            published_date=pub_date,
            gender=gender,
            age=age,
            body_weight=body_weight,
            narrative=narrative,
            doses=doses,
            tags=tags,
            adverse_events=adverse_events,
            harm_flags=harm_flags,
            word_count=word_count,
            url=url,
        )

    @classmethod
    def extract_harm_signals(cls, text: str) -> Tuple[List[AdverseEvent], List[str]]:
        """Scans text for clinical adverse events, extracts context excerpts, and assigns severity."""
        adverse_events = []
        harm_flags = set()
        seen_symptoms = set()

        # Split text into sentences for excerpt extraction
        sentences = re.split(r"(?<=[.!?])\s+", text)

        for symptom, severity, pattern in cls.SYMPTOM_PATTERNS:
            regex = re.compile(pattern, re.I)
            for sentence in sentences:
                if regex.search(sentence):
                    if symptom not in seen_symptoms:
                        seen_symptoms.add(symptom)
                        excerpt = sentence.strip()[:250]
                        adverse_events.append(AdverseEvent(
                            symptom=symptom,
                            severity=severity,
                            excerpt=excerpt
                        ))
                        # Create human-readable harm flag
                        flag_name = symptom.replace("_", " ").title()
                        harm_flags.add(flag_name)
                    break

        return adverse_events, sorted(list(harm_flags))


class ErowidSubstanceParser:
    """Parses Erowid Substance Vault dose and duration pages."""

    @classmethod
    def parse_dose_page(cls, html_content: str, substance_name: str) -> List[DosageInfo]:
        """Extracts oral, insufflated, or other dosage charts from substance dose pages."""
        dosages = []
        # Pattern for standard Erowid dosage table
        # Table with chart1 (heading like Oral MDMA Dosages) and chart5 (threshold, common, heavy)
        table_matches = re.finditer(r"<table[^>]*>([\s\S]*?)</table>", html_content, re.I)
        for table_m in table_matches:
            table_html = table_m.group(1)
            if "threshold" in table_html.lower() or "common" in table_html.lower() or "heavy" in table_html.lower():
                route = "Oral"
                if "insufflat" in table_html.lower() or "nasal" in table_html.lower():
                    route = "Insufflated"
                elif "smoked" in table_html.lower() or "inhaled" in table_html.lower():
                    route = "Smoked"
                elif "sublingual" in table_html.lower():
                    route = "Sublingual"
                elif "iv" in table_html.lower() or "im" in table_html.lower() or "inject" in table_html.lower():
                    route = "Injection"

                threshold = None
                light = None
                common = None
                strong = None
                heavy = None
                unit = "mg"

                for row in re.finditer(r"<tr[^>]*>([\s\S]*?)</tr>", table_html, re.I):
                    r_text = row.group(1)
                    clean_row = re.sub(r"<[^>]+>", " ", r_text)
                    clean_row = html.unescape(clean_row).strip()

                    if "threshold" in clean_row.lower():
                        val = re.sub(r"threshold", "", clean_row, flags=re.I).strip()
                        threshold = val
                    elif "light" in clean_row.lower():
                        val = re.sub(r"light", "", clean_row, flags=re.I).strip()
                        light = val
                    elif "common" in clean_row.lower():
                        val = re.sub(r"common.*?\)", "", clean_row, flags=re.I)
                        val = re.sub(r"common", "", val, flags=re.I).strip()
                        common = val
                    elif "strong" in clean_row.lower():
                        val = re.sub(r"strong", "", clean_row, flags=re.I).strip()
                        strong = val
                    elif "heavy" in clean_row.lower():
                        val = re.sub(r"heavy", "", clean_row, flags=re.I).strip()
                        heavy = val

                if any([threshold, light, common, strong, heavy]):
                    dosages.append(DosageInfo(
                        route=route,
                        threshold=threshold,
                        light=light,
                        common=common,
                        strong=strong,
                        heavy=heavy,
                        unit=unit
                    ))
        return dosages
