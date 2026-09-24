"""Semantic stability + self-healing — cognitive consistency measurement & recovery.

Tracks whether the system "remains the same system over time":
  - Goal drift detection + anchoring
  - Decision trajectory divergence
  - Memory contamination tracking
  - Cognitive state snapshots (stable identity capture)
  - Semantic rollback (context pruning, goal re-anchoring, tool restriction)
  - Self-healing orchestration (detect → compare → restore → verify)
"""

from .goal_drift import GoalDriftDetector, DriftSnapshot, GoalAnchor, get_goal_drift_detector
from .trajectory import TrajectoryDivergence, TrajectoryPoint, DivergenceReport, get_trajectory_divergence
from .memory_contamination import (
    MemoryContaminationTracker, ContaminationReport, get_memory_contamination_tracker,
)
from .monitor import (
    SemanticStabilityMonitor, SemanticStabilityReport, get_semantic_monitor,
)
from .state_snapshot import (
    StateSnapshotManager, CognitiveSnapshot, get_snapshot_manager,
)
from .rollback import SemanticRollback, get_semantic_rollback
from .healer import SelfHealingMonitor, get_self_healing_monitor

from .invariance import CognitiveInvariance, Invariant, HealingContract, RecoveryValidation, get_cognitive_invariance

__all__ = [
    "GoalDriftDetector", "DriftSnapshot", "GoalAnchor", "get_goal_drift_detector",
    "TrajectoryDivergence", "TrajectoryPoint", "DivergenceReport", "get_trajectory_divergence",
    "MemoryContaminationTracker", "ContaminationReport", "get_memory_contamination_tracker",
    "SemanticStabilityMonitor", "SemanticStabilityReport", "get_semantic_monitor",
    "StateSnapshotManager", "CognitiveSnapshot", "get_snapshot_manager",
    "SemanticRollback", "get_semantic_rollback",
    "SelfHealingMonitor", "get_self_healing_monitor",
    "CognitiveInvariance", "Invariant", "HealingContract", "RecoveryValidation",
    "get_cognitive_invariance",
]
