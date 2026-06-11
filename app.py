"""
app.py – Production Inferno · Streamlit UI
==========================================
Run:  streamlit run app.py
Deps: pip install streamlit
"""

import json
import os
import random
import re

import streamlit as st

from engine import (
    BOARD_QUESTIONS,
    DANISH_SCALE,
    QUIZ_QUESTIONS,
    danish_grade,
    grade_answer,
)

# ---------------------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Production Inferno",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CUSTOM CSS  – dark terminal feel, amber accent, no default Streamlit padding
# ---------------------------------------------------------------------------

st.markdown("""
<style>
/* Base */
[data-testid="stAppViewContainer"] {
    background-color: #0d1117;
    color: #e6edf3;
}
[data-testid="stSidebar"] {
    background-color: #161b22;
    border-right: 1px solid #30363d;
}

/* Typography */
h1, h2, h3 { color: #f0883e; font-family: monospace; letter-spacing: -0.5px; }
h4, h5, h6 { color: #79c0ff; font-family: monospace; }
p, li { color: #c9d1d9; line-height: 1.7; }

/* Cards */
.card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}
.card-green  { border-left: 4px solid #3fb950; }
.card-red    { border-left: 4px solid #f85149; }
.card-amber  { border-left: 4px solid #f0883e; }
.card-blue   { border-left: 4px solid #79c0ff; }
.card-purple { border-left: 4px solid #bc8cff; }

/* Hit / miss tags */
.hit  { color: #3fb950; font-weight: 600; }
.miss { color: #f85149; }

/* Score pill */
.pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.85rem;
    font-weight: 700;
    font-family: monospace;
}
.pill-green  { background: #1f3d2b; color: #3fb950; border: 1px solid #3fb950; }
.pill-red    { background: #3d1f1f; color: #f85149; border: 1px solid #f85149; }
.pill-amber  { background: #3d2b1f; color: #f0883e; border: 1px solid #f0883e; }
.pill-blue   { background: #1f2d3d; color: #79c0ff; border: 1px solid #79c0ff; }

/* Progress bar override */
.stProgress > div > div { background-color: #f0883e; }

/* Buttons */
.stButton > button {
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    font-family: monospace;
}
.stButton > button:hover {
    background-color: #f0883e;
    color: #0d1117;
    border-color: #f0883e;
}

/* Text area */
.stTextArea textarea {
    background-color: #161b22 !important;
    color: #e6edf3 !important;
    border: 1px solid #30363d !important;
    font-family: monospace;
    font-size: 0.9rem;
}

/* Radio */
.stRadio label { color: #c9d1d9 !important; }

/* Expander */
.streamlit-expanderHeader { color: #bc8cff !important; font-family: monospace; }

/* Monospace inline */
code { color: #f0883e; background: #21262d; padding: 1px 5px; border-radius: 3px; }

/* Sidebar nav buttons */
div[data-testid="stSidebarContent"] .stButton > button {
    width: 100%;
    text-align: left;
    margin-bottom: 4px;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# SESSION STATE INIT
# ---------------------------------------------------------------------------

def _init():
    defaults = {
        "page": "home",
        # Quiz state
        "quiz_questions": [],
        "quiz_index": 0,
        "quiz_score": 0,
        "quiz_answered": False,
        "quiz_selected": None,
        "quiz_topic_filter": "Alle emner",
        "quiz_done": False,
        # Board state
        "board_index": 0,
        "board_score": 0,
        "board_max": 0,
        "board_answers": [],   # list of dicts with result info
        "board_done": False,
        # Global scoreboard
        "scores": {},  # { module_name: {"points": x, "max": y} }
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

TOPICS = sorted({q["topic"] for q in QUIZ_QUESTIONS})
GRADE_COLORS = {
    "12": "pill-green",
    "10": "pill-green",
    "7":  "pill-blue",
    "4":  "pill-amber",
    "02": "pill-amber",
    "00/−3": "pill-red",
}


def pill(text, style="pill-blue"):
    return f'<span class="pill {style}">{text}</span>'


def card(content, style=""):
    return f'<div class="card {style}">{content}</div>'


def pct_color(pct):
    if pct >= 78: return "pill-green"
    if pct >= 60: return "pill-blue"
    if pct >= 40: return "pill-amber"
    return "pill-red"


def set_page(name):
    st.session_state.page = name
    st.rerun()


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------

def sidebar():
    with st.sidebar:
        st.markdown("## 🔥 Production Inferno")
        st.markdown('<p style="color:#6e7681;font-size:0.8rem;margin-top:-0.5rem;">IT-Drift Exam Trainer</p>', unsafe_allow_html=True)
        st.divider()

        nav = [
            ("🏠 Forside",         "home"),
            ("⚡ Quiz",            "quiz"),
            ("🎓 Eksamensboard",   "board"),
            ("📊 Scoreboard",      "scores"),
        ]
        for label, page in nav:
            active = st.session_state.page == page
            btn_style = "color:#f0883e;font-weight:700;" if active else ""
            if st.button(label, key=f"nav_{page}"):
                set_page(page)

        st.divider()

        # Mini scoreboard in sidebar
        if st.session_state.scores:
            st.markdown("**Seneste scores**")
            for name, sc in st.session_state.scores.items():
                if sc["max"] > 0:
                    p = round(100 * sc["points"] / sc["max"])
                    g, _ = danish_grade(p)
                    st.markdown(
                        f'<small>{name}: {sc["points"]}/{sc["max"]} '
                        f'{pill(g, GRADE_COLORS.get(g, "pill-blue"))}</small>',
                        unsafe_allow_html=True,
                    )
        st.divider()
        st.markdown('<p style="color:#6e7681;font-size:0.75rem;">EK/KEA IT-Drift pensum<br/>Made by Najib Nawabi</p>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# HOME PAGE
# ---------------------------------------------------------------------------

def page_home():
    st.markdown("# 🔥 Production Inferno")
    st.markdown("#### Terminal-based IT-Operations exam trainer – nu i browser")
    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
<div class="card card-amber">
<h4>⚡ Quiz</h4>
<p>30+ multiple choice spørgsmål på tværs af hele pensum. Hurtig scanning af definitioner og fakta.</p>
</div>
""", unsafe_allow_html=True)
        if st.button("Start Quiz →", key="home_quiz"):
            set_page("quiz")

    with col2:
        st.markdown("""
<div class="card card-blue">
<h4>🎓 Eksamensboard</h4>
<p>20 fri-tekst spørgsmål bygget på EK/KEA-pensum. Svar som til den rigtige mundtlige eksamen.</p>
</div>
""", unsafe_allow_html=True)
        if st.button("Start Board →", key="home_board"):
            set_page("board")

    with col3:
        st.markdown("""
<div class="card card-purple">
<h4>📊 Scoreboard</h4>
<p>Se dine samlede scores på tværs af quiz og board, med dansk karakter.</p>
</div>
""", unsafe_allow_html=True)
        if st.button("Se Scores →", key="home_scores"):
            set_page("scores")

    st.divider()
    st.markdown("#### 📚 Pensum dækket")

    topics_grid = [
        ("ITIL 4", "Service Value Chain, Guiding Principles, Incident/Problem/Change/Release Management, CMDB, Servicedesk"),
        ("ISO 27001", "ISMS, SoA, Annex A, PDCA/HLS, Stage 1/2 audit, non-conformity"),
        ("Risikoanalyse", "CIA-triaden, iAAA, risikoformler (CEO vs analytiker), 4 behandlingsformer, risk matrix"),
        ("GDPR", "72-timers regel, DSAR, privacy by design, databehandleraftale"),
        ("SLA/OLA/UC", "SLA-design, OLA/UC-hierarki, KPI'er og eskalation"),
        ("CMMI", "5 modenhedsniveauer, staged vs continuous, business case"),
        ("Backup & DR", "Backup-agent, SAN vs NAS, 3-2-1, RPO/RTO/MAO, BIA"),
        ("Virtualisering", "Type 1/2 hypervisor, VM vs fysisk, noisy neighbor, ROI"),
        ("Cloud", "IaaS/PaaS/SaaS, public/private/hybrid, Shared Responsibility"),
        ("Change & DevOps", "7 R'er, CAB/ECAB, CI/CD/Deployment, IaC, MTTR, siloer"),
        ("PRINCE2", "7 principper, 7 temaer, 7 processer, management products"),
        ("Netværk & AD", "VLAN, OSI-lag, DMZ, IDS/IPS, AD/GPO/MDM/MAM, BYOD"),
    ]

    cols = st.columns(2)
    for i, (topic, desc) in enumerate(topics_grid):
        with cols[i % 2]:
            st.markdown(f"""
<div class="card card-blue" style="padding:0.8rem 1rem;margin-bottom:0.6rem;">
<strong style="color:#79c0ff;">{topic}</strong>
<p style="font-size:0.82rem;margin:0.3rem 0 0 0;">{desc}</p>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# QUIZ PAGE
# ---------------------------------------------------------------------------

def _start_quiz(filtered_qs):
    qs = filtered_qs.copy()
    random.shuffle(qs)
    st.session_state.quiz_questions = qs
    st.session_state.quiz_index = 0
    st.session_state.quiz_score = 0
    st.session_state.quiz_answered = False
    st.session_state.quiz_selected = None
    st.session_state.quiz_done = False


def page_quiz():
    st.markdown("# ⚡ Quiz")
    st.markdown("*Multiple choice – hurtig scanning af pensum*")
    st.divider()

    # --- Setup / filter ---
    if not st.session_state.quiz_questions and not st.session_state.quiz_done:
        st.markdown("#### Vælg emner")
        topic_opts = ["Alle emner"] + TOPICS
        chosen = st.selectbox("Filtrér på emne:", topic_opts, key="quiz_topic_sel")

        filtered = QUIZ_QUESTIONS if chosen == "Alle emner" else [
            q for q in QUIZ_QUESTIONS if q["topic"] == chosen
        ]
        st.markdown(f"**{len(filtered)} spørgsmål klar**")

        if st.button("🚀 Start quiz"):
            st.session_state.quiz_topic_filter = chosen
            _start_quiz(filtered)
            st.rerun()
        return

    # --- Done screen ---
    if st.session_state.quiz_done:
        total = len(st.session_state.quiz_questions)
        score = st.session_state.quiz_score
        pct = round(100 * score / total) if total else 0
        grade, label = danish_grade(pct)

        st.markdown(f"""
<div class="card card-{'green' if pct >= 60 else 'red'}">
<h3>Quiz færdig!</h3>
<p>Rigtige svar: <strong>{score}/{total}</strong> ({pct}%)</p>
<p>Karakter: {pill(grade, GRADE_COLORS.get(grade, 'pill-blue'))} – {label}</p>
</div>
""", unsafe_allow_html=True)

        # Save to scoreboard
        st.session_state.scores["Quiz"] = {"points": score, "max": total}

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Prøv igen (samme emner)"):
                filtered = QUIZ_QUESTIONS if st.session_state.quiz_topic_filter == "Alle emner" else [
                    q for q in QUIZ_QUESTIONS if q["topic"] == st.session_state.quiz_topic_filter
                ]
                _start_quiz(filtered)
                st.rerun()
        with col2:
            if st.button("🏠 Tilbage til menu"):
                st.session_state.quiz_questions = []
                st.session_state.quiz_done = False
                set_page("home")
        return

    # --- Active quiz ---
    qs = st.session_state.quiz_questions
    idx = st.session_state.quiz_index
    total = len(qs)

    if idx >= total:
        st.session_state.quiz_done = True
        st.rerun()
        return

    q = qs[idx]
    progress = idx / total
    st.progress(progress)
    st.markdown(f'<small style="color:#6e7681;">{idx + 1} / {total} &nbsp;·&nbsp; {q["topic"]}</small>', unsafe_allow_html=True)
    st.markdown(f"### {q['question']}")

    answered = st.session_state.quiz_answered
    selected = st.session_state.quiz_selected

    if not answered:
        choice = st.radio("Vælg svar:", q["options"], key=f"quiz_radio_{idx}", index=None)
        if st.button("✅ Svar", disabled=(choice is None)):
            st.session_state.quiz_selected = choice
            st.session_state.quiz_answered = True
            if choice and choice.startswith(q["answer"]):
                st.session_state.quiz_score += 1
            st.rerun()
    else:
        correct = q["answer"]
        for opt in q["options"]:
            letter = opt[0]
            if letter == correct:
                st.markdown(f'<p class="hit">✅ {opt}</p>', unsafe_allow_html=True)
            elif selected and selected.startswith(letter) and letter != correct:
                st.markdown(f'<p class="miss">❌ {opt}</p>', unsafe_allow_html=True)
            else:
                st.markdown(f'<p style="color:#6e7681;">{opt}</p>', unsafe_allow_html=True)

        is_correct = selected and selected.startswith(correct)
        result_style = "card-green" if is_correct else "card-red"
        result_icon = "✅ Korrekt!" if is_correct else f"❌ Forkert – korrekt svar: {correct}"
        st.markdown(f"""
<div class="card {result_style}" style="margin-top:0.8rem;">
<strong>{result_icon}</strong><br/>
<span style="font-size:0.9rem;">{q['explanation']}</span>
</div>
""", unsafe_allow_html=True)

        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("Næste →"):
                st.session_state.quiz_index += 1
                st.session_state.quiz_answered = False
                st.session_state.quiz_selected = None
                st.rerun()

        # Running score
        cur_score = st.session_state.quiz_score
        cur_pct = round(100 * cur_score / (idx + 1))
        st.markdown(
            f'<small style="color:#6e7681;">Aktuel score: {cur_score}/{idx + 1} ({cur_pct}%)</small>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# BOARD PAGE  (free text oral exam)
# ---------------------------------------------------------------------------

def _start_board():
    st.session_state.board_index = 0
    st.session_state.board_score = 0
    st.session_state.board_max = sum(q["points"] for q in BOARD_QUESTIONS)
    st.session_state.board_answers = []
    st.session_state.board_done = False


def page_board():
    st.markdown("# 🎓 Eksamensboard")
    st.markdown("*Fri tekst – svar som til den rigtige mundtlige eksamen*")
    st.divider()

    # --- Not started ---
    if not st.session_state.board_answers and not st.session_state.board_done and st.session_state.board_index == 0:
        st.markdown("""
<div class="card card-amber">
<h4>Sådan fungerer boardet</h4>
<ul>
<li>20 spørgsmål baseret på dit faktiske EK/KEA IT-Drift pensum</li>
<li>Skriv dit svar i tekstfeltet – som om du sidder foran to censorer</li>
<li>Graderingsmotoren scorer hvilke koncepter du rammer</li>
<li>Hvert spørgsmål afsluttes med en Senior Engineer Post-Mortem</li>
</ul>
</div>
""", unsafe_allow_html=True)
        if st.button("🎓 Start eksamensboard"):
            _start_board()
            st.rerun()
        return

    # --- Done screen ---
    if st.session_state.board_done:
        pts = st.session_state.board_score
        mx = st.session_state.board_max
        pct = round(100 * pts / mx) if mx else 0
        grade, label = danish_grade(pct)

        st.markdown(f"""
<div class="card card-{'green' if pct >= 60 else 'red'}">
<h3>Board færdig!</h3>
<p>Score: <strong>{pts}/{mx}</strong> ({pct}%)</p>
<p>Simlueret karakter: {pill(grade, GRADE_COLORS.get(grade, 'pill-blue'))} – {label}</p>
</div>
""", unsafe_allow_html=True)

        # Save to scoreboard
        st.session_state.scores["Board"] = {"points": pts, "max": mx}

        # Per-question breakdown
        st.markdown("#### Spørgsmål for spørgsmål")
        for a in st.session_state.board_answers:
            q_pct = round(100 * a["awarded"] / a["points"]) if a["points"] else 0
            color = "green" if q_pct >= 60 else "red"
            with st.expander(f"{'✅' if q_pct >= 60 else '❌'} {a['topic']} – {a['awarded']}/{a['points']} pts"):
                st.markdown(f"**Spørgsmål:** {a['question'][:120]}...")
                if a["hits"]:
                    st.markdown("**Rammer:**")
                    for h in a["hits"]:
                        st.markdown(f'<span class="hit">+ {h}</span>', unsafe_allow_html=True)
                if a["missed"]:
                    st.markdown("**Manglede:**")
                    for m in a["missed"]:
                        st.markdown(f'<span class="miss">– {m}</span>', unsafe_allow_html=True)
                st.markdown("**Post-mortem:**")
                st.info(a["post_mortem"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Tag boardet igen"):
                _start_board()
                st.rerun()
        with col2:
            if st.button("🏠 Tilbage til menu"):
                set_page("home")
        return

    # --- Active board ---
    idx = st.session_state.board_index
    if idx >= len(BOARD_QUESTIONS):
        st.session_state.board_done = True
        st.rerun()
        return

    q = BOARD_QUESTIONS[idx]
    total = len(BOARD_QUESTIONS)
    progress = idx / total

    st.progress(progress)
    st.markdown(
        f'<small style="color:#6e7681;">Spørgsmål {idx + 1} / {total} &nbsp;·&nbsp; '
        f'{q["topic"]} &nbsp;·&nbsp; {q["points"]} point</small>',
        unsafe_allow_html=True,
    )

    st.markdown(f"""
<div class="card card-blue">
<p style="font-size:1rem;font-style:italic;">"{q['question']}"</p>
</div>
""", unsafe_allow_html=True)

    answer_key = f"board_answer_{idx}"
    answer = st.text_area(
        "Dit svar:",
        key=answer_key,
        height=160,
        placeholder="Skriv dit svar her – brug hele sætninger som til den rigtige eksamen...",
    )

    submit_key = f"board_submit_{idx}"
    if st.button("📝 Indsend svar", key=submit_key, disabled=(not answer or not answer.strip())):
        hits, missed, passed = grade_answer(answer, q["groups"], q.get("threshold"))
        awarded = round(q["points"] * len(hits) / len(q["groups"])) if q["groups"] else 0
        st.session_state.board_score += awarded
        st.session_state.board_answers.append({
            "topic": q["topic"],
            "question": q["question"],
            "hits": hits,
            "missed": missed,
            "awarded": awarded,
            "points": q["points"],
            "post_mortem": q["post_mortem"],
            "post_mortem_title": q["post_mortem_title"],
        })
        # Store result to display below
        st.session_state[f"board_result_{idx}"] = {
            "hits": hits, "missed": missed,
            "awarded": awarded, "passed": passed,
        }
        st.rerun()

    # Show result after submit
    result = st.session_state.get(f"board_result_{idx}")
    if result:
        color = "green" if result["passed"] else "red"
        pct_q = round(100 * result["awarded"] / q["points"]) if q["points"] else 0

        st.markdown(f"""
<div class="card card-{color}" style="margin-top:0.5rem;">
<strong>Score: {result['awarded']}/{q['points']} point ({pct_q}%)</strong>
</div>
""", unsafe_allow_html=True)

        col_hits, col_miss = st.columns(2)
        with col_hits:
            if result["hits"]:
                st.markdown("**✅ Koncepter du ramte:**")
                for h in result["hits"]:
                    st.markdown(f'<span class="hit">+ {h}</span>', unsafe_allow_html=True)
        with col_miss:
            if result["missed"]:
                st.markdown("**❌ Censoren ville høre:**")
                for m in result["missed"]:
                    st.markdown(f'<span class="miss">– {m}</span>', unsafe_allow_html=True)

        with st.expander(f"📋 Post-Mortem: {q['post_mortem_title']}"):
            st.markdown(q["post_mortem"])

        running_pct = round(100 * st.session_state.board_score / q["points"] / (idx + 1) * len(q["groups"])) if q["points"] else 0

        if st.button("Næste spørgsmål →", key=f"board_next_{idx}"):
            st.session_state.board_index += 1
            st.rerun()


# ---------------------------------------------------------------------------
# SCORES PAGE
# ---------------------------------------------------------------------------

def page_scores():
    st.markdown("# 📊 Scoreboard")
    st.divider()

    scores = st.session_state.scores
    if not scores:
        st.markdown("""
<div class="card card-amber">
<p>Ingen scores endnu. Gennemfør Quiz eller Eksamensboard for at se dine resultater her.</p>
</div>
""", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⚡ Start Quiz"):
                set_page("quiz")
        with col2:
            if st.button("🎓 Start Board"):
                set_page("board")
        return

    total_pts = sum(s["points"] for s in scores.values())
    total_max = sum(s["max"] for s in scores.values())
    total_pct = round(100 * total_pts / total_max) if total_max else 0
    grade, label = danish_grade(total_pct)

    st.markdown(f"""
<div class="card card-{'green' if total_pct >= 60 else 'red'}">
<h3>Samlet resultat</h3>
<p><strong>{total_pts}/{total_max} point</strong> ({total_pct}%)</p>
<p>Simuleret karakter: {pill(grade, GRADE_COLORS.get(grade, 'pill-blue'))} &nbsp; {label}</p>
</div>
""", unsafe_allow_html=True)

    st.markdown("#### Breakdown")
    for name, sc in scores.items():
        if sc["max"] == 0:
            continue
        p = round(100 * sc["points"] / sc["max"])
        g, lbl = danish_grade(p)
        bar_val = p / 100

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown(f"**{name}**")
            st.progress(bar_val)
        with col2:
            st.markdown(f'<p style="margin-top:0.3rem;">{sc["points"]}/{sc["max"]} ({p}%)</p>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'{pill(g, GRADE_COLORS.get(g, "pill-blue"))} {lbl}', unsafe_allow_html=True)

    st.divider()
    st.markdown("#### Karakterskala")
    scale_data = []
    for cutoff, g, lbl in DANISH_SCALE:
        scale_data.append({"Fra": f"{cutoff}%", "Karakter": g, "Beskrivelse": lbl})

    for row in scale_data:
        g = row["Karakter"]
        st.markdown(
            f'{pill(g, GRADE_COLORS.get(g, "pill-blue"))} &nbsp; '
            f'<span style="color:#c9d1d9;">{row["Fra"]}+ &nbsp;·&nbsp; {row["Beskrivelse"]}</span>',
            unsafe_allow_html=True,
        )

    st.divider()
    if st.button("🗑️ Nulstil scores"):
        st.session_state.scores = {}
        st.rerun()


# ---------------------------------------------------------------------------
# ROUTER
# ---------------------------------------------------------------------------

sidebar()

page = st.session_state.page
if page == "home":
    page_home()
elif page == "quiz":
    page_quiz()
elif page == "board":
    page_board()
elif page == "scores":
    page_scores()
