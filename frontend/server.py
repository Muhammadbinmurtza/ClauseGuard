"""ClauseGuard Server — FastAPI backend that serves the frontend and exposes the analysis API."""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clauseguard.agents.copilot import build_contract_context, run_copilot
from clauseguard.agents.orchestrator import run_pipeline, set_event_callback
from clauseguard.config.settings import validate_config
from clauseguard.models.clause import Clause, ClauseType
from clauseguard.models.findings import RiskFinding, ScoredClause, Severity
from clauseguard.models.report import FinalReport
from clauseguard.tools.file_tools import extract_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}

app = FastAPI(title="ClauseGuard", description="AI Contract Risk Analyzer")

FRONTEND_DIR = Path(__file__).resolve().parent

# ── Agent status store (in-memory, one per session) ──
agent_status: dict[str, dict] = {}


def build_demo_report() -> dict:
    """Return the demo report as a JSON-serializable dict."""
    demo_clauses = [
        {
            "text": "Recipient hereby irrevocably assigns to Company all inventions, discoveries, and intellectual property created during this Agreement and for 1 year after, regardless of whether created on Recipient's own time or equipment.",
            "ctype": "IP_ASSIGNMENT", "sev": "CRITICAL",
            "title": "IP Assignment of Personal Work",
            "reason": "Claims ownership of ALL creations including personal projects on personal time and equipment, extending 1 year after termination.",
            "plain": "You give the company ownership of everything you create — including personal side projects on your own time and equipment — for up to a year after you leave.",
            "action": "Demand a carve-out for inventions created on your own time using your own equipment.",
            "safer": "Employee assigns to Company all inventions directly related to Company's business and created during working hours using Company resources. Inventions created on Employee's own time using personal equipment, and unrelated to Company's business, remain the sole property of Employee.",
            "negotiation": "Hi, I've reviewed the IP clause and would like to request an adjustment to ensure personal projects created outside work hours remain mine. I've suggested alternative wording below. Would you be open to this change? Thanks!",
            "impacts": [
                "You may lose ownership of any side projects or startups you work on during employment",
                "The company could claim your open-source contributions made on weekends",
            ],
        },
        {
            "text": "All disputes shall be resolved exclusively through binding arbitration. The parties waive any right to a trial by jury and waive the right to participate in any class action.",
            "ctype": "ARBITRATION", "sev": "CRITICAL",
            "title": "Mandatory Arbitration with Jury + Class Action Waiver",
            "reason": "Forces disputes into private arbitration, waives your constitutional right to a jury trial, and blocks class actions — with no opt-out.",
            "plain": "You give up your right to sue in court or join a class-action lawsuit. All disputes go through private arbitration instead.",
            "action": "Add an opt-out clause for arbitration — preserve your right to go to court.",
            "safer": "Either party may opt out of binding arbitration by providing written notice within 30 days of signing. Nothing in this section prevents participation in class actions where permitted by law.",
            "negotiation": "Hi, I've reviewed the dispute resolution clause. I'd like to add an opt-out option for arbitration so both parties retain the right to choose their preferred forum. I've suggested language below. Does this work for you?",
            "impacts": [
                "If the company violates your rights, you cannot sue them in a public court",
                "You cannot join with other affected parties in a class action — you must fight alone",
            ],
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
            "impacts": [
                "You may be unable to work in your industry anywhere in the world for 18 months after leaving",
                "Relocating to a new city won't help — the restriction is global",
            ],
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
    for i, d in enumerate(demo_clauses, 1):
        clause = Clause(
            id=i, raw_text=d["text"], plain_english=d["plain"],
            clause_type=ClauseType(d["ctype"]),
            section_heading=d["ctype"].replace("_", " "), position=i,
            confidence_score=0.95,
        )
        finding = RiskFinding(
            clause_id=i, severity=Severity(d["sev"]),
            risk_title=d["title"], risk_reason=d["reason"],
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
    raw = (crit * 10 + high * 7 + med * 4 + low * 1) / len(scored)
    overall = round(min(raw, 10.0), 1)

    report = FinalReport(
        contract_name="sample_nda.txt (Demo)",
        generated_at=datetime.now(),
        summary={
            "total_clauses": len(scored), "critical_count": crit,
            "high_count": high, "medium_count": med, "low_count": low,
            "overall_score": overall, "contract_type": "NDA",
        },
        top_3_actions=[
            "Demand a carve-out for inventions created on your own time using your own equipment.",
            "Add an opt-out clause for arbitration — preserve your right to go to court.",
            "Reduce non-compete to 12 months with geographic scope tied to actual operations.",
        ],
        scored_clauses=scored,
        markdown_report="",
        processed_normally=False,
    )
    return _report_to_json(report)


def _report_to_json(report: FinalReport) -> dict:
    """Convert a FinalReport to a JSON-serializable dict."""
    def _serialize(obj):
        if hasattr(obj, 'model_dump'):
            return obj.model_dump(mode='json')
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        if isinstance(obj, set):
            return list(obj)
        raise TypeError(f"Type {type(obj)} not serializable")

    return json.loads(json.dumps(report.model_dump(), default=_serialize))


# ── API Routes ──


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/demo")
async def get_demo():
    """Return the pre-built demo report."""
    return build_demo_report()


@app.get("/api/agent-status")
async def get_agent_status():
    """Return current agent pipeline status."""
    return agent_status


@app.post("/api/analyze")
async def analyze_contract(file: UploadFile = File(...)):
    """Upload a contract and run the full 5-agent pipeline."""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: .{ext}. Allowed: PDF, TXT, DOCX")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(400, f"File too large ({len(contents)/1024/1024:.1f}MB). Max: {MAX_FILE_SIZE_MB}MB")

    try:
        validate_config()
    except ValueError as e:
        raise HTTPException(500, str(e))

    agent_status.clear()
    agent_names = ["Extractor", "Classifier", "Risk Scorer", "Translator", "Reporter"]
    for name in agent_names:
        agent_status[name] = {"status": "pending", "message": ""}

    def _on_event(agent: str, status: str, details: dict):
        agent_status[agent] = {
            "status": status,
            "message": details.get("message", ""),
        }

    set_event_callback(_on_event)

    try:
        raw_text = extract_text(contents, file.filename)
    except Exception as e:
        raise HTTPException(400, f"Could not read file: {e}")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(run_pipeline(raw_text, file.filename))
        finally:
            loop.close()
    except Exception as e:
        logger.error("Pipeline error: %s", e)
        raise HTTPException(500, f"Analysis pipeline failed: {e}")

    for name in agent_names:
        if agent_status.get(name, {}).get("status") == "pending":
            agent_status[name] = {"status": "completed", "message": "OK"}

    return _report_to_json(report)


@app.post("/api/chat")
async def chat_with_copilot(request: dict):
    """Chat with the AI copilot about the analyzed contract."""
    context = request.get("context", "")
    history = request.get("history", [])
    message = request.get("message", "")

    if not message:
        raise HTTPException(400, "Message is required")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(run_copilot(context, history, message))
        finally:
            loop.close()
    except Exception as e:
        logger.error("Chat error: %s", e)
        raise HTTPException(500, f"Chat failed: {e}")

    return {"response": response}


@app.post("/api/build-context")
async def build_context(request: dict):
    """Build copilot context from contract text and report data."""
    raw_text = request.get("raw_text", "")
    report_data = request.get("report", {})

    if not raw_text or not report_data:
        raise HTTPException(400, "raw_text and report are required")

    try:
        report = FinalReport(**report_data.get("__raw__", report_data))
    except Exception:
        context_parts = [
            "=" * 60,
            "FULL CONTRACT TEXT",
            "=" * 60,
            raw_text,
            "",
            "=" * 60,
            "CONTRACT SUMMARY",
            "=" * 60,
            f"Contract: {report_data.get('contract_name', 'Unknown')}",
            f"Type: {report_data.get('summary', {}).get('contract_type', 'Unknown')}",
            f"Risk Score: {report_data.get('summary', {}).get('overall_score', 'N/A')}/10",
        ]
        return {"context": "\n".join(context_parts)}

    context = build_contract_context(raw_text, report)
    return {"context": context}


# ── Static file serving ──


@app.get("/", response_class=HTMLResponse)
async def index():
    return (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
