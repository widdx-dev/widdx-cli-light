# Contributing to WIDDX Nexus

## Quick Start

```bash
git clone https://github.com/widdx1990/widdx-cli-light
cd widdx-cli-light
pip install -e ".[dev,api]"
pre-commit install
```

## Development

```bash
# Run tests
python -m pytest tests/ -q

# Run tests with coverage
python -m pytest tests/ --cov=core --cov-report=term

# Lint all source code
ruff check core/ cli/ tui/ scripts/

# Type check
mypy core/ --ignore-missing-imports --check-untyped-defs

# Start Web UI
widdx-web

# Run CLI
widdx

# Run TUI
widdx-tui

# Run API server
widdx-api
```

## Makefile Targets

```bash
make help          # Show all targets
make install-dev   # Install + dev + api deps
make test          # Run tests (quick)
make test-v        # Run tests (verbose)
make test-cov      # Run tests with coverage report
make lint          # Ruff check core/ cli/ tui/ scripts/
make lint-fix      # Ruff check + auto-fix
make typecheck     # Mypy type checking
make build         # Build pip package
make clean         # Remove caches and build artifacts
```

## Architecture

See `docs/architecture/` for complete documentation.

## Environment Setup

1. Optionally set API keys via environment variables:
   - `DEEPSEEK_API_KEY`
   - `OPENAI_API_KEY`

2. Configure `config.json` or `~/.widdx/config.json`:
   ```json
   {
     "provider": {
       "name": "opencode-zen",
       "model": "deepseek-v4-flash-free"
     }
   }
   ```

## Build Rules

1. **No breakage**: All tests must pass (`make test`)
2. **Reuse existing**: Before creating new modules, check existing ones
3. **Clean code**: Type hints, docstrings, no bare except
4. **Test everything**: Every new capability gets a test
5. **Backend first**: core/ -> scripts/web/ -> static/js/

## Adding a Provider

1. Create `core/providers/myprovider.py` extending `Provider`
2. Implement `chat(messages, tool_defs, temperature) -> tuple[str, list]`
3. Add to `factory.py` -> `create_provider()`
4. Add to `settings.py` -> `_VALID_PROVIDERS`
5. Test: `python -m pytest tests/test_providers.py`

## Adding a Skill

1. Create a directory under `skills/` with your skill name
2. Add a `skill.md` file with the skill instructions
3. Optionally add a `skill.py` for Python tool extensions
4. The skill is auto-loaded by the plugin loader

## Commit Convention

- `Fix:` — Bug fixes
- `Feat:` — New features
- `Docs:` — Documentation
- `Perf:` — Performance improvements
- `Refactor:` — Code restructuring
- `Test:` — Tests
- `Chore:` — Build/tooling changes

Example: `Fix(core): handle empty response from provider`
