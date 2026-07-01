"""
Streamlit UI for the Multi-Agent Research System.
"""

import datetime
import os
import time
from typing import Any

import httpx
import streamlit as st

# Configure page
st.set_page_config(
    page_title="Deep Research Agent",
    page_icon="🧠",
    layout="wide",
)

# Constants
API_URL = os.getenv("API_URL", "http://localhost:8000")

# Session state
if "last_queries" not in st.session_state:
    st.session_state.last_queries = []
if "current_report" not in st.session_state:
    st.session_state.current_report = None


def run_research(query: str) -> dict[str, Any] | None:
    """Call the FastAPI backend to run research."""
    try:
        with httpx.Client(timeout=300.0) as client:
            response = client.post(
                f"{API_URL}/research",
                json={"query": query, "stream": False},
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        st.error(f"Error contacting backend: {e}")
        return None


def fetch_health() -> dict[str, Any]:
    """Check API health."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{API_URL}/health")
            response.raise_for_status()
            return response.json()
    except Exception:
        return {"status": "offline", "memory_count": 0}


# --- UI ---

st.title("🧠 Autonomous Deep Research Agent")
st.markdown("Enter a complex research query. The system will plan, search, summarize, critique, and compile a final cited report.")

# Sidebar
with st.sidebar:
    st.header("System Status")
    health = fetch_health()
    if health.get("status") == "ok":
        st.success("🟢 API Online")
        st.metric("Cached Reports", health.get("memory_count", 0))
    else:
        st.error("🔴 API Offline")

    st.header("Recent Queries")
    if not st.session_state.last_queries:
        st.info("No queries yet.")
    for q in reversed(st.session_state.last_queries[-5:]):
        st.text(f"• {q}")

# Main Input
with st.form("research_form"):
    query_input = st.text_area("Research Query", placeholder="e.g., How does CRISPR-Cas9 work?")
    submit_button = st.form_submit_button("Run Research")

if submit_button and query_input.strip():
    if query_input not in st.session_state.last_queries:
        st.session_state.last_queries.append(query_input)

    with st.status("Running Research Pipeline...", expanded=True) as status:
        st.write("Initializing agents...")
        start_time = time.time()
        
        # Execute request
        report_data = run_research(query_input)
        
        duration = time.time() - start_time
        if report_data:
            status.update(label=f"Research Complete in {duration:.1f}s", state="complete", expanded=False)
            st.session_state.current_report = report_data
        else:
            status.update(label="Research Failed", state="error")


# Display Report
if st.session_state.current_report:
    report = st.session_state.current_report
    
    st.divider()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header(report.get("title", "Research Report"))
    with col2:
        st.metric("Quality Score", f"{report.get('quality_score', 0):.2f}")
    
    # Render sections
    sections = report.get("sections", [])
    report_md = f"# {report.get('title')}\n\n"
    
    for section in sections:
        heading = section.get("heading", "")
        content = section.get("content", "")
        st.subheader(heading)
        st.markdown(content)
        report_md += f"## {heading}\n\n{content}\n\n"
        
        # Display supporting sources for this section inline
        sources = section.get("supporting_sources", [])
        if sources:
            with st.expander("Supporting Sources"):
                for src in sources:
                    st.write(f"- {src}")
    
    # Render Citations
    citations = report.get("citations", [])
    if citations:
        st.subheader("References")
        report_md += "## References\n\n"
        for i, cite in enumerate(citations, 1):
            st.write(f"{i}. {cite}")
            report_md += f"{i}. {cite}\n"
    
    # Export
    st.divider()
    st.download_button(
        label="Download Report as Markdown",
        data=report_md,
        file_name=f"report_{datetime.datetime.now().strftime('%Y%md_%H%M%S')}.md",
        mime="text/markdown",
    )
