"""
evaluation/metrics.py — RAG Evaluation Metrics Engine

Computes accuracy, precision, recall, F1 score, and retrieval quality
metrics against a labeled test set. Results are stored in SQLite and
surfaced in the Streamlit admin dashboard.

Evaluation approach:
  - Ground truth: labeled QA pairs in evaluation/test_set.json
  - Retrieval quality: measured by chunk relevance scores from ChromaDB
  - Answer quality: keyword-overlap F1 (lexical) + confidence scoring
  - Triage accuracy: predicted L1/L2 vs. labeled expected level
"""

import json
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

# ── Constants ─────────────────────────────────────────────────────────────────
EVAL_DB_PATH = "./evaluation/eval_results.db"
TEST_SET_PATH = "./evaluation/test_set.json"


@dataclass
class EvalResult:
    """Result for a single evaluated QA pair."""
    question: str
    expected_answer: str
    predicted_answer: str
    expected_triage: str
    predicted_triage: str
    retrieval_score: float       # Top similarity score from ChromaDB
    answer_f1: float             # Token-level F1 between expected and predicted
    answer_precision: float
    answer_recall: float
    triage_correct: bool
    sources_retrieved: list[str]
    latency_ms: float
    timestamp: str


@dataclass
class EvalSummary:
    """Aggregate metrics across all evaluated QA pairs."""
    total_questions: int
    avg_retrieval_score: float
    avg_answer_f1: float
    avg_answer_precision: float
    avg_answer_recall: float
    triage_accuracy: float       # % of L1/L2 labels correctly predicted
    avg_latency_ms: float
    l1_precision: float          # Precision of L1 predictions
    l1_recall: float             # Recall of L1 predictions
    l2_precision: float
    l2_recall: float
    coverage_rate: float         # % of questions where KB found relevant docs
    run_timestamp: str
    run_id: str


def _init_eval_db() -> None:
    """Create evaluation results database tables if not present."""
    Path(EVAL_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(EVAL_DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS eval_runs (
            run_id      TEXT PRIMARY KEY,
            timestamp   TEXT NOT NULL,
            summary     TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS eval_details (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id      TEXT NOT NULL,
            question    TEXT NOT NULL,
            result_json TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES eval_runs(run_id)
        );
    """)
    conn.commit()
    conn.close()


def _tokenize(text: str) -> set[str]:
    """
    Tokenize text into a set of lowercase, non-stopword words for F1 scoring.

    Args:
        text: Raw text string.

    Returns:
        Set of lowercase word tokens with stopwords removed.
    """
    stopwords = {
        "a","an","the","is","it","in","of","to","and","or","for",
        "with","on","at","by","this","that","are","was","be","as",
        "we","you","your","our","can","will","have","has","not","do",
        "if","from","but","its","they","their","there","than","when",
    }
    tokens = re.findall(r'\b[a-z]+\b', text.lower())
    return set(t for t in tokens if t not in stopwords and len(t) > 2)


def compute_token_f1(
    predicted: str, expected: str
) -> tuple[float, float, float]:
    """
    Compute token-level precision, recall, and F1 score between two text strings.

    This is the same metric used in SQuAD QA benchmarks.

    Args:
        predicted: Model's generated answer.
        expected: Ground-truth reference answer.

    Returns:
        Tuple of (f1, precision, recall) all in range [0.0, 1.0].
    """
    pred_tokens = _tokenize(predicted)
    exp_tokens = _tokenize(expected)

    if not pred_tokens and not exp_tokens:
        return 1.0, 1.0, 1.0
    if not pred_tokens or not exp_tokens:
        return 0.0, 0.0, 0.0

    common = pred_tokens & exp_tokens
    if not common:
        return 0.0, 0.0, 0.0

    precision = len(common) / len(pred_tokens)
    recall = len(common) / len(exp_tokens)
    f1 = 2 * precision * recall / (precision + recall)
    return round(f1, 4), round(precision, 4), round(recall, 4)


def compute_triage_metrics(
    results: list[EvalResult],
) -> dict:
    """
    Compute per-class precision and recall for L1/L2 triage classification.

    Args:
        results: List of EvalResult objects from a completed evaluation run.

    Returns:
        Dict with l1_precision, l1_recall, l2_precision, l2_recall,
        overall_accuracy, confusion_matrix.
    """
    tp_l1 = fp_l1 = fn_l1 = 0
    tp_l2 = fp_l2 = fn_l2 = 0

    for r in results:
        pred = r.predicted_triage
        true = r.expected_triage

        if pred == "L1" and true == "L1":
            tp_l1 += 1
        elif pred == "L1" and true == "L2":
            fp_l1 += 1
            fn_l2 += 1
        elif pred == "L2" and true == "L2":
            tp_l2 += 1
        elif pred == "L2" and true == "L1":
            fp_l2 += 1
            fn_l1 += 1

    def safe_div(a, b):
        return round(a / b, 4) if b else 0.0

    return {
        "l1_precision": safe_div(tp_l1, tp_l1 + fp_l1),
        "l1_recall":    safe_div(tp_l1, tp_l1 + fn_l1),
        "l2_precision": safe_div(tp_l2, tp_l2 + fp_l2),
        "l2_recall":    safe_div(tp_l2, tp_l2 + fn_l2),
        "overall_accuracy": safe_div(tp_l1 + tp_l2, len(results)),
        "confusion_matrix": {
            "TP_L1": tp_l1, "FP_L1": fp_l1, "FN_L1": fn_l1,
            "TP_L2": tp_l2, "FP_L2": fp_l2, "FN_L2": fn_l2,
        },
    }


def run_evaluation(rag_chain, verbose: bool = True) -> EvalSummary:
    """
    Run the full evaluation suite against the labeled test set.

    Loads test questions from evaluation/test_set.json, queries the RAG
    pipeline for each, computes all metrics, and saves results to the
    evaluation database.

    Args:
        rag_chain: Initialized RAGChain instance to evaluate.
        verbose: Print per-question results to stdout if True.

    Returns:
        EvalSummary dataclass with aggregate metrics for the run.

    Raises:
        FileNotFoundError: If test_set.json does not exist.
    """
    _init_eval_db()

    test_path = Path(TEST_SET_PATH)
    if not test_path.exists():
        raise FileNotFoundError(
            f"Test set not found at {TEST_SET_PATH}. "
            "Run evaluation/generate_test_set.py to create it."
        )

    with open(test_path, "r") as f:
        test_cases = json.load(f)

    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    results: list[EvalResult] = []

    print(f"\n{'='*60}")
    print(f"  Evaluation Run: {run_id}")
    print(f"  Test cases: {len(test_cases)}")
    print(f"{'='*60}\n")

    for i, case in enumerate(test_cases, 1):
        question = case["question"]
        expected_answer = case.get("expected_answer", "")
        expected_triage = case.get("expected_triage", "L1")

        if verbose:
            print(f"[{i:02d}/{len(test_cases)}] {question[:70]}...")

        # Run through RAG — disable cache for fair evaluation
        t0 = time.perf_counter()
        try:
            response = rag_chain.ask(question, use_cache=False)
            latency_ms = (time.perf_counter() - t0) * 1000
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        # Compute metrics
        f1, precision, recall = compute_token_f1(
            response.answer, expected_answer
        )

        result = EvalResult(
            question=question,
            expected_answer=expected_answer,
            predicted_answer=response.answer,
            expected_triage=expected_triage,
            predicted_triage=response.triage_level,
            retrieval_score=response.confidence_score,
            answer_f1=f1,
            answer_precision=precision,
            answer_recall=recall,
            triage_correct=(response.triage_level == expected_triage),
            sources_retrieved=response.sources,
            latency_ms=round(latency_ms, 1),
            timestamp=datetime.utcnow().isoformat(),
        )
        results.append(result)

        if verbose:
            status = "✅" if result.triage_correct else "❌"
            print(f"  {status} Triage: {result.predicted_triage} (expected {expected_triage}) | "
                  f"F1: {f1:.3f} | Score: {response.confidence_score:.3f} | "
                  f"Latency: {latency_ms:.0f}ms")

    if not results:
        raise ValueError("No results computed — check test set format.")

    # Aggregate metrics
    triage_metrics = compute_triage_metrics(results)
    n = len(results)

    summary = EvalSummary(
        total_questions=n,
        avg_retrieval_score=round(sum(r.retrieval_score for r in results) / n, 4),
        avg_answer_f1=round(sum(r.answer_f1 for r in results) / n, 4),
        avg_answer_precision=round(sum(r.answer_precision for r in results) / n, 4),
        avg_answer_recall=round(sum(r.answer_recall for r in results) / n, 4),
        triage_accuracy=triage_metrics["overall_accuracy"],
        avg_latency_ms=round(sum(r.latency_ms for r in results) / n, 1),
        l1_precision=triage_metrics["l1_precision"],
        l1_recall=triage_metrics["l1_recall"],
        l2_precision=triage_metrics["l2_precision"],
        l2_recall=triage_metrics["l2_recall"],
        coverage_rate=round(
            sum(1 for r in results if r.retrieval_score > 0.3) / n, 4
        ),
        run_timestamp=datetime.utcnow().isoformat(),
        run_id=run_id,
    )

    # Persist to DB
    conn = sqlite3.connect(EVAL_DB_PATH)
    conn.execute(
        "INSERT INTO eval_runs (run_id, timestamp, summary) VALUES (?, ?, ?)",
        (run_id, summary.run_timestamp, json.dumps(asdict(summary))),
    )
    for r in results:
        conn.execute(
            "INSERT INTO eval_details (run_id, question, result_json) VALUES (?, ?, ?)",
            (run_id, r.question, json.dumps(asdict(r))),
        )
    conn.commit()
    conn.close()

    _print_summary(summary)
    return summary


def get_eval_history() -> list[dict]:
    """
    Retrieve all past evaluation run summaries from the database.

    Returns:
        List of summary dicts ordered by most recent first.
    """
    _init_eval_db()
    conn = sqlite3.connect(EVAL_DB_PATH)
    rows = conn.execute(
        "SELECT run_id, timestamp, summary FROM eval_runs ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [{"run_id": r[0], "timestamp": r[1], **json.loads(r[2])} for r in rows]


def get_eval_details(run_id: str) -> list[dict]:
    """
    Retrieve per-question results for a specific evaluation run.

    Args:
        run_id: The run identifier string.

    Returns:
        List of per-question result dicts.
    """
    _init_eval_db()
    conn = sqlite3.connect(EVAL_DB_PATH)
    rows = conn.execute(
        "SELECT question, result_json FROM eval_details WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    conn.close()
    return [json.loads(r[1]) for r in rows]


def _print_summary(s: EvalSummary) -> None:
    """Print a formatted summary table to stdout."""
    print(f"\n{'='*60}")
    print(f"  EVALUATION SUMMARY — {s.run_id}")
    print(f"{'='*60}")
    print(f"  Questions evaluated  : {s.total_questions}")
    print(f"  Avg Answer F1        : {s.avg_answer_f1:.4f}  ({s.avg_answer_f1*100:.1f}%)")
    print(f"  Avg Precision        : {s.avg_answer_precision:.4f}  ({s.avg_answer_precision*100:.1f}%)")
    print(f"  Avg Recall           : {s.avg_answer_recall:.4f}  ({s.avg_answer_recall*100:.1f}%)")
    print(f"  Triage Accuracy      : {s.triage_accuracy:.4f}  ({s.triage_accuracy*100:.1f}%)")
    print(f"  L1 Precision/Recall  : {s.l1_precision:.3f} / {s.l1_recall:.3f}")
    print(f"  L2 Precision/Recall  : {s.l2_precision:.3f} / {s.l2_recall:.3f}")
    print(f"  Avg Retrieval Score  : {s.avg_retrieval_score:.4f}")
    print(f"  KB Coverage Rate     : {s.coverage_rate:.4f}  ({s.coverage_rate*100:.1f}%)")
    print(f"  Avg Latency          : {s.avg_latency_ms:.0f} ms")
    print(f"{'='*60}\n")
