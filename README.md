# 🔥 Production Inferno

> **IT-Operations exam trainer and incident simulator – terminal CLI + Streamlit browser UI.**
> Built on EK/KEA IT-Drift pensum. Python 3, one optional dependency (Streamlit).

---

## Two ways to run it

| Interface | File | Command | Best for |
|-----------|------|---------|----------|
| **Browser UI** | `streamlit_simulator.py` | `streamlit run streamlit_simulator.py` | Incident scenarios with live scoreboard |
| **Browser UI** | `app.py` | `streamlit run app.py` | Quiz (35 spørgsmål) + oral exam board (20 spørgsmål) |
| **Terminal CLI** | `ops_simulator.py` | `python3 ops_simulator.py` | No dependencies, runs anywhere |

```bash
# Clone
git clone https://github.com/CodeByNajib/production-inferno.git
cd production-inferno

# Option A – browser (recommended)
pip install streamlit
streamlit run app.py            # exam board + quiz
streamlit run streamlit_simulator.py  # incident simulator

# Option B – terminal, no install needed
python3 ops_simulator.py
```

Python 3.8+ required.

---

## What's inside

### Incident Simulator (`streamlit_simulator.py` + `ops_simulator.py`)

Four isolated service modules communicate over a simulated network bus.
Every request is serialised to JSON before crossing the module boundary –
the same contract-first isolation real microservices have over HTTP.

| Module | Focus | Scenarios |
|--------|-------|-----------|
| **IT-Drift** | Infrastructure, HA, incident response | SSL expiry, DDoS, split-brain, RTO/RPO design |
| **Next.js Frontend** | SSR performance and architecture | Memory leaks, Core Web Vitals, ISR, hydration failures |
| **Spring Boot Backend** | Enterprise Java, concurrency, safety | HikariCP pool starvation, race conditions, circuit breakers, thread dump analysis |
| **PostgreSQL** | Database administration | Live psql REPL – B-Tree vs GIN indexes, deadlock resolution, read replicas, window functions |

### Exam Board + Quiz (`app.py` + `engine.py`)

Built directly on the EK/KEA IT-Drift studieordning. Covers the full pensum:

- **ITIL 4** – Service Value Chain, Guiding Principles, Incident/Problem/Change/Release Management, CMDB, Servicedesk, escalation flow
- **ISO 27001** – ISMS, SoA, Annex A (93 controls), PDCA/HLS, Stage 1/2 audit, non-conformity
- **Risikoanalyse** – CIA-triaden, iAAA, risikoformler (CEO vs. analytiker), 4 behandlingsformer, risk matrix
- **GDPR** – 72-timers regel, DSAR, privacy by design, databehandleraftale
- **SLA/OLA/UC** – SLA-design, OLA/UC-hierarki, KPI'er, eskalation ved brud
- **CMMI** – 5 modenhedsniveauer, staged vs. continuous, business case (+35% produktivitet)
- **Backup & DR** – Backup-agent, SAN vs. NAS, 3-2-1, RPO/RTO/MAO, BIA
- **Virtualisering** – Type 1/2 hypervisor, VM vs. fysisk server, noisy neighbor, ROI
- **Cloud** – IaaS/PaaS/SaaS, public/private/hybrid, Shared Responsibility Model
- **Change Management & DevOps** – 7 R'er, CAB/ECAB, CI/CD/Deployment, IaC, MTTR, siloer
- **PRINCE2** – 7 principper, 7 temaer, 7 processer, management products
- **Netværk & AD** – VLAN-segmentering, OSI-lag, DMZ, IDS/IPS, AD/GPO/MDM/MAM, BYOD

**Quiz:** 35 multiple choice spørgsmål, filtrérbare per emne.  
**Exam board:** 20 fri-tekst spørgsmål. Svar som til den rigtige mundtlige eksamen – en keyword-group grader scorer hvilke koncepter du rammer og fortæller præcis hvad censoren ville have hørt. Hvert spørgsmål afsluttes med en Senior Engineer Post-Mortem.

---

## How grading works

Answers are **free text** – no multiple choice for the board. A keyword-group engine
scores your answer against the concepts a censor listens for, then reports exactly
which ones you hit and which ones you missed.

The PostgreSQL REPL is live: type real commands, get a simulated query planner
response. Create a B-Tree on a `jsonb` column? The planner explains why it still
does a seq scan and what you should have used instead.

Scores map to the Danish 7-step scale:

| Score | Grade | Verdict |
|-------|-------|---------|
| 90%+ | **12** | Fremragende |
| 78%+ | **10** | Fortrinlig |
| 60%+ | **7** | God |
| 50%+ | **4** | Jævn |
| 40%+ | **02** | Tilstrækkelig |
| <40% | **00/−3** | Back to the runbooks |

---

## File structure

```
production-inferno/
├── app.py                  # Streamlit UI – quiz + oral exam board (EK/KEA pensum)
├── engine.py               # Shared grading engine, quiz questions, board questions
├── streamlit_simulator.py  # Streamlit UI – incident simulator (4 modules)
├── ops_simulator.py        # Terminal CLI – full simulator, no dependencies
└── README.md
```

`engine.py` is the single source of truth for all grading logic and question data.
Both Streamlit apps import from it. Update questions here, both UIs reflect it.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Orchestrator                   │
└──────────────────────┬──────────────────────────┘
                       │ JSON serialisation (NetworkBus)
          ┌────────────┼────────────┬─────────────┐
          ▼            ▼            ▼             ▼
    svc-itdrift   svc-frontend  svc-backend  svc-database
    (IT-Drift)    (Next.js)     (Spring Boot) (PostgreSQL)
```

Modules never share Python objects. The bus serialises every request and response
to JSON and simulates HTTP latency – enforcing the same contract-first isolation
real microservices have over HTTP/gRPC.

---

## Adding your own questions

Quiz and board questions are plain Python dicts in `engine.py`. Each quiz question follows this structure:

```python
{
    "topic": "ITIL",
    "question": "Hvad er formålet med Problem Management?",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "answer": "B",
    "explanation": "Forklaring der vises efter svar..."
}
```

Board questions use keyword-group grading:

```python
{
    "topic": "ISO 27001",
    "question": "Forklar ISMS og SoA...",
    "groups": [
        ("concept label", [r"regex1", r"regex2"]),
    ],
    "points": 8,
    "threshold": 3,
    "post_mortem_title": "ISO 27001",
    "post_mortem": "Dybdegående forklaring..."
}
```

Pull requests with new questions are welcome.

---

## Author

**Najib Nawabi** – Computer Science, EK (Business Academy Copenhagen)

[linkedin.com/in/najib-nawabi](https://www.linkedin.com/in/najib-nawabi)
