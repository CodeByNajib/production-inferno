# 🔥 Production Inferno

> **IT-Operations exam trainer and incident simulator – terminal CLI + Streamlit browser UI.**
> Built on the EK/KEA IT-Drift curriculum. Python 3, one optional dependency (Streamlit).

🇩🇰 [Dansk version](README.da.md)

---

## Two ways to run it

| Interface | File | Command | Best for |
|-----------|------|---------|----------|
| **Browser UI** | `app.py` | `streamlit run app.py` | Quiz + oral exam board (full curriculum) |
| **Browser UI** | `streamlit_simulator.py` | `streamlit run streamlit_simulator.py` | Incident scenarios with live scoreboard |
| **Terminal CLI** | `ops_simulator.py` | `python3 ops_simulator.py` | No dependencies, runs anywhere |

```bash
# Clone
git clone https://github.com/CodeByNajib/production-inferno.git
cd production-inferno

# Option A – browser (recommended)
pip install streamlit
streamlit run app.py

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

Built directly on the EK/KEA IT-Drift curriculum. Covers the full syllabus:

- **ITIL 4** – Service Value Chain, Guiding Principles, Incident/Problem/Change/Release Management, CMDB, Servicedesk, escalation flow
- **ISO 27001** – ISMS, SoA, Annex A (93 controls), PDCA/HLS, Stage 1/2 audit, non-conformity
- **Risk analysis** – CIA triad, iAAA, risk formulas (CEO vs. analyst), 4 treatment forms, risk matrix
- **GDPR** – 72-hour rule, DSAR, privacy by design, data processing agreements
- **SLA/OLA/UC** – SLA design, OLA/UC hierarchy, KPIs, breach escalation
- **CMMI** – 5 maturity levels, staged vs. continuous, business case
- **Backup & DR** – Backup agent architecture, SAN vs. NAS, 3-2-1, RPO/RTO/MAO, BIA
- **Virtualisation** – Type 1/2 hypervisors, VM vs. bare metal, noisy neighbor, ROI
- **Cloud** – IaaS/PaaS/SaaS, public/private/hybrid, Shared Responsibility Model
- **Change Management & DevOps** – 7 R's, CAB/ECAB, CI/CD/Deployment, IaC, MTTR, silos
- **PRINCE2** – 7 principles, 7 themes, 7 processes, management products
- **Network & AD** – VLAN segmentation, OSI layers, DMZ, IDS/IPS, AD/GPO/MDM/MAM, BYOD

**Quiz:** 35 multiple choice questions, filterable by topic.

**Exam board:** 20 free-text questions. A keyword-group grader scores your answer
against the concepts a censor listens for and tells you exactly what you missed.
Every question ends with a Senior Engineer Post-Mortem.

---

## How grading works

Answers are free text – no multiple choice for the board. The grading engine
scores your answer against concept groups and reports exactly which ones you
hit and which ones you missed.

The PostgreSQL REPL is live: type real commands, get a simulated query planner
response. Create a B-Tree index on a `jsonb` column? The planner explains why
it still does a seq scan and what you should have used instead.

Scores map to the Danish 7-step grading scale:

| Score | Grade | Verdict |
|-------|-------|---------|
| 90%+ | **12** | Excellent |
| 78%+ | **10** | Very good |
| 60%+ | **7** | Good |
| 50%+ | **4** | Satisfactory |
| 40%+ | **02** | Sufficient |
| <40% | **00/−3** | Back to the runbooks |

---

## File structure

```
production-inferno/
├── app.py                  # Streamlit UI – quiz + oral exam board
├── engine.py               # Shared grading engine, all questions and board data
├── streamlit_simulator.py  # Streamlit UI – incident simulator (4 modules)
├── ops_simulator.py        # Terminal CLI – full simulator, no dependencies
├── README.md               # English
└── README.da.md            # Danish
```

`engine.py` is the single source of truth for all grading logic and question data.
Both Streamlit apps import from it.

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

## Adding questions

Quiz and board questions live in `engine.py` as plain Python dicts.

```python
# Quiz question
{
    "topic": "ITIL",
    "question": "What is the primary goal of Incident Management?",
    "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
    "answer": "B",
    "explanation": "Explanation shown after answering..."
}

# Board question (free text, keyword grading)
{
    "topic": "ISO 27001",
    "question": "Explain the relationship between ISO 27001 and an ISMS...",
    "groups": [
        ("concept label", [r"regex1", r"regex2"]),
    ],
    "points": 8,
    "threshold": 3,
    "post_mortem_title": "ISO 27001",
    "post_mortem": "In-depth explanation..."
}
```

Pull requests with new questions are welcome.

---

## Author

**Najib Nawabi** – Computer Science, EK (Business Academy Copenhagen)

[linkedin.com/in/najib-nawabi](https://www.linkedin.com/in/najib-nawabi)
