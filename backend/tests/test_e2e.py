"""端到端集成测试 - 验证核心功能链路"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


class TestE2EFlows:
    """端到端核心流程测试"""

    @pytest.mark.asyncio
    async def test_health_to_chat_flow(self, client):
        """健康检查 → 发送消息 → 获取回复"""
        resp = await client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "services" in data

        chat_resp = await client.post("/api/chat", json={
            "message": "你好",
        })
        assert chat_resp.status_code == 200
        chat_data = chat_resp.json()
        assert "content" in chat_data or "reply" in chat_data

    @pytest.mark.asyncio
    async def test_emotion_to_vrm_flow(self, client):
        """情绪分析 → VRM 动作映射"""
        resp = await client.post("/api/emotion/analyze", params={"message": "今天心情真好！"})
        assert resp.status_code == 200
        data = resp.json()
        assert "emotion" in data
        assert "vrm_action" in data or "action" in data

    @pytest.mark.asyncio
    async def test_memory_read_write_flow(self, client):
        """写入记忆 → 读取记忆"""
        write_resp = await client.put("/api/memory/work", json={
            "label": "work",
            "value": "测试记忆内容",
        })
        assert write_resp.status_code == 200

        read_resp = await client.get("/api/memory/work")
        assert read_resp.status_code == 200
        assert read_resp.json().get("value") == "测试记忆内容"

    @pytest.mark.asyncio
    async def test_workflow_create_execute_flow(self, client):
        """创建工作流 → 执行工作流"""
        create_resp = await client.post("/api/workflow", json={
            "name": "E2E测试工作流",
            "description": "自动测试",
            "nodes": [
                {"id": "n1", "type": "hermesLLM", "label": "LLM", "config": {"prompt": "你好"}, "position": {}},
            ],
            "edges": [],
        })
        assert create_resp.status_code == 200
        wf_id = create_resp.json().get("id", "")

        exec_resp = await client.post(f"/api/workflow/{wf_id}/execute", json={"inputs": {}})
        assert exec_resp.status_code == 200

    @pytest.mark.asyncio
    async def test_tts_flow(self, client):
        """TTS 合成（验证语音链路）"""
        tts_resp = await client.post("/api/voice/tts", params={
            "text": "你好，我是CompanionOS",
        })
        assert tts_resp.status_code == 200
        tts_data = tts_resp.json()
        assert "engine" in tts_data or "audio" in tts_data or "file" in tts_data or "path" in tts_data

    @pytest.mark.asyncio
    async def test_security_encrypt_decrypt_flow(self, client):
        """加密 → 解密 链路（通过 EncryptionManager 直接验证）"""
        from server import state
        encrypted = state.encryption.encrypt("敏感信息测试")
        assert encrypted != "敏感信息测试"

        decrypted = state.encryption.decrypt(encrypted)
        assert decrypted == "敏感信息测试"

    @pytest.mark.asyncio
    async def test_config_check_flow(self, client):
        """配置检查 API"""
        resp = await client.get("/api/config/check")
        assert resp.status_code == 200
        data = resp.json()
        assert "llm_ready" in data
        assert "engines" in data
        assert "recommendation" in data
