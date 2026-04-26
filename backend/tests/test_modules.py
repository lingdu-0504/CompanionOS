"""
CompanionOS E2E测试 - 第5部分：记忆/伴侣/意图/工作流/语音/安全API
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


class TestMemoryAPI:
    """记忆系统API"""

    @pytest.mark.asyncio
    async def test_list_memory_blocks(self, client):
        """GET /api/memory - 列出所有记忆块"""
        resp = await client.get("/api/memory")
        assert resp.status_code == 200
        data = resp.json()

        assert "human" in data
        assert "persona" in data
        assert "work" in data
        assert "emotional" in data
        assert "skills" in data

    @pytest.mark.asyncio
    async def test_get_memory_block(self, client):
        """GET /api/memory/{block_type} - 获取指定记忆块"""
        resp = await client.get("/api/memory/persona")
        assert resp.status_code == 200
        data = resp.json()

        assert "label" in data
        assert "value" in data
        assert data["label"] == "persona"

    @pytest.mark.asyncio
    async def test_update_memory_block(self, client):
        """PUT /api/memory/{block_type} - 更新记忆块"""
        resp = await client.put("/api/memory/work", json={
            "label": "work",
            "value": "E2E测试写入的工作记忆",
        })
        assert resp.status_code == 200
        data = resp.json()

        assert data["label"] == "work"
        assert data["value"] == "E2E测试写入的工作记忆"

        # 验证读取
        resp2 = await client.get("/api/memory/work")
        assert resp2.json()["value"] == "E2E测试写入的工作记忆"


class TestCompanionAPI:
    """伴侣状态API"""

    @pytest.mark.asyncio
    async def test_get_companion_state(self, client):
        """GET /api/companion/state - 获取伴侣状态"""
        resp = await client.get("/api/companion/state")
        assert resp.status_code == 200
        data = resp.json()

        assert data["name"] == "小暖"
        assert "affection" in data
        assert "trust" in data
        assert "intimacy" in data
        assert "comfort" in data
        assert "respect" in data
        assert "relation_level" in data
        assert "relation_name" in data

    @pytest.mark.asyncio
    async def test_companion_interact(self, client):
        """POST /api/companion/interact - 伴侣互动"""
        resp = await client.post("/api/companion/interact", params={
            "interaction_type": "chat",
            "delta": 1.0,
        })
        assert resp.status_code == 200
        data = resp.json()

        assert data["affection"] > 0  # chat会增加affection

    @pytest.mark.asyncio
    async def test_relation_levels(self, client):
        """GET /api/companion/relation-levels - 获取关系等级"""
        resp = await client.get("/api/companion/relation-levels")
        assert resp.status_code == 200
        data = resp.json()

        levels = data["levels"]
        assert len(levels) == 8
        assert levels[0]["name"] == "陌生人"
        assert levels[-1]["name"] == "灵魂伴侣"


class TestIntentAPI:
    """意图分类API"""

    @pytest.mark.asyncio
    async def test_classify_intent_work(self, client):
        """POST /api/intent/classify - 办公意图"""
        resp = await client.post("/api/intent/classify", params={
            "message": "帮我写一份周报",
            "use_llm": False,
        })
        assert resp.status_code == 200
        data = resp.json()

        assert data["intent"] == "work"
        assert data["confidence"] > 0
        assert len(data["keywords_matched"]) > 0

    @pytest.mark.asyncio
    async def test_classify_intent_emotional(self, client):
        """POST /api/intent/classify - 情感意图"""
        resp = await client.post("/api/intent/classify", params={
            "message": "我好累啊",
            "use_llm": False,
        })
        assert resp.status_code == 200
        data = resp.json()

        assert data["intent"] == "emotional"

    @pytest.mark.asyncio
    async def test_classify_intent_mixed(self, client):
        """POST /api/intent/classify - 混合意图"""
        resp = await client.post("/api/intent/classify", params={
            "message": "加班写代码好累啊",
            "use_llm": False,
        })
        assert resp.status_code == 200
        data = resp.json()

        assert data["intent"] == "mixed"
        assert len(data["keywords_matched"]) > 0

    @pytest.mark.asyncio
    async def test_classify_intent_greeting(self, client):
        """POST /api/intent/classify - 问候意图"""
        resp = await client.post("/api/intent/classify", params={
            "message": "你好",
            "use_llm": False,
        })
        assert resp.status_code == 200
        data = resp.json()

        assert data["intent"] == "greeting"

    @pytest.mark.asyncio
    async def test_classify_intent_with_eigent(self, client):
        """POST /api/intent/classify - 含Eigent关键词"""
        resp = await client.post("/api/intent/classify", params={
            "message": "帮我搜索一下最新的AI论文",
            "use_llm": False,
        })
        assert resp.status_code == 200
        data = resp.json()

        assert "browser" in data["eigent_agents"]

    @pytest.mark.asyncio
    async def test_classify_intent_llm_enhanced(self, client):
        """POST /api/intent/classify?use_llm=true - LLM增强分类"""
        resp = await client.post("/api/intent/classify", params={
            "message": "今天心情不太好，能帮我整理一下会议纪要吗",
            "use_llm": True,
        })
        assert resp.status_code == 200
        data = resp.json()

        assert "intent" in data
        assert "llm_enhanced" in data
        # 即使LLM不可用，应降级到关键词匹配
        assert data["intent"] in ("work", "emotional", "mixed", "greeting")


class TestWorkflowAPI:
    """工作流API"""

    @pytest.mark.asyncio
    async def test_list_workflows(self, client):
        """GET /api/workflow - 列出工作流"""
        resp = await client.get("/api/workflow")
        assert resp.status_code == 200
        data = resp.json()
        assert "workflows" in data

    @pytest.mark.asyncio
    async def test_create_and_execute_workflow(self, client):
        """POST /api/workflow + POST /api/workflow/{id}/execute - 创建并执行工作流"""
        # 创建
        resp = await client.post("/api/workflow", json={
            "name": "E2E测试工作流",
            "description": "自动测试创建",
            "nodes": [
                {"id": "n1", "type": "hermesLLM", "label": "LLM处理", "config": {"prompt": "测试"}, "position": {}},
                {"id": "n2", "type": "emotion", "label": "情感交互", "config": {}, "position": {}},
            ],
            "edges": [
                {"id": "e1", "source": "n1", "target": "n2"},
            ],
        })
        assert resp.status_code == 200
        wf_id = resp.json()["id"]

        # 执行
        resp = await client.post(f"/api/workflow/{wf_id}/execute", json={"inputs": {}})
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "completed"
        assert "results" in data

    @pytest.mark.asyncio
    async def test_list_node_types(self, client):
        """GET /api/workflow/node-types - 列出节点类型"""
        resp = await client.get("/api/workflow/node-types")
        assert resp.status_code == 200
        data = resp.json()

        node_types = data["node_types"]
        assert len(node_types) >= 10
        assert "hermesLLM" in node_types
        assert "emotion" in node_types
        assert "browser" in node_types


class TestVoiceAPI:
    """语音API"""

    @pytest.mark.asyncio
    async def test_tts(self, client):
        """POST /api/voice/tts - 语音合成"""
        resp = await client.post("/api/voice/tts", params={"text": "你好，测试语音合成"})
        assert resp.status_code == 200
        data = resp.json()
        # edge-tts可能未安装
        assert data["engine"] == "edge-tts"
        assert data["status"] in ("completed", "not_installed", "error")

    @pytest.mark.asyncio
    async def test_list_voice_engines(self, client):
        """GET /api/voice/engines - 列出TTS引擎"""
        resp = await client.get("/api/voice/engines")
        assert resp.status_code == 200
        data = resp.json()

        engines = data["engines"]
        assert len(engines) >= 1
        assert engines[0]["name"] == "edge"


class TestSecurityAPI:
    """安全API"""

    @pytest.mark.asyncio
    async def test_list_keys(self, client):
        """GET /api/security/keys - 列出密钥"""
        resp = await client.get("/api/security/keys")
        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data

    @pytest.mark.asyncio
    async def test_approve_reject(self, client):
        """POST /api/security/approve/{id} + reject/{id}"""
        # 不存在的approval_id
        resp = await client.post("/api/security/approve/nonexistent")
        assert resp.status_code == 200
        assert resp.json()["approved"] is False

        resp = await client.post("/api/security/reject/nonexistent")
        assert resp.status_code == 200
        assert resp.json()["rejected"] is False
