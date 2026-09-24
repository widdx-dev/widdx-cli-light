"""UIL — Unified Intelligence Layer for WIDDX.

Phase 1.1: Data contracts + Task Analyzer.
Phase 1.2: Decision Router + UIL Brain.
"""

from .contract import (
    TaskType, ExecutionMode, Domain,
    DecisionStep, ClassificationResult, ExecutionPlan,
    RoutingDecision, ExecutionResult, ExecutionContext,
    TaskStep, Plan,
)

from .analyzer import TaskAnalyzer
from .router import DecisionRouter
from .planner import TaskPlanner
from .brain import UnifiedIntelligenceLayer
from .knowledge import KnowledgeBase

__all__ = [
    # Enums
    "TaskType", "ExecutionMode", "Domain",
    # Decision trace
    "DecisionStep",
    # Data contracts
    "ClassificationResult", "ExecutionPlan",
    "RoutingDecision", "ExecutionResult", "ExecutionContext",
    "TaskStep", "Plan",
    # Telemetry (Phase 2.2)
    # StepResult, ExecutionMetrics — defined in contract but may not be re-exported
    # Analyzer
    "TaskAnalyzer",
    # Router
    "DecisionRouter",
    # Planner
    "TaskPlanner",
    # Brain
    "UnifiedIntelligenceLayer",
    # Knowledge
    "KnowledgeBase",
]
