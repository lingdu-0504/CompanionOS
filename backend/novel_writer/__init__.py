"""
商业级小说创作大模型开发框架
Novel Writing Framework - A commercial-grade novel generation system
"""

__version__ = "1.0.0"
__author__ = "Novel Writing Framework Team"

from .core import NovelWriterCore
from .project import NovelProject
from .engine import GlobalMemoryEngine, WordCountEngine, NarrativeStructureEngine
from .platform import NovelPlatformPublisher
from .parallel import ParallelTaskManager

__all__ = [
    "NovelWriterCore",
    "NovelProject",
    "GlobalMemoryEngine",
    "WordCountEngine",
    "NarrativeStructureEngine",
    "NovelPlatformPublisher",
    "ParallelTaskManager",
]
