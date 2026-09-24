"""Configuration loader / saver — JSON config file with automatic secret stripping.

Resolution order (first found wins):
  1. .widdx/config.json    (project-local, in CWD)
  2. config.json            (bare in CWD)
  3. ~/.widdx/config.json   (global user config — survives across all projects)
  4. <install>/config.json  (bundled default — read-only)
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("widdx.config")

_INSTALL_DIR = Path(__file__).resolve().parent.parent.parent
_USER_CONFIG_DIR = Path.home() / ".widdx"

_VALID_PROVIDERS = {"ollama", "gguf", "opencode-zen", "opencode", "deepseek", "openai-compatible", "openai"}


def validate_config(cfg: dict) -> dict:
    """Validate config fields, apply defaults, warn on issues.
    Returns a cleaned copy of the config.
    """
    validated = dict(cfg)
    issues = []

    # ── provider ───────────────────────────────────────────
    provider = validated.get("provider")
    if not isinstance(provider, dict):
        issues.append("'provider' is missing or not an object — using defaults")
        provider = {"name": "opencode", "model": "opencode/mimo-v2.5-free"}
        validated["provider"] = provider

    pname = provider.get("name", "")
    if not isinstance(pname, str) or not pname:
        issues.append("'provider.name' is missing or empty — defaulting to 'opencode-zen'")
        provider["name"] = "opencode-zen"
    elif pname not in _VALID_PROVIDERS:
        issues.append(f"'provider.name' = '{pname}' is not a known provider ({', '.join(sorted(_VALID_PROVIDERS))}) — will be treated as OpenAI-compatible")

    pmodel = provider.get("model", "")
    if not isinstance(pmodel, str) or not pmodel:
        issues.append("'provider.model' is missing or empty — will be auto-resolved")
        provider["model"] = ""

    if "base_url" in provider and (not isinstance(provider["base_url"], str) or not provider["base_url"]):
        issues.append("'provider.base_url' must be a non-empty string — removing")
        del provider["base_url"]

    # ── system_prompt is hardcoded in core/constants.py — ignored from config
    validated.pop("system_prompt", None)

    # ── max_turns ──────────────────────────────────────────
    mt = validated.get("max_turns", 10)
    if not isinstance(mt, int) or mt < 1:
        issues.append(f"'max_turns' = {mt!r} is invalid — defaulting to 10")
        mt = 10
    validated["max_turns"] = mt

    # ── temperature ────────────────────────────────────────
    temp = validated.get("temperature", 0.7)
    if not isinstance(temp, (int, float)) or temp < 0 or temp > 2:
        issues.append(f"'temperature' = {temp!r} is invalid (must be 0–2) — defaulting to 0.7")
        temp = 0.7
    validated["temperature"] = temp

    # ── mcp_servers ────────────────────────────────────────
    mcp = validated.get("mcp_servers", [])
    if not isinstance(mcp, list):
        issues.append("'mcp_servers' must be a list — ignoring")
        validated["mcp_servers"] = []
    else:
        clean = []
        for i, s in enumerate(mcp):
            if not isinstance(s, dict):
                issues.append(f"'mcp_servers[{i}]' is not an object — skipping")
                continue
            sname = s.get("name", "")
            scmd = s.get("command", "")
            if not isinstance(sname, str) or not sname:
                issues.append(f"'mcp_servers[{i}]' missing 'name' — skipping")
                continue
            if not isinstance(scmd, str) or not scmd:
                issues.append(f"'mcp_servers[{i}].name={sname}' missing 'command' — skipping")
                continue
            sargs = s.get("args", [])
            if not isinstance(sargs, list):
                issues.append(f"'mcp_servers[{i}].name={sname}' 'args' must be a list — treating as empty")
                sargs = []
            clean.append({"name": sname, "command": scmd, "args": sargs})
        validated["mcp_servers"] = clean

    for issue in issues:
        logger.warning("Config validation: %s", issue)

    return validated


def _find_config() -> tuple[Path, bool]:
    """Find the first existing config file.

    Returns (path, is_writable).
    The bundled config at install location is read-only.
    """
    cwd = Path.cwd().resolve()

    # 1. Project-local config (.widdx/)
    local = cwd / ".widdx" / "config.json"
    if local.exists():
        return local, True

    # 2. Bare config.json in CWD
    bare = cwd / "config.json"
    if bare.exists():
        return bare, True

    # 3. Global user config (~/.widdx/config.json)
    global_config = _USER_CONFIG_DIR / "config.json"
    if global_config.exists():
        return global_config, True

    # 4. Bundled default (read-only — copy to CWD to modify)
    bundled = _INSTALL_DIR / "config.json"
    if bundled.exists():
        return bundled, False

    # No config exists yet — create global user config
    _USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return global_config, True


def _resolve_placeholders(cfg: dict) -> dict:
    """Replace {PROJECT_ROOT}, {USER_HOME}, and {CWD} placeholders.

    {PROJECT_ROOT} now resolves to CWD (the user's working directory),
    NOT the install directory. This makes MCP server paths etc. work
    even when the tool is installed via pip.
    """
    project_root = os.getcwd().replace("\\", "/")
    user_home = os.environ.get("USERPROFILE", "").replace("\\", "/") or os.environ.get("HOME", "")
    cwd = project_root  # same as PROJECT_ROOT

    def _walk(val):
        if isinstance(val, str):
            return (val.replace("{PROJECT_ROOT}", project_root)
                       .replace("{USER_HOME}", user_home)
                       .replace("{CWD}", cwd))
        elif isinstance(val, dict):
            return {k: _walk(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [_walk(v) for v in val]
        return val
    return _walk(cfg)


# ── Module-level cache ──────────────────────────────
_config_path: Path | None = None
_config_writable: bool = False


def _get_config_path() -> tuple[Path, bool]:
    """Cached lookup of config path."""
    global _config_path, _config_writable
    if _config_path is None:
        _config_path, _config_writable = _find_config()
    return _config_path, _config_writable


def load() -> dict:
    path, _ = _get_config_path()
    if path.exists():
        cfg = json.loads(path.read_text(encoding="utf-8"))
        cfg = _resolve_placeholders(cfg)
        cfg = validate_config(cfg)
        return cfg
    return validate_config({})


def get(key: str, default=None):
    return load().get(key, default)


def get_config_path() -> Path:
    """Return the path to the active config file."""
    path, _ = _get_config_path()
    return path


def _strip_secrets(cfg: dict) -> dict:
    """Remove sensitive fields before persisting to disk."""
    safe = json.loads(json.dumps(cfg))
    provider = safe.get("provider", {})
    if "api_key" in provider:
        del provider["api_key"]
    return safe


def save(cfg: dict) -> None:
    """Save config to a writable location.

    Writes to CWD/.widdx/config.json if the current config is
    the bundled read-only default. Otherwise writes in-place.
    """
    path, writable = _get_config_path()
    if not writable:
        # Bundled default → copy to project-local location
        path = Path.cwd().resolve() / ".widdx" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        # Update cache
        global _config_path, _config_writable
        _config_path = path
        _config_writable = True

    safe = _strip_secrets(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
