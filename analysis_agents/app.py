"""
Streamlit UI for Analysis Agents.
Select an agent, upload files, and chat.
"""

import sys
import os
import tempfile
from pathlib import Path

# Ensure workspace root is on sys.path so analysis_agents / tools are importable
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

import streamlit as st
import uuid
from datetime import datetime
import importlib

AGENTS = {
    "Excel Analyzer": ("analysis_agents.excel_analyzer", "ExcelAnalyzerAgent"),
    "RAG Document Q&A": ("analysis_agents.rag_agent", "RagAgent"),
    "Financial Analyst": ("analysis_agents.financial_analyst", "FinancialAnalystAgent"),
}

ACCEPTED_FILES = {
    "Excel Analyzer": ["xlsx", "xls"],
    "RAG Document Q&A": ["txt", "md", "pdf"],
    "Financial Analyst": ["xlsx", "xls", "txt", "md", "pdf"],
}

LOAD_MESSAGES = {
    "Excel Analyzer": "Load the file {path}",
    "RAG Document Q&A": "Store the file {path}",
    "Financial Analyst": "Load the file {path}",
}

st.set_page_config(page_title="Analysis Agents", layout="wide")
st.title("Analysis Agents")

# --- Session state defaults ---
if "session_id" not in st.session_state:
    st.session_state.session_id = (
        f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    )
if "messages" not in st.session_state:
    st.session_state.messages = []
if "loaded_files" not in st.session_state:
    st.session_state.loaded_files = set()
if "agent" not in st.session_state:
    st.session_state.agent = None
if "agent_key" not in st.session_state:
    st.session_state.agent_key = None
if "pending_file_msg" not in st.session_state:
    st.session_state.pending_file_msg = None

# --- Sidebar ---
with st.sidebar:
    st.header("Configuration")
    agent_choice = st.selectbox("Agent", list(AGENTS.keys()))

    st.text(f"Session: {st.session_state.session_id}")

    if st.button("New session"):
        st.session_state.session_id = (
            f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        )
        st.session_state.agent = None
        st.session_state.agent_key = None
        st.session_state.messages = []
        st.session_state.loaded_files = set()
        st.session_state.pending_file_msg = None
        st.rerun()

    st.divider()
    st.subheader("Upload File")
    extensions = ACCEPTED_FILES[agent_choice]
    uploaded = st.file_uploader(
        f"Accepted: {', '.join(extensions)}",
        type=extensions,
        key=f"uploader_{agent_choice}",
    )

    if uploaded is not None and uploaded.name not in st.session_state.loaded_files:
        # Save to temp dir and queue a message for the agent
        tmp_dir = tempfile.mkdtemp()
        tmp_path = os.path.join(tmp_dir, uploaded.name)
        with open(tmp_path, "wb") as f:
            f.write(uploaded.getbuffer())
        st.session_state.loaded_files.add(uploaded.name)
        st.session_state.pending_file_msg = LOAD_MESSAGES[agent_choice].format(path=tmp_path)
        st.success(f"Uploaded: {uploaded.name}")

# --- Agent init ---
agent_key = f"{agent_choice}_{st.session_state.session_id}"
if st.session_state.agent_key != agent_key:
    module_path, class_name = AGENTS[agent_choice]
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    st.session_state.agent = cls(session_id=st.session_state.session_id)
    st.session_state.agent_key = agent_key

agent = st.session_state.agent

# --- Chat history ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Handle pending file upload message ---
if st.session_state.pending_file_msg:
    user_msg = st.session_state.pending_file_msg
    st.session_state.pending_file_msg = None

    st.session_state.messages.append({"role": "user", "content": user_msg})
    with st.chat_message("user"):
        st.markdown(user_msg)

    with st.chat_message("assistant"):
        with st.spinner("Processing file..."):
            response = agent.chat(user_msg)
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()

# --- Chat input ---
if prompt := st.chat_input("Ask a question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = agent.chat(prompt)
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
