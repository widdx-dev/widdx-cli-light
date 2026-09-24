"""Tests for L4: Token Budget Enforcer (core/token_budget.py)."""
from core.token_budget import TokenBudget, BudgetExceededError, get_budget


def test_budget_creates():
    b = TokenBudget(max_tokens=1000, max_cost_usd=0.50)
    assert b.tokens_used == 0
    assert b.cost_used == 0.0


def test_budget_consume_free_model():
    b = TokenBudget(max_tokens=10000)
    b.consume(100, 200, "opencode-zen")
    assert b.tokens_used == 300
    assert b.cost_used == 0.0


def test_budget_consume_paid_model():
    b = TokenBudget(max_tokens=10000, max_cost_usd=10.0)
    b.consume(1000, 500, "deepseek-v4-flash")
    assert b.tokens_used == 1500
    assert b.cost_used > 0


def test_budget_would_exceed():
    b = TokenBudget(max_tokens=1000)
    b.consume(500, 0, "opencode-zen")
    assert b.would_exceed(600)
    assert not b.would_exceed(400)


def test_budget_exceeded_raises():
    b = TokenBudget(max_tokens=100)
    try:
        b.consume(200, 0, "opencode-zen")
        assert False, "Should have raised"
    except BudgetExceededError:
        pass


def test_budget_remaining():
    b = TokenBudget(max_tokens=1000, max_cost_usd=1.00)
    b.consume(100, 0, "opencode-zen")
    tokens_left, cost_left = b.remaining()
    assert tokens_left == 900
    assert cost_left == 1.00


def test_budget_summary():
    b = TokenBudget(max_tokens=500)
    b.consume(100, 0, "opencode-zen")
    s = b.summary()
    assert "100/500" in s


def test_get_pricing_known():
    price = TokenBudget._get_pricing("deepseek-v4-flash-free")
    assert price["input"] == 0.0


def test_get_pricing_unknown():
    price = TokenBudget._get_pricing("unknown-model-xyz")
    assert price["input"] > 0  # conservative default


def test_singleton_budget():
    b = get_budget(max_tokens=5000)
    assert b is not None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  ✅ {name}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")
    print("Done.")
