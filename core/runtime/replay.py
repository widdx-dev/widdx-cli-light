"""Deterministic Replay Engine — full state recording and replay with diff verification.

Provides scientific auditability: every execution step is recorded with complete
state snapshots, enabling deterministic replay and signal delta analysis.

Architecture:
  1. ReplayRecorder — captures state at every step (signals, decisions, actions, context)
  2. ReplayPlayer — replays recorded execution with deterministic inputs
  3. ReplayVerifier — compares replay output against original to detect drift

State captured per step:
  - Timestamp and step number
  - Active signals (type, value, source)
  - ECP decision (raw + stabilized)
  - Tool calls and results
  - Context hash (for integrity verification)
  - Policy state (cooldown, caps, oscillation pattern)

Usage:
    recorder = ReplayRecorder()
    recorder.start_task("task_id")
    
    # During execution:
    recorder.capture_step(step, signals, decision, tool_calls, context_hash)
    
    # After execution:
    recording = recorder.save()
    
    # Replay:
    player = ReplayPlayer(recording)
    result = player.replay()
    
    # Verify:
    verifier = ReplayVerifier()
    report = verifier.compare(original, replayed)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("widdx.replay")


@dataclass
class StepSnapshot:
    """Complete state snapshot at a single execution step."""
    step: int
    timestamp: float
    phase: str  # "before_llm", "after_llm", "after_tool"
    signals: list[dict[str, Any]]  # [{type, value, source}]
    decision_raw: str  # raw ECP action name
    decision_final: str  # stabilized action name
    policy_applied: bool
    tool_calls: list[dict[str, Any]]  # [{name, args, result}]
    context_hash: str  # SHA256 of serialized messages
    policy_state: dict[str, Any]  # cooldown, caps, oscillation
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskRecording:
    """Complete recording of a task execution."""
    task_id: str
    goal: str
    start_time: float
    end_time: float
    steps: list[StepSnapshot]
    final_outcome: str  # "success", "failure", "aborted", "max_iterations"
    final_state: dict[str, Any]  # cost, turns, tools_used, etc.
    checksum: str  # integrity verification


@dataclass
class ReplayResult:
    """Result of a replay execution."""
    task_id: str
    success: bool
    steps_replayed: int
    decisions_match: bool
    divergence_step: int | None  # first step where replay diverged
    divergence_details: dict[str, Any]
    replay_time_ms: float


@dataclass
class ReplayReport:
    """Complete replay verification report."""
    task_id: str
    is_deterministic: bool  # replay matched original exactly
    match_percentage: float  # % of steps that matched
    divergences: list[dict[str, Any]]
    signal_deltas: list[dict[str, Any]]
    recommendation: str


class ReplayRecorder:
    """Records complete execution state for deterministic replay."""

    def __init__(self):
        self._task_id: str = ""
        self._goal: str = ""
        self._start_time: float = 0.0
        self._steps: list[StepSnapshot] = []
        self._final_state: dict[str, Any] = {}
        self._is_recording: bool = False

    def start_task(self, task_id: str, goal: str = "") -> None:
        """Start recording a task execution."""
        self._task_id = task_id
        self._goal = goal
        self._start_time = time.time()
        self._steps.clear()
        self._final_state = {}
        self._is_recording = True
        logger.info("REPLAY RECORD: task=%s started", task_id[:12])

    def capture_step(
        self,
        step: int,
        phase: str,
        signals: list[Any] | None = None,
        decision_raw: str = "",
        decision_final: str = "",
        policy_applied: bool = False,
        tool_calls: list[dict[str, Any]] | None = None,
        messages: list[dict[str, Any]] | None = None,
        policy_state: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StepSnapshot:
        """Capture a single execution step."""
        if not self._is_recording:
            raise RuntimeError("Recorder not started — call start_task() first")

        # Serialize signals
        signal_dicts = []
        if signals:
            for s in signals:
                try:
                    signal_dicts.append({
                        "type": s.signal_type.name if hasattr(s, 'signal_type') else str(s.get('type', 'unknown')),
                        "value": float(s.value) if hasattr(s, 'value') else float(s.get('value', 0)),
                        "source": str(s.source) if hasattr(s, 'source') else str(s.get('source', '')),
                    })
                except Exception:
                    continue

        # Compute context hash from messages
        context_hash = ""
        if messages:
            try:
                serialized = json.dumps(messages, sort_keys=True, default=str)
                context_hash = hashlib.sha256(serialized.encode()).hexdigest()[:16]
            except Exception:
                context_hash = "hash_error"

        snapshot = StepSnapshot(
            step=step,
            timestamp=time.time() - self._start_time,
            phase=phase,
            signals=signal_dicts,
            decision_raw=decision_raw,
            decision_final=decision_final,
            policy_applied=policy_applied,
            tool_calls=tool_calls or [],
            context_hash=context_hash,
            policy_state=policy_state or {},
            metadata=metadata or {},
        )
        self._steps.append(snapshot)
        return snapshot

    def finalize(self, outcome: str = "success", final_state: dict[str, Any] | None = None) -> TaskRecording:
        """Finalize recording and return the complete TaskRecording."""
        if not self._is_recording:
            raise RuntimeError("Recorder not started")

        self._is_recording = False
        end_time = time.time()
        self._final_state = final_state or {}

        # Compute integrity checksum
        recording_data = json.dumps([self._step_to_dict(s) for s in self._steps], sort_keys=True, default=str)
        checksum = hashlib.sha256(recording_data.encode()).hexdigest()[:16]

        recording = TaskRecording(
            task_id=self._task_id,
            goal=self._goal,
            start_time=self._start_time,
            end_time=end_time,
            steps=list(self._steps),
            final_outcome=outcome,
            final_state=self._final_state,
            checksum=checksum,
        )

        logger.info(
            "REPLAY RECORD: task=%s finalized — %d steps, outcome=%s, checksum=%s",
            self._task_id[:12], len(self._steps), outcome, checksum,
        )
        return recording

    def _step_to_dict(self, step: StepSnapshot) -> dict:
        return {
            "step": step.step,
            "timestamp": step.timestamp,
            "phase": step.phase,
            "signals": step.signals,
            "decision_raw": step.decision_raw,
            "decision_final": step.decision_final,
            "policy_applied": step.policy_applied,
            "tool_calls": step.tool_calls,
            "context_hash": step.context_hash,
            "policy_state": step.policy_state,
            "metadata": step.metadata,
        }

    def save(self, path: str | Path | None = None) -> Path:
        """Save recording to disk."""
        if self._is_recording:
            self.finalize()

        if not self._steps:
            raise RuntimeError("No recording to save")

        # Build recording from current state
        end_time = time.time()
        recording_data = json.dumps([self._step_to_dict(s) for s in self._steps], sort_keys=True, default=str)
        checksum = hashlib.sha256(recording_data.encode()).hexdigest()[:16]

        recording = TaskRecording(
            task_id=self._task_id,
            goal=self._goal,
            start_time=self._start_time,
            end_time=end_time,
            steps=list(self._steps),
            final_outcome="success",
            final_state=self._final_state,
            checksum=checksum,
        )

        path = Path(path or f".widdx/recordings/{recording.task_id}.json")
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "task_id": recording.task_id,
            "goal": recording.goal,
            "start_time": recording.start_time,
            "end_time": recording.end_time,
            "final_outcome": recording.final_outcome,
            "final_state": recording.final_state,
            "checksum": recording.checksum,
            "steps": [self._step_to_dict(s) for s in recording.steps],
        }
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        logger.info("REPLAY SAVE: %s", path)
        return path

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def step_count(self) -> int:
        return len(self._steps)


class ReplayPlayer:
    """Replays a recorded execution with deterministic inputs."""

    def __init__(self, recording: TaskRecording | dict[str, Any]):
        if isinstance(recording, dict):
            recording = self._from_dict(recording)
        self._recording = recording
        self._current_step: int = 0
        self._replay_results: list[dict[str, Any]] = []

    def _from_dict(self, data: dict[str, Any]) -> TaskRecording:
        steps = []
        for s in data.get("steps", []):
            steps.append(StepSnapshot(
                step=s.get("step", 0),
                timestamp=s.get("timestamp", 0),
                phase=s.get("phase", ""),
                signals=s.get("signals", []),
                decision_raw=s.get("decision_raw", ""),
                decision_final=s.get("decision_final", ""),
                policy_applied=s.get("policy_applied", False),
                tool_calls=s.get("tool_calls", []),
                context_hash=s.get("context_hash", ""),
                policy_state=s.get("policy_state", {}),
                metadata=s.get("metadata", {}),
            ))
        return TaskRecording(
            task_id=data.get("task_id", ""),
            goal=data.get("goal", ""),
            start_time=data.get("start_time", 0),
            end_time=data.get("end_time", 0),
            steps=steps,
            final_outcome=data.get("final_outcome", ""),
            final_state=data.get("final_state", {}),
            checksum=data.get("checksum", ""),
        )

    def replay(self, decision_fn=None) -> ReplayResult:
        """Replay the recorded execution.

        Args:
            decision_fn: optional callable(step, signals) -> decision_override.
                        If provided, uses this instead of recorded decisions
                        (for what-if analysis).

        Returns:
            ReplayResult with match/diverge analysis.
        """
        start_time = time.time()
        divergences = []
        decisions_match = True

        for i, step in enumerate(self._recording.steps):
            self._current_step = i

            # If decision function provided, compare its output
            if decision_fn:
                try:
                    replayed_decision = decision_fn(step.step, step.signals)
                    if replayed_decision != step.decision_final:
                        divergences.append({
                            "step": step.step,
                            "phase": step.phase,
                            "expected": step.decision_final,
                            "actual": replayed_decision,
                            "type": "decision_mismatch",
                        })
                        decisions_match = False
                except Exception as e:
                    divergences.append({
                        "step": step.step,
                        "phase": step.phase,
                        "error": str(e),
                        "type": "decision_error",
                    })
                    decisions_match = False

            self._replay_results.append({
                "step": step.step,
                "decision": step.decision_final,
                "signals": step.signals,
                "tool_calls": step.tool_calls,
            })

        elapsed_ms = (time.time() - start_time) * 1000

        return ReplayResult(
            task_id=self._recording.task_id,
            success=True,
            steps_replayed=len(self._recording.steps),
            decisions_match=decisions_match,
            divergence_step=divergences[0]["step"] if divergences else None,
            divergence_details={"divergences": divergences},
            replay_time_ms=elapsed_ms,
        )

    def replay_iter(self):
        """Generator that yields each step for step-by-step replay analysis."""
        for step in self._recording.steps:
            yield step

    @property
    def recording(self) -> TaskRecording:
        return self._recording


class ReplayVerifier:
    """Compares two recordings to detect drift and verify determinism."""

    def compare(self, original: TaskRecording, replayed: TaskRecording) -> ReplayReport:
        """Compare original vs replayed execution."""
        divergences = []
        signal_deltas = []

        min_steps = min(len(original.steps), len(replayed.steps))
        matching_steps = 0

        for i in range(min_steps):
            orig_step = original.steps[i]
            repl_step = replayed.steps[i]

            # Compare decisions
            if orig_step.decision_final != repl_step.decision_final:
                divergences.append({
                    "step": orig_step.step,
                    "phase": orig_step.phase,
                    "type": "decision_divergence",
                    "original": orig_step.decision_final,
                    "replayed": repl_step.decision_final,
                })
            else:
                matching_steps += 1

            # Compare signals (delta analysis)
            orig_signals = {(s.get("type"), round(s.get("value", 0), 3)) for s in orig_step.signals}
            repl_signals = {(s.get("type"), round(s.get("value", 0), 3)) for s in repl_step.signals}

            added = repl_signals - orig_signals
            removed = orig_signals - repl_signals

            if added or removed:
                signal_deltas.append({
                    "step": orig_step.step,
                    "signals_added": [{"type": t, "value": v} for t, v in added],
                    "signals_removed": [{"type": t, "value": v} for t, v in removed],
                })

        match_pct = ( matching_steps / max(min_steps, 1)) * 100
        is_deterministic = len(divergences) == 0 and len(signal_deltas) == 0

        if is_deterministic:
            rec = "Execution is fully deterministic — replay matches original exactly."
        elif match_pct >= 90:
            rec = f"Near-deterministic ({match_pct:.1f}% match). Minor signal drift detected."
        elif match_pct >= 70:
            rec = f"Partial determinism ({match_pct:.1f}% match). Review divergences."
        else:
            rec = f"Non-deterministic ({match_pct:.1f}% match). Significant drift detected."

        return ReplayReport(
            task_id=original.task_id,
            is_deterministic=is_deterministic,
            match_percentage=round(match_pct, 1),
            divergences=divergences,
            signal_deltas=signal_deltas,
            recommendation=rec,
        )

    def verify_integrity(self, recording: TaskRecording) -> bool:
        """Verify recording hasn't been tampered with."""
        # Use same serialization as finalize()
        step_dicts = []
        for s in recording.steps:
            step_dicts.append({
                "step": s.step,
                "timestamp": s.timestamp,
                "phase": s.phase,
                "signals": s.signals,
                "decision_raw": s.decision_raw,
                "decision_final": s.decision_final,
                "policy_applied": s.policy_applied,
                "tool_calls": s.tool_calls,
                "context_hash": s.context_hash,
                "policy_state": s.policy_state,
                "metadata": s.metadata,
            })
        recording_data = json.dumps(step_dicts, sort_keys=True, default=str)
        computed = hashlib.sha256(recording_data.encode()).hexdigest()[:16]
        return computed == recording.checksum


class ReplayManager:
    """High-level manager for recording, replaying, and verifying executions."""

    def __init__(self):
        self._recorder = ReplayRecorder()
        self._recordings: dict[str, TaskRecording] = {}

    def start_recording(self, task_id: str, goal: str = "") -> ReplayRecorder:
        """Start recording a new task execution."""
        self._recorder.start_task(task_id, goal)
        return self._recorder

    def load_recording(self, path: str | Path) -> ReplayPlayer:
        """Load a recording from disk for replay."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        player = ReplayPlayer(data)
        self._recordings[player.recording.task_id] = player.recording
        return player

    def list_recordings(self, limit: int = 20) -> list[dict]:
        """List available recordings."""
        rec_dir = Path(".widdx/recordings")
        if not rec_dir.exists():
            return []

        recordings = []
        for p in sorted(rec_dir.iterdir(), reverse=True):
            if not p.is_file() or p.suffix != ".json":
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                recordings.append({
                    "task_id": data.get("task_id", "")[:12],
                    "goal": data.get("goal", "")[:60],
                    "steps": len(data.get("steps", [])),
                    "outcome": data.get("final_outcome", ""),
                    "file": str(p),
                })
            except Exception:
                continue
            if len(recordings) >= limit:
                break
        return recordings

    def verify_recording(self, path: str | Path) -> dict:
        """Verify integrity of a recording file."""
        player = self.load_recording(path)
        verifier = ReplayVerifier()
        is_valid = verifier.verify_integrity(player.recording)
        return {
            "task_id": player.recording.task_id[:12],
            "integrity_valid": is_valid,
            "checksum": player.recording.checksum,
            "steps": len(player.recording.steps),
        }


_replay_manager: ReplayManager | None = None


def get_replay_manager() -> ReplayManager:
    global _replay_manager
    if _replay_manager is None:
        _replay_manager = ReplayManager()
    return _replay_manager
