"""ClauseGuard Streamlit UI — redesigned modern SaaS edition."""
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

# ── Constants ────────────────────────────────────────────────────────────────

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = ["pdf", "txt", "docx"]

TAB_NAMES = ["📊  Overview", "📋  Clauses", "💬  Negotiation", "🤖  Chat Assistant"]
TAB_SESSION_KEY = "tab_selector_radio"

AGENT_NAMES = ["Extractor", "Classifier", "Risk Scorer", "Translator", "Reporter"]
AGENT_ICONS = {"running": "⚙️", "completed": "✅", "failed": "❌", "pending": "⏳"}
AGENT_STEP_NUMBERS = {"Extractor": "①", "Classifier": "②", "Risk Scorer": "③",
                       "Translator": "④", "Reporter": "⑤"}

SEVERITY_STYLE = {
    Severity.CRITICAL: {"badge": "🔴 CRITICAL", "border": "#ff4444", "bg": "rgba(255,68,68,0.12)", "color": "#ff6666", "tag_bg": "rgba(255,68,68,0.18)"},
    Severity.HIGH:     {"badge": "🟠 HIGH",     "border": "#ff8c00", "bg": "rgba(255,140,0,0.12)",  "color": "#ffaa44", "tag_bg": "rgba(255,140,0,0.15)"},
    Severity.MEDIUM:   {"badge": "🟡 MEDIUM",   "border": "#ffd700", "bg": "rgba(255,215,0,0.12)",  "color": "#ffdd55", "tag_bg": "rgba(255,215,0,0.12)"},
    Severity.LOW:      {"badge": "🟢 LOW",      "border": "#32cd32", "bg": "rgba(50,205,50,0.12)",   "color": "#55dd55", "tag_bg": "rgba(50,205,50,0.10)"},
    Severity.INFO:     {"badge": "ℹ️ INFO",      "border": "#1e90ff", "bg": "rgba(30,144,255,0.08)",  "color": "#55aaff", "tag_bg": "rgba(30,144,255,0.08)"},
}


def _check_model_connectivity() -> tuple[bool, str]:
    """Quick connectivity check against the configured model endpoint.

    Returns:
        (ok, error_message) — ok is True if the endpoint is reachable.
    """
    import asyncio
    from clauseguard.services.model_service import get_client
    from clauseguard.config.settings import MODEL_NAME

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            client = get_client()
            loop.run_until_complete(
                asyncio.wait_for(
                    client.models.list(),
                    timeout=10,
                )
            )
            return True, ""
        except asyncio.TimeoutError:
            return False, "Model endpoint timed out — the vLLM server may be offline or unreachable"
        except Exception as e:
            err = str(e)
            if "ConnectionRefusedError" in err or "Connection refused" in err or "ConnectError" in err:
                return False, f"Connection refused — vLLM server is not running at the configured BASE_URL"
            if "Name or service not known" in err or "getaddrinfo" in err.lower():
                return False, f"Cannot resolve host — check that the BASE_URL is correct"
            return False, f"Model endpoint error: {err[:120]}"
        finally:
            loop.close()
    except Exception as e:
        return False, f"Connectivity check failed: {str(e)[:120]}"

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM CSS
# ═══════════════════════════════════════════════════════════════════════════════

CUSTOM_CSS = """
<style>
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        font-size: 0.95rem;
        padding: 0.65rem 1.5rem;
        transition: all 0.2s ease;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(102,126,234,0.35);
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: #fff !important;
        border: none !important;
    }
    .stButton > button[kind="secondary"] {
        background: rgba(255,255,255,0.06) !important;
        color: #e0e0e0 !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
    }
    
    .stFileUploader section {
        border: 2px dashed #667eea !important;
        border-radius: 14px !important;
        padding: 1.5rem !important;
        background: rgba(102,126,234,0.03) !important;
        transition: all 0.25s ease;
    }
    .stFileUploader section:hover {
        border-color: #8ab4f8 !important;
        background: rgba(102,126,234,0.08) !important;
    }
    
    div[role="radiogroup"] {
        display: flex; gap: 4px;
        background: #0e1117; padding: 4px;
        border-radius: 14px; border: 1px solid rgba(255,255,255,0.06);
        margin-bottom: 1rem;
    }
    div[role="radiogroup"] label {
        flex: 1; text-align: center;
        padding: 10px 16px !important;
        border-radius: 10px;
        font-weight: 600; font-size: 0.92rem;
        color: #aaa; cursor: pointer;
        transition: all 0.2s ease;
    }
    div[role="radiogroup"] label:hover { background: rgba(255,255,255,0.04); }
    div[role="radiogroup"] label:has(input:checked) {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: #ffffff !important;
    }
    div[role="radiogroup"] input[type="radio"] {
        position: absolute; opacity: 0; width: 0; height: 0;
    }
    
    @media (max-width: 768px) {
        div[role="radiogroup"] label { padding: 8px 10px; font-size: 0.78rem; }
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        font-size: 0.95rem;
        padding: 10px 20px;
        border-radius: 10px;
        color: #aaa;
    }
    .stTabs [aria-selected="true"] {
        color: #ffffff !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border-radius: 10px !important;
    }
    
    .stExpander {
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 10px !important;
        margin-bottom: 0.3rem !important;
        overflow: hidden;
        transition: all 0.15s ease;
    }
    .stExpander:hover {
        border-color: rgba(255,255,255,0.1) !important;
    }
    .stExpander > div:first-child {
        border-radius: 10px !important;
        background: rgba(255,255,255,0.015);
    }
    
    .stChatMessage { border-radius: 12px !important; }
    
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #667eea, #764ba2) !important;
        border-radius: 4px;
    }
    
    [data-testid="stMetric"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 0.75rem 1rem;
    }
    [data-testid="stMetric"] label { font-weight: 500 !important; }
    
    .stCodeBlock { border-radius: 10px !important; }
    
    .cg-card {
        background: linear-gradient(145deg, #12121f 0%, #0e1117 100%);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        transition: border-color 0.2s ease;
    }
    .cg-card:hover { border-color: rgba(255,255,255,0.12); }
    
    .cg-badge {
        display: inline-block;
        padding: 0.25rem 0.7rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.4px;
        text-transform: uppercase;
    }
    
    @keyframes pulse-glow {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
    }
    .agent-running {
        animation: pulse-glow 1.4s ease-in-out infinite;
    }
    
    .cg-chip {
        display: inline-block;
        padding: 0.35rem 0.9rem;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 500;
        background: rgba(102,126,234,0.12);
        color: #8ab4f8;
        border: 1px solid rgba(102,126,234,0.2);
        cursor: pointer;
        margin: 0.2rem;
        transition: all 0.15s ease;
    }
    .cg-chip:hover {
        background: rgba(102,126,234,0.25);
        border-color: rgba(102,126,234,0.4);
    }
    
    @media (max-width: 768px) {
        .stTabs [data-baseweb="tab"] { padding: 8px 12px; font-size: 0.8rem; }
    }
</style>
"""

# ═══════════════════════════════════════════════════════════════════════════════
# DEMO REPORT BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def _build_demo_report() -> FinalReport:
    """Build a pre-cached demo report showcasing all features with realistic contract data."""
    from clauseguard.models.clause import Clause, ClauseType

    demo_clauses: list[dict] = [
        {
            "text": "Employee hereby irrevocably assigns to Company all inventions, discoveries, works of authorship, and intellectual property created or conceived by Employee, whether during working hours or on Employee's own time, using Company equipment or Employee's personal equipment, and whether or not related to Company's business. This obligation survives termination of employment for a period of two (2) years.",
            "ctype": "IP_ASSIGNMENT", "sev": "CRITICAL",
            "title": "Overbroad IP Assignment Covering Personal Work",
            "reason": "This clause claims ownership of ALL employee creations made at any time on any equipment, including unrelated personal side projects, and extends the obligation for 2 years after leaving the company — well beyond industry standard.",
            "plain": "You give the company full ownership of everything you ever create — including personal hobbies, side projects, and weekend work done on your own computer — even for two years after you quit or are fired.",
            "action": "Negotiate a strict carve-out limiting IP assignment to work directly related to company business, created during work hours using company resources only.",
            "safer": "Employee assigns to Company all inventions that (a) relate directly to Company's current or planned business, (b) are created during working hours, and (c) use Company resources. Inventions created on Employee's own time using personal equipment and unrelated to Company's business remain Employee's sole property. This obligation ends upon termination of employment.",
            "negotiation": "Hi [Name],\n\nI've reviewed the intellectual property clause and have a concern about its extremely broad scope. As written, it covers personal side projects, hobbies, and work done on my own time with my own equipment — even extending 2 years after I leave. That's well beyond what's standard.\n\nI've drafted an alternative below that protects the company's legitimate interests while respecting my personal creative freedom. The key change: it limits the scope to work actually related to the company's business, done during working hours, using company resources.\n\nWould you be open to this revision?\n\nThanks,\n[Your Name]",
            "impacts": ["You could lose ownership of a personal startup, app, or creative project you build on weekends", "The company could claim royalties or ownership of open-source contributions you make", "Even after quitting, anything you invent for 2 years could be claimed by your former employer"],
        },
        {
            "text": "Any and all disputes, claims, or controversies arising out of or relating to this Agreement shall be resolved exclusively through final and binding arbitration administered by the American Arbitration Association. The Parties hereby expressly waive any right to a trial by jury and waive any right to participate in or bring a class, collective, or representative action. The arbitrator shall have no authority to consolidate claims or conduct class-wide proceedings.",
            "ctype": "ARBITRATION", "sev": "CRITICAL",
            "title": "Mandatory Arbitration Forcing Waiver of All Court Rights",
            "reason": "This clause strips away your right to sue in court, forces mandatory private arbitration, waives your constitutional right to a jury trial, and blocks you from joining any class action — with zero opt-out provision.",
            "plain": "You cannot ever take the company to court. Any dispute — no matter how serious — goes through private arbitration that the company pays for and controls. You also give up your right to join a class-action lawsuit with others who may have been wronged the same way.",
            "action": "Demand an opt-out provision allowing either party to choose court over arbitration. Alternatively, remove the class action waiver entirely.",
            "safer": "Either party may elect to opt out of binding arbitration by providing written notice within thirty (30) days of signing this Agreement. Nothing in this section shall prevent any party from participating in a class, collective, or representative action where permitted by applicable law. Both parties retain the right to seek injunctive or equitable relief in a court of competent jurisdiction.",
            "negotiation": "Hi [Name],\n\nI've reviewed the dispute resolution section and have significant concerns about the mandatory arbitration clause. It completely removes my ability to go to court — even for serious disputes — and blocks class actions entirely.\n\nI'm not opposed to arbitration as an option, but forcing it as the ONLY option with no way out is too one-sided. I've drafted a revised version that adds a 30-day opt-out window (so both parties can choose) and preserves the right to join class actions where the law allows.\n\nThis creates a fair balance. Would you be open to this?\n\nBest,\n[Your Name]",
            "impacts": ["If the company steals your work or fails to pay you, you cannot sue in a public court — you must go through a private arbitrator they help select", "You face the company alone — you cannot pool resources with other employees who were treated the same way", "Arbitration decisions are nearly impossible to appeal, giving you no safety net if the arbitrator makes a mistake"],
        },
        {
            "text": "Employee expressly agrees that during the term of employment and for a period of eighteen (18) months following the termination of employment for any reason, Employee shall not, directly or indirectly, own, manage, operate, control, be employed by, consult for, or render services to any business that is competitive with Company, as determined by Company in its sole discretion, anywhere in the world.",
            "ctype": "NON_COMPETE", "sev": "HIGH",
            "title": "Worldwide Non-Compete with Unlimited Company Discretion",
            "reason": "This 18-month non-compete bans you from working for ANY business the company unilaterally deems 'competitive' — worldwide, with no geographic limit, and the company alone decides who counts as a competitor.",
            "plain": "You cannot work for any company anywhere in the world for 18 months after leaving — and your employer alone gets to decide which companies count as 'competitors.' Even a completely unrelated job could be blocked if the company says so.",
            "action": "Reduce duration to 12 months maximum, limit geographic scope to regions where the company actually operates, and define competitors objectively (not at the company's sole discretion).",
            "safer": "For a period of twelve (12) months following termination, Employee shall not provide services to entities that are direct competitors of Company, limited to the specific metropolitan areas and regions where Company has active and material business operations, and limited to services substantially similar to those Employee performed for Company.",
            "negotiation": "Hi [Name],\n\nThe non-compete clause is exceptionally broad — 18 months, worldwide, covering any business the company chooses to label as a competitor. This would make it nearly impossible for me to find work in my field after leaving.\n\nI've proposed a revised version that's far more reasonable: 12 months, limited to direct competitors (objectively defined), and restricted to regions where the company actually operates. This still protects your legitimate business interests without unfairly restricting my career.\n\nWould this work for you?\n\nThanks,\n[Your Name]",
            "impacts": ["You may be unable to work in your entire industry for a year and a half after leaving — regardless of where you live", "A company in a different country doing vaguely related work could trigger the restriction", "The 'sole discretion' language means the company can retroactively decide you violated it"],
        },
        {
            "text": "Company shall have no liability to Employee for any indirect, incidental, special, consequential, or punitive damages arising out of this Agreement, regardless of the theory of liability, even if Company has been advised of the possibility of such damages. In no event shall Company's total aggregate liability exceed the lesser of (a) $1,000 or (b) one month of Employee's base salary.",
            "ctype": "LIABILITY_CAP", "sev": "HIGH",
            "title": "Extremely Low Liability Cap with Unlimited Damage Waiver",
            "reason": "The company caps its liability at just $1,000 or one month's salary (whichever is lower) and completely waives all indirect, consequential, and punitive damages — even if they knowingly caused harm.",
            "plain": "No matter what the company does to you — even if they intentionally harm you — the most you can ever recover is $1,000 or one month's pay. You cannot claim any additional damages for lost opportunities, emotional distress, or other consequences.",
            "action": "Negotiate liability cap to at least 12 months' salary or the full value of the contract. Remove the blanket waiver of consequential damages for cases of willful misconduct.",
            "safer": "Company's total aggregate liability under this Agreement shall not exceed the greater of (a) twelve (12) months of Employee's base salary or (b) $50,000. This limitation shall not apply to damages arising from Company's willful misconduct, gross negligence, fraud, or violation of applicable law.",
            "negotiation": "Hi [Name],\n\nThe liability cap at $1,000 or one month's salary is extremely low — it basically means the company faces no meaningful consequences even for serious violations of the agreement. I'd like to propose a more balanced cap at 12 months' salary or $50,000, with an exception for willful misconduct and fraud.\n\nThis is standard for contracts like this and ensures both parties have real skin in the game. Let me know your thoughts.\n\nBest,\n[Your Name]",
            "impacts": ["If the company breaches the contract and costs you your career, the most you get is $1,000", "You cannot recover for lost job opportunities, relocation costs, or emotional distress caused by the company's actions"],
        },
        {
            "text": "Company may terminate this Agreement and Employee's engagement at any time, with or without cause, upon providing one (1) day written notice. Upon termination, Employee shall receive no severance, continuation of benefits, or compensation of any kind other than base salary earned through the date of termination.",
            "ctype": "TERMINATION", "sev": "HIGH",
            "title": "No-Notice At-Will Termination with Zero Severance",
            "reason": "The company can fire you with just 1 day notice for any reason — or no reason at all — and you walk away with absolutely nothing: no severance, no benefits continuation, no compensation of any kind.",
            "plain": "The company can fire you tomorrow with one day's notice and pay you nothing beyond what you already earned. No severance, no health insurance continuation, no transition support — you're on your own immediately.",
            "action": "Negotiate a minimum 30-day notice period (or pay in lieu) and at least 2-4 weeks of severance, especially for termination without cause.",
            "safer": "Either party may terminate this Agreement upon thirty (30) days written notice. In the event of termination by Company without cause, Employee shall receive severance equal to four (4) weeks of base salary and continuation of health benefits for thirty (30) days. Termination with cause requires written documentation of the specific cause.",
            "negotiation": "Hi [Name],\n\nI noticed the termination clause allows the company to end the relationship with essentially zero notice and provides no severance or benefits continuation whatsoever. This creates significant financial risk for me.\n\nI'd suggest a more balanced approach: 30 days' notice on both sides, plus a modest severance of 4 weeks' salary if terminated without cause. This is standard practice and ensures stability for both parties.\n\nWould you be open to discussing this?\n\nThanks,\n[Your Name]",
            "impacts": ["You could lose your job with no warning and no financial cushion whatsoever", "You immediately lose health insurance with no COBRA or continuation option provided", "The company can fire you for an arbitrary reason with no documentation required"],
        },
        {
            "text": "This Agreement shall automatically renew for successive one-year terms unless either party provides written notice of non-renewal at least ninety (90) days prior to the end of the then-current term.",
            "ctype": "AUTO_RENEWAL", "sev": "MEDIUM",
            "title": "Auto-Renewal with Long 90-Day Notice Window",
            "reason": "Contract auto-renews annually and requires 90-day notice to cancel — much longer than the standard 30-day notice. Easy to miss the window.",
            "plain": "This agreement renews automatically every year. You must give 90 days' written notice (3 months!) to cancel — miss that window and you're locked in for another full year.",
            "action": "Reduce notice period to 30 days and request automatic email reminders 45 days before each renewal.",
            "safer": "", "negotiation": "", "impacts": [],
        },
        {
            "text": "The Recipient shall not disclose any Confidential Information to any third party without prior written consent of the Disclosing Party. 'Confidential Information' means all information disclosed by the Disclosing Party, whether oral, written, or in any other form, regardless of whether it is marked 'confidential.' The obligation of confidentiality shall survive termination of this Agreement indefinitely.",
            "ctype": "NDA", "sev": "MEDIUM",
            "title": "Overly Broad and Perpetual Confidentiality Obligation",
            "reason": "Defines confidential information to include ALL information shared — even oral conversations and unmarked documents — and the obligation lasts forever with no expiration.",
            "plain": "Anything the company tells you — even casual conversations or unmarked documents — counts as confidential, and you must keep it secret forever. There's no time limit and no exception for information that becomes public.",
            "action": "Request that only written information marked 'confidential' be covered, and add a reasonable time limit (e.g., 3-5 years) or a public-domain exception.",
            "safer": "", "negotiation": "", "impacts": [],
        },
        {
            "text": "Employee agrees to indemnify, defend, and hold harmless Company and its officers, directors, employees, and agents from and against any and all claims, damages, losses, liabilities, costs, and expenses (including reasonable attorneys' fees) arising out of or related to Employee's performance under this Agreement, regardless of whether Company was negligent or at fault.",
            "ctype": "INDEMNIFICATION", "sev": "HIGH",
            "title": "One-Sided Indemnification Covering Company's Own Negligence",
            "reason": "You must pay for ALL legal costs and damages — even those caused by the company's own negligence — with no reciprocal obligation from the company. This exposes you to unlimited financial liability.",
            "plain": "If the company does something negligent and gets sued, you have to pay all their legal bills and any damages they owe — even though it was their fault. Meanwhile, the company has no obligation to cover you for anything.",
            "action": "Make indemnification mutual (both parties cover each other) and exclude claims arising from the other party's own negligence or misconduct.",
            "safer": "Each party shall indemnify and hold harmless the other party from claims arising from the indemnifying party's own negligence or willful misconduct. Neither party shall be required to indemnify the other for claims arising from the other party's own fault. This obligation is mutual and reciprocal.",
            "negotiation": "Hi [Name],\n\nThe indemnification clause is entirely one-sided — I'm responsible for covering the company's legal costs even when the company is at fault, but the company covers nothing for me. This creates potentially unlimited financial exposure.\n\nI've proposed a mutual version where each party covers claims arising from their own actions, not the other's. This is standard and fair. Can we discuss?\n\nThanks,\n[Your Name]",
            "impacts": ["You could be forced to pay hundreds of thousands in legal fees for a lawsuit caused by the company's own negligence", "Your personal assets (savings, home) could be at risk with no cap on liability"],
        },
        {
            "text": "The Recipient shall not collect, store, process, or transmit any personal data of third parties without obtaining prior express written consent and implementing reasonable security measures. Any data shared with third-party service providers must be governed by a written data processing agreement.",
            "ctype": "DATA_SHARING", "sev": "LOW",
            "title": "Standard Data Protection Clause",
            "reason": "Standard data protection language requiring consent and security measures before handling personal data — no unusual or risky provisions.",
            "plain": "You must get written permission and use proper security before handling anyone's personal data. This is standard practice and protects everyone involved.",
            "action": "No action needed — this is standard and reasonable.",
            "safer": "", "negotiation": "", "impacts": [],
        },
        {
            "text": "Invoices shall be submitted monthly and payment shall be made within sixty (60) days of receipt of a properly submitted invoice. Late payments shall accrue interest at a rate of 1.5% per month.",
            "ctype": "PAYMENT", "sev": "MEDIUM",
            "title": "Net-60 Payment Terms with High Late Interest",
            "reason": "Net-60 payment terms (2 months to get paid) are significantly longer than standard Net-30, and the 1.5% monthly late fee compounds to over 19% annually.",
            "plain": "You submit invoices monthly but the company has 60 days (2 months) to pay you. If they're late, they add 1.5% monthly interest — which sounds good but means you wait a long time for your money.",
            "action": "Negotiate Net-30 payment terms and reduce late interest to a standard rate (e.g., 8-10% annually).",
            "safer": "", "negotiation": "", "impacts": [],
        },
        {
            "text": "This Agreement shall be governed by and construed in accordance with the laws of the State of New York, without regard to its conflict of laws principles. Any legal action shall be brought exclusively in the state or federal courts located in New York County, New York.",
            "ctype": "GOVERNING_LAW", "sev": "LOW",
            "title": "Standard New York Governing Law and Venue",
            "reason": "Standard choice-of-law and venue clause selecting New York, a common jurisdiction for commercial contracts.",
            "plain": "This agreement is governed by New York law, and any court cases must be handled in New York courts — standard practice for many U.S. contracts.",
            "action": "No action needed unless you're located far from New York and would prefer a more convenient venue.",
            "safer": "", "negotiation": "", "impacts": [],
        },
        {
            "text": "If any provision of this Agreement is found to be invalid or unenforceable, the remaining provisions shall continue in full force and effect. This Agreement constitutes the entire agreement between the parties and supersedes all prior agreements, whether written or oral. No modification shall be effective unless in writing and signed by both parties.",
            "ctype": "OTHER", "sev": "INFO",
            "title": "Standard Severability and Entire Agreement",
            "reason": "Standard boilerplate provisions covering severability (invalid parts don't void the whole agreement), entire agreement (this document is the complete deal), and written modification requirement.",
            "plain": "Standard legal wrap-up: if one part of this contract is found invalid, the rest still stands. This document is the complete agreement, and any changes must be in writing and signed.",
            "action": "No action needed — these are standard boilerplate provisions found in virtually every contract.",
            "safer": "", "negotiation": "", "impacts": [],
        },
    ]

    scored = []
    for i, d in enumerate(demo_clauses, 1):
        clause = Clause(
            id=i,
            raw_text=d["text"],
            plain_english=d["plain"],
            clause_type=ClauseType(d["ctype"]),
            section_heading=d["ctype"].replace("_", " "),
            position=i,
            confidence_score=0.95,
        )
        finding = RiskFinding(
            clause_id=i,
            severity=Severity(d["sev"]),
            risk_title=d["title"],
            risk_reason=d["reason"],
            recommended_action=d["action"],
            safer_clause_version=d["safer"],
            negotiation_message=d["negotiation"],
            impact_scenarios=d["impacts"],
        )
        scored.append(ScoredClause(clause=clause, finding=finding))

    crit = sum(1 for s in scored if s.finding.severity == Severity.CRITICAL)
    high = sum(1 for s in scored if s.finding.severity == Severity.HIGH)
    med = sum(1 for s in scored if s.finding.severity == Severity.MEDIUM)
    low = sum(1 for s in scored if s.finding.severity == Severity.LOW)
    info = sum(1 for s in scored if s.finding.severity == Severity.INFO)
    total = len(scored)
    raw_score = (crit * 10 + high * 7 + med * 4 + low * 1) / total
    overall = round(min(raw_score, 10.0), 1)

    dt = datetime.now().strftime('%B %d, %Y at %H:%M')

    markdown = f"""# ClauseGuard Risk Analysis Report

**Contract:** sample_employment_agreement.txt (Demo)
**Type:** Employment
**Overall Risk Score:** {overall}/10
**Generated:** {dt}

---

## Executive Summary

This employment agreement contains **{crit} critical** and **{high} high-severity** risks that demand immediate attention before signing. The most severe issues involve an overly broad IP assignment clause that claims ownership of personal projects, mandatory arbitration waiving all court rights, and a worldwide non-compete with unlimited company discretion. We strongly recommend negotiating the top 3 actions below.

---

## Top 3 Actions Before Signing

1. **Restrict IP Assignment** — Demand a carve-out excluding personal projects made on your own time and equipment unrelated to company business.
2. **Add Arbitration Opt-Out** — Request a 30-day window to opt out of binding arbitration and preserve your right to go to court.
3. **Limit the Non-Compete** — Reduce duration to 12 months and restrict geographic scope to regions where the company actually operates.

---

## Risk Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | {crit} |
| 🟠 High | {high} |
| 🟡 Medium | {med} |
| 🟢 Low | {low} |
| ℹ️ Info | {info} |

**Total Clauses Analyzed:** {total}

---

## Clause-by-Clause Analysis

"""

    for sc in scored:
        emoji_map = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢", "INFO": "ℹ️"}
        emoji = emoji_map.get(sc.finding.severity.value, "⚪")
        markdown += f"""### {sc.clause.clause_type.value} — {emoji} {sc.finding.severity.value}

**Original Text:**
{sc.clause.raw_text}

**Plain English:**
{sc.clause.plain_english or 'N/A'}

**Risk Assessment:** {sc.finding.risk_reason}

**Recommended Action:** {sc.finding.recommended_action}

"""

        if sc.finding.safer_clause_version:
            markdown += f"**Safer Alternative:** {sc.finding.safer_clause_version}\n\n"
        if sc.finding.negotiation_message:
            markdown += f"**Negotiation Script:**\n\n{sc.finding.negotiation_message}\n\n"
        if sc.finding.impact_scenarios:
            markdown += "**Potential Consequences:**\n"
            for impact in sc.finding.impact_scenarios:
                markdown += f"- {impact}\n"
            markdown += "\n"
        markdown += "---\n\n"

    markdown += "\n*Generated by ClauseGuard AI • Powered by Qwen2.5 via vLLM on AMD • Not legal advice*\n"

    return FinalReport(
        contract_name="Sample Employment Agreement (Demo)",
        generated_at=datetime.now(),
        summary={
            "total_clauses": total,
            "critical_count": crit,
            "high_count": high,
            "medium_count": med,
            "low_count": low,
            "overall_score": overall,
            "contract_type": "Employment",
        },
        top_3_actions=[
            "Restrict IP assignment to work directly related to company business, created during work hours using company resources",
            "Add a 30-day opt-out window for binding arbitration to preserve your right to go to court",
            "Limit non-compete to 12 months in specific regions where the company has active operations",
        ],
        scored_clauses=scored,
        markdown_report=markdown,
        processed_normally=False,
    )


def _load_demo_report() -> None:
    st.session_state.report = _build_demo_report()
    st.session_state.error = None
    st.session_state.uploaded_filename = "sample_nda.txt"
    demo_raw = ""
    for sc in st.session_state.report.scored_clauses:
        heading = sc.clause.section_heading or ""
        text = sc.clause.raw_text
        demo_raw += f"{heading}\n{text}\n\n" if heading else f"{text}\n\n"
    st.session_state.copilot_raw_text = demo_raw.strip()
    st.session_state.active_tab = 0
    st.session_state.copilot_messages = []
    st.session_state.clause_ai_responses = {}
    st.session_state.generated_emails = {}
    st.session_state.copilot_cache_key = None
    st.rerun()


def _load_guided_demo() -> None:
    st.session_state.guided_demo = True
    st.session_state.demo_step = 0
    _load_demo_report()


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════════════════════

def _init_session_state() -> None:
    defaults = {
        "report": None,
        "error": None,
        "analyzing": False,
        "uploaded_filename": None,
        "uploaded_bytes": None,
        "agent_statuses": {a: "pending" for a in AGENT_NAMES},
        "agent_messages": {a: "" for a in AGENT_NAMES},
        "guided_demo": False,
        "demo_step": 0,
        "copilot_messages": [],
        "copilot_context": "",
        "copilot_raw_text": "",
        "copilot_cache_key": None,
        "clause_ai_responses": {},
        "pending_ai_query": None,
        "generated_emails": {},
        "active_tab": 0,
        "highlight_clause_id": None,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


# ═══════════════════════════════════════════════════════════════════════════════
# LIVE AGENT EVENT HANDLER
# ═══════════════════════════════════════════════════════════════════════════════

def _on_agent_event(agent: str, status: str, details: dict) -> None:
    st.session_state.agent_statuses[agent] = status
    st.session_state.agent_messages[agent] = details.get("message", "")


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSIS RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

def _run_analysis() -> None:
    file_bytes = st.session_state.uploaded_bytes
    filename = st.session_state.uploaded_filename
    try:
        validate_config()
    except ValueError as e:
        st.session_state.error = str(e)
        st.session_state.analyzing = False
        return

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

        status_text.markdown("<h3 style='color:#8ab4f8'>🔗 Testing model connection...</h3>", unsafe_allow_html=True)
        ok, conn_err = _check_model_connectivity()
        if not ok:
            st.session_state.error = f"Cannot connect to model API: {conn_err}"
            st.session_state.analyzing = False
            progress_bar.empty()
            status_text.empty()
            agent_panel.empty()
            st.rerun()
            return

        status_text.markdown("<h3 style='color:#8ab4f8'>🤖 Running AI analysis pipeline...</h3>", unsafe_allow_html=True)

        def _render_agent_panel():
            rows = ""
            for a in AGENT_NAMES:
                step = AGENT_STEP_NUMBERS.get(a, "")
                s = st.session_state.agent_statuses[a]
                icon = AGENT_ICONS.get(s, "⏳")
                msg = st.session_state.agent_messages.get(a, "")
                if s == "completed":
                    color = "#55dd55"
                    anim = ""
                elif s == "failed":
                    color = "#ff4444"
                    anim = ""
                elif s == "running":
                    color = "#ffaa44"
                    anim = " class='agent-running'"
                else:
                    color = "#666"
                    anim = ""
                rows += f"<tr{anim}><td style='padding:8px 12px;text-align:center;font-size:1.1rem'>{step}</td><td style='padding:8px 12px'>{icon}</td><td style='padding:8px 12px;color:{color};font-weight:600'>{a}</td><td style='padding:8px 12px;color:#aaa;font-size:0.85rem'>{msg}</td></tr>"
            return f"<div style='background:#1a1a2e;border-radius:14px;padding:1.25rem;border:1px solid rgba(255,255,255,0.08)'><table style='width:100%;border-collapse:collapse'><thead><tr><th style='padding:6px 12px;color:#888;font-size:0.7rem;text-transform:uppercase;letter-spacing:1px'>Step</th><th style='padding:6px 12px'></th><th style='padding:6px 12px;color:#888;font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;text-align:left'>Agent</th><th style='padding:6px 12px;color:#888;font-size:0.7rem;text-transform:uppercase;letter-spacing:1px;text-align:left'>Status</th></tr></thead><tbody>{rows}</tbody></table></div>"

        agent_panel.markdown(_render_agent_panel(), unsafe_allow_html=True)

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

        if report.summary.total_clauses == 0:
            logger.error("Pipeline produced 0 clauses — model API may be unreachable or returned errors")
            failed_agents = [
                a for a in AGENT_NAMES
                if st.session_state.agent_statuses.get(a) == "failed"
            ]
            if failed_agents:
                st.session_state.error = (
                    f"Analysis failed — the {failed_agents[0]} agent could not complete. "
                    "The model API may be unreachable or returned malformed responses. "
                    "Check that the vLLM endpoint is running at the configured BASE_URL."
                )
            else:
                st.session_state.error = (
                    "Analysis could not extract any clauses from the document. "
                    "The model may be unavailable or the document format may be unsupported. "
                    "Check your model endpoint configuration."
                )
            status_text.markdown("<h3 style='color:#ff4444'>❌ Analysis failed</h3>", unsafe_allow_html=True)
            st.session_state.report = None
            st.session_state.analyzing = False
            progress_bar.empty()
            status_text.empty()
            agent_panel.empty()
            st.rerun()
            return

        status_text.markdown("<h3 style='color:#55dd55'>✅ Analysis complete!</h3>", unsafe_allow_html=True)
        st.session_state.report = report
        st.session_state.error = None
        st.session_state.copilot_messages = []
        st.session_state.clause_ai_responses = {}
        st.session_state.generated_emails = {}

        if not report.processed_normally or report.summary.critical_count == 0 and report.summary.high_count == 0 and report.summary.medium_count == 0:
            st.session_state.error = (
                "Analysis completed but no significant risks were detected. "
                "The model responses may have been incomplete — review the "
                f"report ({report.summary.total_clauses} clauses analyzed) carefully."
            )

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


# ═══════════════════════════════════════════════════════════════════════════════
# FALLBACK GENERATORS FOR NEGOTIATION COPILOT
# ═══════════════════════════════════════════════════════════════════════════════

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
        "CONFIDENTIALITY": "Confidential information excludes publicly available data and independently developed knowledge.",
        "NON_SOLICITATION": "Non-solicitation limited to 12 months and applies only to employees directly worked with.",
        "FORCE_MAJEURE": "Neither party liable for delays due to circumstances beyond reasonable control, with prompt notice.",
        "SEVERABILITY": "If any provision is found unenforceable, remaining provisions stay in full effect.",
        "ASSIGNMENT": "Neither party may assign without written consent, not to be unreasonably withheld.",
        "WAIVER": "Failure to enforce any provision does not constitute waiver. Waivers must be in writing.",
        "SURVIVAL": "Confidentiality, indemnification, and payment obligations survive termination.",
        "NOTICE": "Notices effective upon email delivery with read receipt or 3 days after certified mail.",
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
    lines: list[str] = []
    lines.append(f"# SAFER VERSION — {report.contract_name}")
    lines.append(f"# Auto-generated by ClauseGuard — replaces {report.summary.critical_count + report.summary.high_count} high-risk clauses")
    lines.append(f"# Original risk score: {report.summary.overall_score}/10")
    lines.append(f"# Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}")
    lines.append("")

    replaced_count = 0
    for i, sc in enumerate(report.scored_clauses, 1):
        safer = sc.finding.safer_clause_version
        sev = sc.finding.severity

        if safer and sev in (Severity.CRITICAL, Severity.HIGH):
            replaced_count += 1
            lines.append(f"# {'─' * 70}")
            lines.append(f"# CLAUSE {i}: REPLACED — {sev.value} Risk — {sc.finding.risk_title}")
            lines.append(f"# {'─' * 70}")
            lines.append(f"# ORIGINAL (RISKY):")
            for orig_line in sc.clause.raw_text.split("\n"):
                lines.append(f"#   {orig_line.strip()}")
            lines.append(f"#")
            lines.append(f"# SAFER VERSION:")
            lines.append(f"{i}. {sc.clause.section_heading or 'CLAUSE ' + str(i)}")
            lines.append(f"   {safer}")
            lines.append("")
        else:
            heading = sc.clause.section_heading or f"CLAUSE {i}"
            lines.append(f"{i}. {heading}")
            lines.append(f"   {sc.clause.raw_text.strip()}")
            lines.append("")

    lines.append(f"# {'=' * 70}")
    lines.append(f"# END OF SAFER CONTRACT")
    lines.append(f"# {replaced_count} clauses replaced | {report.summary.total_clauses - replaced_count} left unchanged")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# UI HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def seats(n: int) -> str:
    if n <= 0:
        return "No parties"
    if n == 1:
        return "1 party"
    return f"{n} parties"


def _render_info_card(title: str, body: str, icon: str = "ℹ️", bg: str = "rgba(30,144,255,0.08)", border: str = "#1e90ff") -> str:
    return f"""<div style="background:{bg};border-left:4px solid {border};border-radius:4px 12px 12px 4px;padding:0.75rem 1rem;margin:0.4rem 0">
        <span style="font-size:0.85rem;font-weight:600;color:#ccc">{icon} {title}</span>
        <div style="font-size:0.82rem;color:#aaa;margin-top:0.25rem;line-height:1.5">{body}</div>
    </div>"""


def _render_info_card_raw(html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def _switch_to_chat_with_prompt(prompt_text: str) -> None:
    st.session_state.active_tab = 3
    st.session_state.pending_ai_query = prompt_text
    st.rerun()


def _render_single_clause_card(sc: ScoredClause, style: dict, show_actions: bool = True) -> None:
    s = style
    c = sc.clause
    f = sc.finding

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {s['bg']} 0%, rgba(20,22,30,0.6) 100%);
        border: 1px solid {s['border']}22;
        border-left: 4px solid {s['border']};
        border-radius: 0 12px 12px 0;
        padding: 1.25rem 1.25rem 0.75rem 1.25rem;
        margin-bottom: 0.5rem;
    ">
        <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.75rem">
            <span style="
                display:inline-flex;align-items:center;gap:4px;
                background:{s['tag_bg']};
                color:{s['color']};
                padding:0.25rem 0.75rem;
                border-radius:20px;
                font-size:0.73rem;
                font-weight:700;
                letter-spacing:0.4px;
                text-transform:uppercase;
                white-space:nowrap;
            ">{s['badge']}</span>
            <span style="font-weight:600;color:#e8e8e8;font-size:1rem;line-height:1.3">{f.risk_title}</span>
        </div>
        <div style="display:flex;gap:1rem;margin-bottom:0.6rem">
            <span style="color:#888;font-size:0.75rem">📂 {c.section_heading or ''}</span>
            <span style="color:#888;font-size:0.75rem">🏷️ {c.clause_type.value}</span>
            <span style="color:#666;font-size:0.75rem">Clause #{c.id}</span>
        </div>
    </div>""", unsafe_allow_html=True)

    with st.expander("📜 View Original Text"):
        st.markdown(f"<div style='background:#1c1d2a;padding:0.85rem;border-radius:8px;font-family:Consolas,monospace;font-size:0.88rem;line-height:1.65;color:#d0d0d0;white-space:pre-wrap'>{c.raw_text}</div>", unsafe_allow_html=True)

    if c.plain_english:
        st.markdown(f"""<div style="display:flex;gap:0.5rem;align-items:flex-start;margin:0.5rem 0;padding:0.6rem 0.85rem;background:rgba(30,144,255,0.07);border-radius:8px;border:1px solid rgba(30,144,255,0.12)">
            <span style="font-size:0.95rem;flex-shrink:0">💬</span>
            <span style="color:#c0cfe0;font-size:0.9rem;line-height:1.5">{c.plain_english}</span>
        </div>""", unsafe_allow_html=True)

    st.markdown(f"""<div style="display:flex;gap:0.5rem;align-items:flex-start;margin:0.5rem 0;padding:0.6rem 0.85rem;background:{s['bg']};border-radius:8px;border:1px solid {s['border']}18">
        <span style="font-size:0.95rem;flex-shrink:0">⚠️</span>
        <div>
            <div style="color:{s['color']};font-size:0.8rem;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:0.2rem">Risk</div>
            <div style="color:#d0d0d0;font-size:0.9rem;line-height:1.55">{f.risk_reason}</div>
        </div>
    </div>""", unsafe_allow_html=True)

    if f.recommended_action:
        st.markdown(f"""<div style="display:flex;gap:0.5rem;align-items:flex-start;margin:0.5rem 0;padding:0.6rem 0.85rem;background:rgba(50,205,50,0.06);border-radius:8px;border:1px solid rgba(50,205,50,0.12)">
            <span style="font-size:0.95rem;flex-shrink:0">✅</span>
            <span style="color:#b0d0b0;font-size:0.9rem;line-height:1.5">{f.recommended_action}</span>
        </div>""", unsafe_allow_html=True)

    if f.impact_scenarios:
        with st.expander("⚠️ What Could Happen If You Sign This"):
            for impact in f.impact_scenarios:
                st.markdown(f"<div style='background:rgba(255,68,68,0.06);padding:0.4rem 0.75rem;margin:0.15rem 0;border-radius:6px;border-left:3px solid {s['border']};font-size:0.85rem;color:#e0a0a0'>• {impact}</div>", unsafe_allow_html=True)

    if show_actions and f.severity not in (Severity.LOW, Severity.INFO):
        if st.button("✏️ Ask AI to Explain", key=f"explain_{c.id}", use_container_width=True):
            _switch_to_chat_with_prompt(f"Explain clause {c.id} ({f.risk_title}) in simple terms. What does this mean for me?")


# ═══════════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════════

def render_header() -> None:
    hero_l, hero_r = st.columns([3, 1])
    with hero_l:
        st.markdown("""<div style="background:linear-gradient(135deg,#1e3a5f 0%,#2a5298 100%);padding:1.5rem 2rem;border-radius:16px;margin-bottom:0.5rem">
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


# ═══════════════════════════════════════════════════════════════════════════════
# GUIDED DEMO TOUR
# ═══════════════════════════════════════════════════════════════════════════════

def _render_guided_tour() -> None:
    if not st.session_state.get("guided_demo"):
        return
    step = st.session_state.get("demo_step", 0)
    tour_steps = [
        {
            "title": "🎯 Welcome to ClauseGuard!",
            "body": "Let's walk through a sample NDA contract analysis. You'll see how 5 AI agents work together to identify risks, explain legal jargon, and help you negotiate better terms. Each agent has a specific role in the pipeline.",
            "tab": 0,
            "icon": "🎯",
        },
        {
            "title": "📊 Step 1: Risk Overview Dashboard",
            "body": "The **Overview tab** shows your contract's risk score, severity breakdown, and the top 3 actions you should take before signing. Check the bar chart to see how many clauses fall into each risk category. The risk score is calculated from 0 (safe) to 10 (extremely risky).",
            "tab": 0,
            "icon": "📊",
        },
        {
            "title": "📋 Step 2: Clause-by-Clause Deep Dive",
            "body": "Switch to the **Clauses tab** to drill into each clause. Critical and High-risk clauses are expanded by default so you see the most dangerous issues first. Each clause card shows: original legal text, plain English translation, the specific risk reason, and a recommended action.",
            "tab": 1,
            "icon": "📋",
        },
        {
            "title": "💬 Step 3: Negotiation Copilot",
            "body": "In the **Negotiation tab**, you'll find side-by-side comparisons: what you signed vs. what you should ask for instead. Each risky clause comes with a pre-written negotiation message and a safer alternative. You can also download a fully rewritten 'Safer Contract' with all high-risk clauses replaced.",
            "tab": 2,
            "icon": "💬",
        },
        {
            "title": "🤖 Step 4: AI Chat Assistant",
            "body": "The **Chat Assistant tab** lets you ask follow-up questions in plain English. The AI has full context of your entire contract and all clause analyses. Try questions like 'Summarize this contract' or 'What's the most dangerous clause and why?' Use the quick-action chips for common questions.",
            "tab": 3,
            "icon": "🤖",
        },
        {
            "title": "✅ You're Ready!",
            "body": "Now you know your way around ClauseGuard. Use the **Instant Demo** button anytime to revisit this tour, or upload your own contract to run a real analysis with the full 5-agent AI pipeline. Remember: always consult a qualified attorney for final legal review.",
            "tab": 0,
            "icon": "✅",
        },
    ]

    if step < len(tour_steps):
        ts = tour_steps[step]
        progress_pct = (step + 1) / len(tour_steps)
        with st.container():
            st.markdown(f"""<div style="background:linear-gradient(135deg,#1e3a5f 0%,#2a5298 100%);padding:1.25rem 1.5rem;border-radius:14px;margin:0.5rem 0;border:1px solid rgba(255,255,255,0.1)">
                <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.25rem">
                    <span style="font-size:1.5rem">{ts['icon']}</span>
                    <h3 style="margin:0;color:#fff;font-size:1.2rem">{ts['title']}</h3>
                </div>
                <p style="color:#c8d8f0;margin:0.5rem 0;line-height:1.6">{ts['body']}</p>
                <div style="background:rgba(255,255,255,0.1);border-radius:4px;height:4px;margin-top:0.75rem">
                    <div style="background:linear-gradient(90deg,#667eea,#764ba2);border-radius:4px;height:100%;width:{progress_pct*100:.0f}%"></div>
                </div>
                <div style="text-align:right;font-size:0.75rem;color:rgba(255,255,255,0.5);margin-top:0.25rem">Step {step + 1} of {len(tour_steps)}</div>
            </div>""", unsafe_allow_html=True)

            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                if step > 0:
                    if st.button("⬅️ Previous", key=f"tour_prev_{step}", use_container_width=True):
                        st.session_state.demo_step = step - 1
                        st.rerun()
            with c3:
                if st.button("Next ➡️" if step < len(tour_steps) - 1 else "✅ Finish Tour", key=f"tour_next_{step}", use_container_width=True):
                    if step < len(tour_steps) - 1:
                        st.session_state.demo_step = step + 1
                        tab_idx = tour_steps[step + 1]["tab"]
                        st.session_state.active_tab = tab_idx
                    else:
                        st.session_state.guided_demo = False
                    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# RISK BANNER
# ═══════════════════════════════════════════════════════════════════════════════

def render_risk_banner() -> None:
    if not st.session_state.report:
        return
    r = st.session_state.report
    s = r.summary
    total_risky = s.critical_count + s.high_count

    if total_risky >= 3:
        st.error(f"🚨 **HIGH ALERT — {total_risky} critical or high-risk clauses detected!** Review carefully before signing. We strongly recommend negotiating these terms.")
    elif total_risky > 0:
        st.warning(f"⚠️ **This contract has {total_risky} high-risk clause(s)** — review carefully before signing")
    elif s.medium_count > 0:
        st.info(f"ℹ️ **{s.medium_count} medium-risk clause(s) found** — this contract may need attention before signing")
    else:
        st.success("✅ **This contract looks clean** — no high or critical risk clauses detected. Still review all terms before signing.")


# ═══════════════════════════════════════════════════════════════════════════════
# ISSUES SUMMARY (displays before tabs)
# ═══════════════════════════════════════════════════════════════════════════════

def render_issues_summary() -> None:
    report = st.session_state.report
    criticals = [sc for sc in report.scored_clauses if sc.finding.severity == Severity.CRITICAL]
    highs = [sc for sc in report.scored_clauses if sc.finding.severity == Severity.HIGH]
    mediums = [sc for sc in report.scored_clauses if sc.finding.severity == Severity.MEDIUM]
    all_issues = criticals + highs + mediums

    if not all_issues:
        if not report.processed_normally:
            st.warning(
                "⚠️ **Analysis was incomplete** — the AI risk scorer could not evaluate these clauses. "
                "All clauses are marked as MEDIUM 'Needs Human Review'. "
                "This typically means the model API is having issues. Check your vLLM endpoint configuration."
            )
            return
        st.success("✅ No issues found — all clauses look reasonable. Use the tabs below to explore the full analysis.")
        return

    st.markdown("## 🔍 Issues Found")
    total_labels = []
    if criticals:
        total_labels.append(f"{len(criticals)} critical")
    if highs:
        total_labels.append(f"{len(highs)} high")
    if mediums:
        total_labels.append(f"{len(mediums)} medium")
    st.caption(f"{len(all_issues)} clauses need attention — {', '.join(total_labels)}")

    issue_cols = st.columns(min(len(all_issues), 3))
    for idx, sc in enumerate(all_issues):
        col_idx = idx % 3
        style = SEVERITY_STYLE.get(sc.finding.severity, SEVERITY_STYLE[Severity.INFO])
        with issue_cols[col_idx]:
            reason_preview = sc.finding.risk_reason[:120]
            if len(sc.finding.risk_reason) > 120:
                reason_preview += "..."
            st.markdown(
                f"""<div style="background:#1e1e2e;border-radius:12px;padding:1rem;margin:0.3rem 0;
                    border-top:3px solid {style['border']};border-left:1px solid #333;border-right:1px solid #333;border-bottom:1px solid #333">
                    <div style="font-weight:700;margin-bottom:0.3rem;font-size:0.8rem">{style['badge']}</div>
                    <div style="font-size:0.9rem;color:#e0e0e0;line-height:1.4;margin-bottom:0.5rem"><b>{sc.finding.risk_title}</b></div>
                    <div style="font-size:0.8rem;color:#aaa;line-height:1.4">{reason_preview}</div>
                </div>""",
                unsafe_allow_html=True,
            )
    st.markdown("")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

def render_overview_tab() -> None:
    report = st.session_state.report
    s = report.summary

    st.markdown("### 📊 Risk Score Dashboard")
    st.caption(f"Contract Type: **{s.contract_type}** • {s.total_clauses} clauses analyzed • {s.critical_count + s.high_count + s.medium_count} need attention")

    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_a:
        score = s.overall_score
        if score >= 7:
            sc_color = "#ff4444"
            label = "High Risk"
            bg_glow = "rgba(255,68,68,0.08)"
        elif score >= 4:
            sc_color = "#ff8c00"
            label = "Medium Risk"
            bg_glow = "rgba(255,140,0,0.06)"
        else:
            sc_color = "#32cd32"
            label = "Low Risk"
            bg_glow = "rgba(50,205,50,0.06)"
        st.markdown(f"""<div style="background:#1e1e2e;border-radius:16px;padding:1.5rem;text-align:center;border:1px solid #333;box-shadow:0 0 30px {bg_glow}">
            <div style="font-size:0.8rem;color:#888;text-transform:uppercase;letter-spacing:2px">Risk Score</div>
            <div style="font-size:3.5rem;font-weight:900;color:{sc_color};line-height:1.1">{score}<span style="font-size:1.5rem;color:#666">/10</span></div>
            <div style="font-size:0.85rem;color:{sc_color};margin-top:0.2rem;font-weight:600">{label}</div>
            <div style="font-size:0.82rem;color:#aaa;margin-top:0.5rem">{s.critical_count}C · {s.high_count}H · {s.medium_count}M · {s.low_count}L</div>
        </div>""", unsafe_allow_html=True)
    with col_b:
        max_val = max(s.critical_count, s.high_count, s.medium_count, s.low_count,
                      s.total_clauses - s.critical_count - s.high_count - s.medium_count - s.low_count, 1)
        chart_data = pd.DataFrame({
            "Severity": ["Critical", "High", "Medium", "Low", "Info"],
            "Count": [s.critical_count, s.high_count, s.medium_count, s.low_count,
                      max(s.total_clauses - s.critical_count - s.high_count - s.medium_count - s.low_count, 0)],
        })
        st.bar_chart(chart_data.set_index("Severity"), use_container_width=True, height=220)
    with col_c:
        risky = s.critical_count + s.high_count + s.medium_count
        pct = (risky / s.total_clauses * 100) if s.total_clauses > 0 else 0
        if pct >= 50:
            attn_color = "#ff4444"
            attn_label = "Review Urgently"
        elif pct >= 25:
            attn_color = "#ff8c00"
            attn_label = "Needs Review"
        else:
            attn_color = "#32cd32"
            attn_label = "Mostly Clean"
        st.markdown(f"""<div style="background:#1e1e2e;border-radius:12px;padding:1.25rem;text-align:center;border:1px solid #333;height:100%">
            <div style="font-size:0.75rem;color:#888;text-transform:uppercase;letter-spacing:1px">Needs Attention</div>
            <div style="font-size:2.5rem;font-weight:900;color:{attn_color}">{risky}<span style="font-size:1rem;color:#666">/{s.total_clauses}</span></div>
            <div style="font-size:0.85rem;color:{attn_color};font-weight:500">{attn_label}</div>
            <div style="font-size:0.8rem;color:#888;margin-top:0.25rem">{pct:.0f}% of clauses</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("")
    st.markdown("### ⚡ Top 3 Actions Before Signing")
    if report.top_3_actions:
        for i, action in enumerate(report.top_3_actions, 1):
            colors = ["#ff4444", "#ff8c00", "#ffd700"]
            emojis = ["①", "②", "③"]
            st.markdown(f"""<div style="background:#1e1e2e;border-radius:10px;padding:1rem 1.25rem;margin:0.4rem 0;
                border-left:4px solid {colors[i-1]}">
                <b style="color:#8ab4f8;font-size:1.1rem">{emojis[i-1]}</b>
                <span style="margin-left:0.5rem;color:#e8e8e8">{action}</span></div>""", unsafe_allow_html=True)
    else:
        st.info("No specific actions needed — this contract appears well-balanced.")

    criticals = [sc for sc in report.scored_clauses if sc.finding.severity == Severity.CRITICAL]
    if criticals:
        st.markdown("")
        st.markdown("### ⚠️ What Could Happen If You Sign This?")
        st.caption("Realistic AI-generated consequence scenarios based on these clause patterns. These are illustrative examples — consult an attorney for legal advice.")
        for idx, sc in enumerate(criticals[:3]):
            scenarios = sc.finding.impact_scenarios
            if not scenarios:
                scenarios = ["You may face significant legal or financial consequences from this clause."]
            st.markdown(f"**{idx + 1}. 🔴 {sc.finding.risk_title}**")
            for scenario in scenarios:
                st.markdown(f"<div style='background:rgba(255,68,68,0.08);border-left:3px solid #ff4444;padding:0.5rem 0.75rem;margin:0.2rem 0;margin-left:1rem;border-radius:4px;font-size:0.9rem;color:#e0a0a0'>{scenario}</div>", unsafe_allow_html=True)

    high_risks = [sc for sc in report.scored_clauses if sc.finding.severity == Severity.HIGH]
    if high_risks:
        st.markdown("")
        st.markdown("### 🟠 High-Risk Clauses at a Glance")
        for sc in high_risks:
            style = SEVERITY_STYLE[Severity.HIGH]
            reason_preview = sc.finding.risk_reason[:120]
            if len(sc.finding.risk_reason) > 120:
                reason_preview += "..."
            st.markdown(f"""<div style="background:{style['bg']};border-left:3px solid {style['border']};padding:0.6rem 0.9rem;margin:0.3rem 0;border-radius:4px">
                <b style="color:{style['color']}">{sc.finding.risk_title}</b>
                <span style="color:#aaa;font-size:0.85rem;margin-left:0.5rem">— {reason_preview}</span>
            </div>""", unsafe_allow_html=True)

    medium_risks = [sc for sc in report.scored_clauses if sc.finding.severity == Severity.MEDIUM]
    if medium_risks:
        st.markdown("")
        st.markdown("### 🟡 Medium-Risk Clauses")
        for sc in medium_risks:
            style = SEVERITY_STYLE[Severity.MEDIUM]
            reason_preview = sc.finding.risk_reason[:80]
            if len(sc.finding.risk_reason) > 80:
                reason_preview += "..."
            st.markdown(f"""<div style="background:{style['bg']};border-left:3px solid {style['border']};padding:0.5rem 0.8rem;margin:0.2rem 0;border-radius:4px;font-size:0.9rem">
                <b style="color:{style['color']}">{sc.finding.risk_title}</b>
                <span style="color:#999;margin-left:0.3rem">— {reason_preview}</span>
            </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: CLAUSES
# ═══════════════════════════════════════════════════════════════════════════════

def render_clauses_tab() -> None:
    report = st.session_state.report
    st.markdown("### 📋 Clause-by-Clause Analysis")
    st.caption("Each issue below shows the original legal text, plain-English translation, risk assessment, and recommended actions.")

    filter_cols = st.columns(5)
    show_crit = filter_cols[0].checkbox("🔴 Critical", value=True)
    show_high = filter_cols[1].checkbox("🟠 High", value=True)
    show_med  = filter_cols[2].checkbox("🟡 Medium", value=True)
    show_low  = filter_cols[3].checkbox("🟢 Low", value=False)
    show_info = filter_cols[4].checkbox("ℹ️ Info", value=False)

    visible = {Severity.CRITICAL: show_crit, Severity.HIGH: show_high,
               Severity.MEDIUM: show_med, Severity.LOW: show_low, Severity.INFO: show_info}

    default_s = SEVERITY_STYLE[Severity.INFO]
    issue_num = 0
    for sc in report.scored_clauses:
        sev = sc.finding.severity
        if not visible.get(sev, False):
            continue
        issue_num += 1
        style = SEVERITY_STYLE.get(sev, default_s)

        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:0.75rem;margin:1.5rem 0 0.75rem 0">
            <span style="
                background:{style['border']};
                color:#fff;
                min-width:2rem;height:2rem;
                border-radius:50%;
                display:inline-flex;align-items:center;justify-content:center;
                font-weight:800;font-size:0.9rem;
            ">#{issue_num}</span>
            <div style="background:linear-gradient(90deg, {style['border']}44 0%, transparent 100%);height:1px;flex:1"></div>
        </div>""", unsafe_allow_html=True)

        _render_single_clause_card(sc, style, show_actions=True)

    if issue_num == 0:
        st.info("Select severity levels above to view issues. Try enabling Critical and High to see the most important clauses that need your attention.")
    else:
        st.caption(f"Showing {issue_num} of {report.summary.total_clauses} clauses — use severity filters above to adjust view")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: NEGOTIATION
# ═══════════════════════════════════════════════════════════════════════════════

def _highlight_diff(original: str, safer: str) -> tuple[str, str]:
    original_span = f"<span style='background:rgba(255,68,68,0.20);padding:0 2px;border-radius:2px;text-decoration:line-through'>{original}</span>"
    safer_span = f"<span style='background:rgba(50,205,50,0.20);padding:0 2px;border-radius:2px;font-weight:600'>{safer}</span>"
    return original_span, safer_span


def generate_negotiation_email(sc: ScoredClause, recipient: str = "[Other Party]") -> str:
    topic = sc.clause.section_heading or sc.clause.clause_type.value.replace("_", " ").title()
    safer = sc.finding.safer_clause_version or _generate_fallback_safer(sc)
    risk_reason = sc.finding.risk_reason
    return (
        f"Subject: Proposed adjustment — {topic} clause\n\n"
        f"Hi {recipient},\n\n"
        f"I've reviewed the contract and have a concern about the {topic} clause.\n\n"
        f"My concern: {risk_reason}\n\n"
        f"I'd suggest the following alternative language to make this fair for both parties:\n\n"
        f'"{safer}"\n\n'
        f"Let me know your thoughts — I'm happy to discuss further.\n\n"
        f"Best regards"
    )


def _render_email_card(sc: ScoredClause, recipient: str = "[Other Party]") -> None:
    recipient_input = st.text_input("Recipient name", value=recipient, key=f"recipient_{sc.clause.id}")
    email_body = generate_negotiation_email(sc, recipient_input)
    st.markdown("**📧 Formal Email Draft**")
    st.code(email_body, language=None)
    col_copy, col_info = st.columns([1, 3])
    with col_copy:
        if st.button("📋 Copy to Clipboard", key=f"copy_email_{sc.clause.id}"):
            st.toast("Email copied!", icon="📋")
    with col_info:
        st.caption("Click the code block above to select all text, then Ctrl+C to copy")


def render_negotiation_tab() -> None:
    report = st.session_state.report
    default_s = SEVERITY_STYLE[Severity.INFO]

    st.markdown("### 💬 Negotiation Copilot")
    st.caption("Each risky clause shows what you signed vs. a safer alternative, side-by-side. Use the pre-written messages or generate a formal email to send to the other party.")

    negotiable = [sc for sc in report.scored_clauses if sc.finding.severity not in (Severity.LOW, Severity.INFO)]
    if not negotiable:
        st.success("✅ No actionable risks detected — this contract looks reasonable!")
    else:
        st.info(f"📋 **{len(negotiable)} clauses** flagged for negotiation below")

        for i, sc in enumerate(negotiable):
            style = SEVERITY_STYLE.get(sc.finding.severity, default_s)
            sev_label = sc.finding.severity.value

            st.markdown(f"""<div style="background:{style['bg']};border-left:4px solid {style['border']};padding:0.6rem 1rem;border-radius:4px 10px 10px 4px;margin:1.2rem 0 0.5rem 0">
                <span style="font-weight:700;color:{style['color']}">{style['badge']}</span>
                <span style="font-weight:600;color:#e0e0e0;margin-left:0.5rem">{sc.finding.risk_title}</span>
                <span style="color:#888;font-size:0.8rem;margin-left:0.8rem">Clause {sc.clause.id}</span>
            </div>""", unsafe_allow_html=True)

            st.markdown("**📋 Why This Matters**")
            st.markdown(f"<div style='color:#ccc;font-size:0.9rem;line-height:1.55;margin-bottom:0.75rem;padding:0.5rem 0.75rem;background:rgba(255,255,255,0.02);border-radius:8px'>{sc.finding.risk_reason}</div>", unsafe_allow_html=True)

            neg_l, neg_r = st.columns(2)
            with neg_l:
                st.markdown("**⚠️ Current Clause (Risky)**")
                text_to_show = sc.clause.raw_text[:500]
                if len(sc.clause.raw_text) > 500:
                    text_to_show += "..."
                st.markdown(f"<div style='background:rgba(255,68,68,0.08);padding:0.75rem;border-radius:8px;border:1px solid rgba(255,68,68,0.2);font-size:0.85rem;line-height:1.6;color:#e0e0e0'>{text_to_show}</div>", unsafe_allow_html=True)

            with neg_r:
                st.markdown("**💡 Safer Alternative**")
                safer = sc.finding.safer_clause_version
                if not safer:
                    safer = _generate_fallback_safer(sc)
                st.markdown(f"<div style='background:rgba(50,205,50,0.08);padding:0.75rem;border-radius:8px;border:1px solid rgba(50,205,50,0.2);font-size:0.85rem;line-height:1.6;color:#e0e0e0'>{safer}</div>", unsafe_allow_html=True)

            if sc.finding.recommended_action:
                st.markdown(f"**✅ Recommended:** {sc.finding.recommended_action}")

            neg_msg = sc.finding.negotiation_message
            if not neg_msg:
                neg_msg = _generate_fallback_message(sc)
            st.markdown("**📧 Quick Negotiation Message**")
            st.code(neg_msg, language=None)

            if sc.finding.impact_scenarios:
                st.markdown("**⚠️ Consequences of Not Negotiating**")
                for impact in sc.finding.impact_scenarios:
                    st.markdown(f"<div style='background:rgba(255,68,68,0.06);padding:0.35rem 0.75rem;margin:0.15rem 0;margin-left:0.5rem;border-radius:4px;font-size:0.85rem;color:#ff9999'>• {impact}</div>", unsafe_allow_html=True)

            with st.expander("📧 Generate Formal Email to Send"):
                _render_email_card(sc)

            if i < len(negotiable) - 1:
                st.divider()

    safe_contract = _build_safer_contract(report)
    with st.expander("📋 Preview Safer Contract"):
        preview_max = 3500
        preview_text = safe_contract[:preview_max]
        if len(safe_contract) > preview_max:
            preview_text += f"\n\n... (showing first {preview_max} chars of {len(safe_contract)} — download full contract at bottom of page)"
        st.code(preview_text, language=None)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4: CHAT ASSISTANT
# ═══════════════════════════════════════════════════════════════════════════════

def render_chat_tab() -> None:
    report = st.session_state.report
    st.markdown("### 🤖 Chat Assistant")
    st.caption("Ask questions about your contract in plain English. The AI has full context of every clause, risk assessment, and recommended action — all injected into this conversation automatically.")

    cache_key = id(report)
    if st.session_state.get("copilot_cache_key") != cache_key:
        raw_text = st.session_state.get("copilot_raw_text", "")
        st.session_state.copilot_context = build_contract_context(raw_text, report)
        st.session_state.copilot_cache_key = cache_key

    copilot_context = st.session_state.copilot_context

    if not st.session_state.copilot_messages:
        total_risky = report.summary.critical_count + report.summary.high_count
        if total_risky > 0:
            welcome = (
                f"I've analyzed your contract and found **{total_risky} high-risk clause(s)** "
                f"(risk score: **{report.summary.overall_score}/10**). "
                "You can ask me to:\n\n"
                "- Explain any clause in simple terms\n"
                "- Tell you which clauses are risky and why\n"
                "- Suggest safer wording for specific clauses\n"
                "- Help you draft a negotiation message\n"
                "- Describe what could happen if you sign as-is\n"
                "- Compare clauses to industry standards\n\n"
                "What would you like to know?"
            )
        else:
            welcome = (
                f"I've analyzed your contract and it looks reasonable (risk score: **{report.summary.overall_score}/10**). "
                "You can ask me to explain any clause, check for potential hidden issues, or compare terms to standard practices. "
                "What would you like to know?"
            )
        with st.chat_message("assistant"):
            st.markdown(welcome)
        st.session_state.copilot_messages = [{"role": "assistant", "content": welcome}]

    st.markdown("**💡 Click a question to ask instantly:**")
    chip_cols = st.columns(4)
    quick_prompts = [
        "Summarize this contract in 3 sentences",
        "What's the most dangerous clause and why?",
        "Suggest safer wording for the IP clause",
        "What should I negotiate first?",
        "Explain the non-compete in simple English",
        "Are there any hidden fees, penalties, or traps?",
        "What happens if I breach this contract?",
        "Draft an email requesting changes to all risky clauses",
    ]
    for idx, prompt in enumerate(quick_prompts):
        col = chip_cols[idx % 4]
        with col:
            if st.button(prompt, key=f"chip_{idx}", use_container_width=True):
                st.session_state.pending_ai_query = prompt
                st.rerun()

    for msg in st.session_state.copilot_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if st.session_state.get("pending_ai_query"):
        query = st.session_state.pending_ai_query
        st.session_state.pending_ai_query = None
        if copilot_context:
            st.session_state.copilot_messages.append({"role": "user", "content": query})
            with st.chat_message("user"):
                st.markdown(query)
            with st.chat_message("assistant"):
                with st.spinner("Thinking — analyzing contract context..."):
                    chat_history = st.session_state.copilot_messages[:-1]
                    response = run_copilot_sync(copilot_context, chat_history, query)
                    st.markdown(response)
                st.session_state.copilot_messages.append({"role": "assistant", "content": response})
            st.rerun()

    if prompt := st.chat_input("Ask about this contract...", key="copilot_chat_input"):
        if not copilot_context:
            st.warning("No contract analysis available. Please upload and analyze a contract first.")
        else:
            st.session_state.copilot_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Thinking — analyzing contract context..."):
                    chat_history = st.session_state.copilot_messages[:-1]
                    response = run_copilot_sync(copilot_context, chat_history, prompt)
                    st.markdown(response)
                st.session_state.copilot_messages.append({"role": "assistant", "content": response})

    if st.session_state.copilot_messages:
        cc1, cc2, cc3 = st.columns([1, 2, 1])
        with cc1:
            if st.button("🗑️ Clear Chat", key="copilot_clear", use_container_width=True):
                st.session_state.copilot_messages = []
                st.rerun()
        with cc3:
            st.caption(f"{len(st.session_state.copilot_messages)} messages")


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("""<div style="background:#1e2a3a;border-radius:12px;padding:1.25rem;border:1px solid #3a4a5a">
            <h4 style="margin:0 0 0.5rem 0;color:#fff">🎯 How It Works</h4>
            <ol style="margin:0;padding-left:1.25rem;font-size:0.9rem;color:#ccc;line-height:2">
                <li>Upload any contract file (PDF, DOCX, TXT)</li>
                <li>5 specialized AI agents analyze every clause</li>
                <li>Get a detailed risk report with plain English explanations</li>
                <li>Use Negotiation Copilot to draft counter-proposals</li>
                <li>Chat with the AI Copilot for any follow-up questions</li>
            </ol>
        </div>""", unsafe_allow_html=True)

        st.markdown("")
        st.markdown("""<div style="background:#1e2a3a;border-radius:12px;padding:1.25rem;border:1px solid #3a4a5a">
            <h4 style="margin:0 0 0.5rem 0;color:#fff">🤖 5-Agent AI Pipeline</h4>
            <div style="font-size:0.85rem;color:#ccc;line-height:2">
                <p style="margin:0.2rem 0"><b style="color:#8ab4f8">① Extractor</b> — Segments contract into individual clauses</p>
                <p style="margin:0.2rem 0"><b style="color:#8ab4f8">② Classifier</b> — Labels each clause by legal type</p>
                <p style="margin:0.2rem 0"><b style="color:#8ab4f8">③ Risk Scorer</b> — Evaluates severity of each clause</p>
                <p style="margin:0.2rem 0"><b style="color:#8ab4f8">④ Translator</b> — Converts legalese to plain English</p>
                <p style="margin:0.2rem 0"><b style="color:#8ab4f8">⑤ Reporter</b> — Compiles the final risk report</p>
            </div>
        </div>""", unsafe_allow_html=True)

        if st.session_state.report:
            s = st.session_state.report.summary
            total_risky = s.critical_count + s.high_count
            st.markdown("")
            st.markdown("#### 📊 Contract Stats")

            risk_delta = f"{total_risky} high-risk" if total_risky > 0 else "Clean"
            st.metric(
                "🎯 Risk Score",
                f"{s.overall_score}/10",
                delta=risk_delta,
                delta_color="inverse" if total_risky > 0 else "normal",
            )
            st.metric("📄 Total Clauses", s.total_clauses)

            has_any_risks = False
            for icon, label, key in [
                ("🔴", "Critical", "critical_count"),
                ("🟠", "High", "high_count"),
                ("🟡", "Medium", "medium_count"),
                ("🟢", "Low", "low_count"),
            ]:
                count = getattr(s, key, 0)
                if count > 0:
                    has_any_risks = True
                    st.metric(f"{icon} {label}", count)

            st.divider()
            st.markdown(f"**Contract Type:** {s.contract_type}")
            st.markdown(f"**Analyzed:** {st.session_state.report.generated_at.strftime('%b %d, %Y at %H:%M')}")

            if not st.session_state.report.processed_normally:
                st.caption("⚠️ Report may not cover all clauses due to processing constraints.")

        st.markdown("")
        st.markdown("""<div style="background:#1e2a3a;border-radius:12px;padding:1.25rem;border:1px solid #3a4a5a">
            <h4 style="margin:0 0 0.5rem 0;color:#fff">⚡ Powered by</h4>
            <p style="font-size:0.85rem;color:#ccc;margin:0;line-height:1.8">
                Qwen2.5 via vLLM on AMD MI300X<br>
                OpenAI-compatible API<br>
                Streamlit • Python 3.10+
            </p>
            <div style="margin-top:0.5rem;padding:0.3rem 0.5rem;background:#1a0533;border-radius:6px;border:1px solid #667eea;text-align:center;font-size:0.7rem;color:#aabbcc">
                🏷️ AMD Developer Cloud
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("")
        st.markdown("""<div style="font-size:0.7rem;color:#555;text-align:center;margin-top:1rem">
            <p style="margin:0">⚠️ Not legal advice. AI-generated analysis.</p>
            <p style="margin:0">Always consult a qualified attorney before signing.</p>
        </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APP ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="ClauseGuard — AI Contract Risk Analyzer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
_init_session_state()

render_header()

_render_guided_tour()

render_risk_banner()

uploaded_file = st.file_uploader(
    "Choose a contract file",
    type=ALLOWED_EXTENSIONS,
    help="Supported: PDF, TXT, DOCX • Maximum file size: 10MB",
    key="file_uploader",
)

if uploaded_file is not None:
    fb = uploaded_file.read()
    st.session_state.uploaded_filename = uploaded_file.name
    st.session_state.uploaded_bytes = fb
    if len(fb) > MAX_FILE_SIZE_BYTES:
        st.error(f"File too large ({len(fb)/1024/1024:.1f}MB). Max file size is {MAX_FILE_SIZE_MB}MB. Please reduce the file size or split the contract.")
    else:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.success(f"**{uploaded_file.name}** loaded successfully — `{len(fb)/1024:.1f} KB` ready for analysis")
        with c2:
            analyze_disabled = st.session_state.analyzing
            if st.button(
                "🔍 Analyze Contract",
                type="primary",
                disabled=analyze_disabled,
                use_container_width=True,
                help="Run the full 5-agent AI pipeline on this contract",
            ):
                st.session_state.analyzing = True
                st.session_state.error = None
                st.session_state.guided_demo = False
                st.rerun()

if st.session_state.analyzing and st.session_state.uploaded_bytes:
    _run_analysis()

if st.session_state.error:
    st.error(st.session_state.error)
    if "DEEPSEEK_API_KEY" in st.session_state.error:
        st.info("💡 To use ClauseGuard, set the `BASE_URL` and `MODEL_NAME` in your `.env` file to point to your Qwen/vLLM endpoint. See the README for setup instructions.")

if st.session_state.report:
    report = st.session_state.report
    s = report.summary

    st.divider()

    render_issues_summary()

    active_tab = st.radio(
        "Navigate between sections",
        TAB_NAMES,
        index=min(st.session_state.get("active_tab", 0), len(TAB_NAMES) - 1),
        label_visibility="collapsed",
        horizontal=True,
    )
    st.session_state.active_tab = TAB_NAMES.index(active_tab)
    tab_index = st.session_state.active_tab

    if tab_index == 0:
        render_overview_tab()
    elif tab_index == 1:
        render_clauses_tab()
    elif tab_index == 2:
        render_negotiation_tab()
    elif tab_index == 3:
        render_chat_tab()

    st.divider()
    st.markdown("### 📥 Download Your Report")
    st.caption("Download the full analysis in your preferred format to share with legal counsel or reference later.")

    dl_cols = st.columns(3)
    with dl_cols[0]:
        st.download_button(
            "📝 Download Markdown Report",
            data=report.markdown_report or "# ClauseGuard Report\n\nRun analysis first.",
            file_name=f"clauseguard_report_{report.contract_name.replace('.','_')}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with dl_cols[1]:
        safe_contract = _build_safer_contract(report)
        st.download_button(
            "🛡️ Download Safer Contract",
            data=safe_contract,
            file_name=f"safer_{report.contract_name.replace('.txt','').replace('.pdf','').replace('.docx','')}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with dl_cols[2]:
        csv_lines = ["Clause ID,Type,Severity,Risk Title,Risk Reason,Recommended Action,Plain English,Negotiation Message"]
        for sc in report.scored_clauses:
            csv_lines.append(
                f'"{sc.clause.id}","{sc.clause.clause_type.value}","{sc.finding.severity.value}","{sc.finding.risk_title}","{sc.finding.risk_reason}","{sc.finding.recommended_action}","{sc.clause.plain_english or ""}","{sc.finding.negotiation_message or ""}"'
            )
        st.download_button(
            "📊 Download CSV Data",
            data="\n".join(csv_lines),
            file_name=f"clauseguard_data_{report.contract_name.replace('.','_')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.caption(
        f"Generated {report.generated_at.strftime('%B %d, %Y at %H:%M')} "
        f"• {s.contract_type} • {s.total_clauses} clauses analyzed"
        f"{' • ⚠️ Partial analysis' if not report.processed_normally else ''}"
    )

render_sidebar()
