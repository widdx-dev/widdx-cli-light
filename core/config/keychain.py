"""Secure API key management using session-scoped environment variables.

Keys are:
- Stored in os.environ for the current process
- Persisted to .widdx/apikeys.json (AES-128-CBC + HMAC via Fernet) for survival across restarts
- Input via getpass (hidden typing) for security
- NEVER stored in config.json (shared/public)
"""

import os
import json
import getpass
import base64
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from cryptography.fernet import Fernet

logger = logging.getLogger("widdx.keychain")

# Prefix for all environment variables we set
_ENV_PREFIX = "WIDDX_API_KEY_"

# Providers that need API keys — loaded from config first, then fallback
_KEY_PROVIDERS: dict[str, str] = {}

# Persistence file (in .gitignore via .widdx/*)
def _key_file() -> Path:
    """Get path to persisted API keys file — ALWAYS in package root, never in CWD.

    The API key stays in the main project folder and does NOT follow
    the user to other directories. Uses the install location of this file.
    """
    # Use the directory where this module is installed (package root)
    pkg_dir = Path(__file__).resolve().parent.parent.parent  # core/config/ → root
    widdx_dir = pkg_dir / ".widdx"
    widdx_dir.mkdir(exist_ok=True)
    return widdx_dir / "apikeys.json"


_LEGACY_XOR_KEY = b"WIDDX_NEXUS_KEY_2026"


def _xor_obfuscate(text: str) -> str:
    """Legacy XOR obfuscation — kept ONLY to read/migrate pre-existing files."""
    data = text.encode("utf-8")
    result = bytes(data[i] ^ _LEGACY_XOR_KEY[i % len(_LEGACY_XOR_KEY)] for i in range(len(data)))
    return base64.b64encode(result).decode("ascii")


def _xor_deobfuscate(encoded: str) -> str:
    """Reverse _xor_obfuscate (legacy migration path only)."""
    data = base64.b64decode(encoded.encode("ascii"))
    result = bytes(data[i] ^ _LEGACY_XOR_KEY[i % len(_LEGACY_XOR_KEY)] for i in range(len(data)))
    return result.decode("utf-8")


def _fernet_key() -> "Fernet":
    """Load (or generate) the Fernet key used for authenticated encryption.

    The key is a random 256-bit key stored in ``.widdx/.fernet_key`` with
    owner-only permissions. It is never hardcoded, so reading the source
    provides no way to decrypt stored API keys.
    """
    from cryptography.fernet import Fernet

    key_path = _key_file().parent / ".fernet_key"
    if key_path.exists():
        return Fernet(key_path.read_bytes())
    key = Fernet.generate_key()
    key_path.write_bytes(key)
    try:
        key_path.chmod(0o600)
    except OSError:
        pass  # chmod is a no-op / unsupported on some filesystems
    return Fernet(key)


def _encrypt(text: str) -> str:
    """Encrypt with AES-128-CBC + HMAC (Fernet). Output is urlsafe base64."""
    token = _fernet_key().encrypt(text.encode("utf-8"))
    return "v2:" + token.decode("ascii")


def _decrypt(encoded: str) -> str:
    """Decrypt a stored value.

    Supports the current ``v2:`` Fernet format and the legacy XOR format
    (transparently migrated on read).
    """
    if encoded.startswith("v2:"):
        try:
            return _fernet_key().decrypt(encoded[3:].encode("ascii")).decode("utf-8")
        except Exception as enc_e:
            logger.debug("Fernet decrypt failed, trying legacy XOR: %s", enc_e)
    return _xor_deobfuscate(encoded)


def _load_persisted_keys() -> dict[str, str]:
    """Load persisted API keys from disk."""
    kf = _key_file()
    if not kf.exists():
        return {}
    try:
        with open(kf, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {k: _decrypt(v) for k, v in data.items()}
    except Exception:
        return {}


def _save_persisted_keys(keys: dict[str, str]) -> None:
    """Save API keys to disk (Fernet-encrypted)."""
    kf = _key_file()
    kf.parent.mkdir(parents=True, exist_ok=True)
    encrypted = {k: _encrypt(v) for k, v in keys.items() if v}
    with open(kf, "w", encoding="utf-8") as f:
        json.dump(encrypted, f)
    # Restrict file permissions — owner read/write only
    try:
        kf.chmod(0o600)
    except OSError:
        pass  # chmod unsupported on some filesystems (e.g. Windows)


def _get_providers() -> dict[str, str]:
    """Lazy-load provider list from config on first access."""
    if not _KEY_PROVIDERS:
        try:
            from .settings import load as _load_cfg
            cfg = _load_cfg()
            p = cfg.get("provider", {})
            name = p.get("name", "")
            if name:
                _KEY_PROVIDERS[name] = name.upper().replace("-", "_")
                _KEY_PROVIDERS[name.replace("-zen", "")] = name.upper().replace("-", "_")
        except Exception:
            pass
        # Fallback defaults
        if not _KEY_PROVIDERS:
            _KEY_PROVIDERS.update({
                "deepseek": "DEEPSEEK",
                "openai": "OPENAI",
                "atria": "ATRIA",
                "opencode-zen": "OPENCODE_ZEN",
                "opencode": "OPENCODE_ZEN",
            })
    return _KEY_PROVIDERS


def _env_name(provider_name: str) -> str:
    """Convert a provider name to its canonical env-var name."""
    providers = _get_providers()
    key = providers.get(provider_name, provider_name.upper())
    return f"{_ENV_PREFIX}{key}"


# Providers whose users commonly set the variable with spaces instead of an
# underscore (e.g. Windows "set ATRIA API KEY=..."). Checked in addition to the
# canonical <PROVIDER>_API_KEY form.
_ENV_ALIASES: dict[str, tuple[str, ...]] = {
    "atria": ("ATRIA API KEY", "ATRIA_API_KEY"),
}


def _env_candidates(provider_name: str) -> tuple[str, ...]:
    """Environment variable names to probe for a provider, most specific first."""
    providers = _get_providers()
    canonical = providers.get(provider_name, provider_name.upper())
    names = [_ENV_PREFIX + canonical, canonical + "_API_KEY"]
    names.extend(_ENV_ALIASES.get(provider_name, ()))
    # de-duplicate, preserve order
    seen: set[str] = set()
    ordered: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            ordered.append(n)
    return tuple(ordered)


def get_key(provider_name: str) -> Optional[str]:
    """Retrieve an API key.

    Checks (in order):
      1. WIDDX_API_KEY_<PROVIDER> (set by set_key during this session)
      2. <PROVIDER>_API_KEY (e.g. DEEPSEEK_API_KEY — pre-existing env var)
      3. Provider-specific aliases (e.g. the spaced "ATRIA API KEY" form)
      4. Persisted .widdx/apikeys.json (survives restarts)
      5. WIDDX_API_KEY (fallback generic key)

    Returns None if no key is found.
    """
    # 1. Session key set via set_key()
    session_var = _env_name(provider_name)
    val = os.environ.get(session_var)
    if val:
        return val

    # 2. Pre-existing provider env vars, including spaced aliases
    for candidate in _env_candidates(provider_name)[1:]:
        val = os.environ.get(candidate)
        if val:
            return val

    # 3. Persisted key file (survives restarts)
    persisted = _load_persisted_keys()
    val = persisted.get(provider_name)
    if val:
        # Load into session env for faster access next time
        os.environ[session_var] = val
        return val

    # 4. Generic fallback
    val = os.environ.get("WIDDX_API_KEY")
    return val


def set_key(provider_name: str, api_key: str) -> None:
    """Store an API key in the session AND persist to disk.

    The key is set in os.environ for the current process
    AND saved to .widdx/apikeys.json (Fernet-encrypted) to survive restarts.
    NEVER written to config.json.
    """
    # Session (immediate)
    os.environ[_env_name(provider_name)] = api_key
    # Persist to disk (encrypted)
    persisted = _load_persisted_keys()
    persisted[provider_name] = api_key
    _save_persisted_keys(persisted)


def has_key(provider_name: str) -> bool:
    """Check if a key exists for the given provider (checks env + persisted)."""
    return get_key(provider_name) is not None


def prompt_key(provider_name: str, message: Optional[str] = None) -> str:
    """Prompt the user to enter an API key with hidden input.

    Uses getpass so the typed key is NOT shown on screen.
    Automatically stores the key in session + persisted.
    Returns the key.
    """
    if message is None:
        message = f"\U0001f511 Enter {provider_name.title()} API Key"
    key = getpass.getpass(f"{message}: ").strip()
    if key:
        set_key(provider_name, key)
    return key


def forget_key(provider_name: str) -> None:
    """Remove a key from session AND persisted storage."""
    var = _env_name(provider_name)
    os.environ.pop(var, None)
    persisted = _load_persisted_keys()
    if provider_name in persisted:
        del persisted[provider_name]
        _save_persisted_keys(persisted)


def list_providers_with_keys() -> list[str]:
    """Return names of providers that have keys set."""
    providers = _get_providers()
    return [p for p in providers if has_key(p)]


def sanitized_environ() -> dict[str, str]:
    """Return the current environment with WIDDX API keys stripped.

    Use this when spawning subprocesses to prevent leaking
    API keys to child processes (e.g. bash commands).
    """
    clean = dict(os.environ)
    keys_to_remove = [k for k in clean if k.startswith(_ENV_PREFIX)]
    for k in keys_to_remove:
        del clean[k]
    return clean
