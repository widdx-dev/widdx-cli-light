---
name: generate-tests
description: Generate comprehensive unit, integration, and edge-case tests for any codebase
icon: 🧪
---

# Test Generation Skill

You write tests that actually catch bugs — not tests that just increase coverage numbers.

## Process

### 1. Analyze the Target
- Read the source file completely
- Identify all public functions/methods/classes
- Note parameter types, return types, and exceptions raised
- Check for existing tests in the project to match conventions
- Detect the testing framework (pytest, unittest, jest, mocha, etc.)

### 2. Plan Test Coverage

For each function, write tests for:

| Category | What to Test | Example |
|----------|-------------|---------|
| **Happy path** | Normal input → expected output | `add(2, 3) == 5` |
| **Empty/null** | None, "", [], {}, 0 | `add(None, 3)` raises TypeError |
| **Boundaries** | Min/max values, off-by-one | `fib(0)`, `fib(1)`, `fib(100)` |
| **Invalid types** | Wrong type passed | `add("a", 3)` raises TypeError |
| **Large input** | Very large values, long strings | `sort(list(range(10000)))` |
| **Unicode** | Non-ASCII characters | `validate("José")` |
| **Concurrency** | Race conditions, parallel access | Thread safety tests |
| **Time** | Timezone, DST, leap years | `format_date(2024-02-29)` |
| **Error paths** | Exceptions raised, error handling | `read_file("/nonexistent")` |
| **Side effects** | File writes, DB changes, network calls | Mock external dependencies |
| **State** | Object state before/after calls | `stack.push(1); stack.pop() == 1` |

### 3. Match Project Conventions
- Same directory structure (`tests/` or `__tests__/`)
- Same file naming (`test_*.py`, `*.test.js`, `*_test.go`)
- Same test function naming (`test_*`, `should_*`, `it("*")`)
- Same assertion style (assert, expect, should)
- Same mocking library (unittest.mock, pytest-mock, jest.mock, sinon)

### 4. Write Clean Tests
```python
# ✅ GOOD: Clear, isolated, descriptive
def test_transfer_insufficient_funds_raises_error():
    account = Account(balance=100)
    with pytest.raises(InsufficientFundsError):
        account.transfer(200, "recipient")

# ❌ BAD: Vague, dependent on other tests
def test_case_1():
    global account
    account.transfer(200)
    assert account.balance == -100
```

### 5. Test File Structure
```python
"""Tests for the payment module — covers transfers, validation, and edge cases."""
import pytest
from app.payment import transfer, validate_amount

class TestTransfer:
    """Transfer functionality tests."""

    def test_basic_transfer_succeeds(self):
        ...

    def test_negative_amount_raises_error(self):
        ...

    def test_zero_amount_is_valid(self):
        ...

class TestValidateAmount:
    """Amount validation tests."""

    def test_valid_amount_passes(self):
        ...

    def test_amount_over_max_raises_error(self):
        ...

    def test_amount_with_decimals_is_valid(self):
        ...
```

### 6. Mock External Dependencies
```python
from unittest.mock import Mock, patch

def test_send_email_calls_smtp():
    with patch("smtplib.SMTP") as mock_smtp:
        send_email("user@example.com", "Subject", "Body")
        mock_smtp.return_value.sendmail.assert_called_once()

def test_fetch_user_handles_api_error():
    with patch("requests.get") as mock_get:
        mock_get.side_effect = requests.Timeout()
        result = fetch_user(42)
        assert result is None  # graceful degradation
```

## Rules
- **DO NOT run tests** unless explicitly asked
- **Match existing patterns** — don't introduce new frameworks
- **One assertion concept per test** — don't test multiple things
- **Test behavior, not implementation** — test what it does, not how
- **Include imports** — every test file must be runnable independently
- **Add docstrings** — every test class and complex test function
