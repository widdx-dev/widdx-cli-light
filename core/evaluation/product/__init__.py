"""Product Verification Engine — verifies final product quality."""
from .engine import (  # noqa: F401
    ProductVerificationEngine, get_product_verifier,
    GameVerifier, WebVerifier, VerificationResult,
    ProductDefect, ProductSignalType,
)
