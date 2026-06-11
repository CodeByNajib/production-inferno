"""
engine.py – Production Inferno grading engine
==============================================
Zero terminal dependencies. Imported by both ops_simulator.py (CLI) and
app.py (Streamlit). Contains:
  - grade_answer()      keyword-group grader
  - DANISH_SCALE        grade mapping
  - danish_grade()      score -> grade lookup
  - BOARD_QUESTIONS     the 20-question IT-Drift oral exam board
  - SCENARIOS_META      metadata for the 4 incident scenarios per module
"""

import math
import re

# ---------------------------------------------------------------------------
# GRADING ENGINE
# ---------------------------------------------------------------------------

def grade_answer(answer: str, groups: list, threshold: int = None):
    """
    groups: list of (label, [regex, ...])
    Returns (hits, missed, passed).
    """
    hits, missed = [], []
    for label, patterns in groups:
        if any(re.search(p, answer, re.IGNORECASE | re.DOTALL) for p in patterns):
            hits.append(label)
        else:
            missed.append(label)
    if threshold is None:
        threshold = max(1, math.ceil(len(groups) * 0.6))
    return hits, missed, len(hits) >= threshold


DANISH_SCALE = [
    (90, "12", "Fremragende"),
    (78, "10", "Fortrinlig"),
    (60, "7",  "God"),
    (50, "4",  "Jævn"),
    (40, "02", "Tilstrækkelig"),
    (0,  "00/−3", "Ikke bestået"),
]


def danish_grade(pct: float):
    for cutoff, grade, label in DANISH_SCALE:
        if pct >= cutoff:
            return grade, label
    return "00/−3", "Ikke bestået"


# ---------------------------------------------------------------------------
# QUIZ QUESTIONS  (multiple-choice, level 1)
# Loaded from questions.json at runtime; this list is the fallback default.
# ---------------------------------------------------------------------------

QUIZ_QUESTIONS = [
    {
        "topic": "ITIL",
        "question": "Hvad er det primære mål med Incident Management?",
        "options": [
            "A. Finde og fjerne rodårsagen permanent",
            "B. Genoprette normal service så hurtigt som muligt",
            "C. Godkende ændringer i produktionsmiljøet",
            "D. Dokumentere alle konfigurationer i CMDB",
        ],
        "answer": "B",
        "explanation": (
            "Incident Management handler om HURTIG genopretning – "
            "ofte via en workaround. Problem Management finder rodårsagen bagefter."
        ),
    },
    {
        "topic": "ITIL",
        "question": "Hvilken change-type kræver ECAB-godkendelse?",
        "options": [
            "A. Standard Change",
            "B. Normal Change",
            "C. Emergency Change",
            "D. Alle change-typer",
        ],
        "answer": "C",
        "explanation": (
            "Emergency Changes er kritiske og akutte. ECAB (Emergency Change "
            "Advisory Board) mødes inden ændringen, og skriftlig godkendelse "
            "gives efterfølgende."
        ),
    },
    {
        "topic": "ITIL",
        "question": "Hvad er forskellen på reaktiv og proaktiv Problem Management?",
        "options": [
            "A. Reaktiv fjerner rodårsagen; proaktiv genopretter service",
            "B. Reaktiv aktiveres efter incidents; proaktiv forsøger at forhindre incidents",
            "C. Reaktiv kræver CAB-godkendelse; proaktiv gør ikke",
            "D. Der er ingen forskel – begge er det samme",
        ],
        "answer": "B",
        "explanation": (
            "Reaktiv PM analyserer eksisterende incidents for at finde "
            "rodårsagen. Proaktiv PM identificerer potentielle problemer "
            "INDEN de giver incidents."
        ),
    },
    {
        "topic": "ITIL",
        "question": "Hvad indeholder en CMDB?",
        "options": [
            "A. Kun hardware-aktiver med serienumre",
            "B. Historisk og aktuel info om alle Configuration Items og deres relationer",
            "C. Udelukkende softwarelicenser og versioner",
            "D. SLA-aftaler med kunder",
        ],
        "answer": "B",
        "explanation": (
            "CMDB (Configuration Management Database) indeholder løbende "
            "opdateret information om alle CIs – servere, software, netværk, "
            "dokumenter – samt deres indbyrdes afhængigheder."
        ),
    },
    {
        "topic": "ITIL",
        "question": "Et P1 Critical incident – hvad er response time og resolution target?",
        "options": [
            "A. Response: 10 min, Resolution: 4 timer",
            "B. Response: 1 time, Resolution: 8 timer",
            "C. Response: Immediate, Resolution: 1 time",
            "D. Response: 4 timer, Resolution: 24 timer",
        ],
        "answer": "C",
        "explanation": (
            "P1 Critical = system down, major impact. "
            "Response: Immediate. Resolution: ~1 time. Håndteres af 2nd/3rd line."
        ),
    },
    {
        "topic": "ISO 27001",
        "question": "Hvad er en SoA (Statement of Applicability)?",
        "options": [
            "A. En kontrakt med en ekstern leverandør",
            "B. Et dokument der viser valgte/fravalgte Annex A-kontroller og begrundelsen",
            "C. En log over sikkerhedshændelser",
            "D. Organisationens risikoappetit godkendt af bestyrelsen",
        ],
        "answer": "B",
        "explanation": (
            "SoA dokumenterer præcis hvilke af Annex A's 93 kontroller "
            "organisationen har valgt og fravalgt – og HVORFOR. "
            "Det er et obligatorisk dokument ved certificering."
        ),
    },
    {
        "topic": "ISO 27001",
        "question": "Hvad er forskellen på en Minor og en Major non-conformity ved audit?",
        "options": [
            "A. Minor = systemisk svigt; Major = isoleret fejl",
            "B. Minor = isoleret fejl; Major = systemisk svigt der kan blokere certificering",
            "C. Begge kan blokere certificering",
            "D. Ingen af dem påvirker certificeringen",
        ],
        "answer": "B",
        "explanation": (
            "Minor non-conformity er en isoleret afvigelse. "
            "Major non-conformity er et systemisk svigt der truer ISMS-integriteten "
            "og KAN blokere certificering."
        ),
    },
    {
        "topic": "ISO 27001",
        "question": "Hvilke tre principper udgør CIA-triaden?",
        "options": [
            "A. Compliance, Integrity, Availability",
            "B. Confidentiality, Integrity, Availability",
            "C. Confidentiality, Identification, Authorization",
            "D. Control, Integrity, Accountability",
        ],
        "answer": "B",
        "explanation": (
            "CIA = Confidentiality (kun autoriserede ser data), "
            "Integrity (data er uændret), Availability (systemer er tilgængelige). "
            "Fundamentet for al informationssikkerhed."
        ),
    },
    {
        "topic": "ISO 27001",
        "question": "Hvad styrer valget af Annex A-kontroller?",
        "options": [
            "A. Leverandørens anbefalinger",
            "B. CISO'ens personlige præferencer",
            "C. Risikovurderingen",
            "D. Antallet af ansatte i organisationen",
        ],
        "answer": "C",
        "explanation": (
            "Risikovurderingen (kap. 6.1.2) identificerer hvilke risici der "
            "skal behandles. Derfra vælger man de relevante kontroller fra "
            "Annex A og dokumenterer det i SoA'en."
        ),
    },
    {
        "topic": "ISO 27001",
        "question": "Hvad sker der ved en ISO 27001 Stage 1-audit?",
        "options": [
            "A. Auditoren tester om kontrollerne virker i praksis",
            "B. Auditoren gennemgår dokumentationen (har I de rigtige politikker?)",
            "C. Organisationen gennemgår sin egen ISMS-ydelse",
            "D. Medarbejderne testes i sikkerhedsbevidsthed",
        ],
        "answer": "B",
        "explanation": (
            "Stage 1 = dokumentationsgennemgang. "
            "Stage 2 = feltevaluering (virker det i praksis?). "
            "Herefter re-certificering hvert 3. år + årlige surveillance audits."
        ),
    },
    {
        "topic": "Risikoanalyse",
        "question": "Hvad er CEO-perspektivets risikoformel?",
        "options": [
            "A. Risk = Threat × Vulnerability × Impact",
            "B. Risk = Likelihood × Consequence",
            "C. Risk = Attack Surface × Attack Vector",
            "D. Risk = Probability × Exposure",
        ],
        "answer": "B",
        "explanation": (
            "CEO/ledelses-perspektiv: RISK = Likelihood × Consequence. "
            "IT-analytiker-perspektiv: RISK = Threat × Vulnerability × Impact. "
            "Sammenhængen: Threat × Vulnerability = Likelihood."
        ),
    },
    {
        "topic": "Risikoanalyse",
        "question": "En risiko scorer 4 på Likelihood og 3 på Consequence. Hvad er risikoscore og farve?",
        "options": [
            "A. Score 7 – Moderate (gul)",
            "B. Score 12 – High (orange)",
            "C. Score 12 – Extreme (rød)",
            "D. Score 7 – High (orange)",
        ],
        "answer": "B",
        "explanation": (
            "Risikoscore = Likelihood × Consequence = 4 × 3 = 12. "
            "Score 8-12 = High (orange) – kræver handling. "
            "Score 15-25 = Extreme (rød)."
        ),
    },
    {
        "topic": "Risikoanalyse",
        "question": "Hvilken risikohåndteringsform passer til: 'Vi tegner cyberforsikring'?",
        "options": [
            "A. Mitigate",
            "B. Accept",
            "C. Transfer",
            "D. Avoid",
        ],
        "answer": "C",
        "explanation": (
            "Transfer = risikoen flyttes til tredjepart (forsikring, outsourcing). "
            "Mitigate = reducer med kontroller. Accept = bevidst accept. "
            "Avoid = stop aktiviteten der skaber risikoen."
        ),
    },
    {
        "topic": "iAAA",
        "question": "Hvad er forskellen på Authentication og Authorization?",
        "options": [
            "A. Authentication tildeler adgang; Authorization verificerer identitet",
            "B. Authentication verificerer identitet; Authorization tildeler adgang",
            "C. De er det samme begreb med forskellige navne",
            "D. Authentication logger handlinger; Authorization verificerer identitet",
        ],
        "answer": "B",
        "explanation": (
            "Authentication = systemet verificerer hvem du er (password, MFA, biometri). "
            "Authorization = du tildeles adgang til ressourcer baseret på din profil (RBAC, ACL). "
            "Identification er trinnet før – du hævder hvem du er."
        ),
    },
    {
        "topic": "iAAA",
        "question": "JHB: 'iAAA is THE central key to it all.' Hvad er det fjerde A?",
        "options": [
            "A. Automation",
            "B. Accountability",
            "C. Availability",
            "D. Auditing",
        ],
        "answer": "B",
        "explanation": (
            "Accountability = du er ansvarlig for dine handlinger. "
            "Implementeres via logging, audit logs, SIEM. "
            "Kobler til Integrity i CIA-triaden."
        ),
    },
    {
        "topic": "Backup & DR",
        "question": "RPO er 4 timer og RTO er 6 timer. Hvad er den maksimale MAO?",
        "options": [
            "A. 4 timer",
            "B. 6 timer",
            "C. 10 timer",
            "D. 24 timer",
        ],
        "answer": "C",
        "explanation": (
            "MAO = Maximum Acceptable Outage. "
            "RPO + RTO ≤ MAO. Her: 4 + 6 = 10 timer. "
            "MAO defineres i BIA (Business Impact Analysis)."
        ),
    },
    {
        "topic": "Backup & DR",
        "question": "Hvad mangler 3-2-1-reglen for at beskytte mod ransomware?",
        "options": [
            "A. En fjerde kopi på bånd",
            "B. En immutabel/air-gapped kopi + testede restores",
            "C. Kryptering af alle backups",
            "D. Daglig backup i stedet for ugentlig",
        ],
        "answer": "B",
        "explanation": (
            "Ransomware krypterer også tilgængelige backups. "
            "Moderne udvidelse: 3-2-1-1-0 – én immutabel/air-gapped kopi "
            "og nul fejl på restore-tests. En utestet backup er ikke en backup."
        ),
    },
    {
        "topic": "Virtualisering",
        "question": "Hvad er forskellen på Type 1 og Type 2 hypervisor?",
        "options": [
            "A. Type 1 kører oven på et OS; Type 2 kører direkte på hardware",
            "B. Type 1 kører direkte på hardware (bare-metal); Type 2 kører oven på et OS",
            "C. Type 1 bruges kun til test; Type 2 bruges i produktion",
            "D. Der er ingen funktionel forskel",
        ],
        "answer": "B",
        "explanation": (
            "Type 1 (bare-metal): VMware ESXi, Hyper-V, KVM – enterprise/datacenter. "
            "Type 2 (hosted): VirtualBox, VMware Workstation – test/udvikling. "
            "Type 1 er mere stabil og effektiv da den ikke har et mellemliggende OS."
        ),
    },
    {
        "topic": "Virtualisering",
        "question": "Hvad er 'noisy neighbor'-effekten ved virtualisering?",
        "options": [
            "A. En VM der larmer fysisk i serverrummet",
            "B. En VM på samme fysiske host der bruger alle ressourcer og påvirker andres performance",
            "C. En netværksstorm der overbelaster switchen",
            "D. En backup-agent der kører midt i arbejdstiden",
        ],
        "answer": "B",
        "explanation": (
            "Noisy neighbor = en VM på samme fysiske server der forbruger "
            "uforholdsmæssigt mange CPU/RAM/IO-ressourcer og degraderer "
            "performance for de andre VMs. En af de primære ulemper ved virtualisering."
        ),
    },
    {
        "topic": "CMMI",
        "question": "En organisation løser alle problemer ad hoc uden dokumenterede processer. Hvilket CMMI-niveau er det?",
        "options": [
            "A. Level 2 – Managed",
            "B. Level 3 – Defined",
            "C. Level 1 – Initial",
            "D. Level 0 – Umoden",
        ],
        "answer": "C",
        "explanation": (
            "Level 1 Initial = ad hoc, reaktiv, hero-kultur. "
            "Processer er uforudsigelige og gentages ikke systematisk. "
            "Man starter fra bunden ved hver ny opgave."
        ),
    },
    {
        "topic": "CMMI",
        "question": "Må man springe et CMMI-niveau over?",
        "options": [
            "A. Ja, hvis organisationen har ressourcerne",
            "B. Ja, men kun fra Level 2 til Level 4",
            "C. Nej – hvert niveau er fundamentet for det næste",
            "D. Det afhænger af om man bruger Staged eller Continuous repræsentation",
        ],
        "answer": "C",
        "explanation": (
            "Niveauer MÅ IKKE springes over. Level 2 er fundamentet for Level 3 "
            "osv. Hvert niveau bygger på de kapabiliteter der er etableret i "
            "det foregående."
        ),
    },
    {
        "topic": "Change Management",
        "question": "Hvad er de 7 R'er i Change Management?",
        "options": [
            "A. Raised, Reason, Return, Risks, Resources, Responsible, Relationship",
            "B. Request, Review, Risk, Rollback, Release, Retire, Report",
            "C. Raised, Review, Return, Risk, Resources, Release, Relationship",
            "D. Request, Reason, Return, Risk, Resources, Responsible, Report",
        ],
        "answer": "A",
        "explanation": (
            "De 7 R'er: Raised (hvem rejste?), Reason (årsag?), Return (udbytte?), "
            "Risks (risici?), Resources (ressourcer?), Responsible (ansvarlig?), "
            "Relationship (relation til andre ændringer?)."
        ),
    },
    {
        "topic": "Change Management",
        "question": "Hvad adskiller en Standard Change fra en Normal Change?",
        "options": [
            "A. Standard Changes er dyrere og kræver mere dokumentation",
            "B. Standard Changes er pre-godkendte, gentagne og lav-risiko – kræver ingen CAB-godkendelse",
            "C. Standard Changes håndterer kun hardware; Normal Changes håndterer software",
            "D. Standard Changes kræver ECAB-godkendelse",
        ],
        "answer": "B",
        "explanation": (
            "Standard Change = pre-autoriseret, repetitiv, velkendt, lav risiko. "
            "Ingen godkendelse nødvendig hver gang. "
            "Normal Change = ny/ukendt ændring der kræver CAB-vurdering og godkendelse."
        ),
    },
    {
        "topic": "DevOps",
        "question": "Hvad er forskellen på Continuous Delivery og Continuous Deployment?",
        "options": [
            "A. De er identiske begreber",
            "B. Continuous Delivery deployer automatisk; Continuous Deployment kræver manuel godkendelse",
            "C. Continuous Delivery kræver manuel godkendelse til produktion; Continuous Deployment er fuldt automatisk",
            "D. Continuous Delivery dækker kun test; Continuous Deployment dækker kun produktion",
        ],
        "answer": "C",
        "explanation": (
            "CI = auto test + integrer. "
            "Continuous Delivery = kode er altid deployerbar, men deploy til "
            "produktion kræver menneskelig godkendelse. "
            "Continuous Deployment = alt automatisk, kode går direkte til produktion ved grøn test."
        ),
    },
    {
        "topic": "DevOps",
        "question": "Hvorfor opstår siloer mellem Dev og Ops?",
        "options": [
            "A. Dev og Ops bruger forskellige programmeringssprog",
            "B. Dev belønnes for features; Ops straffes for nedetid – modsatrettede incitamenter",
            "C. De sidder i forskellige bygninger",
            "D. Ops har ikke adgang til kildekoden",
        ],
        "answer": "B",
        "explanation": (
            "Dev (inventors) belønnes for at levere nye features. "
            "Ops (mechanics) straffes for nedetid. "
            "Disse modsatrettede incitamenter skaber siloer. "
            "DevOps løser det ved at gøre feature-levering og stabilitet til delte mål."
        ),
    },
    {
        "topic": "PRINCE2",
        "question": "Hvad betyder princippet 'Manage by Exception' i PRINCE2?",
        "options": [
            "A. Projektlederen håndterer alle undtagelser selv uden at involvere styregruppen",
            "B. Projektstyregruppen involveres KUN ved (potentielle) problemer eller afvigelser",
            "C. Alle ændringer behandles som undtagelser og kræver fuld godkendelse",
            "D. Undtagelser fra planen ignoreres hvis de er under 10% afvigelse",
        ],
        "answer": "B",
        "explanation": (
            "Manage by Exception: et projekt der kører godt behøver ikke megen "
            "ledelsesintervention. Styregruppen informeres KUN når tolerancerne "
            "overskrides. Det frigiver ledelsestid til strategiske beslutninger."
        ),
    },
    {
        "topic": "PRINCE2",
        "question": "Hvad er PRINCE2 en forkortelse for?",
        "options": [
            "A. Project Resource Integration Network for Controlled Environments",
            "B. PRojects IN Controlled Environments",
            "C. Process Review IN Complex Enterprises",
            "D. Project Reporting and Integration for Networked Controlled Environments",
        ],
        "answer": "B",
        "explanation": (
            "PRINCE2 = PRojects IN Controlled Environments. "
            "En struktureret projektledelsesmetode med fokus på business "
            "justification, definerede roller og produktbaseret tilgang."
        ),
    },
    {
        "topic": "Cloud",
        "question": "Hvad er Shared Responsibility Model?",
        "options": [
            "A. Kunden er ansvarlig for alt i skyen",
            "B. Cloud-udbyderen er ansvarlig for alt",
            "C. Ansvaret deles mellem udbyder og kunde – forskelligt afhængig af IaaS/PaaS/SaaS",
            "D. Shared Responsibility gælder kun ved hybrid cloud",
        ],
        "answer": "C",
        "explanation": (
            "Ved IaaS er kunden ansvarlig for OS, apps og data. "
            "Ved PaaS er udbyderen ansvarlig for runtime og OS. "
            "Ved SaaS er udbyderen ansvarlig for næsten alt. "
            "Kunden er ALTID ansvarlig for egne data og adgangsstyring."
        ),
    },
    {
        "topic": "Cloud",
        "question": "Microsoft 365 er et eksempel på hvad?",
        "options": [
            "A. IaaS",
            "B. PaaS",
            "C. SaaS",
            "D. Hybrid Cloud",
        ],
        "answer": "C",
        "explanation": (
            "SaaS (Software as a Service) = færdigt program via browser/app "
            "hvor leverandøren håndterer alt det tekniske. "
            "Andre eksempler: e-conomic, Netflix, Salesforce."
        ),
    },
    {
        "topic": "Netværk",
        "question": "Hvilken OSI-lag arbejder en Switch på?",
        "options": [
            "A. Lag 1 (Physical)",
            "B. Lag 2 (Data Link) – MAC-adresser",
            "C. Lag 3 (Network) – IP-adresser",
            "D. Lag 4 (Transport)",
        ],
        "answer": "B",
        "explanation": (
            "Hub = Lag 1 (dum, sender til alle porte). "
            "Switch = Lag 2 (lærer MAC-adresser, sender kun til modtager). "
            "Router = Lag 3 (IP-adresser, forbinder netværk)."
        ),
    },
    {
        "topic": "Netværk",
        "question": "Hvad er formålet med VLAN-segmentering i jeres portfolio-virksomhed?",
        "options": [
            "A. At øge netværkshastigheden",
            "B. At spare på switches",
            "C. At begrænse spredning af angreb (fx ransomware) ved at isolere afdelinger",
            "D. At gøre firewall-konfiguration nemmere",
        ],
        "answer": "C",
        "explanation": (
            "VLAN-segmentering (HR, Finance, Guest, Server) sikrer at et "
            "ransomware-angreb der kompromitterer ét segment ikke automatisk "
            "spreder sig til resten. Defence in depth via netværksisolation."
        ),
    },
    {
        "topic": "Kryptering",
        "question": "Hvad er forskellen på hashing og kryptering?",
        "options": [
            "A. Hashing er tovejs; kryptering er envejs",
            "B. Hashing er envejs og kan ikke gendannes; kryptering er tovejs og kan dekrypteres",
            "C. De er det samme – bare forskellige ord for det samme",
            "D. Hashing bruges til netværk; kryptering bruges til filer",
        ],
        "answer": "B",
        "explanation": (
            "Hash = envejs fingeraftryk – kan ikke gendannes. Bruges til passwords. "
            "Kryptering = tovejs – kan dekrypteres med korrekt nøgle. "
            "Bruges til sikker kommunikation, VPN, HTTPS."
        ),
    },
    {
        "topic": "MDM",
        "question": "Hvad er forskellen på MDM og MAM i et BYOD-scenarie?",
        "options": [
            "A. MDM styrer kun apps; MAM styrer hele enheden",
            "B. MDM styrer hele enheden (OS-niveau); MAM styrer kun firma-apps og -data",
            "C. De er identiske – MDM og MAM er synonymer",
            "D. MDM bruges til iOS; MAM bruges til Android",
        ],
        "answer": "B",
        "explanation": (
            "MDM (Mobile Device Management) = hele enheden, OS-niveau. "
            "Bruges til firmaejet udstyr. Remote wipe sletter ALT. "
            "MAM (Mobile Application Management) = kun firma-apps og -data. "
            "Remote wipe rammer kun firmadelen – privat data bevares. BYOD-løsningen."
        ),
    },
    {
        "topic": "SLA",
        "question": "Hvad er forholdet mellem SLA, OLA og Underpinning Contract?",
        "options": [
            "A. De er tre navne for det samme dokument",
            "B. SLA = intern; OLA = ekstern kunde; UC = intern team",
            "C. SLA = ekstern kunde; OLA = interne teams; UC = ekstern leverandør – og OLA/UC skal være strammere end SLA",
            "D. UC erstattes altid af en SLA ved outsourcing",
        ],
        "answer": "C",
        "explanation": (
            "SLA = aftale med den eksterne kunde. "
            "OLA = aftale mellem interne teams der leverer til hinanden. "
            "UC = kontrakt med ekstern leverandør/supplier. "
            "OLA'er og UC'er SKAL være strammere end SLA'en – de er fundamentet den hviler på."
        ),
    },
    {
        "topic": "GDPR",
        "question": "Inden for hvor mange timer skal et databrud anmeldes til Datatilsynet?",
        "options": [
            "A. 24 timer",
            "B. 48 timer",
            "C. 72 timer",
            "D. 7 dage",
        ],
        "answer": "C",
        "explanation": (
            "GDPR 72-timers reglen: databrud skal anmeldes til Datatilsynet "
            "SENEST 72 timer efter opdagelse. "
            "Dette er et af de GDPR-krav der ikke er oplagt i ISO 27001."
        ),
    },
]


# ---------------------------------------------------------------------------
# ORAL EXAM BOARD QUESTIONS (free text, level 2)
# These are imported by app.py and used directly.
# The full grading logic lives in grade_answer() above.
# ---------------------------------------------------------------------------

BOARD_QUESTIONS = [
    {
        "id": "board_01",
        "topic": "ITIL",
        "question": (
            "Censor 1: 'Hvad er ITIL, og forklar Service Value Chain. "
            "Nævn derefter mindst tre af de 7 Guiding Principles.'"
        ),
        "groups": [
            ("ITIL = rammeværk for ITSM, leverandør-uafhængigt",
             [r"itsm", r"service\s*management", r"rammev", r"framework",
              r"best\s*practice", r"infrastructure\s+library"]),
            ("Plan", [r"\bplan\b"]),
            ("Engage", [r"engage"]),
            ("Design & Transition", [r"design", r"transition"]),
            ("Obtain/Build + Deliver & Support + Improve",
             [r"obtain", r"build", r"deliver", r"support", r"improve", r"forbedr"]),
            ("Guiding Principles (focus on value, iterate, automate...)",
             [r"focus\s+on\s+value", r"start\s+where\s+you\s+are",
              r"iterat", r"collaborat", r"holisti", r"keep\s+it\s+simple",
              r"optimi[sz]e\s+and\s+automate", r"automat"]),
        ],
        "points": 8,
        "threshold": 4,
        "post_mortem_title": "ITIL Service Value Chain",
        "post_mortem": (
            "ITIL er ikke et produkt eller en teknologi – det er et sæt best "
            "practices for IT Service Management der kan tilpasses enhver organisation. "
            "Service Value Chain er kernemodellen: seks aktiviteter der omformer "
            "demand og opportunity til value. De arbejder ikke lineært – de "
            "kombineres i 'value streams' tilpasset den konkrete service. "
            "De 7 Guiding Principles er vejledende under hele ITIL-rejsen. "
            "'Optimize and automate' er den der typisk giver 12-point-svar: "
            "manuelt arbejde er en fejl – reserver menneskelig indsats til det "
            "der kræver dømmekraft."
        ),
    },
    {
        "id": "board_02",
        "topic": "ITIL",
        "question": (
            "Censor 2: 'En server er nede – og det er femte gang denne måned. "
            "Forklar med ITIL-begreber forskellen på Incident Management og "
            "Problem Management.'"
        ),
        "groups": [
            ("IM = genopret service SÅ HURTIGT som muligt",
             [r"genopret", r"restore", r"hurtig", r"as\s+fast"]),
            ("IM bruger workarounds og kræver INGEN godkendelse",
             [r"workaround", r"midlertidig", r"ingen\s+godkend",
              r"no\s+approval"]),
            ("PM = find og fjern ROOT CAUSE",
             [r"root\s*cause", r"rod[aå]rsag", r"problem\s+management"]),
            ("Reaktiv vs proaktiv PM",
             [r"\b5\b.{0,30}(gang|times)", r"reactive", r"proactive",
              r"reaktiv", r"proaktiv", r"gentag"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "Incident vs Problem Management",
        "post_mortem": (
            "Den klassiske fejl: behandle det som én stor proces. "
            "Incident Management har ét mål – genopret. Hurtigt. En workaround "
            "er en valid løsning i IM. Problem Management starter EFTER (eller "
            "parallelt med) – og dens mål er at sikre at incidenten aldrig "
            "opstår igen. 5-gange-reglen er en tommelfingerregel: gentagne "
            "incidents af samme type er et symptom på et ubehandlet problem. "
            "En Known Error er en midlertidig status: vi kender rodårsagen men "
            "har endnu ikke en permanent løsning. Den fjernes via en Change Request."
        ),
    },
    {
        "id": "board_03",
        "topic": "ITIL",
        "question": (
            "Censor 1: 'I skal bygge et servicecenter op. Beskriv servicedesken "
            "opgaver, escalation flow (linje 0-3) og hvad Priority 1 – Critical kræver.'"
        ),
        "groups": [
            ("log, kategorisér og prioritér alle henvendelser",
             [r"log", r"kategoris", r"prioriter"]),
            ("Linje 0 = self-help (FAQ, wiki, chatbot)",
             [r"linje\s*0", r"self.?help", r"faq", r"wiki", r"chatbot"]),
            ("Linje 1 = servicedesk løser simple/kendte problemer",
             [r"linje\s*1", r"service\s*desk", r"f[oø]rste.?linje"]),
            ("Linje 2-3 = eksperter, nye/ukendte problemer",
             [r"linje\s*2", r"2nd", r"3rd", r"ekspert", r"specialist"]),
            ("P1: immediate response, ~1 times resolution, 2nd/3rd level",
             [r"immediate", r"straks", r"1\s*(time|hour)", r"system\s+down"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "Servicedesk & Escalation",
        "post_mortem": (
            "Linje 0 er undervurderet: en god FAQ eller chatbot der løser 30% "
            "af henvendelserne er billigere end 30% flere L1-agenter. "
            "Prioritetsmatricen er ikke tilfældig – response time og resolution "
            "target er præcis hvad SLA'en lover kunden. P1 Critical med "
            "'immediate response og 1-times resolution' er bindende. "
            "Eskalation sker IKKE kun opad – horisontale eskalationer til "
            "specialister på samme niveau er hyppige og vigtige."
        ),
    },
    {
        "id": "board_04",
        "topic": "Change Management",
        "question": (
            "Censor 2: 'Jeres team vil migrere økonomi-systemet fra fysisk til "
            "virtuel server. Hvilken change-type, hvem godkender, og hvad siger "
            "de 7 R'er I skal afklare?'"
        ),
        "groups": [
            ("Normal change -> CAB-godkendelse",
             [r"normal\s+change", r"\bcab\b", r"change\s+advisory"]),
            ("kender Standard og Emergency",
             [r"standard\s+change", r"pre.?godkendt", r"emergency", r"ecab"]),
            ("RFC + back-out/rollback-plan + testmiljø",
             [r"\brfc\b", r"request\s+for\s+change", r"back.?out",
              r"rollback", r"testmilj"]),
            ("7 R'er (nævner mindst tre)",
             [r"raised", r"reason", r"return", r"risks?", r"resources",
              r"responsible", r"relationship"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "Change Management",
        "post_mortem": (
            "De 7 R'er er ikke bureaukrati – de er en tjekliste der sikrer "
            "at ingen har glemt noget vigtigt inden implementeringen. "
            "Back-out planen er den vigtigste: hvad gør vi kl. 03:00 hvis "
            "migreringsscriptet fejler? En Normal Change der ikke har en "
            "back-out plan bør ikke godkendes af CAB. "
            "Emergency Changes håndteres anderledes: ECAB mødes, ændringen "
            "laves, og den formelle skriftlige godkendelse gives efterfølgende."
        ),
    },
    {
        "id": "board_05",
        "topic": "SLA",
        "question": (
            "Censor 1: 'Studieordningen siger, du skal kunne UDARBEJDE en SLA. "
            "Skitsér indholdet – og forklar hvordan OLA'er og Underpinning "
            "Contracts skal understøtte den.'"
        ),
        "groups": [
            ("scope: hvilke services er dækket",
             [r"scope", r"services?\b", r"omfang"]),
            ("målbare mål: oppetid + response/resolution tider pr. prioritet",
             [r"99[.,]9", r"oppetid", r"uptime", r"response\s*time",
              r"resolution", r"reaktionstid"]),
            ("måling og rapportering (KPI'er)",
             [r"kpi", r"m[aå]l(ing|es)", r"rapport", r"metric"]),
            ("konsekvenser/eskalation ved brud + ansvar",
             [r"sanktion", r"konsekvens", r"eskaler", r"penalty", r"ansvar"]),
            ("SLA = kunde; OLA = interne; UC = ekstern leverandør (skrappere)",
             [r"ola", r"underpinning", r"\buc\b", r"skrapper", r"strammere",
              r"underst[oø]t"]),
        ],
        "points": 10,
        "threshold": 3,
        "post_mortem_title": "SLA Design",
        "post_mortem": (
            "En SLA der ikke er målbar er ikke en SLA – det er et ønske. "
            "Hvert serviceniveau skal have konkrete tal: 99,9% oppetid, "
            "10 minutters response på P2, 4 timers resolution. "
            "OLA'er og UC'er er det interne og eksterne fundament SLA'en "
            "hviler på. Hvis din interne IT-afdeling kun lover dig 95% "
            "oppetid, kan du ikke love kunden 99,9%. "
            "Hierarkiet er: UC/OLA er strammere end SLA."
        ),
    },
    {
        "id": "board_06",
        "topic": "iAAA",
        "question": (
            "Censor 2 (JHB): 'iAAA er nøglen til det hele. Forklar de fire "
            "begreber og useradministration-lifecycle: on- og offboarding.'"
        ),
        "groups": [
            ("Identification = hævder hvem du er",
             [r"identifi", r"h[aæ]vder", r"brugernavn", r"claim"]),
            ("Authentication = verificerer (MFA, biometri)",
             [r"authenti", r"verific", r"password", r"mfa", r"biometri"]),
            ("Authorization = adgang tildeles (RBAC/PoLP)",
             [r"authori[sz]", r"rbac", r"least\s+privilege", r"polp"]),
            ("Accountability = logging/audit",
             [r"accountab", r"logg?ing", r"audit", r"siem", r"ansvar"]),
            ("lifecycle: onboarding, rolleskift, offboarding (deaktiver først)",
             [r"onboard", r"offboard", r"deaktiver", r"disable",
              r"lifecycle", r"livscyklus"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "iAAA & Useradministration",
        "post_mortem": (
            "JHB's pointe: useradministration er fundamentet fordi alt andet "
            "hviler på at vi ved præcist hvem der har adgang til hvad. "
            "En konto der ikke lukkes ved offboarding er en åben dør. "
            "Deaktivér FØRST (data bevares, historik bevares) – slet efter "
            "karantæneperioden. Accountability via logging er det der gør "
            "det muligt at bruge logs som retsgyldig dokumentation: "
            "integritets-hashing af logs er afgørende (en angriber der "
            "ændrer logs bryder Integrity i CIA-triaden)."
        ),
    },
    {
        "id": "board_07",
        "topic": "Risikoanalyse",
        "question": (
            "Censor 1: 'Skriv risikoformlen fra BÅDE ledelsens og analytikerens "
            "perspektiv. Forklar sammenhængen og de fire måder at behandle en risiko.'"
        ),
        "groups": [
            ("CEO: RISK = Likelihood × Consequence",
             [r"likelihood\s*[x*×]\s*consequence",
              r"sandsynlighed\s*[x*×]\s*konsekvens"]),
            ("Analytiker: RISK = Threat × Vulnerability × Impact",
             [r"threat\s*[x*×]\s*vulnerab", r"trussel\s*[x*×]\s*s[aå]rbar"]),
            ("Threat × Vulnerability = Likelihood",
             [r"(threat|trussel).{0,40}=\s*likelihood",
              r"udg[oø]r\s+likelihood"]),
            ("risk matrix / score",
             [r"matrix", r"score", r"extreme", r"gr[oø]n", r"r[oø]d"]),
            ("4 behandlinger: Mitigate, Accept, Transfer, Avoid",
             [r"mitigat", r"accept", r"transfer", r"avoid"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "Risikoformler",
        "post_mortem": (
            "De to formler er ikke konkurrerende – de er perspektiver. "
            "IT-analytikeren leverer Threat × Vulnerability (den tekniske "
            "sandsynlighedsdel). Ledelsen/CEO leverer Impact/Consequence "
            "(forretningsdelen – det kræver forretningsviden). "
            "Risikomatricen konverterer det til en handling: "
            "Extreme og High kræver behandling. Moderate overvejes. "
            "Low accepteres. De fire behandlingsformer er ikke hierarkiske – "
            "man vælger den der passer bedst til risikoprofilen."
        ),
    },
    {
        "id": "board_08",
        "topic": "ISO 27001",
        "question": (
            "Censor 2: 'Forklar forholdet mellem ISO 27001, et ISMS og SoA'en. "
            "Hvad styrer Annex A-kontrolvalget, og hvordan er PDCA bygget ind?'"
        ),
        "groups": [
            ("ISMS = samlet system; ISO 27001 = kravene",
             [r"isms", r"management\s+system", r"ledelsessystem"]),
            ("SoA = valgte/fravalgte kontroller og HVORFOR",
             [r"soa", r"statement\s+of\s+applicability", r"fravalg"]),
            ("RISIKOVURDERINGEN styrer kontrolvalget",
             [r"risikovurdering", r"risk\s+assessment",
              r"risiko.{0,40}(styrer|v[aæ]lger|driver)"]),
            ("Annex A: 93 kontroller, 4 temaer",
             [r"93", r"annex\s*a", r"4\s+temaer", r"organisatorisk"]),
            ("PDCA i HLS: kap 4-6 Plan, 7-8 Do, 9 Check, 10 Act",
             [r"pdca", r"plan.?do.?check.?act", r"kap(itel)?\s*4", r"hls"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "ISO 27001 & ISMS",
        "post_mortem": (
            "ISO 27001 er ikke ISMS'et – det er standarden der definerer "
            "kravene til et ISMS. Som JHB siger: ISO 27001 must NOT be just "
            "another paper. PDCA er ikke bare en model – det er direkte "
            "bygget ind i kapitelstrukturen (HLS). Plan=4-6, Do=7-8, "
            "Check=9, Act=10. SoA'en er beviset: den viser en ekstern auditor "
            "præcis hvilke kontroller I har valgt, fravalgt og HVORFOR. "
            "Uden SoA ingen certificering."
        ),
    },
    {
        "id": "board_09",
        "topic": "ISO 27001",
        "question": (
            "Censor 1: 'Virksomheden vil ISO 27001-certificeres. Forklar "
            "Stage 1 vs Stage 2-audit, hvad der sker bagefter, og forskellen "
            "på minor og major non-conformity.'"
        ),
        "groups": [
            ("Stage 1 = dokumentationsgennemgang",
             [r"stage\s*1.{0,80}(dokument|paper|politik)"]),
            ("Stage 2 = feltevaluering (virker det i praksis?)",
             [r"stage\s*2.{0,80}(praksis|felt|practice)"]),
            ("årlige surveillance audits + re-certificering hvert 3. år",
             [r"surveillance", r"3\.?\s*[aå]r", r"re.?certificer"]),
            ("minor = isoleret; major = systemisk, kan blokere",
             [r"minor.{0,80}(isoler|enkelt)", r"major.{0,80}(system|bloker)",
              r"non.?conformit"]),
        ],
        "points": 8,
        "threshold": 2,
        "post_mortem_title": "ISO 27001 Certificering",
        "post_mortem": (
            "Stage 1 og Stage 2 er ikke bare to ture fra auditoren – "
            "de tester fundamentalt forskellige ting. Stage 1 checker om I "
            "HAR politikkerne. Stage 2 checker om I LEVER efter dem. "
            "En organisation der har fine dokumenter men ingen praksis "
            "dumper Stage 2. "
            "Surveillance audits er hvad der holder certifikatet gyldigt "
            "mellem de treårige re-certificeringer. "
            "Major non-conformity = systemisk svigt. Én isoleret fejl er "
            "minor. Fem af de samme fejl er major."
        ),
    },
    {
        "id": "board_10",
        "topic": "GDPR",
        "question": (
            "Censor 2: 'En medarbejder finder et print med persondata ved "
            "kopimaskinen efter en ekstern tekniker. Hvad gør I – og hvilke "
            "GDPR-begreber er i spil? (JHB's øvelse)'"
        ),
        "groups": [
            ("sikr dokumentet straks + rapportér til leder/DPO",
             [r"sikr", r"beskyt", r"fjern", r"rapport", r"dpo", r"leder"]),
            ("72-timers reglen: anmeld til Datatilsynet",
             [r"72", r"datatilsynet", r"anmeld"]),
            ("forebyg: Clear Desk Policy, besøgsregler",
             [r"clear\s*desk", r"bes[oø]gs", r"printer", r"politik"]),
            ("kender GDPR-begreber: DSAR, retten til at blive glemt, privacy by design",
             [r"dsar", r"blive\s+glemt", r"privacy\s+by\s+design",
              r"databehandler"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "GDPR Incident Response",
        "post_mortem": (
            "JHB's øvelse er designet til at vise at GDPR ikke er teoretisk. "
            "En tekniker der efterlader persondata = potentielt databrud. "
            "72-timers reglen gælder fra OPDAGELSE – ikke fra bruddet. "
            "Selv uden formelle politikker er man bundet af loven. "
            "Scenariet bekræfter præcis behovet for de politikker I er ved "
            "at implementere. Brug det som case til at drive ISMS fremad."
        ),
    },
    {
        "id": "board_11",
        "topic": "Backup & DR",
        "question": (
            "Censor 1: 'Forklar backup-agentens rolle i et SQL-setup, "
            "forskellen på SAN og NAS, 3-2-1-reglen – og hvad MAO er.'"
        ),
        "groups": [
            ("agenten læser fra SQL, krypterer, sender til storage",
             [r"agent.{0,120}(l[aæ]ser|henter|sender|krypter)",
              r"backup\s*manager", r"storage\s*server"]),
            ("inkrementel backup",
             [r"inkrement", r"kun.{0,30}[aæ]ndr"]),
            ("SAN = block-level; NAS = file-level",
             [r"san.{0,80}block", r"nas.{0,80}file"]),
            ("3-2-1 + TEST RESTORE",
             [r"3.?2.?1", r"test.{0,30}(restore|gendan)", r"utestet"]),
            ("MAO = RPO + RTO ≤ MAO, defineres i BIA",
             [r"mao", r"rpo\s*\+\s*rto", r"\bbia\b"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "Backup Architecture",
        "post_mortem": (
            "Backup-agenten er intelligent: inkrementel backup sender kun "
            "det der er ændret siden sidst. Det sparer båndbredde og tid. "
            "SAN vs NAS: SAN er block-level (som en intern harddisk over "
            "netværk), NAS er file-level (som et netværksdrev). "
            "MAO er det overordnede loft: RPO + RTO MÅ ikke overstige MAO. "
            "Og den vigtigste sætning til enhver censor: "
            "en utestet backup er ikke en backup – det er en hypotese."
        ),
    },
    {
        "id": "board_12",
        "topic": "CMMI",
        "question": (
            "Censor 2: 'Vurder modenhedsniveauet: alle incidents løses af én "
            "heroisk admin uden dokumenterede processer. Placér på CMMI-skalaen, "
            "nævn alle 5 niveauer og læg plan til Level 3. Må man springe?'"
        ),
        "groups": [
            ("Level 1 Initial: ad hoc, hero-kultur",
             [r"(level|niveau)\s*1", r"initial", r"ad\s*hoc", r"hero"]),
            ("niveauerne: Managed, Defined, Quantitatively Managed, Optimizing",
             [r"managed", r"defined", r"quantitat", r"optimi[sz]"]),
            ("Level 3 = processer på ORGANISATIONSNIVEAU",
             [r"organisationsniveau", r"samme\s+(regler|processer)"]),
            ("må IKKE springe niveauer",
             [r"ikke.{0,30}spring", r"cannot\s+skip", r"fundament"]),
            ("plan: dokumentér, ITIL, metrics",
             [r"dokumenter", r"itil", r"metric", r"staged", r"continuous"]),
        ],
        "points": 10,
        "threshold": 3,
        "post_mortem_title": "CMMI Strategisk Case",
        "post_mortem": (
            "CMMI's business case er stærk: +35% produktivitet, -19% time "
            "to market, -39% fejl efter release. Men det kræver tålmodighed. "
            "Level 1 til Level 3 tager typisk 2-3 år for en organisation. "
            "Staged repræsentation viser hele organisationens niveau – godt "
            "til benchmarking. Continuous viser specifikke procesområders "
            "niveau – godt til intern prioritering. "
            "Husk: ITIL og CMMI er komplementære – ITIL giver processerne, "
            "CMMI måler modenhedsgraden af dem."
        ),
    },
    {
        "id": "board_13",
        "topic": "Virtualisering",
        "question": (
            "Censor 1: 'Type 1 vs Type 2 hypervisor med eksempler. Fordele "
            "ved virtualisering, noisy neighbor, og hvornår vælger man "
            "stadig fysisk server?'"
        ),
        "groups": [
            ("Type 1 = bare-metal (ESXi, Hyper-V, KVM)",
             [r"type\s*1.{0,120}(bare.?metal|direkte|esxi|hyper.?v|kvm)"]),
            ("Type 2 = hosted (VirtualBox, Workstation)",
             [r"type\s*2.{0,120}(hosted|oven|virtualbox|workstation)"]),
            ("fordele: konsolidering, snapshots, skalering, failover",
             [r"konsolider", r"snapshot", r"skaler", r"failover"]),
            ("noisy neighbor + overhead",
             [r"noisy\s+neighbor", r"overhead"]),
            ("fysisk: HPC, store databaser, compliance",
             [r"hpc", r"stor.{0,20}(database|sql)", r"complian", r"fysisk\s+isolation"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "Virtualisering",
        "post_mortem": (
            "Valget er ikke binært. De fleste organisationer kører en blanding: "
            "95% virtualiseret for fleksibilitet, og en håndfuld fysiske "
            "servere til workloads der kræver dedikerede ressourcer. "
            "Snapshots er undervurderede i driften: en snapshot inden en "
            "patch-runde giver en rollback-mulighed på sekunder. "
            "ROI-regnestykket taler for virtualisering i langt de fleste tilfælde."
        ),
    },
    {
        "id": "board_14",
        "topic": "ROI",
        "question": (
            "Censor 2: '10 fysiske servere -> virtualiseret. Investering "
            "200.000 kr, årlig besparelse 120.000 kr. ROI-formlen, ROI "
            "efter 2 år, og sammenhængen med Change Management.'"
        ),
        "groups": [
            ("ROI = (gevinst - investering) / investering × 100",
             [r"gevinst\s*-\s*invest", r"return\s+on\s+investment"]),
            ("20% / break-even under 2 år",
             [r"40\.?000", r"20\s*%", r"break.?even"]),
            ("ROI = business case til ledelsen; CM = kontrolleret gennemførelse",
             [r"roi.{0,120}(ledelse|business\s*case|godkend)",
              r"change\s*management.{0,120}(kontrol|kaos|risiko|back.?out)"]),
        ],
        "points": 8,
        "threshold": 2,
        "post_mortem_title": "ROI & Change Management",
        "post_mortem": (
            "ROI er ikke bare et tal – det er et argument. "
            "200.000 kr investering, 120.000 kr/år besparelse = break-even "
            "på under 2 år. ROI = (240.000 - 200.000) / 200.000 × 100 = 20%. "
            "Change Management sikrer at investeringen ikke ødelægges af en "
            "fejlslået implementering. "
            "De to hænger uløseligt sammen: ROI overbeviser ledelsen om at "
            "investere, Change Management sikrer at de får det de betalte for."
        ),
    },
    {
        "id": "board_15",
        "topic": "Cloud",
        "question": (
            "Censor 1: 'IaaS, PaaS og SaaS med eksempler. Public/private/"
            "hybrid cloud. Hvad betyder Shared Responsibility Model?'"
        ),
        "groups": [
            ("IaaS = rå infrastruktur/VMs",
             [r"iaas.{0,80}(infrastruktur|hardware|vm)"]),
            ("PaaS = platform til at udvikle",
             [r"paas.{0,80}(platform|udvikl|milj)"]),
            ("SaaS = færdigt program via browser (M365, e-conomic)",
             [r"saas.{0,80}(f[aæ]rdig|program|browser|365)"]),
            ("public/private/hybrid + elasticitet",
             [r"public", r"private", r"hybrid", r"elastic", r"on.?demand"]),
            ("Shared Responsibility: delt ansvar udbyder/kunde pr. lag",
             [r"shared\s+responsibility", r"delt\s+ansvar"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "Cloud Architecture",
        "post_mortem": (
            "Shared Responsibility er den vigtigste konceptuelle forskel "
            "mellem on-premise og cloud. "
            "IaaS: du patcher OS'et selv. PaaS: udbyderen patcher OS, "
            "du patcher din app. SaaS: udbyderen patcher alt – du "
            "konfigurerer kun. Men data og adgangsstyring er ALTID "
            "kundens ansvar uanset model. Det er der, de fleste cloud-brud sker."
        ),
    },
    {
        "id": "board_16",
        "topic": "DevOps",
        "question": (
            "Censor 2: 'Siloer mellem Dev og Ops – og forskellen på CI, "
            "Continuous Delivery og Continuous Deployment. IaC og MTTR.'"
        ),
        "groups": [
            ("Dev belønnes for features, Ops straffes for nedetid",
             [r"bel[oø]nn.{0,60}features", r"straffes.{0,60}nedetid",
              r"inventors", r"mechanics"]),
            ("CI = automatisk test + integration",
             [r"\bci\b.{0,120}(auto|test|integr)"]),
            ("Continuous Delivery = altid deployerbar, MANUEL deploy til prod",
             [r"delivery.{0,140}(manuel|manual|godkend)"]),
            ("Continuous Deployment = fuldt automatisk",
             [r"deployment.{0,140}(auto|fuldt)", r"fuldt\s+auto"]),
            ("IaC = programmerbar infrastruktur; MTTR forbedres",
             [r"infrastructure\s+as\s+code", r"\biac\b", r"mttr"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "DevOps & CI/CD",
        "post_mortem": (
            "Siloer er ikke et personlighedsproblem – de er et "
            "incitamentsstruktur-problem. Løsningen er ikke at bede folk "
            "om at samarbejde bedre, men at gøre feature-levering og "
            "stabilitet til delte mål. "
            "CI/CD-distinktionen er kritisk til eksamen: "
            "Continuous Delivery er IKKE det samme som Continuous Deployment. "
            "Delivery = kode er klar, menneske godkender deploy. "
            "Deployment = alt automatisk. Mange organisationer foretrækker "
            "Delivery netop fordi et menneske har det sidste ord."
        ),
    },
    {
        "id": "board_17",
        "topic": "PRINCE2",
        "question": (
            "Censor 1: 'PRINCE2-forkortelse, tre principper inkl. Manage by "
            "Exception og Continued Business Justification, og vigtigste "
            "management products.'"
        ),
        "groups": [
            ("PRojects IN Controlled Environments",
             [r"controlled\s+environments"]),
            ("Continued Business Justification: altid retfærdiggørligt",
             [r"business\s+justification", r"retf[aæ]rdigg"]),
            ("Manage by Exception: styregruppe kun ved problemer",
             [r"exception.{0,120}(kun|problem|afvig)"]),
            ("øvrige principper (mindst to)",
             [r"learn\s+from\s+experience", r"roles", r"stages",
              r"focus\s+on\s+products", r"tailor"]),
            ("management products: Business Case, Risk Register, Lessons Log",
             [r"business\s+case", r"risk\s+register", r"lessons\s+log"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "PRINCE2",
        "post_mortem": (
            "PRINCE2's styrke er struktur og dokumentation. "
            "Continued Business Justification er det princip der stopper "
            "zombieprojekter: hvis projektet ikke længere kan retfærdiggøres "
            "forretningsmæssigt, SKAL det stoppes. "
            "Manage by Exception frigiver ledelsestid: styregruppen er ikke "
            "en daglig operationskomité – de informeres kun når noget går "
            "uden for tolerancerne. "
            "26 management products lyder af meget – Lessons Log er "
            "den mest oversete og den der giver mest værdi over tid."
        ),
    },
    {
        "id": "board_18",
        "topic": "Netværk",
        "question": (
            "Censor 2: 'Tegn netværket for 500-ansatte virksomheden: "
            "VLAN-segmentering mod ransomware, OSI-lag for hub/switch/router, "
            "firewall/IDS/IPS og DMZ.'"
        ),
        "groups": [
            ("VLAN begrænser spredning (HR, Finance, Guest, Server)",
             [r"vlan", r"segment", r"begr[aæ]ns.{0,40}(spredning|angreb)"]),
            ("hub=lag 1, switch=lag 2, router=lag 3",
             [r"hub.{0,60}(lag|layer)\s*1", r"switch.{0,60}(lag|layer)\s*2",
              r"router.{0,60}(lag|layer)\s*3"]),
            ("firewall filtrerer trafik",
             [r"firewall.{0,80}(filtrer|regler|deny|bloker)"]),
            ("IDS opdager / IPS blokerer; honeypot",
             [r"ids", r"ips", r"intrusion", r"honeypot"]),
            ("DMZ isolerer offentlige services fra internt net",
             [r"dmz", r"demilitari", r"subnet"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "Netværksarkitektur",
        "post_mortem": (
            "VLAN-segmentering er den vigtigste enkelt-kontrol mod "
            "lateral movement i et netværk. Ransomware der kompromitterer "
            "HR-segmentet skal ikke automatisk kunne nå Finance. "
            "IDS opdager og alerter – IPS blokerer aktivt. "
            "Honeypot er en lokkefælde: den har ingen legitim trafik, "
            "så enhver forbindelsesattempt er per definition mistænkelig."
        ),
    },
    {
        "id": "board_19",
        "topic": "AD/MDM",
        "question": (
            "Censor 1: 'Ny medarbejder starter mandag. Forklar onboarding-flowet "
            "med AD, GPO og MDM – og MDM vs MAM i BYOD.'"
        ),
        "groups": [
            ("AD-konto oprettes (PowerShell/CSV) i OU",
             [r"new-aduser", r"powershell", r"\bou\b", r"active\s*directory"]),
            ("GPO pusher konfiguration til OU'ens maskiner",
             [r"gpo", r"group\s*policy", r"push.{0,40}konfig"]),
            ("MDM (Intune) enroller enheder via Azure AD",
             [r"mdm", r"intune", r"enroll"]),
            ("PoLP/RBAC: kun nødvendige rettigheder",
             [r"polp", r"least\s+privilege", r"rbac"]),
            ("MDM = hele enheden; MAM = kun firmadata (BYOD)",
             [r"mam", r"byod", r"remote\s*wipe", r"hele\s+enheden"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "AD/GPO/MDM Onboarding",
        "post_mortem": (
            "Onboarding-flowet er et eksempel på iAAA i praksis: "
            "AD-kontoen giver Identification og Authentication. "
            "GPO og RBAC giver Authorization (PoLP). "
            "Logging giver Accountability. "
            "MDM vs MAM er den vigtige distinktion ved BYOD: "
            "en medarbejder der bruger sin private iPhone til firma-mail "
            "vil ikke have at IT kan remote-wipe private billeder. "
            "MAM-container løser det: firmadelen kan slettes, "
            "privat data bevares."
        ),
    },
    {
        "id": "board_20",
        "topic": "Kryptering",
        "question": (
            "Censor 2, sidst: 'Symmetrisk vs asymmetrisk kryptering, "
            "hvorfor hasher vi passwords, hvad løser Diffie-Hellman, "
            "og de tre elementer i 2FA.'"
        ),
        "groups": [
            ("symmetrisk = én delt nøgle; asymmetrisk = public/private (HTTPS)",
             [r"symmetrisk.{0,120}(en|delt|samme)\s*n[oø]gle",
              r"asymmetrisk.{0,120}(public|private|offentlig|privat)"]),
            ("hashing = envejs, kan ikke gendannes",
             [r"envejs", r"one.?way", r"ikke\s+gendan"]),
            ("Diffie-Hellman = nøgleudveksling over usikker kanal (TLS/SSH)",
             [r"diffie", r"n[oø]gleudveksling", r"usikker\s+(kanal|forbindelse)"]),
            ("2FA = HAVE + KNOW + ARE (kombination af to)",
             [r"have", r"\bare\b", r"know", r"noget\s+du\s+(har|er|ved)",
              r"2fa", r"mfa"]),
        ],
        "points": 8,
        "threshold": 3,
        "post_mortem_title": "Kryptering & 2FA",
        "post_mortem": (
            "Hashing til passwords er ikke et valg – det er et krav. "
            "Lagring af plaintext passwords er uacceptabelt. "
            "Salt tilføjes før hashing for at forhindre rainbow table-angreb: "
            "to brugere med samme password får forskellig hash. "
            "Diffie-Hellman løser et fundamentalt problem: "
            "to parter der aldrig har mødt hinanden kan etablere en "
            "fælles hemmelig nøgle over en kanal som Eve lytter på. "
            "Det er fundamentet for HTTPS, SSH og VPN."
        ),
    },
]
