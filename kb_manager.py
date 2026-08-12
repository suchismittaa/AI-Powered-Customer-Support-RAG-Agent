"""
kb_manager.py — Knowledge Base management helpers

Surfaces real information about the documents already sitting in
data/support_docs/ and the chunks already stored in ChromaDB, so the
"Knowledge Base" page in the UI reflects the actual ingestion pipeline
(ingest.py) instead of fabricated numbers. Also exposes upload +
re-ingest actions that call straight into the existing pipeline.
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DOCS_DIR = Path("data/support_docs")
CHROMA_PERSIST_DIR = "./chroma_db"
COLLECTION_NAME = "support_kb"
ALLOWED_EXTENSIONS = {".txt", ".pdf"}


def _get_collection():
    """Open a read-only handle to the existing Chroma collection, if any."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        return client.get_collection(COLLECTION_NAME)
    except Exception:
        return None


def _chunk_counts_by_source() -> dict[str, int]:
    """Count how many stored chunks belong to each source file, using the
    same 'source_file' metadata tag that ingest.py writes for every chunk."""
    collection = _get_collection()
    if collection is None:
        return {}
    try:
        data = collection.get(include=["metadatas"])
    except Exception:
        return {}

    counts: dict[str, int] = {}
    for meta in data.get("metadatas") or []:
        source = (meta or {}).get("source_file", "unknown")
        counts[source] = counts.get(source, 0) + 1
    return counts


def list_documents() -> list[dict]:
    """List every source document on disk, with real chunk counts and
    file modification times (used as an 'updated' signal in the UI)."""
    if not DOCS_DIR.exists():
        return []

    chunk_counts = _chunk_counts_by_source()
    docs = []
    for path in sorted(DOCS_DIR.rglob("*")):
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        stat = path.stat()
        docs.append({
            "filename": path.name,
            "size_bytes": stat.st_size,
            "chunks": chunk_counts.get(path.name, 0),
            "updated_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })
    return docs


def get_kb_health(rag=None) -> dict:
    """Compile a knowledge-base health snapshot from real, available data
    only — no invented production metrics."""
    docs = list_documents()
    total_chunks = sum(d["chunks"] for d in docs)
    indexed_chunks = 0
    try:
        if rag is not None:
            indexed_chunks = rag.doc_count
    except Exception:
        pass

    stale_docs = [d["filename"] for d in docs if d["chunks"] == 0]

    last_indexed = None
    chroma_sqlite = Path(CHROMA_PERSIST_DIR) / "chroma.sqlite3"
    if chroma_sqlite.exists():
        last_indexed = datetime.fromtimestamp(
            chroma_sqlite.stat().st_mtime, tz=timezone.utc
        ).isoformat()

    return {
        "documents": len(docs),
        "chunks_on_disk": total_chunks,
        "chunks_indexed": indexed_chunks,
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "vector_database": "ChromaDB",
        "last_indexed": last_indexed,
        "documents_not_yet_indexed": stale_docs,
    }


def save_uploaded_file(filename: str, content: bytes) -> str:
    """Persist an uploaded document into data/support_docs/ so the next
    ingestion run (POST /kb/ingest) picks it up. Does not modify the
    vector store directly — ingestion stays a single, explicit pipeline."""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{suffix}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(filename).name  # strip any path components
    dest = DOCS_DIR / safe_name
    with open(dest, "wb") as f:
        f.write(content)
    return safe_name


def run_ingestion() -> dict:
    """Run the existing ingest.py pipeline end-to-end and return a summary.
    This intentionally reuses ingest.load_documents/split_documents/
    store_in_chroma rather than reimplementing ingestion logic."""
    import ingest as ingest_module

    documents = ingest_module.load_documents(ingest_module.DOCS_DIR)
    if not documents:
        raise RuntimeError("No documents found to ingest.")
    chunks = ingest_module.split_documents(documents)
    embeddings = ingest_module.get_embeddings()
    ingest_module.store_in_chroma(chunks, embeddings)

    return {
        "documents_loaded": len(documents),
        "chunks_stored": len(chunks),
        "completed_at": datetime.utcnow().isoformat() + "Z",
    }
