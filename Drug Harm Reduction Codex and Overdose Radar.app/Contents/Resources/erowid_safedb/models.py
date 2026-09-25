"""
Data models for Erowid Harm Reduction & Experience Database.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
import json


@dataclass
class DosageInfo:
    route: str
    threshold: Optional[str] = None
    light: Optional[str] = None
    common: Optional[str] = None
    strong: Optional[str] = None
    heavy: Optional[str] = None
    unit: str = "mg"
    notes: Optional[str] = None


@dataclass
class DurationInfo:
    route: str
    onset: Optional[str] = None
    coming_up: Optional[str] = None
    peak: Optional[str] = None
    plateau: Optional[str] = None
    coming_down: Optional[str] = None
    after_effects: Optional[str] = None
    total_duration: Optional[str] = None


@dataclass
class DrugInteraction:
    substance_a: str
    substance_b: str
    risk_level: str  # DEADLY, DANGEROUS, UNSAFE, CAUTION, LOW_RISK_SYNERGY, LOW_RISK_NO_SYNERGY
    mechanism: str
    harm_reduction_advice: str


@dataclass
class Substance:
    id: Optional[int] = None
    slug: str = ""
    name: str = ""
    common_names: List[str] = field(default_factory=list)
    category: str = ""  # Psychedelic, Stimulant, Depressant, Dissociative, Opioid, etc.
    description: str = ""
    harm_summary: str = ""
    addiction_potential: str = "Low"  # None, Low, Moderate, High, Very High
    toxicity_notes: str = ""
    legal_status: str = ""
    testing_reagents: Dict[str, str] = field(default_factory=dict)
    dosages: List[DosageInfo] = field(default_factory=list)
    durations: List[DurationInfo] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExperienceDoseItem:
    substance: str
    amount: Optional[str] = None
    unit: Optional[str] = None
    method: Optional[str] = None
    form: Optional[str] = None


@dataclass
class AdverseEvent:
    symptom: str
    severity: str  # Mild, Moderate, Severe, Life-Threatening
    excerpt: str


@dataclass
class ExperienceReport:
    id: int  # Erowid Experience ID (e.g. 71809)
    title: str = ""
    author: Optional[str] = None
    substance_summary: str = ""
    exp_year: Optional[int] = None
    published_date: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[str] = None
    body_weight: Optional[str] = None
    narrative: str = ""
    doses: List[ExperienceDoseItem] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    adverse_events: List[AdverseEvent] = field(default_factory=list)
    harm_flags: List[str] = field(default_factory=list)
    word_count: int = 0
    url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CatalogEntry:
    slug: str
    name: str
    description: str = ""
    synonyms: List[str] = field(default_factory=list)
    master_url: str = ""
    categories: Dict[str, str] = field(default_factory=dict)
    vault_url: Optional[str] = None
    total_reports: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReportIndexItem:
    id: int
    substance_slug: str
    category: str = "General"
    title: str = ""
    author: str = ""
    status: str = "pending"  # pending, scraped, failed
    scraped_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

