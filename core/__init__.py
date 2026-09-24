# WIDDX Nexus - Core Module
# Created by MUHAMMAD MUSLIH (widdx.com)
# Re-exports for convenient access

from core.config.settings import load, get, save
from core.proxy import proxy_manager, ProxyManager
from core.providers.providers import (
    Provider, ToolCall,
    OllamaProvider, OpenAICompatibleProvider, OpenCodeZenProvider,
    DeepSeekProvider, GGUFDirectProvider,
    fetch_free_models, create_provider,
    get_available_models, resolve_model, estimate_turn_cost,
)
from core.memory import MemoryStore
from core.memory_learner import MemoryLearner
from core.activity import ActivityStore, get_store as get_activity_store, add as add_activity
from core.background import BackgroundTaskManager
from core.delegation import DelegationManager
from core.voice import TTSEngine
from core.cron.scheduler import CronScheduler
from core.gateway import GatewayCore, Platform, Message, Reply
from core.vision import describe_image, VisionMode, process_user_input_with_vision
from core.tools import TOOL_DEFINITIONS, execute, execute_with_skills
from core.state_manager import StateManager
from core.verification.loop import VerifyLoop, LoopResult
from core.guard import CommandGuard, GuardResult
from core.learning.pattern_library import PatternLibrary, UnifiedPatternStore
from core.knowledge_graph import KnowledgeGraph
from core.sandbox import SandboxExecutor, SandboxResult, ResourceLimits
from core.tools.security import scan_dangerous

__all__ = [
    "load", "get", "save",
    "proxy_manager", "ProxyManager",
    "Provider", "ToolCall",
    "OllamaProvider", "OpenAICompatibleProvider", "OpenCodeZenProvider",
    "DeepSeekProvider", "GGUFDirectProvider",
    "fetch_free_models", "create_provider",
    "get_available_models", "resolve_model", "estimate_turn_cost",
    "MemoryStore",
    "MemoryLearner",
    "ActivityStore", "get_activity_store", "add",
    "BackgroundTaskManager",
    "DelegationManager",
    "TTSEngine",
    "CronScheduler",
    "GatewayCore", "Platform", "Message", "Reply",
    "describe_image", "VisionMode", "process_user_input_with_vision",
    "TOOL_DEFINITIONS", "execute", "execute_with_skills",
    "add_activity",
    "StateManager",
    "VerifyLoop", "LoopResult",
    "CommandGuard", "GuardResult",
    "PatternLibrary", "UnifiedPatternStore",
    "KnowledgeGraph",
    "SandboxExecutor", "SandboxResult", "ResourceLimits",
    "scan_dangerous",
]
