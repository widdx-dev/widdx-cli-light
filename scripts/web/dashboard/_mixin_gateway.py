"""Dashboard mixin — gateway."""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger("widdx.web.dashboard")



class GatewayMixin:
    def gateway_status(self) -> dict:
        """Return status of all communication channels."""
        channels = []
        try:
            from core.gateway import GatewayCore
            gw = GatewayCore()
            # Check which platform adapters are registered
            adapters = getattr(gw, '_adapters', {})
            for platform_name in ("telegram", "discord"):
                adapter = adapters.get(platform_name)
                if adapter is not None:
                    is_connected = getattr(adapter, 'is_connected', lambda: False)()
                    channels.append({
                        "name": platform_name.title(),
                        "icon": self._gateway_icon(platform_name),
                        "status": "connected" if is_connected else "disconnected",
                        "last_message": None,
                        "message_count": 0,
                        "error": None,
                    })
                else:
                    channels.append({
                        "name": platform_name.title(),
                        "icon": self._gateway_icon(platform_name),
                        "status": "not_configured",
                        "last_message": None,
                        "message_count": 0,
                        "error": None,
                    })
        except ImportError:
            channels = [
                {"name": "Telegram", "icon": "fa-telegram", "status": "not_available", "last_message": None, "message_count": 0, "error": "Gateway module not installed"},
                {"name": "Discord", "icon": "fa-discord", "status": "not_available", "last_message": None, "message_count": 0, "error": "Gateway module not installed"},
            ]
        except Exception as e:
            channels = [
                {"name": "Telegram", "icon": "fa-telegram", "status": "error", "last_message": None, "message_count": 0, "error": str(e)[:80]},
            ]

        return {
            "channels": channels,
            "total_channels": len(channels),
            "active_channels": sum(1 for c in channels if c["status"] == "connected"),
        }

    @staticmethod
    def _gateway_icon(name: str) -> str:
        icons = {"telegram": "fa-telegram", "discord": "fa-discord", "sms": "fa-comment-sms", "whatsapp": "fa-whatsapp"}
        return icons.get(name.lower(), "fa-plug")


    def mcp_status(self) -> list[dict]:
        """List all MCP servers and their status."""
        try:
            from core.mcp.client import get_mcp_manager
            mgr = get_mcp_manager()
            return [s.to_dict() if hasattr(s, 'to_dict') else {"name": str(k), "status": "unknown"}
                    for k, s in getattr(mgr, '_connections', {}).items()]
        except Exception:
            return []


    def mcp_add(self, name: str, command: str, args: list[Any] | None = None) -> dict:
        """Add a new MCP server."""
        try:
            from core.mcp.client import get_mcp_manager
            mgr = get_mcp_manager()
            mgr.add_server(name, command, args or [])
            return {"status": "added", "name": name}
        except Exception as e:
            return {"error": str(e)}


    def mcp_remove(self, name: str) -> dict:
        """Remove an MCP server."""
        try:
            from core.mcp.client import get_mcp_manager
            mgr = get_mcp_manager()
            mgr.remove_server(name)
            return {"status": "removed", "name": name}
        except Exception as e:
            return {"error": str(e)}


    def mcp_restart(self, name: str) -> dict:
        """Restart an MCP server."""
        try:
            from core.mcp.client import get_mcp_manager
            mgr = get_mcp_manager()
            mgr.restart_server(name)  # type: ignore[attr-defined]
            return {"status": "restarted", "name": name}
        except Exception as e:
            return {"error": str(e)}

    # ════════════════════════════════════════════════════════
    # NEW: Proxy Settings
    # ════════════════════════════════════════════════════════


    def proxy_status(self) -> dict:
        """Get current proxy settings."""
        try:
            from core.proxy import proxy_manager
            working = getattr(proxy_manager, '_working', [])
            return {"enabled": len(working) > 0, "proxies": len(working), "proxy_list": working[:5]}
        except Exception:
            return {"enabled": False, "proxies": 0, "proxy_list": []}

    def proxy_update(self, http: str = "", https: str = "", enabled: bool = False) -> dict:
        """Update proxy settings (proxies are auto-discovered)."""
        return {"status": "ok", "message": "Proxies are auto-discovered from free sources"}

    # ════════════════════════════════════════════════════════
    # NEW: Permissions Management
    # ════════════════════════════════════════════════════════


    def permissions_status(self) -> dict:
        """Get current permission level."""
        try:
            from core.permissions import PermissionManager
            pm = PermissionManager()
            return {
                "level": str(pm.level.value if hasattr(pm.level, 'value') else pm.level),
                "status": pm.status(),
            }
        except Exception:
            return {"level": "normal", "status": "Permission system unavailable"}

    def permissions_set(self, level: str) -> dict:
        """Set permission level."""
        try:
            from core.permissions import PermissionManager
            pm = PermissionManager()
            pm.level = level
            return {"status": "set", "level": level}
        except Exception as e:
            return {"error": str(e)}

    # ════════════════════════════════════════════════════════
    # NEW: GGUF Model Management
    # ════════════════════════════════════════════════════════


