"""
CompanionOS E2E测试 - 第2部分：对话与SSE流
覆盖: /api/chat, /api/chat/stream, /api/sessions
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


import pytest


class TestChatAPI:
    """对话API"""

    @pytest.mark.asyncio
    async def test_chat_emotional(self, client):
        """POST /api/chat - 情感类消息路由到Neuro-sama"""
        resp = await client.post("/api/chat", json={
            "message": "我好累啊",
            "stream": False,
        })
        assert resp.status_code == 200
        data = resp.json()

        assert "content" in data
        assert data["engine"] in ("neuro-sama", "mixed")
        assert data["session_id"] != ""
        assert "intent" in data
        assert "emotion" in data

    @pytest.mark.asyncio
    async def test_chat_work(self, client):
        """POST /api/chat - 办公类消息路由到Hermes"""
        resp = await client.post("/api/chat", json={
            "message": "帮我写一个周报",
            "stream": False,
        })
        assert resp.status_code == 200
        data = resp.json()

        assert "content" in data
        assert data["intent"] in ("work", "mixed")
        assert data["session_id"] != ""

    @pytest.mark.asyncio
    async def test_chat_greeting(self, client):
        """POST /api/chat - 问候类消息"""
        resp = await client.post("/api/chat", json={
            "message": "你好呀",
            "stream": False,
        })
        assert resp.status_code == 200
        data = resp.json()

        assert "content" in data
        assert data["intent"] in ("greeting", "emotional", "mixed")

    @pytest.mark.asyncio
    async def test_chat_with_session(self, client):
        """POST /api/chat - 带session_id的多轮对话"""
        # 创建会话
        session_resp = await client.post("/api/sessions")
        assert session_resp.status_code == 200
        session_id = session_resp.json()["session_id"]

        # 第一轮
        resp1 = await client.post("/api/chat", json={
            "message": "你好",
            "session_id": session_id,
        })
        assert resp1.status_code == 200

        # 第二轮
        resp2 = await client.post("/api/chat", json={
            "message": "帮我总结一下今天的工作",
            "session_id": session_id,
        })
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_chat_stream(self, client):
        """POST /api/chat/stream - SSE流式对话"""
        resp = await client.post("/api/chat/stream", json={
            "message": "你好呀",
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"

        # 读取SSE流
        content = resp.text
        assert "data:" in content
        assert "[DONE]" in content

    @pytest.mark.asyncio
    async def test_chat_stream_emotional(self, client):
        """POST /api/chat/stream - 情感消息SSE流"""
        resp = await client.post("/api/chat/stream", json={
            "message": "我好想你",
        })
        assert resp.status_code == 200
        content = resp.text

        # 情感类应该先发送emotion事件
        lines = [line for line in content.split("\n") if line.startswith("data: ")]
        assert len(lines) >= 2  # 至少有intent + done


class TestSessionAPI:
    """会话API"""

    @pytest.mark.asyncio
    async def test_create_session(self, client):
        """POST /api/sessions - 创建会话"""
        resp = await client.post("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0

    @pytest.mark.asyncio
    async def test_list_sessions(self, client):
        """GET /api/sessions - 列出会话"""
        # 先创建一个
        await client.post("/api/sessions")

        resp = await client.get("/api/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert len(data["sessions"]) > 0

    @pytest.mark.asyncio
    async def test_session_history(self, client):
        """GET /api/sessions/{id}/history - 获取会话历史"""
        # 创建会话并对话
        session_resp = await client.post("/api/sessions")
        session_id = session_resp.json()["session_id"]

        await client.post("/api/chat", json={
            "message": "测试消息",
            "session_id": session_id,
        })

        # 获取历史
        resp = await client.get(f"/api/sessions/{session_id}/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data
        assert len(data["history"]) > 0

    @pytest.mark.asyncio
    async def test_close_session(self, client):
        """DELETE /api/sessions/{id} - 关闭会话"""
        session_resp = await client.post("/api/sessions")
        session_id = session_resp.json()["session_id"]

        resp = await client.delete(f"/api/sessions/{session_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
