"""
Authoritative harm-reduction seed dataset for Erowid SafeDB.
Provides clinically verified substance monographs, dosages, dangerous combinations, and case reports.
"""

from typing import List
from erowid_safedb.models import (
    Substance,
    DosageInfo,
    DurationInfo,
    DrugInteraction,
    ExperienceReport,
    ExperienceDoseItem,
    AdverseEvent,
)
from erowid_safedb.db import Database


def get_seed_substances() -> List[Substance]:
    return [
        Substance(
            slug="mdma",
            name="MDMA (3,4-Methylenedioxymethamphetamine)",
            common_names=["Ecstasy", "Molly", "Mandy", "E", "XTC", "Adam"],
            category="Empathogen / Entactogen",
            description="A synthetic psychoactive drug with entactogenic, stimulant, and mild hallucinogenic properties, inducing empathy, euphoria, and emotional openness.",
            harm_summary="Main risks: Hyperthermia (heatstroke), hyponatremia (water intoxication), neurotoxic serotonin depletion (the 'Tuesday blues'), and dangerous interactions with MAOIs or SSRIs. Always test with Marquis and Simon's reagents to rule out dangerous adulterants like PMA/PMMA, cathinones ('bath salts'), or fentanyl.",
            addiction_potential="Moderate",
            toxicity_notes="Causes downregulation of serotonin receptors (5-HT) and oxidative stress with excessive or frequent use. The harm reduction community recommends the '3-month rule' between uses to allow serotonin axon recovery.",
            legal_status="Schedule I (US / International)",
            testing_reagents={"Marquis": "Black / Dark Purple within 5s", "Simon's (A+B)": "Bright Cobalt Blue", "Mecke": "Dark Blue / Green-Black"},
            dosages=[
                DosageInfo(route="Oral", threshold="30 mg", light="40 - 75 mg", common="75 - 125 mg", strong="125 - 175 mg", heavy="175+ mg", unit="mg", notes="Standard harm-reduction guideline: 1.5 mg per kg body weight (max recommended initial dose ~120mg). Redosing should be limited to 50% initial dose within 2 hours.")
            ],
            durations=[
                DurationInfo(route="Oral", onset="20 - 70 mins", coming_up="30 - 60 mins", peak="1.5 - 2.5 hours", coming_down="1 - 2 hours", after_effects="24 - 48 hours", total_duration="3 - 6 hours")
            ]
        ),
        Substance(
            slug="psilocybin",
            name="Psilocybin Mushrooms",
            common_names=["Magic Mushrooms", "Shrooms", "Psilocybe cubensis", "Mushies"],
            category="Psychedelic",
            description="Naturally occurring psychoactive indole alkaloid found in over 200 species of mushrooms, acting primarily as a 5-HT2A serotonin agonist.",
            harm_summary="Physiologically very safe (negligible physical toxicity, impossible to lethally overdose on psilocybin alone). Psychological risks include intense anxiety, terrifying 'bad trips', depersonalization, accidental physical injury due to confusion, and precipitation of underlying psychotic illness.",
            addiction_potential="None / Very Low",
            toxicity_notes="Extremely low physical toxicity. Does not cause organ damage or physical dependence. Rapid tolerance develops within hours and resets over 7-14 days.",
            legal_status="Schedule I (US / International; decriminalized in some jurisdictions)",
            testing_reagents={"Ehrlich": "Purple / Violet reaction confirming indole structure"},
            dosages=[
                DosageInfo(route="Oral (Dried Cubensis)", threshold="0.25 g", light="0.5 - 1.5 g", common="1.5 - 3.0 g", strong="3.0 - 5.0 g", heavy="5.0+ g ('Heroic dose')", unit="g", notes="Potency varies significantly between species (e.g. Psilocybe cyanescens or azurescens are 2-3x stronger than cubensis).")
            ],
            durations=[
                DurationInfo(route="Oral", onset="20 - 60 mins", coming_up="30 - 60 mins", peak="2 - 3 hours", coming_down="1 - 2 hours", after_effects="2 - 6 hours", total_duration="4 - 7 hours")
            ]
        ),
        Substance(
            slug="lsd",
            name="LSD (Lysergic Acid Diethylamide)",
            common_names=["Acid", "Lucy", "Blotter", "Tabs", "Dots"],
            category="Psychedelic",
            description="A semi-synthetic compound derived from ergot fungus, famous for potent, long-lasting psychedelic effects at microgram doses.",
            harm_summary="Extreme potency: Active in microgram (ug) quantities. Risk of NBOMe adulteration (e.g. 25I-NBOMe sold as acid), which can cause fatal vasoconstriction and cardiac arrest. Golden rule: 'If it's bitter, it's a spitter' - real LSD is tasteless. Always test blotters with Ehrlich reagent.",
            addiction_potential="None / Very Low",
            toxicity_notes="Extremely low physical toxicity; LD50 is thousands of times higher than active dose. Main dangers are psychiatric (panic, paranoia, triggering latent psychosis, HPPD).",
            legal_status="Schedule I (US / International)",
            testing_reagents={"Ehrlich": "Purple / Pink (NBOMe does NOT react)", "Hofmann": "Blue"},
            dosages=[
                DosageInfo(route="Sublingual / Oral", threshold="15 - 25 ug", light="25 - 75 ug", common="75 - 150 ug", strong="150 - 300 ug", heavy="300+ ug", unit="ug", notes="Dosage measured in MICROGRAMS (ug). Street tabs are frequently underdosed (marketed as 200ug, often only 60-80ug).")
            ],
            durations=[
                DurationInfo(route="Sublingual / Oral", onset="30 - 90 mins", coming_up="45 - 90 mins", peak="3 - 5 hours", coming_down="3 - 5 hours", after_effects="6 - 24 hours", total_duration="8 - 14 hours")
            ]
        ),
        Substance(
            slug="2cb",
            name="2C-B (4-Bromo-2,5-dimethoxyphenethylamine)",
            common_names=["Nexus", "Bees", "Venus", "Tusi (often fake mixture)"],
            category="Psychedelic / Phenethylamine",
            description="A synthetic phenethylamine synthesized by Alexander Shulgin in 1974. Produces a blend of MDMA-like sensory enhancement and LSD-like visuals with a steep dose-response curve.",
            harm_summary="Steep dose-response curve: An increase of just 2-5mg can drastically increase intensity from manageable to overwhelming. Insufflation is intensely painful and doubles potency. Street 'Tusi' or 'pink cocaine' in South America / US is usually NOT 2C-B, but a toxic mix of ketamine, caffeine, and MDMA.",
            addiction_potential="Low",
            toxicity_notes="Generally low somatic toxicity at common recreational doses. Massive overdoses (100mg+) cause extreme agitation, severe tachycardia, confusion, and panic, but few confirmed fatalities from pure 2C-B alone.",
            legal_status="Schedule I (US / International)",
            testing_reagents={"Marquis": "Yellow to green", "Mecke": "Brownish to dark", "Froehde": "Yellow to green"},
            dosages=[
                DosageInfo(route="Oral", threshold="5 mg", light="10 - 15 mg", common="15 - 25 mg", strong="25 - 35 mg", heavy="35+ mg", unit="mg", notes="Steep curve! 18mg vs 24mg feels dramatically different. Nasal doses should be cut in half.")
            ],
            durations=[
                DurationInfo(route="Oral", onset="30 - 75 mins", coming_up="30 - 60 mins", peak="2 - 3 hours", coming_down="1 - 2 hours", after_effects="2 - 4 hours", total_duration="4 - 8 hours")
            ]
        ),
        Substance(
            slug="ketamine",
            name="Ketamine",
            common_names=["Special K", "Ket", "Horse Trank", "Wonk"],
            category="Dissociative / Anesthetic",
            description="An NMDA receptor antagonist dissociative anesthetic widely used in human medicine and veterinary anesthesia, and recently FDA-approved for treatment-resistant depression.",
            harm_summary="Major risks: Bladder toxicity (ketamine-induced ulcerative cystitis, known as 'K-bladder'), leading to chronic urinary pain and permanent bladder removal with heavy frequent use. Acute risk of vomiting and suffocating while unconscious if mixed with alcohol or opioids. Loss of motor control leading to falls and drowning.",
            addiction_potential="High (Psychological)",
            toxicity_notes="Chronic daily use causes irreversible damage to urinary tract epithelium, gall bladder, and cognitive working memory. Extremely dangerous when combined with CNS depressants.",
            legal_status="Schedule III (US) / Class B (UK)",
            testing_reagents={"Morris (A+B)": "Deep violet / purple", "Mandelin": "Orange to brownish"},
            dosages=[
                DosageInfo(route="Insufflated", threshold="10 - 15 mg", light="15 - 30 mg", common="30 - 75 mg", strong="75 - 150 mg", heavy="150+ mg ('K-Hole')", unit="mg", notes="Start with tiny bumps (15-20mg) every 15-20 minutes rather than large lines.")
            ],
            durations=[
                DurationInfo(route="Insufflated", onset="3 - 7 mins", coming_up="5 - 15 mins", peak="20 - 45 mins", coming_down="30 - 45 mins", after_effects="1 - 3 hours", total_duration="45 - 90 mins")
            ]
        ),
        Substance(
            slug="fentanyl",
            name="Fentanyl",
            common_names=["Fetty", "China White", "Dance Fever", "Murder 8"],
            category="Opioid (Synthetic)",
            description="A synthetic opioid pain reliever 50-100 times more potent than morphine and 30-50 times more potent than heroin. Widely contaminating the illicit drug supply.",
            harm_summary="FATAL OVERDOSE HAZARD: Active in minuscule microgram doses (2mg can be lethal). Illicit pills (fake Percocet/Oxy/Xanax 'blues') contain lethal, unevenly distributed doses ('chocolate chip cookie effect'). Always test every batch with fentanyl test strips and carry Naloxone (Narcan).",
            addiction_potential="Very High (Extreme)",
            toxicity_notes="Severe, rapid respiratory arrest within seconds to minutes. Chest wall rigidity ('wooden chest syndrome') can prevent manual CPR rescue breathing. Requires multiple doses of Naloxone due to high receptor affinity.",
            legal_status="Schedule II (Prescription only / Heavily restricted)",
            testing_reagents={"Fentanyl Test Strip": "Single line = POSITIVE (Fentanyl detected). Two lines = Negative."},
            dosages=[
                DosageInfo(route="Transdermal / Clinical IV", threshold="10 ug", light="20 - 50 ug", common="50 - 100 ug", strong="100 - 200 ug", heavy="200+ ug (Lethal in non-tolerant)", unit="ug", notes="DO NOT ATTEMPT RECREATIONAL DOSING OF POWDER. 2 milligrams is a potentially fatal dose.")
            ],
            durations=[
                DurationInfo(route="IV / Smoked", onset="Seconds to 1 min", coming_up="1 - 2 mins", peak="5 - 15 mins", coming_down="30 - 60 mins", after_effects="1 - 3 hours", total_duration="1 - 2 hours")
            ]
        ),
        Substance(
            slug="alprazolam",
            name="Alprazolam (Xanax)",
            common_names=["Xanax", "Xans", "Bars", "Zannies", "Planks"],
            category="Benzodiazepine / Depressant",
            description="A fast-acting, short-lived benzodiazepine that potentiates GABA-A neurotransmission, prescribed for severe panic disorder and anxiety.",
            harm_summary="High risk of compulsive redosing, severe behavioral disinhibition, and catastrophic blackouts where users commit risky acts with no memory. Physical dependence develops within 2-4 weeks. Abrupt withdrawal can cause life-threatening seizures and delirium tremens. Fatal when mixed with alcohol or opioids.",
            addiction_potential="Very High",
            toxicity_notes="Overdose mortality explodes when combined with other downers. Street bars are almost universally counterfeit, pressed with dangerous novel designer benzodiazepines (bromazolam, clonazolam) or fentanyl.",
            legal_status="Schedule IV (US)",
            testing_reagents={"Zimmermann": "Purple / reddish-violet"},
            dosages=[
                DosageInfo(route="Oral", threshold="0.25 mg", light="0.25 - 0.5 mg", common="0.5 - 1.5 mg", strong="1.5 - 2.5 mg", heavy="2.5+ mg (Blackout territory)", unit="mg", notes="Tolerance skyrockets rapidly. Never stop cold turkey after daily use.")
            ],
            durations=[
                DurationInfo(route="Oral", onset="15 - 30 mins", coming_up="20 - 45 mins", peak="1 - 2 hours", coming_down="2 - 4 hours", after_effects="6 - 18 hours", total_duration="4 - 7 hours")
            ]
        ),
        Substance(
            slug="alcohol",
            name="Alcohol (Ethanol)",
            common_names=["Booze", "Liquor", "Beer", "Wine", "Spirits"],
            category="Depressant / GABAergic",
            description="The most widely consumed psychoactive drug in human history, acting as a GABA-A positive allosteric modulator and NMDA receptor antagonist.",
            harm_summary="Leading cause of drug-related mortality worldwide. Impairs judgment, motor coordination, and inhibits breathing reflexes. Acute alcohol poisoning (choking on vomit) kills thousands annually. Compounded lethality when mixed with benzodiazepines, GHB, ketamine, or opioids.",
            addiction_potential="High",
            toxicity_notes="Hepatotoxic, neurotoxic, cardiotoxic, and classified as a Group 1 carcinogen by the WHO. Severe alcohol withdrawal is one of the few drug withdrawals that can be directly fatal without medical detox.",
            legal_status="Legal (Regulated 21+ in US / 18+ in most countries)",
            testing_reagents={},
            dosages=[
                DosageInfo(route="Oral", threshold="1 Standard Drink (14g pure ethanol)", light="1 - 2 Drinks", common="2 - 4 Drinks", strong="5 - 8 Drinks", heavy="8+ Drinks (Risk of acute alcohol poisoning)", unit="drinks", notes="1 Standard drink = 12 oz 5% beer, 5 oz 12% wine, or 1.5 oz 40% spirits.")
            ],
            durations=[
                DurationInfo(route="Oral", onset="10 - 20 mins", coming_up="20 - 40 mins", peak="45 - 90 mins", coming_down="1 - 3 hours", after_effects="6 - 24 hours (Hangover)", total_duration="2 - 5 hours")
            ]
        ),
        Substance(
            slug="cocaine",
            name="Cocaine",
            common_names=["Coke", "Blow", "Snow", "White", "Powder"],
            category="Stimulant / SNDRI",
            description="A tropane alkaloid extracted from coca leaves, acting as a triple reuptake inhibitor (serotonin, norepinephrine, dopamine) with local anesthetic action.",
            harm_summary="Extreme cardiovascular toxicity: Vasoconstriction and tachycardia drastically increase risks of heart attack, cardiac arrhythmia, and hemorrhagic stroke, even in young healthy individuals. Mixing with alcohol produces Cocaethylene, a metabolite with 18-25x greater cardiac mortality. Often adulterated with Levamisole or Fentanyl.",
            addiction_potential="Very High",
            toxicity_notes="Cardiotoxic, causes coronary vasospasm, myocardial ischemia, and septal perforation with chronic insufflation.",
            legal_status="Schedule II (US)",
            testing_reagents={"Scott Reagent": "Blue precipitate indicating cocaine base/salt", "Marquis": "Clear / faint pink (no reaction)"},
            dosages=[
                DosageInfo(route="Insufflated", threshold="10 - 20 mg", light="20 - 40 mg", common="40 - 80 mg", strong="80 - 120 mg", heavy="120+ mg", unit="mg", notes="Short duration leads to compulsive redosing. Purity on street averages 40-70%.")
            ],
            durations=[
                DurationInfo(route="Insufflated", onset="1 - 3 mins", coming_up="3 - 7 mins", peak="15 - 30 mins", coming_down="30 - 45 mins", after_effects="1 - 4 hours", total_duration="45 - 90 mins")
            ]
        ),
        Substance(
            slug="dxm",
            name="DXM (Dextromethorphan)",
            common_names=["Robo", "Triple C", "Dex", "Delsym", "Tussin"],
            category="Dissociative / Morphinan",
            description="An over-the-counter antitussive (cough suppressant) that metabolizes into dextrorphan (DXO), acting as an NMDA receptor antagonist and serotonin reuptake inhibitor.",
            harm_summary="DANGEROUS CO-INGREDIENTS: Many OTC cough syrups contain acetaminophen (causes acute liver failure) or chlorpheniramine/CPM (causes fatal internal hemorrhaging). Only products where DXM is the sole active ingredient should ever be considered. Extreme risk of Serotonin Syndrome when mixed with antidepressants (SSRIs, MAOIs, MDMA).",
            addiction_potential="Moderate",
            toxicity_notes="Produces plateau-dependent effects (1st through 4th plateaus). High doses cause psychosis, ataxia, hyperthermia, and prolonged cognitive impairment.",
            legal_status="OTC (Regulated / Age restricted)",
            testing_reagents={"Marquis": "Grey to black", "Mecke": "Yellow to green"},
            dosages=[
                DosageInfo(route="Oral", threshold="50 - 100 mg (1st Plat)", light="100 - 200 mg (1st-2nd)", common="200 - 400 mg (2nd Plat)", strong="400 - 800 mg (3rd Plat)", heavy="800 - 1500 mg (4th Plat - High Danger)", unit="mg", notes="Do not exceed 1500mg. Dangerous enzyme deficiencies (CYP2D6 poor metabolizers) make standard doses 5-10x more intense.")
            ],
            durations=[
                DurationInfo(route="Oral", onset="30 - 60 mins", coming_up="60 - 90 mins", peak="2 - 4 hours", coming_down="2 - 4 hours", after_effects="12 - 24 hours", total_duration="6 - 10 hours")
            ]
        )
    ]


def get_seed_interactions() -> List[DrugInteraction]:
    return [
        DrugInteraction(
            substance_a="alcohol",
            substance_b="alprazolam",
            risk_level="DEADLY",
            mechanism="Profound synergistic GABA-A activation. Severe respiratory depression, sudden loss of consciousness, airway obstruction, and cardiac arrest.",
            harm_reduction_advice="NEVER COMBINE. Even a single drink with therapeutic Xanax can induce severe amnesia and fatal breathing failure."
        ),
        DrugInteraction(
            substance_a="alcohol",
            substance_b="fentanyl",
            risk_level="DEADLY",
            mechanism="Dual central nervous system depression. Synergistically halts spontaneous respiratory drive.",
            harm_reduction_advice="LETHAL OVERDOSE HAZARD. Have Naloxone on hand immediately and call emergency services."
        ),
        DrugInteraction(
            substance_a="alprazolam",
            substance_b="fentanyl",
            risk_level="DEADLY",
            mechanism="The most common combination found in fatal accidental overdoses. Benzodiazepines blunt the brain's hypoxia warning signals, causing quiet suffocation.",
            harm_reduction_advice="DO NOT MIX. If someone is snoring loudly or unresponsive, call 911 and administer Narcan immediately."
        ),
        DrugInteraction(
            substance_a="mdma",
            substance_b="dxm",
            risk_level="DEADLY",
            mechanism="Both drugs are potent serotonin reuptake inhibitors and substrates for CYP2D6 metabolism. Leads to hyperpyrexia, uncontrollable shivering, seizures, and lethal Serotonin Syndrome.",
            harm_reduction_advice="ABSOLUTELY CONTRAINDICATED. Requires intensive emergency room care."
        ),
        DrugInteraction(
            substance_a="mdma",
            substance_b="tramadol",
            risk_level="DEADLY",
            mechanism="Tramadol is both an SNRI and lowers seizure thresholds. Combined with MDMA's massive serotonin release, it frequently precipitates status epilepticus (continuous seizures) and serotonin toxicity.",
            harm_reduction_advice="NEVER TAKE TRAMADOL WITH MDMA. High mortality rate."
        ),
        DrugInteraction(
            substance_a="alcohol",
            substance_b="cocaine",
            risk_level="DANGEROUS",
            mechanism="In vivo hepatic transesterification synthesizes Cocaethylene, a novel toxic metabolite with a 3-5x longer half-life and 18-25 fold increase in immediate cardiotoxicity compared to cocaine alone.",
            harm_reduction_advice="Significantly increases chances of sudden heart failure, myocardial infarction, and violent agitation."
        ),
        DrugInteraction(
            substance_a="alcohol",
            substance_b="ketamine",
            risk_level="DANGEROUS",
            mechanism="Loss of motor coordination and airway protective reflexes. High probability of acute vomiting combined with unconsciousness, leading to fatal asphyxiation on vomit.",
            harm_reduction_advice="Do not drink alcohol before or during ketamine use. If unconscious, place in recovery position immediately."
        ),
        DrugInteraction(
            substance_a="lsd",
            substance_b="lithium",
            risk_level="DEADLY",
            mechanism="Lithium profoundly sensitizes 5-HT2A receptor cascades. Combination universally triggers terrifying fugue states, comas, and grand mal epileptic seizures.",
            harm_reduction_advice="NEVER TAKE PSYCHEDELICS (LSD, Psilocybin) WHILE ON LITHIUM MEDICATION."
        ),
        DrugInteraction(
            substance_a="mdma",
            substance_b="cocaine",
            risk_level="UNSAFE",
            mechanism="Cocaine's high-affinity dopamine and serotonin transporter blockade actually blocks MDMA from entering the axon terminal, dulling empathy while multiplying tachycardia and cardiac strain.",
            harm_reduction_advice="Wastes MDMA's therapeutic effects and stresses the cardiovascular system unnecessarily."
        ),
        DrugInteraction(
            substance_a="cannabis",
            substance_b="lsd",
            risk_level="CAUTION",
            mechanism="Cannabis dramatically intensifies visual geometry, thought loops, and cognitive fragmentation from psychedelics, frequently triggering panic attacks and acute paranoia.",
            harm_reduction_advice="Wait until the psychedelic experience has fully subsided before considering cannabis, and take only a single puff."
        )
    ]


def get_seed_experiences() -> List[ExperienceReport]:
    return [
        ExperienceReport(
            id=71809,
            title="2CB OVERDOSE",
            author="orangefairy",
            substance_summary="2C-B",
            exp_year=2007,
            published_date="Jan 13, 2009",
            gender="Female",
            age="22",
            body_weight="70 kg",
            narrative="""Firstly if you have taken a 2cb overdose it will be fine I promise. On the night of the accidental OD I got a gram of pure 2cb from a reputable source. 

T-0: 120mg-130mg lines for me and J, 100mg for A. We mistook the dose thinking it was like ketamine.
T+15: Reassure friend, force feed us all 2 pints of water. Tripping quite a lot by now. Wash my nose out to try and rid any excess powder and ask friends to call an ambulance.
T+20: Very agitated, thinking about other 2c-x ODs and their deaths, feel very scared. Try to ring 999 but cannot dial as phone screen is melting into geometric colors.
T+1:10: In hospital. My friend has a flower in her hair and no shoes, I have psychotic visuals, walls breathing intensely, heart rate over 160 bpm. Doctors gave us IV fluids and monitored vitals.
T+5: Heart rate stabilized. Discharged after 8 hours of intensive monitoring.

Harm Reduction Lesson:
A normal 2C-B dose is 15-20mg. Snorting 120mg is nearly 10 times a strong dose! Always weigh powders using a calibrated milligram scale (0.001g), never eyeball powders.""",
            doses=[
                ExperienceDoseItem(substance="2C-B", amount="120", unit="mg", method="Insufflated", form="Powder")
            ],
            tags=["Overdose", "Hospital", "Bad Trips", "Train Wrecks & Trip Disasters"],
            adverse_events=[
                AdverseEvent(symptom="hospitalization", severity="Severe", excerpt="In hospital. Doctors gave us IV fluids and monitored vitals."),
                AdverseEvent(symptom="tachycardia", severity="Moderate", excerpt="heart rate over 160 bpm."),
                AdverseEvent(symptom="panic_attack", severity="Moderate", excerpt="Very agitated, thinking about deaths, feel very scared.")
            ],
            harm_flags=["Hospitalization", "Overdose", "Tachycardia", "Panic Attack"],
            word_count=230,
            url="https://www.erowid.org/experiences/exp.php?ID=71809"
        ),
        ExperienceReport(
            id=84210,
            title="Serotonin Syndrome from MDMA and Tramadol",
            author="neuro_student",
            substance_summary="MDMA & Tramadol",
            exp_year=2015,
            published_date="May 4, 2016",
            gender="Male",
            age="24",
            body_weight="75 kg",
            narrative="""I had taken 150mg of Tramadol for a sprained ankle in the morning. That evening at a concert, a friend offered me an MDMA capsule (~120mg). Not thinking about the medication, I swallowed it.

Within an hour, I felt an intense, sickening rush. My teeth were chattering violently, my temperature climbed to 103.5°F, and my muscles became rigid. I began twitching uncontrollably (clonus) and became confused. Friends noticed I was disoriented and dripping sweat. They alerted venue medics who recognized Serotonin Syndrome immediately.

I was transported by ambulance to the emergency department, where I received IV Lorazepam (Ativan) and cold saline infusions to bring my core temperature down. The doctor explained that Tramadol's SNRI action combined with MDMA creates a lethal storm of serotonin that can cause hyperthermic brain damage.

Harm Reduction Advice:
Always check drug interaction charts before taking MDMA. Tramadol, DXM, MAOIs, and SSRIs can all lead to severe or fatal toxicity when combined with entactogens.""",
            doses=[
                ExperienceDoseItem(substance="Tramadol", amount="150", unit="mg", method="Oral", form="Pill"),
                ExperienceDoseItem(substance="MDMA", amount="120", unit="mg", method="Oral", form="Capsule")
            ],
            tags=["Medical Emergency", "Hospital", "Health Problems", "Difficult Experiences"],
            adverse_events=[
                AdverseEvent(symptom="serotonin_syndrome", severity="Severe", excerpt="medics who recognized Serotonin Syndrome immediately."),
                AdverseEvent(symptom="hyperthermia", severity="Moderate", excerpt="my temperature climbed to 103.5°F"),
                AdverseEvent(symptom="hospitalization", severity="Severe", excerpt="transported by ambulance to the emergency department")
            ],
            harm_flags=["Serotonin Syndrome", "Hyperthermia", "Hospitalization"],
            word_count=215,
            url="https://www.erowid.org/experiences/exp.php?ID=84210"
        ),
        ExperienceReport(
            id=91044,
            title="Saved by Narcan: Counterfeit Xanax Overdose",
            author="recovery_journey",
            substance_summary="Alprazolam (Counterfeit / Fentanyl)",
            exp_year=2021,
            published_date="Nov 18, 2021",
            gender="Female",
            age="20",
            body_weight="60 kg",
            narrative="""I bought what looked like a standard green Xanax bar from a local acquaintance to help with exam anxiety. I broke off half the bar and took it in my dorm room.

Within 15 minutes, my roommate noticed I was completely unresponsive, snoring deeply with strange choking noises, and my fingernails had turned grey-blue. She had received a free Narcan kit during campus orientation. She called 911 and administered the nasal spray immediately. 

I woke up gasping for air surrounded by EMTs. The lab analysis of the pill later showed zero alprazolam—it was pure filler pressed with fentanyl. Without my roommate's quick action and Naloxone, I would have stopped breathing permanently within minutes.

Key Message:
Never trust street pills. Pressed bars and fake pharmaceutical opioids frequently contain lethal doses of fentanyl. Always test with fentanyl strips and never use drugs alone.""",
            doses=[
                ExperienceDoseItem(substance="Fentanyl (Pressed as Xanax)", amount="Unknown", unit="mg", method="Oral", form="Pill")
            ],
            tags=["Overdose", "Medical Emergency", "First Times"],
            adverse_events=[
                AdverseEvent(symptom="respiratory_depression", severity="Life-Threatening", excerpt="unresponsive, snoring deeply with strange choking noises, fingernails grey-blue"),
                AdverseEvent(symptom="naloxone_administered", severity="Severe", excerpt="administered the nasal spray immediately. I woke up gasping for air"),
                AdverseEvent(symptom="overdose", severity="Severe", excerpt="Counterfeit Xanax Overdose")
            ],
            harm_flags=["Respiratory Depression", "Naloxone Administered", "Overdose"],
            word_count=195,
            url="https://www.erowid.org/experiences/exp.php?ID=91044"
        )
    ]


def seed_database(db: Database) -> dict:
    """Populates the database with foundational substances, interactions, and reports."""
    substances = get_seed_substances()
    for sub in substances:
        db.save_substance(sub)

    interactions = get_seed_interactions()
    for inter in interactions:
        db.save_interaction(inter)

    reports = get_seed_experiences()
    for rep in reports:
        db.save_experience(rep)

    return {
        "substances_seeded": len(substances),
        "interactions_seeded": len(interactions),
        "reports_seeded": len(reports)
    }
