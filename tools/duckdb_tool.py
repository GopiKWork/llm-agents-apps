"""
DuckDB Tool - Strands module-based tool for data analysis.
Includes all DuckDB operations inline (no external helper class).
"""

import duckdb
import pandas as pd
from typing import Any, List, Optional
from pathlib import Path

from tools.excel_tool import read_workbook, read_workbook_from_s3, get_worksheet_names, read_worksheet_data


# ============================================================================
# Session-scoped DuckDB connections
# ============================================================================

_connections: dict[str, duckdb.DuckDBPyConnection] = {}


def _get_conn(session_id: str) -> duckdb.DuckDBPyConnection:
    if session_id not in _connections:
        _connections[session_id] = duckdb.connect(f"/tmp/duckdb_{session_id}.duckdb")
    return _connections[session_id]


# ============================================================================
# Inline DB helpers (only what the tool actions actually use)
# ============================================================================

def _load_excel_data(conn: duckdb.DuckDBPyConnection, data: List[List], table_name: str) -> None:
    """Load list-of-lists (first row = headers) into a DuckDB table."""
    if not data:
        raise ValueError("Data cannot be empty")
    df = pd.DataFrame(data[1:], columns=data[0])
    conn.execute(f"DROP TABLE IF EXISTS {table_name}")
    conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")


def _query(conn: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return conn.execute(sql).df()


def _list_tables(conn: duckdb.DuckDBPyConnection) -> List[str]:
    return [r[0] for r in conn.execute("SHOW TABLES").fetchall()]


def _describe_table(conn: duckdb.DuckDBPyConnection, table: str) -> pd.DataFrame:
    return conn.execute(f"DESCRIBE {table}").df()


def _get_table_info(conn: duckdb.DuckDBPyConnection, table: str) -> dict:
    schema = _describe_table(conn, table)
    row_count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return {"name": table, "columns": schema.to_dict("records"), "row_count": row_count}


def _get_statistics(conn: duckdb.DuckDBPyConnection, table: str, column: str) -> dict:
    r = conn.execute(f"""
        SELECT MIN({column}), MAX({column}), AVG({column}),
               STDDEV({column}), COUNT({column}), COUNT(DISTINCT {column})
        FROM {table}
    """).fetchone()
    return {"min": r[0], "max": r[1], "avg": r[2], "stddev": r[3], "count": r[4], "distinct_count": r[5]}


def _export_csv(conn: duckdb.DuckDBPyConnection, table: str, path: str) -> None:
    conn.execute(f"COPY {table} TO '{path}' (HEADER, DELIMITER ',')")


# ============================================================================
# Response helpers
# ============================================================================

def _ok(tid: str, text: str) -> dict:
    return {"toolUseId": tid, "status": "success", "content": [{"text": text}]}


def _error(tid: str, text: str) -> dict:
    return {"toolUseId": tid, "status": "error", "content": [{"text": text}]}


# ============================================================================
# Shared Excel-load logic (used by load_excel and load_excel_s3)
# ============================================================================

def _do_load(conn, tid, inp, from_s3=False):
    """Load an Excel file (local or S3) into a DuckDB table."""
    if from_s3:
        s3_path = inp.get("s3_path")
        if not s3_path:
            return _error(tid, "Error: s3_path is required")
        workbook = read_workbook_from_s3(s3_path, inp.get("aws_region", "us-west-2"))
        default_name = s3_path.split("/")[-1].replace(".xlsx", "").replace(".xls", "")
    else:
        filepath = inp.get("filepath")
        if not filepath:
            return _error(tid, "Error: filepath is required")
        workbook = read_workbook(filepath)
        default_name = Path(filepath).stem

    sheets = get_worksheet_names(workbook)
    if not sheets:
        return _error(tid, "Error: No sheets found in Excel file")

    target = inp.get("sheet_name") or sheets[0]
    if target not in sheets:
        return _error(tid, f"Error: Sheet '{target}' not found. Available: {', '.join(sheets)}")

    data = read_worksheet_data(workbook[target])
    if not data:
        return _error(tid, "Error: No data found in sheet")

    table_name = inp.get("table_name") or default_name.replace("-", "_").replace(".", "_").replace(" ", "_")
    _load_excel_data(conn, data, table_name)

    src = " from S3" if from_s3 else ""
    return _ok(tid, f"Loaded {len(data) - 1} rows{src} from '{target}' into table '{table_name}'")


# ============================================================================
# TOOL_SPEC and entry point
# ============================================================================

TOOL_SPEC = {
    "name": "duckdb_tool",
    "description": (
        "DuckDB data analysis tool for loading and querying data.\n\n"
        "Actions:\n"
        "- load_excel: Load Excel file into DuckDB\n"
        "- load_excel_s3: Load Excel file from S3\n"
        "- show_tables: List all tables\n"
        "- describe_table: Get table schema\n"
        "- run_query: Execute SQL query\n"
        "- get_sample: Get sample rows\n"
        "- get_summary: Get table summary\n"
        "- get_stats: Get column statistics\n"
        "- filter: Filter table data\n"
        "- aggregate: Aggregate data\n"
        "- export_csv: Export to CSV\n"
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform",
                    "enum": ["load_excel", "load_excel_s3", "show_tables", "describe_table",
                             "run_query", "get_sample", "get_summary", "get_stats",
                             "filter", "aggregate", "export_csv"],
                },
                "session_id": {"type": "string", "description": "Session ID for database isolation (required)"},
                "filepath": {"type": "string", "description": "Path to Excel file"},
                "s3_path": {"type": "string", "description": "S3 path (s3://bucket/key)"},
                "table_name": {"type": "string", "description": "Table name"},
                "sheet_name": {"type": "string", "description": "Sheet name (optional, defaults to first)"},
                "query": {"type": "string", "description": "SQL query for run_query"},
                "column_name": {"type": "string", "description": "Column name for get_stats"},
                "conditions": {"type": "string", "description": "WHERE clause for filter"},
                "group_by": {"type": "string", "description": "Comma-separated columns for aggregate"},
                "aggregations": {"type": "string", "description": "Aggregation expressions for aggregate"},
                "limit": {"type": "integer", "description": "Row limit (default: 100)"},
                "n": {"type": "integer", "description": "Sample rows (default: 10)"},
                "output_path": {"type": "string", "description": "Output file path for export"},
                "aws_region": {"type": "string", "description": "AWS region (default: us-west-2)"},
            },
            "required": ["action", "session_id"],
        }
    },
}


def duckdb_tool(tool: dict, **kwargs: Any) -> dict:
    """DuckDB data analysis tool for loading and querying data."""
    try:
        tid = tool.get("toolUseId", "default-id")
        inp = tool.get("input", {})
        action = inp.get("action")
        session_id = inp.get("session_id")

        if not action:
            return _error(tid, "Error: action parameter is required")
        if not session_id:
            return _error(tid, "Error: session_id parameter is required")

        conn = _get_conn(session_id)

        # --- load actions ---
        if action in ("load_excel", "load_excel_s3"):
            return _do_load(conn, tid, inp, from_s3=(action == "load_excel_s3"))

        # --- query actions ---
        elif action == "show_tables":
            tables = _list_tables(conn)
            return _ok(tid, ", ".join(tables) if tables else "No tables found")

        elif action == "describe_table":
            tn = inp.get("table_name")
            if not tn:
                return _error(tid, "Error: table_name is required")
            df = _describe_table(conn, tn)
            return _ok(tid, f"Table: {tn}\n{df.to_string(index=False)}")

        elif action == "run_query":
            q = inp.get("query")
            if not q:
                return _error(tid, "Error: query is required")
            df = _query(conn, q)
            return _ok(tid, df.to_string(index=False) if not df.empty else "Query returned no results")

        elif action == "get_sample":
            tn = inp.get("table_name")
            if not tn:
                return _error(tid, "Error: table_name is required")
            df = _query(conn, f"SELECT * FROM {tn} LIMIT {inp.get('n', 10)}")
            return _ok(tid, df.to_string(index=False))

        elif action == "get_summary":
            tn = inp.get("table_name")
            if not tn:
                return _error(tid, "Error: table_name is required")
            info = _get_table_info(conn, tn)
            lines = [f"Table: {info['name']}", f"Rows: {info['row_count']}",
                     f"Columns: {len(info['columns'])}", "", "Column Details:"]
            for c in info["columns"]:
                lines.append(f"  - {c['column_name']}: {c['column_type']}")
            return _ok(tid, "\n".join(lines))

        elif action == "get_stats":
            tn = inp.get("table_name")
            cn = inp.get("column_name")
            if not tn:
                return _error(tid, "Error: table_name is required")
            if not cn:
                return _error(tid, "Error: column_name is required")
            s = _get_statistics(conn, tn, cn)
            lines = [f"Statistics for {tn}.{cn}:",
                     f"  Min: {s['min']}", f"  Max: {s['max']}", f"  Average: {s['avg']}",
                     f"  Std Dev: {s['stddev']}", f"  Count: {s['count']}", f"  Distinct: {s['distinct_count']}"]
            return _ok(tid, "\n".join(lines))

        elif action == "filter":
            tn = inp.get("table_name")
            cond = inp.get("conditions")
            if not tn:
                return _error(tid, "Error: table_name is required")
            if not cond:
                return _error(tid, "Error: conditions is required")
            df = _query(conn, f"SELECT * FROM {tn} WHERE {cond} LIMIT {inp.get('limit', 100)}")
            return _ok(tid, df.to_string(index=False))

        elif action == "aggregate":
            tn = inp.get("table_name")
            gb = inp.get("group_by")
            agg = inp.get("aggregations")
            if not tn:
                return _error(tid, "Error: table_name is required")
            if not gb:
                return _error(tid, "Error: group_by is required")
            if not agg:
                return _error(tid, "Error: aggregations is required")
            df = _query(conn, f"SELECT {gb}, {agg} FROM {tn} GROUP BY {gb}")
            return _ok(tid, df.to_string(index=False))

        elif action == "export_csv":
            tn = inp.get("table_name")
            op = inp.get("output_path")
            if not tn:
                return _error(tid, "Error: table_name is required")
            if not op:
                return _error(tid, "Error: output_path is required")
            _export_csv(conn, tn, op)
            return _ok(tid, f"Exported table '{tn}' to {op}")

        else:
            return _error(tid, f"Error: Unknown action '{action}'")

    except Exception as e:
        return _error(tool.get("toolUseId", "default-id"), f"Error: {str(e)}")
