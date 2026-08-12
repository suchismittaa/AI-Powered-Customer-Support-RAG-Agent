"""
ingest.py — Data Ingestion Pipeline for AI Customer Support RAG Agent

Loads PDF/TXT documents from data/support_docs/, splits them into chunks,
generates embeddings using HuggingFace all-MiniLM-L6-v2, and stores them
in a local ChromaDB collection called 'support_kb'.
"""

import os
import sys
from pathlib import Path
from typing import List

from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document


# ── Constants ────────────────────────────────────────────────────────────────
DOCS_DIR = Path("data/support_docs")
CHROMA_PERSIST_DIR = "./chroma_db"
COLLECTION_NAME = "support_kb"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def load_documents(docs_dir: Path) -> List[Document]:
    """
    Load all PDF and TXT files from the specified directory.

    Args:
        docs_dir: Path to the directory containing support documents.

    Returns:
        List of LangChain Document objects with content and metadata.

    Raises:
        FileNotFoundError: If the docs directory does not exist.
    """
    if not docs_dir.exists():
        raise FileNotFoundError(
            f"Documents directory not found: {docs_dir}\n"
            "Create it and add PDF or TXT files to ingest."
        )

    documents: List[Document] = []
    supported_extensions = {".txt", ".pdf"}
    files_found = 0

    for file_path in sorted(docs_dir.rglob("*")):
        if file_path.suffix.lower() not in supported_extensions:
            continue

        files_found += 1
        print(f"  📄 Loading: {file_path.name}")

        try:
            if file_path.suffix.lower() == ".pdf":
                loader = PyPDFLoader(str(file_path))
            else:
                loader = TextLoader(str(file_path), encoding="utf-8")

            docs = loader.load()
            # Tag each doc with the source filename for traceability
            for doc in docs:
                doc.metadata["source_file"] = file_path.name
            documents.extend(docs)

        except Exception as e:
            print(f"  ⚠️  Warning: Could not load {file_path.name}: {e}")

    if files_found == 0:
        print(f"⚠️  No PDF or TXT files found in {docs_dir}")
    else:
        print(f"\n✅ Loaded {len(documents)} document pages from {files_found} files.")

    return documents


def split_documents(documents: List[Document]) -> List[Document]:
    """
    Split loaded documents into overlapping chunks using RecursiveCharacterTextSplitter.

    Args:
        documents: List of LangChain Document objects to split.

    Returns:
        List of chunked Document objects ready for embedding.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.split_documents(documents)
    print(f"✅ Split into {len(chunks)} chunks "
          f"(chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}).")
    return chunks


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Initialize HuggingFace sentence-transformer embeddings (runs locally, no API key).

    Returns:
        HuggingFaceEmbeddings instance using all-MiniLM-L6-v2.
    """
    print(f"⚙️  Loading embedding model: {EMBEDDING_MODEL} ...")
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    print("✅ Embedding model loaded.")
    return embeddings


def store_in_chroma(chunks: List[Document], embeddings: HuggingFaceEmbeddings) -> Chroma:
    """
    Embed all chunks and persist them in a local ChromaDB collection.

    If the collection already exists, it is deleted and recreated to ensure
    a fresh, consistent index on each ingestion run.

    Args:
        chunks: List of chunked Document objects to store.
        embeddings: HuggingFace embedding function.

    Returns:
        Chroma vector store instance pointing to the persisted collection.
    """
    # Wipe existing collection for a clean re-index
    if Path(CHROMA_PERSIST_DIR).exists():
        import shutil
        shutil.rmtree(CHROMA_PERSIST_DIR)
        print("🗑️  Cleared existing ChromaDB collection for fresh ingestion.")

    print(f"💾 Embedding and storing {len(chunks)} chunks in ChromaDB ...")

    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_PERSIST_DIR,
    )

    print(f"✅ Stored {len(chunks)} chunks in collection '{COLLECTION_NAME}'.")
    print(f"   Persisted to: {Path(CHROMA_PERSIST_DIR).resolve()}")
    return vector_store


def ingest() -> None:
    """
    Main ingestion pipeline: load → split → embed → store.

    Orchestrates the full ingestion workflow and prints a summary report.
    """
    print("=" * 60)
    print("  AI Customer Support RAG — Data Ingestion Pipeline")
    print("=" * 60)

    # Step 1: Load documents
    print("\n[1/4] Loading documents ...")
    documents = load_documents(DOCS_DIR)

    if not documents:
        print("❌ No documents loaded. Exiting.")
        sys.exit(1)

    # Step 2: Split into chunks
    print("\n[2/4] Splitting into chunks ...")
    chunks = split_documents(documents)

    # Step 3: Load embeddings model
    print("\n[3/4] Initializing embeddings ...")
    embeddings = get_embeddings()

    # Step 4: Store in ChromaDB
    print("\n[4/4] Storing in ChromaDB ...")
    vector_store = store_in_chroma(chunks, embeddings)

    # Summary
    print("\n" + "=" * 60)
    print("  ✅ Ingestion Complete!")
    print(f"  📦 Total chunks stored : {len(chunks)}")
    print(f"  🗂️  Collection name     : {COLLECTION_NAME}")
    print(f"  💾 Storage path        : {Path(CHROMA_PERSIST_DIR).resolve()}")
    print(f"  🤖 Embedding model     : {EMBEDDING_MODEL}")
    print("=" * 60)


if __name__ == "__main__":
    ingest()
