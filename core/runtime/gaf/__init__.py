"""Global Arbitration Function — evidence-weighted unified decision kernel.

ECP = Router
GAF = Brain
Subsystems = Evidence Sources

Every decision is the result of argmax(Σ weight × confidence × utility)
across all evidence providers. No hidden logic, no priority hacks.
"""

from .types import (
    Evidence,
    EvidenceDirection,
    GAFDecision,
    EvidenceProvider,
)
from .aggregator import (
    GAF,
    get_gaf,
)

__all__ = [
    "Evidence",
    "EvidenceDirection",
    "GAFDecision",
    "EvidenceProvider",
    "GAF",
    "get_gaf",
]
