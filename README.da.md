# 🔥 Production Inferno

> **IT-Operations eksamenstræner og incident simulator – terminal CLI + Streamlit browser UI.**
> Bygget direkte på EK/KEA IT-Drift pensum. Python 3, én valgfri afhængighed (Streamlit).

🇬🇧 [English version](README.md)

---

## To måder at køre det på

| Grænseflade | Fil | Kommando | Bedst til |
|-------------|-----|---------|-----------|
| **Browser UI** | `app.py` | `streamlit run app.py` | Quiz + mundtligt eksamensboard (fuldt pensum) |
| **Browser UI** | `streamlit_simulator.py` | `streamlit run streamlit_simulator.py` | Incident-scenarier med live scoreboard |
| **Terminal CLI** | `ops_simulator.py` | `python3 ops_simulator.py` | Ingen installation, kører overalt |

```bash
# Klon repo
git clone https://github.com/CodeByNajib/production-inferno.git
cd production-inferno

# Mulighed A – browser (anbefalet)
pip install streamlit
streamlit run app.py

# Mulighed B – terminal, ingen installation
python3 ops_simulator.py
```

Kræver Python 3.8+.

---

## Hvad er indeni

### Incident Simulator (`streamlit_simulator.py` + `ops_simulator.py`)

Fire isolerede service-moduler kommunikerer over en simuleret network bus.
Hvert request serialiseres til JSON før det krydser modul-grænsen – præcis
samme kontrakt-baserede isolation som rigtige microservices har over HTTP.

| Modul | Fokus | Scenarier |
|-------|-------|-----------|
| **IT-Drift** | Infrastruktur, HA, incident response | SSL-udløb, DDoS, split-brain, RTO/RPO-design |
| **Next.js Frontend** | SSR performance og arkitektur | Memory leaks, Core Web Vitals, ISR, hydration-fejl |
| **Spring Boot Backend** | Enterprise Java, concurrency, sikkerhed | HikariCP pool starvation, race conditions, circuit breakers, thread dump-analyse |
| **PostgreSQL** | Databaseadministration | Live psql REPL – B-Tree vs GIN indexes, deadlock-opløsning, read replicas, window functions |

### Eksamensboard + Quiz (`app.py` + `engine.py`)

Bygget direkte på EK/KEA IT-Drift studieordningen. Dækker hele pensum:

- **ITIL 4** – Service Value Chain, Guiding Principles, Incident/Problem/Change/Release Management, CMDB, Servicedesk, eskalationsflow
- **ISO 27001** – ISMS, SoA, Annex A (93 kontroller), PDCA/HLS, Stage 1/2-audit, non-conformity
- **Risikoanalyse** – CIA-triaden, iAAA, risikoformler (CEO vs. analytiker), 4 behandlingsformer, risk matrix
- **GDPR** – 72-timers regel, DSAR, privacy by design, databehandleraftale
- **SLA/OLA/UC** – SLA-design, OLA/UC-hierarki, KPI'er, eskalation ved brud
- **CMMI** – 5 modenhedsniveauer, staged vs. continuous, business case (+35% produktivitet)
- **Backup & DR** – Backup-agentarkitektur, SAN vs. NAS, 3-2-1, RPO/RTO/MAO, BIA
- **Virtualisering** – Type 1/2 hypervisor, VM vs. fysisk server, noisy neighbor, ROI
- **Cloud** – IaaS/PaaS/SaaS, public/private/hybrid, Shared Responsibility Model
- **Change Management & DevOps** – 7 R'er, CAB/ECAB, CI/CD/Deployment, IaC, MTTR, siloer
- **PRINCE2** – 7 principper, 7 temaer, 7 processer, management products
- **Netværk & AD** – VLAN-segmentering, OSI-lag, DMZ, IDS/IPS, AD/GPO/MDM/MAM, BYOD

**Quiz:** 35 multiple choice-spørgsmål, filtrérbare per emne.

**Eksamensboard:** 20 fri-tekst-spørgsmål. En keyword-gruppe-grader scorer dit svar
mod de koncepter en censor lytter efter og fortæller præcis hvad du manglede.
Hvert spørgsmål afsluttes med en Senior Engineer Post-Mortem.

---

## Sådan fungerer karaktergivning

Svar er fri tekst – ikke multiple choice på boardet. Graderingsmotoren scorer dit
svar mod konceptgrupper og rapporterer præcis hvilke du ramte og hvilke du missede.

PostgreSQL REPL'en er live: skriv rigtige kommandoer, få et simuleret query planner-svar.
Opretter du et B-Tree index på en `jsonb`-kolonne? Planneren forklarer hvorfor den
stadig laver en seq scan og hvad du burde have brugt i stedet.

Scores mapper til den danske 7-trinsskala:

| Score | Karakter | Betegnelse |
|-------|----------|------------|
| 90%+ | **12** | Fremragende |
| 78%+ | **10** | Fortrinlig |
| 60%+ | **7** | God |
| 50%+ | **4** | Jævn |
| 40%+ | **02** | Tilstrækkelig |
| <40% | **00/−3** | Tilbage til runbooks |

---

## Filstruktur

```
production-inferno/
├── app.py                  # Streamlit UI – quiz + mundtligt eksamensboard
├── engine.py               # Delt graderingsmotor, alle spørgsmål og board-data
├── streamlit_simulator.py  # Streamlit UI – incident simulator (4 moduler)
├── ops_simulator.py        # Terminal CLI – fuld simulator, ingen afhængigheder
├── README.md               # Engelsk
└── README.da.md            # Dansk
```

`engine.py` er single source of truth for al graderingslogik og spørgsmålsdata.
Begge Streamlit-apps importerer fra den. Opdatér spørgsmål ét sted – begge UI'er afspejler det.

---

## Arkitektur

```
┌─────────────────────────────────────────────────┐
│                  Orchestrator                   │
└──────────────────────┬──────────────────────────┘
                       │ JSON-serialisering (NetworkBus)
          ┌────────────┼────────────┬─────────────┐
          ▼            ▼            ▼             ▼
    svc-itdrift   svc-frontend  svc-backend  svc-database
    (IT-Drift)    (Next.js)     (Spring Boot) (PostgreSQL)
```

Moduler deler aldrig Python-objekter. Bussen serialiserer hvert request og response
til JSON og simulerer HTTP-latency – samme kontrakt-baserede isolation som rigtige
microservices har over HTTP/gRPC.

---

## Tilføj egne spørgsmål

Quiz- og board-spørgsmål ligger i `engine.py` som simple Python-dicts.

```python
# Quiz-spørgsmål
{
    "topic": "ITIL",
    "question": "Hvad er det primære mål med Incident Management?",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "answer": "B",
    "explanation": "Forklaring der vises efter svar..."
}

# Board-spørgsmål (fri tekst, keyword-baseret gradering)
{
    "topic": "ISO 27001",
    "question": "Forklar forholdet mellem ISO 27001 og et ISMS...",
    "groups": [
        ("koncept-label", [r"regex1", r"regex2"]),
    ],
    "points": 8,
    "threshold": 3,
    "post_mortem_title": "ISO 27001",
    "post_mortem": "Dybdegående forklaring..."
}
```

Pull requests med nye spørgsmål er velkomne.

---

## Forfatter

**Najib Nawabi** – Datamatiker, EK (Erhvervsakademi København)

[linkedin.com/in/najib-nawabi](https://www.linkedin.com/in/najib-nawabi)
