# Analysis Agents

Multi-turn conversational AI agents built on [Strands Agents SDK](https://strandsagents.com/) with custom tools for data analysis, document Q&A, and financial research.

## Overview

This project provides three specialized agents that can be used via a Streamlit web UI or programmatically. Each agent supports multi-turn conversations with session persistence via `FileSessionManager`. Tools follow the Strands module-based tool pattern and live in the sibling `tools/` folder.

Model: Amazon Bedrock (`global.anthropic.claude-sonnet-4-5-20250929-v1:0`)

## Agents

### Excel Analyzer

Analyze Excel spreadsheets using natural language. Loads files into DuckDB for SQL-based analysis.

- Upload `.xlsx` / `.xls` files via the UI or provide a file path
- Run SQL queries, filter, aggregate, get statistics, export to CSV
- Tools: `excel_tool`, `duckdb_tool`

### RAG Document Q&A

Semantic search and question answering over documents using FAISS vector store.

- Upload `.txt`, `.md`, `.pdf` files
- Documents are chunked, embedded (all-MiniLM-L6-v2), and stored in FAISS
- Ask questions and get answers grounded in document content
- Tools: `faiss_tool`

### Financial Analyst

Stock research combining live market data with uploaded documents and spreadsheets.

- Fetch real-time stock prices, fundamentals, income statements, analyst recommendations, news, and technical indicators
- Cross-reference live data with uploaded Excel spreadsheets or research documents
- Upload `.xlsx`, `.xls`, `.txt`, `.md`, `.pdf` files
- Tools: `yfinance_tool`, `excel_tool`, `duckdb_tool`, `faiss_tool`

## Tools

All tools follow the Strands module-based pattern: a module-level `TOOL_SPEC` dict and a function with matching name. Function signature: `def tool_name(tool: dict, **kwargs) -> dict`. Returns a ToolResult dict with `toolUseId`, `status`, and `content`.

| Tool | File | Description | Actions |
|------|------|-------------|---------|
| `excel_tool` | `tools/excel_tool.py` | Read and inspect Excel files | `read_file`, `read_s3`, `list_sheets`, `get_info` |
| `duckdb_tool` | `tools/duckdb_tool.py` | Load Excel into DuckDB, run SQL | `load_excel`, `load_excel_s3`, `run_query`, `describe_table`, `show_tables`, `get_sample`, `get_summary`, `get_stats`, `filter`, `aggregate`, `export_csv` |
| `faiss_tool` | `tools/faiss_tool.py` | FAISS vector store for document storage and semantic search | `store_file`, `store_s3`, `search`, `list_documents`, `stats` |
| `yfinance_tool` | `tools/yfinance_tool.py` | Yahoo Finance market data | `stock_price`, `company_info`, `stock_fundamentals`, `income_statements`, `analyst_recommendations`, `historical_prices`, `company_news`, `technical_indicators` |

## Project Structure

```
analysis_agents/
    __init__.py              # Package exports
    base_agent.py            # BaseAgent class (session, chat, response extraction)
    excel_analyzer.py        # ExcelAnalyzerAgent(BaseAgent)
    rag_agent.py             # RagAgent(BaseAgent)
    financial_analyst.py     # FinancialAnalystAgent(BaseAgent)
    app.py                   # Streamlit UI
    requirements.txt         # Python dependencies
    README.md
    .venv/                   # Python 3.11 virtual environment
tools/
    __init__.py
    excel_tool.py
    duckdb_tool.py
    faiss_tool.py
    yfinance_tool.py
    tests/
        __init__.py
        test_excel_tool.py
        test_duckdb_tool.py
        test_faiss_tool.py
        test_yfinance_tool.py
        test_products.xlsx   # Test fixture
```

## Setup

### Prerequisites

- Python 3.11+
- AWS credentials configured for Bedrock access (for the default model)

### Install

```bash
# Create virtual environment
python3.11 -m venv analysis_agents/.venv

# Install dependencies
analysis_agents/.venv/bin/pip install -r analysis_agents/requirements.txt
```

Note: `sentence-transformers==2.7.0` and `numpy<2` are pinned for torch 2.2.2 compatibility on x86 Mac.

## Usage

### Streamlit App

```bash
analysis_agents/.venv/bin/streamlit run analysis_agents/app.py
```

- Select an agent from the sidebar dropdown
- Upload files using the sidebar uploader (accepted types depend on agent)
- Chat in the main panel -- conversations persist across messages within a session
- Click "New session" to start fresh

### Programmatic

```python
from analysis_agents import ExcelAnalyzerAgent, RagAgent, FinancialAnalystAgent

# Excel analysis
agent = ExcelAnalyzerAgent(session_id="my-session")
agent.chat("Load the file /path/to/data.xlsx")
print(agent.chat("What are the top 5 products by revenue?"))

# Document Q&A
rag = RagAgent(session_id="rag-session")
rag.chat("Store the file /path/to/report.pdf")
print(rag.chat("What were the key findings?"))

# Financial research
fin = FinancialAnalystAgent(session_id="fin-session")
print(fin.chat("Get me the current price and fundamentals for AAPL"))
print(fin.chat("Compare AAPL vs MSFT technical indicators"))
```

## Running Tests

```bash
# All tests
analysis_agents/.venv/bin/python -m pytest tools/tests/ -v

# Individual tool tests
analysis_agents/.venv/bin/python -m pytest tools/tests/test_excel_tool.py -v
analysis_agents/.venv/bin/python -m pytest tools/tests/test_duckdb_tool.py -v
analysis_agents/.venv/bin/python -m pytest tools/tests/test_faiss_tool.py -v
analysis_agents/.venv/bin/python -m pytest tools/tests/test_yfinance_tool.py -v
```

Test counts: excel_tool (10), duckdb_tool (16), faiss_tool (13), yfinance_tool (13) = 52 total.

## Architecture

### BaseAgent

All agents extend `BaseAgent` which provides:
- Session management via Strands `FileSessionManager` (sessions stored in `analysis_agents/.sessions/`)
- `chat(message)` method for multi-turn conversation
- Response text extraction from Strands `AgentResult`
- Configurable model ID (defaults to Bedrock Claude Sonnet)

Subclasses implement `_get_tools()` and `_get_instructions()`.

### Tool Pattern

Each tool module exports:
- `TOOL_SPEC`: dict with `name`, `description`, and `inputSchema` (JSON Schema)
- A function matching the tool name: `def tool_name(tool: dict, **kwargs) -> dict`
- The `tool` dict contains `toolUseId` (for response correlation) and `input` (the parameters)
- Returns `{"toolUseId": ..., "status": "success"|"error", "content": [{"text": ...}]}`

Tools that need multi-user isolation (`duckdb_tool`, `faiss_tool`) require a `session_id` parameter.

### Streamlit App

- Agent selection dropdown with dynamic file type filtering
- File upload saves to temp directory and auto-sends a load/store message to the agent
- Chat history maintained in `st.session_state`
- New session button resets everything
