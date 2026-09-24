"""GGUF model import — read metadata, build Modelfile, register in Ollama.

Usage:
  /gguf import <path.gguf> [--name <name>] [--context <N>] [--template <name>]
  /gguf list
  /gguf remove <name>
"""

import json
import logging
import shutil
import struct
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("widdx.gguf")


# ── GGUF constants ──────────────────────────────────────────
GGUF_MAGIC = b"GGUF"

# Metadata value types
_GGUF_TYPES = {
    0:  "uint8",   1:  "int8",     2:  "uint16",   3:  "int16",
    4:  "uint32",  5:  "int32",    6:  "float32",  7:  "bool",
    8:  "string",  9:  "array",    10: "uint64",   11: "int64",
    12: "float64",
}

# ── Known chat templates (Jinja2 for Ollama Modelfile) ─────
_CHAT_TEMPLATES = {
    "chatml": (
        '{{ if .System }}<|im_start|>system\n{{ .System }}<|im_end|>\n'
        '{{ end }}{{ if .Prompt }}<|im_start|>user\n{{ .Prompt }}<|im_end|>\n'
        '{{ end }}<|im_start|>assistant\n'
    ),
    "llama3": (
        '{{ if .System }}<|start_header_id|>system<|end_header_id|>\n\n'
        '{{ .System }}<|eot_id|>{{ end }}'
        '{{ if .Prompt }}<|start_header_id|>user<|end_header_id|>\n\n'
        '{{ .Prompt }}<|eot_id|>{{ end }}'
        '<|start_header_id|>assistant<|end_header_id|>\n\n'
    ),
    "mistral": (
        '<s>{{ if .System }}[INST] {{ .System }} [/INST]</s><s>'
        '{{ end }}{{ if .Prompt }}[INST] {{ .Prompt }} [/INST]'
        '{{ end }}'
    ),
    "deepseek": (
        '{{ if .System }}<｜begin▁of▁sentence｜>{{ .System }}\n\n'
        '{{ end }}{{ if .Prompt }}<｜User｜>{{ .Prompt }}<｜Assistant｜>'
        '{{ end }}'
    ),
    "phi3": (
        '{{ if .System }}<|system|>\n{{ .System }}<|end|>\n'
        '{{ end }}{{ if .Prompt }}<|user|>\n{{ .Prompt }}<|end|>\n'
        '{{ end }}<|assistant|>\n'
    ),
    "gemma": (
        '<bos>{{ if .System }}<start_of_turn>system\n{{ .System }}<end_of_turn>\n'
        '{{ end }}{{ if .Prompt }}<start_of_turn>user\n{{ .Prompt }}<end_of_turn>\n'
        '{{ end }}<start_of_turn>model\n'
    ),
    "zephyr": (
        '{{ if .System }}<|system|>\n{{ .System }}<|end|>\n'
        '{{ end }}{{ if .Prompt }}<|user|>\n{{ .Prompt }}<|end|>\n'
        '{{ end }}<|assistant|>\n'
    ),
}

# Template auto-detection from architecture
_ARCH_TEMPLATE_MAP = {
    "llama": "llama3",
    "mistral": "mistral",
    "gemma": "gemma",
    "gemma2": "gemma",
    "phi": "phi3",
    "phi3": "phi3",
    "phi4": "phi3",
    "qwen2": "chatml",
    "qwen2.5": "chatml",
    "deepseek": "deepseek",
    "deepseek2": "deepseek",
    "command-r": "chatml",
    "stablelm": "zephyr",
    "falcon": "chatml",
    "starcoder2": "chatml",
    "cohere": "chatml",
    "dbrx": "chatml",
    "minicpm": "chatml",
    "olmo": "chatml",
}


# ── GGUF Header Reader ─────────────────────────────────────

def _read_bytes(f, n: int) -> bytes:
    b = f.read(n)
    if len(b) < n:
        raise ValueError(f"Unexpected EOF reading GGUF: expected {n} bytes, got {len(b)}")
    return b


def _read_string(f) -> str:
    """Read a GGUF string from file stream."""
    length = struct.unpack("<Q", _read_bytes(f, 8))[0]  # uint64 length
    return _read_bytes(f, length).decode("utf-8", errors="replace")


def _read_value(f, vtype: int):
    """Read a single GGUF typed value from file stream."""
    if vtype == 0:   # uint8
        return _read_bytes(f, 1)[0]
    elif vtype == 1:  # int8
        return struct.unpack("<b", _read_bytes(f, 1))[0]
    elif vtype == 2:  # uint16
        return struct.unpack("<H", _read_bytes(f, 2))[0]
    elif vtype == 3:  # int16
        return struct.unpack("<h", _read_bytes(f, 2))[0]
    elif vtype == 4:  # uint32
        return struct.unpack("<I", _read_bytes(f, 4))[0]
    elif vtype == 5:  # int32
        return struct.unpack("<i", _read_bytes(f, 4))[0]
    elif vtype == 6:  # float32
        return struct.unpack("<f", _read_bytes(f, 4))[0]
    elif vtype == 7:  # bool
        return struct.unpack("<B", _read_bytes(f, 1))[0] != 0
    elif vtype == 8:  # string
        return _read_string(f)
    elif vtype == 9:  # array
        # Array: element_type (uint32) + count (uint64) + values
        etype = struct.unpack("<I", _read_bytes(f, 4))[0]
        count = struct.unpack("<Q", _read_bytes(f, 8))[0]
        values = []
        for _ in range(count):
            values.append(_read_value(f, etype))
        return values
    elif vtype == 10:  # uint64
        return struct.unpack("<Q", _read_bytes(f, 8))[0]
    elif vtype == 11:  # int64
        return struct.unpack("<q", _read_bytes(f, 8))[0]
    elif vtype == 12:  # float64
        return struct.unpack("<d", _read_bytes(f, 8))[0]
    else:
        raise ValueError(f"Unknown GGUF type: {vtype}")


def read_gguf_metadata(filepath: str | Path) -> dict:
    """Read GGUF header metadata sequentially without loading tensors or crashing on large data.

    Returns a dict with keys:
      - architecture, name, description, chat_template
      - context_length, embedding_length
      - file_size, header_size
      - all_metadata (raw key→value dict)
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"GGUF file not found: {filepath}")
    if path.is_dir():
        raise IsADirectoryError(
            f"'{filepath}' is a directory, not a .gguf file.\n"
            f"Please specify the full path to a .gguf file, e.g.:\n"
            f"  /gguf import {filepath}/model.Q4_K_M.gguf"
        )
    if path.suffix.lower() not in (".gguf", ".bin"):
        import warnings
        warnings.warn(f"File extension is '{path.suffix}', expected '.gguf'. Attempting anyway...")

    result: dict = {
        "architecture": "",
        "name": "",
        "description": "",
        "chat_template": "",
        "context_length": 2048,
        "embedding_length": 0,
        "file_size": path.stat().st_size,
        "header_size": 0,
        "all_metadata": {},
    }

    with open(path, "rb") as f:
        magic = _read_bytes(f, 4)
        if magic != GGUF_MAGIC:
            raise ValueError("Not a valid GGUF file (missing GGUF magic)")

        version = struct.unpack("<I", _read_bytes(f, 4))[0]
        tensor_count = struct.unpack("<Q", _read_bytes(f, 8))[0]
        meta_count = struct.unpack("<Q", _read_bytes(f, 8))[0]

        result["gguf_version"] = version
        result["tensor_count"] = tensor_count

        # Read metadata key-value pairs
        for _ in range(meta_count):
            key = _read_string(f)
            vtype = struct.unpack("<I", _read_bytes(f, 4))[0]

            # Optimization: skip large tokenizer metadata to save time and memory
            if key in (
                "tokenizer.ggml.tokens",
                "tokenizer.ggml.scores",
                "tokenizer.ggml.token_type",
                "tokenizer.ggml.merges",
            ):
                if vtype == 9:  # array
                    etype = struct.unpack("<I", _read_bytes(f, 4))[0]
                    count = struct.unpack("<Q", _read_bytes(f, 8))[0]
                    # Skip items sequentially
                    for _ in range(count):
                        _read_value(f, etype)
                    value = f"[Skipped large array of {count} items]"
                else:
                    value = _read_value(f, vtype)
            else:
                value = _read_value(f, vtype)

            result["all_metadata"][key] = value

            # Extract known useful fields
            if key == "general.architecture":
                result["architecture"] = str(value)
            elif key == "general.name":
                result["name"] = str(value)
            elif key == "general.description":
                result["description"] = str(value)[:200]
            elif key == "tokenizer.chat_template":
                result["chat_template"] = str(value)

        result["header_size"] = f.tell()

    # ── Context length from architecture-specific key ──────
    arch = result["architecture"]
    ctx_key = f"{arch}.context_length"
    if ctx_key in result["all_metadata"]:
        result["context_length"] = int(result["all_metadata"][ctx_key])

    # Embedding length
    emb_key = f"{arch}.embedding_length"
    if emb_key in result["all_metadata"]:
        result["embedding_length"] = int(result["all_metadata"][emb_key])

    return result


# ── Ollama interaction ─────────────────────────────────────

def _find_ollama() -> Optional[str]:
    """Find the ollama binary on the system."""
    ollama = shutil.which("ollama")
    if ollama:
        return ollama
    # Common Windows install paths
    for p in [
        Path.home() / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
        Path("C:/Program Files/Ollama/ollama.exe"),
    ]:
        if p.exists():
            return str(p)
    return None


def _ollama_running() -> bool:
    """Check if ollama serve is running."""
    import httpx
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def suggest_model_name(gguf_path: str | Path, metadata: dict) -> str:
    """Generate a model name from GGUF metadata or filename."""
    path = Path(gguf_path)

    # 1. From metadata
    if metadata.get("name"):
        name = metadata["name"].lower().replace(" ", "-").replace("/", "-")
        # Strip common prefixes
        for prefix in ["models--", "ggml-", "gguf-"]:
            if name.startswith(prefix):
                name = name[len(prefix):]
        return name

    # 2. From architecture + size hints
    arch = metadata.get("architecture", "")
    if arch:
        size_gb = metadata.get("file_size", 0) / (1024 ** 3)
        size_tag = f"{size_gb:.0f}b" if size_gb >= 1 else f"{int(size_gb * 1000)}m"
        return f"{arch}-{size_tag}"

    # 3. From filename
    stem = path.stem.lower()
    # Remove common suffixes
    for sfx in [".gguf", "-gguf", "-Q4", "-Q5", "-Q8", "-F16", "_q4", "_q5", "_q8"]:
        stem = stem.replace(sfx, "")
    stem = stem.replace("_", "-").replace(".", "-")
    return stem[:63]  # Ollama max name length


def suggest_template(metadata: dict) -> Optional[str]:
    """Detect the best chat template from GGUF metadata."""
    arch = metadata.get("architecture", "").lower()

    # 1. Check if GGUF contains a native chat template
    if metadata.get("chat_template"):
        return None  # Ollama will use it automatically

    # 2. Architecture-based mapping
    for key, tmpl in _ARCH_TEMPLATE_MAP.items():
        if key in arch:
            return tmpl

    return None


def build_modelfile(
    gguf_path: str | Path,
    model_name: str,
    template: Optional[str] = None,
    context_size: Optional[int] = None,
    temperature: float = 0.7,
) -> str:
    """Build a Modelfile string for Ollama import."""
    abs_path = str(Path(gguf_path).resolve())
    # On Windows, Ollama needs backslashes in the FROM path (no quotes)
    # Escape backslashes inside the Modelfile string

    lines = [f"FROM {abs_path}"]

    if template:
        tmpl = _CHAT_TEMPLATES.get(template)
        if tmpl:
            lines.append(f'TEMPLATE """{tmpl}"""')
        else:
            # Custom template string
            lines.append(f'TEMPLATE """{template}"""')

    if context_size:
        lines.append(f"PARAMETER num_ctx {context_size}")

    lines.append(f"PARAMETER temperature {temperature}")

    return "\n".join(lines) + "\n"


def import_gguf(
    gguf_path: str | Path,
    model_name: Optional[str] = None,
    template: Optional[str] = None,
    context_size: Optional[int] = None,
    temperature: float = 0.7,
) -> dict:
    """Import a GGUF file into Ollama.

    Steps:
      1. Read GGUF metadata
      2. Suggest name/template if not provided
      3. Build Modelfile
      4. Run ``ollama create``
      5. Return result with model info

    Returns:
      dict with keys: success, model_name, output, modelfile_content, metadata
    """
    # ── Prerequisites ───────────────────────────────────────
    ollama_bin = _find_ollama()
    if not ollama_bin:
        return {"success": False, "error": "ollama not found. Install from https://ollama.com"}

    if not _ollama_running():
        return {
            "success": False,
            "error": "Ollama is not running. Run: ollama serve",
        }

    # ── Read metadata ──────────────────────────────────────
    path = Path(gguf_path)
    if not path.exists():
        return {"success": False, "error": f"File not found: {gguf_path}"}

    try:
        meta = read_gguf_metadata(str(path))
    except Exception as e:
        return {"success": False, "error": f"Failed to read GGUF: {e}"}

    # ── Name / template suggestions ─────────────────────────
    if not model_name:
        model_name = suggest_model_name(path, meta)

    if template is None:
        template = suggest_template(meta)

    if not context_size:
        context_size = meta.get("context_length", 2048)
        if context_size < 512:
            context_size = 2048

    # ── Build Modelfile ────────────────────────────────────
    modelfile = build_modelfile(path, model_name, template, context_size, temperature)

    # ── Run ollama create ──────────────────────────────────
    # Write Modelfile to temp file instead of stdin — more reliable on Windows
    import tempfile as _tmp
    _mf = _tmp.NamedTemporaryFile(mode="w", suffix=".Modelfile", delete=False, encoding="utf-8")
    try:
        _mf.write(modelfile)
        _mf.close()

        proc = subprocess.run(
            [ollama_bin, "create", model_name, "-f", _mf.name],
            capture_output=True,
            text=True,
            timeout=600,  # 10 min for large models
        )
        output = proc.stdout + proc.stderr
        success = proc.returncode == 0
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Import timed out (10 minutes)"}
    except Exception as e:
        return {"success": False, "error": f"ollama create failed: {e}"}
    finally:
        try:
            Path(_mf.name).unlink(missing_ok=True)
        except Exception:
            pass

    return {
        "success": success,
        "model_name": model_name,
        "output": output.strip(),
        "modelfile": modelfile,
        "metadata": {
            "architecture": meta.get("architecture", "?"),
            "context_length": context_size,
            "file_size": meta["file_size"],
            "template_used": template or "auto-detected",
        },
        "error": "" if success else output.strip(),
    }


# ── Previously imported models tracker ─────────────────────

_IMPORT_LOG_PATH = Path.home() / ".widdx" / "gguf_imports.json"


def _load_import_log() -> list[dict]:
    if _IMPORT_LOG_PATH.exists():
        try:
            return json.loads(_IMPORT_LOG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save_import_log(log: list[dict]):
    _IMPORT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _IMPORT_LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def log_import(entry: dict):
    """Record a successful GGUF import."""
    log = _load_import_log()
    # Remove duplicate entries for same model
    log = [e for e in log if e.get("model_name") != entry.get("model_name")]
    entry["imported_at"] = time.time()
    log.append(entry)
    _save_import_log(log)


def list_imports() -> list[dict]:
    """Return previously imported GGUF models."""
    return _load_import_log()


def remove_import(model_name: str) -> dict:
    """Remove an imported GGUF model from Ollama + import log."""
    ollama_bin = _find_ollama()
    if not ollama_bin:
        return {"success": False, "error": "ollama not found"}

    # Remove from Ollama
    try:
        proc = subprocess.run(
            [ollama_bin, "rm", model_name],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        return {"success": False, "error": str(e)}

    # Remove from log
    log = _load_import_log()
    log = [e for e in log if e.get("model_name") != model_name]
    _save_import_log(log)

    return {
        "success": proc.returncode == 0,
        "output": (proc.stdout + proc.stderr).strip(),
        "model_name": model_name,
    }


# ── GGUF Discovery Scanner ─────────────────────────────────

# Common directories where GGUF files are typically stored
_SCAN_DIRS = [
    Path.home() / "Models",
    Path.home() / ".cache" / "lm-studio" / "models",
    Path.home() / ".cache" / "ollama",
    Path.home() / "Downloads",
    Path.home() / "Documents" / "Models",
    Path.home() / "Desktop",
    Path("E:/Models"),
    Path("D:/Models"),
    Path("C:/Models"),
]

_SCAN_CACHE: dict = {"files": [], "timestamp": 0}
_SCAN_CACHE_TTL = 300  # 5 minutes


def scan_gguf_files(force_refresh: bool = False) -> list[dict]:
    """Scan common directories for .gguf files.

    Returns list of dicts: {path, name, size_gb, modified}
    Cached for 5 minutes.
    """
    global _SCAN_CACHE
    now = time.time()
    if not force_refresh and _SCAN_CACHE["files"] and (now - _SCAN_CACHE["timestamp"]) < _SCAN_CACHE_TTL:
        return _SCAN_CACHE["files"]

    found: dict[str, dict] = {}
    seen_dirs: set[Path] = set()
    dirs_to_scan = list(_SCAN_DIRS)

    # Also scan current working directory
    cwd = Path.cwd().resolve()
    dirs_to_scan.insert(0, cwd)

    # Limited drive scan — only real local drives on Windows
    try:
        # C:, D:, E: are the most common — no need to scan all 26 letters
        for letter in ("C", "D", "E", "F", "G"):
            p = Path(f"{letter}:/")
            if p.exists() and p not in seen_dirs:
                seen_dirs.add(p)
                dirs_to_scan.append(p / "Models")
    except Exception:
        pass

    for scan_dir in dirs_to_scan:
        if not scan_dir.exists():
            continue
        try:
            # Limit scan depth to 3 levels to avoid deep traversal
            for i, gguf_file in enumerate(scan_dir.rglob("*.gguf")):
                try:
                    if not gguf_file.is_file() or gguf_file.stat().st_size < 100 * 1024:
                        continue
                    # Check depth — skip files deeper than 3 subdirs
                    rel = gguf_file.relative_to(scan_dir).parts
                    if len(rel) > 4:
                        continue
                    st = gguf_file.stat()
                    # Dedup by (file_name, size_in_bytes) — catches copies
                    dedup_key = f"{gguf_file.name}:{st.st_size}"
                    if dedup_key not in found:
                        found[dedup_key] = {
                            "path": str(gguf_file.resolve()),
                            "name": gguf_file.name,
                            "size_gb": st.st_size / 1e9,
                            "size_mb": st.st_size / 1e6,
                            "modified": st.st_mtime,
                        }
                except (PermissionError, OSError, ValueError):
                    continue
            # Stop after finding enough distinct models
            if len(found) >= 20:
                break
        except (PermissionError, OSError):
            continue

    result = sorted(found.values(), key=lambda x: x["size_gb"], reverse=True)
    _SCAN_CACHE = {"files": result, "timestamp": now}
    return result
