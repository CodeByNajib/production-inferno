#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Production Inferno – Streamlit UI. Grading logic preserved from ops_simulator.py."""

import math
import re
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# GRADING ENGINE  (unchanged from ops_simulator.py)
# ─────────────────────────────────────────────────────────────────────────────

def grade_answer(answer, groups, threshold=None):
    hits, missed = [], []
    for label, patterns in groups:
        if any(re.search(p, answer, re.IGNORECASE | re.DOTALL) for p in patterns):
            hits.append(label)
        else:
            missed.append(label)
    if threshold is None:
        threshold = max(1, math.ceil(len(groups) * 0.6))
    return hits, missed, len(hits) >= threshold


# ─────────────────────────────────────────────────────────────────────────────
# STEP DEFINITIONS
# Each step dict keys:
#   kind          – "question" | "exact" | "numeric" | "repl"
#   scenario      – optional section header (shown only on first Q of scenario)
#   alert         – optional red alert text
#   code          – optional code block string
#   code_lang     – label for code block
#   info          – optional info/hint shown before the prompt
#   prompt        – question text
#   groups        – [(label, [regex, …]), …]
#   points        – int
#   threshold     – int | None  (None → 60% rule)
#   validator     – callable(float) → bool   (numeric only)
#   unit          – str   (numeric only)
#   postmortem_title / postmortem_body  – shown in expander after answering
# ─────────────────────────────────────────────────────────────────────────────

def _steps_itdrift():
    s = []

    # ── Scenario 1: SSL ──────────────────────────────────────────────────────
    s.append(dict(kind="exact",
        scenario="INCIDENT 1: 03:12 AM – 'The padlock is gone'",
        alert="PagerDuty P1: checkout conversion dropped 94% in 6 minutes.",
        code=("03:12:04 monitor  TLS handshake error: certificate has expired\n"
              "03:12:31 support  Customers report: NET::ERR_CERT_DATE_INVALID\n"
              "03:13:10 oncall   YOU are paged. Load balancer terminates TLS (nginx)."),
        code_lang="incident feed",
        prompt="STEP 1 – Confirm the diagnosis. Which exact command inspects the certificate's validity dates?",
        groups=[
            ("uses openssl or certbot tooling", [r"\bopenssl\b", r"\bcertbot\b"]),
            ("inspects the cert (x509 / s_client / certificates)", [r"x509", r"s_client", r"certbot\s+certificates"]),
            ("reads the dates or connects to :443", [r"-enddate", r"-dates", r"-noout", r":443", r"-connect"]),
        ], points=6, threshold=2))

    s.append(dict(kind="exact",
        prompt="STEP 2 – The cert (Let's Encrypt) expired because auto-renewal silently failed. Which command renews it right now?",
        groups=[
            ("certbot / acme client", [r"certbot", r"acme", r"lego", r"dehydrated"]),
            ("renew action", [r"\brenew\b", r"--force-renewal", r"certonly"]),
        ], points=4, threshold=2))

    s.append(dict(kind="exact",
        prompt="STEP 3 – New cert is on disk. Apply it on nginx WITHOUT dropping live connections. Exact command?",
        groups=[
            ("targets nginx / systemd", [r"nginx", r"systemctl"]),
            ("graceful RELOAD, not restart", [r"\breload\b", r"-s\s+reload", r"\bHUP\b"]),
        ], points=5, threshold=2))

    s.append(dict(kind="question",
        prompt="STEP 4 – 'How do we make this class of incident structurally impossible?' Name at least two preventive controls.",
        groups=[
            ("monitoring/alerting on cert expiry", [r"monitor", r"alert", r"blackbox", r"prometheus", r"expiry.{0,30}(warn|alert|check)", r"30\s*d"]),
            ("automated renewal pipeline (cert-manager / certbot timer)", [r"cert-?manager", r"auto.{0,12}renew", r"systemd\s+timer", r"cron", r"acme"]),
            ("test the renewal path (dry-run, staging)", [r"dry.?run", r"staging", r"test.{0,20}renew", r"runbook", r"game.?day"]),
        ], points=6, threshold=2,
        postmortem_title="SSL/TLS Expiry",
        postmortem_body=(
            "Certificate expiry is the most preventable P1 in the industry. The mechanics: TLS clients hard-fail on an expired leaf certificate — validity windows are the only revocation mechanism that works offline. No graceful degradation; every browser shows an interstitial.\n\n"
            "Three layers of defence: (1) AUTOMATED renewal (certbot systemd timer or cert-manager) so a human is never in the loop; (2) MONITORING of the renewal — a Prometheus blackbox_exporter probe at 21 days remaining catches a broken pipeline while you still have three renewal windows left; (3) graceful 'nginx -s reload' instead of restart.\n\n"
            "Exam angle: ITIL 4 'monitoring and event management' + 'incident management' (restore fast) → 'problem management' (kill the root cause)."
        )))

    # ── Scenario 2: DDoS ─────────────────────────────────────────────────────
    s.append(dict(kind="question",
        scenario="INCIDENT 2: Black Friday – DDoS through the CDN",
        alert="Traffic is 41x baseline. Origin CPU 100%. p99 latency 29s.",
        code=("Edge (CDN) requests/sec:   1.2M   (baseline 29k)\n"
              "Cache hit ratio:           4%     (baseline 91%)\n"
              "Top path:                  GET /api/search?q=<random-string>   97.8%\n"
              "Unique source IPs:         ~310.000 (residential, global)\n"
              "Origin DB connections:     saturated"),
        code_lang="traffic dashboard",
        prompt="Q1 – Classify this attack precisely. Which OSI layer is being attacked, what TYPE of DDoS is this, and why is the CDN not saving you?",
        groups=[
            ("Layer 7 / application layer attack", [r"layer\s*7", r"\bl7\b", r"application\s*lay"]),
            ("HTTP flood / cache-busting via unique query strings", [r"http\s*flood", r"cache.?bust", r"random.{0,20}(query|param|string)", r"unique.{0,20}(url|quer)"]),
            ("CDN bypassed because every request is a cache MISS hitting origin", [r"cache\s*miss", r"hit\s*ratio", r"origin", r"uncach"]),
        ], points=8, threshold=2))

    s.append(dict(kind="question",
        prompt="Q2 – You have 10 minutes before the database dies. List your IMMEDIATE mitigations at the edge (at least three concrete controls).",
        groups=[
            ("rate limiting per IP/token at the edge", [r"rate.?limit", r"throttl"]),
            ("WAF rule / managed bot protection", [r"\bwaf\b", r"web\s+application\s+firewall", r"bot\s+(protect|manage)"]),
            ("challenge (CAPTCHA / JS challenge / proof-of-work)", [r"captcha", r"challenge", r"turnstile", r"js\s*challenge"]),
            ("normalize/strip query strings or serve stale/static fallback", [r"normaliz", r"strip.{0,15}quer", r"static\s+fallback", r"cache\s+key", r"stale"]),
            ("block obvious ASNs/geos or upstream scrubbing", [r"\bgeo", r"\basn\b", r"scrub", r"blackhol", r"blokk?er"]),
        ], points=10, threshold=3))

    s.append(dict(kind="question",
        prompt="Q3 – A junior says 'just autoscale the origin x20'. Explain why that is the WRONG primary response.",
        groups=[
            ("attacker scales cheaper than you / cost asymmetry", [r"cost", r"cheap", r"asymmetr", r"attacker.{0,40}scal"]),
            ("database/stateful tier is the bottleneck and does not autoscale", [r"database", r"\bdb\b", r"stateful", r"connection", r"bottleneck"]),
            ("mitigate at the edge, never absorb at origin", [r"edge", r"upstream", r"absorb", r"origin"]),
        ], points=6, threshold=2,
        postmortem_title="Cache-Busting L7 DDoS",
        postmortem_body=(
            "Volumetric attacks (L3/L4) are largely absorbed by any anycast CDN. L7 attacks are smarter: each request is a legitimate HTTP GET, cheap for the attacker, expensive for you — '/api/search?q=zk83jf' forces a cache MISS, a backend invocation, and a DB query. Your 91% cache hit ratio collapses to 4%.\n\n"
            "Defence hierarchy: (1) rate limiting per client fingerprint, (2) WAF managed rules + bot scoring, (3) interactive challenges, (4) cache-key normalization, (5) stale-while-revalidate so the origin can be firewalled off entirely. Autoscaling is a cost-transfer to you — the attacker's botnet scales for free.\n\n"
            "Exam angle: availability in the CIA triad (ISO 27001), capacity management, and SLA: 99.9% = ~43 min/month downtime budget."
        )))

    # ── Scenario 3: Split-brain ───────────────────────────────────────────────
    s.append(dict(kind="question",
        scenario="INCIDENT 3: The cluster that crowned two kings",
        alert="Two-node HA database cluster. Heartbeat link cut by switch firmware update. BOTH nodes promoted to PRIMARY.",
        code=("node-a (rack 1): role=PRIMARY  accepting writes since 14:02\n"
              "node-b (rack 2): role=PRIMARY  accepting writes since 14:02\n"
              "replication:     BROKEN - timelines diverged\n"
              "duration so far: 23 minutes of divergent writes (orders, payments!)"),
        code_lang="cluster status",
        prompt="Q1 – Name this failure condition and the root DESIGN flaw that made it possible.",
        groups=[
            ("split-brain", [r"split.?brain"]),
            ("no quorum / even number of nodes cannot form majority", [r"quorum", r"majority", r"even\s+number", r"\b2\s+nodes?\b.{0,60}(cannot|kan ikke)"]),
            ("no fencing/STONITH or witness to arbitrate", [r"fenc", r"stonith", r"witness", r"arbiter", r"tie.?break"]),
        ], points=8, threshold=2))

    s.append(dict(kind="question",
        prompt="Q2 – You are Incident Commander. Sequence your IMMEDIATE actions. Wrong order loses customer payments.",
        groups=[
            ("STOP the bleeding: fence/isolate one node or block writes at the LB first", [r"fence", r"stonith", r"stop.{0,25}writ", r"block.{0,20}writ", r"isolat", r"read.?only", r"maintenance"]),
            ("choose ONE authoritative node (by txn/WAL analysis)", [r"authoritative", r"source\s+of\s+truth", r"pick\s+one", r"compare.{0,30}(data|timeline|wal)"]),
            ("reconcile/merge or replay diverged writes before resuming", [r"reconcil", r"merge", r"replay", r"diverge"]),
            ("rebuild the loser as a fresh replica from the winner", [r"rebuild", r"re.?sync", r"basebackup", r"re.?clone", r"replica"]),
        ], points=10, threshold=3))

    s.append(dict(kind="question",
        prompt="Q3 – Redesign the cluster so split-brain is structurally impossible. Be specific.",
        groups=[
            ("odd number of voters: 3 nodes, or 2 nodes + witness/quorum device", [r"\b3\b.{0,20}(node|voter)", r"odd", r"witness", r"quorum\s+(device|disk)", r"arbiter", r"tie.?breaker"]),
            ("automatic fencing (STONITH) before promotion", [r"stonith", r"fenc"]),
            ("redundant/independent heartbeat network", [r"redundant.{0,25}(heartbeat|link|network)", r"separate.{0,25}(heartbeat|network)", r"dual.{0,10}link"]),
            ("majority-based promotion (Raft/Paxos/Patroni/etcd)", [r"raft", r"paxos", r"patroni", r"consensus", r"etcd", r"majority.{0,20}(vote|promot)"]),
        ], points=8, threshold=2,
        postmortem_title="Split-Brain & Quorum",
        postmortem_body=(
            "Split-brain happens when an HA cluster confuses 'I cannot SEE my peer' with 'my peer is DEAD'. With two nodes there is no way to tell the difference — each concludes it must take over. Merging diverged payment data is a manual, lawyer-adjacent process; prevention is the only sane strategy.\n\n"
            "The fix is quorum: a node may only act as primary while it can communicate with a strict MAJORITY of voters. With 3 voters, a partition splits 2-vs-1; the side with 2 keeps running, the side with 1 demotes itself. 2-node clusters need a witness or quorum disk. STONITH fires before promotion so a confused node is physically unable to write.\n\n"
            "Exam angle: THE high-availability question. Quorum, fencing, odd voter counts, Raft — deriving 'why 3 nodes and not 2' on a whiteboard is the difference between a 7 and a 12."
        )))

    # ── Scenario 4: Backup & DR ───────────────────────────────────────────────
    s.append(dict(kind="numeric",
        scenario="DESIGN TASK 4: Backup & Disaster Recovery strategy",
        info="NordCommerce: revenue 50.000 kr/hour. The board accepts a maximum of 200.000 kr direct loss per major incident. Order data older than 15 minutes can be reconstructed from the payment provider; anything younger is lost forever.",
        prompt="Q1 – Derive the maximum acceptable RTO in HOURS from the revenue numbers.",
        validator=lambda v: 0 < v <= 4, points=5, unit="hours"))

    s.append(dict(kind="numeric",
        info="✓ RTO: 200.000 kr / 50.000 kr per hour = **4 hours**.",
        prompt="Q2 – Derive the maximum acceptable RPO in MINUTES.",
        validator=lambda v: 0 < v <= 15, points=5, unit="minutes"))

    s.append(dict(kind="question",
        info="✓ RPO: max acceptable data loss = **15 minutes** (reconstruction boundary).",
        prompt="Q3 – Censor: 'Du nævner RPO og RTO — men hvad er MAO, og hvordan hænger de tre sammen på tidslinjen fra seneste backup til reetablering?'",
        groups=[
            ("MAO = Maximum Acceptable Outage — den samlede maksimale nedetid", [r"maximum\s+acceptable\s+outage", r"samlede?.{0,40}nedetid", r"maks.{0,30}(outage|nedetid)", r"total.{0,30}(downtime|outage)"]),
            ("relationen: RPO + RTO ≤ MAO", [r"rpo\s*\+\s*rto", r"rto\s*\+\s*rpo", r"<=?\s*mao", r"summen", r"tilsammen"]),
            ("defineres i BIA — høj kritikalitet = lavere RPO/RTO", [r"\bbia\b", r"business\s+impact", r"kritikalitet", r"kritiske\s+systemer"]),
        ], points=6, threshold=2))

    s.append(dict(kind="question",
        prompt="Q4 – Pick a DR architecture that meets RTO≤4h / RPO≤15min on a mid-size budget. Explain why nightly backups alone FAIL and why active-active is OVERKILL here.",
        groups=[
            ("warm standby / pilot light in second site or cloud region", [r"warm\s+standby", r"pilot\s+light", r"standby", r"secondary\s+(site|region)"]),
            ("continuous replication / WAL streaming / log shipping for RPO", [r"\bwal\b", r"log\s+shipping", r"stream", r"continuous\s+replicat"]),
            ("nightly backups violate RPO (up to 24h data loss)", [r"nightly.{0,80}(24|rpo|loss)", r"24\s*(h|hour|timer)"]),
            ("active-active costs/complexity not justified by 4h RTO", [r"active.?active.{0,120}(cost|complex|overkill|dyr|expens)", r"(cost|dyr|expens|complex).{0,120}active.?active"]),
        ], points=10, threshold=2))

    s.append(dict(kind="question",
        prompt="Q5 – State the 3-2-1 backup rule and add the modern extension that defeats ransomware.",
        groups=[
            ("3 copies of the data", [r"\b3\b.{0,30}(cop|kopi)", r"three\s+cop"]),
            ("2 different media/technologies", [r"\b2\b.{0,40}(media|medier|technolog|typer)"]),
            ("1 copy off-site", [r"\b1\b.{0,30}off.?site", r"off.?site", r"offsite", r"anden\s+lokation"]),
            ("immutable/air-gapped copy + tested restores", [r"immutab", r"air.?gap", r"worm", r"object\s+lock", r"test.{0,25}(restore|gendan)"]),
        ], points=8, threshold=3,
        postmortem_title="RTO/RPO & DR Economics",
        postmortem_body=(
            "RTO and RPO are BUSINESS numbers wearing technical clothes. The exam board loves candidates who derive the targets from kroner. Once derived, the targets dictate the architecture tier: RPO of days = nightly backups; RPO of minutes = continuous replication; RPO of zero = synchronous replication (CAP theorem applies).\n\n"
            "RTO ladder: days = restore from backup; hours = warm standby; minutes = hot standby with automatic failover; ~zero = active-active (doubles infrastructure cost + data conflict complexity).\n\n"
            "The 3-2-1 rule predates ransomware. Modern extension is 3-2-1-1-0: one copy immutable or air-gapped, and ZERO errors on restore tests. An untested backup is a hypothesis, not a backup — say that to the censor."
        )))

    # ── Oral Exam Board (20 questions) ────────────────────────────────────────
    board = [
        ("BOARD Q1/20 — Censor 1: 'Hvad er ITIL, og forklar Service Value Chain. Nævn mindst tre af de 7 Guiding Principles.'",
         [("ITIL = rammeværk for ITSM, leverandør-uafhængigt", [r"itsm", r"service\s*management", r"rammev", r"framework", r"best\s*practice", r"infrastructure\s+library"]),
          ("Plan", [r"\bplan\b"]), ("Engage", [r"engage"]), ("Design & Transition", [r"design", r"transition"]),
          ("Obtain/Build", [r"obtain", r"build"]), ("Deliver & Support + Improve", [r"deliver", r"support", r"improve"]),
          ("guiding principles (focus on value, iterate, collaborate, keep simple, automate…)", [r"focus\s+on\s+value", r"start\s+where", r"iterat", r"collaborat", r"keep\s+it\s+simple", r"automat"])],
         8, 4),
        ("BOARD Q2/20 — Censor 2: 'En server er nede — 5. gang denne måned. Forklar med ITIL-begreber hvad Incident Management og Problem Management gør ved det.'",
         [("IM = genopret service SÅ HURTIGT som muligt", [r"genopret", r"restore", r"hurtig", r"as\s+fast"]),
          ("IM bruger workarounds og kræver INGEN godkendelse", [r"workaround", r"midlertidig", r"ingen\s+godkend", r"no\s+approval"]),
          ("PM = find og fjern ROOT CAUSE", [r"root\s*cause", r"rod[aå]rsag", r"problem\s+management"]),
          ("5-gange-reglen / reactive vs proactive PM", [r"\b5\b.{0,30}(gang|times)", r"reactive", r"proactive", r"proaktiv"])],
         8, 3),
        ("BOARD Q3/20 — Censor 1: 'Beskriv servicedeskens opgaver, escalation flow (linje 0–3) og hvad Priority 1 Critical kræver.'",
         [("log, kategoriser og prioriter alle henvendelser", [r"log", r"kategoris", r"prioriter"]),
          ("Linje 0 = self-help (FAQ, wiki, chatbot)", [r"linje\s*0", r"self.?help", r"faq", r"wiki", r"chatbot"]),
          ("Linje 1 = service desk løser simple/kendte problemer", [r"linje\s*1", r"service\s*desk", r"f[oø]rste.?linje", r"1st\s*line"]),
          ("Linje 2–3 = eksperter, nye/ukendte problemer", [r"linje\s*2", r"2nd", r"3rd", r"ekspert", r"specialist"]),
          ("P1 Critical: immediate response, resolution ~1 time", [r"immediate", r"straks", r"1\s*(time|hour)", r"system\s+down", r"critical"])],
         8, 3),
        ("BOARD Q4/20 — Censor 2: 'I migrerer økonomisystemet fra fysisk til virtuel server. Hvilken change-type, hvem godkender, og hvad siger de 7 R'er?'",
         [("Normal change → CAB-godkendelse", [r"normal\s+change", r"\bcab\b", r"change\s+advisory"]),
          ("Standard (pre-godkendt, lav risiko) og Emergency (ECAB)", [r"standard\s+change", r"pre.?godkendt", r"emergency", r"ecab"]),
          ("RFC + back-out/rollback-plan + test", [r"\brfc\b", r"request\s+for\s+change", r"back.?out", r"rollback", r"testmilj"]),
          ("7 R'er: Raised, Reason, Return, Risks, Resources, Responsible, Relationship", [r"raised", r"reason", r"return", r"risks?", r"resources", r"responsible", r"relationship", r"7\s*r"])],
         8, 3),
        ("BOARD Q5/20 — Censor 1: 'Skitser indholdet af en SLA for vores servicedesk — og forklar hvordan OLA'er og Underpinning Contracts understøtter den.'",
         [("scope: hvilke services/systemer er dækket", [r"scope", r"services?\b", r"omfang", r"hvilke\s+system"]),
          ("målbare mål: oppetid (fx 99,9%) + response/resolution tider", [r"99[.,]9", r"oppetid", r"uptime", r"availab", r"response\s*time", r"resolution", r"prioritet"]),
          ("måling og rapportering (KPI'er)", [r"kpi", r"m[aå]l(ing|es)", r"rapport", r"metric", r"monitor"]),
          ("konsekvenser/eskalation ved brud + ansvar", [r"sanktion", r"konsekvens", r"eskaler", r"penalty", r"ansvar"]),
          ("SLA=kunde; OLA=interne teams; UC=ekstern leverandør — skrappere end SLA'en", [r"ola", r"underpinning", r"\buc\b", r"intern", r"skrapper", r"strammere", r"underst[oø]t"])],
         10, 3),
        ("BOARD Q6/20 — Censor 2 (JHB-klassiker): 'iAAA er nøglen til det hele. Forklar de fire begreber og hvad der skal ske ved on- og offboarding.'",
         [("Identification = du hævder hvem du er (brugernavn)", [r"identifi", r"h[aæ]vder", r"brugernavn", r"claim"]),
          ("Authentication = systemet verificerer (password, MFA)", [r"authenti", r"verific", r"password", r"mfa", r"biometri"]),
          ("Authorization = adgang tildeles (RBAC/ACL/PoLP)", [r"authori[sz]", r"rbac", r"acl", r"least\s+privilege", r"polp", r"rettighed"]),
          ("Accountability = logging/audit", [r"accountab", r"logg?ing", r"audit", r"siem", r"ansvar"]),
          ("klare procedurer: onboarding, rolleskift, offboarding", [r"onboard", r"offboard", r"deaktiver", r"disable", r"lifecycle", r"keycard"])],
         8, 3),
        ("BOARD Q7/20 — Censor 1: 'Skriv risikoformlen fra BÅDE ledelsens og analytikerens perspektiv. Nævn de fire måder at behandle en risiko.'",
         [("CEO: RISK = Likelihood × Consequence", [r"likelihood\s*[x*×]\s*consequence", r"sandsynlighed\s*[x*×]\s*konsekvens"]),
          ("Analytiker: RISK = Threat × Vulnerability × Impact", [r"threat\s*[x*×]\s*vulnerab", r"trussel\s*[x*×]\s*s[aå]rbar"]),
          ("Threat × Vulnerability = Likelihood", [r"(threat|trussel).{0,40}=\s*likelihood", r"udg[oø]r\s+likelihood"]),
          ("risk matrix / score styrer handling", [r"matrix", r"score", r"extreme", r"gr[oø]n", r"r[oø]d"]),
          ("4 behandlinger: Mitigate, Accept, Transfer, Avoid", [r"mitigat", r"accept", r"transfer", r"avoid", r"undg[aå]"])],
         8, 3),
        ("BOARD Q8/20 — Censor 2: 'Forklar forholdet mellem ISO 27001, et ISMS og SoA'en. Hvordan er PDCA bygget ind i standarden?'",
         [("ISMS = system af politikker/processer/kontroller; 27001 = standarden/kravene", [r"isms", r"management\s+system", r"ledelsessystem"]),
          ("SoA = Statement of Applicability: valgte/fravalgte kontroller og HVORFOR", [r"soa", r"statement\s+of\s+applicability", r"fravalg"]),
          ("RISIKOVURDERINGEN styrer kontrolvalget", [r"risikovurdering", r"risk\s+assessment", r"risiko.{0,40}(styrer|v[aæ]lger|driver)"]),
          ("Annex A: 93 kontroller, 4 temaer", [r"93", r"annex\s*a", r"4\s+temaer", r"organisatorisk", r"teknologisk"]),
          ("PDCA i HLS: kap 4–6 Plan, 7–8 Do, 9 Check, 10 Act", [r"pdca", r"plan.?do.?check.?act", r"hls", r"high\s+level\s+structure"])],
         8, 3),
        ("BOARD Q9/20 — Censor 1: 'Virksomheden vil ISO 27001-certificeres. Forklar Stage 1 vs Stage 2 og forskellen på minor og major non-conformity.'",
         [("Stage 1 = dokumentationsgennemgang (har I politikkerne?)", [r"stage\s*1.{0,80}(dokument|paper|politik)", r"dokument.{0,60}stage\s*1"]),
          ("Stage 2 = feltevaluering (virker det i PRAKSIS?)", [r"stage\s*2.{0,80}(praksis|felt|practice)"]),
          ("årlige surveillance audits + re-certificering hvert 3. år", [r"surveillance", r"3\.?\s*[aå]r", r"re.?certificer", r"[aå]rlig"]),
          ("minor = isoleret fejl; major = systemisk svigt, kan blokere certificering", [r"minor.{0,80}(isoler|enkelt)", r"major.{0,80}(system|bloker)", r"non.?conformit"])],
         8, 2),
        ("BOARD Q10/20 — Censor 2: 'En medarbejder finder et print med persondata ved kopimaskinen efter en ekstern tekniker. Hvad gør I — og hvilke GDPR-begreber er i spil?'",
         [("sikr dokumentet straks + rapporter til leder/DPO", [r"sikr", r"beskyt", r"fjern", r"rapport", r"dpo", r"leder"]),
          ("72-timers reglen: anmeld databrud til Datatilsynet", [r"72", r"datatilsynet", r"anmeld"]),
          ("forebyg: Clear Desk Policy, besøgsregler, adgangskontrol", [r"clear\s*desk", r"bes[oø]gs", r"printer", r"politik", r"procedure"]),
          ("GDPR-begreber: DSAR, retten til at blive glemt, privacy by design", [r"dsar", r"blive\s+glemt", r"forgotten", r"privacy\s+by\s+design", r"databehandler", r"minimization"])],
         8, 3),
        ("BOARD Q11/20 — Censor 1: 'Forklar backup-agentens rolle, forskellen på SAN og NAS, hvad er 3-2-1, og hvad gør en backup til en RIGTIG backup?'",
         [("agenten læser data, pakker/krypterer og sender til storage; styres af Backup Manager", [r"agent.{0,120}(l[aæ]ser|henter|sender|krypter|pakker)", r"backup\s*manager"]),
          ("inkrementel backup — kun ændringer siden sidst", [r"inkrement", r"increment", r"kun.{0,30}[aæ]ndr"]),
          ("SAN = block-level, dedikeret netværk; NAS = file-level", [r"san.{0,80}block", r"block.{0,60}san", r"nas.{0,80}file", r"file.{0,60}nas"]),
          ("3-2-1: 3 kopier, 2 medier, 1 offsite", [r"3\s*kopi", r"2\s*(medier|forskellige)", r"1\s*off.?site", r"3.?2.?1"]),
          ("TEST RESTORE — en utestet backup er ikke en backup", [r"test.{0,30}(restore|gendan)", r"utestet", r"ikke\s+en\s+backup"])],
         8, 3),
        ("BOARD Q12/20 — Censor 2: 'Placer os på CMMI-skalaen (incidents løses af én heltemodigt admin). Nævn alle 5 niveauer, læg en plan for Level 3. Må man springe niveauer over?'",
         [("Level 1 Initial: ad hoc, reaktiv, hero-kultur", [r"(level|niveau)\s*1", r"initial", r"ad\s*hoc", r"hero", r"reaktiv"]),
          ("niveauerne: Managed, Defined, Quantitatively Managed, Optimizing", [r"managed", r"defined", r"quantitat", r"optimi[sz]"]),
          ("Level 3 = processer defineret på ORGANISATIONSNIVEAU", [r"organisationsniveau", r"org.{0,20}wide", r"samme\s+(regler|processer)"]),
          ("man må IKKE springe niveauer over", [r"ikke.{0,30}spring", r"cannot\s+skip", r"fundament", r"trin\s+for\s+trin"]),
          ("plan: dokumenter processer, ITIL som ramme, mål med metrics", [r"dokumenter", r"itil", r"metric", r"m[aå]l\b", r"staged"])],
         10, 3),
        ("BOARD Q13/20 — Censor 1: 'Type 1 vs Type 2 hypervisor. Hvad er noisy neighbor, og hvornår vælger man stadig en fysisk server?'",
         [("Type 1 = bare-metal, direkte på hardware (ESXi, Hyper-V, KVM)", [r"type\s*1.{0,120}(bare.?metal|direkte|hardware|esxi|hyper.?v|kvm)", r"bare.?metal"]),
          ("Type 2 = hosted, oven på et OS (VirtualBox, VMware Workstation)", [r"type\s*2.{0,120}(hosted|oven|os|virtualbox|workstation)", r"hosted"]),
          ("fordele: konsolidering, snapshots, skalering, failover/HA", [r"konsolider", r"snapshot", r"skaler", r"failover"]),
          ("noisy neighbor + hypervisor-overhead", [r"noisy\s+neighbor", r"overhead", r"deler?\s+ressourcer"]),
          ("fysisk ved: HPC, kæmpe databaser, compliance", [r"hpc", r"high.?performance", r"stor.{0,20}(database|sql)", r"complian", r"fysisk\s+isolation"])],
         8, 3),
        ("BOARD Q14/20 — Censor 2: 'Konsolidering: investering 200.000 kr, besparelse 120.000 kr/år. Skriv ROI-formlen og regn ROI efter 2 år.'",
         [("ROI-formlen: (gevinst − investering) / investering × 100", [r"gevinst\s*-\s*invest", r"\(.{0,30}-.{0,30}\)\s*/\s*invest", r"return\s+on\s+investment"]),
          ("regnestykket: ROI = 20% / break-even under 2 år", [r"40\.?000", r"20\s*%", r"break.?even", r"240"]),
          ("ROI → business case for ledelsen; Change Management → kontrolleret gennemførelse", [r"roi.{0,120}(ledelse|business\s*case|godkend)", r"change\s*management.{0,120}(kontrol|risiko|back.?out)"])],
         8, 2),
        ("BOARD Q15/20 — Censor 1: 'Forklar IaaS, PaaS og SaaS med eksempler, public/private/hybrid cloud, og Shared Responsibility Model.'",
         [("IaaS = rå infrastruktur/VM'er (lejer hardware)", [r"iaas.{0,80}(infrastruktur|hardware|vm|virtuelle)", r"infrastructure\s+as\s+a\s+service"]),
          ("PaaS = platform/miljø til at udvikle apps", [r"paas.{0,80}(platform|udvikl|milj)", r"platform\s+as\s+a\s+service"]),
          ("SaaS = færdigt program via browser (M365)", [r"saas.{0,80}(f[aæ]rdig|program|browser|abonnement|365)", r"software\s+as\s+a\s+service"]),
          ("public/private/hybrid + elasticitet/on-demand", [r"public", r"private", r"hybrid", r"elastic", r"on.?demand"]),
          ("Shared Responsibility: ansvaret deles forskelligt pr. lag", [r"shared\s+responsibility", r"delt\s+ansvar", r"provider.{0,60}kunde"])],
         8, 3),
        ("BOARD Q16/20 — Censor 2: 'Hvorfor opstår siloer mellem Dev og Ops? Forskellen på CI, Continuous Delivery og Continuous Deployment? IaC og MTTR?'",
         [("Dev belønnes for features, Ops straffes for nedetid", [r"bel[oø]nn.{0,60}features", r"straffes.{0,60}nedetid", r"inventors", r"mechanics"]),
          ("CI = automatisk test + integration", [r"\bci\b.{0,120}(auto|test|integr)", r"continuous\s+integration"]),
          ("Continuous Delivery = deployerbar, men MANUEL godkendelse", [r"delivery.{0,140}(manuel|manual|godkend)", r"(manuel|manual).{0,80}deploy"]),
          ("Continuous Deployment = fuldt automatisk til produktion", [r"deployment.{0,140}(auto|fuldt)", r"fuldt\s+auto"]),
          ("IaC = programmerbar infrastruktur; MTTR forbedres", [r"infrastructure\s+as\s+code", r"\biac\b", r"mttr", r"mean\s+time\s+to\s+recover"])],
         8, 3),
        ("BOARD Q17/20 — Censor 1: 'Hvad står PRINCE2 for? Tre principper, særligt Manage by Exception og Continued Business Justification.'",
         [("PRojects IN Controlled Environments", [r"controlled\s+environments", r"kontrollerede\s+milj"]),
          ("Continued Business Justification: projektet skal ALTID kunne retfærdiggøres", [r"business\s+justification", r"retf[aæ]rdigg", r"forretningsm[aæ]ssig"]),
          ("Manage by Exception: styregruppen involveres kun ved afvigelser", [r"exception.{0,120}(kun|only|problem|afvig)", r"styregrupp.{0,80}(kun|problem)"]),
          ("Learn from Experience, Roles & Responsibilities, Stages, Focus on Products, Tailor", [r"learn\s+from\s+experience", r"roles", r"stages", r"focus\s+on\s+products", r"tailor"]),
          ("management products: Business Case, Risk Register, Lessons Log", [r"business\s+case", r"risk\s+register", r"lessons\s+log", r"project\s+brief"])],
         8, 3),
        ("BOARD Q18/20 — Censor 2: 'VLAN-segmentering mod ransomware, OSI-lag for hub/switch/router, og hvad laver firewall, IDS/IPS og DMZ?'",
         [("VLAN-segmentering begrænser spredning/skadeomfang", [r"vlan", r"segment", r"begr[aæ]ns.{0,40}(spredning|angreb|skade)", r"adskil"]),
          ("hub=lag 1; switch=lag 2 (MAC); router=lag 3 (IP)", [r"hub.{0,60}(lag|layer)\s*1", r"switch.{0,60}(lag|layer)\s*2", r"router.{0,60}(lag|layer)\s*3", r"mac.?adress"]),
          ("firewall filtrerer trafik efter regler (default deny)", [r"firewall.{0,80}(filtrer|regler|deny|bloker)"]),
          ("IDS opdager / IPS blokerer mistænkelig trafik", [r"ids", r"ips", r"intrusion", r"honeypot"]),
          ("DMZ isolerer offentligt eksponerede services fra internt net", [r"dmz", r"demilitari", r"subnet", r"gateway"])],
         8, 3),
        ("BOARD Q19/20 — Censor 1: 'Forklar onboarding-flowet med AD, GPO og MDM — og forskellen på MDM og MAM i et BYOD-scenarie.'",
         [("AD-konto oprettes (PowerShell New-ADUser) i den rette OU", [r"new-aduser", r"powershell", r"csv", r"\bou\b", r"active\s*directory"]),
          ("GPO pusher konfiguration (password-politik, firewall, software)", [r"gpo", r"group\s*policy", r"password.?politik", r"push.{0,40}konfig"]),
          ("MDM (fx Intune) enroller enheder og håndhæver compliance", [r"mdm", r"intune", r"enroll", r"complian"]),
          ("PoLP/RBAC: kun nødvendige rettigheder via grupper", [r"polp", r"least\s+privilege", r"rbac", r"grupper"]),
          ("MDM = hele enheden; MAM = kun firma-apps/data (BYOD, remote wipe)", [r"mam", r"byod", r"remote\s*wipe", r"container", r"hele\s+enheden"])],
         8, 3),
        ("BOARD Q20/20 — Censor 2: 'Symmetrisk vs asymmetrisk kryptering, hvorfor HASHER vi passwords, hvad løser Diffie-Hellman, og hvad er de tre elementer i 2FA?'",
         [("symmetrisk = en delt nøgle (hurtig); asymmetrisk = public/private key (HTTPS)", [r"symmetrisk.{0,120}(en|delt|samme)\s*n[oø]gle", r"asymmetrisk.{0,120}(public|private)", r"https"]),
          ("hashing er ENVEJS — kan ikke gendannes; sammenlign hash af input", [r"envejs", r"one.?way", r"ikke\s+gendan", r"sammenlign.{0,40}hash"]),
          ("Diffie-Hellman: sikker nøgleudveksling over usikker kanal", [r"diffie", r"n[oø]gleudveksling", r"usikker\s+(kanal|forbindelse)", r"key\s+exchange"]),
          ("2FA = Something you HAVE / ARE / KNOW", [r"have", r"\bare\b", r"know", r"noget\s+du\s+(har|er|ved)", r"to.?faktor", r"2fa", r"mfa"])],
         8, 3),
    ]

    for i, (prompt, groups, pts, thresh) in enumerate(board):
        step = dict(kind="question", prompt=prompt, groups=groups, points=pts, threshold=thresh)
        if i == 0:
            step["scenario"] = "THE ORAL EXAM BOARD — EK/KEA IT-Drift pensum"
            step["info"] = "To censorer (JHB og Oskar Tuska). Svar i hele sætninger — dansk eller engelsk."
        s.append(step)

    s[-1]["postmortem_title"] = "Facing the Board"
    s[-1]["postmortem_body"] = (
        "Boardet dækker nu hele EK/KEA-pensum. Mønsteret der giver 12: (1) definer begrebet i en sætning, "
        "(2) placer det i rammeværket, (3) giv et konkret driftseksempel fra dit portfolio-projekt, "
        "(4) nævn selv begrænsningen eller trade-off'et.\n\n"
        "Bind emnerne sammen: iAAA → CIA-triaden → risikoanalysen → Annex A-kontroller → SoA → audit. "
        "En kandidat der kan gå fra 'hvem må logge ind' til 'hvordan beviser vi det over for en auditor' "
        "i én sammenhængende fortælling har vist hele governance-kæden — præcis dér ligger 7→12-grænsen."
    )
    return s


def _steps_frontend():
    s = []

    # ── Case 1: Memory leak ───────────────────────────────────────────────────
    s.append(dict(kind="question",
        scenario="CASE 1: The SSR pod that eats 4 GB and dies",
        alert="Kubernetes: next-ssr pods OOMKilled every ~40 minutes under load. RSS climbs linearly, never plateaus.",
        code=("// lib/productCache.js\n"
              "const cache = new Map();\n\n"
              "export async function getProductData(id, locale) {\n"
              "  const key = `${id}:${locale}`;\n"
              "  if (!cache.has(key)) {\n"
              "    const data = await fetchProductFromCMS(id, locale);  // ~120 KB object\n"
              "    cache.set(key, data);\n"
              "  }\n"
              "  return cache.get(key);\n"
              "}"),
        code_lang="javascript",
        info="50.000 products × 12 locales. Node process lives for days.",
        prompt="Q1 – Explain the exact mechanism of the leak. Why does this code behave fine in `next dev` but kill production pods?",
        groups=[
            ("module-scope Map lives for the entire process lifetime (evaluated once, singleton)", [r"module.{0,30}(scope|level)", r"top.?level", r"global", r"process\s+lifetime", r"evaluated\s+once", r"singleton"]),
            ("unbounded growth: 600k keys × 120 KB, no eviction/TTL", [r"unbounded", r"no\s+(eviction|ttl|limit)", r"grows?\s+forever", r"never\s+(evict|clear|remov)"]),
            ("dev restarts/HMR constantly so it never accumulates; prod is long-lived", [r"dev.{0,80}(restart|recompil|hot\s*reload|hmr)", r"long.?lived", r"shared\s+across\s+request"]),
        ], points=9, threshold=2))

    s.append(dict(kind="question",
        prompt="Q2 – Write/describe the production-grade fix. Commit to one approach and justify it.",
        groups=[
            ("bounded cache: LRU with max size and/or TTL (e.g. lru-cache)", [r"\blru\b", r"ttl", r"max.{0,12}(size|entries)", r"bounded", r"evict"]),
            ("externalize: Redis/CDN cache shared across pods", [r"redis", r"memcach", r"external\s+cache", r"cdn", r"shared\s+cache"]),
            ("per-request memoization (React cache() / request scope) instead of process scope", [r"react\s+cache", r"\bcache\(\)", r"per.?request", r"request\s+scope", r"unstable_cache"]),
        ], points=8, threshold=1))

    s.append(dict(kind="question",
        prompt="Q3 – Your fix ships. How do you PROVE to the team lead that the leak is gone? Name tools/signals.",
        groups=[
            ("heap snapshots / --inspect / Chrome DevTools comparison", [r"heap\s*(snapshot|dump)", r"--inspect", r"devtools", r"clinic", r"heapdump"]),
            ("process.memoryUsage / RSS metrics over time under load", [r"memoryusage", r"\brss\b", r"memory\s+(metric|graph)", r"grafana", r"prometheus"]),
            ("load test + observe plateau instead of linear growth", [r"load\s*test", r"k6", r"vegeta", r"artillery", r"plateau", r"soak"]),
        ], points=6, threshold=2,
        postmortem_title="SSR Memory Leaks",
        postmortem_body=(
            "The deepest mental-model shift when moving from SPA to SSR: your React code now runs inside ONE long-lived Node process serving thousands of users. Anything at module scope — Maps, arrays, closures captured by timers — is effectively a global that survives every request.\n\n"
            "Why dev hides it: HMR tears the module graph down constantly, so the Map never accumulates. The classic signature is RSS climbing linearly under steady traffic with no plateau.\n\n"
            "The senior fix is choosing the right cache LOCATION: per-request memoization for request-coherence, bounded in-process LRU for hot keys, Redis for cross-pod sharing, and HTTP/CDN caching in front of all of it."
        )))

    # ── Case 2: Core Web Vitals ───────────────────────────────────────────────
    s.append(dict(kind="question",
        scenario="CASE 2: Core Web Vitals are failing — SEO traffic drops",
        code=("Field data (CrUX, 28 days, mobile p75):\n"
              "  LCP : 4.9s   (target < 2.5s)   FAIL\n"
              "  CLS : 0.31   (target < 0.1)    FAIL\n"
              "  INP : 180ms  (target < 200ms)  pass\n\n"
              "Findings:\n"
              "  - Hero image: <img src=\"/hero.jpg\">  2.4 MB JPEG, no dimensions\n"
              "  - Custom font: blocking @font-face, FOIT\n"
              "  - Campaign banner injected by JS ~1.8s after load, shifts page\n"
              "  - 740 KB JS main bundle; chart lib used on 2% of pages"),
        code_lang="lighthouse/CrUX report",
        prompt="Q1 – Fix LCP. Name the concrete Next.js mechanisms for the hero image and the font.",
        groups=[
            ("next/image with priority (preload + optimized format/size)", [r"next/image", r"<image", r"\bpriority\b", r"preload"]),
            ("modern format + responsive sizes (AVIF/WebP, srcset/sizes)", [r"avif", r"webp", r"srcset", r"\bsizes\b", r"compress", r"resize"]),
            ("next/font or font-display: swap to kill the FOIT", [r"next/font", r"font-display", r"\bswap\b", r"self.?host"]),
        ], points=8, threshold=2))

    s.append(dict(kind="question",
        prompt="Q2 – Fix CLS. What is causing the 0.31 and what are the two fixes?",
        groups=[
            ("late-injected banner shifts layout / images without dimensions", [r"banner", r"inject", r"shift", r"dimension", r"width.{0,15}height"]),
            ("reserve space: fixed-size container/skeleton/placeholder or min-height", [r"reserve", r"placeholder", r"skeleton", r"min-?height", r"aspect.?ratio"]),
            ("set width/height so the browser can pre-allocate the box", [r"width", r"height", r"aspect", r"fill"]),
        ], points=7, threshold=2))

    s.append(dict(kind="question",
        prompt="Q3 – Fix the 740 KB bundle. Which technique removes the chart library from 98% of page loads, and how do you verify what is inside the bundle?",
        groups=[
            ("dynamic import / next/dynamic / code splitting (lazy load on the 2%)", [r"dynamic\s*import", r"next/dynamic", r"import\(", r"code.?split", r"lazy"]),
            ("bundle analyzer to inspect composition", [r"analyz", r"@next/bundle", r"webpack.?bundle", r"source.?map.?explorer"]),
            ("tree-shaking / import only used parts", [r"tree.?shak", r"named\s+import", r"per.?module\s+import", r"sideeffects"]),
        ], points=6, threshold=2,
        postmortem_title="Core Web Vitals",
        postmortem_body=(
            "Web Vitals are not a Lighthouse vanity score — Google uses FIELD data (CrUX, real users at p75) as a ranking signal. The p75-on-mobile detail matters: your M3 MacBook on office wifi tells you nothing about the median Android phone on 4G.\n\n"
            "LCP chain: discover → fetch → decode → paint. next/image gives AVIF/WebP transcoding, responsive srcset, lazy loading by default, and `priority` to preload the LCP element. Fonts cause both LCP and CLS damage; next/font self-hosts, preloads, and applies size-adjusted fallbacks.\n\n"
            "CLS contract: every element must have its space reserved before it arrives. Bundle size attacks INP and TTFB-to-interactive: next/dynamic moves the cost to the pages that actually pay rent on it."
        )))

    # ── Case 3: ISR ───────────────────────────────────────────────────────────
    s.append(dict(kind="question",
        scenario="CASE 3: 50.000 product pages — the build takes 3 hours",
        info="Marketing edits prices in the CMS and screams when the site shows stale prices for hours. A full rebuild takes 3 hours. SSR on every request would melt the CMS API (rate-limited at 50 rps).",
        prompt="Q1 – Write/describe the Next.js config that gives every product page background regeneration every 5 minutes.",
        groups=[
            ("revalidate = 300 (export const revalidate / getStaticProps revalidate / fetch next.revalidate)", [r"revalidate\s*[:=]\s*300", r"revalidate\s*[:=]\s*\d+", r"next:\s*\{\s*revalidate"]),
            ("static generation as the base (generateStaticParams / getStaticProps / getStaticPaths)", [r"generatestaticparams", r"getstaticprops", r"getstaticpaths", r"static"]),
        ], points=7, threshold=1))

    s.append(dict(kind="question",
        prompt="Q2 – 5 minutes is still too slow for a Black Friday price change. Which Next.js mechanism updates ONE page within seconds of the CMS edit, and how is it wired up?",
        groups=[
            ("on-demand revalidation: revalidatePath / revalidateTag / res.revalidate", [r"revalidatepath", r"revalidatetag", r"res\.revalidate", r"on.?demand"]),
            ("triggered by a CMS webhook hitting a secured route handler/API route", [r"webhook", r"api\s*route", r"route\s*handler", r"secret", r"token"]),
        ], points=7, threshold=2))

    s.append(dict(kind="question",
        prompt="Q3 – You cannot pre-build 50.000 pages. How do you build only the top 500 and still serve the long tail on first visit? Name the mechanism and what the FIRST visitor experiences.",
        groups=[
            ("generateStaticParams returns subset + dynamicParams=true (or fallback:'blocking' in Pages Router)", [r"dynamicparams", r"fallback", r"blocking", r"subset", r"top\s*500", r"generatestaticparams"]),
            ("first visitor triggers SSR/on-demand generation, result is cached for everyone after", [r"first\s+(visit|request).{0,90}(generat|render|ssr)", r"on.?demand.{0,40}(generat|render)", r"cached?\s+(after|for)"]),
        ], points=7, threshold=1,
        postmortem_title="ISR & Caching Strategy",
        postmortem_body=(
            "ISR solves a trilemma: static = fast but stale, SSR = fresh but expensive, full rebuilds don't scale past a few thousand pages. ISR serves a cached static page while regenerating it in the background once it's older than `revalidate` — stale-while-revalidate.\n\n"
            "Time-based revalidation caps staleness; on-demand revalidation (CMS webhook → route handler → revalidateTag) makes updates event-driven — fresher AND cheaper. Tag-based invalidation is the senior detail: tag fetches with 'product-123' so a price change invalidates exactly the pages that depend on it.\n\n"
            "For huge catalogues: build the head of the traffic distribution (top 500) and let dynamicParams handle the tail on first request. You've reinvented a demand-filled CDN cache — which is the point."
        )))

    # ── Case 4: Hydration ────────────────────────────────────────────────────
    s.append(dict(kind="question",
        scenario="CASE 4: 'Text content does not match server-rendered HTML'",
        alert="Sentry: 31.000 hydration errors in 24h.",
        code=("export default function CampaignHeader({ endsAt }) {\n"
              "  const msLeft = new Date(endsAt) - Date.now();\n"
              "  const greeting = Math.random() > 0.5 ? \"Hurry!\" : \"Last chance!\";\n"
              "  return (\n"
              "    <header>\n"
              "      <h1>{greeting}</h1>\n"
              "      <span>Ends in {Math.floor(msLeft / 60000)} minutes</span>\n"
              "      <span>{new Date(endsAt).toLocaleTimeString()}</span>\n"
              "    </header>\n"
              "  );\n"
              "}"),
        code_lang="jsx",
        prompt="Q1 – Explain what hydration IS and exactly why this component throws. Identify all three bugs.",
        groups=[
            ("hydration = React attaches to server HTML and expects IDENTICAL first client render", [r"hydrat", r"attach", r"match.{0,40}server", r"identical", r"mismatch"]),
            ("Math.random() differs between server and client render", [r"math\.random", r"random"]),
            ("Date.now()/time differs (server render time vs client render time)", [r"date\.now", r"time\s+diff", r"clock", r"render\s+time"]),
            ("toLocaleTimeString depends on locale/timezone — server (UTC) vs user's browser", [r"locale", r"timezone", r"tidszone", r"utc", r"tolocale"]),
        ], points=9, threshold=3))

    s.append(dict(kind="question",
        prompt="Q2 – Fix it properly. When is suppressHydrationWarning acceptable and why is it usually a trap?",
        groups=[
            ("two-pass render: useState+useEffect / 'mounted' flag — render time-dependent parts only after mount", [r"useeffect", r"usestate", r"mounted", r"client.?only", r"after\s+mount", r"two.?pass"]),
            ("make output deterministic: compute greeting/seed on the server and pass as prop", [r"prop", r"deterministic", r"seed", r"server.{0,40}(compute|decide)", r"samme\s+(v[aæ]rdi|input)"]),
            ("suppressHydrationWarning only for a single unavoidable node — never as a blanket fix", [r"suppresshydrationwarning.{0,160}(single|one|timestamp|last|kun|aldrig|trap|hide)", r"(only|kun).{0,80}suppresshydrationwarning"]),
        ], points=8, threshold=2,
        postmortem_title="Hydration Failures",
        postmortem_body=(
            "Hydration is React replaying the initial render in the browser and wiring event handlers onto HTML the server already produced. The contract: server render and FIRST client render must be byte-equal. Any nondeterminism breaks it — randomness, the current time, locale/timezone formatting, browser-only APIs.\n\n"
            "React 18 may throw the server HTML away and re-render the whole subtree client-side — you pay full CSR cost AND get a visual flash, and in lists it can attach handlers to the wrong rows.\n\n"
            "Fix taxonomy: (1) push nondeterminism UP — decide it on the server, pass as prop; (2) push it DOWN past hydration — stable placeholder, then swap in useEffect (the 'mounted' pattern); (3) suppressHydrationWarning on THAT element only. Blanket suppression is how teams ship the wrong prices in the right font."
        )))
    return s


def _steps_backend():
    s = []

    # ── Case 1: HikariCP ─────────────────────────────────────────────────────
    s.append(dict(kind="question",
        scenario="CASE 1: Connection pool starvation at 09:00 every day",
        alert="SQLTransientConnectionException: HikariPool-1 — Connection is not available, request timed out after 30000ms",
        code=("# application.yml\nspring.datasource.hikari.maximum-pool-size: 100\n\n"
              "@Service\npublic class InvoiceService {\n"
              "  @Transactional\n"
              "  public Receipt settle(Order order) {\n"
              "    Invoice inv = invoiceRepo.lockAndLoad(order.id());   // takes DB conn\n"
              "    TaxResult tax = taxApiClient.calculate(inv);          // HTTP, p99 = 8s !!\n"
              "    inv.apply(tax);\n"
              "    return receiptRepo.save(inv.toReceipt());\n"
              "  }\n"
              "}\n\nHost: 8 vCPU, SSD storage. 200 concurrent requests at peak."),
        code_lang="yaml + java",
        prompt="Q1 – The team already raised the pool to 100 and it got WORSE. Find the real root cause in the code above.",
        groups=[
            ("slow external HTTP call happens INSIDE @Transactional, so each request holds a DB connection for ~8s", [r"http.{0,90}(inside|i|within).{0,30}transac", r"transac.{0,90}(http|extern|tax)", r"holds?.{0,40}connection.{0,60}(8s|http|extern)"]),
            ("pool size is not the bottleneck — hold TIME is (Little's Law)", [r"hold.{0,12}time", r"little", r"duration", r"not.{0,20}pool\s+size"]),
            ("100 conns can also overload Postgres itself (context switching, lock contention)", [r"100.{0,80}(overload|too\s+many|postgres)", r"too\s+many\s+connections", r"context\s+switch"]),
        ], points=9, threshold=1))

    s.append(dict(kind="question",
        prompt="Q2 – Refactor: describe the fix to the CODE (not the config).",
        groups=[
            ("move the external call OUTSIDE the transaction (call tax API first, then open a short transaction)", [r"(outside|out\s+of|f[oø]r|before).{0,40}transak?c", r"split.{0,40}transac", r"remove.{0,20}@?transactional"]),
            ("keep transactions short: only DB work inside, set timeouts on the HTTP client", [r"short\s+transac", r"timeout", r"kun\s+db", r"only\s+db"]),
        ], points=7, threshold=1))

    s.append(dict(kind="numeric",
        info="HikariCP guidance: pool_size = (core_count × 2) + effective_spindle_count. Host: 8 vCPU, SSD (count as 1 spindle).",
        prompt="Q3 – Calculate the recommended maximum-pool-size.",
        validator=lambda v: 15 <= v <= 20, points=5, unit="connections"))

    s.append(dict(kind="exact",
        info="✓ (8 × 2) + 1 = 17. Anything 16–20 is defensible; 100 never was.",
        prompt="Q4 – One Hikari property exists specifically to catch connections that code forgot to close. Name it (and a sane value).",
        groups=[
            ("leak-detection-threshold", [r"leak.?detection.?threshold", r"leakdetection"]),
            ("a value in the seconds-to-a-minute range", [r"\b(10|15|20|30|60)\s*0{0,3}\s*(ms|s|sek|sec)?\b", r"\b(10000|15000|20000|30000|60000)\b"]),
        ], points=4, threshold=1,
        postmortem_title="HikariCP & Pool Sizing",
        postmortem_body=(
            "Pool starvation is a queueing problem: concurrent demand = arrival rate × hold time. 200 concurrent requests × 8s hold time needs 1600 connections — no pool survives that, and Postgres would collapse long before.\n\n"
            "HikariCP's own documentation recommends SMALL pools: (cores × 2) + spindles = 17 here. A small pool + short hold times outperforms a huge pool — counterintuitive to juniors, favourite interview question.\n\n"
            "The structural rule: NEVER perform network I/O inside a database transaction. And leakDetectionThreshold logs the stack trace of any connection held past N ms — catching the forgotten-close and the accidental-slow-transaction alike."
        )))

    # ── Case 2: Race condition ────────────────────────────────────────────────
    s.append(dict(kind="question",
        scenario="CASE 2: The account that went negative",
        alert="Finance reports: account #88231 balance = -7.250,00 kr. Withdrawals 'cannot' exceed balance. And yet.",
        code=("@Service\npublic class AccountService {\n"
              "  public void withdraw(long accountId, BigDecimal amount) {\n"
              "    Account acc = accountRepo.findById(accountId).orElseThrow();\n"
              "    if (acc.getBalance().compareTo(amount) >= 0) {       // CHECK\n"
              "      acc.setBalance(acc.getBalance().subtract(amount)); // ACT\n"
              "      accountRepo.save(acc);\n"
              "    } else {\n"
              "      throw new InsufficientFundsException();\n"
              "    }\n"
              "  }\n"
              "}"),
        code_lang="java",
        prompt="Q1 – Name the bug pattern precisely and narrate the exact interleaving of two threads that produces the negative balance.",
        groups=[
            ("check-then-act race / TOCTOU / lost update", [r"check.?then.?act", r"toctou", r"time.?of.?check", r"lost\s+update", r"race"]),
            ("both threads read the same balance before either writes", [r"both.{0,60}read", r"read.{0,60}(before|f[oø]r).{0,30}(writ|save)", r"same\s+balance"]),
            ("both pass the check, both subtract, second save wins → overdraw", [r"both\s+pass", r"second.{0,30}(save|write)", r"overwrit", r"overdraw", r"negativ"]),
        ], points=8, threshold=2))

    s.append(dict(kind="question",
        prompt="Q2 – Fix this in a system with MULTIPLE app instances behind a load balancer (so `synchronized` is useless). Give at least two database-backed strategies and state the trade-off.",
        groups=[
            ("pessimistic locking: SELECT ... FOR UPDATE / @Lock(PESSIMISTIC_WRITE)", [r"for\s+update", r"pessimistic", r"@lock"]),
            ("optimistic locking: @Version column, retry on OptimisticLockException", [r"optimistic", r"@version", r"version\s+(col|felt|field)"]),
            ("atomic conditional UPDATE: SET balance = balance - ? WHERE balance >= ?", [r"update.{0,80}balance\s*-\s*", r"where\s+balance\s*>=", r"atomic\s+update", r"conditional\s+update"]),
            ("trade-off: pessimistic blocks (safe, lower throughput); optimistic scales but needs retry", [r"(pessimi|lock).{0,120}(block|throughput|contention|venter)", r"optimi.{0,120}(retry|conflict|skaler|scale)", r"trade.?off"]),
        ], points=10, threshold=2))

    s.append(dict(kind="question",
        prompt="Q3 – Why does adding `synchronized` to the method 'work' on the developer laptop and create a false sense of safety?",
        groups=[
            ("synchronized only locks within ONE JVM/process", [r"one\s+jvm", r"single\s+(jvm|instance|process)", r"within.{0,20}(jvm|process)"]),
            ("production runs multiple instances/pods — the DB is the only shared arbiter", [r"multiple\s+(instance|pod|node)", r"load\s*balanc", r"distributed", r"database.{0,40}(eneste|only|shared|arbiter)"]),
        ], points=6, threshold=1,
        postmortem_title="Race Conditions & Locking",
        postmortem_body=(
            "Check-then-act is THE canonical concurrency bug: the world is allowed to change between your read and your write. @Transactional alone does NOT fix it at the default READ_COMMITTED isolation level — both transactions commit happily.\n\n"
            "The horizontal-scaling insight: any JVM-level mechanism (synchronized, ReentrantLock, Atomic*) coordinates threads in ONE process. Behind a load balancer you have N processes — the coordination point must be the shared resource itself: the database.\n\n"
            "Rule of thumb for interviews: pessimistic for hot rows and money, optimistic for low-contention business data, and put the invariant in the database (CHECK constraint balance >= 0) as the last line of defence regardless."
        )))

    # ── Case 3: Circuit breaker ───────────────────────────────────────────────
    s.append(dict(kind="question",
        scenario="CASE 3: The downstream API that dragged you under",
        alert="Your payment provider's API fails 80% of calls with 25s timeouts. YOUR service's Tomcat threads are all stuck. Healthy endpoints now 503 too. Cascade.",
        prompt="Q1 – Explain the cascade mechanically: why does ONE slow dependency take down endpoints that never call it?",
        groups=[
            ("shared, finite thread pool (Tomcat workers) exhausted by threads parked waiting on slow dependency", [r"thread\s*pool", r"tomcat", r"worker", r"exhaust", r"blocked\s+threads"]),
            ("slow is worse than down: 25s timeouts hold resources; a fast failure would release them", [r"slow.{0,80}(worse|v[aæ]rre)", r"timeout.{0,60}(hold|binder)", r"fast\s+fail", r"25s"]),
            ("no bulkhead/isolation between dependency calls and the rest of the app", [r"bulkhead", r"isolat", r"shared\s+resource"]),
        ], points=8, threshold=2))

    s.append(dict(kind="question",
        prompt="Q2 – Write the Resilience4j configuration (YAML or annotations) for a circuit breaker on 'paymentProvider'. Include the properties that control WHEN it opens and when it tries again.",
        groups=[
            ("failure-rate-threshold (e.g. 50)", [r"failure.?rate.?threshold"]),
            ("sliding-window to measure over recent calls", [r"sliding.?window"]),
            ("wait-duration-in-open-state before probing again", [r"wait.?duration.?in.?open"]),
            ("half-open probe calls (permitted-number-of-calls-in-half-open-state)", [r"half.?open", r"permitted.?number"]),
            ("plus a TIMEOUT (TimeLimiter/connect+read timeout) — breaker without timeout is half a fix", [r"time.?limiter", r"timeout"]),
        ], points=10, threshold=3))

    s.append(dict(kind="question",
        prompt="Q3 – Walk through the breaker's state machine and what your service should DO while it is open (the user still wants to pay!).",
        groups=[
            ("CLOSED: calls flow, failures counted against the window", [r"closed"]),
            ("OPEN: calls fail fast immediately, no threads risked", [r"open.{0,80}(fail\s*fast|immediate|straks|afvis|reject)", r"fail\s+fast"]),
            ("HALF_OPEN: limited probe calls decide close vs re-open", [r"half.?open", r"probe", r"test\s+calls"]),
            ("fallback: queue payment for retry / alternative provider / graceful degradation", [r"fallback", r"queue", r"retry\s+later", r"alternative", r"degrad"]),
        ], points=8, threshold=3,
        postmortem_title="Circuit Breakers & Cascading Failure",
        postmortem_body=(
            "The killer fact: a SLOW dependency is more dangerous than a DEAD one. Dead fails in milliseconds and releases the thread; slow parks the thread for the full timeout. With 200 Tomcat workers and a 25s timeout at 80% failure, your entire worker pool is parked within seconds.\n\n"
            "Circuit breaker state machine: CLOSED (traffic flows, failures tracked in sliding window) → OPEN (every call fails instantly, dependency gets breathing room) → HALF_OPEN (a handful of probes; success closes it, failure re-opens).\n\n"
            "A breaker without a fallback is just a faster error. Pair it with: aggressive timeouts, a bulkhead (separate thread budget per dependency), and a business fallback — queue the payment for async retry, fail over to a second provider, or degrade honestly."
        )))

    # ── Case 4: Thread dump ───────────────────────────────────────────────────
    s.append(dict(kind="question",
        scenario="CASE 4: Production is frozen — read the thread dump",
        alert="Order processing throughput: 0/sec. CPU: 3%. The JVM is alive but nothing moves.",
        code=('"order-worker-3" #41 BLOCKED\n'
              "   at com.nordpay.InventoryService.reserve(InventoryService.java:88)\n"
              "   - waiting to lock <0x000000076ab2> (a com.nordpay.Inventory)\n"
              "   at com.nordpay.OrderService.place(OrderService.java:42)\n"
              "   - locked <0x000000076aa1> (a com.nordpay.Ledger)\n\n"
              '"inventory-sync-1" #57 BLOCKED\n'
              "   at com.nordpay.LedgerService.book(LedgerService.java:31)\n"
              "   - waiting to lock <0x000000076aa1> (a com.nordpay.Ledger)\n"
              "   at com.nordpay.SyncJob.run(SyncJob.java:19)\n"
              "   - locked <0x000000076ab2> (a com.nordpay.Inventory)\n\n"
              '"order-worker-1" #39 WAITING (parking)\n'
              "   at jdk.internal.misc.Unsafe.park\n"
              "   - parking to wait for <0x00000007821> (LinkedBlockingQueue)\n\n"
              "Found 1 deadlock."),
        code_lang="jstack output",
        prompt="Q1 – Name the two threads that are deadlocked (exact thread names).",
        groups=[
            ("order-worker-3", [r"order.?worker.?3"]),
            ("inventory-sync-1", [r"inventory.?sync.?1"]),
        ], points=6, threshold=2))

    s.append(dict(kind="question",
        prompt="Q2 – Reconstruct the deadlock: who holds what and waits for what? And why is 'order-worker-1' NOT part of the problem?",
        groups=[
            ("order-worker-3 holds Ledger(76aa1), waits for Inventory(76ab2)", [r"order.?worker.?3.{0,140}(hold|locked|76aa1|ledger).{0,160}(wait|76ab2|inventory)"]),
            ("inventory-sync-1 holds Inventory(76ab2), waits for Ledger(76aa1) — a cycle", [r"inventory.?sync.?1.{0,140}(hold|locked|76ab2|inventory).{0,160}(wait|76aa1|ledger)", r"cycle", r"hinanden"]),
            ("order-worker-1 is WAITING/parked on a queue = idle and normal, not BLOCKED on a monitor", [r"order.?worker.?1.{0,140}(waiting|park|queue|idle|normal)", r"waiting.{0,60}(not|ikke).{0,30}blocked"]),
        ], points=9, threshold=2))

    s.append(dict(kind="question",
        prompt="Q3 – The permanent fix. State the classic rule that prevents lock-ordering deadlocks, plus one defensive alternative.",
        groups=[
            ("global consistent lock ORDERING (always Ledger before Inventory, everywhere)", [r"lock\s+order", r"consistent\s+order", r"global\s+order", r"always.{0,30}(first|f[oø]r)"]),
            ("tryLock with timeout + back off (ReentrantLock) instead of synchronized", [r"trylock", r"timeout", r"back.?off", r"reentrantlock"]),
            ("shrink/redesign: smaller critical sections, one lock, or a queue/single-writer design", [r"smaller\s+critical", r"single\s+lock", r"queue", r"single.?writer", r"redesign", r"actor"]),
        ], points=8, threshold=2,
        postmortem_title="Thread Dump Analysis",
        postmortem_body=(
            "A frozen JVM at 3% CPU is the signature of a LOCKING problem. jstack is the X-ray. Read by thread STATE: RUNNABLE = working, WAITING/parking on a queue = healthy idle pool thread, BLOCKED on an object monitor = contention, BLOCKED in a cycle = deadlock.\n\n"
            "Here OrderService takes Ledger then Inventory; SyncJob takes Inventory then Ledger. Coffman condition #4 (circular wait) is satisfied. Standard kill: one global lock acquisition order, documented and enforced.\n\n"
            "Interview move: name the four Coffman conditions (mutual exclusion, hold-and-wait, no preemption, circular wait) and point out that lock ordering attacks the fourth. That is a senior answer."
        )))
    return s


def _steps_database():
    # Module 4 has a REPL step followed by two question steps
    return [
        dict(kind="repl",
             scenario="MODULE 4 — POSTGRESQL OPERATIONS",
             info="Cluster 'nordshop-prod', PostgreSQL 16. Tables: orders (12.4M rows: id, customer_id, total, created_at, attributes jsonb) and customers (310k rows: id, name, country). Use the psql simulator below to complete M1–M3, then answer M4–M5.",
             missions=[
                 "M1  Diagnose the jsonb query with EXPLAIN, fix with the RIGHT index type, verify.\n    SELECT * FROM orders WHERE attributes @> '{\"color\": \"red\"}';",
                 "M2  The dashboard range query is slow. Index it correctly.\n    SELECT count(*) FROM orders WHERE created_at >= now() - interval '7 days';",
                 "M3  Writes are frozen. Inspect pg_stat_activity / pg_locks and terminate the CORRECT backend.",
             ]),
        dict(kind="question",
             scenario="MISSION M4: Read-replica architecture",
             info="Read traffic is 9× write traffic and analytics queries are starving OLTP. You will add two streaming read-replicas.",
             prompt="Q – Name the key PRIMARY-side and STANDBY-side configuration parameters for streaming replication, and state the one consistency caveat you must warn the app team about.",
             groups=[
                 ("primary: wal_level = replica", [r"wal_level\s*=?\s*replica", r"wal.?level"]),
                 ("primary: max_wal_senders > 0 (+ replication slot / pg_hba replication entry)", [r"max_wal_senders", r"replication\s+slot", r"pg_hba"]),
                 ("standby: hot_standby = on + primary_conninfo (+ standby.signal)", [r"hot_standby", r"primary_conninfo", r"standby\.signal"]),
                 ("caveat: ASYNC by default → replication lag, read-your-own-writes can fail", [r"lag", r"async", r"asynkron", r"read.?your.?own", r"stale\s+read", r"eventual"]),
             ], points=10, threshold=2,
             postmortem_title="Streaming Replication",
             postmortem_body=(
                 "Postgres replication ships the Write-Ahead Log. Primary side: wal_level=replica, max_wal_senders, a replication slot (monitor it — an abandoned slot fills your disk), plus a pg_hba.conf replication entry. Standby side: standby.signal + primary_conninfo, hot_standby=on.\n\n"
                 "The caveat: default replication is ASYNCHRONOUS. A user who saves a profile (write to primary) and immediately reloads (read from replica) may see their old data — the read-your-own-writes anomaly. Solutions: route freshness-critical reads to the primary, sticky sessions after writes, or synchronous_commit for chosen transactions (paying write latency)."
             )),
        dict(kind="question",
             scenario="MISSION M5: The window-function query",
             info="Analytics request: 'For every customer, show their single LARGEST order: customer name, order id, total.' 12.4M orders — a correlated subquery per customer is not acceptable.",
             prompt="Q – Write the SQL. (CTE + window function expected.)",
             groups=[
                 ("window function ranking: ROW_NUMBER()/RANK() … OVER", [r"row_number\s*\(\s*\)", r"\brank\s*\(\s*\)", r"\bover\s*\("]),
                 ("PARTITION BY customer_id", [r"partition\s+by\s+\w*customer"]),
                 ("ORDER BY total DESC inside the window", [r"order\s+by\s+\w*total\s+desc"]),
                 ("filter to the top row (WHERE rn = 1) via CTE/subquery", [r"=\s*1", r"\bwith\b", r"\bcte\b", r"qualify"]),
                 ("JOIN customers for the name", [r"join\s+customers", r"customers\s+c", r"c\.name", r"customers\."]),
             ], points=12, threshold=3,
             postmortem_title="Window Functions & Top-N-per-Group",
             postmortem_body=(
                 "Top-N-per-group is the canonical window-function use case. The naive correlated subquery re-scans orders once per customer: 310k scans of a 12.4M-row table. The window version makes ONE pass: PARTITION BY restarts numbering per customer, ORDER BY total DESC makes the biggest order row 1, WHERE rn=1 keeps it.\n\n"
                 "Know the trio: ROW_NUMBER (always unique), RANK (gaps after ties), DENSE_RANK (no gaps). And the GIN-vs-B-Tree rule: B-Tree indexes ordered scalar values (=, <, >, BETWEEN, ORDER BY); GIN is an inverted index over elements inside composite values (jsonb keys/values, arrays, full-text lexemes) — which is why @> needs GIN and created_at wants B-Tree."
             )),
    ]


MODULES = {
    "IT-Drift (Module 1)":       ("svc-itdrift",   _steps_itdrift),
    "Next.js Frontend (Module 2)": ("svc-frontend", _steps_frontend),
    "Spring Boot Backend (Module 3)": ("svc-backend", _steps_backend),
    "PostgreSQL Operations (Module 4)": ("svc-database", _steps_database),
}

DANISH_SCALE = [
    (90, "12", "Fremragende"),
    (78, "10", "Fortrinlig"),
    (60,  "7", "God"),
    (50,  "4", "Jævn"),
    (40, "02", "Tilstrækkelig"),
    (0, "00/-3", "Not yet"),
]

# ─────────────────────────────────────────────────────────────────────────────
# REPL LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def _repl_explain_jsonb(gin_created):
    if gin_created:
        return ("Bitmap Heap Scan on orders  (cost=124.31..9882.20 rows=3100)\n"
                "  ->  Bitmap Index Scan on idx_orders_attributes_gin\n"
                "Execution Time: 38.412 ms", "ok")
    return ("Seq Scan on orders  (cost=0.00..374061.00 rows=3100)\n"
            "  Filter: (attributes @> '{\"color\": \"red\"}'::jsonb)\n"
            "  Rows Removed by Filter: 12396900\n"
            "Execution Time: 8417.203 ms  ← reads ALL 12.4M rows", "warn")

def _repl_explain_range(btree_created):
    if btree_created:
        return ("Aggregate → Index Only Scan using idx_orders_created_at\n"
                "Execution Time: 91.330 ms", "ok")
    return ("Aggregate → Seq Scan on orders\n"
            "  Filter: (created_at >= now() - '7 days'::interval)\n"
            "Execution Time: 6120.877 ms", "warn")

def _repl_process(cmd, rs):
    """Process one psql command. Returns list of (text, style) tuples. Mutates rs dict."""
    low = cmd.lower().rstrip(";").strip()
    out = []

    if low in (r"\q", "quit", "exit"):
        rs["done"] = True
        out.append(("Leaving the REPL. Proceeding to M4–M5.", "info"))
        return out

    if low in (r"\d", r"\dt", r"\d orders"):
        out.append(("Table public.orders (~12,400,000 rows)\n"
                    " id bigint PK | customer_id int | total numeric(12,2)\n"
                    " created_at timestamptz | attributes jsonb\n"
                    "Indexes: " + ", ".join(sorted(rs["indexes"])), "code"))
        return out

    if low in (r"\d customers",):
        out.append(("Table public.customers (~310,000 rows)\n"
                    " id integer PK | name text | country varchar(2)", "code"))
        return out

    if low == r"\di":
        out.append(("\n".join(sorted(rs["indexes"])), "code"))
        return out

    if re.match(r"^explain", low):
        if "attributes" in low or "@>" in cmd:
            text, style = _repl_explain_jsonb(rs["gin_created"])
            out.append((text, style))
            if rs["gin_created"]:
                rs["explain_after"] = True
            else:
                rs["explain_before"] = True
        elif "created_at" in low:
            out.append(_repl_explain_range(rs["btree_created"]))
        else:
            out.append(("Seq Scan on orders  (cost=0.00..312044.10 rows=12400000)", "code"))
        return out

    if re.match(r"^create\s+index", low):
        m_table = re.search(r"on\s+(\w+)", low)
        table = m_table.group(1) if m_table else "?"
        using = re.search(r"using\s+(\w+)", low)
        method = using.group(1) if using else "btree"
        col_m = re.search(r"\(\s*([\w,\s]+?)\s*\)", low)
        col = col_m.group(1).strip() if col_m else "?"
        if table != "orders":
            out.append((f"Index created on '{table}', but slow queries hit 'orders'. No mission progress.", "warn"))
        elif "attributes" in col:
            if method == "gin":
                rs["indexes"].add("idx_orders_attributes_gin (gin on orders.attributes)")
                if not rs["gin_created"]:
                    rs["gin_created"] = True
                    rs["missions_done"].add("M1")
                    rs["points"] += 10
                    out.append(("CREATE INDEX (GIN on jsonb) done. M1 complete: +10 pts. Verify with EXPLAIN.", "ok"))
                else:
                    out.append(("Index already exists.", "info"))
            else:
                out.append(("B-Tree on jsonb only supports equality on the WHOLE document. The @> operator CANNOT use it. Think: operator class.", "warn"))
        elif "created_at" in col:
            if method == "btree":
                rs["indexes"].add("idx_orders_created_at (btree on orders.created_at)")
                if not rs["btree_created"]:
                    rs["btree_created"] = True
                    rs["missions_done"].add("M2")
                    rs["points"] += 6
                    out.append(("CREATE INDEX (B-Tree on created_at) done. M2 complete: +6 pts.", "ok"))
                else:
                    out.append(("Index already exists.", "info"))
            elif method == "gin":
                out.append(("GIN on a scalar timestamp gains nothing. Range predicates on scalars want a B-Tree.", "warn"))
            else:
                out.append(("Hash indexes support ONLY equality (=). Your query is a range (>=). Seq Scan remains.", "warn"))
        return out

    if "pg_stat_activity" in low:
        if rs["deadlock_resolved"]:
            out.append((" pid  | state  | query\n"
                        "------+--------+-------------------------------------------\n"
                        " 4901 | active | INSERT INTO orders ...\n"
                        " 4922 | active | UPDATE orders SET total ...", "ok"))
        else:
            out.append((" pid  | state               | wait_event      | xact_age | query\n"
                        "------+---------------------+-----------------+----------+------------------------------------------\n"
                        " 4821 | idle in transaction |                 | 00:41:17 | UPDATE orders SET total = ... WHERE id=9\n"
                        " 5102 | active              | Lock:transactionid | 00:39:50 | UPDATE orders SET total = ... WHERE id=9\n"
                        " 5311 | active              | Lock:tuple      | 00:22:05 | UPDATE orders SET status='paid' WHERE id=9\n"
                        " 5409 | active              | Lock:tuple      | 00:11:48 | DELETE FROM orders WHERE id = 9\n\n"
                        "⚠️  pid 4821: 'idle in transaction' for 41 minutes — holding locks but doing NOTHING.", "warn"))
        return out

    if "pg_locks" in low:
        if rs["deadlock_resolved"]:
            out.append(("pg_locks: no ungranted locks. Clean.", "ok"))
        else:
            out.append((" pid  | locktype      | granted | relation\n"
                        "------+---------------+---------+----------\n"
                        " 4821 | transactionid | t       | orders   ← HOLDS the lock\n"
                        " 5102 | transactionid | f       | orders   ← waits on 4821\n"
                        " 5311 | tuple         | f       | orders   ← waits on 5102\n"
                        " 5409 | tuple         | f       | orders   ← waits on 5311", "code"))
        return out

    if "pg_terminate_backend" in low or "pg_cancel_backend" in low:
        m = re.search(r"\(\s*(\d+)\s*\)", cmd)
        if not m:
            out.append(("Syntax: SELECT pg_terminate_backend(<pid>);", "warn"))
            return out
        pid = int(m.group(1))
        if rs["deadlock_resolved"]:
            out.append((f"Backend {pid} not found (already clean).", "info"))
        elif pid == 4821:
            rs["deadlock_resolved"] = True
            rs["missions_done"].add("M3")
            awarded = max(10 - 3 * rs["failed_kills"], 4)
            rs["points"] += awarded
            out.append((f"pg_terminate_backend(4821) → t. The zombie transaction rolled back, locks released. "
                        f"Pids 5102/5311/5409 completed within 2s. M3 complete: +{awarded} pts.", "ok"))
        elif pid in (5102, 5311, 5409):
            rs["failed_kills"] += 1
            out.append((f"You terminated pid {pid} — a VICTIM. Its transaction rolled back (lost work for a customer), "
                        f"and the queue re-formed behind the real culprit (pid 4821, still idle in transaction). -3 pts on M3.", "error"))
        else:
            out.append((f"No backend with pid {pid}.", "warn"))
        return out

    if re.match(r"^select", low):
        if "attributes" in low or "@>" in cmd:
            ms = 38 if rs["gin_created"] else 8417
        elif "created_at" in low:
            ms = 91 if rs["btree_created"] else 6120
        else:
            import random
            ms = random.randint(2, 40)
        style = "ok" if ms < 200 else "warn"
        out.append((f"Time: {ms} ms" + (" ← still reading the whole table. EXPLAIN it." if ms > 1000 else ""), style))
        return out

    out.append(("Command not recognized. Supported: EXPLAIN, CREATE INDEX, SELECT * FROM pg_stat_activity, SELECT * FROM pg_locks, SELECT pg_terminate_backend(<pid>), \\d, \\di, \\q", "warn"))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────────────────

def _init_state():
    if "module" not in st.session_state:
        st.session_state.module = None
    if "step_idx" not in st.session_state:
        st.session_state.step_idx = 0
    if "steps" not in st.session_state:
        st.session_state.steps = []
    if "scores" not in st.session_state:
        st.session_state.scores = {}  # module_key → {points, max}
    if "history" not in st.session_state:
        st.session_state.history = []
    if "feedback" not in st.session_state:
        st.session_state.feedback = None
    if "submitted" not in st.session_state:
        st.session_state.submitted = False
    # REPL state (for module 4)
    if "repl_state" not in st.session_state:
        st.session_state.repl_state = None
    if "repl_history" not in st.session_state:
        st.session_state.repl_history = []


# ─────────────────────────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _render_feedback(feedback):
    if feedback is None:
        return
    hits, missed, awarded, max_pts, passed = (
        feedback["hits"], feedback["missed"], feedback["awarded"],
        feedback["max"], feedback["passed"],
    )
    if passed:
        st.success(f"**Score: {awarded}/{max_pts}** ✓")
    else:
        st.error(f"**Score: {awarded}/{max_pts}**")

    if hits:
        st.markdown("**Concepts you nailed:**")
        for h in hits:
            st.markdown(f"&nbsp;&nbsp;✅ {h}")
    if missed:
        st.markdown("**Concepts the board expected but did not hear:**")
        for m in missed:
            st.markdown(f"&nbsp;&nbsp;❌ {m}")


def _render_scoreboard():
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Scoreboard")
    total_pts = 0
    total_max = 0
    for mod_key, score in st.session_state.scores.items():
        pts, mx = score["points"], score["max"]
        total_pts += pts
        total_max += mx
        pct = int(100 * pts / mx) if mx else 0
        color = "🟢" if pct >= 60 else ("🟡" if pct >= 40 else "🔴")
        short = mod_key.split("(")[0].strip()
        st.sidebar.markdown(f"{color} **{short}**: {pts}/{mx} ({pct}%)")
    if total_max:
        pct = int(100 * total_pts / total_max)
        grade = "00/-3"
        for cutoff, g, _ in DANISH_SCALE:
            if pct >= cutoff:
                grade = g
                break
        st.sidebar.markdown(f"---\n**Total: {total_pts}/{total_max} ({pct}%) → Grade {grade}**")


def _render_step_context(step):
    if "scenario" in step:
        st.subheader(step["scenario"])
    if "alert" in step:
        st.error(f"🚨 {step['alert']}")
    if "code" in step:
        lang = step.get("code_lang", "")
        st.code(step["code"], language=None)
        if lang:
            st.caption(lang)
    if "info" in step:
        st.info(step["info"])


def _submit_question(step, answer):
    groups = step["groups"]
    points = step["points"]
    threshold = step.get("threshold")
    hits, missed, passed = grade_answer(answer, groups, threshold)
    awarded = round(points * len(hits) / len(groups))

    mod = st.session_state.module
    if mod not in st.session_state.scores:
        st.session_state.scores[mod] = {"points": 0, "max": 0}
    st.session_state.scores[mod]["points"] += awarded
    st.session_state.scores[mod]["max"] += points

    st.session_state.history.append({
        "module": mod, "prompt": step["prompt"][:80],
        "awarded": awarded, "max": points, "passed": passed,
    })
    st.session_state.feedback = {
        "hits": hits, "missed": missed,
        "awarded": awarded, "max": points, "passed": passed,
    }
    st.session_state.submitted = True


def _advance():
    st.session_state.step_idx += 1
    st.session_state.feedback = None
    st.session_state.submitted = False


# ─────────────────────────────────────────────────────────────────────────────
# REPL RENDERER
# ─────────────────────────────────────────────────────────────────────────────

def _render_repl(step):
    _render_step_context(step)

    rs = st.session_state.repl_state
    if rs is None:
        rs = {
            "indexes": {"orders_pkey (btree on orders.id)"},
            "gin_created": False, "btree_created": False,
            "deadlock_resolved": False, "failed_kills": 0,
            "missions_done": set(), "points": 0,
            "explain_before": False, "explain_after": False,
            "done": False,
        }
        st.session_state.repl_state = rs
        st.session_state.repl_history = []

    st.markdown("**Missions:**")
    for m in step["missions"]:
        tag = "✅" if m.split()[0] in rs["missions_done"] else "⬜"
        st.markdown(f"{tag} `{m}`")

    # Terminal history
    if st.session_state.repl_history:
        st.markdown("---")
        for entry in st.session_state.repl_history[-20:]:
            st.markdown(f"```\nnordshop-prod=# {entry['cmd']}\n```")
            for text, style in entry["output"]:
                if style == "ok":
                    st.success(text)
                elif style == "warn":
                    st.warning(text)
                elif style == "error":
                    st.error(text)
                elif style == "code":
                    st.code(text)
                else:
                    st.info(text)

    if rs["done"]:
        # Award diagnostic points
        diag = (2 if rs["explain_before"] else 0) + (2 if rs["explain_after"] else 0)
        rs["points"] += diag
        mod = st.session_state.module
        if mod not in st.session_state.scores:
            st.session_state.scores[mod] = {"points": 0, "max": 0}
        st.session_state.scores[mod]["points"] += rs["points"]
        st.session_state.scores[mod]["max"] += 26  # 10+6+10 missions
        if "M3" not in rs["missions_done"]:
            st.warning("M3 (deadlock) left unresolved — writes still frozen. 0/10 pts.")
        st.session_state.repl_state = None
        st.session_state.repl_history = []
        _advance()
        st.rerun()
        return

    cmd = st.text_input("nordshop-prod=#", key=f"repl_cmd_{len(st.session_state.repl_history)}", placeholder="Type a command (\\q to exit REPL)")
    col1, col2 = st.columns([1, 4])
    with col1:
        run = st.button("Run ▶")
    with col2:
        done_btn = st.button("Exit REPL (\\q)")

    if done_btn:
        rs["done"] = True
        st.rerun()
    elif run and cmd.strip():
        output = _repl_process(cmd.strip(), rs)
        st.session_state.repl_history.append({"cmd": cmd.strip(), "output": output})
        if rs.get("done"):
            pass
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="Production Inferno", page_icon="🔥", layout="wide")
    _init_state()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.title("🔥 Production Inferno")
        st.caption("IT-Operations & Engineering Simulator")
        st.markdown("---")
        st.markdown("**Select a module:**")
        for mod_name in MODULES:
            if st.button(mod_name, key=f"btn_{mod_name}", use_container_width=True):
                svc_key, step_fn = MODULES[mod_name]
                st.session_state.module = mod_name
                st.session_state.step_idx = 0
                st.session_state.steps = step_fn()
                st.session_state.feedback = None
                st.session_state.submitted = False
                st.session_state.repl_state = None
                st.session_state.repl_history = []
                # Keep scores across modules; reset only this module's running score
                if mod_name not in st.session_state.scores:
                    st.session_state.scores[mod_name] = {"points": 0, "max": 0}
                st.rerun()

        _render_scoreboard()

    # ── Main area ─────────────────────────────────────────────────────────────
    if st.session_state.module is None:
        st.title("🔥 Production Inferno")
        st.markdown("""
**IT-Operations & Engineering Simulator** — 4 isolated service modules.

| Module | Focus |
|--------|-------|
| IT-Drift (Module 1) | Incident response + oral exam board (ITIL, ISO 27001, CMMI, SLA…) |
| Next.js Frontend (Module 2) | SSR memory leaks, Web Vitals, ISR, hydration |
| Spring Boot Backend (Module 3) | Connection pools, race conditions, circuit breakers, thread dumps |
| PostgreSQL Operations (Module 4) | Indexes, deadlocks, streaming replication, window functions |

Select a module from the sidebar to begin.
        """)
        return

    steps = st.session_state.steps
    idx = st.session_state.step_idx

    if idx >= len(steps):
        # Module complete
        mod = st.session_state.module
        score = st.session_state.scores.get(mod, {"points": 0, "max": 1})
        pts, mx = score["points"], score["max"]
        pct = int(100 * pts / mx) if mx else 0
        grade = "00/-3"
        for cutoff, g, _ in DANISH_SCALE:
            if pct >= cutoff:
                grade = g
                break
        st.title(f"✅ {mod} complete")
        st.metric("Score", f"{pts}/{mx}", f"{pct}% → Grade {grade}")
        if pct < 60:
            st.info("Re-run the module. Mastery means the post-mortems contain nothing you didn't already say yourself.")
        if st.button("Restart this module"):
            _, step_fn = MODULES[mod]
            st.session_state.steps = step_fn()
            st.session_state.step_idx = 0
            st.session_state.feedback = None
            st.session_state.submitted = False
            st.session_state.scores[mod] = {"points": 0, "max": 0}
            st.rerun()
        return

    step = steps[idx]
    total = len(steps)

    # Progress bar
    st.progress(idx / total, text=f"Question {idx + 1} / {total}")

    kind = step["kind"]

    # ── REPL ─────────────────────────────────────────────────────────────────
    if kind == "repl":
        _render_repl(step)
        return

    # ── Context display ───────────────────────────────────────────────────────
    _render_step_context(step)

    # ── Feedback from previous submission ────────────────────────────────────
    if st.session_state.submitted and st.session_state.feedback:
        _render_feedback(st.session_state.feedback)

        # Post-mortem expander
        if "postmortem_title" in step:
            with st.expander(f"📋 Post-mortem: {step['postmortem_title']}", expanded=False):
                st.markdown(step["postmortem_body"])

        if st.button("Next →", type="primary"):
            _advance()
            st.rerun()
        return

    # ── Question input ────────────────────────────────────────────────────────
    st.markdown(f"**{step['prompt']}**")

    if kind == "numeric":
        val = st.number_input("Your answer:", value=0.0, step=0.5,
                              format="%.1f", key=f"num_{idx}")
        unit = step.get("unit", "")
        if unit:
            st.caption(f"Unit: {unit}")
        if st.button("Submit", key=f"submit_{idx}", type="primary"):
            validator = step["validator"]
            points = step["points"]
            if validator(val):
                awarded = points
                passed = True
                fb_hits = [f"Correct: {val:g} {unit}"]
                fb_missed = []
            else:
                awarded = 0
                passed = False
                fb_hits = []
                fb_missed = [f"Value {val:g} {unit} — not acceptable"]

            mod = st.session_state.module
            if mod not in st.session_state.scores:
                st.session_state.scores[mod] = {"points": 0, "max": 0}
            st.session_state.scores[mod]["points"] += awarded
            st.session_state.scores[mod]["max"] += points
            st.session_state.history.append({
                "module": mod, "prompt": step["prompt"][:80],
                "awarded": awarded, "max": points, "passed": passed,
            })
            st.session_state.feedback = {
                "hits": fb_hits, "missed": fb_missed,
                "awarded": awarded, "max": points, "passed": passed,
            }
            st.session_state.submitted = True
            st.rerun()

    elif kind in ("question", "exact"):
        if kind == "exact":
            answer = st.text_input("Your command:", key=f"ans_{idx}",
                                   placeholder="Type a single-line command…")
        else:
            answer = st.text_area("Your answer:", key=f"ans_{idx}", height=160,
                                  placeholder="Type your answer here…")
        if st.button("Submit", key=f"submit_{idx}", type="primary"):
            if answer.strip():
                _submit_question(step, answer)
                st.rerun()
            else:
                st.warning("Please enter an answer before submitting.")


if __name__ == "__main__":
    main()
