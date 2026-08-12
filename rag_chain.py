"""
rag_chain.py — RAG Pipeline for AI Customer Support Agent

Loads the ChromaDB vector store, embeds user queries, retrieves relevant
context, classifies query complexity (L1/L2 triage), and generates
grounded answers via Groq LLaMA3.
"""

import os
import hashlib
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document

load_dotenv()

# ── Constants ────────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = "./chroma_db"
COLLECTION_NAME = "support_kb"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
GROQ_MODEL = "llama-3.1-8b-instant"
TOP_K_RESULTS = 8

# Triage thresholds
L1_CONFIDENCE_THRESHOLD = 0.25   # similarity score above this → L1 (simple FAQ)
L2_WORD_COUNT_THRESHOLD = 30      # queries longer than this hint at L2 complexity
L2_COMPLEXITY_KEYWORDS = [
    "escalate", "manager", "legal", "lawsuit", "fraud", "hack", "breach",
    "discrimination", "urgent", "emergency", "severe", "data loss", "corrupted",
    "lost all", "cannot work", "blocking", "critical", "down for days",
    "threatening", "complaint", "regulatory", "compliance",
]

# Cache file
CACHE_FILE = "./response_cache.json"


@dataclass
class RetrievedChunk:
    """A single retrieved context chunk, kept for source-attribution UI."""
    source: str
    text: str
    score: float = 0.0


@dataclass
class RAGResponse:
    """Structured response from the RAG pipeline."""
    answer: str
    sources: list[str]
    triage_level: str          # "L1" or "L2"
    triage_reason: str
    confidence_score: float
    query: str
    from_cache: bool = False
    retrieved_chunks: list = field(default_factory=list)  # list[RetrievedChunk]


def _load_cache() -> dict:
    """
    Load the response cache from disk.

    Returns:
        Dictionary mapping query hashes to cached RAGResponse dicts.
    """
    if Path(CACHE_FILE).exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_cache(cache: dict) -> None:
    """
    Persist the response cache to disk.

    Args:
        cache: Dictionary of cached responses to save.
    """
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"⚠️  Cache write failed: {e}")


def _query_hash(query: str) -> str:
    """
    Generate a stable hash for a query string used as a cache key.

    Args:
        query: The user query string.

    Returns:
        MD5 hex digest of the lowercased, stripped query.
    """
    return hashlib.md5(query.strip().lower().encode()).hexdigest()


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Load the HuggingFace sentence-transformer model for query embedding.

    Returns:
        HuggingFaceEmbeddings instance.
    """
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def load_vector_store(embeddings: HuggingFaceEmbeddings) -> Optional[Chroma]:
    """
    Load the persisted ChromaDB vector store.

    Args:
        embeddings: Embedding function used during ingestion.

    Returns:
        Chroma vector store instance, or None if not found.
    """
    if not Path(CHROMA_PERSIST_DIR).exists():
        return None

    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
    )


def get_llm() -> ChatGroq:
    """
    Initialize the Groq LLaMA3 language model.

    Returns:
        ChatGroq instance configured for the LLaMA3 model.

    Raises:
        ValueError: If the GROQ_API_KEY environment variable is not set.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not found. Set it in your .env file.\n"
            "Get a free key at https://console.groq.com/"
        )
    return ChatGroq(
        model=GROQ_MODEL,
        temperature=0.1,
        max_tokens=1024,
        groq_api_key=api_key,
    )


def build_prompt() -> PromptTemplate:
    """
    Build the LangChain prompt template for RAG-grounded answer generation.

    Returns:
        PromptTemplate that injects retrieved context and the user's question.
    """
    template = """You are SupportAI, a warm and professional customer support assistant.

KNOWLEDGE BASE CONTEXT:
{context}

CUSTOMER MESSAGE:
{question}

INSTRUCTIONS:
- Answer using the context above as your primary source. Do not invent facts.
- Be concise, warm, and professional in tone.
- If the context contains a clear answer, provide it directly and helpfully.
- If the context does not cover the question, say: "I don't have specific information on that in our knowledge base. Please contact our support team at support@company.com and they will be happy to help."
- Never say "based on the context" or "according to the documents" — respond naturally like a real support agent would.
- For simple follow-up questions or clarifications, respond helpfully even with limited context.

ANSWER:"""

    return PromptTemplate(
        input_variables=["context", "question"],
        template=template,
    )


def classify_triage(
    query: str,
    top_similarity_score: float,
    retrieved_docs: list[Document],
) -> tuple[str, str]:
    """
    Classify a support query as L1 (simple FAQ) or L2 (complex / escalate).

    Classification logic:
    - L2 if query contains complexity keywords (severity, legal, fraud, etc.)
    - L2 if query word count exceeds the L2 threshold (long, detailed issue)
    - L2 if similarity score is below threshold (knowledge base lacks coverage)
    - L1 otherwise (well-covered, straightforward FAQ)

    Args:
        query: The raw customer query string.
        top_similarity_score: Highest similarity score from vector search (0-1).
        retrieved_docs: Documents retrieved from the vector store.

    Returns:
        Tuple of (triage_level, triage_reason) where triage_level is "L1" or "L2".
    """
    query_lower = query.lower()
    word_count = len(query.split())

    # Check for high-complexity keywords
    matched_keywords = [kw for kw in L2_COMPLEXITY_KEYWORDS if kw in query_lower]
    if matched_keywords:
        return "L2", f"Query contains escalation keywords: {', '.join(matched_keywords[:3])}"

    # Check query length (very detailed queries hint at complex issues)
    if word_count > L2_WORD_COUNT_THRESHOLD:
        return "L2", f"Complex query ({word_count} words) — may require human review"

    # Check similarity confidence
    if top_similarity_score < L1_CONFIDENCE_THRESHOLD or not retrieved_docs:
        return "L2", f"Low knowledge base coverage (confidence: {top_similarity_score:.2f}) — human review recommended"

    return "L1", f"Well-covered FAQ (confidence: {top_similarity_score:.2f}) — answered from knowledge base"


def format_context(docs: list[Document]) -> str:
    """
    Format retrieved documents into a single context string for the prompt.

    Args:
        docs: List of retrieved Document objects.

    Returns:
        Concatenated context string with source attribution per chunk.
    """
    if not docs:
        return "No relevant context found in the knowledge base."

    parts = []
    for i, doc in enumerate(docs, 1):
        source = doc.metadata.get("source_file", "unknown")
        parts.append(f"[Source {i}: {source}]\n{doc.page_content.strip()}")

    return "\n\n---\n\n".join(parts)


def get_unique_sources(docs: list[Document]) -> list[str]:
    """
    Extract deduplicated source file names from retrieved documents.

    Args:
        docs: List of retrieved Document objects.

    Returns:
        Sorted list of unique source filenames.
    """
    sources = set()
    for doc in docs:
        source = doc.metadata.get("source_file", "unknown")
        sources.add(source)
    return sorted(sources)



# ── Conversational message handler ──────────────────────────────────────────
_GREETINGS = {
    "hi", "hello", "hey", "hiya", "howdy", "greetings", "good morning",
    "good afternoon", "good evening", "good day", "morning", "afternoon",
    "evening", "yo", "sup", "whats up", "helo", "hii", "hiii", "hai",
}

_THANKS = {
    "thanks", "thank you", "thank u", "thankyou", "thx", "ty",
    "cheers", "appreciate it", "appreciated", "many thanks",
}

_FAREWELLS = {
    "bye", "goodbye", "see you", "see ya", "take care", "later",
    "cya", "farewell", "have a good day", "have a nice day",
}

_HOW_ARE_YOU = {
    "how are you", "how r u", "how are u", "how do you do",
    "hows it going", "how are things", "you ok", "are you ok",
}

_WHAT_CAN_YOU_DO = {
    "what can you do", "what do you do", "help", "what can i ask",
    "how can you help", "what are you", "who are you", "what is this",
}


def _handle_conversational(query: str) -> str:
    """
    Detect casual messages and return a friendly direct reply.
    Returns empty string if the message needs knowledge base search.
    """
    q = query.lower().strip().rstrip("!?,.")

    if q in _GREETINGS:
        return (
            "Hello! Welcome to SupportAI. I am here to help you with any questions "
            "about billing, accounts, shipping, refunds, or technical issues. "
            "What can I help you with today?"
        )
    if q in _THANKS:
        return (
            "You are very welcome! If you have any other questions, "
            "feel free to ask. I am always here to help."
        )
    if q in _FAREWELLS:
        return (
            "Goodbye! Have a wonderful day. "
            "Do not hesitate to reach out if you need anything else."
        )
    if q in _HOW_ARE_YOU:
        return (
            "I am doing great, thank you for asking! "
            "Ready to help you with any support questions. "
            "What would you like to know?"
        )
    if q in _WHAT_CAN_YOU_DO:
        return (
            "I am SupportAI, an intelligent customer support assistant. "
            "I can help you with billing and payment questions, account and login issues, "
            "password resets, shipping and delivery queries, refunds and returns, "
            "technical troubleshooting, and SLA or service policy questions.\n\n"
            "Just type your question and I will find the answer from our knowledge base."
        )
    return ""

class RAGChain:
    """
    End-to-end RAG pipeline for customer support query answering.

    Handles embedding, retrieval, triage classification, LLM generation,
    and response caching in a single cohesive interface.
    """

    def __init__(self):
        """Initialize the RAG chain: load embeddings, vector store, LLM, and cache."""
        self.embeddings = get_embeddings()
        self.vector_store = load_vector_store(self.embeddings)
        self.llm = get_llm()
        self.prompt = build_prompt()
        self.cache = _load_cache()
        self._doc_count = self._count_docs()

    def _count_docs(self) -> int:
        """
        Count the number of chunks in the vector store.

        Returns:
            Integer count of stored document chunks, or 0 if store unavailable.
        """
        if self.vector_store is None:
            return 0
        try:
            return self.vector_store._collection.count()
        except Exception:
            return 0

    @property
    def is_ready(self) -> bool:
        """Return True if the vector store is loaded and has documents."""
        return self.vector_store is not None and self._doc_count > 0

    @property
    def doc_count(self) -> int:
        """Return the number of chunks in the knowledge base."""
        return self._doc_count

    def ask(self, query: str, use_cache: bool = True) -> RAGResponse:
        """
        Answer a customer support query using the RAG pipeline.

        Workflow:
            1. Check response cache for identical past queries.
            2. Embed the query and retrieve top-K similar chunks from ChromaDB.
            3. Classify triage level (L1/L2) based on similarity and complexity.
            4. Build prompt with retrieved context and generate answer via Groq LLM.
            5. Cache and return the structured RAGResponse.

        Args:
            query: The customer support question string.
            use_cache: Whether to check/update the response cache (default True).

        Returns:
            RAGResponse dataclass with answer, sources, triage info, and metadata.

        Raises:
            RuntimeError: If the knowledge base has not been ingested yet.
        """
        if not self.is_ready:
            raise RuntimeError(
                "Knowledge base not found. Run `python ingest.py` first to build the index."
            )

        query = query.strip()
        if not query:
            return RAGResponse(
                answer="Please enter a valid question.",
                sources=[],
                triage_level="L1",
                triage_reason="Empty query",
                confidence_score=0.0,
                query=query,
            )

        # ── Conversational / greeting detection ───────────────────────────────
        conversational_reply = _handle_conversational(query)
        if conversational_reply:
            return RAGResponse(
                answer=conversational_reply,
                sources=[],
                triage_level="L1",
                triage_reason="Conversational message — no knowledge base search needed",
                confidence_score=1.0,
                query=query,
                from_cache=False,
            )

        # ── Cache check ───────────────────────────────────────────────────────
        cache_key = _query_hash(query)
        if use_cache and cache_key in self.cache:
            cached = self.cache[cache_key]
            cached_chunks = [
                RetrievedChunk(**c) for c in cached.get("retrieved_chunks", [])
            ]
            return RAGResponse(
                answer=cached["answer"],
                sources=cached["sources"],
                triage_level=cached["triage_level"],
                triage_reason=cached["triage_reason"],
                confidence_score=cached["confidence_score"],
                query=query,
                from_cache=True,
                retrieved_chunks=cached_chunks,
            )

        # ── Retrieval ─────────────────────────────────────────────────────────
        results_with_scores = self.vector_store.similarity_search_with_relevance_scores(
            query, k=TOP_K_RESULTS
        )

        retrieved_docs = [doc for doc, _ in results_with_scores]
        scores = [score for _, score in results_with_scores]
        top_score = max(scores) if scores else 0.0

        # ── Triage Classification ─────────────────────────────────────────────
        triage_level, triage_reason = classify_triage(query, top_score, retrieved_docs)

        # ── Answer Generation ─────────────────────────────────────────────────
        context = format_context(retrieved_docs)
        prompt_text = self.prompt.format(context=context, question=query)

        try:
            response = self.llm.invoke(prompt_text)
            answer = response.content.strip()
        except Exception as e:
            answer = (
                f"I'm sorry, I encountered an error generating a response. "
                f"Please try again or contact support directly. (Error: {e})"
            )

        sources = get_unique_sources(retrieved_docs)

        retrieved_chunks = [
            RetrievedChunk(
                source=doc.metadata.get("source_file", "unknown"),
                text=doc.page_content.strip()[:600],
                score=round(scores[i], 4) if i < len(scores) else 0.0,
            )
            for i, doc in enumerate(retrieved_docs[:5])
        ]

        # ── Cache save ────────────────────────────────────────────────────────
        if use_cache:
            self.cache[cache_key] = {
                "answer": answer,
                "sources": sources,
                "triage_level": triage_level,
                "triage_reason": triage_reason,
                "confidence_score": round(top_score, 4),
                "retrieved_chunks": [asdict(c) for c in retrieved_chunks],
            }
            _save_cache(self.cache)

        return RAGResponse(
            answer=answer,
            sources=sources,
            triage_level=triage_level,
            triage_reason=triage_reason,
            confidence_score=round(top_score, 4),
            query=query,
            from_cache=False,
            retrieved_chunks=retrieved_chunks,
        )


# ── Module-level singleton (lazy init) ───────────────────────────────────────
_rag_instance: Optional[RAGChain] = None


def get_rag_chain() -> RAGChain:
    """
    Return the module-level singleton RAGChain instance (created on first call).

    Returns:
        Shared RAGChain instance for use across app.py and api.py.
    """
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGChain()
    return _rag_instance


if __name__ == "__main__":
    # Quick smoke-test from the command line
    print("Initializing RAG chain ...")
    rag = get_rag_chain()
    print(f"Ready: {rag.is_ready} | Chunks: {rag.doc_count}")

    test_queries = [
        "How do I reset my password?",
        "My package hasn't arrived after 10 days and tracking hasn't updated. I need an urgent resolution.",
        "What payment methods do you accept?",
    ]

    for q in test_queries:
        print(f"\n{'─'*60}\nQ: {q}")
        result = rag.ask(q)
        print(f"Triage: [{result.triage_level}] {result.triage_reason}")
        print(f"Sources: {result.sources}")
        print(f"Answer:\n{result.answer}")
