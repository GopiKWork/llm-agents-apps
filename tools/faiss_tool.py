"""
FAISS Tool - Strands module-based tool for document storage and retrieval
using an in-memory FAISS vector store.

Supports: .txt, .md, .pdf
Embedding: sentence-transformers (all-MiniLM-L6-v2) running locally.
"""

import io
import os
import numpy as np
import faiss
import boto3
from pathlib import Path
from typing import Any, List, Dict, Optional
from sentence_transformers import SentenceTransformer


# ============================================================================
# Globals: embedding model + per-session stores
# ============================================================================

_model: Optional[SentenceTransformer] = None
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
EMBED_DIM = 384

# Per-session state: {session_id: {"index": faiss.Index, "chunks": [...]}}
_stores: Dict[str, dict] = {}


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL_NAME)
    return _model


def _get_store(session_id: str) -> dict:
    if session_id not in _stores:
        _stores[session_id] = {
            "index": faiss.IndexFlatL2(EMBED_DIM),
            "chunks": [],
        }
    return _stores[session_id]


# ============================================================================
# Document parsing
# ============================================================================

def _read_file_bytes(filepath: str) -> bytes:
    with open(filepath, "rb") as f:
        return f.read()


def _read_s3_bytes(s3_path: str, region: str = "us-west-2") -> bytes:
    if not s3_path.startswith("s3://"):
        raise ValueError("S3 path must start with 's3://'")
    parts = s3_path[5:].split("/", 1)
    bucket, key = parts[0], parts[1] if len(parts) > 1 else ""
    return boto3.client("s3", region_name=region).get_object(Bucket=bucket, Key=key)["Body"].read()


def _detect_type(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    if ext in (".txt", ".text"):
        return "txt"
    elif ext in (".md", ".markdown"):
        return "md"
    elif ext == ".pdf":
        return "pdf"
    return "txt"


def _parse(raw: bytes, doc_type: str) -> str:
    if doc_type == "pdf":
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        return "\n\n".join(p.extract_text() or "" for p in reader.pages)
    return raw.decode("utf-8", errors="replace")


def _chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start:start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


# ============================================================================
# Response helpers
# ============================================================================

def _ok(tid: str, text: str) -> dict:
    return {"toolUseId": tid, "status": "success", "content": [{"text": text}]}


def _error(tid: str, text: str) -> dict:
    return {"toolUseId": tid, "status": "error", "content": [{"text": text}]}


# ============================================================================
# Action handlers
# ============================================================================

def _do_store(session_id, tid, source_name, raw_bytes, chunk_size, chunk_overlap):
    doc_type = _detect_type(source_name)
    text = _parse(raw_bytes, doc_type)
    if not text.strip():
        return _error(tid, "Error: document is empty after parsing")

    chunks = _chunk_text(text, chunk_size, chunk_overlap)
    if not chunks:
        return _error(tid, "Error: no chunks produced")

    embeddings = np.array(_get_model().encode(chunks, show_progress_bar=False), dtype="float32")

    store = _get_store(session_id)
    base_id = len(store["chunks"])
    for i, chunk in enumerate(chunks):
        store["chunks"].append({"text": chunk, "source": source_name, "chunk_id": base_id + i})
    store["index"].add(embeddings)

    return _ok(tid, f"Stored {len(chunks)} chunks from '{source_name}' (type: {doc_type}, chars: {len(text)})")


def _store_file(inp, tid):
    filepath = inp.get("filepath")
    if not filepath:
        return _error(tid, "Error: filepath is required")
    if not os.path.exists(filepath):
        return _error(tid, f"Error: file not found: {filepath}")
    raw = _read_file_bytes(filepath)
    return _do_store(inp["session_id"], tid, filepath, raw,
                     inp.get("chunk_size", 512), inp.get("chunk_overlap", 64))


def _store_s3(inp, tid):
    s3_path = inp.get("s3_path")
    if not s3_path:
        return _error(tid, "Error: s3_path is required")
    raw = _read_s3_bytes(s3_path, inp.get("aws_region", "us-west-2"))
    return _do_store(inp["session_id"], tid, s3_path, raw,
                     inp.get("chunk_size", 512), inp.get("chunk_overlap", 64))


def _list_documents(inp, tid):
    store = _get_store(inp["session_id"])
    sources = sorted(set(c["source"] for c in store["chunks"]))
    return _ok(tid, "\n".join(sources) if sources else "No documents stored yet")


def _stats(inp, tid):
    store = _get_store(inp["session_id"])
    sources = set(c["source"] for c in store["chunks"])
    return _ok(tid, f"Documents: {len(sources)}\nChunks: {len(store['chunks'])}\nIndex size: {store['index'].ntotal}")


def _search(inp, tid):
    query = inp.get("query")
    if not query:
        return _error(tid, "Error: query is required")

    store = _get_store(inp["session_id"])
    if store["index"].ntotal == 0:
        return _error(tid, "Error: no documents stored yet")

    top_k = min(inp.get("top_k", 5), store["index"].ntotal)
    q_emb = np.array(_get_model().encode([query], show_progress_bar=False), dtype="float32")
    distances, indices = store["index"].search(q_emb, top_k)

    results = []
    for rank, (idx, dist) in enumerate(zip(indices[0], distances[0]), 1):
        chunk = store["chunks"][idx]
        results.append(f"[{rank}] (score: {dist:.4f}) source: {chunk['source']}\n{chunk['text']}")

    return _ok(tid, "\n\n".join(results))


# ============================================================================
# TOOL_SPEC and entry point
# ============================================================================

TOOL_SPEC = {
    "name": "faiss_tool",
    "description": (
        "FAISS vector store tool for document storage and semantic retrieval.\n\n"
        "Supports: .txt, .md, .pdf\n\n"
        "Actions:\n"
        "- store_file: Parse, chunk, embed and store a local file\n"
        "- store_s3: Store a file from S3\n"
        "- search: Semantic search over stored documents\n"
        "- list_documents: List stored document sources\n"
        "- stats: Show store statistics\n"
    ),
    "inputSchema": {
        "json": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to perform",
                    "enum": ["store_file", "store_s3", "search", "list_documents", "stats"],
                },
                "session_id": {"type": "string", "description": "Session ID (required)"},
                "filepath": {"type": "string", "description": "Local file path (for store_file)"},
                "s3_path": {"type": "string", "description": "S3 path s3://bucket/key (for store_s3)"},
                "query": {"type": "string", "description": "Search query text (for search)"},
                "top_k": {"type": "integer", "description": "Number of search results (default: 5)"},
                "chunk_size": {"type": "integer", "description": "Chunk size in chars (default: 512)"},
                "chunk_overlap": {"type": "integer", "description": "Overlap in chars (default: 64)"},
                "aws_region": {"type": "string", "description": "AWS region (default: us-west-2)"},
            },
            "required": ["action", "session_id"],
        }
    },
}

_ACTIONS = {
    "store_file": _store_file,
    "store_s3": _store_s3,
    "search": _search,
    "list_documents": _list_documents,
    "stats": _stats,
}


def faiss_tool(tool: dict, **kwargs: Any) -> dict:
    """FAISS vector store tool: store documents and search semantically."""
    try:
        tid = tool.get("toolUseId", "default-id")
        inp = tool.get("input", {})
        action = inp.get("action")
        session_id = inp.get("session_id")

        if not action:
            return _error(tid, "Error: action is required")
        if not session_id:
            return _error(tid, "Error: session_id is required")

        handler = _ACTIONS.get(action)
        if not handler:
            return _error(tid, f"Error: Unknown action '{action}'")

        return handler(inp, tid)

    except Exception as e:
        return _error(tool.get("toolUseId", "default-id"), f"Error: {str(e)}")
