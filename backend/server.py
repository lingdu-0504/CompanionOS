"""
CompanionOS 后端统一入口 - Phase 2 升级
FastAPI服务 - 端口18080

升级内容：
- SSE流式对话API
- 完善WebSocket协议
- MCP/A2A网关生命周期管理
- 会话管理API
- Eigent四Agent API
"""

import warnings

# 抑制第三方库弃用警告（websockets 16.x legacy API、uvicorn 内部依赖）
warnings.filterwarnings("ignore", message="websockets.legacy is deprecated", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*WebSocketServerProtocol is deprecated", category=DeprecationWarning)

import asyncio  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import uuid  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from agent_bridge import A2AGateway, EigentAdapter, MCPGateway  # noqa: E402
from companion import UtsuwaEngine  # noqa: E402
from daemon import CronScheduler, FileWatcher  # noqa: E402
from memory import MemoryBridge, MemorySync  # noqa: E402
from novel_writer import NovelWriterCore  # noqa: E402

# ==================== 内部模块导入 ====================
from router import AgentRouter  # noqa: E402
from security import ApprovalManager, EncryptionManager, KeychainManager  # noqa: E402
from voice import VoiceService  # noqa: E402
from workflow_engine import WorkflowEngine  # noqa: E402

# ==================== 数据目录 ====================

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
for subdir in ["workflows", "templates", "memories", "profiles", "skills", "logs", "watch"]:
    (DATA_DIR / subdir).mkdir(exist_ok=True)

# ==================== 模型定义 ====================


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    context: dict | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    content: str
    companion_remark: str | None = None
    intent: str = "work"
    intent_confidence: float = 0
    emotion: str | None = None
    vrm_action: str | None = None
    vrm_expression: str | None = None
    engine: str = "hermes"
    session_id: str = ""


class StreamChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    context: dict | None = None


class WorkflowNode(BaseModel):
    id: str
    type: str
    label: str
    config: dict = {}
    position: dict = {}


class WorkflowEdge(BaseModel):
    id: str
    source: str
    target: str
    source_handle: str | None = None
    target_handle: str | None = None


class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    nodes: list[WorkflowNode] = []
    edges: list[WorkflowEdge] = []


class WorkflowExecute(BaseModel):
    inputs: dict = {}


class MemoryBlock(BaseModel):
    label: str
    value: str


class EigentExecuteRequest(BaseModel):
    agent_type: str  # browser | document | developer | multimodal
    action: str
    parameters: dict = {}


class EigentChainRequest(BaseModel):
    steps: list[dict]  # [{"agent_type": str, "action": str, "parameters": dict}]


# ==================== 小说创作模型 ====================

class NovelProjectCreate(BaseModel):
    name: str
    description: str = ""
    genre: str = "fantasy"
    target_word_count: int = 1000000
    config: dict = {}

class NovelStyleCreate(BaseModel):
    name: str
    description: str = ""
    writing_style: str = "fiction"
    tone_style: str = "neutral"
    narrative_mode: str = "third_person"
    features: dict = {}
    keywords: list = []
    examples: list = []

class NovelCreationPlanCreate(BaseModel):
    total_chapters: int = 100
    start_chapter: int = 1
    words_per_chapter: int = 3000
    narrative_arc: str = "hero_journey"
    auto_publish: bool = False
    publish_platform: str = ""
    publish_schedule: dict = {}

class NovelChapterOutlineCreate(BaseModel):
    number: int
    title: str
    summary: str = ""
    key_events: list = []
    character_arcs: dict = {}
    word_count: int = 3000

class NovelTextAnalysisRequest(BaseModel):
    text: str


class NovelChapterCreate(BaseModel):
    number: int
    title: str
    content: str = ""


class NovelChapterGenerate(BaseModel):
    chapter_number: int
    title: str
    target_words: int | None = None


class NovelPlatformPublish(BaseModel):
    chapter_number: int
    platform: str = "qidian"
    config: dict = {}


# ==================== 全局状态 ====================


class AppState:
    def __init__(self):
        # 核心引擎
        self.agent_router = AgentRouter(str(DATA_DIR))
        self.workflow_engine = WorkflowEngine()
        self.utsuwa = UtsuwaEngine()
        self.memory_bridge = MemoryBridge(DATA_DIR)
        self.memory_sync = MemorySync(self.memory_bridge)
        self.voice_service = VoiceService()

        # 小说创作引擎
        novel_data_dir = DATA_DIR / "novels"
        novel_data_dir.mkdir(exist_ok=True)
        self.novel_writer = NovelWriterCore(novel_data_dir)

        # 网关
        self.mcp_gateway = MCPGateway(data_dir=str(DATA_DIR))
        self.a2a_gateway = A2AGateway()

        # Eigent
        self.eigent = EigentAdapter()

        # 安全
        self.keychain = KeychainManager(str(DATA_DIR))
        self.approval = ApprovalManager()
        self.encryption = EncryptionManager()

        # 守护进程
        self.daemon = {"file_watcher": FileWatcher(DATA_DIR), "cron": CronScheduler()}

        # 连接
        self.ws_clients: list[WebSocket] = []
        self.workflow_registry: dict[str, dict] = {}


state = AppState()


# ==================== 生命周期 ====================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("[CompanionOS] 后端服务启动中...")
    print(f"[CompanionOS] 数据目录: {DATA_DIR}")

    # 启动网关
    await state.mcp_gateway.start()
    await state.a2a_gateway.start()

    # 初始化Eigent
    await state.eigent.initialize()

    # 设置Hermes MCP回调
    state.agent_router.hermes.set_mcp_register_callback(
        lambda: state.mcp_gateway
    )

    # 设置Neuro记忆桥接
    state.agent_router.neuro.set_memory_bridge(state.memory_bridge)

    # 设置AgentRouter记忆桥接
    state.agent_router.set_memory_bridge(state.memory_bridge, state.memory_sync)

    # 启动守护进程
    await state.daemon["file_watcher"].start()
    await state.daemon["cron"].start()

    print("[CompanionOS] 后端服务已就绪 http://localhost:18080")
    print(f"[CompanionOS] MCP工具: {len(state.mcp_gateway.list_tools())} | A2A Agent: {len(state.a2a_gateway.list_agents())}")
    yield

    # 停止服务
    await state.mcp_gateway.stop()
    await state.a2a_gateway.stop()
    await state.daemon["file_watcher"].stop()
    await state.daemon["cron"].stop()
    print("[CompanionOS] 后端服务关闭")


# ==================== FastAPI应用 ====================


app = FastAPI(
    title="CompanionOS",
    description="虚拟伴侣AI办公一体桌面端后端",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== API路由 ====================


@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    companion = state.utsuwa.get_state()
    mcp_stats = state.mcp_gateway.get_stats()
    a2a_stats = state.a2a_gateway.get_stats()

    return {
        "status": "running",
        "version": "0.2.0",
        "services": {
            "hermes": "ready",
            "neuro-sama": "ready",
            "eigent": "ready",
            "letta": "pending",
            "daemon": "running",
        },
        "companion": companion,
        "tools": {
            "mcp": mcp_stats,
            "a2a": a2a_stats,
            "workflow_nodes": len(state.workflow_engine.registry.list_types()),
        },
        "timestamp": datetime.now().isoformat(),
    }


# ---- 对话API ----


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """核心对话接口 - 意图识别+多Agent路由"""
    # 使用AgentRouter处理
    result = await state.agent_router.chat(
        message=request.message,
        session_id=request.session_id,
        context=request.context,
    )

    # 更新关系值
    state.utsuwa.update_relation("chat", 0.5)

    # 更新情绪
    if result.get("emotion"):
        state.utsuwa.set_emotion(result["emotion"])

    # 同步记忆
    await state.memory_sync.sync_interaction({
        "user_input": request.message,
        "intent": result["intent"],
        "response": result["content"],
        "emotion": result.get("emotion"),
    })

    # 广播给WS客户端
    await broadcast_ws({
        "type": "chat_response",
        "data": result,
    })

    return ChatResponse(**result)


@app.post("/api/chat/stream")
async def chat_stream(request: StreamChatRequest):
    """SSE流式对话接口"""
    async def generate():
        async for chunk in state.agent_router.stream_chat(
            message=request.message,
            session_id=request.session_id,
            context=request.context,
        ):
            yield f"data: {chunk}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---- 会话API ----


@app.post("/api/sessions")
async def create_session():
    """创建新会话"""
    session_id = state.agent_router.create_session()
    return {"session_id": session_id}


@app.get("/api/sessions")
async def list_sessions():
    """列出所有会话"""
    return {"sessions": state.agent_router.list_sessions()}


@app.get("/api/sessions/{session_id}/history")
async def get_session_history(session_id: str, limit: int = Query(default=20, ge=1, le=100)):
    """获取会话历史"""
    history = state.agent_router.get_session_history(session_id, limit)
    return {"session_id": session_id, "history": history}


@app.delete("/api/sessions/{session_id}")
async def close_session(session_id: str):
    """关闭会话"""
    state.agent_router.close_session(session_id)
    return {"status": "closed", "session_id": session_id}


# ---- 工作流API ----


@app.get("/api/workflow")
async def list_workflows():
    """列出所有工作流"""
    workflows = []
    wf_dir = DATA_DIR / "workflows"
    for f in wf_dir.glob("*.json"):
        with open(f, encoding="utf-8") as fp:
            workflows.append(json.load(fp))
    return {"workflows": workflows}


@app.post("/api/workflow")
async def create_workflow(wf: WorkflowCreate):
    """创建工作流"""
    wf_id = str(uuid.uuid4())[:8]
    wf_data = {
        "id": wf_id,
        "name": wf.name,
        "description": wf.description,
        "nodes": [n.model_dump() for n in wf.nodes],
        "edges": [e.model_dump() for e in wf.edges],
        "created_at": datetime.now().isoformat(),
    }

    wf_path = DATA_DIR / "workflows" / f"{wf_id}.json"
    with open(wf_path, "w", encoding="utf-8") as f:
        json.dump(wf_data, f, ensure_ascii=False, indent=2)

    state.workflow_registry[wf_id] = wf_data
    return {"id": wf_id, "status": "created"}


@app.post("/api/workflow/{wf_id}/execute")
async def execute_workflow(wf_id: str, inputs: WorkflowExecute):
    """执行工作流"""
    wf_path = DATA_DIR / "workflows" / f"{wf_id}.json"
    if not wf_path.exists():
        return {"error": "工作流不存在"}

    with open(wf_path, encoding="utf-8") as f:
        wf_data = json.load(f)

    result = await state.workflow_engine.execute(wf_data, inputs.inputs)
    return {"workflow_id": wf_id, **result}


@app.get("/api/workflow/node-types")
async def list_node_types():
    """列出可用的工作流节点类型"""
    return {"node_types": state.workflow_engine.registry.list_types()}


# ---- 记忆API ----


@app.get("/api/memory")
async def list_memory_blocks():
    """列出所有记忆块"""
    return state.memory_bridge.get_all_blocks()


@app.get("/api/memory/{block_type}")
async def get_memory(block_type: str):
    """获取记忆块"""
    return state.memory_bridge.get_block(block_type)


@app.put("/api/memory/{block_type}")
async def update_memory(block_type: str, block: MemoryBlock):
    """更新记忆块"""
    return state.memory_bridge.save_block(block_type, block.value)


# ---- 伴侣状态API ----


@app.get("/api/companion/state")
async def get_companion_state():
    """获取伴侣状态"""
    return state.utsuwa.get_state()


@app.post("/api/companion/interact")
async def companion_interact(interaction_type: str, delta: float = 1.0):
    """伴侣互动"""
    state.utsuwa.update_relation(interaction_type, delta)
    return state.utsuwa.get_state()


@app.get("/api/companion/relation-levels")
async def get_relation_levels():
    """获取关系等级定义"""
    from companion import RELATION_LEVELS
    return {"levels": RELATION_LEVELS}


# ---- 语音API ----


@app.post("/api/voice/tts")
async def text_to_speech(text: str, engine: str = None):
    """语音合成"""
    result = await state.voice_service.synthesize(text, engine)
    return result


@app.get("/api/voice/engines")
async def list_voice_engines():
    """列出可用的TTS引擎"""
    return {"engines": state.voice_service.list_engines()}


# ---- MCP工具API ----


@app.get("/api/mcp/tools")
async def list_mcp_tools(group: str = None):
    """列出MCP工具"""
    return {"tools": state.mcp_gateway.list_tools(group)}


@app.get("/api/mcp/tools/{tool_name}")
async def get_mcp_tool(tool_name: str):
    """获取MCP工具详情"""
    tool = state.mcp_gateway.get_tool(tool_name)
    if tool:
        return tool
    return {"error": f"工具 {tool_name} 不存在"}


@app.post("/api/mcp/call")
async def call_mcp_tool(tool_name: str, arguments: dict = None, session_id: str = None, auto_approve: bool = True):
    """调用MCP工具"""
    result = await state.mcp_gateway.call_tool(tool_name, arguments, session_id, auto_approve)
    return result.model_dump()


@app.post("/api/mcp/call-batch")
async def call_mcp_tools_batch(calls: list[dict], session_id: str = None):
    """批量调用MCP工具"""
    results = await state.mcp_gateway.call_tools_batch(calls, session_id)
    return {"results": [r.model_dump() for r in results]}


@app.get("/api/mcp/groups")
async def list_mcp_groups():
    """列出MCP工具分组"""
    return {"groups": state.mcp_gateway.list_groups()}


@app.get("/api/mcp/sessions")
async def list_mcp_sessions():
    """列出MCP会话"""
    return {"sessions": state.mcp_gateway.list_sessions()}


@app.get("/api/mcp/stats")
async def get_mcp_stats():
    """获取MCP统计"""
    return state.mcp_gateway.get_stats()


# ---- A2A Agent API ----


@app.get("/api/a2a/agents")
async def list_a2a_agents(status: str = None, capability: str = None):
    """列出已注册Agent"""
    return {"agents": state.a2a_gateway.list_agents(status, capability)}


@app.get("/api/a2a/agents/{agent_id}")
async def get_a2a_agent(agent_id: str):
    """获取Agent详情"""
    agent = state.a2a_gateway.get_agent(agent_id)
    if agent:
        return agent
    return {"error": f"Agent {agent_id} 不存在"}


@app.post("/api/a2a/delegate")
async def delegate_task(
    from_agent: str,
    to_agent: str,
    task_type: str,
    description: str = "",
    payload: dict = None,
    priority: int = 5,
    timeout_ms: int = 60000,
):
    """Agent间任务委派"""
    result = await state.a2a_gateway.delegate(
        from_agent=from_agent,
        to_agent=to_agent,
        task_type=task_type,
        description=description,
        payload=payload,
        priority=priority,
        timeout_ms=timeout_ms,
    )
    return result.model_dump()


@app.post("/api/a2a/delegate-parallel")
async def delegate_tasks_parallel(from_agent: str, tasks: list[dict]):
    """并行委派多个任务"""
    results = await state.a2a_gateway.delegate_parallel(from_agent, tasks)
    return {"results": [r.model_dump() for r in results]}


@app.get("/api/a2a/tasks")
async def list_a2a_tasks(agent_id: str = None, status: str = None):
    """列出任务"""
    return {"tasks": state.a2a_gateway.list_tasks(agent_id, status)}


@app.get("/api/a2a/tasks/{task_id}")
async def get_a2a_task(task_id: str):
    """获取任务详情"""
    task = state.a2a_gateway.get_task(task_id)
    if task:
        return task
    return {"error": f"任务 {task_id} 不存在"}


@app.get("/api/a2a/context/{context_id}")
async def get_a2a_context(context_id: str):
    """获取共享上下文"""
    ctx = state.a2a_gateway.get_context(context_id)
    if ctx:
        return ctx
    return {"error": f"上下文 {context_id} 不存在"}


@app.put("/api/a2a/context/{context_id}")
async def set_a2a_context(context_id: str, data: dict, scope: str = "global", updated_by: str = ""):
    """设置共享上下文"""
    return state.a2a_gateway.set_context(context_id, data, scope, updated_by)


@app.get("/api/a2a/stats")
async def get_a2a_stats():
    """获取A2A统计"""
    return state.a2a_gateway.get_stats()


# ---- Eigent Agent API ----


@app.get("/api/eigent/agents")
async def list_eigent_agents():
    """列出Eigent Agent"""
    return {"agents": state.eigent.list_agents()}


@app.post("/api/eigent/execute")
async def execute_eigent_task(request: EigentExecuteRequest):
    """执行Eigent Agent任务"""
    result = await state.eigent.execute(
        agent_type=request.agent_type,
        action=request.action,
        parameters=request.parameters,
    )
    return result


@app.post("/api/eigent/chain")
async def execute_eigent_chain(request: EigentChainRequest):
    """执行Eigent Agent链"""
    results = await state.eigent.execute_chain(request.steps)
    return {"results": results}


@app.post("/api/eigent/parallel")
async def execute_eigent_parallel(request: EigentChainRequest):
    """并行执行Eigent Agent任务"""
    results = await state.eigent.execute_parallel(request.steps)
    return {"results": results}


@app.get("/api/eigent/tasks")
async def list_eigent_tasks(agent_type: str = None, status: str = None):
    """列出Eigent任务"""
    return {"tasks": state.eigent.list_tasks(agent_type, status)}


# ---- 安全API ----


@app.get("/api/security/keys")
async def list_keys():
    """列出密钥列表（不返回值）"""
    return {"keys": state.keychain.list_keys()}


@app.post("/api/security/approve/{approval_id}")
async def approve_operation(approval_id: str):
    """批准操作"""
    result = state.approval.approve(approval_id)
    return {"approved": result}


@app.post("/api/security/reject/{approval_id}")
async def reject_operation(approval_id: str):
    """拒绝操作"""
    result = state.approval.reject(approval_id)
    return {"rejected": result}


# ---- Hermes自学习API ----


@app.get("/api/hermes/skills")
async def list_hermes_skills():
    """列出Hermes自学习技能"""
    return {"skills": state.agent_router.hermes.list_skills()}


@app.post("/api/hermes/skills")
async def learn_hermes_skill(name: str, pattern: str, template: str, description: str = ""):
    """学习新技能"""
    result = state.agent_router.hermes.learn_skill(name, pattern, template, description)
    return result


# ---- 小说创作API ----


@app.get("/api/novel/projects")
async def list_novel_projects():
    """列出所有小说项目"""
    projects = state.novel_writer.list_projects()
    return {"projects": [p.to_dict() for p in projects]}


@app.post("/api/novel/projects")
async def create_novel_project(request: NovelProjectCreate):
    """创建新小说项目"""
    project = state.novel_writer.create_project(
        name=request.name,
        description=request.description,
        genre=request.genre,
        target_word_count=request.target_word_count,
    )
    project.config.update(request.config)
    project.save(state.novel_writer.data_dir)
    return project.to_dict()


@app.get("/api/novel/projects/{project_id}")
async def get_novel_project(project_id: str):
    """获取小说项目详情"""
    project = state.novel_writer.get_project(project_id)
    if not project:
        return {"error": "项目不存在"}
    return project.to_dict()


@app.delete("/api/novel/projects/{project_id}")
async def delete_novel_project(project_id: str):
    """删除小说项目"""
    success = state.novel_writer.delete_project(project_id)
    return {"success": success}


@app.get("/api/novel/projects/{project_id}/chapters")
async def list_novel_chapters(project_id: str):
    """列出小说章节"""
    project = state.novel_writer.get_project(project_id)
    if not project:
        return {"error": "项目不存在"}
    return {"chapters": [
        {
            "id": c.id,
            "number": c.number,
            "title": c.title,
            "word_count": c.word_count,
            "status": c.status,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
        for c in project.chapters
    ]}


@app.get("/api/novel/projects/{project_id}/chapters/{chapter_number}")
async def get_novel_chapter(project_id: str, chapter_number: int):
    """获取小说章节内容"""
    project = state.novel_writer.get_project(project_id)
    if not project:
        return {"error": "项目不存在"}
    chapter = project.get_chapter(chapter_number)
    if not chapter:
        return {"error": "章节不存在"}
    return {
        "id": chapter.id,
        "number": chapter.number,
        "title": chapter.title,
        "content": chapter.content,
        "word_count": chapter.word_count,
        "status": chapter.status,
        "created_at": chapter.created_at,
        "updated_at": chapter.updated_at,
    }


@app.post("/api/novel/projects/{project_id}/chapters")
async def create_novel_chapter(project_id: str, request: NovelChapterCreate):
    """创建/更新小说章节"""
    project = state.novel_writer.get_project(project_id)
    if not project:
        return {"error": "项目不存在"}
    chapter = project.add_chapter(
        title=request.title,
        number=request.number,
        content=request.content,
    )
    project.save(state.novel_writer.data_dir)
    return {
        "id": chapter.id,
        "number": chapter.number,
        "title": chapter.title,
        "word_count": chapter.word_count,
    }


@app.post("/api/novel/projects/{project_id}/generate")
async def generate_novel_chapter(project_id: str, request: NovelChapterGenerate):
    """生成小说章节"""
    result = await state.novel_writer.generate_chapter(
        project_id=project_id,
        chapter_title=request.title,
        chapter_number=request.chapter_number,
        target_words=request.target_words,
    )
    return result


@app.post("/api/novel/projects/{project_id}/publish")
async def publish_novel_chapter(project_id: str, request: NovelPlatformPublish):
    """发布小说章节"""
    project = state.novel_writer.get_project(project_id)
    if not project:
        return {"error": "项目不存在"}
    result = await state.novel_writer.auto_publish(
        project_id=project_id,
        platform_config=request.model_dump(),
    )
    return result


@app.get("/api/novel/tasks")
async def list_novel_tasks(project_id: str | None = None):
    """列出创作任务"""
    tasks = state.novel_writer.parallel_manager.get_all_tasks(project_id)
    return {"tasks": tasks}


@app.get("/api/novel/tasks/{task_id}")
async def get_novel_task(task_id: str):
    """获取任务状态"""
    task = state.novel_writer.get_task_status(task_id)
    if not task:
        return {"error": "任务不存在"}
    return task


@app.post("/api/novel/tasks/{task_id}/cancel")
async def cancel_novel_task(task_id: str):
    """取消任务"""
    success = state.novel_writer.cancel_task(task_id)
    return {"success": success}


@app.get("/api/novel/platforms")
async def list_novel_platforms():
    """列出支持的发布平台"""
    platforms = state.novel_writer.platform_publisher.get_platforms()
    return {"platforms": platforms}


# ---- 风格管理 API ----

@app.get("/api/novel/styles")
async def list_novel_styles():
    """列出所有创作风格"""
    styles = state.novel_writer.get_all_styles()
    return {"styles": [s.to_dict() if hasattr(s, 'to_dict') else {
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "is_preset": s.is_preset
    } for s in styles]}


@app.get("/api/novel/styles/{style_id}")
async def get_novel_style(style_id: str):
    """获取创作风格详情"""
    style = state.novel_writer.get_style(style_id)
    if not style:
        return {"error": "风格不存在"}
    return style.to_dict() if hasattr(style, 'to_dict') else {
        "id": style.id,
        "name": style.name,
        "description": style.description,
        "is_preset": style.is_preset
    }


@app.post("/api/novel/styles")
async def create_novel_style(request: NovelStyleCreate):
    """创建自定义创作风格"""
    try:
        saved_style = state.novel_writer.create_style({
            'name': request.name,
            'description': request.description,
            'writing_style': request.writing_style,
            'tone_style': request.tone_style,
            'narrative_mode': request.narrative_mode
        })
        if saved_style:
            return saved_style
        return {"error": "Failed to create style"}
    except Exception as e:
        return {"error": str(e)}


@app.put("/api/novel/styles/{style_id}")
async def update_novel_style(style_id: str, updates: dict):
    """更新创作风格"""
    updated_style = state.novel_writer.update_style(style_id, updates)
    if not updated_style:
        return {"error": "风格不存在"}
    return updated_style.to_dict() if hasattr(updated_style, 'to_dict') else {
        "id": updated_style.id,
        "name": updated_style.name,
        "description": updated_style.description,
        "is_preset": updated_style.is_preset
    }


@app.delete("/api/novel/styles/{style_id}")
async def delete_novel_style(style_id: str):
    """删除创作风格"""
    success = state.novel_writer.delete_style(style_id)
    return {"success": success}


@app.post("/api/novel/styles/analyze")
async def analyze_text_style(request: NovelTextAnalysisRequest):
    """分析文本风格"""
    analysis = await state.novel_writer.analyze_text_style(request.text)
    return {"analysis": analysis}


@app.post("/api/novel/styles/{style_id}/prompt")
async def generate_style_prompt(style_id: str, context: dict = None):
    """生成风格提示词"""
    prompt = await state.novel_writer.generate_style_prompt(style_id, context or {})
    return {"prompt": prompt}


@app.post("/api/novel/projects/{project_id}/style")
async def apply_style_to_project(project_id: str, request: dict):
    """将风格应用到项目"""
    style_id = request.get("style_id")
    success = state.novel_writer.apply_style_to_project(project_id, style_id)
    return {"success": success}


# ---- 智能创作 API ----

@app.post("/api/novel/projects/{project_id}/plan")
async def create_creation_plan(project_id: str, request: NovelCreationPlanCreate):
    """创建创作计划"""
    try:
        plan = await state.novel_writer.create_creation_plan(project_id, request.model_dump())
        return {
            "success": True,
            "plan": plan.to_dict() if hasattr(plan, 'to_dict') else plan
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}


@app.get("/api/novel/projects/{project_id}/plan")
async def get_creation_plan(project_id: str):
    """获取创作计划"""
    plan = state.novel_writer.get_creation_plan(project_id)
    if not plan:
        return {"error": "创作计划不存在"}
    return plan.to_dict() if hasattr(plan, 'to_dict') else plan


@app.post("/api/novel/projects/{project_id}/plan/execute")
async def execute_creation_plan(project_id: str, request: dict = None):
    """执行创作计划"""
    try:
        start_chapter = request.get("start_chapter") if request else None
        end_chapter = request.get("end_chapter") if request else None
        result = await state.novel_writer.execute_creation_plan(project_id, start_chapter, end_chapter)
        return {
            "success": True,
            "result": result
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}


@app.post("/api/novel/projects/{project_id}/outlines")
async def add_chapter_outline(project_id: str, request: NovelChapterOutlineCreate):
    """添加章节大纲"""
    outline = state.novel_writer.add_chapter_outline(project_id, request.model_dump())
    return {
        "success": True,
        "outline": outline.to_dict() if hasattr(outline, 'to_dict') else outline
    }


@app.get("/api/novel/projects/{project_id}/outlines")
async def get_chapter_outlines(project_id: str):
    """获取章节大纲列表"""
    outlines = state.novel_writer.get_chapter_outlines(project_id)
    return {
        "outlines": [o.to_dict() if hasattr(o, 'to_dict') else o for o in outlines]
    }


@app.get("/api/novel/projects/{project_id}/quality")
async def analyze_creation_quality(project_id: str):
    """分析创作质量"""
    try:
        quality = await state.novel_writer.analyze_creation_quality(project_id)
        return {
            "success": True,
            "quality": quality
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}


@app.get("/api/novel/automation-levels")
async def get_automation_levels():
    """获取自动化等级信息"""
    return state.novel_writer.get_automation_levels()


# ---- 情绪分析API ----


@app.post("/api/emotion/analyze")
async def analyze_emotion(message: str):
    """分析消息情绪"""
    result = state.agent_router.neuro.analyze_emotion(message)
    return result


@app.post("/api/emotion/analyze-enhanced")
async def analyze_emotion_enhanced(message: str):
    """增强情绪分析（LLM增强推理+情绪趋势）"""
    result = await state.agent_router.neuro.analyze_emotion_enhanced(message)
    return result


@app.get("/api/emotion/trend")
async def get_emotion_trend():
    """获取情绪趋势"""
    return state.agent_router.neuro.get_emotion_trend()


@app.get("/api/emotion/history")
async def get_emotion_history(limit: int = Query(default=10, ge=1, le=50)):
    """获取情绪历史"""
    return {"history": state.agent_router.neuro.get_emotion_history(limit)}


# ==================== WebSocket ====================


async def broadcast_ws(message: dict):
    """广播消息给所有WS客户端"""
    disconnected = []
    for client in state.ws_clients:
        try:
            await client.send_json(message)
        except Exception:
            disconnected.append(client)
    for client in disconnected:
        if client in state.ws_clients:
            state.ws_clients.remove(client)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket实时通信（增强版：完整协议+心跳+错误处理）"""
    await ws.accept()
    client_id = str(uuid.uuid4())[:8]
    state.ws_clients.append(ws)

    # 发送欢迎消息
    await ws.send_json({
        "type": "connected",
        "client_id": client_id,
        "server_version": "0.2.0",
    })

    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_json(), timeout=120.0)
            except TimeoutError:
                # 超时发送心跳检测
                await ws.send_json({"type": "ping"})
                continue

            msg_type = data.get("type", "")

            if msg_type == "chat":
                result = await chat(ChatRequest(
                    message=data.get("message", ""),
                    session_id=data.get("session_id"),
                    context=data.get("context"),
                ))
                await ws.send_json({
                    "type": "chat_response",
                    "data": result.model_dump(),
                })

            elif msg_type == "stream_chat":
                # WebSocket流式对话（增强版：解析SSE格式数据）
                session_id = data.get("session_id")
                try:
                    async for chunk in state.agent_router.stream_chat(
                        message=data.get("message", ""),
                        session_id=session_id,
                        context=data.get("context"),
                    ):
                        try:
                            chunk_data = json.loads(chunk)
                            await ws.send_json({
                                "type": "stream_chunk",
                                "data": chunk_data,
                            })
                        except json.JSONDecodeError:
                            await ws.send_json({
                                "type": "stream_chunk",
                                "raw": chunk,
                            })
                except Exception as e:
                    await ws.send_json({
                        "type": "stream_error",
                        "error": str(e),
                    })
                await ws.send_json({"type": "stream_done", "session_id": session_id})

            elif msg_type == "ping":
                await ws.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})

            elif msg_type == "pong":
                # 心跳响应，忽略
                pass

            elif msg_type == "companion_action":
                action = data.get("action", "")
                emotion = data.get("emotion", "neutral")
                # 触发VRM动作
                state.utsuwa.set_emotion(emotion)
                state.utsuwa.update_relation("chat", 0.3)

                # 获取VRM映射
                vrm_result = state.agent_router.neuro.analyze_emotion(emotion)

                await ws.send_json({
                    "type": "action_executed",
                    "action": action,
                    "emotion": emotion,
                    "vrm_map": vrm_result.get("vrm_map", {}),
                })

            elif msg_type == "emotion_update":
                # 情绪更新（前端推送VRM状态）
                emotion = data.get("emotion", "neutral")
                state.utsuwa.set_emotion(emotion)
                await ws.send_json({
                    "type": "emotion_updated",
                    "emotion": emotion,
                })

            elif msg_type == "mcp_call":
                # WebSocket MCP工具调用
                result = await state.mcp_gateway.call_tool(
                    tool_name=data.get("tool_name", ""),
                    arguments=data.get("arguments", {}),
                    session_id=data.get("session_id"),
                )
                await ws.send_json({
                    "type": "mcp_result",
                    "data": result.model_dump(),
                })

            elif msg_type == "mcp_list":
                # MCP工具列表
                tools = state.mcp_gateway.list_tools(data.get("group"))
                await ws.send_json({
                    "type": "mcp_tools",
                    "data": tools,
                })

            elif msg_type == "a2a_delegate":
                # WebSocket A2A委派
                result = await state.a2a_gateway.delegate(
                    from_agent=data.get("from_agent", ""),
                    to_agent=data.get("to_agent", ""),
                    task_type=data.get("task_type", ""),
                    payload=data.get("payload", {}),
                )
                await ws.send_json({
                    "type": "a2a_result",
                    "data": result.model_dump(),
                })

            elif msg_type == "eigent_execute":
                # WebSocket Eigent执行
                result = await state.eigent.execute(
                    agent_type=data.get("agent_type", ""),
                    action=data.get("action", ""),
                    parameters=data.get("parameters", {}),
                )
                await ws.send_json({
                    "type": "eigent_result",
                    "data": result,
                })

            elif msg_type == "subscribe":
                # 订阅MCP事件
                queue = state.mcp_gateway.subscribe_events()
                await ws.send_json({"type": "subscribed", "channel": "mcp_events"})
                # 在后台推送事件
                asyncio.create_task(_forward_mcp_events(ws, queue))

            else:
                await ws.send_json({
                    "type": "error",
                    "message": f"未知消息类型: {msg_type}",
                })

    except WebSocketDisconnect:
        if ws in state.ws_clients:
            state.ws_clients.remove(ws)
    except Exception as e:
        print(f"[WebSocket] 客户端 {client_id} 异常: {e}")
        if ws in state.ws_clients:
            state.ws_clients.remove(ws)


async def _forward_mcp_events(ws: WebSocket, queue: asyncio.Queue):
    """将MCP事件转发给WebSocket客户端"""
    try:
        while True:
            event = await queue.get()
            await ws.send_json({
                "type": "mcp_event",
                "data": event,
            })
    except Exception:
        pass  # WebSocket断开时静默退出


# ==================== 增强API ====================


@app.get("/api/routes")
async def list_routes():
    """列出所有API路由"""
    routes = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            routes.append({
                "path": route.path,
                "methods": list(route.methods) if route.methods else [],
                "name": route.name,
            })
    return {"routes": routes, "total": len(routes)}


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "version": "0.2.0",
        "uptime": datetime.now().isoformat(),
        "services": {
            "mcp": len(state.mcp_gateway.list_tools()),
            "a2a": len(state.a2a_gateway.list_agents()),
            "eigent": len(state.eigent.list_agents()),
            "ws_clients": len(state.ws_clients),
        },
    }


@app.post("/api/intent/classify")
async def classify_user_intent(message: str, use_llm: bool = True):
    """意图分类API"""
    if use_llm:
        from router.intent_classifier import classify_intent_with_llm
        result = await classify_intent_with_llm(message)
    else:
        from router.intent_classifier import classify_intent
        result = classify_intent(message)
    return result


# ---- 配置管理API ----

# 获取 .env 文件路径
ENV_PATH = Path(__file__).parent.parent / ".env"


@app.get("/api/config")
async def get_config():
    """获取当前配置（不暴露密钥完整值）"""
    config = {}
    env_path = ENV_PATH
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    # 对敏感字段只显示前4位
                    if "KEY" in key or "SECRET" in key or "TOKEN" in key:
                        config[key] = val[:4] + "..." if val else ""
                    else:
                        config[key] = val
    return config


@app.post("/api/config")
async def update_config(config: dict):
    """更新配置项"""
    env_path = ENV_PATH
    if not env_path.exists():
        return {"error": ".env file not found"}

    with open(env_path, encoding="utf-8") as f:
        lines = f.readlines()

    updated_keys = []
    for key, value in config.items():
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                found = True
                updated_keys.append(key)
                break
        if not found:
            lines.append(f"{key}={value}\n")
            updated_keys.append(key)

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # 更新当前进程的环境变量
    for key in updated_keys:
        os.environ[key] = str(config[key])

    return {"status": "updated", "keys": updated_keys}


@app.get("/api/config/check")
async def check_config():
    """检查配置状态，返回各服务的可用性"""
    api_key = os.getenv("OPENAI_API_KEY", "")
    has_api_key = bool(api_key)

    # 检查 Ollama 是否可用
    ollama_available = False
    if not has_api_key:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get("http://localhost:11434/api/tags")
                ollama_available = resp.status_code == 200
        except Exception:
            ollama_available = False

    return {
        "openai_configured": has_api_key,
        "ollama_available": ollama_available,
        "llm_ready": has_api_key or ollama_available,
        "engines": {
            "hermes": {
                "mode": "openai" if has_api_key else ("ollama" if ollama_available else "fallback"),
                "model": os.getenv("HERMES_MODEL", "default"),
            },
            "neuro": {
                "mode": "openai" if has_api_key else ("ollama" if ollama_available else "fallback"),
                "model": os.getenv("NEURO_MODEL", "default"),
            },
        },
        "recommendation": "已就绪" if (has_api_key or ollama_available) else "请配置 OpenAI API Key 或启动本地 Ollama",
    }


# ==================== 启动 ====================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=18080)
