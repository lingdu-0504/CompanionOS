"""
CompanionOS Agent Bridge模块
智能体协同总线
"""

from .a2a_gateway import A2AGateway
from .eigent_adapter import EigentAdapter
from .hermes_adapter import HermesAdapter
from .mcp_gateway import MCPGateway
from .neuro_adapter import (
    EmotionMemoryManager,
    EmotionReasoner,
    EmotionReplyGenerator,
    EmotionState,
    NeuroAdapter,
    VRMActionMap,
)

__all__ = [
    "HermesAdapter",
    "NeuroAdapter",
    "EmotionReasoner",
    "EmotionReplyGenerator",
    "EmotionMemoryManager",
    "EmotionState",
    "VRMActionMap",
    "MCPGateway",
    "A2AGateway",
    "EigentAdapter",
]
