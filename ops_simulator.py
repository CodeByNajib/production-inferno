#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PRODUCTION INFERNO - IT-Operations & Engineering Simulator
===========================================================
A terminal-based incident-response and exam-preparation simulator.

Architecture:
    The simulator is decoupled into 4 isolated service modules. Modules
    NEVER call each other directly and never share Python objects. All
    communication crosses a simulated network boundary (NetworkBus) where
    every request and response is serialized to JSON, given a latency
    budget, and dispatched to a registered service endpoint - exactly the
    way independent microservices would talk over HTTP/an event bus.

    Services:
        svc-itdrift    : IT-Drift exam prep (incidents + oral exam board)
        svc-frontend   : Next.js production debugging
        svc-backend    : Spring Boot performance & concurrency
        svc-database   : PostgreSQL admin via a simulated psql REPL

Run:
    python3 ops_simulator.py
"""

import json
import math
import random
import re
import shutil
import sys
import textwrap
import time

# ---------------------------------------------------------------------------
# 0. TERMINAL UI LAYER
# ---------------------------------------------------------------------------


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITAL = "\033[3m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRED = "\033[91m"
    BGREEN = "\033[92m"
    BYELLOW = "\033[93m"
    BBLUE = "\033[94m"
    BMAGENTA = "\033[95m"
    BCYAN = "\033[96m"
    GREY = "\033[90m"


def term_width():
    try:
        return min(shutil.get_terminal_size().columns, 100)
    except Exception:
        return 80


def hr(ch="-", color=C.GREY):
    print(f"{color}{ch * term_width()}{C.RESET}")


def wrap(text, indent=0, color=""):
    width = term_width() - indent
    pad = " " * indent
    for para in text.strip().split("\n\n"):
        para = " ".join(line.strip() for line in para.splitlines())
        for line in textwrap.wrap(para, width=width):
            print(f"{pad}{color}{line}{C.RESET}")
        print()


def banner(title, subtitle="", color=C.BCYAN):
    hr("=", color)
    print(f"{color}{C.BOLD}  {title}{C.RESET}")
    if subtitle:
        print(f"{C.GREY}  {subtitle}{C.RESET}")
    hr("=", color)


def section(title, color=C.BYELLOW):
    print()
    print(f"{color}{C.BOLD}>> {title}{C.RESET}")
    hr("-", C.GREY)


def alert(text):
    print(f"{C.BRED}{C.BOLD}  [ALERT] {text}{C.RESET}")


def ok(text):
    print(f"{C.BGREEN}  [OK] {text}{C.RESET}")


def warn(text):
    print(f"{C.BYELLOW}  [WARN] {text}{C.RESET}")


def info(text):
    print(f"{C.BCYAN}  [INFO] {text}{C.RESET}")


def code_block(code, lang=""):
    print(f"{C.GREY}  .{'-' * (term_width() - 4)}.{C.RESET}")
    if lang:
        print(f"{C.GREY}  | {C.ITAL}{lang}{C.RESET}")
    for line in code.strip("\n").splitlines():
        print(f"{C.GREY}  |{C.RESET} {C.WHITE}{line}{C.RESET}")
    print(f"{C.GREY}  '{'-' * (term_width() - 4)}'{C.RESET}")


class QuitGame(Exception):
    """Raised when the player quits or stdin is exhausted."""


def safe_input(prompt):
    try:
        raw = input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        raise QuitGame()
    if raw.strip().lower() in (":q", ":quit", ":exit"):
        raise QuitGame()
    return raw


def ask_line(prompt):
    return safe_input(f"{C.BGREEN}{prompt} > {C.RESET}").strip()


def read_block(prompt):
    """Read a multi-line answer. Finish with an empty line."""
    print(f"{C.BGREEN}{prompt}{C.RESET}")
    print(f"{C.GREY}  (Write your answer - commands, config or prose. "
          f"Finish with an EMPTY line. ':q' quits.){C.RESET}")
    lines = []
    while True:
        line = safe_input(f"{C.GREEN}  > {C.RESET}")
        if line.strip() == "":
            if lines:
                break
            continue
        lines.append(line)
    return "\n".join(lines)


def pause():
    safe_input(f"{C.GREY}  [press ENTER to continue]{C.RESET}")


# ---------------------------------------------------------------------------
# 1. GRADING ENGINE
# ---------------------------------------------------------------------------


def grade_answer(answer, groups, threshold=None):
    """
    groups: list of (label, [regex, regex, ...]).
    A group is 'hit' if any regex matches the answer (case-insensitive).
    Returns (hit_labels, missed_labels, passed).
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


def report_grading(hits, missed, points_awarded, points_max):
    if hits:
        print(f"{C.BGREEN}  Concepts you nailed:{C.RESET}")
        for h in hits:
            print(f"{C.GREEN}    + {h}{C.RESET}")
    if missed:
        print(f"{C.BYELLOW}  Concepts the board expected but did not hear:{C.RESET}")
        for m in missed:
            print(f"{C.YELLOW}    - {m}{C.RESET}")
    color = C.BGREEN if points_awarded >= points_max * 0.6 else C.BRED
    print(f"{color}{C.BOLD}  Score for this question: "
          f"{points_awarded}/{points_max}{C.RESET}")


def post_mortem(title, body):
    print()
    print(f"{C.BMAGENTA}{C.BOLD}  ============================================{C.RESET}")
    print(f"{C.BMAGENTA}{C.BOLD}   SENIOR ENGINEER POST-MORTEM: {title}{C.RESET}")
    print(f"{C.BMAGENTA}{C.BOLD}  ============================================{C.RESET}")
    wrap(body, indent=2, color=C.MAGENTA)
    pause()


# ---------------------------------------------------------------------------
# 2. NETWORK BUS (the simulated microservice boundary)
# ---------------------------------------------------------------------------


class NetworkBus:
    """
    Simulated network layer. Every call is serialized to a JSON request
    envelope, dispatched to the registered service, and the response is
    serialized back. Services never receive live Python objects from the
    orchestrator and never reference each other. This enforces the same
    contract-first isolation real microservices have over HTTP/gRPC.
    """

    def __init__(self):
        self._services = {}
        self._request_id = 0

    def register(self, service_name, handler):
        self._services[service_name] = handler
        print(f"{C.GREY}  [bus] service registered: "
              f"{C.BCYAN}{service_name}{C.GREY} "
              f"(endpoint: /{service_name}/*){C.RESET}")

    def call(self, service, endpoint, payload=None):
        self._request_id += 1
        rid = f"req-{self._request_id:04d}"
        envelope = json.dumps({
            "id": rid,
            "service": service,
            "endpoint": endpoint,
            "payload": payload or {},
        })
        latency = random.randint(4, 38)
        print(f"{C.GREY}  [bus] {rid} POST /{service}/{endpoint} "
              f"... ({latency}ms simulated){C.RESET}")
        # --- network boundary: only the JSON string crosses this line ---
        request = json.loads(envelope)
        handler = self._services.get(request["service"])
        if handler is None:
            return {"status": 502, "error": f"unknown service {service}"}
        try:
            response = handler(request["endpoint"], request["payload"])
        except QuitGame:
            raise
        except Exception as exc:  # the service crashed; bus returns 500
            response = {"status": 500, "error": str(exc)}
        # --- response crosses the boundary as JSON as well ---
        wire_response = json.loads(json.dumps(response))
        status = wire_response.get("status", 200)
        scolor = C.BGREEN if status < 400 else C.BRED
        print(f"{C.GREY}  [bus] {rid} <- {scolor}{status}{C.GREY} "
              f"from {service}{C.RESET}")
        return wire_response


# ---------------------------------------------------------------------------
# 3. BASE SERVICE
# ---------------------------------------------------------------------------


class ServiceModule:
    """Base class. Each module is a self-contained 'microservice'."""

    name = "svc-base"
    title = "Base"

    def __init__(self):
        self.points = 0
        self.max_points = 0

    def handle(self, endpoint, payload):
        if endpoint == "info":
            return {"status": 200, "body": self.describe()}
        if endpoint == "run":
            self.points = 0
            self.max_points = 0
            self.run(payload)
            return {"status": 200,
                    "body": {"service": self.name,
                             "points": self.points,
                             "max": self.max_points}}
        return {"status": 404, "error": f"no endpoint {endpoint}"}

    def describe(self):
        return {"name": self.name, "title": self.title}

    def run(self, payload):
        raise NotImplementedError

    # ---- shared scenario helpers -----------------------------------------

    def free_question(self, prompt, groups, points, threshold=None):
        self.max_points += points
        answer = read_block(prompt)
        hits, missed, passed = grade_answer(answer, groups, threshold)
        awarded = round(points * len(hits) / len(groups))
        self.points += awarded
        report_grading(hits, missed, awarded, points)
        return passed

    def exact_command(self, prompt, groups, points, threshold=None):
        """Single-line command answer."""
        self.max_points += points
        answer = ask_line(prompt)
        hits, missed, passed = grade_answer(answer, groups, threshold)
        awarded = round(points * len(hits) / len(groups))
        self.points += awarded
        report_grading(hits, missed, awarded, points)
        return passed

    def numeric_question(self, prompt, validator, points, unit=""):
        self.max_points += points
        raw = ask_line(prompt)
        try:
            value = float(re.sub(r"[^\d.,-]", "", raw).replace(",", "."))
        except ValueError:
            value = None
        if value is not None and validator(value):
            self.points += points
            print(f"{C.BGREEN}{C.BOLD}  Correct: {value:g} {unit} "
                  f"(+{points} pts){C.RESET}")
            return True
        print(f"{C.BRED}{C.BOLD}  Not acceptable. (0/{points} pts){C.RESET}")
        return False


# ---------------------------------------------------------------------------
# 4. MODULE 1 - IT-DRIFT (EXAM FOCUS, JUNE 23rd)
# ---------------------------------------------------------------------------


class ITDriftService(ServiceModule):
    name = "svc-itdrift"
    title = "IT-DRIFT - Incident Command + Oral Exam Board"

    def run(self, payload):
        banner("MODULE 1 - IT-DRIFT", "Exam focus: June 23rd. "
               "Incidents first, then the oral exam board.", C.BRED)
        wrap("""
        You are the on-call Operations Engineer for NordCommerce A/S,
        an e-commerce platform doing 50.000 kr/hour in revenue. You will
        handle four production disasters, then face a simulated exam board
        covering the full IT-Drift curriculum: ITIL 4, CMMI, SLA/OLA/UC,
        ISO 27001, virtualisation, network architecture and backup/DR.
        """, indent=2)
        pause()
        self.scenario_ssl()
        self.scenario_ddos()
        self.scenario_split_brain()
        self.scenario_bdr()
        self.oral_exam_board()
        banner("MODULE 1 COMPLETE",
               f"IT-Drift score: {self.points}/{self.max_points}", C.BRED)

    # ---- Scenario 1: SSL expiry ------------------------------------------

    def scenario_ssl(self):
        section("INCIDENT 1: 03:12 AM - 'The padlock is gone'", C.BRED)
        alert("PagerDuty P1: checkout conversion dropped 94% in 6 minutes.")
        code_block("""
03:12:04 monitor  uptime-probe: https://shop.nordcommerce.dk FAILED
03:12:05 monitor  TLS handshake error: certificate has expired
03:12:31 support  Customers report: NET::ERR_CERT_DATE_INVALID
03:13:10 oncall   YOU are paged. Load balancer terminates TLS (nginx).
""", "incident feed")
        self.exact_command(
            "STEP 1 - Confirm the diagnosis from the server. Which exact "
            "command do you run to inspect the certificate's validity dates?",
            [
                ("uses openssl or certbot tooling",
                 [r"\bopenssl\b", r"\bcertbot\b"]),
                ("inspects the cert (x509 / s_client / certificates)",
                 [r"x509", r"s_client", r"certbot\s+certificates"]),
                ("reads the dates (-enddate/-dates) or connects to :443",
                 [r"-enddate", r"-dates", r"-noout", r":443", r"-connect"]),
            ],
            points=6, threshold=2)
        self.exact_command(
            "STEP 2 - The cert (Let's Encrypt) expired because auto-renewal "
            "silently failed. Which command renews it right now?",
            [
                ("certbot / acme client",
                 [r"certbot", r"acme", r"lego", r"dehydrated"]),
                ("renew action",
                 [r"\brenew\b", r"--force-renewal", r"certonly"]),
            ],
            points=4, threshold=2)
        self.exact_command(
            "STEP 3 - New cert is on disk. Apply it on nginx WITHOUT "
            "dropping live connections. Exact command?",
            [
                ("targets nginx / systemd",
                 [r"nginx", r"systemctl"]),
                ("graceful RELOAD, not restart",
                 [r"\breload\b", r"-s\s+reload", r"\bHUP\b"]),
            ],
            points=5, threshold=2)
        self.free_question(
            "STEP 4 - The CTO asks in the retro: 'How do we make this class "
            "of incident structurally impossible?' Name at least two "
            "preventive controls.",
            [
                ("monitoring/alerting on cert expiry (e.g. blackbox probe, "
                 "30-day warning)",
                 [r"monitor", r"alert", r"blackbox", r"prometheus",
                  r"expiry.{0,30}(warn|alert|check)", r"30\s*d"]),
                ("automated renewal pipeline (cert-manager / certbot timer)",
                 [r"cert-?manager", r"auto.{0,12}renew", r"systemd\s+timer",
                  r"cron", r"acme"]),
                ("test the renewal path, not just the cert (dry-run, staging)",
                 [r"dry.?run", r"staging", r"test.{0,20}renew",
                  r"runbook", r"game.?day"]),
            ],
            points=6, threshold=2)
        post_mortem("SSL/TLS Expiry", """
        Certificate expiry is the most preventable P1 in the industry, and
        it still takes down giants (Microsoft Teams 2020, Spotify 2020).
        The mechanics: TLS clients hard-fail on an expired leaf certificate
        because validity windows are the only revocation mechanism that
        works offline. There is no graceful degradation - every browser
        shows an interstitial and every API client throws.

        Three layers of defence, in order of importance: (1) AUTOMATED
        renewal (certbot systemd timer or cert-manager in Kubernetes) so a
        human is never in the loop; (2) MONITORING of the renewal, because
        automation fails silently - a Prometheus blackbox_exporter probe
        with an alert at 21 days remaining catches a broken pipeline while
        you still have three renewal windows left; (3) graceful 'nginx -s
        reload' instead of restart, because reload forks new workers with
        the new cert while old workers drain existing connections - zero
        dropped requests.

        Exam angle: this maps to ITIL 4 'monitoring and event management'
        plus 'incident management' (restore service fast) followed by
        'problem management' (kill the root cause). Saying those words to
        the board converts a war story into curriculum points.
        """)

    # ---- Scenario 2: DDoS -------------------------------------------------

    def scenario_ddos(self):
        section("INCIDENT 2: Black Friday - DDoS through the CDN", C.BRED)
        alert("Traffic is 41x baseline. Origin CPU 100%. p99 latency 29s.")
        code_block("""
Edge (CDN) requests/sec:   1.2M   (baseline 29k)
Cache hit ratio:           4%     (baseline 91%)
Top path:                  GET /api/search?q=<random-string>   97.8%
Unique source IPs:         ~310.000 (residential, global)
Origin DB connections:     saturated
""", "traffic dashboard")
        self.free_question(
            "Q1 - Classify this attack precisely. Which OSI layer is being "
            "attacked, what TYPE of DDoS is this, and why is the CDN not "
            "saving you?",
            [
                ("Layer 7 / application layer attack",
                 [r"layer\s*7", r"\bl7\b", r"application\s*lay"]),
                ("HTTP flood / cache-busting via unique query strings",
                 [r"http\s*flood", r"cache.?bust", r"random.{0,20}(query|param|string)",
                  r"unik", r"unique.{0,20}(url|quer)"]),
                ("CDN bypassed because every request is a cache MISS hitting origin",
                 [r"cache\s*miss", r"hit\s*ratio", r"origin", r"uncach"]),
            ],
            points=8, threshold=2)
        self.free_question(
            "Q2 - You have 10 minutes before the database dies. List your "
            "IMMEDIATE mitigations at the edge (at least three concrete "
            "controls).",
            [
                ("rate limiting per IP/token at the edge",
                 [r"rate.?limit", r"throttl"]),
                ("WAF rule / managed bot protection",
                 [r"\bwaf\b", r"web\s+application\s+firewall", r"bot\s+(protect|manage)"]),
                ("challenge (CAPTCHA / JS challenge / proof-of-work)",
                 [r"captcha", r"challenge", r"turnstile", r"js\s*challenge"]),
                ("normalize/strip query strings or serve cached/static fallback",
                 [r"normaliz", r"strip.{0,15}quer", r"static\s+fallback",
                  r"cache\s+key", r"stale"]),
                ("block obvious ASNs/geos or upstream scrubbing",
                 [r"\bgeo", r"\basn\b", r"scrub", r"blackhol", r"blokk?er"]),
            ],
            points=10, threshold=3)
        self.free_question(
            "Q3 - A junior says 'just autoscale the origin x20'. Explain in "
            "2-3 sentences why that is the WRONG primary response.",
            [
                ("attacker scales cheaper than you / cost asymmetry",
                 [r"cost", r"pris", r"cheap", r"asymmetr", r"attacker.{0,40}scal"]),
                ("database/stateful tier is the bottleneck and does not autoscale",
                 [r"database", r"\bdb\b", r"stateful", r"connection",
                  r"bottleneck", r"flaskehals"]),
                ("mitigate at the edge, never absorb at origin",
                 [r"edge", r"upstream", r"absorb", r"origin"]),
            ],
            points=6, threshold=2)
        post_mortem("Cache-Busting L7 DDoS", """
        Volumetric attacks (L3/L4: UDP floods, SYN floods, amplification)
        try to saturate bandwidth and are largely absorbed by any anycast
        CDN. Application-layer (L7) attacks are smarter: each request is a
        legitimate-looking HTTP GET, cheap for the attacker, expensive for
        you, because '/api/search?q=zk83jf' forces a cache MISS, a backend
        invocation and often a database query. Your 91% cache hit ratio -
        the thing that made your capacity planning valid - collapses to 4%,
        and the origin receives more traffic than it was ever sized for.

        The defence hierarchy: (1) rate limiting per client fingerprint at
        the edge, (2) WAF managed rules + bot scoring, (3) interactive
        challenges that cost the attacker CPU, (4) cache-key normalization
        so junk parameters cannot bust the cache, (5) serving stale content
        ('stale-while-revalidate' / 'stale-if-error') so the origin can be
        firewalled off entirely. Autoscaling is a cost-transfer to you, not
        a mitigation - the attacker's botnet scales for free.

        Exam angle: tie this to availability in the CIA triad (ISO 27001),
        to capacity management, and to your SLA: a 99.9% availability SLA
        gives you ~43 minutes of downtime per month - one unmitigated L7
        flood spends a quarter of your error budget.
        """)

    # ---- Scenario 3: Split-brain -----------------------------------------

    def scenario_split_brain(self):
        section("INCIDENT 3: The cluster that crowned two kings", C.BRED)
        alert("Two-node HA database cluster. Heartbeat link cut by a "
              "switch firmware update. BOTH nodes promoted to PRIMARY.")
        code_block("""
node-a (rack 1): role=PRIMARY  accepting writes since 14:02
node-b (rack 2): role=PRIMARY  accepting writes since 14:02
replication:     BROKEN - timelines diverged
load balancer:   round-robin -> writes split ~50/50 across both
duration so far: 23 minutes of divergent writes (orders, payments!)
""", "cluster status")
        self.free_question(
            "Q1 - Name this failure condition and the root DESIGN flaw "
            "that made it possible.",
            [
                ("split-brain",
                 [r"split.?brain"]),
                ("no quorum / even number of nodes (2) cannot form majority",
                 [r"quorum", r"majority", r"flertal", r"even\s+number",
                  r"lige\s+antal", r"\b2\s+nodes?\b.{0,60}(cannot|kan ikke)"]),
                ("no fencing/STONITH or witness to arbitrate",
                 [r"fenc", r"stonith", r"witness", r"arbiter", r"tie.?break"]),
            ],
            points=8, threshold=2)
        self.free_question(
            "Q2 - You are Incident Commander. Sequence your IMMEDIATE "
            "actions. Wrong order loses customer payments.",
            [
                ("STOP the bleeding: fence/isolate one node or block writes "
                 "at the load balancer first",
                 [r"fence", r"stonith", r"stop.{0,25}writ", r"block.{0,20}writ",
                  r"isolat", r"read.?only", r"maintenance"]),
                ("choose ONE authoritative node (most/critical data, e.g. "
                 "by txn analysis)",
                 [r"authoritative", r"source\s+of\s+truth", r"v[æa]lg.{0,30}node",
                  r"pick\s+one", r"compare.{0,30}(data|timeline|wal)"]),
                ("reconcile/merge or replay diverged writes before resuming",
                 [r"reconcil", r"merge", r"replay", r"manual.{0,20}(fix|merge)",
                  r"diverge"]),
                ("rebuild the loser as a fresh replica from the winner",
                 [r"rebuild", r"re.?sync", r"basebackup", r"re.?clone",
                  r"replica"]),
            ],
            points=10, threshold=3)
        self.free_question(
            "Q3 - Redesign the cluster so split-brain is structurally "
            "impossible. Be specific.",
            [
                ("odd number of voters: 3 nodes, or 2 nodes + witness/quorum "
                 "device",
                 [r"\b3\b.{0,20}(node|voter)", r"odd", r"ulige", r"witness",
                  r"quorum\s+(device|disk)", r"arbiter", r"tie.?breaker"]),
                ("automatic fencing (STONITH) before promotion",
                 [r"stonith", r"fenc"]),
                ("redundant/independent heartbeat network",
                 [r"redundant.{0,25}(heartbeat|link|network)",
                  r"separate.{0,25}(heartbeat|network)", r"dual.{0,10}link"]),
                ("majority-based promotion (Raft/Paxos/Patroni-style consensus)",
                 [r"raft", r"paxos", r"patroni", r"consensus", r"etcd",
                  r"majority.{0,20}(vote|promot)"]),
            ],
            points=8, threshold=2)
        post_mortem("Split-Brain & Quorum", """
        Split-brain is what happens when an HA cluster confuses 'I cannot
        SEE my peer' with 'my peer is DEAD'. With two nodes there is no way
        to tell the difference: each node sees exactly the same evidence (a
        dead heartbeat) and each concludes it must take over. Both promote,
        both accept writes, and you now have two divergent realities for
        the same bank balance. Merging diverged payment data is a manual,
        lawyer-adjacent process - prevention is the only sane strategy.

        The mathematics of the fix is quorum: a node may only act as
        primary while it can communicate with a strict MAJORITY of voters.
        With 3 voters, a partition splits 2-vs-1; the side with 2 keeps
        running, the side with 1 demotes itself. With 2 voters a partition
        splits 1-vs-1 and NEITHER side has a majority - which is why
        2-node clusters need a witness (a tiny third voter) or a quorum
        disk. The second mechanism is fencing/STONITH ('Shoot The Other
        Node In The Head'): before promotion, power off or isolate the old
        primary via an out-of-band channel, so even a confused node is
        physically unable to write.

        Exam angle: this is THE high-availability question. Quorum,
        fencing, odd voter counts, and consensus algorithms (Raft) - the
        ability to derive 'why 3 nodes and not 2' on a whiteboard is the
        difference between a 7 and a 12.
        """)

    # ---- Scenario 4: Backup & DR design ----------------------------------

    def scenario_bdr(self):
        section("DESIGN TASK 4: Backup & Disaster Recovery strategy", C.BRED)
        wrap("""
        The board gives you the business numbers and expects YOU to derive
        the technical targets. NordCommerce: revenue 50.000 kr/hour. The
        board accepts a maximum of 200.000 kr direct loss per major
        incident. Order data older than 15 minutes can be reconstructed
        from the payment provider; anything younger is lost forever.
        """, indent=2)
        self.numeric_question(
            "Q1 - Derive the maximum acceptable RTO in HOURS from the "
            "revenue numbers",
            lambda v: 0 < v <= 4, points=5, unit="hours")
        info("RTO (Recovery Time Objective): max acceptable downtime. "
             "200.000 kr / 50.000 kr per hour = 4 hours.")
        self.numeric_question(
            "Q2 - Derive the maximum acceptable RPO in MINUTES",
            lambda v: 0 < v <= 15, points=5, unit="minutes")
        info("RPO (Recovery Point Objective): max acceptable data loss "
             "measured in time = 15 minutes.")
        self.free_question(
            "Q3 - Censor follow-up (JHB-pensum): 'I naevner RPO og RTO - "
            "men hvad er MAO, og hvordan haenger de tre sammen paa "
            "tidslinjen fra seneste backup til reetablering?'",
            [
                ("MAO = Maximum Acceptable Outage - den samlede maksimale "
                 "nedetid der kan tolereres",
                 [r"maximum\s+acceptable\s+outage", r"samlede?.{0,40}nedetid",
                  r"maks.{0,30}(outage|nedetid)", r"total.{0,30}(downtime|outage)"]),
                ("relationen: RPO + RTO <= MAO",
                 [r"rpo\s*\+\s*rto", r"rto\s*\+\s*rpo", r"<=?\s*mao",
                  r"mao\s*>=", r"summen", r"tilsammen"]),
                ("defineres i BIA (Business Impact Analysis) / hoej "
                 "kritikalitet = lavere RPO/RTO",
                 [r"\bbia\b", r"business\s+impact", r"kritikalitet",
                  r"kritiske\s+systemer"]),
            ],
            points=6, threshold=2)
        self.free_question(
            "Q4 - Pick a DR architecture that meets RTO<=4h / RPO<=15min on "
            "a mid-size budget, and explain why nightly backups alone FAIL "
            "and why active-active multi-site is OVERKILL here.",
            [
                ("warm standby / pilot light in second site or cloud region",
                 [r"warm\s+standby", r"pilot\s+light", r"standby", r"secondary\s+(site|region)"]),
                ("continuous replication / WAL streaming / log shipping for RPO",
                 [r"\bwal\b", r"log\s+shipping", r"stream", r"continuous\s+replicat",
                  r"replikering"]),
                ("nightly backups violate RPO (up to 24h data loss)",
                 [r"nightly.{0,80}(24|rpo|loss|tab)", r"24\s*(h|hour|timer)",
                  r"natlig.{0,60}(rpo|tab)"]),
                ("active-active costs/complexity not justified by 4h RTO",
                 [r"active.?active.{0,120}(cost|complex|overkill|dyr|expens)",
                  r"(cost|dyr|expens|complex).{0,120}active.?active"]),
            ],
            points=10, threshold=2)
        self.free_question(
            "Q5 - State the 3-2-1 backup rule and add the modern extension "
            "that defeats ransomware.",
            [
                ("3 copies of the data",
                 [r"\b3\b.{0,30}(cop|kopi)", r"three\s+cop"]),
                ("2 different media/technologies",
                 [r"\b2\b.{0,40}(media|medier|technolog|typer)"]),
                ("1 copy off-site",
                 [r"\b1\b.{0,30}off.?site", r"off.?site", r"offsite",
                  r"anden\s+lokation"]),
                ("immutable/air-gapped copy + tested restores",
                 [r"immutab", r"air.?gap", r"worm", r"object\s+lock",
                  r"test.{0,25}(restore|gendan)"]),
            ],
            points=8, threshold=3)
        post_mortem("RTO/RPO & DR Economics", """
        RTO and RPO are BUSINESS numbers wearing technical clothes. RTO is
        derived from cost-of-downtime; RPO from cost-of-data-loss. The exam
        board loves candidates who derive the targets from kroner instead
        of guessing 'uh, an hour?'. Once derived, the targets dictate the
        architecture tier: RPO of days = nightly backups; RPO of minutes =
        continuous replication (WAL streaming/log shipping); RPO of zero =
        synchronous replication, which costs you write latency on every
        single transaction (CAP theorem sends its regards).

        Same ladder for RTO: days = restore from backup to new hardware;
        hours = warm standby you promote; minutes = hot standby with
        automatic failover; ~zero = active-active, which roughly doubles
        infrastructure cost and forces you to solve data conflicts (see
        the split-brain incident you just survived).

        The 3-2-1 rule (3 copies, 2 media, 1 off-site) predates ransomware.
        Modern attackers encrypt your backups FIRST, so the extension is
        3-2-1-1-0: one copy immutable or air-gapped, and zero errors on
        restore tests. An untested backup is a hypothesis, not a backup -
        say that sentence to the censor and watch the nodding.
        """)

    # ---- Oral exam board ---------------------------------------------------

    def oral_exam_board(self):
        section("THE ORAL EXAM BOARD - EK/KEA IT-Drift pensum", C.BMAGENTA)
        wrap("""
        To censorer (kursusansvarlige: JHB og Oskar Tuska). Spoergsmaalene
        foelger dit faktiske pensum: ITIL Service Operations, Change
        Management/DevOps/PRINCE2 (M10), IT-Security 1+2 (M08/M09),
        OS & Devices (AD/GPO/MDM), virtualisering, netvaerk, backup,
        cloud, SLA og CMMI. Svar i hele saetninger - dansk eller engelsk.
        """, indent=2)
        board = [
            # 1 --- ITIL grundmodel -------------------------------------
            ("Censor 1: 'Hvad er ITIL, og forklar Service Value Chain. "
             "Naevn derefter mindst tre af de 7 Guiding Principles.'",
             [
                 ("ITIL = rammevaerk for ITSM, leverandoer-uafhaengigt "
                  "(processer/procedurer/best practice)",
                  [r"itsm", r"service\s*management", r"rammev", r"framework",
                   r"best\s*practice", r"infrastructure\s+library"]),
                 ("Plan", [r"\bplan\b"]),
                 ("Engage", [r"engage"]),
                 ("Design & Transition", [r"design", r"transition"]),
                 ("Obtain/Build", [r"obtain", r"build"]),
                 ("Deliver & Support + Improve",
                  [r"deliver", r"support", r"improve", r"forbedr"]),
                 ("guiding principles (focus on value, start where you are, "
                  "iterate, collaborate, holistic, keep it simple, "
                  "optimize/automate)",
                  [r"focus\s+on\s+value", r"start\s+where\s+you\s+are",
                   r"iterat", r"collaborat", r"holisti", r"keep\s+it\s+simple",
                   r"optimi[sz]e\s+and\s+automate", r"automat"]),
             ], 8, 4),
            # 2 --- Incident vs Problem ---------------------------------
            ("Censor 2: 'En server er nede - og det er femte gang denne "
             "maaned. Forklar med ITIL-begreber forskellen paa, hvad "
             "Incident Management og Problem Management goer ved det.'",
             [
                 ("IM = genopret service SAA HURTIGT som muligt",
                  [r"genopret", r"restore", r"hurtig", r"as\s+fast"]),
                 ("IM bruger workarounds og kraever INGEN godkendelse",
                  [r"workaround", r"midlertidig", r"ingen\s+godkend",
                   r"no\s+approval", r"handle\s+med\s+det\s+samme"]),
                 ("PM = find og fjern ROOT CAUSE (rodaarsagen)",
                  [r"root\s*cause", r"rod[aå]rsag", r"problem\s+management"]),
                 ("5-gange-reglen / reactive vs proactive PM",
                  [r"\b5\b.{0,30}(gang|times)", r"reactive", r"proactive",
                   r"reaktiv", r"proaktiv", r"gentag"]),
             ], 8, 3),
            # 3 --- Servicedesk & escalation -----------------------------
            ("Censor 1: 'I skal bygge et servicecenter op. Beskriv "
             "servicedeskens opgaver, escalation flow (linje 0-3) og "
             "hvad Priority 1 - Critical kraever.'",
             [
                 ("log, kategoriser og prioriter alle henvendelser",
                  [r"log", r"kategoris", r"prioriter"]),
                 ("Linje 0 = self-help (FAQ, wiki, chatbot)",
                  [r"linje\s*0", r"self.?help", r"faq", r"wiki", r"chatbot"]),
                 ("Linje 1 = service desk loeser simple/kendte problemer",
                  [r"linje\s*1", r"service\s*desk", r"f[oø]rste.?linje",
                   r"1st\s*line"]),
                 ("Linje 2-3 = eksperter, nye/ukendte problemer",
                  [r"linje\s*2", r"2nd", r"3rd", r"ekspert", r"specialist"]),
                 ("P1 Critical: system down, immediate response, "
                  "resolution ~1 time, 2nd/3rd level",
                  [r"immediate", r"straks", r"1\s*(time|hour)",
                   r"system\s+down", r"critical"]),
             ], 8, 3),
            # 4 --- Change Management -----------------------------------
            ("Censor 2: 'Jeres team vil migrere oekonomisystemet fra "
             "fysisk til virtuel server. Hvilken change-type er det, "
             "hvem godkender, og hvad siger de 7 R'er I skal afklare?'",
             [
                 ("Normal change -> CAB-godkendelse (assessment, "
                  "authorization)",
                  [r"normal\s+change", r"\bcab\b", r"change\s+advisory"]),
                 ("kender de andre typer: Standard (pre-godkendt, lav "
                  "risiko) og Emergency (ECAB)",
                  [r"standard\s+change", r"pre.?godkendt", r"pre.?author",
                   r"emergency", r"ecab"]),
                 ("RFC + back-out/rollback-plan + test foer implementering",
                  [r"\brfc\b", r"request\s+for\s+change", r"back.?out",
                   r"rollback", r"testmilj", r"n[oø]dplan"]),
                 ("7 R'er: Raised, Reason, Return, Risks, Resources, "
                  "Responsible, Relationship (naevn flere)",
                  [r"raised", r"reason", r"return", r"risks?", r"resources",
                   r"responsible", r"relationship", r"7\s*r"]),
             ], 8, 3),
            # 5 --- SLA design (studieordning: 'udarbejde en SLA') -------
            ("Censor 1: 'Studieordningen siger, du skal kunne UDARBEJDE "
             "en SLA. Skitser indholdet af en SLA for vores servicedesk "
             "- og forklar hvordan OLA'er og Underpinning Contracts "
             "skal understoette den.'",
             [
                 ("scope: hvilke services/systemer er daekket",
                  [r"scope", r"services?\b", r"omfang", r"hvilke\s+system"]),
                 ("maalbare maal: oppetid (fx 99,9%) + response/resolution "
                  "tider pr. prioritet",
                  [r"99[.,]9", r"oppetid", r"uptime", r"availab",
                   r"response\s*time", r"resolution", r"reaktionstid",
                   r"prioritet"]),
                 ("maaling og rapportering (KPI'er, hvordan/hvornaar maales)",
                  [r"kpi", r"m[aå]l(ing|es)", r"rapport", r"metric",
                   r"monitor"]),
                 ("konsekvenser/eskalation ved brud + ansvar/parter",
                  [r"sanktion", r"konsekvens", r"eskaler", r"penalty",
                   r"bod", r"ansvar", r"parter"]),
                 ("SLA = kunde; OLA = interne teams; UC = ekstern "
                  "leverandoer - og de skal vaere SKRAPPERE end SLA'en",
                  [r"ola", r"underpinning", r"\buc\b", r"intern", r"leverand",
                   r"skrapper", r"strammere", r"underst[oø]t"]),
             ], 10, 3),
            # 6 --- iAAA -------------------------------------------------
            ("Censor 2 (JHB-klassiker): 'iAAA er noeglen til det hele. "
             "Forklar de fire begreber, og hvorfor useradministration er "
             "hjoernestenen - inkl. hvad der skal ske ved on- og "
             "offboarding.'",
             [
                 ("Identification = du haevder hvem du er (brugernavn)",
                  [r"identifi", r"h[aæ]vder", r"brugernavn", r"claim"]),
                 ("Authentication = systemet verificerer (password, MFA, "
                  "biometri)",
                  [r"authenti", r"verific", r"password", r"mfa", r"biometri"]),
                 ("Authorization = adgang tildeles (RBAC/ACL/PoLP)",
                  [r"authori[sz]", r"rbac", r"acl", r"least\s+privilege",
                   r"polp", r"rettighed"]),
                 ("Accountability = logging/audit - du staar til ansvar",
                  [r"accountab", r"logg?ing", r"audit", r"siem", r"ansvar"]),
                 ("klare procedurer: onboarding, rolleskift, offboarding "
                  "(deaktiver foerst, slet senere; keycards/hardware)",
                  [r"onboard", r"offboard", r"deaktiver", r"disable",
                   r"lifecycle", r"livscyklus", r"keycard", r"rolleskift"]),
             ], 8, 3),
            # 7 --- Risikoformler ----------------------------------------
            ("Censor 1: 'Skriv risikoformlen paa tavlen - fra BAADE "
             "ledelsens og analytikerens perspektiv. Forklar "
             "sammenhaengen, og naevn de fire maader at behandle en "
             "risiko paa.'",
             [
                 ("CEO: RISK = Likelihood x Consequence",
                  [r"likelihood\s*[x*×]\s*consequence",
                   r"sandsynlighed\s*[x*×]\s*konsekvens"]),
                 ("Analytiker: RISK = Threat x Vulnerability x Impact",
                  [r"threat\s*[x*×]\s*vulnerab", r"trussel\s*[x*×]\s*s[aå]rbar"]),
                 ("sammenhaengen: Threat x Vulnerability = Likelihood",
                  [r"(threat|trussel).{0,40}=\s*likelihood",
                   r"udg[oø]r\s+likelihood", r"er\s+sandsynligheden"]),
                 ("risk matrix / score styrer handling (Extreme/High "
                  "kraever handling)",
                  [r"matrix", r"score", r"extreme", r"1.?5\s*[x*×]\s*1.?5",
                   r"gr[oø]n", r"r[oø]d"]),
                 ("4 behandlinger: Mitigate, Accept, Transfer, Avoid",
                  [r"mitigat", r"accept", r"transfer", r"avoid", r"reducer",
                   r"overf[oø]r", r"undg[aå]"]),
             ], 8, 3),
            # 8 --- ISO 27001 / ISMS ------------------------------------
            ("Censor 2: 'Forklar forholdet mellem ISO 27001, et ISMS og "
             "SoA'en. Hvad styrer hvilke Annex A-kontroller man vaelger, "
             "og hvordan er PDCA bygget ind i standarden?'",
             [
                 ("ISMS = det samlede system af politikker/processer/"
                  "kontroller; 27001 = standarden/kravene til det",
                  [r"isms", r"management\s+system", r"ledelsessystem",
                   r"politikker.{0,60}processer"]),
                 ("SoA = Statement of Applicability: valgte/fravalgte "
                  "kontroller og HVORFOR",
                  [r"soa", r"statement\s+of\s+applicability", r"fravalg"]),
                 ("RISIKOVURDERINGEN styrer kontrolvalget",
                  [r"risikovurdering", r"risk\s+assessment",
                   r"risiko.{0,40}(styrer|v[aæ]lger|driver)"]),
                 ("Annex A: 93 kontroller, 4 temaer (org/menneske/fysisk/"
                  "teknologisk)",
                  [r"93", r"annex\s*a", r"4\s+temaer", r"organisatorisk",
                   r"teknologisk"]),
                 ("PDCA i HLS: kap 4-6 Plan, 7-8 Do, 9 Check, 10 Act",
                  [r"pdca", r"plan.?do.?check.?act", r"kap(itel)?\s*4",
                   r"hls", r"high\s+level\s+structure"]),
             ], 8, 3),
            # 9 --- Certificering & audit --------------------------------
            ("Censor 1: 'Virksomheden vil ISO 27001-certificeres. "
             "Forklar certificeringsauditten - Stage 1 vs Stage 2 - "
             "hvad der sker bagefter, og forskellen paa minor og major "
             "non-conformity.'",
             [
                 ("Stage 1 = dokumentationsgennemgang (har I politikkerne?)",
                  [r"stage\s*1.{0,80}(dokument|paper|politik)",
                   r"dokument.{0,60}stage\s*1"]),
                 ("Stage 2 = feltevaluering (virker det i PRAKSIS?)",
                  [r"stage\s*2.{0,80}(praksis|felt|practice)",
                   r"praksis.{0,60}stage\s*2"]),
                 ("aarlige surveillance audits + re-certificering hvert "
                  "3. aar",
                  [r"surveillance", r"3\.?\s*[aå]r", r"re.?certificer",
                   r"[aå]rlig"]),
                 ("minor = isoleret fejl; major = systemisk svigt, kan "
                  "blokere certificering",
                  [r"minor.{0,80}(isoler|enkelt)", r"major.{0,80}(system|bloker)",
                   r"non.?conformit"]),
             ], 8, 2),
            # 10 --- GDPR ------------------------------------------------
            ("Censor 2: 'En medarbejder finder et print med persondata "
             "ved kopimaskinen efter en ekstern tekniker. Hvad goer I - "
             "og hvilke GDPR-begreber er i spil? (JHB's oevelse)'",
             [
                 ("sikr dokumentet straks + rapporter til leder/DPO",
                  [r"sikr", r"beskyt", r"fjern", r"rapport", r"dpo",
                   r"leder", r"tild[aæ]k"]),
                 ("72-timers reglen: anmeld databrud til Datatilsynet",
                  [r"72", r"datatilsynet", r"anmeld"]),
                 ("forebyg: Clear Desk Policy, besoegsregler, "
                  "adgangskontrol til printere",
                  [r"clear\s*desk", r"bes[oø]gs", r"printer", r"politik",
                   r"procedure"]),
                 ("kender flere GDPR-begreber: DSAR, retten til at blive "
                  "glemt, privacy by design, databehandleraftale",
                  [r"dsar", r"blive\s+glemt", r"forgotten", r"privacy\s+by\s+design",
                   r"databehandler", r"data\s+processing\s+agreement",
                   r"minimization"]),
             ], 8, 3),
            # 11 --- Backup-agent / SAN vs NAS ---------------------------
            ("Censor 1: 'Forklar backup-agentens rolle i et setup med "
             "MS SQL Server, Backup Manager og Storage Server - og "
             "forskellen paa SAN og NAS. Hvad er 3-2-1, og hvad goer "
             "en backup til en RIGTIG backup?'",
             [
                 ("agenten laeser data fra serveren, pakker/krypterer og "
                  "sender til storage; styres af Backup Manager",
                  [r"agent.{0,120}(l[aæ]ser|henter|sender|krypter|pakker)",
                   r"backup\s*manager", r"storage\s*server"]),
                 ("inkrementel backup - kun aendringer siden sidst",
                  [r"inkrement", r"increment", r"kun.{0,30}[aæ]ndr",
                   r"changed\s+(files|data)"]),
                 ("SAN = block-level, dedikeret storage-netvaerk; "
                  "NAS = file-level",
                  [r"san.{0,80}block", r"block.{0,60}san", r"nas.{0,80}file",
                   r"file.{0,60}nas", r"dedikeret\s+netv"]),
                 ("3-2-1: 3 kopier, 2 medier, 1 offsite",
                  [r"3\s*kopi", r"2\s*(medier|forskellige)", r"1\s*off.?site",
                   r"3.?2.?1"]),
                 ("TEST RESTORE - en utestet backup er ikke en backup",
                  [r"test.{0,30}(restore|gendan)", r"restore.{0,30}test",
                   r"utestet", r"ikke\s+en\s+backup"]),
             ], 8, 3),
            # 12 --- CMMI strategisk case --------------------------------
            ("Censor 2: 'Studieordningens strategiske kompetencemaal: "
             "vurder modenhedsniveauet. Hos os loeses alle incidents af "
             "EN heltemodig admin uden dokumenterede processer. Placer "
             "os paa CMMI-skalaen, naevn alle 5 niveauer, og laeg en "
             "plan for at naa Level 3. Maa man springe niveauer over?'",
             [
                 ("Level 1 Initial: ad hoc, reaktiv, hero-kultur",
                  [r"(level|niveau)\s*1", r"initial", r"ad\s*hoc", r"helt",
                   r"hero", r"reaktiv"]),
                 ("naevner niveauerne: Managed, Defined, Quantitatively "
                  "Managed, Optimizing",
                  [r"managed", r"defined", r"quantitat", r"kvantitat",
                   r"optimi[sz]"]),
                 ("Level 3 = processer defineret paa ORGANISATIONSNIVEAU "
                  "(alle foelger samme processer)",
                  [r"organisationsniveau", r"org.{0,20}wide", r"samme\s+(regler|processer)",
                   r"defineret.{0,40}organisation"]),
                 ("man maa IKKE springe niveauer over - hvert niveau er "
                  "fundament for det naeste",
                  [r"ikke.{0,30}spring", r"cannot\s+skip", r"fundament",
                   r"trin\s+for\s+trin"]),
                 ("plan: dokumenter processer, ITIL som ramme, maal med "
                  "metrics (vejen mod 4), staged vs continuous",
                  [r"dokumenter", r"itil", r"metric", r"m[aå]l\b", r"staged",
                   r"continuous", r"procesomr"]),
             ], 10, 3),
            # 13 --- Virtualisering --------------------------------------
            ("Censor 1: 'Type 1 vs Type 2 hypervisor - forklar "
             "forskellen med eksempler. Hvilke fordele giver "
             "virtualisering driften, hvad er noisy neighbor, og "
             "hvornaar vaelger man stadig en fysisk server?'",
             [
                 ("Type 1 = bare-metal, direkte paa hardware (ESXi, "
                  "Hyper-V, KVM) - enterprise/datacenter",
                  [r"type\s*1.{0,120}(bare.?metal|direkte|hardware|esxi|hyper.?v|kvm)",
                   r"bare.?metal"]),
                 ("Type 2 = hosted, oven paa et OS (VirtualBox, VMware "
                  "Workstation) - test/udvikling",
                  [r"type\s*2.{0,120}(hosted|oven|os|virtualbox|workstation)",
                   r"hosted"]),
                 ("fordele: konsolidering/ressourceudnyttelse, snapshots, "
                  "hurtig skalering, failover/HA",
                  [r"konsolider", r"ressourceudnytt", r"snapshot",
                   r"skaler", r"failover", r"isolation"]),
                 ("noisy neighbor + hypervisor-overhead som ulemper",
                  [r"noisy\s+neighbor", r"overhead", r"deler?\s+ressourcer"]),
                 ("fysisk ved: HPC, kaempe databaser, hardware-krav, "
                  "compliance-krav om fysisk isolation",
                  [r"hpc", r"high.?performance", r"stor.{0,20}(database|sql)",
                   r"complian", r"gpu", r"fysisk\s+isolation"]),
             ], 8, 3),
            # 14 --- ROI -------------------------------------------------
            ("Censor 2: 'I vil konsolidere 10 fysiske servere til en "
             "virtualiseret loesning. Investering 200.000 kr, aarlig "
             "besparelse 120.000 kr. Skriv ROI-formlen, regn ROI efter "
             "2 aar, og forklar hvordan ROI og Change Management "
             "spiller sammen i sagen til ledelsen.'",
             [
                 ("ROI-formlen: (gevinst - investering) / investering "
                  "x 100",
                  [r"gevinst\s*-\s*invest", r"\(.{0,30}-.{0,30}\)\s*/\s*invest",
                   r"return\s+on\s+investment"]),
                 ("regnestykket: 240.000 - 200.000 = 40.000 -> ROI = 20% "
                  "(break-even under 2 aar)",
                  [r"40\.?000", r"20\s*%", r"break.?even", r"240"]),
                 ("ROI overbeviser ledelsen (business case); Change "
                  "Management sikrer kontrolleret gennemfoersel",
                  [r"roi.{0,120}(ledelse|business\s*case|godkend|penge)",
                   r"change\s*management.{0,120}(kontrol|kaos|risiko|back.?out)"]),
             ], 8, 2),
            # 15 --- Cloud -----------------------------------------------
            ("Censor 1: 'Forklar IaaS, PaaS og SaaS med eksempler, "
             "forskellen paa public/private/hybrid cloud, og hvad "
             "Shared Responsibility Model betyder for jeres ansvar.'",
             [
                 ("IaaS = raa infrastruktur/VM'er (lejer hardware)",
                  [r"iaas.{0,80}(infrastruktur|hardware|vm|virtuelle)",
                   r"infrastructure\s+as\s+a\s+service"]),
                 ("PaaS = platform/miljoe til at udvikle apps",
                  [r"paas.{0,80}(platform|udvikl|milj)",
                   r"platform\s+as\s+a\s+service"]),
                 ("SaaS = faerdigt program via browser (M365, e-conomic)",
                  [r"saas.{0,80}(f[aæ]rdig|program|browser|abonnement|365)",
                   r"software\s+as\s+a\s+service"]),
                 ("public/private/hybrid + elasticitet/on-demand",
                  [r"public", r"private", r"hybrid", r"elastic",
                   r"on.?demand", r"skalerbar"]),
                 ("Shared Responsibility: provider vs kunde - ansvaret "
                  "deles forskelligt pr. lag",
                  [r"shared\s+responsibility", r"delt\s+ansvar",
                   r"provider.{0,60}kunde", r"udbyder.{0,60}kunde"]),
             ], 8, 3),
            # 16 --- DevOps ----------------------------------------------
            ("Censor 2: 'Hvorfor opstaar der siloer mellem Dev og Ops - "
             "og hvad er forskellen paa CI, Continuous Delivery og "
             "Continuous Deployment? Naevn ogsaa IaC og MTTR.'",
             [
                 ("silo-aarsag: Dev beloennes for features, Ops straffes "
                  "for nedetid (inventors vs mechanics)",
                  [r"bel[oø]nn.{0,60}features", r"straffes.{0,60}nedetid",
                   r"inventors", r"mechanics", r"modsatrettede"]),
                 ("CI = automatisk test + integration (stopper der)",
                  [r"\bci\b.{0,120}(auto|test|integr)",
                   r"continuous\s+integration"]),
                 ("Continuous Delivery = altid deployerbar, men deploy "
                  "kraever MANUEL godkendelse",
                  [r"delivery.{0,140}(manuel|manual|menneske|godkend)",
                   r"(manuel|manual).{0,80}deploy"]),
                 ("Continuous Deployment = fuldt automatisk til "
                  "produktion ved groen test",
                  [r"deployment.{0,140}(auto|fuldt)", r"fuldt\s+auto",
                   r"direkte\s+til\s+produktion"]),
                 ("IaC = programmerbar infrastruktur; MTTR = Mean Time "
                  "to Recovery forbedres",
                  [r"infrastructure\s+as\s+code", r"\biac\b", r"mttr",
                   r"mean\s+time\s+to\s+recover", r"programm?erbar"]),
             ], 8, 3),
            # 17 --- PRINCE2 ---------------------------------------------
            ("Censor 1: 'Hvad staar PRINCE2 for? Naevn mindst tre af de "
             "7 principper og forklar saerligt Manage by Exception og "
             "Continued Business Justification. Hvilke management "
             "products er vigtigst?'",
             [
                 ("PRojects IN Controlled Environments",
                  [r"controlled\s+environments", r"kontrollerede\s+milj"]),
                 ("Continued Business Justification: projektet skal "
                  "ALTID kunne retfaerdiggoeres (ellers stop)",
                  [r"business\s+justification", r"retf[aæ]rdigg",
                   r"forretningsm[aæ]ssig"]),
                 ("Manage by Exception: styregruppen involveres kun ved "
                  "(potentielle) problemer/afvigelser",
                  [r"exception.{0,120}(kun|only|problem|afvig)",
                   r"styregrupp.{0,80}(kun|problem)"]),
                 ("flere principper: Learn from Experience, Roles & "
                  "Responsibilities, Manage by Stages, Focus on "
                  "Products, Tailor",
                  [r"learn\s+from\s+experience", r"roles", r"stages",
                   r"focus\s+on\s+products", r"tailor"]),
                 ("management products: Business Case, Risk Register, "
                  "Lessons Log, Project Brief",
                  [r"business\s+case", r"risk\s+register", r"lessons\s+log",
                   r"project\s+brief", r"daily\s+log"]),
             ], 8, 3),
            # 18 --- Netvaerk --------------------------------------------
            ("Censor 2: 'Tegn netvaerket for jeres portfolio-virksomhed "
             "(500 ansatte, 7 afdelinger): Hvorfor VLAN-segmentering "
             "mod ransomware? Hvilke OSI-lag arbejder hub, switch og "
             "router paa - og hvad laver firewall, IDS/IPS og DMZ?'",
             [
                 ("VLAN-segmentering begraenser spredning/skadesomfang "
                  "(HR, Finance, Guest, Server adskilt)",
                  [r"vlan", r"segment", r"begr[aæ]ns.{0,40}(spredning|angreb|skade)",
                   r"adskil"]),
                 ("hub = lag 1 (dum, alle porte); switch = lag 2 "
                  "(MAC-adresser); router = lag 3 (IP, mellem netvaerk)",
                  [r"hub.{0,60}(lag|layer)\s*1", r"switch.{0,60}(lag|layer)\s*2",
                   r"router.{0,60}(lag|layer)\s*3", r"mac.?adress"]),
                 ("firewall filtrerer trafik efter regler (default deny)",
                  [r"firewall.{0,80}(filtrer|regler|deny|bloker)"]),
                 ("IDS opdager / IPS blokerer mistaenkelig trafik; "
                  "honeypot som lokkemiddel",
                  [r"ids", r"ips", r"intrusion", r"honeypot", r"monitorer"]),
                 ("DMZ isolerer offentligt eksponerede services fra "
                  "internt net; subnet/gateway-forstaaelse",
                  [r"dmz", r"demilitari", r"subnet", r"gateway"]),
             ], 8, 3),
            # 19 --- AD / GPO / MDM --------------------------------------
            ("Censor 1: 'En ny medarbejder starter mandag i en "
             "organisation med 500 ansatte. Forklar hele onboarding-"
             "flowet med AD, GPO og MDM - og forskellen paa MDM og MAM "
             "i et BYOD-scenarie.'",
             [
                 ("AD-konto oprettes (PowerShell New-ADUser / CSV-bulk) "
                  "i den rette OU",
                  [r"new-aduser", r"powershell", r"csv", r"\bou\b",
                   r"active\s*directory", r"\bad\b.{0,40}konto"]),
                 ("GPO pusher konfiguration (password-politik, firewall, "
                  "software) til OU'ens maskiner",
                  [r"gpo", r"group\s*policy", r"password.?politik",
                   r"push.{0,40}konfig"]),
                 ("MDM (fx Intune) enroller enheder via Azure AD og "
                  "haandhaever compliance",
                  [r"mdm", r"intune", r"enroll", r"complian"]),
                 ("PoLP/RBAC: kun noedvendige rettigheder via grupper",
                  [r"polp", r"least\s+privilege", r"rbac", r"grupper",
                   r"n[oø]dvendige\s+rettigheder"]),
                 ("MDM = hele enheden (firmaejet); MAM = kun firma-apps/"
                  "data - remote wipe rammer kun firmadelen (BYOD)",
                  [r"mam", r"byod", r"remote\s*wipe", r"container",
                   r"hele\s+enheden", r"kun\s+firma"]),
             ], 8, 3),
            # 20 --- Kryptering & 2FA ------------------------------------
            ("Censor 2, sidste spoergsmaal: 'Symmetrisk vs asymmetrisk "
             "kryptering - og hvorfor HASHER vi passwords i stedet for "
             "at kryptere dem? Hvad loeser Diffie-Hellman, og hvad er "
             "de tre elementer i 2FA/fysisk adgangskontrol?'",
             [
                 ("symmetrisk = en delt noegle (hurtig, kraever sikker "
                  "udveksling); asymmetrisk = public/private key (HTTPS)",
                  [r"symmetrisk.{0,120}(en|delt|samme)\s*n[oø]gle",
                   r"asymmetrisk.{0,120}(public|private|offentlig|privat)",
                   r"https"]),
                 ("hashing er ENVEJS - kan ikke gendannes; ved login "
                  "sammenlignes hash af input",
                  [r"envejs", r"one.?way", r"ikke\s+gendan", r"sammenlign.{0,40}hash",
                   r"checksum", r"fingeraftryk"]),
                 ("Diffie-Hellman: sikker noegleudveksling over usikker "
                  "kanal (TLS/SSH/IPsec) - diskret logaritme",
                  [r"diffie", r"n[oø]gleudveksling", r"usikker\s+(kanal|forbindelse)",
                   r"diskret\s+logaritme", r"key\s+exchange"]),
                 ("2FA = kombination af Something you HAVE / ARE / KNOW",
                  [r"have", r"\bare\b", r"know", r"noget\s+du\s+(har|er|ved)",
                   r"to.?faktor", r"2fa", r"mfa"]),
             ], 8, 3),
        ]
        for i, (question, groups, pts, thresh) in enumerate(board, 1):
            print()
            print(f"{C.BMAGENTA}{C.BOLD}  BOARD QUESTION {i}/{len(board)}{C.RESET}")
            self.free_question(question, groups, pts, thresh)
        post_mortem("Facing the Board", """
        Boardet daekker nu hele EK/KEA-pensum: ITIL Service Operations,
        Change/DevOps/PRINCE2, IT-Security 1+2 (JHB), OS & Devices,
        virtualisering, ROI, cloud, netvaerk, backup, SLA og CMMI.
        Studieordningens kompetencemaal er indbygget: SLA-spoergsmaalet
        traener 'udarbejde en SLA' (faerdighed), CMMI-casen traener
        'selvstaendigt vurdere og videreudvikle modenhedsniveauet'
        (strategisk kompetence).

        Mønsteret der giver 12 er uaendret: (1) definer begrebet i en
        saetning, (2) placer det i rammevaerket, (3) giv et konkret
        driftseksempel - gerne fra dit portfolio-projekt (Matrix Minds,
        500 ansatte, 7 afdelinger) eller fra incidents i dette spil,
        (4) naevn selv begraensningen eller trade-off'et. Censorer
        opgraderer kandidater, der frivilligt naevner begraensningen.

        Bind emnerne sammen som JHB goer det: iAAA -> CIA-triaden ->
        risikoanalysen -> Annex A-kontroller -> SoA -> audit. En
        kandidat, der kan gaa fra 'hvem maa logge ind' til 'hvordan
        beviser vi det over for en auditor' i EN sammenhaengende
        fortaelling, har vist hele governance-kaeden - og det er
        praecis dér, 7-12-graensen ligger.
        """)


# ---------------------------------------------------------------------------
# 5. MODULE 2 - NEXT.JS FRONTEND
# ---------------------------------------------------------------------------


class FrontendService(ServiceModule):
    name = "svc-frontend"
    title = "NEXT.JS - SSR, Web Vitals, ISR & Hydration"

    def run(self, payload):
        banner("MODULE 2 - NEXT.JS FRONTEND",
               "Internship focus. Production debugging at scale.", C.BBLUE)
        wrap("""
        You join 'NordShop', a Next.js storefront with 50.000 product
        pages and ~2M visits/day, the week before a campaign launch.
        """, indent=2)
        pause()
        self.scenario_memory_leak()
        self.scenario_web_vitals()
        self.scenario_isr()
        self.scenario_hydration()
        banner("MODULE 2 COMPLETE",
               f"Frontend score: {self.points}/{self.max_points}", C.BBLUE)

    def scenario_memory_leak(self):
        section("CASE 1: The SSR pod that eats 4GB and dies", C.BBLUE)
        alert("Kubernetes: next-ssr pods OOMKilled every ~40 minutes "
              "under load. RSS climbs linearly, never plateaus.")
        code_block("""
// lib/productCache.js   (imported by the SSR page)
const cache = new Map();

export async function getProductData(id, locale) {
  const key = `${id}:${locale}`;
  if (!cache.has(key)) {
    const data = await fetchProductFromCMS(id, locale);  // ~120 KB object
    cache.set(key, data);
  }
  return cache.get(key);
}
""", "javascript")
        info("50.000 products x 12 locales. Node process lives for days.")
        self.free_question(
            "Q1 - Explain the exact mechanism of the leak. Why does this "
            "code behave fine in `next dev` but kill production pods?",
            [
                ("module-scope Map lives for the entire process lifetime "
                 "(module is evaluated once and cached)",
                 [r"module.{0,30}(scope|level)", r"top.?level", r"global",
                  r"process\s+lifetime", r"evaluated\s+once", r"singleton"]),
                ("unbounded growth: 600k keys x 120KB, no eviction/TTL",
                 [r"unbounded", r"no\s+(eviction|ttl|limit)", r"ubegrænset",
                  r"grows?\s+forever", r"never\s+(evict|clear|remov)"]),
                ("dev restarts/recompiles constantly so it never accumulates; "
                 "prod is a long-lived server shared across all requests",
                 [r"dev.{0,80}(restart|recompil|hot\s*reload|hmr)",
                  r"long.?lived", r"shared\s+across\s+request",
                  r"every\s+request", r"alle\s+request"]),
            ],
            points=9, threshold=2)
        self.free_question(
            "Q2 - Write/describe the production-grade fix. (More than one "
            "valid answer - commit to one and justify it.)",
            [
                ("bounded cache: LRU with max size and/or TTL "
                 "(e.g. lru-cache)",
                 [r"\blru\b", r"ttl", r"max.{0,12}(size|entries|items)",
                  r"bounded", r"evict"]),
                ("or externalize: Redis/CDN cache shared across pods",
                 [r"redis", r"memcach", r"external\s+cache", r"cdn",
                  r"cache.?control", r"shared\s+cache"]),
                ("or per-request memoization (React cache() / request scope) "
                 "instead of process scope",
                 [r"react\s+cache", r"\bcache\(\)", r"per.?request",
                  r"request\s+scope", r"unstable_cache", r"fetch.{0,20}revalidate"]),
            ],
            points=8, threshold=1)
        self.free_question(
            "Q3 - Your fix ships. How do you PROVE to the team lead that "
            "the leak is gone? Name tools/signals.",
            [
                ("heap snapshots / --inspect / Chrome DevTools comparison",
                 [r"heap\s*(snapshot|dump)", r"--inspect", r"devtools",
                  r"clinic", r"heapdump"]),
                ("process.memoryUsage / RSS metrics over time under load",
                 [r"memoryusage", r"\brss\b", r"memory\s+(metric|graph)",
                  r"grafana", r"prometheus"]),
                ("load test + observe plateau instead of linear growth",
                 [r"load\s*test", r"k6", r"vegeta", r"artillery", r"plateau",
                  r"flad", r"soak"]),
            ],
            points=6, threshold=2)
        post_mortem("SSR Memory Leaks", """
        The deepest mental-model shift when moving from SPA to SSR: your
        React code now runs inside ONE long-lived Node process serving
        thousands of users, not one browser tab per user. Anything at
        module scope - Maps, arrays, event listeners, closures captured by
        timers - is effectively a global that survives every request.
        A per-tab 'cache' that was harmless client-side becomes a memory
        leak multiplied by your entire catalogue.

        Why dev hides it: HMR tears the module graph down constantly, so
        the Map never accumulates. Production runs for days. The classic
        signature is RSS climbing linearly under steady traffic with no
        plateau - a healthy cache plateaus at its bound.

        The senior fix is choosing the right cache LOCATION, not just a
        size limit: per-request memoization (React's cache()) for
        request-coherence, a bounded in-process LRU for hot keys, Redis
        for cross-pod sharing, and HTTP/CDN caching in front of all of it.
        Each layer has a different invalidation story - and cache
        invalidation is the part that pages you at 3 AM.
        """)

    def scenario_web_vitals(self):
        section("CASE 2: Core Web Vitals are failing - SEO traffic drops",
                C.BBLUE)
        code_block("""
Field data (CrUX, 28 days, mobile p75):
  LCP : 4.9s   (target < 2.5s)   FAIL
  CLS : 0.31   (target < 0.1)    FAIL
  INP : 180ms  (target < 200ms)  pass

Findings from the trace:
  - Hero image: <img src="/hero.jpg">  2.4 MB JPEG, no dimensions
  - Custom font: blocking @font-face, no fallback strategy ('FOIT')
  - A campaign banner is injected by JS ~1.8s after load, pushing
    the whole page down.
  - 740 KB of JS in the main bundle; a chart library is imported
    on every page but used on 2% of them.
""", "lighthouse/CrUX report")
        self.free_question(
            "Q1 - Fix LCP. Name the concrete Next.js mechanisms you would "
            "apply to the hero image and the font.",
            [
                ("next/image with priority (preload + optimized "
                 "format/size)",
                 [r"next/image", r"<image", r"\bpriority\b", r"preload"]),
                ("modern format + responsive sizes (AVIF/WebP, srcset/sizes, "
                 "compression)",
                 [r"avif", r"webp", r"srcset", r"\bsizes\b", r"compress",
                  r"resize", r"komprimer"]),
                ("next/font or font-display: swap to kill the FOIT",
                 [r"next/font", r"font-display", r"\bswap\b", r"self.?host"]),
            ],
            points=8, threshold=2)
        self.free_question(
            "Q2 - Fix CLS. What is causing the 0.31 and what are the two "
            "fixes?",
            [
                ("late-injected banner shifts layout / images without "
                 "dimensions",
                 [r"banner", r"inject", r"shift", r"dimension", r"width.{0,15}height",
                  r"uden\s+(mål|størrelse)"]),
                ("reserve space: fixed-size container/skeleton/placeholder "
                 "or min-height",
                 [r"reserve", r"placeholder", r"skeleton", r"min-?height",
                  r"fixed\s+(size|height)", r"aspect.?ratio"]),
                ("set width/height (or fill+sizes) so the browser can "
                 "pre-allocate the box",
                 [r"width", r"height", r"aspect", r"fill"]),
            ],
            points=7, threshold=2)
        self.free_question(
            "Q3 - Fix the 740 KB bundle. Which technique removes the chart "
            "library from 98% of page loads, and how do you verify what is "
            "actually inside the bundle?",
            [
                ("dynamic import / next/dynamic / code splitting (lazy load "
                 "on the 2% of pages)",
                 [r"dynamic\s*import", r"next/dynamic", r"import\(",
                  r"code.?split", r"lazy"]),
                ("bundle analyzer to inspect composition",
                 [r"analyz", r"@next/bundle", r"webpack.?bundle",
                  r"source.?map.?explorer"]),
                ("tree-shaking / import only used parts",
                 [r"tree.?shak", r"named\s+import", r"per.?module\s+import",
                  r"sideeffects"]),
            ],
            points=6, threshold=2)
        post_mortem("Core Web Vitals", """
        Web Vitals are not a Lighthouse vanity score - Google uses FIELD
        data (CrUX, real users at p75) as a ranking signal, so a failing
        LCP literally costs organic traffic and therefore revenue. The
        p75-on-mobile detail matters: your M3 MacBook on office wifi tells
        you nothing about the median Android phone on 4G that defines your
        score.

        LCP is almost always the hero media: the chain is discover ->
        fetch -> decode -> paint, and you attack every link: next/image
        gives you AVIF/WebP transcoding, responsive srcset, lazy loading
        by default, and `priority` to preload the one image that IS the
        LCP element. Fonts cause both LCP and CLS damage; next/font
        self-hosts, preloads, and applies size-adjusted fallbacks so text
        renders instantly without a metric-breaking swap jump.

        CLS is a layout-stability contract: every element must have its
        space reserved before it arrives. Late-injected content (ads,
        banners, cookie walls) is the classic killer - reserve the box.
        Bundle size attacks INP and TTFB-to-interactive: route-level code
        splitting is automatic in Next.js, but a heavy import in a shared
        layout poisons every route; next/dynamic moves the cost to the
        pages that actually pay rent on it.
        """)

    def scenario_isr(self):
        section("CASE 3: 50.000 product pages - the build takes 3 hours",
                C.BBLUE)
        wrap("""
        Marketing edits prices in the CMS and screams when the site shows
        stale prices for hours. A full rebuild+deploy takes 3 hours. SSR
        on every request would melt the CMS API (rate-limited at 50 rps).
        Your task: design the ISR strategy.
        """, indent=2)
        self.free_question(
            "Q1 - Write the actual Next.js code/config (App Router or "
            "Pages Router) that gives every product page background "
            "regeneration every 5 minutes.",
            [
                ("revalidate = 300 (export const revalidate / "
                 "getStaticProps revalidate / fetch next.revalidate)",
                 [r"revalidate\s*[:=]\s*300", r"revalidate\s*[:=]\s*\d+",
                  r"next:\s*\{\s*revalidate"]),
                ("static generation as the base (generateStaticParams / "
                 "getStaticProps / getStaticPaths)",
                 [r"generatestaticparams", r"getstaticprops", r"getstaticpaths",
                  r"static"]),
            ],
            points=7, threshold=1)
        self.free_question(
            "Q2 - 5 minutes is still too slow for a Black Friday price "
            "change. Which Next.js mechanism updates ONE page within "
            "seconds of the CMS edit, and how is it wired up?",
            [
                ("on-demand revalidation: revalidatePath / revalidateTag / "
                 "res.revalidate",
                 [r"revalidatepath", r"revalidatetag", r"res\.revalidate",
                  r"on.?demand"]),
                ("triggered by a CMS webhook hitting a secured route "
                 "handler/API route",
                 [r"webhook", r"api\s*route", r"route\s*handler",
                  r"secret", r"token"]),
            ],
            points=7, threshold=2)
        self.free_question(
            "Q3 - You cannot pre-build 50.000 pages in CI. How do you "
            "build only the top 500 and still serve the long tail "
            "instantly-ish on first visit? Name the mechanism and what "
            "the FIRST visitor experiences.",
            [
                ("generateStaticParams returns subset + dynamicParams=true "
                 "(or fallback:'blocking'/true in Pages Router)",
                 [r"dynamicparams", r"fallback", r"blocking", r"subset",
                  r"top\s*500", r"generatestaticparams"]),
                ("first visitor triggers SSR/on-demand generation, result "
                 "is cached for everyone after",
                 [r"first\s+(visit|request).{0,90}(generat|render|ssr)",
                  r"on.?demand.{0,40}(generat|render)", r"cached?\s+(after|for)",
                  r"genereres\s+ved\s+første"]),
            ],
            points=7, threshold=1)
        post_mortem("ISR & Caching Strategy", """
        ISR is the answer to a trilemma: static = fast but stale, SSR =
        fresh but expensive, and full rebuilds do not scale past a few
        thousand pages. ISR serves a cached static page while regenerating
        it in the background once it is older than `revalidate` - the
        academic name is stale-while-revalidate, and it means one user
        occasionally gets a slightly stale page so that ALL users get CDN
        latency and your CMS only sees one request per page per window.

        Time-based revalidation caps staleness; on-demand revalidation
        (CMS webhook -> route handler -> revalidateTag) makes updates
        event-driven, which is both fresher and cheaper - no polling.
        Tag-based invalidation is the senior detail: tag fetches with
        e.g. 'product-123' and a price change invalidates exactly the
        pages that depend on that product, not the whole cache.

        For huge catalogues, build the head of the traffic distribution
        (top 500 pages = most of the visits) and let dynamicParams handle
        the tail on first request. You have effectively reinvented a
        demand-filled CDN cache - which is the point: modern frontend
        performance IS cache architecture.
        """)

    def scenario_hydration(self):
        section("CASE 4: 'Text content does not match server-rendered HTML'",
                C.BBLUE)
        alert("Sentry: 31.000 hydration errors in 24h. Affected component:")
        code_block("""
export default function CampaignHeader({ endsAt }) {
  const msLeft = new Date(endsAt) - Date.now();
  const greeting = Math.random() > 0.5 ? "Hurry!" : "Last chance!";
  return (
    <header>
      <h1>{greeting}</h1>
      <span>Ends in {Math.floor(msLeft / 60000)} minutes</span>
      <span>{new Date(endsAt).toLocaleTimeString()}</span>
    </header>
  );
}
""", "jsx")
        self.free_question(
            "Q1 - Explain mechanically what hydration IS and exactly why "
            "this component throws. Identify all three bugs.",
            [
                ("hydration = React attaches to server HTML and expects the "
                 "first client render to produce IDENTICAL output",
                 [r"hydrat", r"attach", r"match.{0,40}server", r"identical",
                  r"samme\s+output", r"mismatch"]),
                ("Math.random() differs between server and client render",
                 [r"math\.random", r"random"]),
                ("Date.now()/time differs (server render time vs client "
                 "render time)",
                 [r"date\.now", r"time\s+diff", r"server\s+tid", r"clock",
                  r"render\s+time"]),
                ("toLocaleTimeString depends on locale/timezone of the "
                 "machine - server (UTC) vs user's browser",
                 [r"locale", r"timezone", r"tidszone", r"utc",
                  r"tolocale"]),
            ],
            points=9, threshold=3)
        self.free_question(
            "Q2 - Fix it properly. Describe the pattern (or write the "
            "code). Bonus honesty: when is suppressHydrationWarning "
            "acceptable and why is it usually a trap?",
            [
                ("two-pass render: useState+useEffect / 'mounted' flag - "
                 "render time-dependent parts only on the client after mount",
                 [r"useeffect", r"usestate", r"mounted", r"client.?only",
                  r"after\s+mount", r"two.?pass"]),
                ("make output deterministic: compute greeting/seed on the "
                 "server and pass as prop",
                 [r"prop", r"deterministic", r"seed", r"server.{0,40}(compute|decide)",
                  r"samme\s+(værdi|input)"]),
                ("suppressHydrationWarning only for a single unavoidable "
                 "node (e.g. timestamp), never as a blanket fix - it hides "
                 "real bugs",
                 [r"suppresshydrationwarning.{0,160}(single|one|timestamp|last|kun|aldrig|trap|hide)",
                  r"(only|kun).{0,80}suppresshydrationwarning"]),
            ],
            points=8, threshold=2)
        post_mortem("Hydration Failures", """
        Hydration is React replaying the initial render in the browser and
        wiring event handlers onto HTML the server already produced. The
        contract: server render and FIRST client render must be byte-equal.
        Any nondeterminism breaks it - randomness, the current time,
        locale/timezone formatting, browser-only APIs (window,
        localStorage), even user-agent branching. The cost is not just a
        console error: React 18 may throw the server HTML away and
        re-render the whole subtree client-side, so you pay full CSR cost
        AND get a visual flash - and in lists it can attach handlers to the
        wrong rows.

        The fix taxonomy: (1) push nondeterminism UP - decide it once on
        the server and pass it down as a prop; (2) push it DOWN past
        hydration - render a stable placeholder, then swap in the
        client-only value in useEffect (the 'mounted' pattern); (3) for a
        truly unavoidable node like a local-time stamp,
        suppressHydrationWarning on THAT element only. Blanket suppression
        is how teams ship the wrong prices in the right font.

        Interview gold: explain that 'Ends in X minutes' countdowns belong
        in pattern 2, while A/B-test copy like the greeting belongs in
        pattern 1 (decided server-side, so it is also consistent for SEO).
        """)


# ---------------------------------------------------------------------------
# 6. MODULE 3 - SPRING BOOT BACKEND
# ---------------------------------------------------------------------------


class BackendService(ServiceModule):
    name = "svc-backend"
    title = "SPRING BOOT - Pools, Races, Circuit Breakers, Thread Dumps"

    def run(self, payload):
        banner("MODULE 3 - SPRING BOOT BACKEND",
               "Internship focus. Enterprise Java under fire.", C.BGREEN)
        wrap("""
        You join the payments team. Java 21, Spring Boot 3, PostgreSQL,
        HikariCP, Resilience4j. The system processes real money, which
        means every concurrency bug has a kroner amount attached.
        """, indent=2)
        pause()
        self.scenario_hikari()
        self.scenario_race()
        self.scenario_circuit_breaker()
        self.scenario_thread_dump()
        banner("MODULE 3 COMPLETE",
               f"Backend score: {self.points}/{self.max_points}", C.BGREEN)

    def scenario_hikari(self):
        section("CASE 1: Connection pool starvation at 09:00 every day",
                C.BGREEN)
        alert("SQLTransientConnectionException: HikariPool-1 - Connection "
              "is not available, request timed out after 30000ms")
        code_block("""
# application.yml (current)
spring:
  datasource:
    hikari:
      maximum-pool-size: 100        # 'we raised it last week, still dies'

@Service
public class InvoiceService {
  @Transactional
  public Receipt settle(Order order) {
    Invoice inv = invoiceRepo.lockAndLoad(order.id());   // takes DB conn
    TaxResult tax = taxApiClient.calculate(inv);          // HTTP, p99 = 8s !!
    inv.apply(tax);
    return receiptRepo.save(inv.toReceipt());
  }
}

Host: 8 vCPU, SSD storage. 200 concurrent requests at peak.
""", "yaml + java")
        self.free_question(
            "Q1 - The team already raised the pool to 100 and it got "
            "WORSE. Find the real root cause in the code above.",
            [
                ("slow external HTTP call happens INSIDE @Transactional, so "
                 "each request holds a DB connection for ~8s",
                 [r"http.{0,90}(inside|i|within).{0,30}transac",
                  r"transac.{0,90}(http|extern|tax)",
                  r"holds?.{0,40}connection.{0,60}(8s|http|extern)",
                  r"connection.{0,60}(under|during).{0,40}(http|call)"]),
                ("pool size is not the bottleneck - hold TIME is "
                 "(Little's Law: throughput = pool / hold-time)",
                 [r"hold.{0,12}time", r"little", r"duration", r"holder.{0,30}for\s+l",
                  r"ikke\s+pool\s*størrelse", r"not.{0,20}pool\s+size"]),
                ("100 conns can also overload Postgres itself "
                 "(context switching, lock contention)",
                 [r"100.{0,80}(overload|too\s+many|for\s+mange|postgres|db)",
                  r"too\s+many\s+connections", r"context\s+switch"]),
            ],
            points=9, threshold=1)
        self.free_question(
            "Q2 - Refactor: describe the fix to the CODE (not the config).",
            [
                ("move the external call OUTSIDE the transaction "
                 "(call tax API first, then open a short transaction)",
                 [r"(outside|out\s+of|uden\s*for|før|before).{0,40}transak?c",
                  r"transak?c.{0,60}(short|kort|efter|after)",
                  r"split.{0,40}transac", r"remove.{0,20}@?transactional"]),
                ("keep transactions short: only DB work inside, set "
                 "timeouts on the HTTP client",
                 [r"short\s+transac", r"korte\s+transak", r"timeout",
                  r"kun\s+db", r"only\s+db"]),
            ],
            points=7, threshold=1)
        print()
        info("Now the config. HikariCP's own guidance: "
             "pool_size = (core_count * 2) + effective_spindle_count. "
             "Host: 8 vCPU, SSD (count SSD as 1 spindle).")
        self.numeric_question(
            "Q3 - Calculate the recommended maximum-pool-size",
            lambda v: 15 <= v <= 20, points=5, unit="connections")
        info("(8 * 2) + 1 = 17. Anything from ~16-20 is defensible; "
             "100 never was.")
        self.exact_command(
            "Q4 - One Hikari property exists specifically to catch "
            "connections that code forgot to close. Name it (and a sane "
            "value).",
            [
                ("leak-detection-threshold",
                 [r"leak.?detection.?threshold", r"leakdetection"]),
                ("a value in the seconds-to-a-minute range (e.g. 10000-60000 ms)",
                 [r"\b(10|15|20|30|60)\s*0{0,3}\s*(ms|s|sek|sec)?\b",
                  r"\b(10000|15000|20000|30000|60000)\b"]),
            ],
            points=4, threshold=1)
        post_mortem("HikariCP & Pool Sizing", """
        Pool starvation is a queueing problem, and queueing problems obey
        Little's Law: concurrent demand = arrival rate x hold time. The
        team attacked the only variable that was NOT the problem (pool
        size) while every request held its connection hostage through an
        8-second third-party HTTP call. 200 concurrent requests x 8s hold
        time needs 1600 connections - no pool survives that, and Postgres
        would collapse long before (each backend connection is a process
        with real memory; beyond a few dozen active connections an 8-core
        box loses throughput to context switching).

        That is why HikariCP's own documentation recommends SMALL pools:
        (cores x 2) + spindles, here 17. A small pool plus short hold
        times outperforms a huge pool every time - this is deeply
        counterintuitive to juniors and a favourite interview question.

        The structural rule worth tattooing: NEVER perform network I/O
        inside a database transaction. Transactions should bracket the
        minimal set of statements that must be atomic - milliseconds, not
        seconds. And leakDetectionThreshold is your tripwire: it logs the
        stack trace of any connection held past N ms, catching the
        forgotten-close and the accidental-slow-transaction alike.
        """)

    def scenario_race(self):
        section("CASE 2: The account that went negative", C.BGREEN)
        alert("Finance reports: account #88231 balance = -7.250,00 kr. "
              "Withdrawals 'cannot' exceed balance. And yet.")
        code_block("""
@Service
public class AccountService {
  public void withdraw(long accountId, BigDecimal amount) {
    Account acc = accountRepo.findById(accountId).orElseThrow();
    if (acc.getBalance().compareTo(amount) >= 0) {       // CHECK
      acc.setBalance(acc.getBalance().subtract(amount)); // ACT
      accountRepo.save(acc);
    } else {
      throw new InsufficientFundsException();
    }
  }
}
""", "java")
        self.free_question(
            "Q1 - Name the bug pattern precisely and narrate the exact "
            "interleaving of two threads that produces the negative "
            "balance.",
            [
                ("check-then-act race / TOCTOU / lost update",
                 [r"check.?then.?act", r"toctou", r"time.?of.?check",
                  r"lost\s+update", r"race"]),
                ("both threads read the same balance before either writes",
                 [r"both.{0,60}read", r"begge.{0,60}læser",
                  r"read.{0,60}(before|før).{0,30}(writ|skriv|save)",
                  r"same\s+balance", r"samme\s+saldo"]),
                ("both pass the check, both subtract, second save wins -> "
                 "overdraw",
                 [r"both\s+pass", r"begge.{0,40}(check|tjek)",
                  r"second.{0,30}(save|write)", r"overwrit", r"overdraw",
                  r"negativ"]),
            ],
            points=8, threshold=2)
        self.free_question(
            "Q2 - You must fix this in a system with MULTIPLE app "
            "instances behind a load balancer (so `synchronized` is "
            "useless). Give at least two database-backed strategies and "
            "state the trade-off between them.",
            [
                ("pessimistic locking: SELECT ... FOR UPDATE / "
                 "@Lock(PESSIMISTIC_WRITE)",
                 [r"for\s+update", r"pessimistic", r"pessimistisk",
                  r"@lock"]),
                ("optimistic locking: @Version column, retry on "
                 "OptimisticLockException",
                 [r"optimistic", r"optimistisk", r"@version", r"version\s+(col|felt|field)"]),
                ("or atomic conditional UPDATE: SET balance = balance - ? "
                 "WHERE balance >= ? (check rows affected)",
                 [r"update.{0,80}balance\s*-\s*", r"where\s+balance\s*>=",
                  r"atomic\s+update", r"conditional\s+update", r"rows?\s+affected"]),
                ("trade-off: pessimistic blocks/serializes (safe, lower "
                 "throughput under contention); optimistic scales but "
                 "needs retry logic",
                 [r"(pessimi|lock).{0,120}(block|throughput|contention|venter|wait)",
                  r"optimi.{0,120}(retry|conflict|abort|skaler|scale)",
                  r"trade.?off", r"afvejning"]),
            ],
            points=10, threshold=2)
        self.free_question(
            "Q3 - Why does adding `synchronized` to the method 'work' on "
            "the developer laptop and create a false sense of safety?",
            [
                ("synchronized only locks within ONE JVM/process",
                 [r"one\s+jvm", r"én\s+jvm", r"single\s+(jvm|instance|process)",
                  r"samme\s+jvm", r"within.{0,20}(jvm|process)"]),
                ("production runs multiple instances/pods - the lock does "
                 "not span them, the DB is the only shared arbiter",
                 [r"multiple\s+(instance|pod|node)", r"flere\s+(instanser|pods)",
                  r"load\s*balanc", r"distributed", r"db.{0,60}(shared|arbiter|kilde)",
                  r"database.{0,40}(eneste|only)"]),
            ],
            points=6, threshold=1)
        post_mortem("Race Conditions & Locking", """
        Check-then-act is THE canonical concurrency bug: the world is
        allowed to change between your read and your write, and under load
        it will. The interleaving is mechanical - T1 reads 500, T2 reads
        500, both see 500 >= 400, both subtract, final state depends on
        write order but is wrong either way (lost update). Note that
        @Transactional alone does NOT fix it at the default READ_COMMITTED
        isolation level - both transactions commit happily.

        The horizontal-scaling insight separates juniors from engineers:
        any JVM-level mechanism (synchronized, ReentrantLock, Atomic*)
        coordinates threads in ONE process. Behind a load balancer you
        have N processes, so the coordination point must be the shared
        resource itself - the database. Pessimistic locking (SELECT FOR
        UPDATE) serializes access to the row: correct, simple, but
        contended rows become a queue. Optimistic locking (@Version)
        gambles that conflicts are rare and pays with a retry loop when
        wrong. The atomic conditional UPDATE is the elegant third option:
        one statement, the DB enforces the invariant, no read needed.

        Rule of thumb to quote in interviews: pessimistic for hot rows and
        money, optimistic for low-contention business data, and put the
        invariant in the database (CHECK constraint balance >= 0) as the
        last line of defence regardless.
        """)

    def scenario_circuit_breaker(self):
        section("CASE 3: The downstream API that dragged you under",
                C.BGREEN)
        alert("Your payment provider's API fails 80% of calls with 25s "
              "timeouts. YOUR service's Tomcat threads are all stuck "
              "waiting on it. Healthy endpoints now 503 too. Cascade.")
        self.free_question(
            "Q1 - Explain the cascade mechanically: why does ONE slow "
            "dependency take down endpoints that never call it?",
            [
                ("shared, finite thread pool (Tomcat workers) exhausted by "
                 "threads parked waiting on the slow dependency",
                 [r"thread\s*pool", r"tomcat", r"worker", r"tråd",
                  r"exhaust", r"opbrugt", r"blocked\s+threads"]),
                ("slow is worse than down: 25s timeouts hold resources; a "
                 "fast failure would release them",
                 [r"slow.{0,80}(worse|værre)", r"timeout.{0,60}(hold|binder)",
                  r"fast\s+fail", r"25s", r"hold.{0,30}(thread|resource)"]),
                ("no bulkhead/isolation between dependency calls and the "
                 "rest of the app",
                 [r"bulkhead", r"isolat", r"shared\s+resource", r"skot"]),
            ],
            points=8, threshold=2)
        self.free_question(
            "Q2 - Write the Resilience4j configuration (YAML or "
            "annotations) for a circuit breaker on 'paymentProvider'. "
            "Include the properties that control WHEN it opens and when "
            "it tries again.",
            [
                ("failure-rate-threshold (e.g. 50)",
                 [r"failure.?rate.?threshold"]),
                ("sliding-window (size/type) to measure over recent calls",
                 [r"sliding.?window"]),
                ("wait-duration-in-open-state before probing again",
                 [r"wait.?duration.?in.?open"]),
                ("half-open probe calls "
                 "(permitted-number-of-calls-in-half-open-state)",
                 [r"half.?open", r"permitted.?number"]),
                ("plus a TIMEOUT (TimeLimiter/connect+read timeout) - "
                 "breaker without timeout is half a fix",
                 [r"time.?limiter", r"timeout"]),
            ],
            points=10, threshold=3)
        self.free_question(
            "Q3 - Walk through the breaker's state machine and what your "
            "service should DO while it is open (the user still wants to "
            "pay!).",
            [
                ("CLOSED: calls flow, failures counted against the window",
                 [r"closed"]),
                ("OPEN: calls fail fast immediately, no threads risked",
                 [r"open.{0,80}(fail\s*fast|immediate|straks|afvis|reject)",
                  r"fail\s+fast"]),
                ("HALF_OPEN: limited probe calls decide close vs re-open",
                 [r"half.?open", r"probe", r"test\s+calls", r"prøve"]),
                ("fallback: queue payment for retry / alternative provider "
                 "/ graceful degradation message",
                 [r"fallback", r"queue", r"kø", r"retry\s+later", r"alternative",
                  r"degrad", r"reserve"]),
            ],
            points=8, threshold=3)
        post_mortem("Circuit Breakers & Cascading Failure", """
        The killer fact: in a thread-per-request server, a SLOW dependency
        is more dangerous than a DEAD one. Dead fails in milliseconds and
        releases the thread; slow parks the thread for the full timeout.
        With 200 Tomcat workers and a 25s timeout at 80% failure, your
        entire worker pool is parked within seconds - and now /health,
        /products, everything 503s. That is a cascading failure, and it is
        how one vendor outage becomes YOUR outage.

        The circuit breaker is a state machine wrapped around the call.
        CLOSED: traffic flows, a sliding window tracks the failure rate.
        Past the threshold (e.g. 50% of the last 20 calls) it trips to
        OPEN: every call fails instantly with CallNotPermittedException -
        zero threads risked, and crucially the struggling dependency gets
        breathing room to recover instead of being hammered. After
        waitDurationInOpenState it goes HALF_OPEN and lets a handful of
        probes through; success closes it, failure re-opens.

        A breaker without a fallback is just a faster error. Real designs
        pair it with: aggressive timeouts (seconds, not 25), a bulkhead
        (separate, small thread/connection budget per dependency so one
        cannot starve the rest), and a business fallback - queue the
        payment for async retry, fail over to a second provider, or
        degrade honestly ('payment confirmed pending'). Resilience is a
        business decision expressed in YAML.
        """)

    def scenario_thread_dump(self):
        section("CASE 4: Production is frozen - read the thread dump",
                C.BGREEN)
        alert("Order processing throughput: 0/sec. CPU: 3%. The JVM is "
              "alive but nothing moves. You capture `jstack <pid>`:")
        code_block("""
"order-worker-3" #41 prio=5 tid=0x7f2a BLOCKED
   java.lang.Thread.State: BLOCKED (on object monitor)
        at com.nordpay.InventoryService.reserve(InventoryService.java:88)
        - waiting to lock <0x000000076ab2> (a com.nordpay.Inventory)
        at com.nordpay.OrderService.place(OrderService.java:42)
        - locked <0x000000076aa1> (a com.nordpay.Ledger)

"inventory-sync-1" #57 prio=5 tid=0x7f3b BLOCKED
   java.lang.Thread.State: BLOCKED (on object monitor)
        at com.nordpay.LedgerService.book(LedgerService.java:31)
        - waiting to lock <0x000000076aa1> (a com.nordpay.Ledger)
        at com.nordpay.SyncJob.run(SyncJob.java:19)
        - locked <0x000000076ab2> (a com.nordpay.Inventory)

"order-worker-1" #39 WAITING (parking)
        at jdk.internal.misc.Unsafe.park
        - parking to wait for <0x00000007821> (LinkedBlockingQueue)

Found 1 deadlock.
""", "jstack output")
        self.exact_command(
            "Q1 - Name the two threads that are deadlocked (exact thread "
            "names).",
            [
                ("order-worker-3", [r"order.?worker.?3"]),
                ("inventory-sync-1", [r"inventory.?sync.?1"]),
            ],
            points=6, threshold=2)
        self.free_question(
            "Q2 - Reconstruct the deadlock: who holds what and waits for "
            "what? And why is 'order-worker-1' NOT part of the problem?",
            [
                ("order-worker-3 holds Ledger(76aa1), waits for "
                 "Inventory(76ab2)",
                 [r"order.?worker.?3.{0,140}(hold|locked|76aa1|ledger).{0,160}(wait|76ab2|inventory)"]),
                ("inventory-sync-1 holds Inventory(76ab2), waits for "
                 "Ledger(76aa1) - a perfect cycle",
                 [r"inventory.?sync.?1.{0,140}(hold|locked|76ab2|inventory).{0,160}(wait|76aa1|ledger)",
                  r"cycle", r"cirkul", r"cross", r"hinanden"]),
                ("order-worker-1 is WAITING/parked on a queue = idle and "
                 "normal, not BLOCKED on a monitor",
                 [r"order.?worker.?1.{0,140}(waiting|park|queue|idle|normal)",
                  r"waiting.{0,60}(not|ikke).{0,30}blocked",
                  r"parked.{0,40}(queue|kø)"]),
            ],
            points=9, threshold=2)
        self.free_question(
            "Q3 - The permanent fix. State the classic rule that prevents "
            "lock-ordering deadlocks, plus one defensive alternative.",
            [
                ("global consistent lock ORDERING (always Ledger before "
                 "Inventory, everywhere)",
                 [r"lock\s+order", r"consistent\s+order", r"samme\s+rækkefølge",
                  r"global\s+order", r"always.{0,30}(first|før)"]),
                ("tryLock with timeout + back off (ReentrantLock) instead "
                 "of synchronized",
                 [r"trylock", r"timeout", r"back.?off", r"reentrantlock"]),
                ("or shrink/redesign: smaller critical sections, one lock, "
                 "or a queue/single-writer design",
                 [r"smaller\s+critical", r"single\s+lock", r"én\s+lås",
                  r"queue", r"single.?writer", r"redesign", r"actor"]),
            ],
            points=8, threshold=2)
        post_mortem("Thread Dump Analysis", """
        A frozen JVM at 3% CPU is the signature of a LOCKING problem, not
        a load problem (high CPU + frozen = spinning or GC thrash; low CPU
        + frozen = everyone is waiting). jstack is the X-ray. Read it by
        thread STATE: RUNNABLE = working, WAITING/parking on a queue =
        a healthy idle pool thread (a junior mistake is 'fixing' those),
        BLOCKED on an object monitor = contention, and BLOCKED in a cycle
        = deadlock. Modern jstack even prints 'Found 1 deadlock' - but you
        must still read the cycle, because the fix lives in the stack
        traces: WHICH code paths acquire locks in opposite orders.

        Here OrderService takes Ledger then Inventory; SyncJob takes
        Inventory then Ledger. Coffman condition #4 (circular wait) is
        satisfied, and the standard kill is to make a cycle impossible:
        one global lock acquisition order, documented and enforced.
        Alternatives when ordering is impractical: tryLock with timeout
        and backoff (turns deadlock into a retry), collapsing to a single
        coarser lock (correct first, fast second), or removing shared
        mutable state entirely with a queue/single-writer design.

        Interview move: name the four Coffman conditions (mutual
        exclusion, hold-and-wait, no preemption, circular wait) and point
        out that lock ordering attacks the fourth. That is a senior answer.
        """)


# ---------------------------------------------------------------------------
# 7. MODULE 4 - SQL & POSTGRESQL (interactive REPL)
# ---------------------------------------------------------------------------


class DatabaseService(ServiceModule):
    name = "svc-database"
    title = "POSTGRESQL - Live psql Simulator (indexes, deadlocks, replicas)"

    def __init__(self):
        super().__init__()
        self.reset_state()

    def reset_state(self):
        self.indexes = {"orders_pkey (btree on orders.id)"}
        self.gin_created = False
        self.btree_created = False
        self.deadlock_resolved = False
        self.deadlock_failed_kills = 0
        self.missions_done = set()

    def run(self, payload):
        self.reset_state()
        banner("MODULE 4 - POSTGRESQL OPERATIONS",
               "Internship focus. You are inside a simulated psql.", C.BYELLOW)
        wrap("""
        Cluster 'nordshop-prod', PostgreSQL 16. Tables: orders (12.4M
        rows: id, customer_id, total, created_at, attributes jsonb) and
        customers (310k rows: id, name, country). Type real commands.
        \\m shows missions, \\help shows commands, \\q leaves the module.
        """, indent=2)
        self.print_missions()
        self.repl()
        # Missions 5 (replica design) and 6 (window function) are graded
        # question-style after the REPL if not yet completed inside it.
        self.mission_replica()
        self.mission_window()
        banner("MODULE 4 COMPLETE",
               f"Database score: {self.points}/{self.max_points}", C.BYELLOW)

    # ---- REPL --------------------------------------------------------------

    MISSIONS = [
        "M1  The jsonb query below runs 8.4s. Diagnose with EXPLAIN, fix "
        "with the RIGHT index type, verify it.\n      "
        "SELECT * FROM orders WHERE attributes @> '{\"color\": \"red\"}';",
        "M2  The dashboard range query is slow. Index it correctly.\n      "
        "SELECT count(*) FROM orders WHERE created_at >= now() - interval "
        "'7 days';",
        "M3  Writes are frozen: sessions are stuck behind a lock. Inspect "
        "pg_stat_activity / pg_locks and terminate the CORRECT backend.",
        "M4  (after \\q) Design streaming read-replicas: name the config.",
        "M5  (after \\q) Write the window-function query: each customer's "
        "single LARGEST order, with customer name.",
    ]

    def print_missions(self):
        section("MISSIONS", C.BYELLOW)
        for i, m in enumerate(self.MISSIONS, 1):
            mark = (f"{C.BGREEN}[done]{C.RESET}"
                    if f"M{i}" in self.missions_done else f"{C.GREY}[open]{C.RESET}")
            print(f"  {mark} {C.WHITE}{m}{C.RESET}")
        print()

    def repl(self):
        info("Connected. psql simulator ready.")
        # mission scoring inside the REPL
        self.max_points += 10   # M1 gin
        self.max_points += 6    # M2 btree
        self.max_points += 10   # M3 deadlock
        self.max_points += 4    # using EXPLAIN at least once before/after
        explain_used_before = False
        explain_used_after = False
        while True:
            try:
                cmd = safe_input(f"{C.BYELLOW}nordshop-prod=# {C.RESET}").strip()
            except QuitGame:
                raise
            if not cmd:
                continue
            low = cmd.lower().rstrip(";").strip()
            if low in (r"\q", "quit", "exit"):
                break
            if low in (r"\m", r"\missions"):
                self.print_missions()
                continue
            if low in (r"\help", "help", r"\?"):
                self.repl_help()
                continue
            if low in (r"\d", r"\dt", r"\d orders", r"\d customers"):
                self.describe_tables(low)
                continue
            if low == r"\di":
                section("Indexes", C.BYELLOW)
                for idx in sorted(self.indexes):
                    print(f"   {C.WHITE}{idx}{C.RESET}")
                continue
            if re.match(r"^explain", low):
                if "attributes" in low or "@>" in cmd:
                    self.explain_jsonb()
                    if self.gin_created:
                        explain_used_after = True
                    else:
                        explain_used_before = True
                elif "created_at" in low:
                    self.explain_range()
                else:
                    print(f"{C.GREY}   QUERY PLAN\n   Seq Scan on orders  "
                          f"(cost=0.00..312044.10 rows=12400000){C.RESET}")
                continue
            if re.match(r"^create\s+index", low):
                self.handle_create_index(cmd)
                continue
            if "pg_stat_activity" in low:
                self.show_activity()
                continue
            if "pg_locks" in low:
                self.show_locks()
                continue
            if "pg_terminate_backend" in low or "pg_cancel_backend" in low:
                self.handle_terminate(cmd)
                continue
            if re.match(r"^select", low):
                self.run_select(cmd)
                continue
            if re.match(r"^(set|show)\b", low):
                print(f"{C.GREY}   {('SET' if low.startswith('set') else 'SHOW')} "
                      f"acknowledged (simulated).{C.RESET}")
                continue
            warn("Command not recognized by the simulator. \\help lists "
                 "what the lab supports.")
        # award EXPLAIN diagnostics points
        diag = (2 if explain_used_before else 0) + (2 if explain_used_after else 0)
        self.points += diag
        if diag:
            ok(f"Diagnostic discipline (EXPLAIN before/after): +{diag} pts")
        if "M3" not in self.missions_done:
            warn("M3 (deadlock) left unresolved - writes are still frozen. "
                 "0/10 pts.")

    def repl_help(self):
        section("Supported commands", C.BYELLOW)
        for line in [
            r"\m                          missions and status",
            r"\d / \d orders / \d customers   describe tables",
            r"\di                         list indexes",
            "EXPLAIN [ANALYZE] <query>    show the (simulated) plan",
            "CREATE INDEX ... ON ... USING <btree|gin|hash> (col)",
            "SELECT ... FROM orders/customers ...  (timed, simulated)",
            "SELECT * FROM pg_stat_activity;       see sessions",
            "SELECT * FROM pg_locks;               see lock waits",
            "SELECT pg_terminate_backend(<pid>);   kill a backend",
            r"\q                          leave the REPL",
        ]:
            print(f"   {C.WHITE}{line}{C.RESET}")

    def describe_tables(self, low):
        if "customers" in low:
            code_block("""
Table "public.customers"   (~310,000 rows)
 id integer PK | name text | country varchar(2)
Indexes: customers_pkey (btree on id)
""", "psql")
        else:
            code_block("""
Table "public.orders"   (~12,400,000 rows)
 id bigint PK | customer_id int | total numeric(12,2)
 created_at timestamptz | attributes jsonb
Indexes: """ + ", ".join(sorted(self.indexes)) + "\n", "psql")

    def explain_jsonb(self):
        if self.gin_created:
            code_block("""
QUERY PLAN
Bitmap Heap Scan on orders  (cost=124.31..9882.20 rows=3100)
  Recheck Cond: (attributes @> '{"color": "red"}'::jsonb)
  ->  Bitmap Index Scan on idx_orders_attributes_gin
        (cost=0.00..123.54 rows=3100)
        Index Cond: (attributes @> '{"color": "red"}'::jsonb)
Execution Time: 38.412 ms
""", "plan")
        else:
            code_block("""
QUERY PLAN
Seq Scan on orders  (cost=0.00..374061.00 rows=3100)
  Filter: (attributes @> '{"color": "red"}'::jsonb)
  Rows Removed by Filter: 12396900
Execution Time: 8417.203 ms        <-- reads ALL 12.4M rows
""", "plan")

    def explain_range(self):
        if self.btree_created:
            code_block("""
QUERY PLAN
Aggregate
  ->  Index Only Scan using idx_orders_created_at on orders
        Index Cond: (created_at >= now() - '7 days'::interval)
Execution Time: 91.330 ms
""", "plan")
        else:
            code_block("""
QUERY PLAN
Aggregate
  ->  Seq Scan on orders  (cost=0.00..343061.00)
        Filter: (created_at >= now() - '7 days'::interval)
Execution Time: 6120.877 ms
""", "plan")

    def handle_create_index(self, cmd):
        low = cmd.lower()
        m_table = re.search(r"on\s+(\w+)", low)
        table = m_table.group(1) if m_table else "?"
        using = re.search(r"using\s+(\w+)", low)
        method = using.group(1) if using else "btree"
        col_m = re.search(r"\(\s*([\w,\s]+?)\s*\)", low)
        col = col_m.group(1).strip() if col_m else "?"
        if table != "orders":
            warn(f"Index created on '{table}', but the slow queries hit "
                 f"'orders'. No mission progress.")
            return
        if "attributes" in col:
            if method == "gin":
                self.indexes.add("idx_orders_attributes_gin "
                                 "(gin on orders.attributes)")
                if not self.gin_created:
                    self.gin_created = True
                    self.missions_done.add("M1")
                    self.points += 10
                    ok("CREATE INDEX (GIN on jsonb) ... done in 94s "
                       "(simulated). M1 logic complete: +10 pts. "
                       "Now verify with EXPLAIN + run the query.")
            elif method in ("btree",):
                self.indexes.add("idx_orders_attributes_btree "
                                 "(btree on orders.attributes)")
                warn("Index created - but a B-Tree on a jsonb column only "
                     "supports equality on the WHOLE document. The @> "
                     "containment operator CANNOT use it. EXPLAIN still "
                     "shows a Seq Scan. Think about operator classes.")
            else:
                warn(f"'{method}' is not a useful access method for jsonb "
                     f"containment here.")
        elif "created_at" in col:
            if method in ("btree",):
                self.indexes.add("idx_orders_created_at "
                                 "(btree on orders.created_at)")
                if not self.btree_created:
                    self.btree_created = True
                    self.missions_done.add("M2")
                    self.points += 6
                    ok("CREATE INDEX (B-Tree on created_at) ... done. "
                       "M2 complete: +6 pts. Range scans (>=, BETWEEN, "
                       "ORDER BY) are exactly what B-Trees are for.")
            elif method == "gin":
                warn("GIN on a scalar timestamp gains you nothing - GIN "
                     "indexes ELEMENTS of composite values (jsonb keys, "
                     "array members, lexemes). Range predicates on scalars "
                     "want a B-Tree.")
            elif method == "hash":
                warn("Hash indexes support ONLY equality (=). Your query "
                     "is a range (>=). Seq Scan remains.")
        else:
            info(f"Index on orders({col}) created (simulated) - not "
                 f"relevant to an open mission.")

    def run_select(self, cmd):
        low = cmd.lower()
        if "attributes" in low or "@>" in cmd:
            ms = 38 if self.gin_created else 8417
            rows = 3100
        elif "created_at" in low:
            ms = 91 if self.btree_created else 6120
            rows = 1
        else:
            ms = random.randint(2, 40)
            rows = random.randint(1, 500)
        bar = C.BGREEN if ms < 200 else C.BRED
        print(f"{C.GREY}   ({rows} rows){C.RESET}  "
              f"{bar}Time: {ms}.{random.randint(100, 999)} ms{C.RESET}")
        if ms > 1000:
            warn("That query still reads the whole table. EXPLAIN it.")

    def show_activity(self):
        if self.deadlock_resolved:
            code_block("""
 pid  | state               | wait_event | query
------+---------------------+------------+--------------------------------
 4901 | active              |            | INSERT INTO orders ...
 4922 | active              |            | UPDATE orders SET total ...
""", "pg_stat_activity")
            ok("All sessions healthy. Writes flowing.")
            return
        code_block("""
 pid  | state               | wait_event      | xact_age | query
------+---------------------+-----------------+----------+------------------------------------------
 4821 | idle in transaction |                 | 00:41:17 | UPDATE orders SET total = ... WHERE id=9
 5102 | active              | Lock:transactionid | 00:39:50 | UPDATE orders SET total = ... WHERE id=9
 5311 | active              | Lock:tuple      | 00:22:05 | UPDATE orders SET status='paid' WHERE id=9
 5409 | active              | Lock:tuple      | 00:11:48 | DELETE FROM orders WHERE id = 9
""", "pg_stat_activity")
        warn("Note pid 4821: 'idle in transaction' for 41 minutes. It is "
             "doing NOTHING - but holding its locks.")

    def show_locks(self):
        if self.deadlock_resolved:
            info("pg_locks: no ungranted locks. Clean.")
            return
        code_block("""
 pid  | locktype      | granted | relation
------+---------------+---------+----------
 4821 | transactionid | t       | orders      <- HOLDS the lock
 5102 | transactionid | f       | orders      <- waits on 4821
 5311 | tuple         | f       | orders      <- waits on 5102
 5409 | tuple         | f       | orders      <- waits on 5311
""", "pg_locks")

    def handle_terminate(self, cmd):
        m = re.search(r"\(\s*(\d+)\s*\)", cmd)
        if not m:
            warn("Syntax: SELECT pg_terminate_backend(<pid>);")
            return
        pid = int(m.group(1))
        if self.deadlock_resolved:
            info(f"Backend {pid} not found (already clean).")
            return
        if pid == 4821:
            self.deadlock_resolved = True
            self.missions_done.add("M3")
            awarded = max(10 - 3 * self.deadlock_failed_kills, 4)
            self.points += awarded
            ok(f"pg_terminate_backend(4821) -> t. The zombie transaction "
               f"rolled back, its locks released. Pids 5102/5311/5409 "
               f"acquired their locks and completed within 2s. "
               f"M3 complete: +{awarded} pts.")
        elif pid in (5102, 5311, 5409):
            self.deadlock_failed_kills += 1
            alert(f"You terminated pid {pid} - a VICTIM. Its transaction "
                  f"rolled back (lost work for a customer), and the queue "
                  f"instantly re-formed behind the real culprit, which is "
                  f"still idle in transaction. (-3 pts on this mission)")
        else:
            warn(f"No backend with pid {pid}.")

    # ---- post-REPL design questions ---------------------------------------

    def mission_replica(self):
        section("MISSION M4: Read-replica architecture", C.BYELLOW)
        wrap("""
        Read traffic is 9x write traffic and analytics queries are
        starving OLTP. You will add two streaming read-replicas.
        """, indent=2)
        self.free_question(
            "Q - Name the key PRIMARY-side and STANDBY-side configuration "
            "(parameters/files) for streaming replication, and state the "
            "one consistency caveat you must warn the app team about.",
            [
                ("primary: wal_level = replica (WAL carries enough info)",
                 [r"wal_level\s*=?\s*replica", r"wal.?level"]),
                ("primary: max_wal_senders > 0 (+ replication slot / "
                 "pg_hba replication entry)",
                 [r"max_wal_senders", r"replication\s+slot", r"pg_hba"]),
                ("standby: hot_standby = on + primary_conninfo "
                 "(+ standby.signal)",
                 [r"hot_standby", r"primary_conninfo", r"standby\.signal"]),
                ("caveat: ASYNCHRONOUS by default -> replication lag, "
                 "read-your-own-writes can fail on replicas",
                 [r"lag", r"async", r"asynkron", r"read.?your.?own",
                  r"stale\s+read", r"eventual"]),
            ],
            points=10, threshold=2)
        post_mortem("Streaming Replication", """
        Postgres replication ships the Write-Ahead Log: every change is
        written to WAL before it touches data files (that is what makes
        crash recovery possible), so streaming those same WAL records to
        another server and replaying them yields a byte-identical replica.
        Primary side: wal_level=replica, max_wal_senders for the streaming
        processes, a replication slot so the primary retains WAL while a
        replica is briefly offline (and monitor that slot - an abandoned
        slot will fill your disk), plus a pg_hba.conf replication entry.
        Standby side: standby.signal + primary_conninfo, hot_standby=on so
        it serves read-only queries while replaying.

        The caveat that separates DBAs from disaster: default replication
        is ASYNCHRONOUS. The replica is typically milliseconds behind -
        but under load, seconds. A user who saves a profile (write to
        primary) and immediately reloads the page (read from replica) may
        see their old data: the read-your-own-writes anomaly. Solutions:
        route freshness-critical reads to the primary, sticky sessions
        after writes, or synchronous_commit/synchronous_standby_names for
        chosen transactions - paying write latency for the guarantee.
        Routing reads is an APPLICATION concern; the replica will not
        save you by itself.
        """)

    def mission_window(self):
        section("MISSION M5: The window-function query", C.BYELLOW)
        wrap("""
        Analytics request: 'For every customer, show their single LARGEST
        order: customer name, order id, total.' 12.4M orders - a
        correlated subquery per customer is not acceptable.
        """, indent=2)
        self.free_question(
            "Q - Write the SQL. (CTE + window function expected.)",
            [
                ("window function ranking: ROW_NUMBER()/RANK() ... OVER",
                 [r"row_number\s*\(\s*\)", r"\brank\s*\(\s*\)", r"\bover\s*\("]),
                ("PARTITION BY customer_id",
                 [r"partition\s+by\s+\w*customer"]),
                ("ORDER BY total DESC inside the window",
                 [r"order\s+by\s+\w*total\s+desc"]),
                ("filter to the top row (WHERE rn = 1) via CTE/subquery",
                 [r"=\s*1", r"\bwith\b", r"\bcte\b", r"qualify"]),
                ("JOIN customers for the name",
                 [r"join\s+customers", r"customers\s+c", r"c\.name",
                  r"customers\."]),
            ],
            points=12, threshold=3)
        info("Reference solution:")
        code_block("""
WITH ranked AS (
  SELECT o.id, o.customer_id, o.total,
         ROW_NUMBER() OVER (PARTITION BY o.customer_id
                            ORDER BY o.total DESC, o.id) AS rn
  FROM orders o
)
SELECT c.name, r.id AS order_id, r.total
FROM ranked r
JOIN customers c ON c.id = r.customer_id
WHERE r.rn = 1;
""", "sql")
        post_mortem("Window Functions & Top-N-per-Group", """
        'Top N per group' is the single most common analytics pattern and
        the canonical window-function use case. The naive correlated
        subquery (WHERE total = (SELECT max(total) ... WHERE customer_id =
        o.customer_id)) re-scans orders once per customer: 310k scans of a
        12.4M-row table. The window version makes ONE pass: PARTITION BY
        restarts the numbering per customer, ORDER BY total DESC makes the
        biggest order row 1, and the outer WHERE rn = 1 keeps it. Note
        the deliberate ', o.id' tiebreaker - ROW_NUMBER with a non-unique
        sort key is otherwise nondeterministic, and nondeterministic
        reports get you interesting meetings with finance.

        Know the trio: ROW_NUMBER (always unique), RANK (gaps after ties),
        DENSE_RANK (no gaps). And the GIN-vs-B-Tree lesson from M1 in one
        line: B-Tree indexes ORDERED SCALAR values (perfect for =, <, >,
        BETWEEN, ORDER BY); GIN is an inverted index over the ELEMENTS
        inside composite values (jsonb keys/values, arrays, full-text
        lexemes) - which is why @> needs GIN and created_at wants B-Tree.
        Choosing the index type from the OPERATOR is the skill.
        """)


# ---------------------------------------------------------------------------
# 8. ORCHESTRATOR
# ---------------------------------------------------------------------------


DANISH_SCALE = [
    (90, "12", "Fremragende - hire this person"),
    (78, "10", "Fortrinlig - very strong"),
    (60, "7", "God - solid, gaps remain"),
    (50, "4", "Jævn - passes, shaky"),
    (40, "02", "Tilstrækkelig - bare minimum"),
    (0, "00/-3", "Not yet - back to the runbooks"),
]


def final_report(results):
    banner("FINAL REPORT CARD", "Simulated exam board verdict", C.BMAGENTA)
    total = sum(r["points"] for r in results)
    total_max = sum(r["max"] for r in results) or 1
    for r in results:
        pct = 100 * r["points"] / r["max"] if r["max"] else 0
        bar_len = 24
        filled = int(bar_len * pct / 100)
        color = C.BGREEN if pct >= 60 else (C.BYELLOW if pct >= 40 else C.BRED)
        print(f"  {C.WHITE}{r['service']:<14}{C.RESET} "
              f"{color}{'#' * filled}{C.GREY}{'.' * (bar_len - filled)}{C.RESET} "
              f"{color}{r['points']:>3}/{r['max']:<3} ({pct:4.0f}%){C.RESET}")
    pct_total = 100 * total / total_max
    grade, verdict = "00/-3", ""
    for cutoff, g, v in DANISH_SCALE:
        if pct_total >= cutoff:
            grade, verdict = g, v
            break
    print()
    hr("=", C.BMAGENTA)
    print(f"{C.BMAGENTA}{C.BOLD}  TOTAL: {total}/{total_max} ({pct_total:.0f}%) "
          f"->  SIMULATED GRADE: {grade}  -  {verdict}{C.RESET}")
    hr("=", C.BMAGENTA)
    if pct_total < 90:
        wrap("""
        Re-run the weakest module. Mastery in this format means re-playing
        until the post-mortems contain nothing you did not already say
        yourself.
        """, indent=2, color=C.GREY)


def main():
    random.seed()
    banner("PRODUCTION INFERNO",
           "IT-Operations & Engineering Simulator - 4 isolated services "
           "behind a network bus", C.BCYAN)
    bus = NetworkBus()
    services = [ITDriftService(), FrontendService(),
                BackendService(), DatabaseService()]
    for svc in services:
        bus.register(svc.name, svc.handle)
    results = []
    menu = [
        ("1", "svc-itdrift", "IT-DRIFT (EXAM - June 23rd)  <- do this first"),
        ("2", "svc-frontend", "Next.js Frontend (internship)"),
        ("3", "svc-backend", "Spring Boot Backend (internship)"),
        ("4", "svc-database", "PostgreSQL Operations (internship)"),
        ("5", None, "Final report card + exit"),
    ]
    try:
        while True:
            section("MAIN MENU - choose a service to deploy into", C.BCYAN)
            for key, _, label in menu:
                print(f"   {C.BCYAN}[{key}]{C.RESET} {C.WHITE}{label}{C.RESET}")
            choice = ask_line("Select")
            target = next((s for k, s, _ in menu if k == choice), "absent")
            if target == "absent":
                warn("Pick 1-5.")
                continue
            if target is None:
                break
            response = bus.call(target, "run", {"player": "operator"})
            if response.get("status") == 200:
                body = response["body"]
                results = [r for r in results
                           if r["service"] != body["service"]]
                results.append(body)
                info(f"{body['service']} reported "
                     f"{body['points']}/{body['max']} pts over the bus.")
            else:
                alert(f"Service error: {response.get('error')}")
    except QuitGame:
        print(f"\n{C.GREY}  Session ended by operator.{C.RESET}")
    if results:
        final_report(results)
    else:
        print(f"{C.GREY}  No modules completed. The pager is still on.{C.RESET}")


if __name__ == "__main__":
    main()
