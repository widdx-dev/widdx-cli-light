"""WIDDX Validation Engine — actually RUNS code and CHECKS results.

Unlike the old verifier (regex + compile() only), this engine:
- Actually executes Python code and catches RUNTIME errors
- Renders HTML in headless browser and checks interactivity
- Executes bash commands and validates outputs
- Computes a quality score from multiple signals
- Generates structured validation reports

Fallback: if execution environment is unavailable, degrades to regex checks.
"""

from .runner import (
    RunResult,
    CodeRunner,
    run_code,
    get_runner,
)
from .reporter import (
    Finding,
    ValidationReport,
    ValidationReporter,
    validate_result,
    get_reporter,
)

__all__ = [
    "RunResult",
    "CodeRunner",
    "run_code",
    "get_runner",
    "Finding",
    "ValidationReport",
    "ValidationReporter",
    "validate_result",
    "get_reporter",
]
