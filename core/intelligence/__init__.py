"""WIDDX Intelligence Engine — local, independent decision-making.

This engine makes decisions WITHOUT calling an external LLM.
It uses local embeddings, keyword matching, learned decision trees,
and a pattern knowledge base to classify, route, and plan tasks.

Components:
    classifier.py       — Embedding-based task classification
    decision_engine.py   — Learned decision tree for routing
    patterns.py          — 25+ software project patterns
    planner.py           — Pattern-aware task decomposition
    learner.py           — Extracts new patterns from history
    embeddings.py        — TF-IDF local embeddings
"""

from .classifier import (
    LocalClassifier,
    ClassificationResult,
    classify_input,
    get_classifier,
)
from .decision_engine import (
    DecisionEngine,
    DecisionStats,
    DEFAULT_MODE_MAP,
    get_decision_engine,
)
from .patterns import (
    SoftwarePattern,
    PatternStep,
    PATTERNS,
    find_patterns,
    get_pattern,
    list_patterns_by_category,
    all_patterns,
)
from .planner import (
    PatternAwarePlanner,
    Plan,
    PlanStep,
    create_plan,
    get_planner,
)
from .learner import (
    PatternLearner,
    get_learner,
)
from .embeddings import (
    TFIDFEmbedder,
    SentenceEmbedder,
    EmbeddingStore,
    embed_text,
    similarity,
    get_embedder,
    get_sentence_embedder,
)

__all__ = [
    # Classifier
    "LocalClassifier",
    "ClassificationResult",
    "classify_input",
    "get_classifier",
    # Decision Engine
    "DecisionEngine",
    "DecisionStats",
    "DEFAULT_MODE_MAP",
    "get_decision_engine",
    # Patterns
    "SoftwarePattern",
    "PatternStep",
    "PATTERNS",
    "find_patterns",
    "get_pattern",
    "list_patterns_by_category",
    "all_patterns",
    # Planner
    "PatternAwarePlanner",
    "Plan",
    "PlanStep",
    "create_plan",
    "get_planner",
    # Learner
    "PatternLearner",
    "get_learner",
    # Embeddings
    "TFIDFEmbedder",
    "SentenceEmbedder",
    "EmbeddingStore",
    "embed_text",
    "similarity",
    "get_embedder",
    "get_sentence_embedder",
]
