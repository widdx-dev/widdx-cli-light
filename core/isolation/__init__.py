"""WIDDX Isolation Engine — container-based process isolation.

Replaces regex-only security and bare subprocess execution with
actual container isolation where available (Docker/podman),
with graceful fallback to resource-limited subprocess.

Profiles define what each execution environment can do:
- Network: none / internal / restricted / full
- Filesystem: read-only mounts, tmpfs for writable areas
- Resources: memory limits, CPU limits, timeout
- Commands: allowed command whitelist
"""

from .profiles import (
    IsolationProfile,
    PROFILES,
    get_profile,
)
from .container import (
    ContainerManager,
    ContainerResult,
    get_container_manager,
)
from .policy import (
    IsolationPolicy,
    get_policy,
)

__all__ = [
    "IsolationProfile",
    "PROFILES",
    "get_profile",
    "ContainerManager",
    "ContainerResult",
    "get_container_manager",
    "IsolationPolicy",
    "get_policy",
]
