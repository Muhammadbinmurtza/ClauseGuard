"""ClauseGuard Streamlit UI — hackathon edition with live agents + negotiation copilot."""

import asyncio
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd

from clauseguard.agents.copilot import build_contract_context, run_copilot_sync
from clauseguard.agents.orchestrator import run_pipeline, set_event_callback
from clauseguard.config.settings import validate_config
from clauseguard.models.findings import RiskFinding, ScoredClause, Severity
from clauseguard.models.report import FinalReport
from clauseguard.tools.file_tools import extract_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = ["pdf", "txt", "docx"]

AGENT_NAMES = ["Extractor", "Classifier", "Risk Scorer", "Translator", "Reporter"]
AGENT_ICONS = {"running": "⚙️", "completed": "✅", "failed": "❌", "pending": "⏳"}

CUSTOM_CSS = """
<style>
    .stButton > button {
        width: 100%;
        border-radius: 12px;
        font-weight: 700;
        font-size: 16px;
        padding: 14px 28px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: #ffffff !important;
        border: none;
    }
    .stButton > button:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(102,126,234,0.4); }
    .stDownloadButton > button { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: #000 !important; font-weight: 700; }
    .stFileUploader section { border: 2px dashed #667eea !important; border-radius: 12px !important; padding: 1rem !important; }
    .stFileUploader section:hover { border-color: #8ab4f8 !important; background: rgba(102,126,234,0.05) !important; }
    .stProgress > div > div > div > div { background: linear-gradient(90deg, #667eea, #764ba2); }
    .stTabs [data-baseweb="tab"] {
        font-weight: 700;
        font-size: 1.1rem;
        padding: 12px 24px;
    }
    .stTabs [aria-selected="true"] {
        color: #ffffff !important;
        background: linear-gradient(135deg, #667eea, #764ba2) !important;
        border-radius: 10px 10px 0 0 !important;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        background: #0e1117;
        padding: 6px;
        border-radius: 12px;
    }
    .stTabs [data-baseweb="tab-panel"] {
        padding-top: 1.5rem;
    }
    .stExpander { border: none !important; }
    .stExpander > div:first-child { border-radius: 10px !important; }
    .copy-btn {
        background: #2a2a3a; color: #8ab4f8; border: 1px solid #444;
        padding: 6px 14px; border-radius: 6px; cursor: pointer;
        font-size: 0.8rem; font-weight: 600;
    }
</style>
"""

# ── Demo report builder ──

def _build_demo_report() -> FinalReport:
    """Build a pre-cached demo report with negotiation copilot content."""
    from clauseguard.models.clause import Clause, ClauseType

    demo_with_copilot: list[dict] = [
        {
            "text": "Recipient hereby irrevocably assigns to Company all inventions, discoveries, and intellectual property created during this Agreement and for 1 year after, regardless of whether created on Recipient's own time or equipment.",
            "ctype": "IP_ASSIGNMENT", "sev": "CRITICAL",
            "title": "IP Assignment of Personal Work",
            "reason": "Claims ownership of ALL creations including personal projects on personal time and equipment, extending 1 year after termination.",
            "plain": "You give the company ownership of everything you create — including personal side projects on your own time and equipment — for up to a year after you leave.",
            "action": "Demand a carve-out for inventions created on your own time using your own equipment.",
            "safer": "Employee assigns to Company all inventions directly related to Company's business and created during working hours using Company resources. Inventions created on Employee's own time using personal equipment, and unrelated to Company's business, remain the sole property of Employee.",
            "negotiation": "Hi, I've reviewed the IP clause and would like to request an adjustment to ensure personal projects created outside work hours remain mine. I've suggested alternative wording below. Would you be open to this change? Thanks!",
            "impacts": ["You may lose ownership of any side projects or startups you work on during employment", "The company could claim your open-source contributions made on weekends"],
        },
        {
            "text": "All disputes shall be resolved exclusively through binding arbitration. The parties waive any right to a trial by jury and waive the right to participate in any class action.",
            "ctype": "ARBITRATION", "sev": "CRITICAL",
            "title": "Mandatory Arbitration with Jury + Class Action Waiver",
            "reason": "Forces disputes into private arbitration, waives your constitutional right to a jury trial, and blocks class actions — all with no opt-out.",
            "plain": "You give up your right to sue in court or join a class-action lawsuit. All disputes go through private arbitration instead.",
            "action": "Add an opt-out clause for arbitration — preserve your right to go to court.",
            "safer": "Either party may opt out of binding arbitration by providing written notice within 30 days of signing. Nothing in this section prevents participation in class actions where permitted by law.",
            "negotiation": "Hi, I've reviewed the dispute resolution clause. I'd like to add an opt-out option for arbitration so both parties retain the right to choose their preferred forum. I've suggested language below. Does this work for you?",
            "impacts": ["If the company violates your rights, you cannot sue them in a public court", "You cannot join with other affected parties in a class action — you must fight alone"],
        },
        {
            "text": "For 18 months following termination, Recipient shall not engage in any business competitive with Company, anywhere in the world.",
            "ctype": "NON_COMPETE", "sev": "HIGH",
            "title": "Worldwide Non-Compete — 18 Months",
            "reason": "18-month ban on working for ANY competitor worldwide with no geographic limitation tied to Company's actual operations.",
            "plain": "You cannot work for any competitor anywhere in the world for 18 months after this agreement ends — even if the company doesn't operate in that region.",
            "action": "Reduce duration to 12 months and limit scope to regions where Company actually does business.",
            "safer": "For 12 months following termination, Recipient shall not provide services to direct competitors of Company within the specific metro areas where Company has active business operations.",
            "negotiation": "Hi, the non-compete clause is quite broad — it covers the entire world for 18 months. I'd suggest narrowing the scope to 12 months within regions where the company actually operates. I've drafted alternative language below.",
            "impacts": ["You may be unable to work in your industry anywhere in the world for 18 months after leaving", "Relocating to a new city won't help — the restriction is global"],
        },
        {
            "text": "This Agreement shall automatically renew for successive 1-year terms unless either party provides written notice at least 90 days prior.",
            "ctype": "AUTO_RENEWAL", "sev": "MEDIUM",
            "title": "Auto-Renewal with 90-Day Notice",
            "reason": "Auto-renews annually. 90-day notice period is longer than standard and easy to miss.",
            "plain": "This agreement renews automatically every year. You must give 90 days written notice to cancel — miss the deadline and you're locked in.",
            "action": "Reduce notice period to 30 days or request automatic email reminders.",
            "safer": "", "negotiation": "", "impacts": [],
        },
        {
            "text": "Recipient agrees to hold all Confidential Information in strict confidence.",
            "ctype": "NDA", "sev": "LOW",
            "title": "Standard Confidentiality Obligation",
            "reason": "Standard NDA language requiring reasonable care — no unusual provisions.",
            "plain": "You must keep the company's confidential information secret and only use it as authorized.",
            "action": "No action needed — standard boilerplate.",
            "safer": "", "negotiation": "", "impacts": [],
        },
        {
            "text": "This Agreement shall be governed by the laws of the State of New York.",
            "ctype": "GOVERNING_LAW", "sev": "LOW",
            "title": "Standard Governing Law",
            "reason": "Standard choice-of-law clause selecting New York — common in contracts.",
            "plain": "This agreement is governed by New York law, and disputes must be handled in New York courts.",
            "action": "No action needed unless you are far from New York.",
            "safer": "", "negotiation": "", "impacts": [],
        },
        {
            "text": "This Agreement constitutes the entire agreement between the parties.",
            "ctype": "OTHER", "sev": "INFO",
            "title": "Standard Entire Agreement Clause",
            "reason": "Standard integration clause confirming this is the complete agreement.",
            "plain": "This document is the complete and final agreement between you and the company.",
            "action": "No action needed — standard boilerplate.",
            "safer": "", "negotiation": "", "impacts": [],
        },
    ]

    scored = []
    for i, d in enumerate(demo_with_copilot, 1):
        clause = Clause(id=i, raw_text=d["text"], plain_english=d["plain"],
                        clause_type=ClauseType(d["ctype"]),
                        section_heading=d["ctype"].replace("_", " "), position=i, confidence_score=0.95)
        finding = RiskFinding(clause_id=i, severity=Severity(d["sev"]), risk_title=d["title"],
                              risk_reason=d["reason"], recommended_action=d["action"],
                              safer_clause_version=d["safer"], negotiation_message=d["negotiation"],
                              impact_scenarios=d["impacts"])
        scored.append(ScoredClause(clause=clause, finding=finding))

    crit = sum(1 for s in scored if s.finding.severity == Severity.CRITICAL)
    high = sum(1 for s in scored if s.finding.severity == Severity.HIGH)
    med = sum(1 for s in scored if s.finding.severity == Severity.MEDIUM)
    low = sum(1 for s in scored if s.finding.severity == Severity.LOW)
    raw = (crit * 10 + high * 7 + med * 4 + low * 1) / len(scored)
    overall = round(min(raw, 10.0), 1)

    return FinalReport(
        contract_name="sample_nda.txt (Demo)",
        generated_at=datetime.now(),
        summary={"total_clauses": len(scored), "critical_count": crit, "high_count": high,
                 "medium_count": med, "low_count": low, "overall_score": overall, "contract_type": "NDA"},
        top_3_actions=[
            "Demand a carve-out for inventions created on your own time using your own equipment.",
            "Add an opt-out clause for arbitration — preserve your right to go to court.",
            "Reduce non-compete to 12 months with geographic scope tied to actual operations.",
        ],
        scored_clauses=scored,
        markdown_report="",
        processed_normally=False,
    )


def _load_demo_report() -> None:
    st.session_state.report = _build_demo_report()
    st.session_state.error = None
    st.session_state.uploaded_filename = "sample_nda.txt"
    # Build raw text from demo clauses for copilot context
    demo_raw = ""
    for sc in st.session_state.report.scored_clauses:
        heading = sc.clause.section_heading or ""
        text = sc.clause.raw_text
        demo_raw += f"{heading}\n{text}\n\n" if heading else f"{text}\n\n"
    st.session_state.copilot_raw_text = demo_raw.strip()
    st.rerun()


def _load_guided_demo() -> None:
    st.session_state.guided_demo = True
    _load_demo_report()


# ── Session state ──

def _init_session_state() -> None:
    defaults = {
        "report": None, "error": None, "analyzing": False,
        "uploaded_filename": None, "uploaded_bytes": None,
        "agent_statuses": {a: "pending" for a in AGENT_NAMES},
        "agent_messages": {a: "" for a in AGENT_NAMES},
        "guided_demo": False, "demo_step": 0,
        "copilot_messages": [], "copilot_context": "", "copilot_raw_text": "",
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


# ── Live agent event handler ──

def _on_agent_event(agent: str, status: str, details: dict) -> None:
    st.session_state.agent_statuses[agent] = status
    st.session_state.agent_messages[agent] = details.get("message", "")


# ── Analysis runner ──

def _run_analysis() -> None:
    file_bytes = st.session_state.uploaded_bytes
    filename = st.session_state.uploaded_filename
    try:
        validate_config()
    except ValueError as e:
        st.session_state.error = str(e)
        st.session_state.analyzing = False
        return

    # Reset agent statuses
    for a in AGENT_NAMES:
        st.session_state.agent_statuses[a] = "pending"
        st.session_state.agent_messages[a] = ""

    set_event_callback(_on_agent_event)

    progress_bar = st.progress(0)
    status_text = st.empty()
    agent_panel = st.empty()

    try:
        status_text.markdown("<h3 style='color:#fff'>🔍 Reading file...</h3>", unsafe_allow_html=True)
        raw_text = extract_text(file_bytes, filename)
        st.session_state.copilot_raw_text = raw_text
        status_text.markdown("<h3 style='color:#8ab4f8'>🤖 Running AI analysis pipeline...</h3>", unsafe_allow_html=True)

        def _render_agent_panel():
            rows = ""
            for a in AGENT_NAMES:
                s = st.session_state.agent_statuses[a]
                icon = AGENT_ICONS.get(s, "⏳")
                msg = st.session_state.agent_messages.get(a, "")
                color = "#55dd55" if s == "completed" else "#ff4444" if s == "failed" else "#ffaa44" if s == "running" else "#666"
                rows += f"<tr><td style='padding:8px 12px'>{icon}</td><td style='padding:8px 12px;color:{color};font-weight:600'>{a}</td><td style='padding:8px 12px;color:#aaa;font-size:0.85rem'>{msg}</td></tr>"
            return f"<div style='background:#1a1a2e;border-radius:12px;padding:1rem;border:1px solid #333'><table style='width:100%'>{rows}</table></div>"

        agent_panel.markdown(_render_agent_panel(), unsafe_allow_html=True)

        # Run pipeline — updates agent statuses via callback as each step runs
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(run_pipeline(raw_text, filename))
        finally:
            loop.close()

        for a in AGENT_NAMES:
            if st.session_state.agent_statuses[a] == "pending":
                st.session_state.agent_statuses[a] = "completed"
                st.session_state.agent_messages[a] = "OK"
        agent_panel.markdown(_render_agent_panel(), unsafe_allow_html=True)

        progress_bar.progress(1.0)
        status_text.markdown("<h3 style='color:#55dd55'>✅ Analysis complete!</h3>", unsafe_allow_html=True)
        st.session_state.report = report
        st.session_state.error = None

    except ValueError as e:
        st.session_state.error = f"Could not process: {e}"
    except Exception as e:
        st.session_state.error = "An unexpected error occurred. Try again."
        logger.error("Analysis error: %s", e)
    finally:
        st.session_state.analyzing = False
        progress_bar.empty()
        status_text.empty()
        agent_panel.empty()
        st.rerun()


# ── Severity helpers ──

SEVERITY_STYLE = {
    Severity.CRITICAL: {"badge": "🔴 CRITICAL", "border": "#ff4444", "bg": "rgba(255,68,68,0.12)", "color": "#ff6666"},
    Severity.HIGH:     {"badge": "🟠 HIGH",     "border": "#ff8c00", "bg": "rgba(255,140,0,0.12)",  "color": "#ffaa44"},
    Severity.MEDIUM:   {"badge": "🟡 MEDIUM",   "border": "#ffd700", "bg": "rgba(255,215,0,0.12)",  "color": "#ffdd55"},
    Severity.LOW:      {"badge": "🟢 LOW",      "border": "#32cd32", "bg": "rgba(50,205,50,0.12)",   "color": "#55dd55"},
    Severity.INFO:     {"badge": "ℹ️ INFO",      "border": "#1e90ff", "bg": "rgba(30,144,255,0.08)",  "color": "#55aaff"},
}


# ── Fallback generators for negotiation copilot ──

def _generate_fallback_safer(sc: ScoredClause) -> str:
    ctype = sc.clause.clause_type.value
    fallbacks = {
        "IP_ASSIGNMENT": "Employee assigns only inventions directly related to Company's business, created during working hours using Company resources. Personal projects remain Employee's property.",
        "ARBITRATION": "Either party may opt out of arbitration within 30 days. Both parties retain the right to bring claims in court.",
        "NON_COMPETE": "Non-compete limited to 12 months within specific metro areas where Company operates.",
        "AUTO_RENEWAL": "Agreement renews only with mutual written consent. No automatic renewal.",
        "TERMINATION": "Either party may terminate with 30 days written notice.",
        "INDEMNIFICATION": "Indemnification limited to direct damages caused by negligence or willful misconduct.",
        "LIABILITY_CAP": "Liability capped at the greater of fees paid or $10,000.",
        "DATA_SHARING": "Data shared only with explicit opt-in consent, revocable at any time.",
        "GOVERNING_LAW": "Governing law set to user's home state with optional mediation.",
        "PAYMENT": "Payment due net-30 after invoice receipt. Late fees capped at 5% annually.",
    }
    return fallbacks.get(ctype, "Request a mutual agreement: both parties share rights and obligations equally. Remove one-sided provisions.")


def _generate_fallback_message(sc: ScoredClause) -> str:
    topic = sc.clause.section_heading or sc.clause.clause_type.value.replace("_", " ").title()
    safer = sc.finding.safer_clause_version or _generate_fallback_safer(sc)
    return (
        f"Hi,\n\nI've reviewed the contract and would like to discuss the {topic} clause. "
        f"I'd suggest the following adjustment:\n\n'{safer}'\n\n"
        f"This ensures both parties are treated fairly. Would you be open to this change?\n\nThanks!"
    )


def _build_safer_contract(report: FinalReport) -> str:
    """Build a full rewritten contract with all risky clauses replaced by safer versions."""
    lines: list[str] = []
    lines.append(f"# SAFER VERSION — {report.contract_name}")
    lines.append(f"# Auto-generated by ClauseGuard — replaces {report.summary.critical_count + report.summary.high_count} high-risk clauses")
    lines.append(f"# Original risk score: {report.summary.overall_score}/10")
    lines.append("")

    for i, sc in enumerate(report.scored_clauses, 1):
        safer = sc.finding.safer_clause_version
        sev = sc.finding.severity

        if safer and sev in (Severity.CRITICAL, Severity.HIGH):
            lines.append(f"# ── Replaced: {sc.finding.severity.value} Risk — {sc.finding.risk_title} ──")
            lines.append(f"# Original:")
            for orig_line in sc.clause.raw_text.split("\n"):
                lines.append(f"#   {orig_line.strip()}")
            lines.append("")
            lines.append(f"{i}. {sc.clause.section_heading or 'CLAUSE'}. {safer}")
            lines.append("")
        else:
            lines.append(f"{i}. {sc.clause.section_heading or 'CLAUSE'}. {sc.clause.raw_text.strip()}")
            lines.append("")

    return "\n".join(lines)


# ════════════════════ UI STARTS HERE ════════════════════

st.set_page_config(page_title="ClauseGuard — AI Contract Risk Analyzer", page_icon="🛡️", layout="wide", initial_sidebar_state="expanded")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
_init_session_state()

# ── Hero ──

hero_l, hero_r = st.columns([3, 1])
with hero_l:
    st.markdown("""<div style="background:linear-gradient(135deg,#1e3a5f 0%,#2a5298 100%);padding:1.5rem 2rem;border-radius:16px">
        <h1 style="margin:0;color:#fff;font-size:2.2rem">🛡️ ClauseGuard</h1>
        <p style="margin:0.25rem 0 0 0;color:#c8d8f0;font-size:1.1rem">AI-Powered Contract Clause Risk Analyzer</p>
    </div>""", unsafe_allow_html=True)
with hero_r:
    st.markdown("<br>", unsafe_allow_html=True)
    dc1, dc2 = st.columns(2)
    with dc1:
        if st.button("⚡ Instant Demo", use_container_width=True, help="See a pre-analyzed NDA report instantly"):
            _load_demo_report()
    with dc2:
        if st.button("🎬 Guided Tour", use_container_width=True, help="Walk through a demo with highlights"):
            _load_guided_demo()

# ── Risk banner (appears when report exists) ──

if st.session_state.report:
    r = st.session_state.report
    s = r.summary
    total_risky = s.critical_count + s.high_count
    if total_risky > 0:
        st.warning(f"⚠️ **This contract has {total_risky} HIGH-RISK clause(s)** — review carefully before signing", icon="⚠️")

# ── Main layout ──

uploaded_file = st.file_uploader("Choose a contract file", type=ALLOWED_EXTENSIONS, help="PDF, TXT, DOCX • Max 10MB", key="file_uploader")

if uploaded_file is not None:
    fb = uploaded_file.read()
    st.session_state.uploaded_filename = uploaded_file.name
    st.session_state.uploaded_bytes = fb
    if len(fb) > MAX_FILE_SIZE_BYTES:
        st.error(f"File too large ({len(fb)/1024/1024:.1f}MB). Max {MAX_FILE_SIZE_MB}MB.")
    else:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.success(f"**{uploaded_file.name}** loaded — `{len(fb)/1024:.1f} KB`")
        with c2:
            if st.button("🔍 Analyze Contract", type="primary", disabled=st.session_state.analyzing, use_container_width=True):
                st.session_state.analyzing = True
                st.session_state.error = None
                st.session_state.guided_demo = False
                st.rerun()

if st.session_state.analyzing and st.session_state.uploaded_bytes:
    _run_analysis()

if st.session_state.error:
    st.error(st.session_state.error)

# ── Report area ──

if st.session_state.report:
    report = st.session_state.report
    s = report.summary

    st.divider()

    # ── Issues Found Panel ──

    criticals = [sc for sc in report.scored_clauses if sc.finding.severity == Severity.CRITICAL]
    highs = [sc for sc in report.scored_clauses if sc.finding.severity == Severity.HIGH]
    mediums = [sc for sc in report.scored_clauses if sc.finding.severity == Severity.MEDIUM]
    all_issues = criticals + highs + mediums

    if all_issues:
        st.markdown("## 🔍 Issues Found")
        st.caption(f"{len(all_issues)} clauses need attention — {len(criticals)} critical, {len(highs)} high, {len(mediums)} medium")

        issue_cols = st.columns(min(len(all_issues), 3))
        for idx, sc in enumerate(all_issues):
            col_idx = idx % 3
            style = SEVERITY_STYLE.get(sc.finding.severity, SEVERITY_STYLE[Severity.INFO])
            with issue_cols[col_idx]:
                st.markdown(
                    f"""<div style="background:#1e1e2e;border-radius:12px;padding:1rem;margin:0.3rem 0;
                        border-top:3px solid {style['border']};border-left:1px solid #333;border-right:1px solid #333;border-bottom:1px solid #333">
                        <div style="font-weight:700;margin-bottom:0.3rem">{style['badge']}</div>
                        <div style="font-size:0.9rem;color:#e0e0e0;line-height:1.4;margin-bottom:0.5rem"><b>{sc.finding.risk_title}</b></div>
                        <div style="font-size:0.8rem;color:#aaa;line-height:1.4">{sc.finding.risk_reason[:120]}...</div>
                    </div>""",
                    unsafe_allow_html=True,
                )
        st.markdown("")

    # ── Tabs ──

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Risk Overview", "📋 All Clauses", "💬 Negotiation Copilot", "🤖 Chat Copilot"])

    # ═══ TAB 1: OVERVIEW ═══
    with tab1:
        col_a, col_b, col_c = st.columns([1, 2, 1])
        with col_a:
            score = s.overall_score
            sc = "#ff4444" if score >= 7 else "#ff8c00" if score >= 4 else "#32cd32"
            st.markdown(f"""<div style="background:#1e1e2e;border-radius:16px;padding:1.5rem;text-align:center;border:1px solid #333">
                <div style="font-size:0.8rem;color:#888;text-transform:uppercase;letter-spacing:2px">Risk Score</div>
                <div style="font-size:3.5rem;font-weight:900;color:{sc};line-height:1.1">{score}<span style="font-size:1.5rem;color:#666">/10</span></div>
                <div style="font-size:0.85rem;color:#aaa;margin-top:0.4rem">{s.critical_count}C · {s.high_count}H · {s.medium_count}M · {s.low_count}L</div>
            </div>""", unsafe_allow_html=True)
        with col_b:
            chart_data = pd.DataFrame({
                "Severity": ["Critical", "High", "Medium", "Low", "Info"],
                "Count": [s.critical_count, s.high_count, s.medium_count, s.low_count,
                          max(s.total_clauses - s.critical_count - s.high_count - s.medium_count - s.low_count, 0)],
            })
            st.bar_chart(chart_data.set_index("Severity"), use_container_width=True)
        with col_c:
            risky = s.critical_count + s.high_count + s.medium_count
            pct = (risky / s.total_clauses * 100) if s.total_clauses > 0 else 0
            st.markdown(f"""<div style="background:#1e1e2e;border-radius:12px;padding:1.25rem;text-align:center;border:1px solid #333;height:100%">
                <div style="font-size:0.75rem;color:#888;text-transform:uppercase;letter-spacing:1px">Needs Attention</div>
                <div style="font-size:2.5rem;font-weight:900;color:#ff8c00">{risky}<span style="font-size:1rem;color:#666">/{s.total_clauses}</span></div>
                <div style="font-size:0.85rem;color:#aaa">{pct:.0f}% of clauses</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("")
        st.markdown("### ⚡ Top 3 Actions Before Signing")
        if report.top_3_actions:
            for i, action in enumerate(report.top_3_actions, 1):
                colors = ["#ff4444", "#ff8c00", "#ffd700"]
                st.markdown(f"""<div style="background:#1e1e2e;border-radius:10px;padding:1rem 1.25rem;margin:0.4rem 0;
                    border-left:4px solid {colors[i-1]}">
                    <b style="color:#8ab4f8;font-size:1.1rem">{i}.</b>
                    <span style="margin-left:0.5rem;color:#e8e8e8">{action}</span></div>""", unsafe_allow_html=True)

        # Impact Simulation
        criticals = [sc for sc in report.scored_clauses if sc.finding.severity == Severity.CRITICAL]
        if criticals:
            st.markdown("")
            st.markdown("### ⚠️ What Could Happen If You Sign This?")
            st.caption("Realistic consequences based on these clause patterns.")
            for sc in criticals[:3]:
                scenarios = sc.finding.impact_scenarios
                if not scenarios:
                    scenarios = ["You may face significant legal or financial consequences from this clause."]
                st.markdown(f"**{sc.finding.risk_title}**")
                for scenario in scenarios:
                    st.markdown(f"<div style='background:rgba(255,68,68,0.08);border-left:3px solid #ff4444;padding:0.5rem 0.75rem;margin:0.2rem 0;border-radius:4px;font-size:0.9rem'>{scenario}</div>", unsafe_allow_html=True)

    # ═══ TAB 2: CLAUSES ═══
    with tab2:
        # Filters
        filter_cols = st.columns(5)
        show_crit = filter_cols[0].checkbox("🔴 Critical", value=True)
        show_high = filter_cols[1].checkbox("🟠 High", value=True)
        show_med  = filter_cols[2].checkbox("🟡 Medium", value=True)
        show_low  = filter_cols[3].checkbox("🟢 Low", value=False)
        show_info = filter_cols[4].checkbox("ℹ️ Info", value=False)

        visible = {Severity.CRITICAL: show_crit, Severity.HIGH: show_high,
                   Severity.MEDIUM: show_med, Severity.LOW: show_low, Severity.INFO: show_info}

        default_s = SEVERITY_STYLE[Severity.INFO]
        displayed = 0
        for sc in report.scored_clauses:
            sev = sc.finding.severity
            if not visible.get(sev, False):
                continue
            displayed += 1
            style = SEVERITY_STYLE.get(sev, default_s)

            with st.expander(f"{style['badge']} — {sc.finding.risk_title}", expanded=(sev in (Severity.CRITICAL, Severity.HIGH))):
                # Color-coded border wrapper
                st.markdown(f"""
                <div style="border-left:4px solid {style['border']};border-radius:0 8px 8px 0;padding-left:1rem;margin-bottom:0.5rem;background:{style['bg']}">
                </div>""", unsafe_allow_html=True)

                st.markdown(f"**📜 Original Text**")
                st.markdown(f"<div style='background:#2a2a3a;padding:0.75rem;border-radius:8px;font-family:monospace;font-size:0.9rem;line-height:1.6;color:#e8e8e8;white-space:pre-wrap'>{sc.clause.raw_text}</div>", unsafe_allow_html=True)

                if sc.clause.plain_english:
                    st.info(f"💬 {sc.clause.plain_english}")
                st.warning(f"⚠️ {sc.finding.risk_reason}")
                if sc.finding.recommended_action:
                    st.success(f"✅ {sc.finding.recommended_action}")

        if displayed == 0:
            st.info("Select severity levels above to view clauses.")

    # ═══ TAB 3: NEGOTIATION COPILOT ═══
    with tab3:
        st.markdown("### 💬 Negotiation Copilot")
        st.caption("For Critical and High-risk clauses — copy-paste ready messages and safer language to request.")

        high_risk = [sc for sc in report.scored_clauses if sc.finding.severity in (Severity.CRITICAL, Severity.HIGH)]
        if not high_risk:
            st.success("No Critical or High-risk clauses to negotiate — this contract looks reasonable!")
        else:
            for i, sc in enumerate(high_risk):
                style = SEVERITY_STYLE.get(sc.finding.severity, default_s)
                st.markdown(f"### {style['badge']} — {sc.finding.risk_title}")

                neg_l, neg_r = st.columns(2)
                with neg_l:
                    st.markdown("**⚠️ What You Signed**")
                    st.markdown(f"<div style='background:rgba(255,68,68,0.1);padding:0.75rem;border-radius:8px;border:1px solid #ff4444;font-size:0.85rem;line-height:1.6'>{sc.clause.raw_text[:400]}</div>", unsafe_allow_html=True)

                with neg_r:
                    st.markdown("**💡 What to Ask For Instead**")
                    safer = sc.finding.safer_clause_version
                    if not safer:
                        safer = _generate_fallback_safer(sc)
                    st.markdown(f"<div style='background:rgba(50,205,50,0.1);padding:0.75rem;border-radius:8px;border:1px solid #32cd32;font-size:0.85rem;line-height:1.6'>{safer}</div>", unsafe_allow_html=True)

                # Negotiation message
                neg_msg = sc.finding.negotiation_message
                if not neg_msg:
                    neg_msg = _generate_fallback_message(sc)
                st.markdown("**📧 Negotiation Message** *(Click to copy)*")
                st.code(neg_msg, language=None)

                # Impact scenarios
                if sc.finding.impact_scenarios:
                    st.markdown("**⚠️ If you don't negotiate this...**")
                    for impact in sc.finding.impact_scenarios:
                        st.markdown(f"- {impact}")

                st.divider()

        # Safe Contract Download (inside Negotiation tab)
        safe_contract = _build_safer_contract(report)
        st.markdown("### 📝 Your Safer Contract")
        st.caption("All Critical and High-risk clauses replaced with negotiated safer versions. Download and send to the other party.")
        st.download_button(
            "📥 Download Safer Contract (.txt)",
            data=safe_contract,
            file_name=f"safer_{report.contract_name}",
            mime="text/plain",
            use_container_width=True,
        )

    # ═══ TAB 4: CHAT COPILOT ═══
    with tab4:
        st.markdown("### 🤖 Chat Copilot")
        st.caption("Ask questions about your contract — the AI copilot has full context of every clause and its analysis.")

        # Build copilot context on first load (or when report changes)
        cache_key = id(report)
        if st.session_state.get("copilot_cache_key") != cache_key:
            raw_text = st.session_state.get("copilot_raw_text", "")
            st.session_state.copilot_context = build_contract_context(raw_text, report)
            st.session_state.copilot_cache_key = cache_key

        copilot_context = st.session_state.copilot_context

        # Display chat history
        if st.session_state.copilot_messages:
            for msg in st.session_state.copilot_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
        else:
            # Welcome message from copilot
            total_risky = report.summary.critical_count + report.summary.high_count
            if total_risky > 0:
                welcome = (
                    f"I've analyzed your contract and found **{total_risky} high-risk clause(s)** "
                    f"(score: **{report.summary.overall_score}/10**). "
                    "You can ask me to:\n\n"
                    "- Explain any clause in simple terms\n"
                    "- Tell you which clauses are risky and why\n"
                    "- Suggest safer wording for specific clauses\n"
                    "- Help you draft a negotiation message\n"
                    "- Describe what could happen if you sign as-is\n\n"
                    "What would you like to know?"
                )
            else:
                welcome = (
                    f"I've analyzed your contract and it looks reasonable (score: **{report.summary.overall_score}/10**). "
                    "You can ask me to explain any clause or check for potential issues. "
                    "What would you like to know?"
                )
            with st.chat_message("assistant"):
                st.markdown(welcome)
            st.session_state.copilot_messages = [{"role": "assistant", "content": welcome}]

        # Chat input
        if prompt := st.chat_input("Ask about this contract...", key="copilot_chat_input"):
            # Check we have context
            if not copilot_context:
                st.warning("No contract analysis available. Please analyze a contract first.")
            else:
                # Add user message
                st.session_state.copilot_messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                # Get assistant response
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        chat_history = st.session_state.copilot_messages[:-1]
                        response = run_copilot_sync(copilot_context, chat_history, prompt)
                        st.markdown(response)
                    st.session_state.copilot_messages.append({"role": "assistant", "content": response})

        # Clear chat button
        if st.session_state.copilot_messages and st.button("🗑️ Clear Chat", key="copilot_clear"):
            st.session_state.copilot_messages = []
            st.rerun()

    # ── Download ──

    st.download_button("📥 Download Report (.md)", data=report.markdown_report or "# Report\nRun analysis first.",
                       file_name=f"clauseguard_report_{report.contract_name.replace('.','_')}.md",
                       mime="text/markdown", use_container_width=True)
    st.caption(f"Generated {report.generated_at.strftime('%B %d, %Y at %H:%M')} • {s.contract_type} • {s.total_clauses} clauses")

# ── Sidebar ──

with st.sidebar:
    st.markdown("""<div style="background:#1e2a3a;border-radius:12px;padding:1.25rem;border:1px solid #3a4a5a">
        <h4 style="margin:0 0 0.5rem 0;color:#fff">🎯 How It Works</h4>
        <ol style="margin:0;padding-left:1.25rem;font-size:0.9rem;color:#ccc;line-height:2">
            <li>Upload any contract file</li>
            <li>5 AI agents analyze every clause</li>
            <li>Get a risk report with plain English</li>
            <li>Use Negotiation Copilot to fix issues</li>
            <li>Chat with AI Copilot for answers</li>
        </ol>
    </div>""", unsafe_allow_html=True)

    st.markdown("")
    st.markdown("""<div style="background:#1e2a3a;border-radius:12px;padding:1.25rem;border:1px solid #3a4a5a">
        <h4 style="margin:0 0 0.5rem 0;color:#fff">🤖 Agent Pipeline</h4>
        <div style="font-size:0.85rem;color:#ccc;line-height:2">
            <p style="margin:0.2rem 0"><b style="color:#8ab4f8">① Extractor</b> — Split into clauses</p>
            <p style="margin:0.2rem 0"><b style="color:#8ab4f8">② Classifier</b> — Label types</p>
            <p style="margin:0.2rem 0"><b style="color:#8ab4f8">③ Risk Scorer</b> — Rate severity</p>
            <p style="margin:0.2rem 0"><b style="color:#8ab4f8">④ Translator</b> — Plain English</p>
            <p style="margin:0.2rem 0"><b style="color:#8ab4f8">⑤ Reporter</b> — Compile report</p>
        </div>
    </div>""", unsafe_allow_html=True)

    if st.session_state.report:
        s = st.session_state.report.summary
        st.markdown("")
        st.metric("Overall Score", f"{s.overall_score}/10")
        for icon, label in [("🔴", "Critical"), ("🟠", "High"), ("🟡", "Medium"), ("🟢", "Low")]:
            count = getattr(s, f"{label.lower()}_count", 0)
            if count > 0:
                st.metric(f"{icon} {label}", count)
        st.divider()
        st.markdown(f"**Type:** {s.contract_type}")

    st.markdown("")
    st.markdown("""<div style="background:#1e2a3a;border-radius:12px;padding:1.25rem;border:1px solid #3a4a5a">
        <h4 style="margin:0 0 0.5rem 0;color:#fff">⚡ Powered by</h4>
        <p style="font-size:0.85rem;color:#ccc;margin:0;line-height:1.8">DeepSeek-V3 • AMD MI300X<br>OpenAI Agents SDK • Streamlit</p>
        <div style="margin-top:0.5rem;padding:0.3rem 0.5rem;background:#1a0533;border-radius:6px;border:1px solid #667eea;text-align:center;font-size:0.7rem;color:#aabbcc">🏷️ AMD Developer Hackathon 2025</div>
    </div>""", unsafe_allow_html=True)

