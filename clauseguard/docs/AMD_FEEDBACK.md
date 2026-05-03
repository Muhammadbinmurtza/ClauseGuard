# AMD Developer Cloud Experience — ClauseGuard Build Notes

## Environment
- **Cloud Provider**: AMD Developer Cloud
- **Compute**: AMD MI300X (planned inference endpoint)
- **Model**: DeepSeek-V3
- **Framework**: ROCm (for self-hosted inference)

## Build Experience

### What Worked Well
1. **OpenAI Agents SDK** integrated smoothly with DeepSeek's OpenAI-compatible API — only required changing `base_url` to `https://api.deepseek.com` and setting the API key.
2. **Multi-agent handoff architecture** using the Agents SDK was straightforward. The 5-agent pipeline (Extractor → Classifier → Risk Scorer → Translator → Reporter) follows a clean linear handoff pattern.
3. **Pydantic v2** provided excellent schema validation at every pipeline stage, catching malformed LLM output before it propagated downstream.
4. **PyMuPDF** handled PDF extraction well for text-based contracts with no issues.
5. **Streamlit** enabled rapid UI prototyping — the entire UI was built in under 3 hours.

### Challenges & Solutions
1. **DeepSeek API latency**: Occasional 20-30s response times for complex prompts. Mitigated with 30s timeout per agent and programmatic fallback for the Reporter step.
2. **JSON output reliability**: DeepSeek occasionally wrapped JSON in markdown fences. Implemented `_clean_json_response()` across all agents and retry-once logic for malformed responses.
3. **PDF parsing edge cases**: Scanned/image-based PDFs fail with PyMuPDF text extraction. Added pdfplumber as a fallback parser and user guidance to paste text directly.

### AMD-Specific Notes
- The pipeline is designed to run with DeepSeek-V3 served on AMD MI300X GPUs via ROCm.
- For the hackathon demo, we used the DeepSeek hosted API for reliability, but the architecture supports self-hosted deployment on AMD infrastructure.
- The OpenAI Agents SDK and all Python dependencies run without modification on AMD EPYC processors, which power the AMD Developer Cloud.

### Recommendations for Production
1. Self-host DeepSeek-V3 on AMD MI300X for lower latency and cost at scale.
2. Add Redis caching for repeated contract analysis to reduce API calls.
3. Implement a clause negotiation tips database for Critical/High findings.
4. Add support for scanned PDFs via OCR (Tesseract integration).

---

*Built for AMD Developer Hackathon 2025 — Track 1: AI Agents & Agentic Workflows*
