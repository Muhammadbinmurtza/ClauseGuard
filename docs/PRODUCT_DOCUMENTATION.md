# ClauseGuard — AI-Powered Contract Clause Risk Analyzer

## Product Documentation — AMD Developer Hackathon 2025

---

## 1. What is ClauseGuard?

ClauseGuard is an AI-powered contract analysis system that reads any uploaded contract (PDF, TXT, DOCX) and returns a structured risk report in plain English — in under 2 minutes.

It uses a **5-agent AI pipeline** built with the **OpenAI Agents SDK**, powered by **DeepSeek-V3** on **AMD MI300X** infrastructure. Each agent specializes in one task: extracting clauses, classifying their type, scoring their risk, translating to plain English, and compiling the final report.

**This is not a chatbot.** It is a document processing pipeline with strict Pydantic v2 schemas at every stage, designed to produce consistent, reliable, structured output.

---

## 2. The Problem ClauseGuard Solves

| Problem | Impact |
|---------|--------|
| Average person spends 8 minutes reading a contract | 90% don't read past page 2 |
| Legal review costs $300-$500/hour | Inaccessible to freelancers and startups |
| Dangerous clauses buried in legal jargon | IP grabs, non-competes, arbitration waivers |
| No free instant analysis tool exists | Enterprise tools (LawGeex, ContractSafe) cost thousands |
| Contracts are dense and intimidating | People sign away rights they don't know exist |

**ClauseGuard fixes this.** Upload → Analyze → Get a report showing exactly what to worry about and what to say instead.

---

## 3. Who Is This For?

| User | Use Case |
|------|----------|
| **Freelancers** | Reviewing client contracts before signing |
| **Employees** | Analyzing job offer letters and NDAs |
| **Startup Founders** | Vetting vendor agreements and SaaS contracts |
| **Small Business Owners** | Checking supplier contracts without a lawyer |
| **Anyone** | Understanding what they're signing — no legal background needed |

---

## 4. Architecture — The 5-Agent Pipeline

```
  ┌──────────┐    ┌───────────┐    ┌─────────────┐    ┌──────────────┐    ┌──────────┐
  │ Extractor│───▶│Classifier │───▶│ Risk Scorer │───▶│  Translator  │───▶│ Reporter │
  │ (Agent 1)│    │ (Agent 2) │    │  (Agent 3)  │    │  (Agent 4)   │    │ (Agent 5)│
  └──────────┘    └───────────┘    └─────────────┘    └──────────────┘    └──────────┘
       │               │                 │                   │                 │
       ▼               ▼                 ▼                   ▼                 ▼
  Split text      Assign types     Score severity      Plain English     Final markdown
  into clauses    + contract       per clause          + actions         report
                  type
```

### Agent 1 — Extractor
Splits the raw document into individual clauses using regex patterns for numbered sections, ALL CAPS headings, and double line breaks. Caps at 60 clauses. Returns a `ClauseList` Pydantic model.

### Agent 2 — Classifier
Assigns each clause a `ClauseType` from the 12-category enum (NDA, IP_ASSIGNMENT, NON_COMPETE, ARBITRATION, etc.) and detects the overall contract type (NDA, Employment, Freelance, SaaS, Other). Outputs confidence scores.

### Agent 3 — Risk Scorer
The most critical agent. Evaluates every clause against explicit severity criteria and assigns a rating of CRITICAL, HIGH, MEDIUM, LOW, or INFO. Every finding must cite the specific clause language — no generic reasons allowed.

**Severity criteria examples:**
- **CRITICAL**: IP assignment of personal work, unlimited liability, no termination right, mandatory arbitration with jury waiver
- **HIGH**: Non-compete over 1 year, no geographic limit, auto-renewal without notice
- **MEDIUM**: Standard non-compete under 1 year, 30-day renewal notice, net-60 payment terms
- **LOW**: Standard governing law, payment terms, termination notice
- **INFO**: Boilerplate definitions, recitals, severability

### Agent 4 — Translator
Rewrites every clause in plain English — maximum 2 sentences, starting with "You" or "This clause". Writes specific, actionable recommendations (not generic "review this"). Designed for someone with zero legal background.

### Agent 5 — Reporter
Compiles all agent outputs into a `FinalReport` with:
- Executive summary
- Overall risk score (0-10)
- Top 3 actions before signing
- Risk summary table
- Full clause-by-clause analysis with severity badges

### Orchestrator
The orchestrator manages the full pipeline using OpenAI Agents SDK `handoff()`. Each agent call is wrapped in `try/except` with 30-second timeout. If any agent fails or times out, the pipeline continues with partial data. The Reporter always runs — a partial report is better than no report.

---

## 5. Tech Stack

| Component | Technology | Reason |
|-----------|-----------|--------|
| **Agent Framework** | OpenAI Agents SDK | Clean handoffs, structured output, works with any OpenAI-compatible API |
| **AI Model** | DeepSeek-V3 | Open-source, 128K context window, strong legal document comprehension |
| **API Endpoint** | `https://api.deepseek.com` | OpenAI-compatible — single `base_url` config change |
| **Infrastructure** | AMD MI300X (AMD Developer Cloud) | GPU compute for inference; designed for ROCm self-hosting |
| **Data Validation** | Pydantic v2 | Strict schemas at every pipeline stage — catches bad LLM output |
| **File Parsing** | PyMuPDF (PDF), python-docx (DOCX), chardet (encoding) | Multi-format support with automatic encoding detection |
| **UI** | Streamlit | Rapid interactive dashboard with native file upload and charts |
| **Testing** | pytest + pytest-asyncio | 13 real tests covering extraction, scoring, and pipeline integration |
| **Python** | 3.11+ | Modern async/await, type hints throughout |

---

## 6. Key Features

### Core Features (MUST HAVE)
| # | Feature | Description |
|---|---------|------------|
| F1 | Multi-format Upload | Accept PDF, TXT, DOCX files up to 50 pages / 10MB |
| F2 | Clause Extraction | Segment document into individual clauses with section context |
| F3 | Risk Classification | Label each clause by type + assign Critical/High/Medium/Low/Info severity |
| F4 | Plain English Translation | 1-2 sentences per clause, starts with "You" or "This clause" |
| F5 | Structured Report | Markdown report with executive summary, risk table, clause breakdown |
| F6 | Interactive UI | Streamlit dashboard with upload, progress, rendered report |
| F7 | Report Download | Save full report as .md file (print as PDF from any viewer) |
| F8 | Top 3 Actions | Prioritized recommended actions at the top of every report |
| F9 | Overall Risk Score | Single 0-10 score with weighted formula (Critical × 10, High × 7, etc.) |
| F10 | Contract Type Detection | Auto-detect NDA vs Employment vs Freelance vs SaaS |

### Demo Features (Built for Hackathon)
| Feature | Description |
|---------|------------|
| ⚡ Instant Demo | Pre-analyzed report loads in <1 second — bypasses API latency |
| 📈 Risk Heatmap | Visual bar chart showing severity distribution at a glance |
| ⚖️ Side-by-Side Negotiation | Critical clauses show "What you signed" vs "What to ask for" with counter-language |
| 🏷️ AMD Badge | "AMD Developer Hackathon 2025" branding for judging criteria |

---

## 7. How to Run

### Prerequisites
- Python 3.11+
- DeepSeek API key (free at [platform.deepseek.com](https://platform.deepseek.com))

### Setup
```bash
cd clauseguard
pip install -r requirements.txt
cp .env.example .env
# Edit .env: add DEEPSEEK_API_KEY=your_key_here
```

### CLI
```bash
python main.py --file sample_contracts/sample_nda.txt
python main.py --file my_contract.pdf --output my_report.md
```

### Web UI
```bash
streamlit run app.py
# Open http://localhost:8501
```

### Tests
```bash
pytest tests/ -v   # 13 tests, all passing
```

---

## 8. Sample Output

```
# ClauseGuard Risk Report
**Contract:** sample_nda.txt
**Type:** NDA
**Overall Risk Score:** 3.4/10

## Top 3 Actions Before Signing
1. Demand a carve-out for inventions created on own time using own equipment
2. Add an opt-out clause for mandatory arbitration
3. Reduce non-compete to 12 months with geographic limits

## Risk Summary
| Severity | Count |
|----------|-------|
| 🔴 Critical | 2 |
| 🟠 High | 1 |
| 🟡 Medium | 1 |
| 🟢 Low | 3 |
| ℹ️ Info | 3 |

## Clause Analysis
### IP_ASSIGNMENT — 🔴 CRITICAL
**Original:** Recipient hereby irrevocably assigns to Company all inventions...
**Plain English:** You give the company all rights to anything you create, even
  on your own time and equipment, and for a year after the agreement ends.
**Risk:** Clause assigns all IP including work on personal time and equipment...
**Action:** Negotiate a carve-out for personal projects unrelated to Company's business.
```

---

## 9. Project Structure

```
clauseguard/
├── main.py                    # CLI entry point
├── app.py                     # Streamlit web UI
├── requirements.txt           # All dependencies (pinned versions)
├── .env.example               # API key template
├── README.md                  # Setup guide + ASCII architecture diagram
├── LICENSE                    # MIT License
│
├── agents/
│   ├── extractor.py           # Agent 1: Clause segmentation
│   ├── classifier.py          # Agent 2: Clause type classification
│   ├── risk_scorer.py         # Agent 3: Risk severity scoring
│   ├── translator.py          # Agent 4: Plain English translation
│   ├── reporter.py            # Agent 5: Final report compilation
│   └── orchestrator.py        # Pipeline controller with OpenAI Agents SDK handoff
│
├── tools/
│   ├── file_tools.py          # PDF/TXT/DOCX parsing + encoding detection
│   ├── clause_tools.py        # Clause splitting + heading detection + contract type
│   └── report_tools.py        # Markdown formatting + severity badges
│
├── models/
│   ├── clause.py              # Clause, ClauseType, ClauseList schemas
│   ├── findings.py            # RiskFinding, Severity, RecommendedAction, ScoredClause
│   └── report.py              # FinalReport, RiskSummary, ClauseReport
│
├── config/
│   ├── settings.py            # API endpoints, model name, timeouts
│   └── prompts.py             # All 5 agent system prompts with few-shot examples
│
├── tests/
│   ├── test_extractor.py      # Extraction tests on sample contracts
│   ├── test_risk_scorer.py    # Severity scoring tests with mock clauses
│   └── test_pipeline.py       # Full end-to-end pipeline tests
│
├── sample_contracts/          # Test data
│   ├── sample_nda.txt         # NDA with IP assignment + non-compete + arbitration
│   ├── sample_employment.txt  # Employment with personal IP grab + class action waiver
│   └── sample_freelance.txt   # Freelance with pre-existing IP + unlimited revisions
│
├── docs/
│   ├── architecture.png       # 5-agent pipeline diagram
│   ├── sample_report.md       # Pre-generated sample output
│   ├── AMD_FEEDBACK.md        # ROCm + AMD Cloud build experience notes
│   ├── cached_report_employment.md  # Cached report fallback
│   └── cached_report_freelance.md   # Cached report fallback
│
└── .streamlit/
    └── config.toml            # Streamlit dark theme configuration
```

---

## 10. Risk Mitigation Strategy

| Risk | Level | Mitigation |
|------|-------|-----------|
| PDF parsing fails (scanned docs) | High | PyMuPDF first → pdfplumber fallback → prompt user to paste text |
| DeepSeek returns malformed JSON | High | `try/except` on every agent → retry once with explicit JSON instruction → skip clause on failure |
| Contract too long (>100 pages) | Medium | Cap at 60 clauses → note truncation in report |
| API rate limit during demo | Medium | Pre-generated cached reports — Instant Demo button bypasses API entirely |
| Agent timeout (slow responses) | Medium | 30s timeout per agent → skip agent → Reporter runs with partial data |
| Clause segmentation errors | Medium | Tested on all 3 sample contracts → regex splits handle numbered, CAPS, and paragraph breaks |

---

## 11. Hackathon Submission Notes

### Technology Use
- **DeepSeek-V3**: Fully open-source model with 128K context for legal documents
- **AMD MI300X**: Infrastructure designed for ROCm self-hosting on AMD Developer Cloud
- **OpenAI Agents SDK**: Real multi-agent handoff chain — not a single API call in a wrapper

### Presentation Plan (90 seconds)
1. **0:00**: "This is ClauseGuard. Upload any contract. Get a plain-English risk report in 60 seconds."
2. **0:10**: Click Demo → report appears instantly
3. **0:15**: Walk through Critical findings → IP assignment + arbitration waiver
4. **0:45**: Show side-by-side negotiation view: "What you signed" vs "What to ask for"
5. **1:10**: Show heatmap chart, overall score, download button
6. **1:25**: "5 specialized AI agents, OpenAI Agents SDK, powered by DeepSeek-V3 on AMD MI300X"

### Business Value
Legal review costs $300-$500 per hour. ClauseGuard does a free first pass in 60 seconds. Target users: freelancers, employees, startup founders, small business owners — everyone who signs contracts without a lawyer.

---

## 12. Future Roadmap

| Phase | Feature |
|-------|---------|
| v1.1 | PDF export with styled formatting |
| v1.2 | Multi-language support (Spanish, French, German contracts) |
| v1.3 | Clause version comparison (redline "before/after" view) |
| v2.0 | OCR support for scanned/image contracts (Tesseract) |
| v2.1 | API endpoint for programmatic access |
| v2.2 | User accounts + contract history + team sharing |
| v3.0 | Enterprise: custom risk rules, integration with DocuSign/Salesforce |

---

**ClauseGuard — AMD Developer Hackathon 2025**  
*Track 1: AI Agents & Agentic Workflows*  
*OpenAI Agents SDK + DeepSeek-V3 + AMD MI300X*
