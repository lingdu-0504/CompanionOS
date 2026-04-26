"""
CompanionOS E2E测试 - 第3部分：情绪分析API
覆盖: /api/emotion/analyze, /api/emotion/analyze-enhanced, /api/emotion/trend, /api/emotion/history
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


class TestEmotionAPI:
    """情绪分析API"""

    @pytest.mark.asyncio
    async def test_analyze_emotion_happy(self, client):
        """POST /api/emotion/analyze - 开心情绪"""
        resp = await client.post("/api/emotion/analyze", params={"message": "今天太开心了！"})
        assert resp.status_code == 200
        data = resp.json()

        assert "emotion" in data
        emotion = data["emotion"]
        assert emotion["primary"] == "happy"
        assert emotion["valence"] > 0.7
        assert "vrm_action" in data
        assert "vrm_map" in data

    @pytest.mark.asyncio
    async def test_analyze_emotion_sad(self, client):
        """POST /api/emotion/analyze - 难过情绪"""
        resp = await client.post("/api/emotion/analyze", params={"message": "我好难过"})
        assert resp.status_code == 200
        data = resp.json()

        emotion = data["emotion"]
        assert emotion["primary"] == "sad"
        assert emotion["valence"] < 0.3

    @pytest.mark.asyncio
    async def test_analyze_emotion_neutral(self, client):
        """POST /api/emotion/analyze - 中性消息"""
        resp = await client.post("/api/emotion/analyze", params={"message": "今天吃什么好呢"})
        assert resp.status_code == 200
        data = resp.json()

        emotion = data["emotion"]
        assert emotion["primary"] in ("neutral", "curious")

    @pytest.mark.asyncio
    async def test_analyze_emotion_greeting(self, client):
        """POST /api/emotion/analyze - 问候模式"""
        resp = await client.post("/api/emotion/analyze", params={"message": "早上好"})
        assert resp.status_code == 200
        data = resp.json()

        emotion = data["emotion"]
        assert emotion["primary"] == "happy"
        assert data["vrm_action"] == "wave"

    @pytest.mark.asyncio
    async def test_analyze_emotion_enhanced(self, client):
        """POST /api/emotion/analyze-enhanced - 增强情绪分析"""
        resp = await client.post("/api/emotion/analyze-enhanced", params={"message": "好累但今天完成了好多工作"})
        assert resp.status_code == 200
        data = resp.json()

        assert "emotion" in data
        assert "vrm_action" in data
        assert "vrm_map" in data
        # 增强版应包含趋势
        assert "emotion_trend" in data

    @pytest.mark.asyncio
    async def test_emotion_trend(self, client):
        """GET /api/emotion/trend - 获取情绪趋势"""
        # 先产生一些情绪记录
        await client.post("/api/emotion/analyze", params={"message": "开心"})
        await client.post("/api/emotion/analyze", params={"message": "好累"})

        resp = await client.get("/api/emotion/trend")
        assert resp.status_code == 200
        data = resp.json()

        assert "dominant_emotion" in data
        assert "average_valence" in data
        assert "average_arousal" in data
        assert "emotional_volatility" in data
        assert "mood_direction" in data

    @pytest.mark.asyncio
    async def test_emotion_history(self, client):
        """GET /api/emotion/history - 获取情绪历史"""
        # 通过chat API产生情绪记录（chat -> process -> emotion_memory.record）
        await client.post("/api/chat", json={"message": "今天好开心"})

        resp = await client.get("/api/emotion/history")
        assert resp.status_code == 200
        data = resp.json()

        assert "history" in data
        # 如果有历史记录，验证格式
        if len(data["history"]) > 0:
            entry = data["history"][-1]
            assert "emotion" in entry
            assert "valence" in entry
            assert "arousal" in entry

    @pytest.mark.asyncio
    async def test_emotion_history_with_limit(self, client):
        """GET /api/emotion/history?limit=N - 限制返回数量"""
        resp = await client.get("/api/emotion/history", params={"limit": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["history"]) <= 3

    @pytest.mark.asyncio
    async def test_vrm_action_mapping(self, client):
        """验证VRM动作映射完整性"""
        # 测试多种情绪的VRM映射
        test_cases = [
            ("好开心", "happy"),
            ("好难过", "sad"),
            ("好累", "tired"),
            ("好寂寞", "lonely"),
            ("好焦虑", "anxious"),
            ("烦死了", "angry"),
            ("太激动了", "excited"),
            ("喜欢你", "love"),
            ("好奇", "curious"),
            ("谢谢", "grateful"),
        ]

        for message, expected_emotion in test_cases:
            resp = await client.post("/api/emotion/analyze", params={"message": message})
            assert resp.status_code == 200
            data = resp.json()
            emotion = data["emotion"]
            # 主情绪应匹配（允许降级到neutral）
            if emotion["primary"] != "neutral":
                assert emotion["primary"] == expected_emotion, \
                    f"消息'{message}'期望情绪{expected_emotion}，实际{emotion['primary']}"
            # VRM映射应完整
            assert "vrm_map" in data
            vrm = data["vrm_map"]
            assert "expression" in vrm
            assert "action" in vrm
