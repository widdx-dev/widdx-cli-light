"""UIL Data Contracts — core types for the Unified Intelligence Layer.

Zero external dependencies. Pure Python stdlib.
Every decision is traceable via DecisionStep logs.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any


# -------------------------------------------------------------------
# Enums
# -------------------------------------------------------------------

class TaskType(Enum):
    """Every possible kind of task the system can receive."""
    CODE_READ = "code_read"
    CODE_WRITE = "code_write"
    CODE_MODIFY = "code_modify"
    CODE_REVIEW = "code_review"
    RESEARCH = "research"
    BROWSER = "browser"
    DATABASE = "database"
    REASONING = "reasoning"
    CHAT = "chat"
    FILE_OPS = "file_ops"
    SYSTEM = "system"
    COMPLEX = "complex"      # requires ExpertTeam
    UNKNOWN = "unknown"


class ExecutionMode(Enum):
    """How the system should execute this task."""
    SIMPLE_CHAT = "simple_chat"     # direct LLM call, minimal/no tools
    AUTONOMOUS = "autonomous"        # AutonomousAgent with filtered tools
    EXPERT_TEAM = "expert_team"      # Full ExpertTeam pipeline
    DIRECT_TOOL = "direct_tool"      # single tool call (e.g., MCP tool)


class Domain(Enum):
    """High-level domain category for the task."""
    CODE = "code"
    RESEARCH = "research"
    BROWSER = "browser"
    DATABASE = "database"
    REASONING = "reasoning"
    CHAT = "chat"
    SYSTEM = "system"


# -------------------------------------------------------------------
# Decision Trace
# -------------------------------------------------------------------

@dataclass
class DecisionStep:
    """A single step in the decision-making process.

    Every classifier, filter, or router operation records one of these.
    This makes the entire UIL decision path 100% traceable.
    """
    component: str           # e.g. "CodeWriteClassifier", "KeywordAnalyzer", "DecisionRouter"
    input_summary: str       # short description of what was evaluated
    output: str              # what was decided
    score: float = 0.0       # confidence / relevance score
    detail: str = ""         # human-readable explanation of WHY this decision

    def to_dict(self) -> dict:
        return {
            "component": self.component,
            "input": self.input_summary,
            "output": self.output,
            "score": self.score,
            "detail": self.detail,
        }


# -------------------------------------------------------------------
# Analysis Results
# -------------------------------------------------------------------

@dataclass
class ClassificationResult:
    """Result of analyzing a user's input.

    Contains both the decision AND the full trace of how it was reached.
    """
    task_type: TaskType
    domain: Domain
    confidence: float           # 0.0-1.0
    complexity: float           # 0.0-1.0 based on depth/ambiguity
    reasoning: str              # summary of why classified this way
    keywords: list[str] = field(default_factory=list)
    detected_features: dict[str, str] = field(default_factory=dict)
    decision_path: list[DecisionStep] = field(default_factory=list)
    # True when no classifier could determine the type with sufficient confidence
    is_fallback: bool = False

    def summarize(self) -> str:
        """One-line summary of this classification."""
        mode = "fallback" if self.is_fallback else "classified"
        return (
            f"[{mode}] type={self.task_type.value} "
            f"domain={self.domain.value} "
            f"confidence={self.confidence:.2f} "
            f"complexity={self.complexity:.2f} | {self.reasoning}"
        )


@dataclass
class ExecutionPlan:
    """What to do with the classified task."""
    mode: ExecutionMode
    required_tool_names: list[str] = field(default_factory=list)
    required_mcp_servers: list[str] = field(default_factory=list)
    sub_plans: list["ExecutionPlan"] = field(default_factory=list)
    max_turns: int = 10
    estimated_cost: float = 0.0
    task_analysis: str = ""     # context passed to the execution layer
    decomposed: "Plan | None" = None  # optional planner decomposition


@dataclass
class RoutingDecision:
    """Final routing decision: HOW to execute + WHICH tools + WHY."""
    classification: ClassificationResult
    plan: ExecutionPlan
    tool_defs: list[dict] = field(default_factory=list)   # filtered tool definitions
    context: str = ""           # enriched context for the executor
    decision_path: list[DecisionStep] = field(default_factory=list)

    def summarize(self) -> str:
        """One-line summary of this routing decision."""
        return (
            f"[route] mode={self.plan.mode.value} "
            f"tools={len(self.tool_defs)} "
            f"from={self.classification.task_type.value}"
        )


@dataclass
class ExecutionResult:
    """Result of executing a routed task.

    Carries the full plan-vs-execution delta — the structured feedback
    that Phase 2's Knowledge Graph will consume.
    """
    success: bool
    summary: str                              # preserved — the text output

    # ── Feedback fields (Phase 1.5) ──
    mode: "ExecutionMode | None" = None        # which execution mode was used
    steps_planned: int = 0                     # from plan.decomposed, set by brain
    steps_completed: int = 0                   # reported by executor (if structured)
    steps_failed: int = 0                      # reported by executor (if structured)
    plan_decomposed: "Plan | None" = None      # reference to the original plan
    tools_used: list[str] = field(default_factory=list)
    cost: float = 0.0
    execution_time: float = 0.0                # seconds, measured by brain wrapper
    error: Optional[str] = None
    verification: "VerificationReport | None" = None  # Phase VERIFY


# -------------------------------------------------------------------
# Execution Context — Phase 1.5 Plan Consumption + Phase 2 Foundation
# -------------------------------------------------------------------

@dataclass
class ExecutionContext:
    """Runtime execution state — transparent proxy for RoutingDecision.

    Delegates all RoutingDecision attributes via __getattr__ so existing
    executors work unchanged (they receive this instead of RoutingDecision).

    New plan-aware code accesses .task_plan and .current_step directly.

    Phase 2 extensibility: additional slots are pre-declared here to avoid
    changing executor signatures when the Knowledge Graph goes live.

    Responsibility split:
      - RoutingDecision = static execution decision (mode, tools, path)
      - ExecutionContext = dynamic runtime state (plan, metrics, feedback)
    """
    decision: "RoutingDecision | None" = None  # underlying static decision

    # ── Plan Consumption (Phase 1.5) ──
    task_plan: "Plan | None" = None            # renamed: avoids collision with decision.plan
    current_step: "TaskStep | None" = None     # current step being executed

    # ── Execution Resources (injected by brain.process) ──
    # These give the executor access to the LLM provider, tool definitions,
    # config, and mutable state (cost, turns). Populated by brain.process()
    # before calling the executor, never by the caller directly.
    provider: "Any | None" = None          # LLM provider instance
    tool_defs: "list[dict] | None" = None  # tool definitions (from UIL._tool_defs)
    cfg: "dict | None" = None              # user configuration
    state: "dict | None" = None            # mutable run state (cost, turns, model)

    # ── Phase 2 — Telemetry (Phase 2.2) ──
    execution_metrics: "ExecutionMetrics | None" = None
    step_results: list["StepResult"] = field(default_factory=list)
    execution_feedback: "ExecutionResult | None" = None
    storage_result: "Any | None" = None
    knowledge_updates: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Fill in defaults from the wrapped RoutingDecision when explicit
        fields are left as None.  This preserves backward compatibility for
        code that creates an ExecutionContext directly from a decision."""
        # When tool_defs is None (not set by brain.process), fall back
        # to the RoutingDecision's filtered tool list.
        if self.tool_defs is None and self.decision is not None:
            object.__setattr__(self, "tool_defs",
                               getattr(self.decision, "tool_defs", []))

    def __getattr__(self, name: str):
        """Delegate unknown attributes to the wrapped RoutingDecision.

        This makes ExecutionContext a drop-in replacement so existing
        executors (which expect RoutingDecision) work without changes.
        """
        if self.decision is None:
            # Return empty defaults instead of crashing — keeps the
            # session alive even if routing was bypassed
            if name == "tool_defs":
                return []
            if name == "classification":
                return None
            if name == "plan":
                return None
            return None
        return getattr(self.decision, name)


# -------------------------------------------------------------------
# Planning Data Contracts
# -------------------------------------------------------------------

@dataclass
class TaskStep:
    """A single step in a decomposed execution plan."""
    id: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    tool_hints: list[str] | None = None
    estimated_difficulty: float = 0.5
    status: str = "pending"


@dataclass
class Plan:
    """A decomposed execution plan with ordered steps and dependencies."""
    steps: list[TaskStep] = field(default_factory=list)
    estimated_complexity: float = 0.5
    is_minimal: bool = False
    decision_path: list[DecisionStep] = field(default_factory=list)


# -------------------------------------------------------------------
# Step Result — per-step telemetry (Phase 2.2)
# -------------------------------------------------------------------

@dataclass
class StepResult:
    """Telemetry for a single executed step."""
    step_id: str
    status: str = "pending"         # pending / running / completed / failed
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    tools_used: list[str] = field(default_factory=list)
    error: Optional[str] = None


# -------------------------------------------------------------------
# Execution Metrics — aggregate telemetry (Phase 2.2)
# -------------------------------------------------------------------

@dataclass
class ExecutionMetrics:
    """Aggregate execution telemetry derived from StepResults."""
    total_execution_time: float = 0.0
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    tools_used_count: int = 0


# -------------------------------------------------------------------
# Verification Contracts (Phase VERIFY)
# -------------------------------------------------------------------

class VerificationSeverity(Enum):
    """How serious a verification finding is."""
    CRITICAL = "critical"     # Output is broken — must fix
    ERROR = "error"           # Functional problem
    WARNING = "warning"       # Should improve
    INFO = "info"             # Nice-to-have


@dataclass
class VerificationFinding:
    """A single thing the verifier found."""
    check_name: str                              # e.g. "html_structure", "js_css_binding"
    severity: VerificationSeverity
    message: str                                 # Human-readable description
    location: str = ""                           # e.g. file path, component name
    suggestion: str = ""                         # How to fix it
    passed: bool = True                          # True = this check passed


@dataclass
class VerificationReport:
    """Complete verification output for one execution."""
    findings: list[VerificationFinding] = field(default_factory=list)
    verifier_name: str = "generic"               # Which verifier ran
    execution_time: float = 0.0                  # Seconds spent verifying
    passed_all: bool = True                      # True if no errors/criticals

    @property
    def criticals(self) -> list[VerificationFinding]:
        return [f for f in self.findings if f.severity == VerificationSeverity.CRITICAL]

    @property
    def errors(self) -> list[VerificationFinding]:
        return [f for f in self.findings if f.severity == VerificationSeverity.ERROR]

    @property
    def warnings(self) -> list[VerificationFinding]:
        return [f for f in self.findings if f.severity == VerificationSeverity.WARNING]

    def add(self, check_name: str, severity: VerificationSeverity,
            message: str, location: str = "", suggestion: str = "",
            passed: bool = True) -> "VerificationFinding":
        """Add a finding and return it."""
        f = VerificationFinding(
            check_name=check_name,
            severity=severity,
            message=message,
            location=location,
            suggestion=suggestion,
            passed=passed,
        )
        self.findings.append(f)
        if severity in (VerificationSeverity.CRITICAL, VerificationSeverity.ERROR) and not passed:
            self.passed_all = False
        return f

    def recompute(self):
        """Recompute passed_all from current findings after external mutations."""
        self.passed_all = not any(
            f.severity in (VerificationSeverity.CRITICAL, VerificationSeverity.ERROR) and not f.passed
            for f in self.findings
        )

    def summarize(self) -> str:
        """One-line summary of verification results."""
        total = len(self.findings)
        passed = sum(1 for f in self.findings if f.passed)
        failed = total - passed
        if total == 0:
            return "[verify] No checks ran"
        return (
            f"[verify] {self.verifier_name}: "
            f"{passed}/{total} passed, "
            f"{failed} failed "
            f"({len(self.criticals)} critical, "
            f"{len(self.errors)} errors, "
            f"{len(self.warnings)} warnings) "
            f"in {self.execution_time:.2f}s"
        )
