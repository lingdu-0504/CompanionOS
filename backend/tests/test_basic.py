"""
CompanionOS E2E测试 - 第1部分：基础API
覆盖: /api/status, /api/health, /api/routes
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


class TestBasicAPI:
    """基础信息API"""

    @pytest.mark.asyncio
    async def test_status(self, client):
        """GET /api/status 返回系统状态"""
        resp = await client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "running"
        assert data["version"] == "0.2.0"
        assert "services" in data
        assert data["services"]["hermes"] == "ready"
        assert data["services"]["neuro-sama"] == "ready"
        assert data["services"]["eigent"] == "ready"
        assert "companion" in data
        assert "tools" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_health(self, client):
        """GET /api/health 健康检查"""
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "healthy"
        assert data["version"] == "0.2.0"
        assert "services" in data
        assert data["services"]["mcp"] > 0
        assert data["services"]["a2a"] > 0
        assert data["services"]["eigent"] >= 0

    @pytest.mark.asyncio
    async def test_routes(self, client):
        """GET /api/routes 列出所有路由"""
        resp = await client.get("/api/routes")
        assert resp.status_code == 200
        data = resp.json()

        assert "routes" in data
        assert data["total"] >= 30  # 至少30个路由
        # 验证关键路由存在
        paths = [r["path"] for r in data["routes"]]
        assert "/api/chat" in paths
        assert "/api/status" in paths
        assert "/api/mcp/tools" in paths
        assert "/api/a2a/agents" in paths
        assert "/api/eigent/agents" in paths
