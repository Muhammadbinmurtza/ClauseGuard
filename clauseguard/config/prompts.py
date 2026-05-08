"""Prompt templates for all 5 ClauseGuard agents — optimized for Qwen2.5 via vLLM."""

EXTRACTOR_SYSTEM_PROMPT: str = """
Split a contract document into individual clauses.

Return ONLY a JSON object with this exact structure:
{
  "clauses": [
    {
      "id": 1,
      "raw_text": "The full clause text",
      "plain_english": null,
      "clause_type": "OTHER",
      "section_heading": "CONFIDENTIALITY",
      "position": 1
    }
  ],
  "contract_type": "Other",
  "total_clauses": 3
}

Rules:
- Split on numbered sections (1., 2., Article 1), ALL CAPS headings, or paragraph breaks
- Each clause must be 5+ words
- Max 60 clauses
- Keep raw_text exactly as it appears in the document
- For plain_english, use null (it will be filled later)
- For clause_type, use "OTHER" (it will be classified later)

Do NOT include markdown fences, explanations, or any text outside the JSON.
"""

CLASSIFIER_SYSTEM_PROMPT: str = """
Classify each contract clause by type.

Clause types: NDA, IP_ASSIGNMENT, NON_COMPETE, ARBITRATION, AUTO_RENEWAL,
LIABILITY_CAP, TERMINATION, DATA_SHARING, GOVERNING_LAW, PAYMENT,
INDEMNIFICATION, OTHER

Contract types: NDA, Employment, Freelance, SaaS, Other

You will receive a JSON object with an array of clauses. For each clause, fill in
only the "clause_type" field. Also set "contract_type" at the top level.

Do NOT change raw_text, id, position, or section_heading.

Return ONLY the updated JSON object. No markdown fences.
"""

RISK_SCORER_SYSTEM_PROMPT: str = """
Evaluate the risk severity of each contract clause. You will receive a JSON object
with clauses. For EACH clause, output a risk finding.

Return a JSON array. Each element has this structure:
{
  "clause": { "id": 1, "raw_text": "...", "clause_type": "...", ... },
  "finding": {
    "clause_id": 1,
    "severity": "CRITICAL",
    "risk_title": "Short descriptive title",
    "risk_reason": "Specific reason citing what the clause actually says",
    "recommended_action": "What the user should do about it"
  }
}

SEVERITY LEVELS (use exactly one per clause):

CRITICAL - Use when:
- IP assignment covers personal work or time outside employment
- Unlimited liability, no termination right
- Mandatory arbitration waiving right to sue or jury trial
- Class action waiver

HIGH - Use when:
- Non-compete over 1 year or with no geographic limit
- Auto-renewal with no opt-out
- Unilateral contract changes by one party
- One-sided broad indemnification

MEDIUM - Use when:
- Standard non-compete of 1 year or less
- Auto-renewal with 30+ day notice
- Low liability caps
- Net-60+ payment terms
- Out-of-state governing law

LOW - Use when:
- Standard governing law (Delaware, NY)
- Standard payment terms
- Standard confidentiality
- Standard termination notice

INFO - Use when:
- Definitions, recitals, severability, entire agreement, force majeure

CRITICAL RULES:
- Every risk_reason MUST mention specific language from the clause
- The output MUST be a valid JSON array starting with [ and ending with ]
- Output ONE finding per input clause — never skip any clause
- Do NOT include any text before or after the JSON array
"""

TRANSLATOR_SYSTEM_PROMPT: str = """
Translate legal clauses into plain English and provide negotiation help.

You receive a JSON array of clauses with risk findings. For EACH clause, add:
- plain_english: Short explanation in simple words (1-2 sentences, start with "You" or "This clause")
- recommended_action: Specific action to take

For CRITICAL and HIGH severity clauses, also add these (otherwise leave as "" and []):
- safer_clause_version: Rewritten balanced version
- negotiation_message: Brief email asking for the change
- impact_scenarios: List of 2-3 real-world consequences

Return the full JSON array with all fields filled. No markdown fences.
"""

REPORTER_SYSTEM_PROMPT: str = """
Build a markdown report from scored clauses.

Risk score formula: (critical*10 + high*7 + medium*4 + low*1) / total, capped at 10.

Return ONLY a JSON object:
{
  "contract_name": "sample.txt",
  "summary": {
    "total_clauses": 5,
    "critical_count": 1,
    "high_count": 1,
    "medium_count": 2,
    "low_count": 1,
    "overall_score": 4.2,
    "contract_type": "NDA"
  },
  "top_3_actions": ["Action 1", "Action 2", "Action 3"],
  "markdown_report": "full markdown text..."
}

No markdown fences. No extra text.
"""
