"""
CompanionOS Agent路由器 - Phase 2 升级
LLM增强意图识别 + 多Agent并行调度 + 流式返回 + 会话管理 + Eigent四Agent协同

增强内容：
- LLM增强意图识别
- 多Agent并行调度优化
- 增强流式对话（情绪先行+回复流式+VRM同步）
- 会话上下文增强（情绪历史+意图历史+记忆联动）
"""

import asyncio
import contextlib
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from agent_bridge.eigent_adapter import EigentAdapter
from agent_bridge.hermes_adapter import HermesAdapter
from agent_bridge.neuro_adapter import NeuroAdapter

from .intent_classifier import classify_intent_with_llm

# ==================== 会话管理 ====================


class ChatSession:
    """对话会话"""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.history: list[dict] = []
        self.intent_history: list[str] = []
        self.emotion_history: list[str] = []
        self.created_at = datetime.now().isoformat()
        self.last_active = datetime.now().isoformat()
        self.metadata: dict = {}

    def add_message(self, role: str, content: str, intent: str = "", emotion: str = ""):
        """添加消息"""
        self.history.append({
            "role": role,
            "content": content,
            "intent": intent,
            "emotion": emotion,
            "timestamp": datetime.now().isoformat(),
        })
        if intent:
            self.intent_history.append(intent)
        if emotion:
            self.emotion_history.append(emotion)
        self.last_active = datetime.now().isoformat()

    def get_recent_context(self, limit: int = 5) -> dict:
        """获取最近上下文"""
        recent = self.history[-limit:] if self.history else []
        return {
            "recent_messages": recent,
            "previous_emotion": self.emotion_history[-1] if self.emotion_history else None,
            "previous_intent": self.intent_history[-1] if self.intent_history else None,
            "message_count": len(self.history),
            "dominant_intent": self._get_dominant_intent(),
        }

    def _get_dominant_intent(self) -> str:
        """获取会话主导意图"""
        if not self.intent_history:
            return "neutral"
        counts: dict[str, int] = {}
        for intent in self.intent_history[-10:]:
            counts[intent] = counts.get(intent, 0) + 1
        return max(counts, key=counts.get) if counts else "neutral"


class SessionManager:
    """会话管理器"""

    def __init__(self, max_sessions: int = 100, session_ttl_minutes: int = 60):
        self._sessions: dict[str, ChatSession] = {}
        self.max_sessions = max_sessions
        self.session_ttl_minutes = session_ttl_minutes

    def create_session(self) -> str:
        """创建会话"""
        self._cleanup()
        session_id = str(uuid.uuid4())[:12]
        self._sessions[session_id] = ChatSession(session_id)
        return session_id

    def get_session(self, session_id: str) -> ChatSession | None:
        """获取会话"""
        return self._sessions.get(session_id)

    def close_session(self, session_id: str):
        """关闭会话"""
        self._sessions.pop(session_id, None)

    def _cleanup(self):
        """清理过期会话"""
        if len(self._sessions) >= self.max_sessions:
            sorted_sessions = sorted(
                self._sessions.items(),
                key=lambda x: x[1].last_active,
            )
            for sid, _ in sorted_sessions[:len(sorted_sessions) // 2]:
                del self._sessions[sid]

    def list_sessions(self) -> list[dict]:
        """列出所有会话"""
        return [
            {
                "session_id": s.session_id,
                "message_count": len(s.history),
                "created_at": s.created_at,
                "last_active": s.last_active,
                "dominant_intent": s._get_dominant_intent(),
            }
            for s in self._sessions.values()
        ]


# ==================== 多Agent调度器 ====================


class AgentScheduler:
    """多Agent调度器 - 并行/串行调度"""

    @staticmethod
    async def dispatch_sequential(tasks: list[dict]) -> list[dict]:
        """串行调度"""
        results = []
        for task in tasks:
            coro = task["coro"]
            try:
                result = await coro
                results.append({"status": "success", "result": result})
            except Exception as e:
                results.append({"status": "error", "error": str(e)})
        return results

    @staticmethod
    async def dispatch_parallel(tasks: list[dict]) -> list[dict]:
        """并行调度"""
        coros = [task["coro"] for task in tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)
        return [
            {"status": "success", "result": r} if not isinstance(r, Exception)
            else {"status": "error", "error": str(r)}
            for r in results
        ]


# ==================== Agent路由器核心 ====================


class AgentRouter:
    """意图识别 + 多Agent智能路由器 - Phase 2升级"""

    def __init__(self, data_dir: str = ""):
        self.hermes = HermesAdapter(data_dir)
        self.neuro = NeuroAdapter(data_dir)
        self.eigent = EigentAdapter()
        self.sessions = SessionManager()
        self.data_dir = data_dir

        # 记忆桥接
        self._memory_bridge = None
        self._memory_sync = None

    def set_memory_bridge(self, memory_bridge, memory_sync=None):
        """设置记忆桥接"""
        self._memory_bridge = memory_bridge
        self._memory_sync = memory_sync
        # 同步到Neuro
        self.neuro.set_memory_bridge(memory_bridge)

    async def route(self, message: str, context: dict | None = None) -> dict:
        """
        路由用户消息到对应引擎

        Args:
            message: 用户输入消息
            context: 上下文信息

        Returns:
            dict: 路由结果
        """
        context = context or {}
        session_id = context.get("session_id", "")

        # 获取/创建会话
        if session_id:
            session = self.sessions.get_session(session_id)
            if not session:
                session_id = self.sessions.create_session()
                session = self.sessions.get_session(session_id)
        else:
            session_id = self.sessions.create_session()
            session = self.sessions.get_session(session_id)

        # 合并上下文
        session_context = session.get_recent_context()
        merged_context = {**session_context, **context}

        # 1. LLM增强意图识别
        classification = await classify_intent_with_llm(message)
        intent = classification["intent"]

        # 2. 路由到对应引擎
        result = await self._dispatch(message, intent, merged_context, session_id, classification)

        # 3. 记录会话
        session.add_message(
            role="user",
            content=message,
            intent=intent,
            emotion=result.get("emotion", ""),
        )
        session.add_message(
            role="assistant",
            content=result.get("content", ""),
            intent=intent,
            emotion=result.get("emotion", ""),
        )

        result["session_id"] = session_id
        result["intent"] = intent
        result["intent_confidence"] = classification.get("confidence", 0)
        result["llm_enhanced"] = classification.get("llm_enhanced", False)

        # 4. 同步记忆
        if self._memory_sync:
            try:
                await self._memory_sync.sync_interaction({
                    "user_input": message,
                    "intent": intent,
                    "response": result.get("content", ""),
                    "emotion": result.get("emotion"),
                })
            except Exception as e:
                print(f"[AgentRouter] 记忆同步失败: {e}")

        return result

    async def _dispatch(
        self,
        message: str,
        intent: str,
        context: dict,
        session_id: str,
        classification: dict = None,
    ) -> dict:
        """调度到对应引擎"""
        classification = classification or {}
        eigent_agents = classification.get("eigent_agents", [])

        if intent == "work":
            # 纯办公意图 → Hermes + Eigent
            result = await self.hermes.process(message, context, session_id)

            # 检查是否需要Eigent Agent执行具体任务
            eigent_tasks = self._extract_eigent_tasks(message, eigent_agents)
            if eigent_tasks:
                eigent_results = []
                for task in eigent_tasks:
                    eigent_result = await self.eigent.execute(
                        agent_type=task["agent_type"],
                        action=task["action"],
                        parameters=task.get("parameters", {}),
                    )
                    eigent_results.append(eigent_result)
                result["eigent_results"] = eigent_results

            return {
                "content": result.get("content", ""),
                "companion_remark": None,
                "emotion": None,
                "vrm_action": None,
                "engine": "hermes",
            }

        elif intent in ("emotional", "greeting"):
            # 纯情感意图 → Neuro-sama
            result = await self.neuro.process(message, context)

            return {
                "content": result.get("content", ""),
                "companion_remark": None,
                "emotion": result.get("emotion", "neutral"),
                "vrm_action": result.get("vrm_action", "idle"),
                "vrm_expression": result.get("vrm_expression", "neutral"),
                "emotion_detail": result.get("emotion_detail"),
                "vrm_map": result.get("vrm_map"),
                "engine": "neuro-sama",
            }

        else:  # mixed
            # 混合意图 → 双引擎并行
            hermes_task = self.hermes.process(message, context, session_id)
            neuro_task = self.neuro.process(message, context)
            work_result, emotion_result = await asyncio.gather(hermes_task, neuro_task)

            # 如果有Eigent任务，也并行执行
            eigent_tasks = self._extract_eigent_tasks(message, eigent_agents)
            eigent_results = []
            if eigent_tasks:
                eigent_coros = [
                    self.eigent.execute(
                        agent_type=t["agent_type"],
                        action=t["action"],
                        parameters=t.get("parameters", {}),
                    )
                    for t in eigent_tasks
                ]
                eigent_results = await asyncio.gather(*eigent_coros)

            result = {
                "content": work_result.get("content", ""),
                "companion_remark": emotion_result.get("content", ""),
                "emotion": emotion_result.get("emotion", "neutral"),
                "vrm_action": emotion_result.get("vrm_action", "idle"),
                "vrm_expression": emotion_result.get("vrm_expression", "neutral"),
                "emotion_detail": emotion_result.get("emotion_detail"),
                "vrm_map": emotion_result.get("vrm_map"),
                "engine": "mixed",
            }

            if eigent_results:
                result["eigent_results"] = list(eigent_results)

            return result

    def _extract_eigent_tasks(self, message: str, suggested_agents: list[str] = None) -> list[dict]:
        """从消息中提取Eigent任务"""
        tasks = []
        msg_lower = message.lower()
        agents = set(suggested_agents or [])

        # 浏览器相关
        browser_keywords = ["搜索", "查", "浏览", "网页", "search", "browse", "scrape", "crawl", "打开网址"]
        if "browser" in agents or any(kw in msg_lower for kw in browser_keywords):
            tasks.append({
                "agent_type": "browser",
                "action": "search",
                "parameters": {"query": message},
            })

        # 文档相关
        doc_keywords = ["文档", "写", "报告", "转换", "格式化", "document", "create doc", "生成报告", "周报"]
        if "document" in agents or any(kw in msg_lower for kw in doc_keywords):
            action = "generate" if any(kw in msg_lower for kw in ["生成", "写", "报告", "周报"]) else "create"
            tasks.append({
                "agent_type": "document",
                "action": action,
                "parameters": {"title": message[:30], "type": "report"},
            })

        # 代码相关
        code_keywords = ["代码", "运行", "执行", "debug", "code", "run", "execute", "deploy", "编程", "脚本"]
        if "developer" in agents or any(kw in msg_lower for kw in code_keywords):
            tasks.append({
                "agent_type": "developer",
                "action": "write_code",
                "parameters": {"language": "python", "description": message},
            })

        # 多模态相关
        mm_keywords = ["图片", "照片", "视频", "音频", "image", "video", "audio", "ocr", "识别"]
        if "multimodal" in agents or any(kw in msg_lower for kw in mm_keywords):
            tasks.append({
                "agent_type": "multimodal",
                "action": "describe",
                "parameters": {"content": message},
            })

        return tasks

    async def chat(self, message: str, session_id: str | None = None, context: dict | None = None) -> dict:
        """便捷方法：完整对话流程"""
        ctx = context or {}
        if session_id:
            ctx["session_id"] = session_id
        return await self.route(message, ctx)

    # ==================== 流式对话 ====================

    async def stream_chat(
        self,
        message: str,
        session_id: str | None = None,
        context: dict | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        流式对话（增强版：情绪先行+VRM同步）

        Yields:
            str: SSE格式的JSON数据
        """
        context = context or {}
        if session_id:
            context["session_id"] = session_id

        # 1. LLM增强意图识别
        classification = await classify_intent_with_llm(message)
        intent = classification["intent"]

        # 2. 发送意图信息
        yield json.dumps({
            "type": "intent",
            "intent": intent,
            "confidence": classification.get("confidence", 0),
            "llm_enhanced": classification.get("llm_enhanced", False),
            "eigent_agents": classification.get("eigent_agents", []),
        }, ensure_ascii=False)

        if intent in ("emotional", "greeting"):
            # 情感路径 → Neuro-sama流式
            async for chunk in self.neuro.stream_process(message, context, session_id):
                yield chunk

        elif intent == "work":
            # 办公路径 → Hermes流式 + Eigent
            async for chunk in self.hermes.stream_process(message, context, session_id):
                yield chunk

            # Eigent任务（如果有）
            eigent_tasks = self._extract_eigent_tasks(message, classification.get("eigent_agents"))
            if eigent_tasks:
                for task in eigent_tasks:
                    result = await self.eigent.execute(
                        agent_type=task["agent_type"],
                        action=task["action"],
                        parameters=task.get("parameters", {}),
                    )
                    yield json.dumps({
                        "type": "eigent_result",
                        "data": result,
                    }, ensure_ascii=False)

        else:
            # 混合路径 → 先Neuro情绪，再Hermes办公
            emotion_content = ""
            async for chunk in self.neuro.stream_process(message, context, session_id):
                try:
                    data = json.loads(chunk)
                    if data.get("type") == "done":
                        emotion_content = data.get("content", "")
                    yield json.dumps({**data, "channel": "emotion"}, ensure_ascii=False)
                except json.JSONDecodeError:
                    yield chunk

            # 办公流式
            async for chunk in self.hermes.stream_process(message, context, session_id):
                try:
                    data = json.loads(chunk)
                    yield json.dumps({**data, "channel": "work"}, ensure_ascii=False)
                except json.JSONDecodeError:
                    yield chunk

            # Eigent任务
            eigent_tasks = self._extract_eigent_tasks(message, classification.get("eigent_agents"))
            if eigent_tasks:
                for task in eigent_tasks:
                    result = await self.eigent.execute(
                        agent_type=task["agent_type"],
                        action=task["action"],
                        parameters=task.get("parameters", {}),
                    )
                    yield json.dumps({
                        "type": "eigent_result",
                        "data": result,
                    }, ensure_ascii=False)

            yield json.dumps({
                "type": "done",
                "companion_remark": emotion_content,
                "engine": "mixed",
            }, ensure_ascii=False)

        # 同步记忆
        if self._memory_sync:
            with contextlib.suppress(Exception):
                await self._memory_sync.sync_interaction({
                    "user_input": message,
                    "intent": intent,
                    "response": "",
                    "emotion": None,
                })

    # ==================== 会话API ====================

    def create_session(self) -> str:
        """创建新会话"""
        return self.sessions.create_session()

    def get_session_history(self, session_id: str, limit: int = 20) -> list[dict]:
        """获取会话历史"""
        session = self.sessions.get_session(session_id)
        if session:
            return session.history[-limit:]
        return []

    def close_session(self, session_id: str):
        """关闭会话"""
        self.sessions.close_session(session_id)

    def list_sessions(self) -> list[dict]:
        """列出所有会话"""
        return self.sessions.list_sessions()
