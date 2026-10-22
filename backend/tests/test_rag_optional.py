import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest


@pytest.fixture
def rag(monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "false")
    monkeypatch.delenv("CHROMA_DIR", raising=False)
    monkeypatch.delenv("RAG_ALLOW_MODEL_DOWNLOAD", raising=False)
    from app.services import rag_service
    return importlib.reload(rag_service)


def test_disabled_import_does_not_load_chroma_or_create_files(rag, tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "must-not-exist"))
    assert "chromadb" not in sys.modules
    assert rag.query_rag("synthetic question") == ""
    assert rag.add_document_to_rag(1, "synthetic title", "synthetic document") is False
    assert rag.delete_document_from_rag(1) is False
    assert not (tmp_path / "must-not-exist").exists()
    assert rag.get_rag_status() == {"enabled": False, "ready": False, "state": "disabled"}
    with pytest.raises(rag.RagUnavailable):
        rag.embedding_function(["synthetic question"])


def test_enabled_requires_explicit_store_and_embedding_opt_in(rag, monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "true")
    assert rag.query_rag("question") == ""
    assert rag.get_rag_status()["state"] == "store_not_configured"
    with pytest.raises(rag.RagUnavailable):
        rag.embedding_function(["question"])
    assert "chromadb" not in sys.modules


@pytest.mark.parametrize("size,overlap", [(0, 0), (5, 5), (5, 7), (5, -1)])
def test_chunking_rejects_nonprogressing_ranges(rag, size, overlap):
    with pytest.raises(ValueError):
        rag.chunk_text("synthetic document", size, overlap)


def test_chunking_retains_overlap_and_empty_input(rag):
    assert rag.chunk_text("abcdefghij", 5, 2) == ["abcde", "defgh", "ghij", "j"]
    assert rag.chunk_text("") == []


def test_enabled_backend_is_lazy_and_reuses_explicit_store(rag, monkeypatch, tmp_path):
    calls = []
    store = SimpleNamespace(upsert=lambda **kw: calls.append(("upsert", kw)),
                            delete=lambda **kw: calls.append(("delete", kw)), count=lambda: 1,
                            query=lambda **kw: {"documents": [["synthetic text"]], "metadatas": [[{"title": "Guide"}]]})
    chroma = ModuleType("chromadb")
    chroma.PersistentClient = lambda path: calls.append(("client", path)) or SimpleNamespace(get_or_create_collection=lambda **kw: store)
    utils = ModuleType("chromadb.utils")
    utils.embedding_functions = SimpleNamespace(DefaultEmbeddingFunction=lambda: lambda text: [[1.0] for _ in text])
    monkeypatch.setitem(sys.modules, "chromadb", chroma)
    monkeypatch.setitem(sys.modules, "chromadb.utils", utils)
    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setenv("RAG_ALLOW_MODEL_DOWNLOAD", "true")
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "explicit-store"))
    assert calls == []
    assert rag.query_rag("question") == "【Guide】片段:\nsynthetic text"
    assert rag.add_document_to_rag(3, "Guide", "text") is True
    assert rag.delete_document_from_rag(3) is True
    assert sum(name == "client" for name, _ in calls) == 1
    assert calls[0][1] == str((tmp_path / "explicit-store").resolve())
    assert rag.get_rag_status()["ready"] is True


def test_backend_error_does_not_log_query_or_private_exception(rag, monkeypatch, tmp_path, caplog):
    chroma = ModuleType("chromadb")
    def fail(path):
        raise RuntimeError("synthetic-sensitive-provider-detail")
    chroma.PersistentClient = fail
    utils = ModuleType("chromadb.utils")
    utils.embedding_functions = SimpleNamespace(DefaultEmbeddingFunction=lambda: object())
    monkeypatch.setitem(sys.modules, "chromadb", chroma)
    monkeypatch.setitem(sys.modules, "chromadb.utils", utils)
    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setenv("RAG_ALLOW_MODEL_DOWNLOAD", "true")
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "explicit-store"))
    assert rag.query_rag("synthetic-private-question") == ""
    assert "synthetic-sensitive-provider-detail" not in caplog.text
    assert "synthetic-private-question" not in caplog.text
    assert rag.get_rag_status()["state"] == "optional_backend_unavailable"
