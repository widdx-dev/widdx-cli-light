"""Skills system for WIDDX — hybrid prompt templates + optional Python tool extensions."""

import sys
import importlib.util
import logging
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("widdx.skills")

from .utils import parse_frontmatter  # noqa: E402

SKILLS_DIR = Path(__file__).parent.parent / "skills"

# ── Skill Sandbox: safe builtins for tools.py execution ──
# Skills may provide custom tool functions, but those functions execute
# with the full Python runtime.  To reduce the attack surface we restrict
# what the *module-level* code in tools.py can do at import time.
# Individual tool functions still run with normal builtins — their safety
# relies on the function being well-behaved (no os.system, subprocess, etc.).
_SAFE_BUILTINS = {
    "True": True, "False": False, "None": None,
    "abs": abs, "all": all, "any": any, "ascii": ascii,
    "bin": bin, "bool": bool, "bytes": bytes, "callable": callable,
    "chr": chr, "complex": complex, "dict": dict, "dir": dir,
    "divmod": divmod, "enumerate": enumerate, "filter": filter,
    "float": float, "format": format, "frozenset": frozenset,
    "getattr": getattr, "hasattr": hasattr, "hash": hash,
    "hex": hex, "id": id, "int": int, "isinstance": isinstance,
    "issubclass": issubclass, "iter": iter, "len": len,
    "list": list, "map": map, "max": max, "min": min,
    "next": next, "object": object, "oct": oct, "ord": ord,
    "pow": pow, "print": print, "range": range, "repr": repr,
    "reversed": reversed, "round": round, "set": set,
    "slice": slice, "sorted": sorted, "str": str, "sum": sum,
    "tuple": tuple, "type": type, "vars": vars, "zip": zip,
    # Allow imports of safe stdlib modules
    "__import__": __import__,
    "ImportError": ImportError, "ModuleNotFoundError": ModuleNotFoundError,
    "ValueError": ValueError, "TypeError": TypeError,
    "Exception": Exception, "RuntimeError": RuntimeError,
}

# Modules that skill tools.py files are NOT allowed to import at module level.
_BLOCKED_MODULES: set[str] = {
    "os", "subprocess", "shutil", "sys", "ctypes", "signal",
    "socket", "http", "urllib", "requests", "ftplib", "telnetlib",
    "smtplib", "pickle", "shelve", "marshal", "code", "codeop",
    "builtins", "__builtins__", "importlib", "pkgutil", "runpy",
    "multiprocessing", "threading", "concurrent.futures",
    "pathlib",   # block direct FS access at module level
}



class SkillTool:
    """A callable tool associated with a skill, with OpenAI-compatible schema."""

    def __init__(self, name: str, description: str, parameters: dict, handler: Callable):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler

    def to_openai_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def __call__(self, **kwargs):
        return str(self.handler(**kwargs))

    def __repr__(self):
        return f"SkillTool(name={self.name!r})"


class Skill:
    """A single skill with prompt template and optional custom tools."""

    def __init__(self, name: str, description: str, icon: str,
                 prompt: str, tools: dict | None = None, path: Path | None = None):
        self.name = name
        self.description = description
        self.icon = icon
        self.prompt = prompt
        self.tools = tools or {}
        self.path = path

    def get_tool_definitions(self) -> list:
        """Return OpenAI-compatible tool definitions for this skill's custom tools."""
        if not self.tools:
            return []
        result = []
        for tname, tfunc in self.tools.items():
            doc = (tfunc.__doc__ or "").strip().split("\n")[0]
            result.append({
                "name": tname,
                "description": doc,
                "parameters": {},
            })
        return result

    def __repr__(self):
        return f"Skill(name={self.name!r}, desc={self.description[:30]!r})"


def _load_skill_tools(skill_dir: Path) -> dict:
    """Load custom tools from tools.py in a skill directory, if present.

    Safety: the module-level code in tools.py runs with restricted builtins
    and a blocked-module import hook to prevent dangerous operations at import
    time.  Individual tool functions (called later via ``execute_tool``) still
    run with full builtins — their safety depends on the function being
    well-behaved.
    """
    tools_py = skill_dir / "tools.py"
    if not tools_py.exists():
        return {}
    try:
        spec = importlib.util.spec_from_file_location(
            f"skill_{skill_dir.name}_tools", str(tools_py)
        )
        if spec is None:
            logger.warning("Could not create module spec for %s", tools_py)
            return {}
        mod = importlib.util.module_from_spec(spec)

        # ── Sandbox: restrict builtins at module level ──
        mod.__builtins__ = _SAFE_BUILTINS.copy()  # type: ignore[attr-defined]

        # ── Sandbox: install import hook to block dangerous modules ──
        _install_skill_import_blocker(mod)

        sys.modules[f"_skill_{skill_dir.name}"] = mod
        if spec.loader:
            spec.loader.exec_module(mod)

        # ── Collect all callable public functions ──
        tools = {}
        for name in dir(mod):
            if name.startswith("_"):
                continue
            obj = getattr(mod, name)
            if callable(obj):
                tools[name] = obj
        return tools
    except Exception as e:
        logger.warning("Failed to load skill tools from %s: %s", skill_dir, e)
        return {}


def _install_skill_import_blocker(mod):
    """Install a module-level __import__ hook that blocks dangerous modules.

    Only active during the import of the skill's tools.py module.
    Once the module is loaded, we remove the hook so tool functions
    can import anything they need at runtime.
    """
    original_import = mod.__builtins__.get("__import__", __import__)

    def _safe_import(name, *args, **kwargs):
        # Resolve top-level package name
        top_level = name.split(".")[0]
        if top_level in _BLOCKED_MODULES:
            raise ImportError(
                f"Module '{name}' is blocked for security reasons "
                f"in skill tools.py. Use allowed stdlib modules only."
            )
        return original_import(name, *args, **kwargs)

    mod.__builtins__["__import__"] = _safe_import


class SkillManager:
    """Loads, manages, and activates skills."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._active: Optional[Skill] = None
        self.load_all()

    # ── loading ────────────────────────────────────────────────────────

    def load_all(self):
        """Scan skills/ directory and load all valid skills."""
        self._skills = {}
        if not SKILLS_DIR.exists():
            SKILLS_DIR.mkdir(parents=True, exist_ok=True)
            return
        for entry in sorted(SKILLS_DIR.iterdir()):
            if entry.is_dir():
                skill = self._load_one(entry)
                if skill:
                    self._skills[skill.name] = skill

    def load_skill(self, skill_dir: Path) -> Optional[Skill]:
        """Load (or reload) a single skill from a directory.

        Called by the hot-reload watcher when a skill file changes.
        """
        skill = self._load_one(skill_dir)
        if skill:
            self._skills[skill.name] = skill
        return skill

    def _load_one(self, skill_dir: Path) -> Optional[Skill]:
        """Load a single skill from a directory."""
        # Support both WIDDX (skill.md) and Anthropic (SKILL.md) formats
        md = skill_dir / "skill.md"
        if not md.exists():
            md = skill_dir / "SKILL.md"
        if not md.exists():
            return None
        text = md.read_text(encoding="utf-8")
        meta, prompt = parse_frontmatter(text, nested_metadata=False)
        name = meta.get("name") or skill_dir.name
        desc = meta.get("description", "No description")
        icon = meta.get("icon", "")
        tools = _load_skill_tools(skill_dir)
        return Skill(name=name, description=desc, icon=icon,
                     prompt=prompt, tools=tools, path=skill_dir)

    # ── access ─────────────────────────────────────────────────────────

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list_all(self) -> list[Skill]:
        return list(self._skills.values())

    @property
    def active(self) -> Optional[Skill]:
        return self._active

    def activate(self, name: str) -> bool:
        """Activate a skill by name. Returns True on success."""
        skill = self._skills.get(name)
        if skill:
            self._active = skill
            return True
        return False

    def deactivate(self) -> None:
        """Deactivate the currently active skill."""
        self._active = None

    def toggle(self, name: str) -> bool:
        """Toggle: if already active, deactivate; else activate."""
        if self._active and self._active.name == name:
            self.deactivate()
            return True
        return self.activate(name)

    # ── tools ──────────────────────────────────────────────────────────

    def get_active_tools(self) -> list:
        """Return custom tool definitions for the currently active skill."""
        if not self._active:
            return []
        return self._active.get_tool_definitions()

    def get_use_skill_tool_def(self) -> dict | None:
        """Return an OpenAI-compatible tool definition for `use_skill`.
        The AI calls this to activate/deactivate skills autonomously."""
        skills = self.list_all()
        if not skills:
            return None
        return {
            "name": "use_skill",
            "description": (
                "Activate a specialized skill for the current task. "
                "Call this when the user's request matches a skill's purpose. "
                "Pass an empty string to deactivate the current skill."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "The skill to activate. Empty string to deactivate.",
                        "enum": [s.name for s in skills] + [""]
                    }
                },
                "required": ["skill_name"]
            }
        }

    def suggest_skills(self, user_input: str) -> list[Skill]:
        """Suggest relevant skills based on user input using keyword matching."""
        user_input_lower = user_input.lower()
        suggestions: list[Skill] = []

        # Keyword mappings — comprehensive coverage for all skills
        keyword_maps: dict[str, list[str]] = {
            "graphic-designer": [
                "design", "صمم", "تصميم", "بطاقة", "card", "poster", "بوستر",
                "certificate", "شهادة", "invitation", "دعوة", "svg", "illustration",
                "graphic", "جرافيك", "print", "طباعة", "a4", "graduation", "تخرج",
                "social media post", "منشور", "banner", "بانر", "layout", "رسم",
            ],
            "app-builder": [
                "build app", "create app", "scaffold", "new project", "fullstack",
                "full stack", "full-stack", "production app", "build a", "scaffold a",
                "انشاء تطبيق", "بناء تطبيق", "مشروع جديد",
            ],
            "react-builder": [
                "react", "next.js", "nextjs", "vite", "jsx", "tsx", "component",
                "tailwind", "zustand", "redux", "react router",
            ],
            "vue-builder": [
                "vue", "nuxt", "pinia", "vue router", "composition api",
            ],
            "express-builder": [
                "express", "node.js", "nodejs", "nestjs", "api", "prisma",
                "backend", "typescript", "middleware", "endpoint",
            ],
            "laravel-builder": [
                "laravel", "php", "eloquent", "blade", "livewire", "breeze",
            ],
            "django-builder": [
                "django", "fastapi", "drf", "sqlalchemy", "python web", "flask",
            ],
            "flutter-builder": [
                "flutter", "react native", "expo", "mobile app", "ios", "android",
                "dart", "widget", "تطبيق جوال",
            ],
            "code-review": [
                "review", "code review", "audit", "check code", "bug",
                "security", "style", "مراجعة", "تدقيق",
            ],
            "fix-bug": [
                "fix bug", "debug", "fix error", "problem", "issue", "broken",
                "doesn't work", "not working", "error", "تصليح", "اصلاح", "مشكلة",
            ],
            "refactor": [
                "refactor", "improve code", "clean up", "reorganize", "restructure",
                "simplify", "optimize", "تحسين",
            ],
            "generate-tests": [
                "test", "tests", "generate tests", "write tests", "unit test",
                "pytest", "jest", "اختبارات",
            ],
            "document": [
                "document", "write docs", "documentation", "readme", "api docs",
                "jsdoc", "docstring", "توثيق",
            ],
            "explain-code": [
                "explain", "explain code", "how does this work", "understand",
                "what does", "شرح", "كيف يعمل",
            ],
            "tui-builder": [
                "tui", "terminal ui", "textual", "build interface", "terminal app",
                "واجهة طرفية",
            ],
            "cinematic-experience": [
                "cinematic", "animation", "3d", "webgl", "motion", "parallax",
                "immersive", "scroll", "experience", "تفاعلي", "حركة",
            ],
            "textual-master": [
                "textual css", "tcss", "textual widget", "textual screen",
            ],
        }

        for skill in self._skills.values():
            keywords = keyword_maps.get(skill.name, [])
            # Check skill name match
            if skill.name.lower() in user_input_lower:
                suggestions.append(skill)
                continue
            # Check keywords
            if any(kw in user_input_lower for kw in keywords):
                suggestions.append(skill)
                continue
            # Check description words (partial match)
            desc_words = skill.description.lower().split()
            if any(w in user_input_lower for w in desc_words if len(w) > 3):
                suggestions.append(skill)

        return suggestions

    def execute_tool(self, name: str, args: dict) -> str:
        """Execute a custom tool from the active skill."""
        if not self._active or name not in self._active.tools:
            return f"Tool '{name}' not found in active skill"
        try:
            return str(self._active.tools[name](**args))
        except Exception as e:
            return f"Skill tool error: {e}"

    def start_hot_reload(self):
        """Start watching the skills directory for changes (auto-reload)."""
        try:
            from core.plugin_loader import get_hot_reloader
            reloader = get_hot_reloader()
            reloader.start()
            logger.info("Skill hot reload started")
        except Exception as e:
            logger.debug("Hot reload not available: %s", e)


# Singleton
skill_manager = SkillManager()
