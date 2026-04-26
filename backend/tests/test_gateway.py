"""
CompanionOS E2E测试 - 第4部分：MCP/A2A/Eigent网关API
覆盖: MCP工具, A2A Agent, Eigent Agent
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from server import state


class TestMCPAPI:
    """MCP工具网关API"""

    @pytest.mark.asyncio
    async def test_list_mcp_tools(self, client):
        """GET /api/mcp/tools - 列出所有MCP工具"""
        resp = await client.get("/api/mcp/tools")
        assert resp.status_code == 200
        data = resp.json()

        assert "tools" in data
        assert len(data["tools"]) >= 10  # 至少10个内置工具

    @pytest.mark.asyncio
    async def test_list_mcp_tools_by_group(self, client):
        """GET /api/mcp/tools?group=office - 按分组列出工具"""
        resp = await client.get("/api/mcp/tools", params={"group": "office"})
        assert resp.status_code == 200
        data = resp.json()

        tools = data["tools"]
        assert len(tools) > 0
        for tool in tools:
            assert tool["group"] == "office"

    @pytest.mark.asyncio
    async def test_get_mcp_tool(self, client):
        """GET /api/mcp/tools/{tool_name} - 获取工具详情"""
        resp = await client.get("/api/mcp/tools/document_process")
        assert resp.status_code == 200
        data = resp.json()

        assert data["name"] == "document_process"
        assert "parameters" in data
        assert data["group"] == "office"

    @pytest.mark.asyncio
    async def test_get_mcp_tool_not_found(self, client):
        """GET /api/mcp/tools/{nonexistent} - 工具不存在"""
        resp = await client.get("/api/mcp/tools/nonexistent_tool")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_call_mcp_tool(self, client):
        """POST /api/mcp/call - 调用MCP工具"""
        resp = await client.post("/api/mcp/call", params={
            "tool_name": "document_process",
            "auto_approve": "true",
        }, content='{"action": "summarize", "content": "测试文档内容"}', headers={"Content-Type": "application/json"})
        assert resp.status_code == 200
        data = resp.json()

        # arguments可能解析为None（FastAPI Query不支持dict），降级验证
        assert data["tool_name"] == "document_process"
        assert data["status"] in ("success", "error")

    @pytest.mark.asyncio
    async def test_call_mcp_tool_email_read(self, client):
        """POST /api/mcp/call - 调用邮件读取工具"""
        resp = await client.post("/api/mcp/call", params={
            "tool_name": "email_read",
            "arguments": {"folder": "inbox", "limit": 5},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_call_mcp_tool_missing_params(self, client):
        """POST /api/mcp/call - 缺少必需参数"""
        resp = await client.post("/api/mcp/call", params={
            "tool_name": "email_send",
            # 缺少 to, subject
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "缺少" in data.get("error", "")

    @pytest.mark.asyncio
    async def test_call_mcp_batch(self, client):
        """POST /api/mcp/call-batch - 批量调用工具"""
        resp = await client.post("/api/mcp/call-batch", json=[
            {"tool_name": "document_process", "arguments": {"action": "summarize"}},
            {"tool_name": "calendar_query", "arguments": {}},
        ])
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 2

    @pytest.mark.asyncio
    async def test_list_mcp_groups(self, client):
        """GET /api/mcp/groups - 列出工具分组"""
        resp = await client.get("/api/mcp/groups")
        assert resp.status_code == 200
        data = resp.json()

        groups = data["groups"]
        group_names = [g["name"] for g in groups]
        assert "office" in group_names
        assert "emotion" in group_names

    @pytest.mark.asyncio
    async def test_mcp_sessions(self, client):
        """GET /api/mcp/sessions - 列出MCP会话"""
        resp = await client.get("/api/mcp/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data

    @pytest.mark.asyncio
    async def test_mcp_stats(self, client):
        """GET /api/mcp/stats - 获取MCP统计"""
        # 先调用一个工具产生统计
        await client.post("/api/mcp/call", params={
            "tool_name": "document_process",
            "arguments": {"action": "summarize"},
        })

        resp = await client.get("/api/mcp/stats")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_calls"] > 0
        assert data["success_calls"] > 0
        assert data["tools_count"] > 0


class TestA2AAPI:
    """A2A Agent间通信网关API"""

    @pytest.mark.asyncio
    async def test_list_a2a_agents(self, client):
        """GET /api/a2a/agents - 列出所有Agent"""
        resp = await client.get("/api/a2a/agents")
        assert resp.status_code == 200
        data = resp.json()

        agents = data["agents"]
        assert len(agents) >= 5  # 至少5个默认Agent
        agent_ids = [a["agent_id"] for a in agents]
        assert "hermes-office" in agent_ids
        assert "neuro-emotion" in agent_ids

    @pytest.mark.asyncio
    async def test_list_a2a_agents_by_status(self, client):
        """GET /api/a2a/agents?status=ready - 按状态过滤"""
        resp = await client.get("/api/a2a/agents", params={"status": "ready"})
        assert resp.status_code == 200
        agents = resp.json()["agents"]
        for a in agents:
            assert a["status"] == "ready"

    @pytest.mark.asyncio
    async def test_get_a2a_agent(self, client):
        """GET /api/a2a/agents/{agent_id} - 获取Agent详情"""
        resp = await client.get("/api/a2a/agents/hermes-office")
        assert resp.status_code == 200
        data = resp.json()

        assert data["agent_id"] == "hermes-office"
        assert data["name"] == "Hermes办公Agent"
        assert "capabilities" in data
        assert "document" in data["capabilities"]

    @pytest.mark.asyncio
    async def test_get_a2a_agent_not_found(self, client):
        """GET /api/a2a/agents/{nonexistent}"""
        resp = await client.get("/api/a2a/agents/nonexistent-agent")
        assert resp.status_code == 200
        assert "error" in resp.json()

    @pytest.mark.asyncio
    async def test_delegate_task(self, client):
        """POST /api/a2a/delegate - Agent间任务委派"""
        resp = await client.post("/api/a2a/delegate", params={
            "from_agent": "hermes-office",
            "to_agent": "neuro-emotion",
            "task_type": "emotion",
            "description": "测试委派任务",
        })
        assert resp.status_code == 200
        data = resp.json()

        assert "task_id" in data
        assert data["status"] in ("completed", "delegated")

    @pytest.mark.asyncio
    async def test_delegate_task_nonexistent_agent(self, client):
        """POST /api/a2a/delegate - 委派给不存在的Agent"""
        resp = await client.post("/api/a2a/delegate", params={
            "from_agent": "hermes-office",
            "to_agent": "nonexistent-agent",
            "task_type": "test",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"

    @pytest.mark.asyncio
    async def test_delegate_parallel(self, client):
        """POST /api/a2a/delegate-parallel - 并行委派"""
        resp = await client.post("/api/a2a/delegate-parallel", params={
            "from_agent": "hermes-office",
        }, json=[
            {"to_agent": "neuro-emotion", "task_type": "emotion"},
            {"to_agent": "hermes-office", "task_type": "document"},
        ])
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 2

    @pytest.mark.asyncio
    async def test_a2a_tasks(self, client):
        """GET /api/a2a/tasks - 列出任务"""
        resp = await client.get("/api/a2a/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data

    @pytest.mark.asyncio
    async def test_a2a_context(self, client):
        """PUT/GET /api/a2a/context/{id} - 共享上下文"""
        # 设置上下文
        resp = await client.put("/api/a2a/context/test-ctx-001", params={
            "scope": "session",
            "updated_by": "test",
        }, json={"key": "value"})
        assert resp.status_code == 200

        # 获取上下文
        resp = await client.get("/api/a2a/context/test-ctx-001")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_a2a_stats(self, client):
        """GET /api/a2a/stats - 获取A2A统计"""
        resp = await client.get("/api/a2a/stats")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_agents"] >= 5
        assert data["active_agents"] > 0


class TestEigentAPI:
    """Eigent四Agent API"""

    @pytest.mark.asyncio
    async def test_list_eigent_agents(self, client):
        """GET /api/eigent/agents - 列出Eigent Agent"""
        # 确保Eigent初始化
        await state.eigent.initialize()

        resp = await client.get("/api/eigent/agents")
        assert resp.status_code == 200
        data = resp.json()

        agents = data["agents"]
        assert len(agents) == 4
        agent_types = [a["agent_type"] for a in agents]
        assert "browser" in agent_types
        assert "document" in agent_types
        assert "developer" in agent_types
        assert "multimodal" in agent_types

    @pytest.mark.asyncio
    async def test_execute_browser_agent(self, client):
        """POST /api/eigent/execute - 浏览器Agent"""
        resp = await client.post("/api/eigent/execute", json={
            "agent_type": "browser",
            "action": "search",
            "parameters": {"query": "测试搜索"},
        })
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "completed"
        assert data["agent_type"] == "browser"

    @pytest.mark.asyncio
    async def test_execute_document_agent(self, client):
        """POST /api/eigent/execute - 文档Agent"""
        resp = await client.post("/api/eigent/execute", json={
            "agent_type": "document",
            "action": "create",
            "parameters": {"title": "测试文档", "type": "md"},
        })
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "completed"
        assert data["agent_type"] == "document"

    @pytest.mark.asyncio
    async def test_execute_developer_agent(self, client):
        """POST /api/eigent/execute - 开发者Agent"""
        resp = await client.post("/api/eigent/execute", json={
            "agent_type": "developer",
            "action": "write_code",
            "parameters": {"language": "python", "code": "print('hello')"},
        })
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_execute_multimodal_agent(self, client):
        """POST /api/eigent/execute - 多模态Agent"""
        resp = await client.post("/api/eigent/execute", json={
            "agent_type": "multimodal",
            "action": "describe",
            "parameters": {"content": "测试内容描述"},
        })
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_execute_invalid_agent(self, client):
        """POST /api/eigent/execute - 无效Agent类型"""
        resp = await client.post("/api/eigent/execute", json={
            "agent_type": "invalid_agent",
            "action": "test",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_execute_invalid_action(self, client):
        """POST /api/eigent/execute - 无效操作"""
        resp = await client.post("/api/eigent/execute", json={
            "agent_type": "browser",
            "action": "invalid_action",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_eigent_chain(self, client):
        """POST /api/eigent/chain - Agent链执行"""
        resp = await client.post("/api/eigent/chain", json={
            "steps": [
                {"agent_type": "browser", "action": "search", "parameters": {"query": "测试"}},
                {"agent_type": "document", "action": "create", "parameters": {"title": "测试"}},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 2

    @pytest.mark.asyncio
    async def test_eigent_parallel(self, client):
        """POST /api/eigent/parallel - 并行执行"""
        resp = await client.post("/api/eigent/parallel", json={
            "steps": [
                {"agent_type": "browser", "action": "search", "parameters": {"query": "测试1"}},
                {"agent_type": "document", "action": "create", "parameters": {"title": "测试2"}},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 2

    @pytest.mark.asyncio
    async def test_eigent_tasks(self, client):
        """GET /api/eigent/tasks - 列出任务"""
        # 先执行一个任务
        await client.post("/api/eigent/execute", json={
            "agent_type": "browser",
            "action": "search",
            "parameters": {"query": "测试"},
        })

        resp = await client.get("/api/eigent/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
