"""Runtime — 14-layer Cognitive Runtime OS.

Layers 1-3: Execution Control Plane (ECP)
  control/types.py              — data structures
  control/evaluation.py         — signal-to-action engine
  control/policy.py             — stabilization guards
  control/execution_plane.py    — thin orchestrator (Layer 1)

Layers 4-5: Sensors + Benchmarks
  benchmarks/tracer.py          — decision tracing (Layer 3)
  benchmarks/scorer.py          — performance grading (Layer 3)

Layers 5-7: Semantic Stability + Self-Healing
  semantic/monitor.py           — cognitive stability measurement (Layer 5)
  semantic/state_snapshot.py    — identity snapshots (Layer 6)
  semantic/rollback.py          — semantic restoration (Layer 6)
  semantic/healer.py            — self-healing orchestration (Layer 6)
  semantic/invariance.py        — 7 invariants + 5 healing contracts (Layer 7)

Layers 8-9: Adaptive Learning + Experiments
  control/adaptive_policy.py    — evidence-weighted learning (Layer 8)
  control/experiments.py        — counterfactual A/B testing (Layer 9)

Layers 10-11: Meta-Learning + Containment
  control/metalearning.py       — Lyapunov convergence (Layer 10)
  containment.py                — 4 mathematical bounds (Layer 11)

Layers 12-13: Constraint Reflexivity + Transparency
  meta_constraint.py            — MCL: rigidity/suppression/coupling (Layer 12)
  cti.py                        — CTI: learning occlusion (Layer 13)

Layer 14: Unified Dashboard
  dashboard.py                  — A→F grade, health, contributors (Layer 14)
"""

from .execution_control_plane import (
    ExecutionControlPlane, ControlAction, ControlActionType,
    ExecutionSignal, SignalType, get_control_plane,
    evaluate_signals, apply_stabilizers,
)
from .benchmarks import (
    DecisionTracer, DecisionTrace, get_tracer,
    score_session, BenchmarkScore,
)
from .semantic import (
    SemanticStabilityMonitor, SemanticStabilityReport, get_semantic_monitor,
    StateSnapshotManager, CognitiveSnapshot, get_snapshot_manager,
    SemanticRollback, get_semantic_rollback,
    SelfHealingMonitor, get_self_healing_monitor,
    CognitiveInvariance, Invariant, HealingContract, RecoveryValidation, get_cognitive_invariance,
)
from .control.adaptive_policy import AdaptivePolicy, get_adaptive_policy
from .control.experiments import PolicyExperimentRunner, get_experiment_runner
from .control.metalearning import MetaLearningMonitor, get_metalearning_monitor
from .containment import (
    ContainmentSystem, InvarianceTestSuite, DriftContainment,
    MetalearningStability, AcceptanceControl,
    get_containment,
)
from .cti import ConstraintTransparencyIndex, CTIReport, get_cti
from .dashboard import ContinuousDashboard, get_dashboard
from .meta_constraint import MetaConstraintLayer, MCLReport, get_mcl

__all__ = [
    # Layers 1-3: ECP + Benchmarks
    "ExecutionControlPlane", "ControlAction", "ControlActionType",
    "ExecutionSignal", "SignalType", "get_control_plane",
    "evaluate_signals", "apply_stabilizers",
    "DecisionTracer", "DecisionTrace", "get_tracer",
    "score_session", "BenchmarkScore",
    # Layers 5-7: Semantic + Healing + Invariance
    "SemanticStabilityMonitor", "SemanticStabilityReport", "get_semantic_monitor",
    "StateSnapshotManager", "CognitiveSnapshot", "get_snapshot_manager",
    "SemanticRollback", "get_semantic_rollback",
    "SelfHealingMonitor", "get_self_healing_monitor",
    "CognitiveInvariance", "Invariant", "HealingContract", "RecoveryValidation", "get_cognitive_invariance",
    # Layer 8: Adaptive Policy
    "AdaptivePolicy", "get_adaptive_policy",
    # Layer 9: Experiments
    "PolicyExperimentRunner", "get_experiment_runner",
    # Layer 10: Meta-Learning
    "MetaLearningMonitor", "get_metalearning_monitor",
    # Layer 11: Containment
    "ContainmentSystem", "InvarianceTestSuite", "DriftContainment",
    "MetalearningStability", "AcceptanceControl",
    "get_containment",
    # Layer 12: MCL
    "MetaConstraintLayer", "MCLReport", "get_mcl",
    # Layer 13: CTI
    "ConstraintTransparencyIndex", "CTIReport", "get_cti",
    # Layer 14: Dashboard
    "ContinuousDashboard", "get_dashboard",
]
