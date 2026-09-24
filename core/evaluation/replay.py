"""Replay Engine — scientifically auditable execution.

Records and replays every decision, signal, and action during execution.
Compares two runs step-by-step and explains ANY divergence.

This transforms WIDDX from "powerful" to "scientifically auditable."
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("widdx.replay")


@dataclass
class RecordedStep:
    """A single recorded execution step."""
    step: int
    phase: str  # "collect" | "decide" | "execute" | "after"
    signals_in: list[dict] = field(default_factory=list)
    ecp_raw_action: str = ""
    ecp_stabilized_action: str = ""
    policy_applied: bool = False
    cooldown_active: bool = False
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)
    tool_result: str = ""
    tool_success: bool = False
    model_used: str = ""
    cost: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class ExecutionRecord:
    """Complete record of one task execution."""
    run_id: str
    seed: int
    goal: str
    config_hash: str
    steps: list[RecordedStep] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    total_cost: float = 0.0
    total_steps: int = 0
    ecp_interventions: int = 0


@dataclass
class ReplayDiff:
    """Difference between two replay executions."""
    step: int
    run_a_action: str
    run_b_action: str
    identical: bool
    divergence_reason: str = ""
    signal_delta: dict = field(default_factory=dict)


class ReplayEngine:
    """Records, replays, and compares task executions.

    Records every step of execution with full state.
    Can replay by feeding the same signals into ECP.
    Compares two runs and explains any divergence.
    """

    REPLAY_PATH = ".widdx/replays/"

    def __init__(self):
        self._recording: ExecutionRecord | None = None
        self._records: dict[str, ExecutionRecord] = {}

    def start_recording(self, run_id: str, seed: int, goal: str,
                        config_hash: str = "") -> ExecutionRecord:
        """Begin recording a new execution."""
        rec = ExecutionRecord(
            run_id=run_id,
            seed=seed,
            goal=goal[:200],
            config_hash=config_hash or hashlib.sha256(str(time.time()).encode()).hexdigest()[:8],
        )
        self._recording = rec
        return rec

    def record_step(self, step: int, phase: str,
                    signals: list | None = None,
                    raw_action: str = "",
                    stabilized_action: str = "",
                    policy_applied: bool = False,
                    cooldown: bool = False,
                    tool_name: str = "",
                    tool_args: dict | None = None,
                    tool_result: str = "",
                    tool_success: bool = False,
                    model: str = "",
                    cost: float = 0.0):
        """Record a single execution step."""
        if self._recording is None:
            return
        self._recording.steps.append(RecordedStep(
            step=step, phase=phase,
            signals_in=[{"type": s.signal_type.name, "value": s.value, "source": s.source}
                        for s in (signals or [])],
            ecp_raw_action=raw_action,
            ecp_stabilized_action=stabilized_action,
            policy_applied=policy_applied,
            cooldown_active=cooldown,
            tool_name=tool_name,
            tool_args=tool_args or {},
            tool_result=tool_result[:200],
            tool_success=tool_success,
            model_used=model,
            cost=cost,
        ))

    def stop_recording(self) -> ExecutionRecord | None:
        """Finalize recording and save to disk."""
        if self._recording is None:
            return None
        rec = self._recording
        rec.end_time = time.time()
        rec.total_cost = sum(s.cost for s in rec.steps)
        rec.total_steps = len(rec.steps)
        rec.ecp_interventions = sum(
            1 for s in rec.steps
            if s.ecp_stabilized_action not in ("", "CONTINUE")
        )
        self._records[rec.run_id] = rec
        self._save(rec)
        self._recording = None
        return rec

    def _save(self, rec: ExecutionRecord):
        path = Path(self.REPLAY_PATH) / f"{rec.run_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "run_id": rec.run_id, "seed": rec.seed,
            "goal": rec.goal, "config_hash": rec.config_hash,
            "start_time": rec.start_time, "end_time": rec.end_time,
            "total_cost": rec.total_cost, "total_steps": rec.total_steps,
            "ecp_interventions": rec.ecp_interventions,
            "steps": [
                {
                    "step": s.step, "phase": s.phase,
                    "signals": s.signals_in,
                    "raw": s.ecp_raw_action, "stabilized": s.ecp_stabilized_action,
                    "policy": s.policy_applied, "cooldown": s.cooldown_active,
                    "tool": s.tool_name, "tool_success": s.tool_success,
                    "model": s.model_used, "cost": s.cost,
                }
                for s in rec.steps
            ],
        }
        path.write_text(json.dumps(data, indent=2))
        logger.info("Replay saved: %s (%d steps) → %s", rec.run_id, rec.total_steps, path)

    def load(self, run_id: str) -> ExecutionRecord | None:
        """Load a saved replay from disk."""
        path = Path(self.REPLAY_PATH) / f"{run_id}.json"
        if not path.exists():
            logger.warning("Replay not found: %s", run_id)
            return None
        data = json.loads(path.read_text())
        rec = ExecutionRecord(
            run_id=data["run_id"], seed=data["seed"],
            goal=data["goal"], config_hash=data["config_hash"],
            start_time=data["start_time"], end_time=data["end_time"],
            total_cost=data["total_cost"], total_steps=data["total_steps"],
            ecp_interventions=data["ecp_interventions"],
        )
        for s in data["steps"]:
            rec.steps.append(RecordedStep(
                step=s["step"], phase=s["phase"],
                signals_in=s.get("signals", []),
                ecp_raw_action=s.get("raw", ""),
                ecp_stabilized_action=s.get("stabilized", ""),
                policy_applied=s.get("policy", False),
                cooldown_active=s.get("cooldown", False),
                tool_name=s.get("tool", ""),
                tool_success=s.get("tool_success", False),
                model_used=s.get("model", ""),
                cost=s.get("cost", 0.0),
            ))
        return rec

    def compare(self, run_id_a: str, run_id_b: str) -> dict:
        """Compare two replay executions step by step.

        Returns a detailed diff explaining any divergence.
        """
        rec_a = self._records.get(run_id_a) or self.load(run_id_a)
        rec_b = self._records.get(run_id_b) or self.load(run_id_b)

        if rec_a is None or rec_b is None:
            return {"error": "One or both replays not found"}

        diffs: list[ReplayDiff] = []
        max_steps = max(len(rec_a.steps), len(rec_b.steps))

        for i in range(max_steps):
            step_a = rec_a.steps[i] if i < len(rec_a.steps) else None
            step_b = rec_b.steps[i] if i < len(rec_b.steps) else None

            if step_a is None:
                diffs.append(ReplayDiff(
                    step=i, run_a_action="missing",
                    run_b_action=step_b.ecp_stabilized_action if step_b else "missing",
                    identical=False, divergence_reason="Run A ended earlier",
                ))
                continue
            if step_b is None:
                diffs.append(ReplayDiff(
                    step=i, run_a_action=step_a.ecp_stabilized_action, run_b_action="missing",
                    identical=False, divergence_reason="Run B ended earlier",
                ))
                continue

            signal_diff = {}
            sigs_a = {s["type"]: s["value"] for s in step_a.signals_in}
            sigs_b = {s["type"]: s["value"] for s in step_b.signals_in}
            all_types = set(sigs_a.keys()) | set(sigs_b.keys())
            for t in all_types:
                if sigs_a.get(t) != sigs_b.get(t):
                    signal_diff[t] = {"a": sigs_a.get(t), "b": sigs_b.get(t)}

            action_identical = step_a.ecp_stabilized_action == step_b.ecp_stabilized_action
            reason = ""
            if not action_identical:
                if signal_diff:
                    reason = f"Signals diverged: {list(signal_diff.keys())}"
                elif step_a.cooldown_active != step_b.cooldown_active:
                    reason = "Cooldown timing mismatch"
                else:
                    reason = f"ECP decided differently: {step_a.ecp_raw_action} vs {step_b.ecp_raw_action}"

            diffs.append(ReplayDiff(
                step=i,
                run_a_action=step_a.ecp_stabilized_action,
                run_b_action=step_b.ecp_stabilized_action,
                identical=action_identical,
                divergence_reason=reason,
                signal_delta=signal_diff,
            ))

        identical_steps = sum(1 for d in diffs if d.identical)
        first_divergence = next((d.step for d in diffs if not d.identical), None)

        return {
            "run_a": {"id": rec_a.run_id, "steps": rec_a.total_steps, "cost": rec_a.total_cost, "interventions": rec_a.ecp_interventions},
            "run_b": {"id": rec_b.run_id, "steps": rec_b.total_steps, "cost": rec_b.total_cost, "interventions": rec_b.ecp_interventions},
            "total_steps_compared": max_steps,
            "identical_steps": identical_steps,
            "divergence_rate": round(1.0 - identical_steps / max(max_steps, 1), 3),
            "first_divergence_at_step": first_divergence,
            "is_deterministic": identical_steps == max_steps,
            "diffs": [
                {
                    "step": d.step,
                    "a": d.run_a_action, "b": d.run_b_action,
                    "identical": d.identical,
                    "reason": d.divergence_reason,
                }
                for d in diffs if not d.identical
            ][:20],
        }

    def verify_determinism(self, run_id: str, trials: int = 3) -> dict:
        """Run N trials with same seed and verify they produce identical output.

        Creates load test records, replays them through ECP with the same
        signals, and checks if every decision is identical.
        """
        base = self._records.get(run_id) or self.load(run_id)
        if base is None:
            return {"error": f"Baseline replay {run_id} not found"}

        results = []
        for trial_id in range(trials):
            # Collect signals from baseline
            trial_signals = []
            for s in base.steps:
                if s.signals_in:
                    trial_signals.extend(s.signals_in)

            # Simulate: run ECP with same signals
            from core.runtime.control.types import ExecutionSignal, SignalType as ST
            from core.runtime.control.execution_plane import ExecutionControlPlane
            ecp = ExecutionControlPlane()
            ecp.start_task(current_model="replay-model", plan_steps=base.total_steps)

            trial_decisions = []
            step = 0
            for s in base.steps:
                if s.signals_in:
                    for sig_data in s.signals_in:
                        sig_type = getattr(ST, sig_data["type"], ST.STUCK)
                        ecp.collect_signal(ExecutionSignal(
                            signal_type=sig_type,
                            value=sig_data.get("value", 0.5),
                            source=sig_data.get("source", "replay"),
                        ))
                d = ecp.before_step(step, current_model="replay-model")
                trial_decisions.append(d.action.name)
                step += 1

            # Compare
            same = 0
            for i, (base_s, trial_d) in enumerate(zip(base.steps, trial_decisions)):
                if base_s.ecp_stabilized_action == trial_d:
                    same += 1

            results.append({
                "trial": trial_id,
                "identical": same,
                "total": len(trial_decisions),
                "match_rate": round(same / max(len(trial_decisions), 1), 3),
            })

        perfect_trials = sum(1 for r in results if r["match_rate"] == 1.0)
        return {
            "run_id": run_id,
            "trials": trials,
            "perfect_trials": perfect_trials,
            "is_deterministic": perfect_trials == trials,
            "results": results,
        }


_replay: ReplayEngine | None = None


def get_replay_engine() -> ReplayEngine:
    global _replay
    if _replay is None:
        _replay = ReplayEngine()
    return _replay
