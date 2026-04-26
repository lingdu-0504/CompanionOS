"""
CompanionOS Edge TTS
轻量级TTS引擎，CPU即可运行
"""

import asyncio
import os
from pathlib import Path


class EdgeTTS:
    """Edge TTS 语音合成"""

    VOICES = {
        "xiaoxiao": "zh-CN-XiaoxiaoNeural",
        "xiaoyi": "zh-CN-XiaoyiNeural",
        "yunjian": "zh-CN-YunjianNeural",
        "yunxi": "zh-CN-YunxiNeural",
    }

    def __init__(self):
        self.voice = os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural")
        self.output_dir = Path(os.getenv("VOICE_OUTPUT_DIR", "/tmp/companion-os/voice"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def synthesize(self, text: str, voice: str = None) -> dict:
        voice_name = voice or self.voice
        output_path = self.output_dir / f"tts_{asyncio.get_event_loop().time()}.mp3"

        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice_name)
            await communicate.save(str(output_path))
            return {
                "audio_path": str(output_path),
                "engine": "edge-tts",
                "status": "completed",
            }
        except ImportError:
            return {
                "audio_path": None,
                "engine": "edge-tts",
                "status": "not_installed",
                "text": text,
            }
        except Exception as e:
            return {
                "audio_path": None,
                "engine": "edge-tts",
                "status": "error",
                "error": str(e),
            }
