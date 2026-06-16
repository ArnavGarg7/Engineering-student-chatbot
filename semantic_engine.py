"""
semantic_engine.py
==================
Vector embedding-based semantic similarity search — third layer of the query
resolution pipeline.

Resolution order in route_question():
  1. Gemini AI intent extraction   (ai_service.py)
  2. Rule-based keyword matching   (query_engine.py)
  3. Semantic similarity search    ← this module        (NEW)
  4. "I could not parse that"      ← last resort

How it works
------------
At first use, SemanticEngine embeds ~5 canonical example questions for every
supported intent using Gemini's text-embedding-004 model (65 vectors total).
These are cached in memory for the lifetime of the server process.

When a question reaches layer 3, it is embedded with the same model, and
cosine similarity is computed against every cached example vector.  The highest-
scoring intent is returned if it clears the confidence threshold (default 0.75).

Graceful degradation
--------------------
- No GEMINI_API_KEY → engine is disabled, find_intent() always returns None.
- google-genai not installed → same.
- Any API error → logged as a warning, find_intent() returns None.
In all cases the caller falls through to the "could not parse" response.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("semantic_engine")

# ---------------------------------------------------------------------------
# Similarity threshold
# ---------------------------------------------------------------------------
# Raise this (e.g. 0.80) if wrong intents are being matched.
# Lower this (e.g. 0.70) if too many valid questions still fail.
SIMILARITY_THRESHOLD = 0.75

# ---------------------------------------------------------------------------
# INTENT_EXAMPLES
# ---------------
# 5 varied phrasings per intent.  Variety is important: the embedding model
# generalises well, but covering different vocabulary anchors each cluster.
# ---------------------------------------------------------------------------
INTENT_EXAMPLES: dict[str, list[str]] = {
    "list_departments": [
        "List all engineering departments",
        "What branches are offered at this college?",
        "Show me all the streams available",
        "Which engineering disciplines exist here?",
        "What courses does this college have?",
    ],
    "list_years": [
        "List all academic years available",
        "Which years of study are there?",
        "Show all years in the college",
        "What year groups are present?",
        "How many years does the program have?",
    ],
    "students_by_department": [
        "List all students in Computer Science",
        "Who studies in CSE?",
        "Show all students enrolled in Mechanical Engineering",
        "Give me a list of Biotechnology students",
        "Students in the IT department",
    ],
    "students_by_department_year": [
        "Show all 3rd year Mechanical Engineering students",
        "List second year CSE students",
        "Who are the first year Civil Engineering students?",
        "Show 4th year ECE students",
        "Give me all third year IT students",
    ],
    "students_with_roll_numbers": [
        "Show the list of students with roll numbers in Electrical Engineering",
        "List roll numbers in CSE",
        "Give me roll numbers for all Mechanical Engineering students",
        "Student roll numbers in the IT department",
        "Show roll no list for Aerospace Engineering",
    ],
    "academic_history": [
        "Show full academic history of roll number 2025-CSE-001",
        "Give me the complete transcript of 2025-ME-005",
        "What is the academic record of roll 2025-ECE-010?",
        "All marks and results for student 2025-BT-003",
        "Tell me about the academic performance of 2025-IT-012",
    ],
    "subject_wise_marks": [
        "Show subject-wise marks of roll number 2025-CSE-001",
        "What did 2025-ME-005 score in each subject?",
        "Marks per subject for student 2025-ECE-002",
        "Give me the subject breakdown for roll 2025-BT-007",
        "Subject scores for 2025-IT-015",
    ],
    "semester_performance": [
        "Show semester-wise performance of roll number 2025-CSE-001",
        "Give me the semester breakdown for 2025-ME-003",
        "How did 2025-ECE-008 perform each semester?",
        "Semester-by-semester results for roll 2025-CE-011",
        "Marks breakdown for each semester of 2025-IT-004",
    ],
    "pass_fail_counts": [
        "How many students passed in Computer Science, 2nd year?",
        "How many failed in Civil Engineering 3rd year?",
        "Pass and fail count for ECE second year",
        "How many students cleared all subjects in ME year 1?",
        "Failure count in IT department 4th year",
    ],
    "department_toppers": [
        "Show toppers in Information Technology",
        "Who are the top performers in ECE?",
        "Best students in Biotechnology",
        "Rank students in Mechanical Engineering by marks",
        "Which students scored the highest in Computer Science?",
    ],
    "failed_more_than_two": [
        "Show students who failed in more than 2 subjects",
        "Which students have backlogs?",
        "List students struggling academically",
        "Who failed more than two papers?",
        "Students with multiple subject failures",
    ],
    "average_marks_by_department": [
        "Show average marks by department",
        "Which department has the best academic performance?",
        "Compare departments by average marks",
        "Department-wise average score",
        "Rank all departments by performance",
    ],
    "average_marks_by_subject": [
        "Show average marks by subject",
        "Which subject has the highest average score?",
        "Subject-wise average marks across the college",
        "Average performance per subject",
        "Compare subjects by their average marks",
    ],
}


class SemanticEngine:
    """
    Embedding-based intent classifier used as the third fallback layer.

    Usage
    -----
    engine = SemanticEngine()
    intent_name = engine.find_intent("Give me the semester breakdown of 2025-CSE-001")
    # Returns "semester_performance" or None
    """

    def __init__(self) -> None:
        self._cache: dict[str, list[float]] | None = None  # intent → centroid vector
        self._ready: bool = False

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def find_intent(self, question: str) -> str | None:
        """
        Embed *question* and return the closest matching intent name, or None.

        Returns None if:
        - No API key is configured.
        - google-genai is not installed.
        - The best match scores below SIMILARITY_THRESHOLD.
        - Any embedding API call fails.
        """
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return None

        try:
            from google import genai  # type: ignore[import]
        except ImportError:
            return None

        # Ensure example embeddings are loaded
        if not self._ready:
            self._load_examples(api_key)
            if not self._ready:
                return None

        # Embed the incoming question
        query_vec = self._embed(api_key, question)
        if query_vec is None:
            return None

        # Find the best matching intent
        best_intent, best_score = self._best_match(query_vec)

        if best_score >= SIMILARITY_THRESHOLD:
            logger.info(
                "Semantic match: intent=%r score=%.3f question=%r",
                best_intent, best_score, question,
            )
            return best_intent

        logger.info(
            "Semantic search: best score %.3f below threshold %.2f for question %r",
            best_score, SIMILARITY_THRESHOLD, question,
        )
        return None

    def is_ready(self) -> bool:
        """Return True if example embeddings have been loaded."""
        return self._ready

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _load_examples(self, api_key: str) -> None:
        """
        Embed all example questions and store the centroid vector per intent.
        Called once, results cached for the lifetime of the process.
        """
        logger.info("Semantic engine: loading %d intent clusters…", len(INTENT_EXAMPLES))
        centroids: dict[str, list[float]] = {}

        for intent, examples in INTENT_EXAMPLES.items():
            vectors = []
            for example in examples:
                vec = self._embed(api_key, example)
                if vec is not None:
                    vectors.append(vec)

            if vectors:
                centroids[intent] = _mean_vector(vectors)
            else:
                logger.warning("Semantic engine: no embeddings for intent %r — skipping.", intent)

        if centroids:
            self._cache = centroids
            self._ready = True
            logger.info("Semantic engine: ready with %d intent clusters.", len(centroids))
        else:
            logger.warning("Semantic engine: failed to load any embeddings — disabled.")

    def _embed(self, api_key: str, text: str) -> list[float] | None:
        """Call Gemini text-embedding-004 and return the embedding vector."""
        try:
            from google import genai  # type: ignore[import]
            client = genai.Client(api_key=api_key)
            response = client.models.embed_content(
                model="models/embedding-001",
                contents=text,
            )
            return list(response.embeddings[0].values)
        except Exception as exc:
            logger.warning("Semantic engine: embedding failed for %r: %s", text[:60], exc)
            return None

    def _best_match(self, query_vec: list[float]) -> tuple[str, float]:
        """Return (intent_name, cosine_similarity) for the closest centroid."""
        assert self._cache is not None
        best_intent = ""
        best_score = -1.0
        for intent, centroid in self._cache.items():
            score = _cosine_similarity(query_vec, centroid)
            if score > best_score:
                best_score = score
                best_intent = intent
        return best_intent, best_score


# ---------------------------------------------------------------------------
# Math helpers (pure Python + optional numpy)
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Uses numpy if available."""
    try:
        import numpy as np
        va = np.array(a, dtype=np.float64)
        vb = np.array(b, dtype=np.float64)
        norm_a = np.linalg.norm(va)
        norm_b = np.linalg.norm(vb)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(va, vb) / (norm_a * norm_b))
    except ImportError:
        # Pure Python fallback (slower but dependency-free)
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


def _mean_vector(vectors: list[list[float]]) -> list[float]:
    """Element-wise mean of a list of equal-length vectors."""
    n = len(vectors)
    length = len(vectors[0])
    return [sum(v[i] for v in vectors) / n for i in range(length)]


# ---------------------------------------------------------------------------
# Module-level singleton — imported by query_engine.py
# ---------------------------------------------------------------------------
engine = SemanticEngine()
