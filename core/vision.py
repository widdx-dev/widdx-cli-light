"""
WIDDX Vision Module — Multi-Modal Image Understanding
=====================================================

Three modes as selected by the user:

  A) Ollama Vision     — deepseek-vl2 / llava / qwen-vl via Ollama (local)
  C) Two-Stage Pipeline — small local vision model → text → AI reasoning
  D) DeepSeek Vision API — native API vision endpoint (new)

Usage:
    from core.vision import describe_image, VisionMode

    # Describe an image
    result = describe_image("path/to/photo.jpg", mode=VisionMode.PIPELINE)
    print(result.description)   # "A wooden desk with a laptop, coffee mug..."

Configuration:
    /vision mode pipeline|ollama|deepseek
    /vision model <model_name>
"""

import os
import base64
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger("widdx.vision")

# ── Output ───────────────────────────────────────────────────
@dataclass
class VisionResult:
    description: str
    mode: str
    model: str
    success: bool
    error: Optional[str] = None


# ── Modes ────────────────────────────────────────────────────
class VisionMode:
    PIPELINE = "pipeline"      # Two-Stage Pipeline (local model)
    OLLAMA = "ollama"          # Ollama vision model
    DEEPSEEK = "deepseek"      # DeepSeek native vision API


# ── Global config (set via /vision command) ───────────────────
_vision_config: dict[str, Any] = {
    "mode": VisionMode.PIPELINE,
    "ollama_model": "llava:7b",       # أو deepseek-vl2, qwen-vl
    "ollama_url": "http://localhost:11434",
    "deepseek_model": "deepseek-vl2",
    "pipeline_model": "Salesforce/blip-image-captioning-base",  # HuggingFace model (موثوق)
    "enabled": True,
}


# ═══════════════════════════════════════════════════════════════
# A) Ollama Vision — Direct Vision Model
# ═══════════════════════════════════════════════════════════════

def _ollama_describe(image_path: str) -> VisionResult:
    """Send image to Ollama vision model (deepseek-vl2 / llava / etc).

    Uses the Ollama API directly:
      POST /api/generate  {model, prompt, images: [base64]}
    """
    import httpx

    model = _vision_config["ollama_model"]
    url = f"{_vision_config['ollama_url']}/api/generate"

    # Read and encode image
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        return VisionResult("", VisionMode.OLLAMA, model, False, f"ملف غير موجود: {image_path}")

    payload = {
        "model": model,
        "prompt": "قم بوصف هذه الصورة بالتفصيل باللغة العربية. صف كل ما تراه فيها.",
        "images": [img_b64],
        "stream": False,
    }

    try:
        resp = httpx.post(url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        description = data.get("response", "").strip()
        if not description:
            description = "(لم يتم إرجاع وصف)"
        return VisionResult(description, VisionMode.OLLAMA, model, True)
    except httpx.ConnectError:
        return VisionResult("", VisionMode.OLLAMA, model, False,
                            f"لا يمكن الاتصال بـ Ollama على {_vision_config['ollama_url']}\n"
                            f"شغّل: ollama serve")
    except Exception as e:
        return VisionResult("", VisionMode.OLLAMA, model, False, str(e))


# ═══════════════════════════════════════════════════════════════
# C) Two-Stage Pipeline — Local Vision Model via HuggingFace
# ═══════════════════════════════════════════════════════════════

# Cache for the loaded model (load once)
_pipeline_model: Any = None
_pipeline_processor: Any = None


def _load_pipeline_model():
    """Load the HuggingFace vision model lazily.

    Supports: BLIP, BLIP-2, Florence-2, and standard image captioning models.
    """
    global _pipeline_model, _pipeline_processor

    if _pipeline_model is not None:
        return True

    model_name = _vision_config["pipeline_model"]

    try:
        from transformers import AutoProcessor, BlipForConditionalGeneration
        import torch
    except ImportError:
        logger.warning("HuggingFace Transformers غير مثبت. جارِ التثبيت...")
        import subprocess
        import sys
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "transformers", "torch", "accelerate", "-q"],
                timeout=600,
            )
            from transformers import AutoProcessor, BlipForConditionalGeneration
            import torch
        except Exception as e:
            logger.error(f"فشل تثبيت المكتبات: {e}")
            return False

    try:
        logger.info(f"جارِ تحميل نموذج الرؤية: {model_name}")
        _pipeline_processor = AutoProcessor.from_pretrained(model_name)
        _pipeline_model = BlipForConditionalGeneration.from_pretrained(
            model_name
        )
        if torch.cuda.is_available():
            _pipeline_model = _pipeline_model.cuda()
        logger.info(f"✅ نموذج الرؤية {model_name} جاهز")
        return True
    except Exception as e:
        logger.error(f"فشل تحميل النموذج {model_name}: {e}")

        # Try general AutoModel approach
        try:
            from transformers import AutoModelForCausalLM, AutoProcessor
            _pipeline_processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
            _pipeline_model = AutoModelForCausalLM.from_pretrained(
                model_name, trust_remote_code=True
            )
            if torch.cuda.is_available():
                _pipeline_model = _pipeline_model.cuda()
            logger.info(f"✅ {model_name} (AutoModel) جاهز")
            return True
        except Exception as e2:
            logger.error(f"فشل أيضاً: {e2}")
            return False


def _pipeline_describe(image_path: str) -> VisionResult:
    """Two-Stage Pipeline: local vision model → text description.

    Uses HuggingFace BLIP or similar to generate a detailed caption,
    which can then be fed to DeepSeek for reasoning.
    """
    model_name = _vision_config["pipeline_model"]

    if not _load_pipeline_model():
        # Fallback: basic image analysis without ML
        return _fallback_describe(image_path)

    try:
        from PIL import Image
        import torch

        image = Image.open(image_path).convert("RGB")

        # Try BLIP-style (standard)
        try:
            inputs = _pipeline_processor(images=image, return_tensors="pt")
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            generated_ids = _pipeline_model.generate(**inputs, max_new_tokens=100)

            description = _pipeline_processor.decode(
                generated_ids[0], skip_special_tokens=True
            ).strip()
        except Exception:
            # Fallback: Florence-2 style (with text prompt)
            try:
                inputs = _pipeline_processor(
                    text="<CAPTION>",
                    images=image,
                    return_tensors="pt",
                )
                if torch.cuda.is_available():
                    inputs = {k: v.cuda() for k, v in inputs.items()}

                generated_ids = _pipeline_model.generate(
                    **inputs, max_new_tokens=200, num_beams=3
                )
                description = _pipeline_processor.batch_decode(
                    generated_ids, skip_special_tokens=True
                )[0]
                description = description.replace("<CAPTION>", "").strip()
            except Exception:
                description = None

        if not description:
            return _fallback_describe(image_path)

        return VisionResult(description, VisionMode.PIPELINE, model_name, True)

    except Exception as e:
        return VisionResult("", VisionMode.PIPELINE, model_name, False, str(e))


def _fallback_describe(image_path: str) -> VisionResult:
    """Fallback: use basic image analysis when no vision model is available.

    Extracts: dimensions, colors, brightness, file type, size.
    This is much weaker than a real vision model but works without any ML deps.
    """
    try:
        from PIL import Image

        img = Image.open(image_path)
        w, h = img.size
        fmt = img.format or "Unknown"
        fsize = os.path.getsize(image_path)

        # Edge detection (if OpenCV available)
        has_cv2 = True
        try:
            import cv2
            cv_img = cv2.imread(image_path)
            if cv_img is not None:
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
            else:
                pass
        except Exception:
            has_cv2 = False

        # Face detection (if OpenCV)
        face_count = 0
        if has_cv2 and cv_img is not None:
            try:
                cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                )
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(40, 40))
                face_count = len(faces)
            except Exception:
                logger.debug("Exception suppressed (line 268)")

        # Build description
        parts = [
            f"هذه الصورة بأبعاد {w}×{h} بكسل",
            f"بحجم {fsize/1024:.0f} كيلوبايت",
            f"صيغة {fmt}",
        ]
        if face_count > 0:
            parts.append(f"تحتوي على {face_count} وجه (وجوه)")
        else:
            parts.append("لا تحتوي على وجوه بشرية")

        desc = " | ".join(parts) + "."

        return VisionResult(desc, VisionMode.PIPELINE + "_fallback", "basic_analysis", True)

    except Exception as e:
        return VisionResult("", VisionMode.PIPELINE, "basic_analysis", False, str(e))


# ═══════════════════════════════════════════════════════════════
# D) DeepSeek Vision API — Official Vision Endpoint
# ═══════════════════════════════════════════════════════════════

def _deepseek_vision_describe(image_path: str) -> VisionResult:
    """Use DeepSeek's native vision API (new vision mode).

    Endpoint: POST https://api.deepseek.com/chat/completions
    Uses the vision-capable model ID with image_url content type.

    Note: As of May 2026, DeepSeek is rolling out native vision.
    This may require a specific model ID or header.
    """
    from core.config.keychain import get_key

    model = _vision_config["deepseek_model"]
    api_key = get_key("deepseek")

    if not api_key:
        return VisionResult("", VisionMode.DEEPSEEK, model, False,
                            "مفتاح DeepSeek API غير موجود. استخدم /apikey deepseek")

    # Read and encode image
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
    except FileNotFoundError:
        return VisionResult("", VisionMode.DEEPSEEK, model, False, f"ملف غير موجود: {image_path}")

    # Detect image MIME type
    ext = Path(image_path).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".webp": "image/webp", ".bmp": "image/bmp"}
    mime = mime_map.get(ext, "image/jpeg")

    # Try different vision API endpoints and model IDs
    endpoints: list[dict[str, Any]] = [
        # Primary: standard chat with vision model
        {"url": "https://api.deepseek.com/chat/completions",
         "model": "deepseek-vl2",
         "headers": {"X-DeepSeek-Mode": "vision"}},
        # Fallback: standard completion
        {"url": "https://api.deepseek.com/chat/completions",
         "model": "deepseek-chat",
         "headers": {}},
    ]

    import httpx

    last_error = ""
    for ep in endpoints:
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                **ep["headers"],
            }

            payload = {
                "model": ep["model"],
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "قم بوصف هذه الصورة بالتفصيل باللغة العربية. ماذا ترى فيها؟"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime};base64,{img_b64}"
                                },
                            },
                        ],
                    }
                ],
                "max_tokens": 1024,
                "temperature": 0.3,
            }

            resp = httpx.post(ep["url"], json=payload, headers=headers, timeout=120)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if content:
                    return VisionResult(content.strip(), VisionMode.DEEPSEEK, ep["model"], True)
                else:
                    return VisionResult("(استجابة فارغة)", VisionMode.DEEPSEEK, ep["model"], True,
                                        "النموذج استجاب بدون محتوى")
            else:
                last_error = f"{resp.status_code}: {resp.text[:200]}"

        except httpx.ConnectError:
            last_error = f"لا يمكن الاتصال بـ {ep['url']}"
        except Exception as e:
            last_error = str(e)

    return VisionResult("", VisionMode.DEEPSEEK, model, False, last_error)


# ═══════════════════════════════════════════════════════════════
# Image Validation
# ═══════════════════════════════════════════════════════════════

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

def _is_image_path(text: str) -> Optional[str]:
    """Check if text looks like an image file path.

    Returns the resolved path if valid, None otherwise.
    Supports: absolute paths, ~/ paths, and paths with quotes.
    """
    text = text.strip().strip("\"'")

    # Check if it's a file with image extension
    ext = Path(text).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return None

    # Try as-is
    path = Path(text)
    if path.exists() and path.is_file():
        return str(path.resolve())

    # Try expanding ~
    try:
        path = Path(text).expanduser()
        if path.exists() and path.is_file():
            return str(path.resolve())
    except Exception:
        logger.debug("Exception suppressed (line 417)")

    # Try relative to CWD
    try:
        path = Path.cwd() / text
        if path.exists() and path.is_file():
            return str(path.resolve())
    except Exception:
        logger.debug("Exception suppressed (line 425)")

    return None


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════

def describe_image(image_path: str, mode: Optional[str] = None) -> VisionResult:
    """Describe an image using the configured vision mode.

    Args:
        image_path: Path to the image file on disk.
        mode: Override the configured mode (pipeline/ollama/deepseek).
              Uses the configured mode if None.

    Returns:
        VisionResult with description and metadata.
    """
    if mode is None:
        mode = _vision_config["mode"]

    # Validate file
    if not os.path.exists(image_path):
        return VisionResult("", str(mode), "", False, f"الملف غير موجود: {image_path}")

    ext = Path(image_path).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return VisionResult("", str(mode), "", False,
                            f"صيغة غير مدعومة: {ext}. الصيغ المدعومة: {', '.join(SUPPORTED_EXTENSIONS)}")

    # Route to the selected mode
    if mode == VisionMode.OLLAMA:
        return _ollama_describe(image_path)
    elif mode == VisionMode.DEEPSEEK:
        return _deepseek_vision_describe(image_path)
    else:
        # Pipeline is the default
        return _pipeline_describe(image_path)


def extract_images_from_text(text: str) -> list[tuple[str, str]]:
    """Extract image paths from user input.

    Returns list of (path, original_text) for each image found.
    Supports:
      - Standalone file paths: /home/user/photo.jpg
      - Paths with spaces (Arabic, etc.)
      - Paths in text: "describe this" C:/photo.jpg
      - Multiple images
      - Quoted paths: "path with spaces.jpg"
    """
    import re

    results = []
    seen_paths = set()

    # Strategy 1: Find quoted paths first
    quoted_patterns = [
        r'"([^"]+\.(?:jpg|jpeg|png|webp|bmp|tiff|tif))"',
        r"'([^']+\.(?:jpg|jpeg|png|webp|bmp|tiff|tif))'",
    ]
    for pattern in quoted_patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            path = _is_image_path(m.group(1))
            if path and path not in seen_paths:
                seen_paths.add(path)
                results.append((path, m.group(0)))

    # Remove quoted paths from further processing
    clean_text = text
    for _, orig in results:
        clean_text = clean_text.replace(orig, "", 1)

    # Strategy 2: Try POSIX paths (forward slashes)
    # These don't have space issues in the same way
    posix_pattern = re.finditer(
        r'(/[^\s]+\.(?:jpg|jpeg|png|webp|bmp|tiff|tif))',
        clean_text, re.IGNORECASE
    )
    for m in posix_pattern:
        path = _is_image_path(m.group(1))
        if path and path not in seen_paths:
            seen_paths.add(path)
            results.append((path, m.group(1)))

    # Strategy 3: Try Windows paths w/ drive letter
    win_pattern = re.finditer(
        r'([a-zA-Z]:\\(?:[^\\\s]+?\\)*[^\\\s]+\.(?:jpg|jpeg|png|webp|bmp|tiff|tif))',
        clean_text, re.IGNORECASE
    )
    for m in win_pattern:
        path = _is_image_path(m.group(1))
        if path and path not in seen_paths:
            seen_paths.add(path)
            results.append((path, m.group(1)))

    # Strategy 4: Try Windows paths w/ forward slashes + drive letter
    win_fwd_pattern = re.finditer(
        r'([a-zA-Z]:/(?:[^/\s]+?/)*[^/\s]+\.(?:jpg|jpeg|png|webp|bmp|tiff|tif))',
        clean_text, re.IGNORECASE
    )
    for m in win_fwd_pattern:
        path = _is_image_path(m.group(1))
        if path and path not in seen_paths:
            seen_paths.add(path)
            results.append((path, m.group(1)))

    # Strategy 5: Sliding window for segments (handles Arabic names with spaces)
    # Try sequences of 1-5 words ending in an image extension
    words = clean_text.split()
    for window_size in range(5, 1, -1):  # Try 5-word windows first
        for i in range(len(words) - window_size + 1):
            segment = " ".join(words[i:i + window_size])
            # Check if segment ends with image extension
            if any(segment.lower().endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                path = _is_image_path(segment)
                if path and path not in seen_paths:
                    seen_paths.add(path)
                    results.append((path, segment))
                    # Mark these words as used
                    for j in range(i, i + window_size):
                        words[j] = ""
                    break
        # Re-compact words after removal
        words = [w for w in words if w]

    return results


def inject_vision_context(messages: list[dict], image_desc: str) -> list[dict]:
    """Inject image description into messages as system context.

    The description is added as a system message so the AI model
    can reason about it even if it doesn't support images natively.
    """
    context_msg = {
        "role": "system",
        "content": f"[VISION INPUT — وصف الصورة المرفوعة]\n{image_desc}\n[/VISION INPUT]\n\nالمستخدم رفع صورة. الوصف أعلاه تم إنشاؤه بواسطة نموذج رؤية. استخدم هذا الوصف للإجابة على استفسار المستخدم.",
        "_vision_context": True,
    }
    messages.append(context_msg)
    return messages


def process_user_input_with_vision(text: str, messages: list[dict]) -> tuple[str, list[dict]]:
    """Process user input, detect images, describe them, inject context.

    This is the main entry point for the CLI integration.

    Args:
        text: Raw user input (may contain image paths)
        messages: Current message list (modified in place if images found)

    Returns:
        (cleaned_text, messages) — image paths removed from text,
        vision context added to messages.
    """
    if not _vision_config["enabled"]:
        return text, messages

    images = extract_images_from_text(text)
    if not images:
        return text, messages

    clean_text = text
    described = 0

    for img_path, original_text in images:
        # Try all modes in priority order
        result = None
        modes_to_try = [
            (_vision_config["mode"], "الوضع المختار"),
        ]

        for mode, label in modes_to_try:
            result = describe_image(img_path, mode=mode)
            if result and result.success:
                break

        if result and result.success:
            inject_vision_context(messages, result.description)
            described += 1

            # Show status
            try:
                from cli.display import show_system_msg
                fname = Path(img_path).name
                show_system_msg(
                    f"🖼️ {fname} → وصف عبر {result.model} "
                    f"({result.mode}): {result.description[:100]}..."
                )
            except ImportError:
                pass
        else:
            # Show error
            try:
                from cli.display import show_system_msg
                fname = Path(img_path).name
                err = result.error if result else "فشل غير معروف"
                show_system_msg(f"⚠️ {fname}: فشل إنشاء الوصف - {err}")
            except ImportError:
                pass

        # Remove image path from text
        clean_text = clean_text.replace(original_text, "", 1).strip()

    return clean_text, messages


def _check_ollama_model(model: str) -> bool:
    """Check if a model is available in Ollama."""
    import httpx
    try:
        resp = httpx.get(
            f"{_vision_config['ollama_url']}/api/tags",
            timeout=5,
        )
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            return any(m["name"] == model or m["name"].startswith(model) for m in models)
    except Exception:
        logger.debug("Exception suppressed (line 648)")
    return False


def get_status() -> dict:
    """Get current vision configuration status."""
    status = dict(_vision_config)
    if _vision_config["mode"] == VisionMode.OLLAMA:
        model_available = _check_ollama_model(_vision_config["ollama_model"])
        status["ollama_available"] = model_available
    return status


def update_config(key: str, value: str) -> str:
    """Update vision configuration.

    Returns a user-friendly status message.
    """
    if key == "mode":
        valid_modes = [VisionMode.PIPELINE, VisionMode.OLLAMA, VisionMode.DEEPSEEK]
        if value in valid_modes:
            _vision_config["mode"] = value
            mode_names = {
                VisionMode.PIPELINE: "Two-Stage Pipeline (محلي)",
                VisionMode.OLLAMA: "Ollama Vision Model",
                VisionMode.DEEPSEEK: "DeepSeek Vision API",
            }
            return f"🖼️ وضع الرؤية: {mode_names.get(value, value)}"
        return f"⚠️ أوضاع متاحة: {', '.join(valid_modes)}"

    elif key == "model":
        _vision_config["ollama_model"] = value
        return f"🖼️ نموذج Ollama: {value}"

    elif key == "pipeline_model":
        _vision_config["pipeline_model"] = value
        # Reset cached model
        global _pipeline_model, _pipeline_processor
        _pipeline_model = None
        _pipeline_processor = None
        return f"🖼️ نموذج Pipeline: {value}"

    elif key == "on":
        _vision_config["enabled"] = True
        return "🖼️ الرؤية مفعّلة"

    elif key == "off":
        _vision_config["enabled"] = False
        return "🖼️ الرؤية معطّلة"

    return f"⚠️ مفتاح غير معروف: {key}"
