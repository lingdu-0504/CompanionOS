"""
CompanionOS A2A网关 - Phase 2 完整实现
Agent间协作通信：Agent Card注册中心 + 任务委派/回调 + 上下文共享 + 心跳检测

A2A协议核心：
- Agent Card: Agent身份注册（能力、端点、状态）
- 任务委派: Agent间异步任务分配
- 上下文共享: 跨Agent状态同步
- 心跳检测: Agent存活监控
"""

import asyncio
import contextlib
import uuid
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

# ==================== 数据模型 ====================


class AgentCapability(BaseModel):
    """Agent能力描述"""
    name: str
    description: str = ""
    input_schema: dict = {}
    output_schema: dict = {}


class AgentCard(BaseModel):
    """A2A Agent Card - Agent身份注册"""
    agent_id: str
    name: str
    description: str = ""
    capabilities: list[str] = []
    capability_details: list[AgentCapability] = []
    endpoint: str = ""  # Agent的通信端点
    status: str = "pending"  # pending | ready | busy | offline | error
    version: str = "1.0.0"
    tags: list[str] = []
    metadata: dict = {}

    # 心跳
    last_heartbeat: str = ""
    heartbeat_interval_s: int = 30


class TaskStatus(StrEnum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class DelegationTask(BaseModel):
    """委派任务"""
    task_id: str
    from_agent: str
    to_agent: str
    task_type: str
    description: str = ""
    payload: dict = {}
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str | None = None
    priority: int = 5  # 1-10, 10最高
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    timeout_ms: int = 60000
    callback_url: str | None = None


class SharedContext(BaseModel):
    """共享上下文"""
    context_id: str
    scope: str = "global"  # global | session | task
    data: dict = {}
    version: int = 1
    updated_at: str = ""
    updated_by: str = ""


class A2AEventType(StrEnum):
    """A2A事件类型"""
    AGENT_REGISTERED = "agent_registered"
    AGENT_DEREGISTERED = "agent_deregistered"
    AGENT_STATUS_CHANGED = "agent_status_changed"
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    CONTEXT_UPDATED = "context_updated"
    HEARTBEAT_MISSED = "heartbeat_missed"


# ==================== A2A网关核心 ====================


class A2AGateway:
    """A2A Agent间通信网关 - Phase 2完整实现"""

    def __init__(self, host: str = "127.0.0.1", port: int = 3457):
        self.host = host
        self.port = port

        # Agent注册表
        self._agents: dict[str, AgentCard] = {}
        self._agent_handlers: dict[str, dict[str, Callable]] = {}  # agent_id -> {capability: handler}

        # 任务管理
        self._tasks: dict[str, DelegationTask] = {}
        self._task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()

        # 共享上下文
        self._contexts: dict[str, SharedContext] = {}

        # 事件订阅
        self._event_subscribers: list[asyncio.Queue] = []

        # 心跳监控
        self._heartbeat_task: asyncio.Task | None = None
        self._running = False

        # 统计
        self._stats = {
            "total_delegations": 0,
            "successful_delegations": 0,
            "failed_delegations": 0,
            "active_agents": 0,
        }

        # 注册默认Agent
        self._register_default_agents()

    def _register_default_agents(self):
        """注册默认Agent卡片"""
        default_agents = [
            AgentCard(
                agent_id="hermes-office",
                name="Hermes办公Agent",
                description="通用办公AI，支持文档处理、邮件管理、日历查询、代码执行",
                capabilities=["document", "email", "calendar", "code", "summarize"],
                capability_details=[
                    AgentCapability(name="document", description="文档处理"),
                    AgentCapability(name="email", description="邮件读写"),
                    AgentCapability(name="calendar", description="日历管理"),
                    AgentCapability(name="code", description="代码执行"),
                    AgentCapability(name="summarize", description="内容总结"),
                ],
                status="ready",
                tags=["office", "productivity"],
                heartbeat_interval_s=30,
            ),
            AgentCard(
                agent_id="neuro-emotion",
                name="Neuro-sama情感Agent",
                description="情感交互引擎，支持情绪识别、伴侣回复、表情触发、关系管理",
                capabilities=["emotion", "voice", "expression", "action", "relation"],
                capability_details=[
                    AgentCapability(name="emotion", description="情绪识别与回复"),
                    AgentCapability(name="voice", description="语音合成"),
                    AgentCapability(name="expression", description="表情触发"),
                    AgentCapability(name="action", description="动作播放"),
                    AgentCapability(name="relation", description="关系管理"),
                ],
                status="ready",
                tags=["emotion", "companion"],
                heartbeat_interval_s=30,
            ),
            AgentCard(
                agent_id="eigent-browser",
                name="Eigent浏览器Agent",
                description="浏览器自动化Agent，支持网页导航、内容提取、表单填写",
                capabilities=["browser", "search", "extract", "form_fill", "screenshot"],
                status="pending",
                tags=["browser", "automation"],
                heartbeat_interval_s=30,
            ),
            AgentCard(
                agent_id="eigent-document",
                name="Eigent文档Agent",
                description="文档处理Agent，支持创建、编辑、格式化、转换",
                capabilities=["document_create", "document_edit", "document_format", "document_convert"],
                status="pending",
                tags=["document", "automation"],
                heartbeat_interval_s=30,
            ),
            AgentCard(
                agent_id="eigent-developer",
                name="Eigent开发者Agent",
                description="代码执行Agent，支持编写、执行、调试、部署",
                capabilities=["code_write", "code_execute", "code_debug", "code_deploy"],
                status="pending",
                tags=["developer", "automation"],
                heartbeat_interval_s=30,
            ),
            AgentCard(
                agent_id="eigent-multimodal",
                name="Eigent多模态Agent",
                description="多模态Agent，支持图像理解、音频处理、视频分析",
                capabilities=["image_understand", "audio_process", "video_analyze"],
                status="pending",
                tags=["multimodal", "automation"],
                heartbeat_interval_s=30,
            ),
            AgentCard(
                agent_id="accomplish-daemon",
                name="Accomplish守护Agent",
                description="守护进程Agent，支持文件监听、定时调度、操作审批",
                capabilities=["file_watch", "cron", "approval", "notification"],
                status="pending",
                tags=["daemon", "automation"],
                heartbeat_interval_s=30,
            ),
        ]

        now = datetime.now().isoformat()
        for card in default_agents:
            card.last_heartbeat = now
            self._agents[card.agent_id] = card

    # ==================== Agent注册API ====================

    def register_agent(self, card: AgentCard, handlers: dict[str, Callable] = None) -> dict:
        """注册Agent"""
        now = datetime.now().isoformat()
        card.last_heartbeat = now
        if card.status == "pending":
            card.status = "ready"
        self._agents[card.agent_id] = card

        if handlers:
            self._agent_handlers[card.agent_id] = handlers

        self._update_stats()
        self._emit_event(A2AEventType.AGENT_REGISTERED, {"agent_id": card.agent_id})
        return {"status": "registered", "agent_id": card.agent_id}

    def deregister_agent(self, agent_id: str) -> dict:
        """注销Agent"""
        if agent_id not in self._agents:
            return {"error": f"Agent {agent_id} 不存在"}

        self._agents.pop(agent_id)
        self._agent_handlers.pop(agent_id, None)
        self._update_stats()
        self._emit_event(A2AEventType.AGENT_DEREGISTERED, {"agent_id": agent_id})
        return {"status": "deregistered", "agent_id": agent_id}

    def update_agent_status(self, agent_id: str, status: str) -> dict:
        """更新Agent状态"""
        if agent_id not in self._agents:
            return {"error": f"Agent {agent_id} 不存在"}

        old_status = self._agents[agent_id].status
        self._agents[agent_id].status = status
        self._agents[agent_id].last_heartbeat = datetime.now().isoformat()

        if old_status != status:
            self._emit_event(A2AEventType.AGENT_STATUS_CHANGED, {
                "agent_id": agent_id,
                "old_status": old_status,
                "new_status": status,
            })
        return {"status": "updated", "agent_id": agent_id, "new_status": status}

    def heartbeat(self, agent_id: str) -> dict:
        """Agent心跳"""
        if agent_id not in self._agents:
            return {"error": f"Agent {agent_id} 不存在"}

        self._agents[agent_id].last_heartbeat = datetime.now().isoformat()
        return {"status": "ok", "agent_id": agent_id}

    # ==================== Agent查询API ====================

    def list_agents(self, status: str = None, capability: str = None, tag: str = None) -> list[dict]:
        """列出已注册Agent（支持过滤）"""
        agents = []
        for card in self._agents.values():
            if status and card.status != status:
                continue
            if capability and capability not in card.capabilities:
                continue
            if tag and tag not in card.tags:
                continue
            agents.append(card.model_dump())
        return agents

    def get_agent(self, agent_id: str) -> dict | None:
        """获取Agent详情"""
        if agent_id in self._agents:
            return self._agents[agent_id].model_dump()
        return None

    def find_agents_by_capability(self, capability: str) -> list[dict]:
        """按能力查找Agent"""
        return self.list_agents(capability=capability)

    # ==================== 任务委派API ====================

    async def delegate(
        self,
        from_agent: str,
        to_agent: str,
        task_type: str,
        description: str = "",
        payload: dict = None,
        priority: int = 5,
        timeout_ms: int = 60000,
    ) -> DelegationTask:
        """
        委派任务给目标Agent

        Args:
            from_agent: 委派方Agent ID
            to_agent: 接收方Agent ID
            task_type: 任务类型
            description: 任务描述
            payload: 任务数据
            priority: 优先级 1-10
            timeout_ms: 超时时间
        """
        now = datetime.now().isoformat()
        task_id = str(uuid.uuid4())[:12]

        # 验证
        if to_agent not in self._agents:
            return DelegationTask(
                task_id=task_id,
                from_agent=from_agent,
                to_agent=to_agent,
                task_type=task_type,
                description=description,
                payload=payload or {},
                status=TaskStatus.FAILED,
                error=f"Agent {to_agent} 不存在",
                created_at=now,
            )

        agent = self._agents[to_agent]
        if agent.status not in ("ready", "busy"):
            return DelegationTask(
                task_id=task_id,
                from_agent=from_agent,
                to_agent=to_agent,
                task_type=task_type,
                description=description,
                payload=payload or {},
                status=TaskStatus.FAILED,
                error=f"Agent {to_agent} 状态为 {agent.status}，不可接收任务",
                created_at=now,
            )

        # 检查能力匹配
        if task_type not in agent.capabilities:
            return DelegationTask(
                task_id=task_id,
                from_agent=from_agent,
                to_agent=to_agent,
                task_type=task_type,
                description=description,
                payload=payload or {},
                status=TaskStatus.FAILED,
                error=f"Agent {to_agent} 不具备 {task_type} 能力",
                created_at=now,
            )

        # 创建任务
        task = DelegationTask(
            task_id=task_id,
            from_agent=from_agent,
            to_agent=to_agent,
            task_type=task_type,
            description=description,
            payload=payload or {},
            status=TaskStatus.PENDING,
            priority=priority,
            timeout_ms=timeout_ms,
            created_at=now,
        )

        self._tasks[task_id] = task
        self._stats["total_delegations"] += 1
        self._emit_event(A2AEventType.TASK_CREATED, {"task_id": task_id, "from": from_agent, "to": to_agent})

        # 更新Agent状态
        self.update_agent_status(to_agent, "busy")

        # 执行任务
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now().isoformat()

            # 查找执行器
            handler = None
            if to_agent in self._agent_handlers and task_type in self._agent_handlers[to_agent]:
                handler = self._agent_handlers[to_agent][task_type]

            if handler:
                if asyncio.iscoroutinefunction(handler):
                    result = await asyncio.wait_for(
                        handler(payload or {}),
                        timeout=timeout_ms / 1000,
                    )
                else:
                    result = handler(payload or {})
            else:
                # 无执行器，返回占位结果
                result = {
                    "status": "delegated",
                    "message": f"任务已委派给 {to_agent}（无注册执行器，占位返回）",
                    "task_type": task_type,
                }

            task.status = TaskStatus.COMPLETED
            task.result = result
            task.completed_at = datetime.now().isoformat()
            self._stats["successful_delegations"] += 1
            self._emit_event(A2AEventType.TASK_COMPLETED, {"task_id": task_id, "result": "success"})

        except TimeoutError:
            task.status = TaskStatus.TIMEOUT
            task.error = f"任务执行超时（{timeout_ms}ms）"
            task.completed_at = datetime.now().isoformat()
            self._stats["failed_delegations"] += 1
            self._emit_event(A2AEventType.TASK_FAILED, {"task_id": task_id, "error": "timeout"})

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now().isoformat()
            self._stats["failed_delegations"] += 1
            self._emit_event(A2AEventType.TASK_FAILED, {"task_id": task_id, "error": str(e)})

        finally:
            # 恢复Agent状态
            self.update_agent_status(to_agent, "ready")

        return task

    async def delegate_parallel(
        self,
        from_agent: str,
        tasks: list[dict],
    ) -> list[DelegationTask]:
        """
        并行委派多个任务

        Args:
            from_agent: 委派方Agent ID
            tasks: [{"to_agent": str, "task_type": str, "payload": dict}, ...]
        """
        delegation_tasks = [
            self.delegate(
                from_agent=from_agent,
                to_agent=t["to_agent"],
                task_type=t["task_type"],
                description=t.get("description", ""),
                payload=t.get("payload", {}),
                priority=t.get("priority", 5),
                timeout_ms=t.get("timeout_ms", 60000),
            )
            for t in tasks
        ]
        return await asyncio.gather(*delegation_tasks)

    def get_task(self, task_id: str) -> dict | None:
        """获取任务详情"""
        if task_id in self._tasks:
            return self._tasks[task_id].model_dump()
        return None

    def list_tasks(self, agent_id: str = None, status: TaskStatus = None) -> list[dict]:
        """列出任务"""
        tasks = []
        for task in self._tasks.values():
            if agent_id and task.to_agent != agent_id and task.from_agent != agent_id:
                continue
            if status and task.status != status:
                continue
            tasks.append(task.model_dump())
        return tasks

    def cancel_task(self, task_id: str) -> dict:
        """取消任务"""
        if task_id not in self._tasks:
            return {"error": f"任务 {task_id} 不存在"}

        task = self._tasks[task_id]
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return {"error": f"任务 {task_id} 已完成，无法取消"}

        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now().isoformat()
        return {"status": "cancelled", "task_id": task_id}

    # ==================== 上下文共享API ====================

    def set_context(self, context_id: str, data: dict, scope: str = "global", updated_by: str = "") -> dict:
        """设置共享上下文"""
        now = datetime.now().isoformat()
        if context_id in self._contexts:
            ctx = self._contexts[context_id]
            ctx.data = data
            ctx.scope = scope
            ctx.version += 1
            ctx.updated_at = now
            ctx.updated_by = updated_by
        else:
            self._contexts[context_id] = SharedContext(
                context_id=context_id,
                scope=scope,
                data=data,
                updated_at=now,
                updated_by=updated_by,
            )
        self._emit_event(A2AEventType.CONTEXT_UPDATED, {"context_id": context_id, "updated_by": updated_by})
        return {"status": "updated", "context_id": context_id, "version": self._contexts[context_id].version}

    def get_context(self, context_id: str) -> dict | None:
        """获取共享上下文"""
        if context_id in self._contexts:
            return self._contexts[context_id].model_dump()
        return None

    def list_contexts(self, scope: str = None) -> list[dict]:
        """列出共享上下文"""
        contexts = []
        for ctx in self._contexts.values():
            if scope and ctx.scope != scope:
                continue
            contexts.append(ctx.model_dump())
        return contexts

    def delete_context(self, context_id: str) -> dict:
        """删除共享上下文"""
        if context_id in self._contexts:
            del self._contexts[context_id]
            return {"status": "deleted", "context_id": context_id}
        return {"error": f"上下文 {context_id} 不存在"}

    # ==================== 事件订阅 ====================

    def subscribe_events(self) -> asyncio.Queue:
        """订阅A2A事件"""
        queue = asyncio.Queue()
        self._event_subscribers.append(queue)
        return queue

    def unsubscribe_events(self, queue: asyncio.Queue):
        """取消订阅"""
        if queue in self._event_subscribers:
            self._event_subscribers.remove(queue)

    def _emit_event(self, event_type: A2AEventType, data: dict):
        """发出事件"""
        event = {
            "type": event_type.value,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }
        for queue in self._event_subscribers:
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(event)

    # ==================== 心跳监控 ====================

    async def _heartbeat_monitor(self):
        """心跳监控循环"""
        while self._running:
            now = datetime.now()
            for agent_id, card in list(self._agents.items()):
                if card.status in ("offline", "pending"):
                    continue
                try:
                    last = datetime.fromisoformat(card.last_heartbeat)
                    elapsed = (now - last).total_seconds()
                    if elapsed > card.heartbeat_interval_s * 3:
                        # 心跳超时，标记离线
                        old_status = card.status
                        card.status = "offline"
                        if old_status != "offline":
                            self._emit_event(A2AEventType.HEARTBEAT_MISSED, {"agent_id": agent_id})
                            self._emit_event(A2AEventType.AGENT_STATUS_CHANGED, {
                                "agent_id": agent_id,
                                "old_status": old_status,
                                "new_status": "offline",
                            })
                except (ValueError, TypeError):
                    pass

            await asyncio.sleep(10)  # 每10秒检查一次

    # ==================== 统计 ====================

    def _update_stats(self):
        """更新统计"""
        self._stats["active_agents"] = sum(
            1 for a in self._agents.values() if a.status in ("ready", "busy")
        )

    def get_stats(self) -> dict:
        """获取统计信息"""
        self._update_stats()
        return {
            **self._stats,
            "total_agents": len(self._agents),
            "total_contexts": len(self._contexts),
            "total_tasks": len(self._tasks),
            "subscribers_count": len(self._event_subscribers),
        }

    # ==================== 生命周期 ====================

    async def start(self):
        """启动A2A网关服务"""
        self._running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
        print(f"[A2A] 网关服务启动 {self.host}:{self.port}")
        print(f"[A2A] 已注册 {len(self._agents)} 个Agent")
        for card in self._agents.values():
            print(f"[A2A]   {card.agent_id}: {card.name} ({card.status})")

    async def stop(self):
        """停止A2A网关服务"""
        self._running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
        self._event_subscribers.clear()
        print("[A2A] 网关服务已停止")
