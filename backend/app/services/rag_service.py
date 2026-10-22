"""Optional RAG: importing this module never opens a store or downloads a model."""
import logging
import os
from pathlib import Path
from threading import RLock

logger = logging.getLogger(__name__)
_lock = RLock()
_collection = None
_embedding = None
_initialization_error = None


class RagUnavailable(RuntimeError):
    pass


def _enabled():
    return os.getenv("RAG_ENABLED", "false").strip().lower() == "true"


def get_rag_status():
    """Metadata only; no imports, paths or document content."""
    return {"enabled": _enabled(), "ready": _collection is not None,
            "state": "disabled" if not _enabled() else _initialization_error or
            ("ready" if _collection is not None else "not_initialized")}


def _get_embedding():
    global _embedding
    if not _enabled():
        raise RagUnavailable("Optional vector retrieval is disabled")
    if os.getenv("RAG_ALLOW_MODEL_DOWNLOAD", "false").strip().lower() != "true":
        raise RagUnavailable("Embedding initialization requires explicit operator opt-in")
    with _lock:
        if _embedding is None:
            try:
                from chromadb.utils import embedding_functions
                _embedding = embedding_functions.DefaultEmbeddingFunction()
            except Exception:
                raise RagUnavailable("Optional embedding backend is unavailable") from None
        return _embedding


def embedding_function(input):
    """Compatibility callable used by the chat memory-recall pipeline."""
    return _get_embedding()(input)


def _get_collection():
    global _collection, _initialization_error
    if not _enabled():
        return None
    with _lock:
        if _collection is not None:
            return _collection
        if _initialization_error:
            return None
        directory = os.getenv("CHROMA_DIR", "").strip()
        if not directory:
            _initialization_error = "store_not_configured"
            return None
        try:
            embed = _get_embedding()
            import chromadb
            client = chromadb.PersistentClient(path=str(Path(directory).expanduser().resolve()))
            _collection = client.get_or_create_collection(name="health_knowledge", embedding_function=embed)
        except Exception as exc:
            _initialization_error = "optional_backend_unavailable"
            logger.warning("Optional RAG initialization unavailable (%s)", type(exc).__name__)
        return _collection


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Require chunk_size > overlap >= 0")
    return [text[start:start + chunk_size] for start in range(0, len(text), chunk_size - overlap)]


def add_document_to_rag(doc_id: int, title: str, content: str) -> bool:
    """Best-effort optional index; SQL knowledge records remain authoritative."""
    chunks = chunk_text(content)
    store = _get_collection() if chunks else None
    if store is None:
        return False
    try:
        store.upsert(documents=chunks,
                     metadatas=[{"doc_id": doc_id, "title": title, "chunk_index": i} for i in range(len(chunks))],
                     ids=[f"{doc_id}_chunk_{i}" for i in range(len(chunks))])
        return True
    except Exception as exc:
        logger.warning("Optional RAG indexing unavailable (%s)", type(exc).__name__)
        return False


def delete_document_from_rag(doc_id: int) -> bool:
    store = _get_collection()
    if store is None:
        return False
    try:
        store.delete(where={"doc_id": doc_id})
        return True
    except Exception as exc:
        logger.warning("Optional RAG removal unavailable (%s)", type(exc).__name__)
        return False


def query_rag(query: str, n_results: int = 3) -> str:
    if not query.strip() or n_results <= 0:
        return ""
    store = _get_collection()
    if store is None:
        return ""
    try:
        count = store.count()
        if not count:
            return ""
        results = store.query(query_texts=[query], n_results=min(n_results, count))
        documents = (results.get("documents") or [[]])[0] or []
        metadata = (results.get("metadatas") or [[]])[0] or []
        return "\n\n".join(f"【{(metadata[i] or {}).get('title', '知识库') if i < len(metadata) else '知识库'}】片段:\n{doc}"
                            for i, doc in enumerate(documents))
    except Exception as exc:
        logger.warning("Optional RAG query unavailable (%s)", type(exc).__name__)
        return ""
