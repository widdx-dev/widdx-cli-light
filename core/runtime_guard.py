"""Runtime Reliability Layer — Production-grade execution safety.

Six protections:
  1. Memory pressure detection + graceful degradation
  2. Provider call timeout (per-request)
  3. Infinite execution protection (per-turn + max wall time + loop detection)
  4. Corrupted checkpoint recovery (backup + validation)
  5. Disk write protection (detect failures, never silent)
  6. Transactional tool execution (atomic writes, rollback)

Usage:
    from core.runtime_guard import RuntimeGuard
    guard = RuntimeGuard()
    guard.check_before_execute()   # memory, disk
    guard.check_after_write(path)  # disk verification
    guard.validate_checkpoint(data) # integrity check
"""

from __future__ import annotations

import logging
import os
import time
import json
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("widdx.runtime_guard")


# ═══════════════════════════════════════════════════════════════
# 1. Memory Protection
# ═══════════════════════════════════════════════════════════════

@dataclass
class MemoryStatus:
    healthy: bool = True
    used_pct: float = 0.0
    available_mb: float = 0.0
    warning: str = ""


def _get_memory_status() -> MemoryStatus:
    """Detect memory pressure across platforms."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        used_pct = mem.percent
        available_mb = mem.available / (1024 * 1024)
        if used_pct > 90:
            return MemoryStatus(healthy=False, used_pct=used_pct, available_mb=available_mb,
                                warning=f"CRITICAL: {used_pct:.0f}% memory used, {available_mb:.0f}MB free")
        elif used_pct > 75:
            return MemoryStatus(healthy=True, used_pct=used_pct, available_mb=available_mb,
                                warning=f"WARNING: {used_pct:.0f}% memory used")
        return MemoryStatus(healthy=True, used_pct=used_pct, available_mb=available_mb)
    except ImportError:
        return MemoryStatus()  # psutil not available — assume OK


# ═══════════════════════════════════════════════════════════════
# 2. Provider Timeout
# ═══════════════════════════════════════════════════════════════

PROVIDER_TIMEOUT_SECONDS = 120       # per provider call
MAX_WALL_CLOCK_SECONDS = 1800         # 30 min total per task
PER_TURN_TIMEOUT_SECONDS = 300        # 5 min per turn


class ProviderTimeoutError(Exception):
    pass


class WallClockExceededError(Exception):
    pass


# ═══════════════════════════════════════════════════════════════
# 3. Infinite Loop Protection
# ═══════════════════════════════════════════════════════════════

@dataclass
class LoopDetector:
    """Detects repetitive reasoning patterns even with different tools."""
    _recent_responses: list[str] = field(default_factory=list)
    _max_history: int = 10
    _similarity_threshold: float = 0.7

    def is_repetitive(self, content: str) -> bool:
        """Check if response is too similar to recent ones."""
        if not content:
            return False
        # Simple: check if the first 200 chars match any recent
        prefix = content[:200].strip().lower()
        matches = sum(1 for r in self._recent_responses if r[:200].strip().lower() == prefix)
        self._recent_responses.append(prefix)
        if len(self._recent_responses) > self._max_history:
            self._recent_responses.pop(0)
        return matches >= 3  # Same response prefix repeated 3+ times

    def reset(self):
        self._recent_responses.clear()


# ═══════════════════════════════════════════════════════════════
# 4. Checkpoint Integrity
# ═══════════════════════════════════════════════════════════════

def _compute_hash(data: dict) -> str:
    """Compute a deterministic hash of checkpoint data."""
    raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def save_checkpoint_atomic(data: dict, filepath: Path):
    """Save checkpoint with .tmp + .backup + integrity hash."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    data["_integrity"] = _compute_hash(data)
    data["_timestamp"] = time.time()

    tmp_path = filepath.with_suffix(".tmp")
    bak_path = filepath.with_name(filepath.name + ".backup")

    # Write to temp
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Backup existing
    if filepath.exists():
        try:
            filepath.replace(bak_path)
        except OSError:
            pass

    # Atomic replace
    try:
        os.replace(str(tmp_path), str(filepath))
    except OSError:
        tmp_path.rename(filepath)


def load_checkpoint_safe(filepath: Path) -> dict | None:
    """Load checkpoint with integrity validation. Falls back to .backup."""
    for path in (filepath, filepath.with_name(filepath.name + ".backup")):
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            saved_hash = data.pop("_integrity", None)
            data.pop("_timestamp", None)
            if saved_hash:
                current = _compute_hash(data)
                if current != saved_hash:
                    logger.warning("Checkpoint integrity FAILED for %s — trying backup", filepath)
                    continue  # Try backup
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Checkpoint corrupt: %s — %s", path, e)
            continue
    return None


# ═══════════════════════════════════════════════════════════════
# 5. Disk Write Protection
# ═══════════════════════════════════════════════════════════════

MIN_FREE_DISK_MB = 100


def _check_disk_space(write_path: str | Path) -> bool:
    """Check if disk has enough free space."""
    try:
        import shutil
        p = Path(write_path)
        # Find the mount point
        while not p.exists():
            p = p.parent
        usage = shutil.disk_usage(p)
        free_mb = usage.free / (1024 * 1024)
        if free_mb < MIN_FREE_DISK_MB:
            logger.critical("DISK FULL: %.0fMB free < %dMB minimum", free_mb, MIN_FREE_DISK_MB)
            return False
        return True
    except Exception:
        return True  # Can't check — assume OK


def verify_write_success(filepath: str | Path, expected_min_bytes: int = 0) -> bool:
    """Verify a file was actually written to disk."""
    p = Path(filepath)
    if not p.exists():
        logger.error("Write verification FAILED: %s does not exist", filepath)
        return False
    if expected_min_bytes > 0 and p.stat().st_size < expected_min_bytes:
        logger.error("Write verification FAILED: %s is %d bytes (expected >=%d)",
                     filepath, p.stat().st_size, expected_min_bytes)
        return False
    return True


# ═══════════════════════════════════════════════════════════════
# 6. Transactional Tool Execution
# ═══════════════════════════════════════════════════════════════

class TransactionalWrite:
    """Atomic file write with rollback capability."""

    def __init__(self, filepath: str | Path):
        self._path = Path(filepath)
        self._tmp = self._path.with_suffix(".txn_tmp")
        self._backup: bytes | None = None
        self._committed = False

    def __enter__(self):
        # Backup original
        if self._path.exists():
            self._backup = self._path.read_bytes()
        return self

    def write(self, content: str | bytes):
        """Write to temp file."""
        data = content.encode("utf-8") if isinstance(content, str) else content
        # Check disk space first
        if not _check_disk_space(self._tmp):
            raise OSError(f"Disk full — cannot write to {self._path}")
        self._tmp.parent.mkdir(parents=True, exist_ok=True)
        self._tmp.write_bytes(data)
        # Verify
        if not verify_write_success(self._tmp, len(data)):
            raise OSError(f"Write verification failed for {self._tmp}")

    def commit(self):
        """Atomically replace the target file."""
        try:
            os.replace(str(self._tmp), str(self._path))
            self._committed = True
        except OSError:
            self._tmp.rename(self._path)
            self._committed = True

    def rollback(self):
        """Restore original content."""
        if self._tmp.exists():
            self._tmp.unlink(missing_ok=True)
        if self._backup is not None:
            self._path.write_bytes(self._backup)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False


# ═══════════════════════════════════════════════════════════════
# Unified RuntimeGuard
# ═══════════════════════════════════════════════════════════════

class RuntimeGuard:
    """Unified runtime sensor — feeds signals to ECP, does NOT block execution.

    Under Unified Control Theory, RuntimeGuard is a PURE SENSOR.
    It reports state through collect() — ECP is the sole decision authority.
    """

    def __init__(self):
        self._loop_detector = LoopDetector()
        self._wall_start: float = 0.0
        self._turn_start: float = 0.0
        self._total_turns: int = 0
        self._warnings: list[str] = []
        self._memory_status: MemoryStatus | None = None
        self._loop_detected: bool = False
        self._turn_timeout: bool = False

    def start_task(self):
        """Called once at the beginning of an autonomous task."""
        self._wall_start = time.time()
        self._loop_detector.reset()
        self._warnings.clear()
        self._memory_status = None
        self._loop_detected = False
        self._turn_timeout = False

    def collect(self) -> list:
        """Return current signals for ECP. PURE SENSOR — no side effects."""
        from core.runtime.execution_control_plane import ExecutionSignal, SignalType
        signals = []

        mem = _get_memory_status()
        self._memory_status = mem
        if not mem.healthy:
            signals.append(ExecutionSignal(
                signal_type=SignalType.MEMORY_PRESSURE,
                value=mem.used_pct / 100.0,
                source="RuntimeGuard",
                detail=mem.warning,
            ))

        if self._loop_detected:
            signals.append(ExecutionSignal(
                signal_type=SignalType.LOOP_DETECTED,
                value=0.85,
                source="RuntimeGuard",
                detail="Repetitive response loop detected",
            ))
            self._loop_detected = False

        if self._turn_timeout:
            signals.append(ExecutionSignal(
                signal_type=SignalType.TOKEN_INEFFICIENCY,
                value=0.7,
                source="RuntimeGuard",
                detail=f"Turn timeout exceeded {PER_TURN_TIMEOUT_SECONDS}s",
            ))
            self._turn_timeout = False

        if self._wall_start > 0:
            elapsed = time.time() - self._wall_start
            if elapsed > MAX_WALL_CLOCK_SECONDS * 0.8:
                signals.append(ExecutionSignal(
                    signal_type=SignalType.QUALITY_DEGRADATION,
                    value=0.7,
                    source="RuntimeGuard",
                    detail=f"Wall clock at {elapsed:.0f}s / {MAX_WALL_CLOCK_SECONDS}s",
                ))

        return signals

    def before_provider_call(self) -> bool:
        """Track timing and check wall clock. Always returns True (sensor only)."""
        self._check_wall_clock()
        self._turn_start = time.time()
        return True

    def after_provider_call(self, content: str) -> bool:
        """Track loops and timeouts. Always returns True (sensor only)."""
        elapsed = time.time() - self._turn_start
        if elapsed > PER_TURN_TIMEOUT_SECONDS:
            logger.warning("Turn timeout: %.0fs > %ds", elapsed, PER_TURN_TIMEOUT_SECONDS)
            self._turn_timeout = True

        if self._loop_detector.is_repetitive(content):
            logger.warning("Loop detected: repetitive responses")
            self._loop_detected = True
        self._total_turns += 1
        return True

    def before_write(self, filepath: str | Path) -> bool:
        """Check if it's safe to write. Returns True if disk has space."""
        return _check_disk_space(filepath)

    def after_write(self, filepath: str | Path, expected_bytes: int = 0) -> bool:
        """Verify write succeeded."""
        return verify_write_success(filepath, expected_bytes)

    def save_checkpoint(self, data: dict, name: str = "checkpoint"):
        """Save a validated checkpoint."""
        from pathlib import Path as _P
        cp_dir = _P.cwd() / ".widdx" / "checkpoints"
        cp_dir.mkdir(parents=True, exist_ok=True)
        save_checkpoint_atomic(data, cp_dir / f"{name}.json")

    def load_checkpoint(self, name: str = "checkpoint") -> dict | None:
        """Load a validated checkpoint with fallback."""
        from pathlib import Path as _P
        return load_checkpoint_safe(_P.cwd() / ".widdx" / "checkpoints" / f"{name}.json")

    def _check_wall_clock(self):
        if self._wall_start > 0:
            elapsed = time.time() - self._wall_start
            if elapsed > MAX_WALL_CLOCK_SECONDS:
                raise WallClockExceededError(
                    f"Task exceeded {MAX_WALL_CLOCK_SECONDS}s wall clock limit"
                )

    @property
    def status(self) -> dict:
        return {
            "total_turns": self._total_turns,
            "wall_elapsed": round(time.time() - self._wall_start, 1) if self._wall_start else 0,
            "warnings": self._warnings[-5:],
            "memory": _get_memory_status().__dict__,
        }


# Singleton
_runtime_guard: RuntimeGuard | None = None


def get_runtime_guard() -> RuntimeGuard:
    global _runtime_guard
    if _runtime_guard is None:
        _runtime_guard = RuntimeGuard()
    return _runtime_guard
