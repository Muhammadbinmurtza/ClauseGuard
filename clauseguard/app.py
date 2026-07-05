"""ClauseGuard Streamlit UI — redesigned modern SaaS edition."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from clauseguard.ui import (
    MAX_FILE_SIZE_MB, MAX_FILE_SIZE_BYTES, ALLOWED_EXTENSIONS,
    AGENT_NAMES, AGENT_ICONS, AGENT_STEP_NUMBERS, SEVERITY_STYLE, CUSTOM_CSS,
    _check_model_connectivity, _build_demo_report, _load_demo_report, _load_guided_demo,
    _init_session_state, _on_agent_event, _run_analysis, _build_safer_contract,
    render_header, _render_guided_tour, render_risk_banner, render_issues_summary,
    render_overview_tab, render_sidebar, render_clauses_tab, render_negotiation_tab, render_chat_tab,
)

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
    st.divider()
    render_issues_summary()
    render_overview_tab()

render_sidebar()
