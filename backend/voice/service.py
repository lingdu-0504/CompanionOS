"""
CompanionOS 语音服务
TTS + ASR 模块
"""

import os

from .tts_edge import EdgeTTS


class VoiceService:
    """语音服务统一入口"""

    def __init__(self):
        self.tts_engines = {
            "edge": EdgeTTS(),
        }
        self.default_tts = "edge"
        self._whisper_model = None
        self._whisper_model_size = None

    async def synthesize(self, text: str, engine: str = None) -> dict:
        """
        语音合成

        Args:
            text: 要合成的文本
            engine: TTS引擎名称

        Returns:
            dict: {"audio_path": str, "engine": str, "status": str}
        """
        engine_name = engine or self.default_tts
        tts = self.tts_engines.get(engine_name)

        if not tts:
            return {"error": f"TTS引擎 {engine_name} 不可用", "status": "failed"}

        return await tts.synthesize(text)

    async def recognize(self, audio_path: str) -> dict:
        """
        语音识别
        优先使用 OpenAI Whisper API，失败时降级到本地模拟

        Args:
            audio_path: 音频文件路径

        Returns:
            dict: {"text": str, "engine": str, "status": str}
        """
        api_key = os.environ.get("OPENAI_API_KEY")
        api_base = os.environ.get("OPENAI_API_BASE")

        if api_key:
            try:
                return await self._transcribe_with_openai(audio_path, api_key, api_base)
            except Exception:
                return await self._transcribe_local(audio_path)
        else:
            return await self._transcribe_local(audio_path)

    async def _transcribe_with_openai(self, audio_path: str, api_key: str, api_base: str | None) -> dict:
        """
        使用 OpenAI Whisper API 进行语音识别

        Args:
            audio_path: 音频文件路径
            api_key: OpenAI API 密钥
            api_base: OpenAI API 基础地址（可选）

        Returns:
            dict: {"text": str, "engine": str, "status": str}
        """
        try:
            from openai import OpenAI
        except ImportError:
            return await self._transcribe_local(audio_path)

        client = OpenAI(api_key=api_key, base_url=api_base) if api_base else OpenAI(api_key=api_key)

        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )

        return {
            "text": transcript.text,
            "engine": "whisper",
            "status": "completed",
        }

    async def _transcribe_local(self, audio_path: str) -> dict:
        """
        使用 faster-whisper 进行本地离线语音识别

        Args:
            audio_path: 音频文件路径

        Returns:
            dict: {"text": str, "engine": str, "status": str, "segments": list}
        """
        try:
            from faster_whisper import WhisperModel

            model_size = os.environ.get("WHISPER_MODEL_SIZE", "base")

            if self._whisper_model is None or self._whisper_model_size != model_size:
                self._whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
                self._whisper_model_size = model_size

            model = self._whisper_model
            segments_gen, info = model.transcribe(audio_path, beam_size=5)
            segments_list = list(segments_gen)
            full_text = "".join(seg.text for seg in segments_list)

            return {
                "text": full_text,
                "engine": f"faster-whisper/{model_size}",
                "status": "completed",
                "segments": [
                    {"start": seg.start, "end": seg.end, "text": seg.text}
                    for seg in segments_list
                ],
                "language": info.language if info else "unknown",
                "duration": info.duration if info else 0,
            }
        except Exception as e:
            return {
                "text": f"[语音识别失败: {str(e)[:100]}]",
                "engine": "faster-whisper",
                "status": "failed",
            }

    def list_engines(self) -> list[dict]:
        """列出可用的TTS引擎"""
        return [
            {"name": name, "available": True}
            for name in self.tts_engines
        ]
