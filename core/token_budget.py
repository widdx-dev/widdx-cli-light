"""Token Budget Enforcer — Hard limits on token usage and cost.

Prevents runaway costs by enforcing per-session token and cost caps.

Architecture:
  TokenBudget  — track consumption, enforce limits

Pricing (per million tokens, USD):
  deepseek-v4-flash:  $0.14 input, $0.28 output
  deepseek-v4-pro:    $0.90 input, $2.70 output
  opencode-zen/free:  $0.00 (free tier)
  ollama/local:       $0.00 (local models)

Usage:
    from core.token_budget import TokenBudget

    budget = TokenBudget(max_tokens=50000, max_cost=1.00)
    budget.consume(200, 500, "deepseek-v4-flash")
    if budget.would_exceed(1000):
        raise BudgetExceededError("Token budget exceeded")
"""

from __future__ import annotations



# ---------------------------------------------------------------------------
# Pricing (USD per million tokens)
# ---------------------------------------------------------------------------

PRICING: dict[str, dict[str, float]] = {
    "deepseek-v4-flash":       {"input": 0.14, "output": 0.28},
    "deepseek-v4-flash-free":  {"input": 0.00, "output": 0.00},
    "deepseek-v4-pro":         {"input": 0.90, "output": 2.70},
    "deepseek-v4":             {"input": 0.90, "output": 2.70},
    "openai-gpt-4o-mini":      {"input": 0.15, "output": 0.60},
    "openai-gpt-4o":           {"input": 2.50, "output": 10.00},
    "opencode-zen":            {"input": 0.00, "output": 0.00},
    "ollama":                  {"input": 0.00, "output": 0.00},
    "gguf":                    {"input": 0.00, "output": 0.00},
}


# ---------------------------------------------------------------------------
# Budget Exceeded Error
# ---------------------------------------------------------------------------

class BudgetExceededError(Exception):
    pass


# ---------------------------------------------------------------------------
# Token Budget
# ---------------------------------------------------------------------------

class TokenBudget:
    """Track and enforce token/cost limits per session."""

    def __init__(
        self,
        max_tokens: int = 100_000,
        max_cost_usd: float = 2.00,
    ):
        self.max_tokens = max_tokens
        self.max_cost = max_cost_usd
        self.tokens_used = 0
        self.cost_used = 0.0
        self.calls = 0

    def consume(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
    ):
        """Record token consumption and enforce limits."""
        pricing = self._get_pricing(model)

        cost = (
            (input_tokens / 1_000_000) * pricing["input"]
            + (output_tokens / 1_000_000) * pricing["output"]
        )

        self.tokens_used += input_tokens + output_tokens
        self.cost_used += cost
        self.calls += 1

        if self.tokens_used > self.max_tokens:
            raise BudgetExceededError(
                f"Token budget exceeded: {self.tokens_used}/{self.max_tokens}"
            )
        if self.cost_used > self.max_cost:
            raise BudgetExceededError(
                f"Cost budget exceeded: ${self.cost_used:.4f}/${self.max_cost:.2f}"
            )

    def would_exceed(self, estimated_tokens: int, model: str = "") -> bool:
        """Check if adding estimated_tokens would exceed limits."""
        return (self.tokens_used + estimated_tokens) > self.max_tokens

    def remaining(self) -> tuple[int, float]:
        """Return (tokens_remaining, cost_remaining)."""
        return (
            max(0, self.max_tokens - self.tokens_used),
            max(0.0, round(self.max_cost - self.cost_used, 4)),
        )

    def reset(self):
        self.tokens_used = 0
        self.cost_used = 0.0
        self.calls = 0

    def summary(self) -> str:
        tokens_left, cost_left = self.remaining()
        return (
            f"Tokens: {self.tokens_used}/{self.max_tokens} "
            f"(${self.cost_used:.4f}) — {tokens_left} tokens, "
            f"${cost_left:.2f} remaining — {self.calls} calls"
        )

    @staticmethod
    def _get_pricing(model: str) -> dict[str, float]:
        """Find pricing for a model (fuzzy match)."""
        # Exact match
        if model in PRICING:
            return PRICING[model]

        # Prefix match
        model_lower = model.lower()
        for key, price in PRICING.items():
            if key in model_lower or model_lower.startswith(key):
                return price

        # Free tier match
        if "free" in model_lower:
            return {"input": 0.0, "output": 0.0}

        # Ollama/GGUF detection
        if any(t in model_lower for t in ("gguf", "llama", "qwen", "mistral", "phi", "gemma")):
            return {"input": 0.0, "output": 0.0}

        # Unknown model — assume conservative pricing
        return {"input": 0.50, "output": 1.00}


# ---------------------------------------------------------------------------
# Global Singleton
# ---------------------------------------------------------------------------

_budget: TokenBudget | None = None


def get_budget(max_tokens: int = 100_000, max_cost: float = 2.00) -> TokenBudget:
    global _budget
    if _budget is None:
        _budget = TokenBudget(max_tokens=max_tokens, max_cost_usd=max_cost)
    return _budget
