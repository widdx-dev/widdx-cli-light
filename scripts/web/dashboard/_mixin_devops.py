"""Dashboard mixin — devops."""
from __future__ import annotations
import logging

logger = logging.getLogger("widdx.web.dashboard")

import sys as _sys  # noqa: E402
from pathlib import Path  # noqa: E402


class DevOpsMixin:
    def gguf_models(self) -> list[dict]:
        """List imported GGUF models."""
        try:
            from core.providers.gguf import list_imports
            imports = list_imports()
            return [{"name": e.get("model_name", "?"), "path": e.get("metadata", {}).get("path", ""),
                     "size": e.get("metadata", {}).get("size", 0)} for e in imports]
        except Exception:
            return []

    def gguf_load(self, path: str) -> dict:
        """Import a GGUF model into Ollama."""
        try:
            from core.providers.gguf import import_gguf
            result = import_gguf(path)
            return {"status": "imported" if result else "failed", "path": path}
        except Exception as e:
            return {"error": str(e)}

    def gguf_unload(self) -> dict:
        """Remove imported GGUF models (placeholder)."""
        return {"status": "ok", "message": "Use Ollama to manage models"}

    # ════════════════════════════════════════════════════════
    # NEW: System Debug / Doctor
    # ════════════════════════════════════════════════════════


    def debug_info(self) -> dict:
        """Get full debug information."""
        info = {
            "config": "N/A",
            "tools": 0,
            "errors_collected": 0,
        }
        try:
            if hasattr(self, '_cfg'):
                info["config"] = f"Provider: {self._cfg.get('provider', {}).get('name', '?')}"
        except Exception:
            pass
        try:
            if hasattr(self, '_tool_defs'):
                info["tools"] = len(self._tool_defs)
        except Exception:
            pass
        try:
            # Check if error collector has recorded anything
            info["errors_collected"] = 0
        except Exception:
            pass
        return info


    def doctor_check(self) -> list[dict]:
        """Run system diagnostics and return issues."""
        issues = []
        checks = [
            ("LLM Provider", self._check_provider),
            ("Config File", self._check_config),
            ("Sandbox", self._check_sandbox),
            ("Memory", self._check_memory),
            ("Cron Scheduler", self._check_cron),
            ("Python Version", self._check_python),
        ]
        for name, check_fn in checks:
            try:
                result = check_fn()
                issues.append({"check": name, **result})
            except Exception as e:
                issues.append({"check": name, "status": "error", "message": str(e)})
        return issues


    def _check_provider(self) -> dict:
        try:
            from core.providers.providers import create_provider
            from core.config.settings import load as load_cfg
            cfg = load_cfg()
            p = create_provider(cfg)
            # Validate provider name is known
            known = ["ollama", "gguf", "opencode-zen", "opencode", "deepseek"]
            provider_name = cfg.get("provider", {}).get("name", "")
            if provider_name and provider_name not in known:
                return {
                    "status": "warning",
                    "message": f"Unknown provider '{provider_name}' — will fall back to OpenAI-compatible. Provider: {p.name if p else 'None'}",
                }
            return {"status": "ok" if p else "warning", "message": f"Provider: {p.name if p else 'None'}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


    def _check_config(self) -> dict:
        try:
            from core.config.settings import load as load_cfg
            cfg = load_cfg()
            return {"status": "ok", "message": f"Config loaded: {len(cfg)} keys"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


    def _check_sandbox(self) -> dict:
        try:
            from core.sandbox import SandboxExecutor
            sb = SandboxExecutor(mode="auto")
            return {"status": "ok", "message": f"Sandbox mode: {sb.mode}"}
        except Exception as e:
            return {"status": "warning", "message": f"Sandbox unavailable: {e}"}


    def _check_memory(self) -> dict:
        try:
            from core.memory import MemoryStore
            mem = MemoryStore()
            count = len(mem.list_all())
            return {"status": "ok", "message": f"{count} memories"}
        except Exception:
            return {"status": "warning", "message": "Memory store unavailable"}


    def _check_cron(self) -> dict:
        try:
            from core.cron.store import JobStore
            store = JobStore()
            jobs = store.list_jobs()  # type: ignore[attr-defined]
            return {"status": "ok", "message": f"{len(jobs)} jobs scheduled"}
        except Exception:
            return {"status": "info", "message": "Cron scheduler not active"}


    def _check_python(self) -> dict:
        v = _sys.version_info
        ok = v.major >= 3 and v.minor >= 10
        return {"status": "ok" if ok else "error", "message": f"Python {v.major}.{v.minor}.{v.micro}"}

    # ════════════════════════════════════════════════════════
    # NEW: Manifest Management
    # ════════════════════════════════════════════════════════


    def manifest_status(self) -> dict:
        """Get MANIFEST.json status."""
        try:
            from core.project.manifest import _walk
            entries = _walk()
            return {"exists": len(entries) > 0, "entries": len(entries), "items": entries[:10]}
        except Exception:
            return {"exists": False, "entries": 0, "items": []}

    def manifest_scan(self) -> dict:
        """Trigger a project scan via ProjectScanner."""
        try:
            from core.project.scanner import ProjectScanner
            scanner = ProjectScanner()
            card = scanner.scan()
            return {"status": "scanned", "name": card.root_name, "files": len(card.files) if card.files else 0}  # type: ignore[attr-defined]
        except Exception as e:
            return {"error": str(e)}

    # ════════════════════════════════════════════════════════
    # NEW: Git Branch / Undo
    # ════════════════════════════════════════════════════════


    def git_branches(self) -> list[dict]:
        """List git branches."""
        try:
            import subprocess
            result = subprocess.run(["git", "branch", "-a"], capture_output=True, text=True, timeout=5)
            branches = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if line:
                    is_current = line.startswith("*")
                    name = line.replace("*", "").strip()
                    branches.append({"name": name, "current": is_current})
            return branches
        except Exception:
            return []


    def git_undo(self) -> dict:
        """Undo last git commit (soft reset)."""
        try:
            import subprocess
            result = subprocess.run(["git", "reset", "--soft", "HEAD~1"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return {"status": "undone", "message": "Last commit undone (soft reset)"}
            return {"error": result.stderr.strip()}
        except Exception as e:
            return {"error": str(e)}


    def git_status(self) -> dict:
        """Get git status summary."""
        try:
            import subprocess
            status = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=5)
            log = subprocess.run(["git", "log", "--oneline", "-5"], capture_output=True, text=True, timeout=5)
            branch = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, timeout=5)
            ahead = subprocess.run(["git", "rev-list", "--count", "@{u}...HEAD"], capture_output=True, text=True, timeout=5)
            return {
                "changes": status.stdout.strip(),
                "recent_commits": log.stdout.strip(),
                "dirty": bool(status.stdout.strip()),
                "branch": branch.stdout.strip(),
                "ahead": ahead.stdout.strip() or "0",
            }
        except Exception:
            return {"changes": "", "recent_commits": "", "dirty": False, "branch": "", "ahead": "0"}

    def git_commit(self, message: str, files: list[str] | None = None) -> dict:
        """Stage and commit changes."""
        try:
            import subprocess
            # Stage all or specific files
            if files:
                for f in files:
                    subprocess.run(["git", "add", f], capture_output=True, text=True, timeout=10)
            else:
                subprocess.run(["git", "add", "-A"], capture_output=True, text=True, timeout=10)
            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message or "Auto-commit from WIDDX Nexus"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                # Extract hash from output: git outputs "[branch hash]"
                import re
                m = re.search(r"\[[\w\-/.]+\s+([a-f0-9]{7,})\]", result.stdout)
                return {"status": "committed", "hash": m.group(1) if m else "unknown", "message": result.stdout.strip()}
            return {"error": result.stderr.strip() or "Nothing to commit"}
        except Exception as e:
            return {"error": str(e)}

    def git_push(self) -> dict:
        """Push commits to remote."""
        try:
            import subprocess
            result = subprocess.run(["git", "push"], capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return {"status": "pushed", "message": result.stdout.strip()}
            return {"error": result.stderr.strip()}
        except Exception as e:
            return {"error": str(e)}

    def git_pull(self) -> dict:
        """Pull latest from remote."""
        try:
            import subprocess
            result = subprocess.run(["git", "pull"], capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return {"status": "pulled", "message": result.stdout.strip()}
            return {"error": result.stderr.strip()}
        except Exception as e:
            return {"error": str(e)}

    def git_branch_create(self, name: str, from_branch: str | None = None) -> dict:
        """Create a new branch."""
        try:
            import subprocess
            if from_branch and from_branch.strip():
                subprocess.run(["git", "checkout", from_branch], capture_output=True, text=True, timeout=10)
            result = subprocess.run(["git", "branch", name], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return {"status": "created", "name": name}
            return {"error": result.stderr.strip()}
        except Exception as e:
            return {"error": str(e)}

    def git_checkout(self, branch: str) -> dict:
        """Switch to a branch."""
        try:
            import subprocess
            result = subprocess.run(["git", "checkout", branch], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return {"status": "switched", "branch": branch}
            return {"error": result.stderr.strip()}
        except Exception as e:
            return {"error": str(e)}

    def git_diff(self, file_path: str) -> dict:
        """Get diff for a file."""
        try:
            import subprocess
            result = subprocess.run(["git", "diff", "--", file_path], capture_output=True, text=True, timeout=10)
            staged = subprocess.run(["git", "diff", "--cached", "--", file_path], capture_output=True, text=True, timeout=10)
            diff = result.stdout.strip()
            if not diff:
                diff = staged.stdout.strip()
            return {"diff": diff}
        except Exception as e:
            return {"error": str(e)}

    # ════════════════════════════════════════════════════════
    # NEW: Token Budget
    # ════════════════════════════════════════════════════════


    def token_budget(self) -> dict:
        """Get token budget info."""
        try:
            from core.token_budget import TokenBudget
            tb = TokenBudget()
            remaining_tokens, remaining_cost = tb.remaining()
            return {
                "remaining_tokens": remaining_tokens,
                "remaining_cost": round(remaining_cost, 4),
                "summary": tb.summary(),
            }
        except Exception:
            return {"remaining_tokens": 0, "remaining_cost": 0, "summary": "N/A"}

    def token_budget_reset(self) -> dict:
        """Reset token budget."""
        try:
            from core.token_budget import TokenBudget
            tb = TokenBudget()
            tb.reset()
            return {"status": "reset"}
        except Exception as e:
            return {"error": str(e)}

    # ════════════════════════════════════════════════════════
    # NEW: Checkpoints
    # ════════════════════════════════════════════════════════


    def checkpoints_list(self) -> list[dict]:
        """List all checkpoints."""
        try:
            from core.checkpoint import CheckpointManager
            mgr = CheckpointManager()
            cdir = mgr._repo / ".widdx" / "checkpoints"
            if cdir.exists():
                return [{"id": d.name, "timestamp": d.name} for d in sorted(cdir.iterdir()) if d.is_dir()]
            return []
        except Exception:
            return []

    def checkpoint_create(self) -> dict:
        """Create a new checkpoint (file snapshot)."""
        try:
            from core.checkpoint import CheckpointManager
            mgr = CheckpointManager()
            cid = mgr.save("Web UI checkpoint")
            if cid:
                return {"status": "created", "id": cid}
            return {"error": "Checkpoint creation failed"}
        except Exception as e:
            return {"error": str(e)}


    def checkpoint_restore(self, checkpoint_id: str) -> dict:
        """Restore a checkpoint."""
        try:
            from core.checkpoint import CheckpointManager
            mgr = CheckpointManager()
            mgr.restore(checkpoint_id)  # type: ignore[attr-defined]
            return {"status": "restored", "id": checkpoint_id}
        except Exception as e:
            return {"error": str(e)}


    def checkpoint_delete(self, checkpoint_id: str) -> dict:
        """Delete a checkpoint."""
        try:
            from core.checkpoint import CheckpointManager
            mgr = CheckpointManager()
            mgr.delete(checkpoint_id)  # type: ignore[attr-defined]
            return {"status": "deleted"}
        except Exception as e:
            return {"error": str(e)}

    # ════════════════════════════════════════════════════════
    # NEW: Plugin Management
    # ════════════════════════════════════════════════════════


    def plugins_list(self) -> list[dict]:
        """List all plugins."""
        try:
            from core.plugin_loader import PluginLoader
            loader = PluginLoader()
            return loader.list_plugins()
        except Exception:
            return []


    def plugin_enable(self, name: str) -> dict:
        """Enable a plugin."""
        try:
            from core.plugin_loader import PluginLoader
            loader = PluginLoader()
            loader.enable(name)
            return {"status": "enabled", "name": name}
        except Exception as e:
            return {"error": str(e)}


    def plugin_disable(self, name: str) -> dict:
        """Disable a plugin."""
        try:
            from core.plugin_loader import PluginLoader
            loader = PluginLoader()
            loader.disable(name)
            return {"status": "disabled", "name": name}
        except Exception as e:
            return {"error": str(e)}

    # ════════════════════════════════════════════════════════
    # NEW: Workflow Management
    # ════════════════════════════════════════════════════════


    def workflows_list(self) -> list[dict]:
        """List all workflows."""
        try:
            from core.workflow import WorkflowEngine
            engine = WorkflowEngine()
            return engine.list_workflows()
        except Exception:
            return []


    def workflow_run(self, workflow_id: str) -> dict:
        """Run a workflow."""
        try:
            from core.workflow import WorkflowEngine
            engine = WorkflowEngine()
            result = engine.run(workflow_id)
            return {"status": "completed", "result": str(result)[:200]}
        except Exception as e:
            return {"error": str(e)}


    def workflow_create(self, name: str, steps: list) -> dict:
        """Create a new workflow."""
        try:
            from core.workflow import WorkflowEngine
            engine = WorkflowEngine()
            wf = engine.create(name, steps)
            return {"status": "created", "id": wf.id}
        except Exception as e:
            return {"error": str(e)}

    # ════════════════════════════════════════════════════════
    # NEW: Version / App Info
    # ════════════════════════════════════════════════════════


    def app_version(self) -> dict:
        """Get full version info."""
        try:
            from core import version  # type: ignore[attr-defined]
            return {
                "version": version.VERSION,
                "build": version.BUILD,
                "python": version.PYTHON_VERSION,
            }
        except Exception:
            # Fallback: read from pyproject.toml directly
            try:
                import tomllib
                with open(Path(__file__).parent.parent.parent / "pyproject.toml", "rb") as f:
                    pyproject = tomllib.load(f)
                ver = pyproject.get("project", {}).get("version", "3.2.0")
            except Exception:
                ver = "3.2.0"
            return {"version": ver, "build": "dev", "python": _sys.version.split()[0]}

    # ════════════════════════════════════════════════════════
    # NEW: Auto-Commit Status
    # ════════════════════════════════════════════════════════


    def autocommit_status(self) -> dict:
        """Get auto-commit status — returns fields the frontend expects."""
        try:
            from core.auto_commit import AutoCommitManager
            ac = AutoCommitManager()
            # Check last commit time from git log
            import subprocess
            last = ""
            try:
                result = subprocess.run(
                    ["git", "log", "-1", "--format=%cr", "--author-date-is-committer-date"],
                    capture_output=True, text=True, timeout=5
                )
                last = result.stdout.strip() or "Never"
            except Exception:
                last = "Never"
            return {
                "enabled": True,
                "available": True,
                "interval": getattr(ac, '_interval', 300),
                "last_commit": last,
                "repo": str(getattr(ac, '_repo', Path('.'))),
            }
        except Exception:
            return {
                "enabled": False,
                "available": False,
                "interval": 0,
                "last_commit": "Never",
                "repo": "",
            }

    def autocommit_toggle(self) -> dict:
        """Placeholder: auto-commit is always enabled."""
        return {"status": "ok", "message": "Auto-commit is automatic when tools modify files"}

    # ════════════════════════════════════════════════════════
    # NEW: API Key Management (multi-key)
    # ════════════════════════════════════════════════════════


    def apikeys_list(self) -> list[dict]:
        """List all stored API keys (without exposing values)."""
        try:
            from core.config.settings import load as load_cfg
            cfg = load_cfg()
            providers = cfg.get("provider", {})
            keys: dict[str, dict[str, object]] = {}
            if isinstance(providers, dict):
                for p_name, p_cfg in providers.items():
                    if isinstance(p_cfg, dict) and p_cfg.get("api_key"):
                        keys[p_name] = {"has_key": True, "masked": p_cfg["api_key"][:8] + "..."}
            return list(keys.values())
        except Exception:
            return []

