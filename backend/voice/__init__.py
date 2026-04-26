"""
CompanionOS Voice模块
TTS + ASR 语音服务
"""

from .service import VoiceService
from .tts_edge import EdgeTTS

__all__ = ["VoiceService", "EdgeTTS"]
