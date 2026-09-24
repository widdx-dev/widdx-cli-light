"""Cron Scheduler for WIDDX — automatic task scheduling.

User writes a natural-language schedule request, and the system handles
everything: parsing, persistence, background execution, and delivery.
"""

# Lazy imports — each submodule loads on first use
# This prevents ImportError when only job.py is needed
