"""Auto Setup — autonomous project bootstrapping for WIDDX.

Handles four capabilities the user requested:
  1. Auto dependency installation (pip, npm, go, cargo)
  2. Deep project learning (structure, DB, APIs → memory facts)
  3. Dynamic skill generation per detected framework
  4. Proactive CLI tool installation when needed
"""

import json
import os
import subprocess
import sys
import logging
import re
from pathlib import Path

logger = logging.getLogger("widdx.auto_setup")

_FRAMEWORK_SKILLS: dict[str, dict] = {
    "django": {
        "icon": "🎯",
        "prompt": (
            "You are helping with a Django project.\n"
            "Rules:\n"
            "- Use `python manage.py` for management commands\n"
            "- Models are in `models.py`, views in `views.py`\n"
            "- Migrations: `python manage.py makemigrations` then `migrate`\n"
            "- Runserver: `python manage.py runserver`\n"
            "- For new apps: `python manage.py startapp <name>`\n"
            "- Always validate after editing models (syntax errors break migrations)"
        ),
    },
    "flask": {
        "icon": "🌶️",
        "prompt": (
            "You are helping with a Flask project.\n"
            "Rules:\n"
            "- App entry point is typically `app.py` or `run.py`\n"
            "- Use `flask run` or `python app.py` to start\n"
            "- Set FLASK_APP env var if needed\n"
            "- Templates go in `templates/`, static files in `static/`\n"
            "- Use `pip install -r requirements.txt` for dependencies"
        ),
    },
    "react": {
        "icon": "⚛️",
        "prompt": (
            "You are helping with a React project.\n"
            "Rules:\n"
            "- Components in `src/components/`\n"
            "- Use `npm start` or `npx vite` to dev server\n"
            "- Build: `npm run build`\n"
            "- Install: `npm install <pkg>`\n"
            "- Use functional components with hooks by default\n"
            "- Run `npx tsc --noEmit` for TypeScript validation"
        ),
    },
    "nextjs": {
        "icon": "▲",
        "prompt": (
            "You are helping with a Next.js project.\n"
            "Rules:\n"
            "- Pages in `app/` or `pages/` directory\n"
            "- API routes in `app/api/` or `pages/api/`\n"
            "- Dev: `npm run dev`, Build: `npm run build`\n"
            "- Use next/link and next/image for optimization\n"
            "- Server components by default in app directory"
        ),
    },
    "vue": {
        "icon": "💚",
        "prompt": (
            "You are helping with a Vue project.\n"
            "Rules:\n"
            "- Components in `src/components/`\n"
            "- Dev: `npm run dev`, Build: `npm run build`\n"
            "- Use `<script setup>` for Composition API\n"
            "- Vue Router in `src/router/`\n"
            "- Pinia for state management"
        ),
    },
    "express": {
        "icon": "🚂",
        "prompt": (
            "You are helping with an Express.js project.\n"
            "Rules:\n"
            "- Entry point is typically `app.js` or `server.js`\n"
            "- Routes in `routes/` directory\n"
            "- Middleware order matters\n"
            "- Use `npm start` or `node app.js` to run\n"
            "- Install: `npm install <pkg>`"
        ),
    },
    "rust": {
        "icon": "🦀",
        "prompt": (
            "You are helping with a Rust project.\n"
            "Rules:\n"
            "- Entry point: `src/main.rs` or `src/lib.rs`\n"
            "- Build: `cargo build`, Run: `cargo run`\n"
            "- Test: `cargo test`, Check: `cargo check`\n"
            "- Add deps: `cargo add <crate>`\n"
            "- Format: `cargo fmt`, Lint: `cargo clippy`"
        ),
    },
    "go": {
        "icon": "🔵",
        "prompt": (
            "You are helping with a Go project.\n"
            "Rules:\n"
            "- Entry point: `main.go`\n"
            "- Build: `go build`, Run: `go run .`\n"
            "- Test: `go test ./...`\n"
            "- Format: `gofmt -s -w .`\n"
            "- Get deps: `go get <module>`"
        ),
    },
}


# ─── 1. Auto Dependency Installer ────────────────────────────────────

def _check_tool(tool: str) -> bool:
    """Check if a CLI tool is available on PATH."""
    try:
        subprocess.run(
            [tool, "--version"] if tool != "node" else ["node", "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def detect_project_deps(project_dir: Path) -> dict:
    """Detect what dependencies the project needs, without installing.

    Returns:
        {"pip": [--extra-index-url ...], "npm": bool, "go": bool, "cargo": bool}
    """
    deps: dict = {"pip": [], "npm": False, "go": False, "cargo": False}

    # Python: requirements.txt
    req = project_dir / "requirements.txt"
    if req.exists() and req.stat().st_size > 0:
        deps["pip"].append(f"-r {req}")

    # Python: pyproject.toml (check if it has a build-system or dependencies)
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            text = pyproject.read_text(encoding="utf-8")
            if "dependencies" in text or "[project]" in text:
                deps["pip"].append("-e .")
        except Exception:
            logger.debug("Exception suppressed (line 156)")

    # Node: package.json (only if node_modules missing)
    pkg = project_dir / "package.json"
    if pkg.exists() and not (project_dir / "node_modules").exists():
        deps["npm"] = True

    # Go: go.mod
    if (project_dir / "go.mod").exists():
        deps["go"] = True

    # Rust: Cargo.toml
    if (project_dir / "Cargo.toml").exists():
        deps["cargo"] = True

    return deps


def auto_install_deps(project_dir: Path, silent: bool = True) -> list[str]:
    """Auto-install project dependencies.

    Args:
        project_dir: Root of the project.
        silent: If True, suppress stdout (show only on error).

    Returns:
        List of human-readable strings describing what was installed.

    Note:
        Dependency installation runs ``pip install``/``npm install`` and can be
        slow (tens of seconds). Set ``WIDDX_AUTO_SETUP_DEPS=0`` to skip it
        entirely — recommended for tests and offline use.
    """
    if os.environ.get("WIDDX_AUTO_SETUP_DEPS", "1").lower() in ("0", "false", "no"):
        logger.debug("Auto dependency install disabled via WIDDX_AUTO_SETUP_DEPS=0")
        return []

    installed: list[str] = []
    deps = detect_project_deps(project_dir)

    # ── pip ───────────────────────────────────────────────
    for req in deps["pip"]:
        if not _check_tool("pip"):
            logger.debug("pip not available, skipping: %s", req)
            continue
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install"] + req.split(),
                capture_output=silent, text=True, timeout=180,
            )
            r.check_returncode()
            installed.append(f"pip {req}")
            logger.info("Installed: pip %s", req)
        except subprocess.CalledProcessError as e:
            logger.debug("pip install %s failed: %s", req, e.stderr[:200])
        except Exception as e:
            logger.debug("pip install %s error: %s", req, e)

    # ── npm ───────────────────────────────────────────────
    if deps["npm"]:
        if not _check_tool("node"):
            logger.debug("node not available, skipping npm install")
        else:
            try:
                r = subprocess.run(
                    ["npm", "install"],
                    cwd=str(project_dir), capture_output=silent, text=True, timeout=180,
                )
                r.check_returncode()
                installed.append("npm install")
                logger.info("Installed: npm install")
            except subprocess.CalledProcessError as e:
                logger.debug("npm install failed: %s", e.stderr[:200])
            except Exception as e:
                logger.debug("npm install error: %s", e)

    # ── go ────────────────────────────────────────────────
    if deps["go"]:
        if not _check_tool("go"):
            logger.debug("go not available, skipping go mod download")
        else:
            try:
                r = subprocess.run(
                    ["go", "mod", "download"],
                    cwd=str(project_dir), capture_output=silent, text=True, timeout=180,
                )
                r.check_returncode()
                installed.append("go mod download")
                logger.info("Installed: go mod download")
            except subprocess.CalledProcessError as e:
                logger.debug("go mod download failed: %s", e.stderr[:200])
            except Exception as e:
                logger.debug("go mod download error: %s", e)

    # ── cargo ─────────────────────────────────────────────
    if deps["cargo"]:
        if not _check_tool("cargo"):
            logger.debug("cargo not available, skipping cargo build")
        else:
            try:
                r = subprocess.run(
                    ["cargo", "build"],
                    cwd=str(project_dir), capture_output=silent, text=True, timeout=180,
                )
                r.check_returncode()
                installed.append("cargo build")
                logger.info("Installed: cargo build")
            except subprocess.CalledProcessError as e:
                logger.debug("cargo build failed: %s", e.stderr[:200])
            except Exception as e:
                logger.debug("cargo build error: %s", e)

    return installed


# ─── 2. Deep Project Learning ───────────────────────────────────────

def _find_entry_points(project_dir: Path) -> list[str]:
    """Find likely entry-point files for the project."""
    candidates = []
    for name in ("main.py", "app.py", "run.py", "index.js", "server.js",
                  "main.rs", "main.go", "lib.rs", "main.ts", "index.ts"):
        p = project_dir / name
        if p.exists():
            candidates.append(str(p.relative_to(project_dir)))
    return candidates


def learn_project(project_dir: Path) -> list[dict]:
    """Deep-analyse a project and return facts suitable for MemoryStore.

    Each fact dict has keys: name, content, type (always "project").
    """
    facts: list[dict] = []
    root = project_dir.resolve()

    # ── Project metadata ──────────────────────────────────
    name = root.name

    # Read description from package.json or pyproject.toml
    description = ""
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            description = data.get("description", "")
        except Exception:
            logger.debug("Exception suppressed (line 303)")
    pyproject = root / "pyproject.toml"
    if pyproject.exists() and not description:
        try:
            text = pyproject.read_text(encoding="utf-8")
            m = re.search(r'description\s*=\s*"([^"]+)"', text)
            if m:
                description = m.group(1)
        except Exception:
            logger.debug("Exception suppressed (line 312)")

    fact_content = f"Project: {name}"
    if description:
        fact_content += f" — {description}"
    facts.append({
        "name": f"project-{name}",
        "content": fact_content,
        "metadata": {"type": "project"},
    })

    # ── Entry points ──────────────────────────────────────
    entries = _find_entry_points(root)
    if entries:
        facts.append({
            "name": f"entry-{name}",
            "content": f"Entry points: {', '.join(entries)}",
            "metadata": {"type": "project"},
        })

    # ── Detect databases ──────────────────────────────────
    db_files: list[Path] = []
    for pattern in ("*.db", "*.sqlite", "*.sqlite3"):
        db_files.extend(root.rglob(pattern))
    if db_files:
        db_list = [str(f.relative_to(root)) for f in db_files[:5]]
        facts.append({
            "name": f"db-{name}",
            "content": f"Databases: {', '.join(db_list)}",
            "metadata": {"type": "project"},
        })

    # ── Detect API routes / controllers ───────────────────
    api_dirs = []
    for sub in ("api", "routes", "controllers", "views", "endpoints",
                 "routers", "handlers", "resources"):
        p = root / sub
        if p.is_dir():
            api_dirs.append(sub)
    for sub in ("app/api", "src/api", "src/routes"):
        p = root / sub
        if p.is_dir():
            api_dirs.append(sub)
    if api_dirs:
        facts.append({
            "name": f"api-{name}",
            "content": f"API directories: {', '.join(api_dirs)}",
            "metadata": {"type": "project"},
        })

    # ── Detect tests ──────────────────────────────────────
    test_dirs = []
    for sub in ("tests", "test", "spec", "__tests__"):
        p = root / sub
        if p.is_dir():
            test_dirs.append(sub)
    if test_dirs:
        facts.append({
            "name": f"tests-{name}",
            "content": f"Test directories: {', '.join(test_dirs)}",
            "metadata": {"type": "project"},
        })

    # ── Detect config files ───────────────────────────────
    configs = [".env.example", ".env", "config.py", "config.js",
               "settings.py", "settings.json", "tsconfig.json",
               "jest.config.js", "vite.config.ts", "next.config.js"]
    found_configs = [c for c in configs if (root / c).exists()]
    if found_configs:
        facts.append({
            "name": f"config-{name}",
            "content": f"Config files: {', '.join(found_configs)}",
            "metadata": {"type": "project"},
        })

    return facts


# ─── 3. Dynamic Skill Generation ────────────────────────────────────

def _detect_frameworks(project_dir: Path) -> set[str]:
    """Detect frameworks used in the project."""
    frameworks: set[str] = set()
    root = project_dir.resolve()

    # Check package.json dependencies
    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            all_deps = {}
            all_deps.update(data.get("dependencies", {}))
            all_deps.update(data.get("devDependencies", {}))
            dep_names = " ".join(all_deps.keys()).lower()

            if "react" in dep_names and "next" not in dep_names:
                frameworks.add("react")
            if "next" in dep_names:
                frameworks.add("nextjs")
            if "vue" in dep_names:
                frameworks.add("vue")
            if "express" in dep_names:
                frameworks.add("express")
        except Exception:
            logger.debug("Exception suppressed (line 416)")

    # Check Python files for framework imports
    py_files = list(root.rglob("*.py"))[:100]
    py_text = ""
    for f in py_files:
        try:
            py_text += f.read_text(encoding="utf-8", errors="ignore") + "\n"
        except Exception:
            continue

    if re.search(r'from\s+django|import\s+django', py_text):
        frameworks.add("django")
    if re.search(r'from\s+flask|import\s+flask', py_text):
        frameworks.add("flask")
    if re.search(r'fastapi|from\s+fastapi', py_text, re.IGNORECASE):
        frameworks.add("fastapi")

    # Check Cargo.toml
    if (root / "Cargo.toml").exists():
        frameworks.add("rust")

    # Check go.mod
    if (root / "go.mod").exists():
        frameworks.add("go")

    return frameworks


def generate_project_skills(project_dir: Path) -> list:
    """Create project-specific Skill objects based on detected frameworks.

    Returns list of Skill objects (from core.skills).
    """
    from core.skills import Skill as WiddxSkill

    frameworks = _detect_frameworks(project_dir)
    skills: list = []

    for fw in frameworks:
        template = _FRAMEWORK_SKILLS.get(fw)
        if not template:
            continue
        skill = WiddxSkill(
            name=fw,
            description=f"Auto-generated {fw} skill for {project_dir.name}",
            icon=template["icon"],
            prompt=(
                f"[AUTO-GENERATED SKILL — {fw}]\n"
                f"{template['prompt']}\n\n"
                f"Project: {project_dir.name}\n"
                f"Directory: {project_dir.resolve()}"
            ),
        )
        skills.append(skill)

    return skills


# ─── 4. Proactive CLI Installer ────────────────────────────────────

_CLI_INSTALLERS: dict[str, dict] = {
    "node": {
        "check": ["node", "--version"],
        "install_pip": [],
        "install_npm": [],
        "message": "Node.js is required. Install from https://nodejs.org/",
    },
    "typescript": {
        "check": ["npx", "tsc", "--version"],
        "install_npm": ["typescript"],
        "message": "Installing TypeScript...",
    },
    "gofmt": {
        "check": ["gofmt", "-e"],
        "install_pip": [],
        "message": "gofmt is part of Go. Install from https://go.dev/",
    },
    "ruby": {
        "check": ["ruby", "--version"],
        "install_pip": [],
        "message": "Ruby is required. Install from https://ruby-lang.org/",
    },
    "dart": {
        "check": ["dart", "--version"],
        "install_pip": [],
        "message": "Dart is required. Install from https://dart.dev/",
    },
}


def ensure_cli_tools(needed: list[str]) -> list[str]:
    """Check if CLI tools are available and try to install them.

    Args:
        needed: List of tool names (e.g. "typescript", "node").

    Returns:
        List of tools that were installed (empty if all were already present).
    """
    installed: list[str] = []

    for name in needed:
        info = _CLI_INSTALLERS.get(name)
        if not info:
            continue

        # Already installed?
        try:
            subprocess.run(info["check"], capture_output=True, text=True, timeout=10)
            continue  # tool exists, skip
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Try npm install
        if info.get("install_npm"):
            try:
                r = subprocess.run(
                    ["npm", "install", "-g"] + info["install_npm"],
                    capture_output=True, text=True, timeout=60,
                )
                if r.returncode == 0:
                    installed.append(name)
                    logger.info("Auto-installed CLI tool: %s", name)
                    continue
            except Exception as e:
                logger.debug("Failed to npm install %s: %s", name, e)

        # Try pip install
        if info.get("install_pip"):
            try:
                r = subprocess.run(
                    [sys.executable, "-m", "pip", "install"] + info["install_pip"],
                    capture_output=True, text=True, timeout=60,
                )
                if r.returncode == 0:
                    installed.append(name)
                    logger.info("Auto-installed CLI tool: %s", name)
                    continue
            except Exception as e:
                logger.debug("Failed to pip install %s: %s", name, e)

    return installed


# ─── 5. Public API — run everything ────────────────────────────────

def setup_project(project_dir: Path) -> dict:
    """Run the full auto-setup pipeline for a project.

    Returns a dict with keys:
      - deps_installed: list of what was installed
      - facts_learned: count of facts stored
      - skills_generated: list of skill names
      - tools_installed: list of tools installed
    """
    result: dict = {
        "deps_installed": [],
        "facts_learned": 0,
        "skills_generated": [],
        "tools_installed": [],
    }

    # 1. Install project dependencies
    deps = auto_install_deps(project_dir)
    if deps:
        result["deps_installed"] = deps

    # 2. Learn project structure
    facts = learn_project(project_dir)
    if facts:
        from core.memory import MemoryStore
        mem = MemoryStore(project_dir=project_dir)
        for fact in facts:
            mem.save(fact["name"], fact["content"], fact.get("metadata", {}))
        result["facts_learned"] = len(facts)

    # 3. Generate project skills
    skills = generate_project_skills(project_dir)
    if skills:
        from core.skills import skill_manager
        for sk in skills:
            # Register as a dynamic skill (not persisted in skills dir)
            skill_manager._skills[sk.name] = sk
        result["skills_generated"] = [s.name for s in skills]

    return result
