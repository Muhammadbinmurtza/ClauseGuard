---
title: ClauseGuard AI
emoji: 🛡️
colorFrom: indigo
colorTo: purple
sdk: streamlit
sdk_version: "1.31.0"
app_file: clauseguard/app.py
pinned: false
license: mit
---

# ClauseGuard — AI-Powered Contract Clause Risk Analyzer

Upload any contract (PDF, TXT, DOCX). ClauseGuard runs it through a 5-agent AI pipeline and outputs a structured risk report classifying every clause by severity with plain-English explanations.

## Architecture

**5-Agent AI Pipeline:** Extractor → Classifier → Risk Scorer → Translator → Reporter

```
  Upload Contract
       │
       ▼
  ┌──────────┐    ┌───────────┐    ┌─────────────┐    ┌──────────────┐    ┌──────────┐
  │Extractor │───▶│Classifier │───▶│ Risk Scorer  │───▶│  Translator  │───▶│ Reporter │
  │ (Agent 1)│    │ (Agent 2) │    │  (Agent 3)   │    │  (Agent 4)   │    │(Agent 5) │
  └──────────┘    └───────────┘    └─────────────┘    └──────────────┘    └──────────┘
       │               │                │                   │                  │
  Split into       Label by         Assign CRITICAL/    Plain English      Compile
  individual       clause type      HIGH/MEDIUM/        + negotiation      FinalReport
  clauses          + contract type  LOW/INFO severity   tips               + markdown
```

## Features

- **5-Agent AI Pipeline** — Extractor, Classifier, Risk Scorer, Translator, Reporter
- **Contract Types** — NDA, Employment, Freelance, SaaS, and more
- **Risk Severity** — CRITICAL, HIGH, MEDIUM, LOW, INFO with specific reasons
- **Plain English** — Every clause translated into simple language
- **Negotiation Copilot** — Pre-written negotiation messages and safer alternatives
- **AI Chat Assistant** — Ask follow-up questions with full contract context
- **Download Reports** — Markdown, CSV, and safer contract versions

## Supported Files

- PDF (scanned or text)
- DOCX (Microsoft Word)
- TXT (plain text)
- Max file size: 10 MB

## Tech Stack

- **Model**: Qwen2.5-1.5B-Instruct via vLLM on AMD MI300X
- **UI**: Streamlit
- **API**: OpenAI-compatible endpoint

## Quick Start

```bash
pip install -r requirements.txt
streamlit run clauseguard/app.py
```

## Configuration

Create a `.env` file (or set environment variables):

```
API_KEY=EMPTY
BASE_URL=http://165.245.141.170:8000/v1
MODEL_NAME=Qwen/Qwen2.5-1.5B-Instruct
```

## License

MIT — see LICENSE file.
