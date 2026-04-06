"""
Streamlit UI for Research Agent Swarm.
Select model provider (Bedrock/Ollama), enter a research task, view results.
"""

import sys
import os
from pathlib import Path

# Ensure workspace root is on sys.path
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

# Point all tool caches to research_agent/cache/
os.environ.setdefault(
    "RESEARCH_CACHE_DIR",
    os.path.join(os.path.dirname(__file__), "cache"),
)

# Suppress OpenTelemetry context detach warnings in Streamlit's threaded env
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import streamlit as st
from research_agent.orchestrator import run_research
from research_agent.config import DEFAULT_PROVIDER, DEFAULT_OLLAMA_MODEL, DEFAULT_BEDROCK_MODEL

st.set_page_config(page_title="Research Agent", layout="wide")
st.title("Research Agent Swarm")

# --- Sidebar ---
with st.sidebar:
    st.header("Configuration")

    providers = ["ollama", "bedrock"]
    provider = st.selectbox("Model Provider", providers, index=providers.index(DEFAULT_PROVIDER))

    if provider == "bedrock":
        model_id = st.text_input("Model ID", value=DEFAULT_BEDROCK_MODEL)
    else:
        model_id = st.text_input("Model ID", value=DEFAULT_OLLAMA_MODEL)

    st.divider()
    st.subheader("Web Research Configs")
    config_dir = os.path.join(os.path.dirname(__file__), "web_research")
    if os.path.isdir(config_dir):
        for fname in sorted(os.listdir(config_dir)):
            if fname.endswith(".md"):
                st.text(f"  {fname}")
    else:
        st.text("No configs found")

# --- Session state ---
if "research_messages" not in st.session_state:
    st.session_state.research_messages = []

# --- Chat history ---
for msg in st.session_state.research_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Chat input ---
if prompt := st.chat_input("Enter a research task..."):
    st.session_state.research_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Running research swarm..."):
            try:
                response = run_research(prompt, provider=provider, model_id=model_id)
            except Exception as e:
                response = f"Error: {str(e)}"
        st.markdown(response)
    st.session_state.research_messages.append({"role": "assistant", "content": response})
