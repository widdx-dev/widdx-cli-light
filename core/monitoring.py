"""WIDDX Nexus — Performance Monitoring & Metrics.

Provides real-time visibility into system performance:
  - Request latency tracking (p50, p95, p99)
  - Memory usage tracking
  - Tool execution profiling
  - Provider call statistics
  - Performance degradation alerts

Usage:
    from core.monitoring import metrics_collector

    # Track a request
    with metrics_collector.track_request("health_check"):
        ...

    # Track a tool execution
    with metrics_collector.track_tool("bash"):
        ...

    # Get report
    report = metrics_collector.report()
"""

import logging
import time
import threading
import os
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("widdx.monitoring")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PercentileSummary:
    """Latency percentiles summary."""
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    avg: float = 0.0
    min: float = 0.0
    max: float = 0.0
    count: int = 0


@dataclass
class ToolMetrics:
    """Per-tool execution metrics."""
    total_calls: int = 0
    total_errors: int = 0
    total_duration: float = 0.0
    latencies: list[float] = field(default_factory=list)
    last_error: Optional[str] = None
    last_called: Optional[float] = None


@dataclass
class ProviderMetrics:
    """Per-provider call metrics."""
    total_calls: int = 0
    total_errors: int = 0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    total_duration: float = 0.0
    latencies: list[float] = field(default_factory=list)
    last_error: Optional[str] = None
    failover_count: int = 0


# ---------------------------------------------------------------------------
# Metrics Collector
# ---------------------------------------------------------------------------

class MetricsCollector:
    """Thread-safe performance metrics collector.

    Collects latency, error rates, and throughput for requests,
    tools, and provider calls. Maintains a rolling window of
    recent latencies for percentile calculations.

    The collector caps stored latencies at MAX_LATENCIES per
    category (LRU-style) to avoid unbounded memory growth.
    """

    MAX_LATENCIES = 1000   # max stored latencies per category
    ALERT_THRESHOLD_P95 = 2.0  # seconds — alerts if p95 exceeds this

    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.monotonic()

        # Request metrics (per endpoint)
        self._request_metrics: dict[str, ToolMetrics] = {}

        # Tool metrics
        self._tool_metrics: dict[str, ToolMetrics] = {}

        # Provider metrics
        self._provider_metrics: dict[str, ProviderMetrics] = {}

        # Global counters
        self._total_requests = 0
        self._total_errors = 0
        self._alerts: list[dict] = []

    # ── Context managers ─────────────────────────────────

    def track_request(self, endpoint: str):
        """Context manager: track an HTTP request."""
        return _TimerContext(self, "request", endpoint)

    def track_tool(self, tool_name: str):
        """Context manager: track a tool execution."""
        return _TimerContext(self, "tool", tool_name)

    def track_provider(self, provider_name: str):
        """Context manager: track a provider call."""
        return _TimerContext(self, "provider", provider_name)

    # ── Recording ────────────────────────────────────────

    def record_request(self, endpoint: str, duration: float, error: bool = False,
                       status_code: int = 200):
        """Record an HTTP request timing."""
        with self._lock:
            self._total_requests += 1
            if error:
                self._total_errors += 1
            m = self._request_metrics.setdefault(endpoint, ToolMetrics())
            m.total_calls += 1
            m.total_duration += duration
            m.latencies.append(duration)
            if error:
                m.total_errors += 1
            if len(m.latencies) > self.MAX_LATENCIES:
                m.latencies = m.latencies[-self.MAX_LATENCIES:]
            m.last_called = time.time()

    def record_tool(self, tool_name: str, duration: float, error: bool = False,
                    error_msg: Optional[str] = None):
        """Record a tool execution timing."""
        with self._lock:
            m = self._tool_metrics.setdefault(tool_name, ToolMetrics())
            m.total_calls += 1
            m.total_duration += duration
            m.latencies.append(duration)
            if error:
                m.total_errors += 1
                m.last_error = error_msg
            if len(m.latencies) > self.MAX_LATENCIES:
                m.latencies = m.latencies[-self.MAX_LATENCIES:]
            m.last_called = time.time()

    def record_provider(self, provider_name: str, duration: float,
                        error: bool = False, tokens_input: int = 0,
                        tokens_output: int = 0, failover: bool = False):
        """Record a provider call timing."""
        with self._lock:
            m = self._provider_metrics.setdefault(provider_name, ProviderMetrics())
            m.total_calls += 1
            m.total_duration += duration
            m.latencies.append(duration)
            if error:
                m.total_errors += 1
            m.total_tokens_input += tokens_input
            m.total_tokens_output += tokens_output
            if failover:
                m.failover_count += 1
            if len(m.latencies) > self.MAX_LATENCIES:
                m.latencies = m.latencies[-self.MAX_LATENCIES:]

    def record_alert(self, category: str, message: str, severity: str = "warning",
                     value: Optional[float] = None):
        """Record a performance alert."""
        with self._lock:
            self._alerts.append({
                "category": category,
                "message": message,
                "severity": severity,
                "value": value,
                "time": time.time(),
            })
            # Keep last 100 alerts
            if len(self._alerts) > 100:
                self._alerts = self._alerts[-100:]

    # ── Reporting ────────────────────────────────────────

    def _calc_percentiles(self, latencies: list[float]) -> PercentileSummary:
        if not latencies:
            return PercentileSummary()
        sorted_lats = sorted(latencies)
        n = len(sorted_lats)
        return PercentileSummary(
            p50=sorted_lats[int(n * 0.50)],
            p95=sorted_lats[int(n * 0.95)],
            p99=sorted_lats[int(n * 0.99)],
            avg=sum(sorted_lats) / n,
            min=sorted_lats[0],
            max=sorted_lats[-1],
            count=n,
        )

    def report(self, detailed: bool = False) -> dict:
        """Return a structured performance report.

        Args:
            detailed: If True, includes per-endpoint/tool/provider breakdown.

        Returns:
            dict with uptime, request stats, tool stats, provider stats, alerts.
        """
        with self._lock:
            uptime = time.monotonic() - self._start_time

            report: dict[str, Any] = {
                "uptime_seconds": round(uptime, 1),
                "total_requests": self._total_requests,
                "total_errors": self._total_errors,
                "error_rate": round(
                    self._total_errors / max(self._total_requests, 1), 4
                ),
                "requests_per_second": round(
                    self._total_requests / max(uptime, 1), 2
                ),
                "alerts": len(self._alerts),
                "recent_alerts": self._alerts[-10:],
            }

            if detailed:
                # Per-endpoint
                endpoints = {}
                for name, m in self._request_metrics.items():
                    endpoints[name] = {
                        "calls": m.total_calls,
                        "errors": m.total_errors,
                        "percentiles": self._calc_percentiles(m.latencies).__dict__,
                    }
                report["endpoints"] = endpoints

                # Per-tool
                tools = {}
                for name, m in self._tool_metrics.items():
                    tools[name] = {
                        "calls": m.total_calls,
                        "errors": m.total_errors,
                        "error_rate": round(
                            m.total_errors / max(m.total_calls, 1), 4
                        ),
                        "percentiles": self._calc_percentiles(m.latencies).__dict__,
                        "last_error": m.last_error,
                    }
                report["tools"] = tools

                # Per-provider
                providers = {}
                for name, pm in self._provider_metrics.items():
                    providers[name] = {
                        "calls": pm.total_calls,
                        "errors": pm.total_errors,
                        "tokens_input": pm.total_tokens_input,
                        "tokens_output": pm.total_tokens_output,
                        "failovers": pm.failover_count,
                        "percentiles": self._calc_percentiles(pm.latencies).__dict__,
                    }
                report["providers"] = providers

            # Performance degradation detection
            degradations = []
            for name, m in self._request_metrics.items():
                p95 = self._calc_percentiles(m.latencies).p95
                if p95 > self.ALERT_THRESHOLD_P95 and m.total_calls >= 5:
                    degradations.append({
                        "endpoint": name,
                        "p95": round(p95, 2),
                        "calls": m.total_calls,
                        "issue": f"p95 latency ({p95:.1f}s) exceeds threshold ({self.ALERT_THRESHOLD_P95}s)",
                    })
            report["degradations"] = degradations

            return report

    def report_text(self, detailed: bool = False) -> str:
        """Return human-readable performance report."""
        r = self.report(detailed)
        lines = [
            "╔══════════════════════════════════════════╗",
            "║  WIDDX Nexus — Performance Report        ║",
            "╚══════════════════════════════════════════╝",
            "",
            f"Uptime:          {r['uptime_seconds']:.0f}s",
            f"Total Requests:  {r['total_requests']}",
            f"Total Errors:    {r['total_errors']} ({r['error_rate']*100:.1f}%)",
            f"Throughput:      {r['requests_per_second']:.1f} req/s",
            f"Alerts:          {r['alerts']}",
        ]

        if r['degradations']:
            lines.append("")
            lines.append("⚠️ Performance Degradations:")
            for d in r['degradations']:
                lines.append(f"  • {d['endpoint']}: p95={d['p95']}s ({d['calls']} calls)")

        if detailed and 'endpoints' in r:
            lines.append("")
            lines.append("📊 Endpoint Latency (p95):")
            for name, m in sorted(r['endpoints'].items()):
                p = m['percentiles']
                lines.append(
                    f"  {name:30s} calls={m['calls']:4d}  "
                    f"p50={p['p50']*1000:5.0f}ms  "
                    f"p95={p['p95']*1000:5.0f}ms  "
                    f"p99={p['p99']*1000:5.0f}ms"
                )

        if detailed and 'tools' in r:
            lines.append("")
            lines.append("🔧 Tool Metrics:")
            for name, m in sorted(r['tools'].items()):
                p = m['percentiles']
                lines.append(
                    f"  {name:25s} calls={m['calls']:4d}  "
                    f"errors={m['errors']:2d}  "
                    f"avg={p['avg']*1000:6.1f}ms  "
                    f"max={p['max']*1000:6.1f}ms"
                )

        if r.get('recent_alerts'):
            lines.append("")
            lines.append("🔔 Recent Alerts:")
            for a in r['recent_alerts'][-5:]:
                lines.append(f"  [{a['severity']}] {a['category']}: {a['message']}")

        return "\n".join(lines)

    def reset(self):
        """Reset all metrics (for testing)."""
        with self._lock:
            self._request_metrics.clear()
            self._tool_metrics.clear()
            self._provider_metrics.clear()
            self._total_requests = 0
            self._total_errors = 0
            self._alerts.clear()
            self._start_time = time.monotonic()


# ---------------------------------------------------------------------------
# Timer Context Manager
# ---------------------------------------------------------------------------

class _TimerContext:
    """Context manager that records timing to a MetricsCollector."""

    def __init__(self, collector: MetricsCollector, category: str, name: str):
        self.collector = collector
        self.category = category
        self.name = name
        self.start: Optional[float] = None
        self.error = False
        self.error_msg: Optional[str] = None

    def __enter__(self):
        self.start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.monotonic() - (self.start or time.monotonic())
        if exc_type is not None:
            self.error = True
            self.error_msg = str(exc_val)[:200]

        if self.category == "request":
            self.collector.record_request(
                self.name, duration, error=self.error,
                status_code=500 if self.error else 200,
            )
        elif self.category == "tool":
            self.collector.record_tool(
                self.name, duration, error=self.error,
                error_msg=self.error_msg,
            )
        elif self.category == "provider":
            self.collector.record_provider(
                self.name, duration, error=self.error,
            )

        # Check for slow execution alert
        if duration > 10.0:  # slow threshold
            self.collector.record_alert(
                category="slow_execution",
                message=f"{self.category} '{self.name}' took {duration:.1f}s",
                severity="warning" if duration < 30 else "critical",
                value=duration,
            )


# ---------------------------------------------------------------------------
# System Resource Monitor
# ---------------------------------------------------------------------------

class SystemMonitor:
    """Monitors system resources (memory, CPU) on demand.

    Uses /proc/self/status on Linux, psutil if available, or falls back
    to basic Python-level tracking.
    """

    def get_memory_usage(self) -> dict:
        """Return current memory usage in MB."""
        mem = {"rss_mb": 0.0, "vms_mb": 0.0}

        # Try /proc/self/status (Linux)
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        mem["rss_mb"] = int(line.split()[1]) / 1024
                    elif line.startswith("VmSize:"):
                        mem["vms_mb"] = int(line.split()[1]) / 1024
        except (FileNotFoundError, IOError, ValueError):
            pass

        # Try psutil as fallback
        if not mem["rss_mb"]:
            try:
                import psutil
                process = psutil.Process()
                mem_info = process.memory_info()
                mem["rss_mb"] = mem_info.rss / (1024 * 1024)
                mem["vms_mb"] = mem_info.vms / (1024 * 1024)
            except (ImportError, Exception):
                pass

        return mem

    def get_cpu_usage(self) -> dict:
        """Return CPU usage info."""
        cpu = {"percent": 0.0, "count": 0}
        try:
            cpu["count"] = os.cpu_count() or 1

            # Try /proc/self/stat (Linux)
            try:
                with open("/proc/self/stat") as f:
                    parts = f.read().split()
                    # utime = parts[13], stime = parts[14]
                    cpu["utime"] = float(parts[13])
                    cpu["stime"] = float(parts[14])
            except (FileNotFoundError, IOError, ValueError, IndexError):
                pass

            try:
                import psutil
                cpu["percent"] = psutil.Process().cpu_percent(interval=0.1)
            except (ImportError, Exception):
                pass
        except Exception:
            pass
        return cpu


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

metrics_collector = MetricsCollector()
system_monitor = SystemMonitor()
