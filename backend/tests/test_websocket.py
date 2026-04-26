"""
CompanionOS E2E测试 - 第6部分：WebSocket实时通信
覆盖: /ws 连接/ping/mcp_list/mcp_call/emotion_update/companion_action/subscribe/a2a/eigent/unknown
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from starlette.testclient import TestClient


class TestWebSocket:
    """WebSocket实时通信"""

    def test_ws_basic_protocol(self):
        """WebSocket基础协议：连接/欢迎/ping/pong/emotion/unknown"""
        from server import app

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            # 1. 连接与欢迎消息
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert "client_id" in data
            assert data["server_version"] == "0.2.0"

            # 2. ping/pong
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
            assert data["type"] == "pong"
            assert "timestamp" in data

            # 3. 情绪更新
            ws.send_json({"type": "emotion_update", "emotion": "happy"})
            data = ws.receive_json()
            assert data["type"] == "emotion_updated"
            assert data["emotion"] == "happy"

            # 4. 未知消息类型
            ws.send_json({"type": "unknown_type"})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "未知" in data["message"]

    def test_ws_mcp_protocol(self):
        """WebSocket MCP协议：工具列表/工具调用"""
        from server import app

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # welcome

            # MCP工具列表
            ws.send_json({"type": "mcp_list"})
            data = ws.receive_json()
            assert data["type"] == "mcp_tools"
            assert isinstance(data["data"], list)
            assert len(data["data"]) > 0

            # MCP工具调用
            ws.send_json({
                "type": "mcp_call",
                "tool_name": "document_process",
                "arguments": {"action": "summarize", "content": "测试"},
            })
            data = ws.receive_json()
            assert data["type"] == "mcp_result"
            assert data["data"]["status"] == "success"

    def test_ws_companion_and_gateway(self):
        """WebSocket伴侣动作/订阅/A2A/Eigent"""
        from server import app

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()  # welcome

            # 伴侣动作
            ws.send_json({
                "type": "companion_action",
                "action": "wave",
                "emotion": "happy",
            })
            data = ws.receive_json()
            assert data["type"] == "action_executed"
            assert data["action"] == "wave"
            assert "vrm_map" in data

            # 订阅
            ws.send_json({"type": "subscribe"})
            data = ws.receive_json()
            assert data["type"] == "subscribed"
            assert data["channel"] == "mcp_events"

            # A2A委派
            ws.send_json({
                "type": "a2a_delegate",
                "from_agent": "hermes-office",
                "to_agent": "neuro-emotion",
                "task_type": "emotion",
            })
            data = ws.receive_json()
            assert data["type"] == "a2a_result"

            # Eigent执行
            ws.send_json({
                "type": "eigent_execute",
                "agent_type": "browser",
                "action": "search",
                "parameters": {"query": "测试"},
            })
            data = ws.receive_json()
            assert data["type"] == "eigent_result"

    @pytest.mark.skip(reason="需要LLM后端，CI环境跳过")
    def test_ws_chat(self):
        """WebSocket对话（需要LLM）"""
        pass

    @pytest.mark.skip(reason="需要LLM后端，CI环境跳过")
    def test_ws_stream_chat(self):
        """WebSocket流式对话（需要LLM）"""
        pass
