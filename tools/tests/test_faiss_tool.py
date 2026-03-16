"""Tests for faiss_tool following strands_tools test conventions."""

import os
import pytest
from tools.faiss_tool import faiss_tool

SESSION = "pytest_faiss"
TXT_FILE = "/tmp/test_faiss.txt"
MD_FILE = "/tmp/test_faiss.md"


def _call(action, **params):
    return faiss_tool({"toolUseId": "test-id", "input": {"action": action, "session_id": SESSION, **params}})


@pytest.fixture(autouse=True, scope="module")
def create_files():
    with open(TXT_FILE, "w") as f:
        f.write("Python was created by Guido van Rossum in 1991. "
                "It supports object-oriented and functional programming.")
    with open(MD_FILE, "w") as f:
        f.write("# ML\n\nMachine learning is a subset of AI.")
    _call("store_file", filepath=TXT_FILE)
    _call("store_file", filepath=MD_FILE)
    yield
    for f in [TXT_FILE, MD_FILE]:
        if os.path.exists(f):
            os.remove(f)


# --- Store actions ---

def test_store_txt():
    r = _call("store_file", filepath=TXT_FILE)
    assert r["status"] == "success"
    assert "chunks" in r["content"][0]["text"]


def test_store_md():
    r = _call("store_file", filepath=MD_FILE)
    assert r["status"] == "success"
    assert "chunks" in r["content"][0]["text"]


def test_list_documents():
    r = _call("list_documents")
    assert r["status"] == "success"
    assert TXT_FILE in r["content"][0]["text"]


def test_stats():
    r = _call("stats")
    assert r["status"] == "success"
    assert "Chunks:" in r["content"][0]["text"]


# --- Search actions ---

def test_search():
    r = _call("search", query="Who created Python?")
    assert r["status"] == "success"
    assert "Guido" in r["content"][0]["text"]


def test_search_top_k():
    r = _call("search", query="programming", top_k=1)
    assert r["status"] == "success"
    assert "[1]" in r["content"][0]["text"]


def test_search_empty_store():
    r = faiss_tool({"toolUseId": "t", "input": {"action": "search", "session_id": "empty_session", "query": "test"}})
    assert r["status"] == "error"
    assert "no documents" in r["content"][0]["text"].lower()


# --- Error cases ---

def test_missing_action():
    r = faiss_tool({"toolUseId": "t", "input": {"session_id": SESSION}})
    assert r["status"] == "error"


def test_missing_session():
    r = faiss_tool({"toolUseId": "t", "input": {"action": "stats"}})
    assert r["status"] == "error"


def test_unknown_action():
    r = _call("bogus")
    assert r["status"] == "error"


def test_missing_filepath():
    r = _call("store_file")
    assert r["status"] == "error"


def test_file_not_found():
    r = _call("store_file", filepath="/tmp/nonexistent_file.txt")
    assert r["status"] == "error"


def test_missing_query():
    r = _call("search")
    assert r["status"] == "error"
