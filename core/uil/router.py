"""Decision Router — maps ClassificationResult to ExecutionPlan.

Zero classification logic. Zero hidden intelligence.
Pure mapping: TaskType → ExecutionMode + filtered tool list.

Dependencies: contract.py only.
"""

import logging
from typing import Any

from .contract import (
    TaskType, ExecutionMode, Domain,
    ClassificationResult, ExecutionPlan,
    RoutingDecision, DecisionStep,
)

logger = logging.getLogger("widdx.router")

# -------------------------------------------------------------------
# Execution Mode Map (deterministic, no conditions)
# -------------------------------------------------------------------

_MODE_MAP: dict[TaskType, ExecutionMode] = {
    # SIMPLE_CHAT: no tools or read-only tools
    TaskType.CHAT:      ExecutionMode.SIMPLE_CHAT,
    TaskType.CODE_READ: ExecutionMode.SIMPLE_CHAT,
    TaskType.FILE_OPS:  ExecutionMode.SIMPLE_CHAT,
    # AUTONOMOUS: agent with filtered tools
    TaskType.CODE_WRITE:   ExecutionMode.AUTONOMOUS,
    TaskType.CODE_MODIFY:  ExecutionMode.AUTONOMOUS,
    TaskType.CODE_REVIEW:  ExecutionMode.AUTONOMOUS,
    TaskType.BROWSER:      ExecutionMode.AUTONOMOUS,
    TaskType.DATABASE:     ExecutionMode.AUTONOMOUS,
    TaskType.RESEARCH:     ExecutionMode.AUTONOMOUS,
    TaskType.REASONING:    ExecutionMode.AUTONOMOUS,
    # EXPERT_TEAM: full multi-agent pipeline
    TaskType.COMPLEX: ExecutionMode.EXPERT_TEAM,
    # DIRECT_TOOL: single system call
    TaskType.SYSTEM: ExecutionMode.DIRECT_TOOL,
    # FALLBACK: treat unknown as simple chat (fast, streaming)
    TaskType.UNKNOWN: ExecutionMode.SIMPLE_CHAT,
}


# -------------------------------------------------------------------
# Tool Filter Groups (deterministic, no conditions)
# -------------------------------------------------------------------

_TOOL_GROUPS: dict[TaskType, list[str] | None] = {
    TaskType.CHAT:       [],
    TaskType.CODE_READ:  ["read", "glob", "grep", "list_files"],
    TaskType.CODE_WRITE: ["read", "write", "edit", "glob", "grep", "bash", "validate", "list_files"],
    TaskType.CODE_MODIFY: ["read", "write", "edit", "glob", "grep", "bash", "validate", "list_files"],
    TaskType.CODE_REVIEW: ["read", "glob", "grep", "validate", "list_files"],
    TaskType.BROWSER:    ["mcp__playwright__*"],
    TaskType.DATABASE:   ["mcp__sqlite__*", "mcp__filesystem__read_file"],
    TaskType.RESEARCH:   ["web_fetch", "mcp__fetch__*", "read", "grep"],
    TaskType.REASONING:  ["read", "grep", "glob",
                          "mcp__sequential-thinking__*"],
    TaskType.FILE_OPS:   ["read", "write", "bash", "list_files", "glob", "grep"],
    TaskType.SYSTEM:     ["bash"],
    TaskType.COMPLEX:    None,
    TaskType.UNKNOWN:    None,
}


# -------------------------------------------------------------------
# Domain Tool Modifiers (secondary routing factor)
# -------------------------------------------------------------------

# Task types that should only have read-only tools, even when
# their domain modifier adds write-capable tools.
_READ_ONLY_TASK_TYPES: set[TaskType] = {
    TaskType.CODE_READ,
    TaskType.CODE_REVIEW,
    TaskType.CHAT,
}

_DOMAIN_TOOL_MODIFIERS: dict[Domain, list[str]] = {
    Domain.CODE:      ["write", "bash"],
    Domain.RESEARCH:  ["web_fetch"],
    Domain.DATABASE:  ["bash", "read"],
    Domain.BROWSER:   [],
    Domain.REASONING: [],
    Domain.CHAT:      [],
    Domain.SYSTEM:    ["bash"],
}


# -------------------------------------------------------------------
# Complexity default by mode
# -------------------------------------------------------------------

_COMPLEXITY_DEFAULTS: dict[ExecutionMode, float] = {
    ExecutionMode.SIMPLE_CHAT:  0.2,
    ExecutionMode.AUTONOMOUS:   0.5,
    ExecutionMode.EXPERT_TEAM:  0.8,
    ExecutionMode.DIRECT_TOOL:  0.3,
}


# -------------------------------------------------------------------
# Router
# -------------------------------------------------------------------

class DecisionRouter:
    """Maps a ClassificationResult to a RoutingDecision."""

    def route(self, classification: ClassificationResult,
              all_tool_defs: list[dict],
              knowledge: Any | None = None) -> RoutingDecision:
        """Transform a classification into a complete routing decision.

        Args:
            classification: Result from TaskAnalyzer.analyze().
            all_tool_defs:  Complete list of all available tool definitions.
            knowledge:      Optional KnowledgeBase for data-driven mode override.
                            Phase 2.1 — Knowledge-Informed Routing.

        Returns:
            RoutingDecision with execution plan + filtered tools + trace.
        """
        steps: list[DecisionStep] = []

        # --- Step 0: PreDecisionForce — modify mode weights by learning ──
        try:
            from core.learning.pre_decision_force import get_pre_decision_force
            pdf = get_pre_decision_force()
            mode_weights = pdf.get_router_weights(classification.task_type.value)
            steps.append(DecisionStep(
                component="PreDecisionForce",
                input_summary=f"weights for {classification.task_type.value}",
                output=", ".join(f"{k}={v:.2f}" for k, v in mode_weights.items()),
                score=0.8,
                detail="Router weights modified by learning history",
            ))
        except Exception as e:
            logger.debug("PreDecisionForce unavailable: %s", e)

        # --- Step 0.5: Learning — query patterns for routing hints ---
        try:
            from core.learning.pattern_library import UnifiedPatternStore
            store = UnifiedPatternStore()
            routing_patterns = store.search(
                category="workflow",
                tags=[classification.task_type.value],
                min_confidence=0.5, limit=1,
            )
            if routing_patterns:
                best = routing_patterns[0]
                steps.append(DecisionStep(
                    component="PatternLibrary",
                    input_summary=f"query=workflow,tag={classification.task_type.value}",
                    output=f"found: {best.name} (conf={best.confidence:.2f})",
                    score=best.confidence,
                    detail=f"Routed with learned pattern: {best.solution[:100]}",
                ))
        except Exception as e:
            logger.debug("PatternLibrary unavailable: %s", e)

        # --- Step 1: Select ExecutionMode ---
        mode = _MODE_MAP.get(
            classification.task_type,
            ExecutionMode.AUTONOMOUS,
        )
        steps.append(DecisionStep(
            component="DecisionRouter",
            input_summary=f"task_type={classification.task_type.value}",
            output=f"mode={mode.value}",
            score=classification.confidence,
            detail=(
                f"TaskType '{classification.task_type.value}' "
                f"maps to ExecutionMode '{mode.value}' "
                f"via deterministic mode table"
            ),
        ))

        # --- Step 1.5: Knowledge-Informed Mode Override ---
        if knowledge is not None:
            suggestion = knowledge.suggest_mode(classification.task_type.value)
            if suggestion is not None:
                original_mode = mode
                mode = suggestion
                steps.append(DecisionStep(
                    component="KnowledgeRouter",
                    input_summary=(
                        f"task_type={classification.task_type.value}, "
                        f"original={original_mode.value}"
                    ),
                    output=f"override={suggestion.value}",
                    score=0.7,
                    detail=(
                        f"Knowledge suggested '{suggestion.value}' for "
                        f"'{classification.task_type.value}' based on "
                        f"historical performance "
                        f"(original: {original_mode.value})"
                    ),
                ))

        # --- Step 2: Filter tools ---
        filtered, filter_steps = self._filter_tools(
            classification.task_type, classification.domain,
            all_tool_defs,
        )
        steps.extend(filter_steps)

        # --- Step 3: Build ExecutionPlan ---
        plan = ExecutionPlan(
            mode=mode,
            required_tool_names=[t["name"] for t in filtered],
            max_turns=self._max_turns_for(mode),
            estimated_cost=self._estimate_cost(mode),
            task_analysis=classification.reasoning,
        )
        steps.append(DecisionStep(
            component="DecisionRouter",
            input_summary=f"mode={mode.value}, tools={len(filtered)}",
            output="ExecutionPlan created",
            score=1.0,
            detail=(
                f"Plan: mode={mode.value}, "
                f"{len(filtered)} tools, "
                f"max_turns={plan.max_turns}, "
                f"est_cost={plan.estimated_cost:.3f}"
            ),
        ))

        return RoutingDecision(
            classification=classification,
            plan=plan,
            tool_defs=filtered,
            decision_path=steps,
        )

    # ------------------------------------------------------------------
    # Internal: tool filtering
    # ------------------------------------------------------------------

    def _filter_tools(
        self, task_type: TaskType, domain: Domain,
        all_tool_defs: list[dict],
    ) -> tuple[list[dict], list[DecisionStep]]:
        """Filter available tools based on task type and domain.

        Applies deterministic tool groups per task type, adds domain-specific
        modifiers, and preserves skill tools and use_skill tool.

        Returns:
            Tuple of (filtered_tool_defs, decision_steps_with_reasoning).
        """
        steps: list[DecisionStep] = []
        allowed_patterns = _TOOL_GROUPS.get(task_type, None)

        if allowed_patterns is None:
            steps.append(DecisionStep(
                component="DecisionRouter._filter_tools",
                input_summary=f"task_type={task_type.value}",
                output=f"ALL tools ({len(all_tool_defs)})",
                score=1.0,
                detail=f"No filter rules for {task_type.value} — passing all tools",
            ))
            return list(all_tool_defs), steps

        if not allowed_patterns:
            steps.append(DecisionStep(
                component="DecisionRouter._filter_tools",
                input_summary=f"task_type={task_type.value}",
                output="NO tools (empty filter)",
                score=0.0,
                detail=f"Explicitly empty filter for {task_type.value} — no tools allowed",
            ))
            return [], steps

        domain_patterns = _DOMAIN_TOOL_MODIFIERS.get(domain, [])
        # For read-only task types, strip write-capable tools from domain modifiers
        if task_type in _READ_ONLY_TASK_TYPES:
            domain_patterns = [dp for dp in domain_patterns
                               if dp not in ("write", "bash", "edit")]
        if domain_patterns:
            for dp in domain_patterns:
                if dp not in allowed_patterns:
                    allowed_patterns = list(allowed_patterns) + [dp]
            steps.append(DecisionStep(
                component="DecisionRouter._filter_tools",
                input_summary=f"domain={domain.value}",
                output=f"+{len(domain_patterns)} domain tool(s)",
                score=0.5,
                detail=f"Domain '{domain.value}' added patterns: "
                       f"{', '.join(domain_patterns)}",
            ))

        from core.skills import skill_manager
        skill_tool_names = {t["name"] for t in skill_manager.get_active_tools()}

        filtered: list[dict] = []
        matched_names: list[str] = []

        for td in all_tool_defs:
            name = td["name"]
            # Always preserve use_skill and active skill tools
            if name == "use_skill" or name in skill_tool_names:
                filtered.append(td)
                matched_names.append(name)
                continue

            for pattern in allowed_patterns:
                if pattern.endswith("*"):
                    prefix = pattern[:-1]
                    if name.startswith(prefix):
                        filtered.append(td)
                        matched_names.append(name)
                        break
                elif name == pattern:
                    filtered.append(td)
                    matched_names.append(name)
                    break

        steps.append(DecisionStep(
            component="DecisionRouter._filter_tools",
            input_summary=f"{len(all_tool_defs)} available, "
                          f"{len(allowed_patterns)} patterns",
            output=f"{len(filtered)} tools selected",
            score=round(len(filtered) / max(len(all_tool_defs), 1), 2)
                    if all_tool_defs else 1.0,
            detail=(
                f"Kept {len(filtered)}/{len(all_tool_defs)} tools "
                f"using {len(allowed_patterns)} filter patterns: "
                f"{', '.join(matched_names[:10])}"
                f"{'...' if len(matched_names) > 10 else ''}"
            ),
        ))

        return filtered, steps

    # ------------------------------------------------------------------
    # Internal: plan defaults
    # ------------------------------------------------------------------

    @staticmethod
    def _max_turns_for(mode: ExecutionMode) -> int:
        """Return maximum conversation turns appropriate for the execution mode."""
        return {
            ExecutionMode.SIMPLE_CHAT: 5,
            ExecutionMode.AUTONOMOUS: 15,
            ExecutionMode.EXPERT_TEAM: 25,
            ExecutionMode.DIRECT_TOOL: 1,
        }.get(mode, 10)

    @staticmethod
    def _estimate_cost(mode: ExecutionMode) -> float:
        """Return estimated dollar cost for a single execution turn in this mode."""
        return {
            ExecutionMode.SIMPLE_CHAT: 0.002,
            ExecutionMode.AUTONOMOUS: 0.010,
            ExecutionMode.EXPERT_TEAM: 0.050,
            ExecutionMode.DIRECT_TOOL: 0.001,
        }.get(mode, 0.005)
