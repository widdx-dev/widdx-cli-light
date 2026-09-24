"""Dashboard — exposes all WIDDX systems via REST API.

Architecture:
  Dashboard composes mixin classes from scripts.web.dashboard._mixin_*.
  Each mixin handles one subsystem. Dashboard itself is a thin facade.

Mixin files:
  _mixin_core.py      — System info, computer operations
  _mixin_scheduler.py  — Cron jobs, background tasks, sub-agents
  _mixin_storage.py    — Sessions, memory, activity, skills
  _mixin_gateway.py    — Gateway channels, MCP, proxy, permissions
  _mixin_settings.py   — Provider settings, models, configuration
  _mixin_devops.py     — Git, checkpoints, plugins, workflows, GGUF, health
"""

from __future__ import annotations

import logging

logger = logging.getLogger("widdx.web.dashboard")

from core._path import ensure_project_root  # noqa: E402
ensure_project_root()

from scripts.web.dashboard._mixin_core import CoreDashboardMixin  # noqa: E402
from scripts.web.dashboard._mixin_scheduler import SchedulerMixin  # noqa: E402
from scripts.web.dashboard._mixin_storage import StorageMixin  # noqa: E402
from scripts.web.dashboard._mixin_gateway import GatewayMixin  # noqa: E402
from scripts.web.dashboard._mixin_settings import SettingsMixin  # noqa: E402
from scripts.web.dashboard._mixin_devops import DevOpsMixin  # noqa: E402


class Dashboard(
    CoreDashboardMixin,
    SchedulerMixin,
    StorageMixin,
    GatewayMixin,
    SettingsMixin,
    DevOpsMixin,
):
    """Aggregates all WIDDX systems for the Web UI.

    Each subsystem is implemented as a separate mixin class.
    This class only contains the initialization glue — all methods
    are inherited from the mixins above.

    ═══ MRO (Method Resolution Order) ═══
    Dashboard → CoreDashboardMixin → SchedulerMixin → StorageMixin
              → GatewayMixin → SettingsMixin → DevOpsMixin → object

    All mixins MUST call super().__init__() if they define __init__.
    Currently only CoreDashboardMixin has __init__. If you add __init__
    to any other mixin, make sure it delegates: super().__init__()
    ═══════════════════════════════════════
    """
