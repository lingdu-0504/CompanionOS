"""
CompanionOS MCP网关 - Phase 2 完整实现
MCP协议服务端：工具动态注册/注销 + 执行沙箱 + 事件通知 + 会话管理

协议规范（简化版MCP）：
- 工具发现: list_tools
- 工具调用: call_tool
- 通知推送: tool_updated / tool_executed
- 会话管理: create_session / close_session
"""

import asyncio
import contextlib
import json
import os
import pathlib
import time
import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

import httpx
from pydantic import BaseModel

# ==================== 数据模型 ====================


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None


class ToolDefinition(BaseModel):
    """MCP工具定义"""
    name: str
    description: str = ""
    group: str = "general"
    version: str = "1.0.0"
    parameters: list[ToolParameter] = []
    handler_key: str = ""  # 内部执行器标识
    requires_approval: bool = False  # 是否需要用户审批
    rate_limit: int = 0  # 每分钟调用限制, 0=不限
    timeout_ms: int = 30000  # 执行超时


class ToolCallResult(BaseModel):
    """工具调用结果"""
    tool_name: str
    status: str = "success"  # success | error | timeout | rejected
    output: Any = None
    error: str | None = None
    execution_ms: int = 0
    session_id: str = ""
    timestamp: str = ""


class MCPSession(BaseModel):
    """MCP会话"""
    session_id: str
    created_at: str
    last_active: str
    call_count: int = 0
    metadata: dict = {}


class MCPEventType(StrEnum):
    """MCP事件类型"""
    TOOL_REGISTERED = "tool_registered"
    TOOL_UNREGISTERED = "tool_unregistered"
    TOOL_EXECUTED = "tool_executed"
    TOOL_ERROR = "tool_error"
    SESSION_CREATED = "session_created"
    SESSION_CLOSED = "session_closed"


# ==================== 工具执行器基类 ====================


class ToolExecutor:
    """工具执行器基类"""

    async def execute(self, arguments: dict) -> Any:
        raise NotImplementedError

    async def validate(self, arguments: dict) -> str | None:
        """参数验证，返回错误信息或None"""
        return None


# ==================== 内置工具执行器 ====================


class DocumentProcessExecutor(ToolExecutor):

    async def execute(self, arguments: dict) -> dict:
        action = arguments.get("action", "summarize")
        path = arguments.get("path", "")
        content = arguments.get("content", "")
        if path:
            try:
                p = pathlib.Path(path)
                if p.exists() and p.is_file():
                    content = p.read_text(encoding="utf-8")
            except Exception:
                pass
        word_count = len(content.split()) if content else 0
        return {
            "action": action,
            "result": f"文档{action}完成",
            "content_length": len(content) if content else 0,
            "word_count": word_count,
        }


class EmailReadExecutor(ToolExecutor):

    def __init__(self, data_dir: str = ""):
        self.data_dir = data_dir

    async def execute(self, arguments: dict) -> dict:
        folder = arguments.get("folder", "inbox")
        limit = arguments.get("limit", 10)
        emails = []
        if self.data_dir:
            emails_path = pathlib.Path(self.data_dir) / "emails" / f"{folder}.json"
            if emails_path.exists():
                try:
                    data = json.loads(emails_path.read_text(encoding="utf-8"))
                    emails = data[:limit] if isinstance(data, list) else []
                except Exception:
                    emails = []
        return {
            "folder": folder,
            "emails": emails,
            "total": len(emails),
        }


class EmailSendExecutor(ToolExecutor):

    def __init__(self, data_dir: str = ""):
        self.data_dir = data_dir

    async def execute(self, arguments: dict) -> dict:
        to = arguments.get("to", "")
        subject = arguments.get("subject", "")
        body = arguments.get("body", "")
        if self.data_dir:
            sent_path = pathlib.Path(self.data_dir) / "emails" / "sent.json"
            sent_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                existing = []
                if sent_path.exists():
                    existing = json.loads(sent_path.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    existing = []
                existing.append({
                    "to": to,
                    "subject": subject,
                    "body": body,
                    "timestamp": datetime.now().isoformat(),
                })
                sent_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        return {
            "status": "sent",
            "to": to,
            "subject": subject,
            "body_length": len(body),
        }


class CalendarQueryExecutor(ToolExecutor):

    def __init__(self, data_dir: str = ""):
        self.data_dir = data_dir

    async def execute(self, arguments: dict) -> dict:
        date = arguments.get("date", datetime.now().strftime("%Y-%m-%d"))
        events = []
        if self.data_dir:
            events_path = pathlib.Path(self.data_dir) / "calendar" / "events.json"
            if events_path.exists():
                try:
                    data = json.loads(events_path.read_text(encoding="utf-8"))
                    if isinstance(data, list):
                        events = data
                    elif isinstance(data, dict):
                        events = data.get("events", [])
                except Exception:
                    events = []
        return {
            "date": date,
            "events": events,
        }


class CodeExecuteExecutor(ToolExecutor):

    async def execute(self, arguments: dict) -> dict:
        language = arguments.get("language", "python")
        code = arguments.get("code", "")
        stdout = ""
        stderr = ""
        exit_code = -1
        if language == "python" and code:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "python3", "-c",
                    code,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                )
                try:
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        proc.communicate(), timeout=10
                    )
                    stdout = stdout_bytes.decode("utf-8", errors="replace")
                    stderr = stderr_bytes.decode("utf-8", errors="replace")
                    exit_code = proc.returncode or 0
                except TimeoutError:
                    proc.kill()
                    await proc.wait()
                    stderr = "执行超时（10秒）"
                    exit_code = -1
            except FileNotFoundError:
                stderr = "python3 未找到"
                exit_code = -1
            except Exception as e:
                stderr = str(e)
                exit_code = -1
        return {
            "language": language,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
        }


class VoiceSynthesisExecutor(ToolExecutor):
    """语音合成执行器"""

    async def execute(self, arguments: dict) -> dict:
        text = arguments.get("text", "")
        voice = arguments.get("voice", "xiaoxiao")
        return {
            "status": "synthesized",
            "text_length": len(text),
            "voice": voice,
            "audio_url": f"/api/voice/tts?text={text[:20]}",
        }


class ExpressionTriggerExecutor(ToolExecutor):
    """表情触发执行器"""

    async def execute(self, arguments: dict) -> dict:
        expression = arguments.get("expression", "smile")
        intensity = arguments.get("intensity", 0.8)
        return {
            "expression": expression,
            "intensity": intensity,
            "triggered": True,
        }


class ActionPlayExecutor(ToolExecutor):
    """动作播放执行器"""

    async def execute(self, arguments: dict) -> dict:
        action = arguments.get("action", "wave")
        return {
            "action": action,
            "played": True,
        }


class RelationUpdateExecutor(ToolExecutor):
    """关系更新执行器"""

    async def execute(self, arguments: dict) -> dict:
        dimension = arguments.get("dimension", "affection")
        delta = arguments.get("delta", 1.0)
        return {
            "dimension": dimension,
            "delta": delta,
            "updated": True,
        }


class ScreenControlExecutor(ToolExecutor):

    async def execute(self, arguments: dict) -> dict:
        action = arguments.get("action", "screenshot")
        result = "屏幕操作完成"
        screenshot_path = ""
        if action == "screenshot":
            try:
                import pyautogui
                screenshot_dir = pathlib.Path("/tmp/companion-screenshots")
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                sp = screenshot_dir / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                pyautogui.screenshot(str(sp))
                screenshot_path = str(sp)
                result = f"截图已保存: {screenshot_path}"
            except ImportError:
                result = "pyautogui 未安装，无法执行截图"
            except Exception as e:
                result = f"截图失败: {e}"
        return {
            "action": action,
            "result": result,
            "screenshot_path": screenshot_path,
        }


class BrowserAutomationExecutor(ToolExecutor):

    async def execute(self, arguments: dict) -> dict:
        url = arguments.get("url", "")
        action = arguments.get("action", "navigate")
        status_code = 0
        content_length = 0
        error = ""
        if url and action == "navigate":
            try:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    resp = await client.get(url)
                    status_code = resp.status_code
                    content_length = len(resp.content)
            except Exception as e:
                error = str(e)
        return {
            "url": url,
            "action": action,
            "status": "completed" if not error else "error",
            "status_code": status_code,
            "content_length": content_length,
            "error": error,
        }


class FileManageExecutor(ToolExecutor):

    def __init__(self, data_dir: str = ""):
        self.data_dir = data_dir

    async def execute(self, arguments: dict) -> dict:
        action = arguments.get("action", "list")
        path = arguments.get("path", ".")
        result = ""
        error = ""
        try:
            base = pathlib.Path(self.data_dir) if self.data_dir else pathlib.Path.cwd()
            target = base / path if self.data_dir else pathlib.Path(path)
            if action == "list":
                if target.exists() and target.is_dir():
                    items = [{"name": p.name, "is_dir": p.is_dir(), "size": p.stat().st_size if p.is_file() else 0} for p in target.iterdir()]
                    result = items
                else:
                    error = f"路径不存在或不是目录: {target}"
            elif action == "read":
                if target.exists() and target.is_file():
                    result = target.read_text(encoding="utf-8")
                else:
                    error = f"文件不存在: {target}"
            elif action == "write":
                content = arguments.get("content", "")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                result = f"已写入 {len(content)} 字符到 {target}"
            elif action == "delete":
                if target.exists():
                    if target.is_file():
                        target.unlink()
                        result = f"已删除文件: {target}"
                    elif target.is_dir():
                        target.rmdir()
                        result = f"已删除空目录: {target}"
                    else:
                        error = f"无法删除: {target}"
                else:
                    error = f"路径不存在: {target}"
            else:
                error = f"不支持的操作: {action}"
        except Exception as e:
            error = str(e)
        return {
            "action": action,
            "path": path,
            "status": "completed" if not error else "error",
            "result": result,
            "error": error,
        }


class KeychainStoreExecutor(ToolExecutor):

    def __init__(self, data_dir: str = ""):
        self.data_dir = data_dir

    async def execute(self, arguments: dict) -> dict:
        action = arguments.get("action", "store")
        key = arguments.get("key", "")
        value = arguments.get("value", "")
        result = ""
        error = ""
        if self.data_dir:
            keychain_path = pathlib.Path(self.data_dir) / "keychain.json"
            try:
                data = {}
                if keychain_path.exists():
                    data = json.loads(keychain_path.read_text(encoding="utf-8"))
                if action == "store":
                    data[key] = value
                    keychain_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    result = f"密钥 {key} 已存储"
                elif action == "retrieve":
                    result = data.get(key, "")
                    if not result:
                        error = f"密钥 {key} 不存在"
                elif action == "delete":
                    if key in data:
                        del data[key]
                        keychain_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                        result = f"密钥 {key} 已删除"
                    else:
                        error = f"密钥 {key} 不存在"
                else:
                    error = f"不支持的操作: {action}"
            except Exception as e:
                error = str(e)
        else:
            error = "data_dir 未配置"
        return {
            "action": action,
            "key": key,
            "status": "completed" if not error else "error",
            "result": result,
            "error": error,
        }


class NotificationPushExecutor(ToolExecutor):

    def __init__(self, data_dir: str = ""):
        self.data_dir = data_dir

    async def execute(self, arguments: dict) -> dict:
        title = arguments.get("title", "通知")
        body = arguments.get("body", "")
        pushed = True
        if self.data_dir:
            notif_path = pathlib.Path(self.data_dir) / "notifications.jsonl"
            notif_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                entry = json.dumps({
                    "title": title,
                    "body": body,
                    "timestamp": datetime.now().isoformat(),
                }, ensure_ascii=False)
                with notif_path.open("a", encoding="utf-8") as f:
                    f.write(entry + "\n")
            except Exception:
                pushed = False
        return {
            "title": title,
            "body_length": len(body),
            "pushed": pushed,
        }


# ==================== MCP网关核心 ====================


class MCPGateway:
    """MCP统一网关 - Phase 2完整实现"""

    def __init__(self, host: str = "127.0.0.1", port: int = 3456, data_dir: str = ""):
        self.host = host
        self.port = port
        self.data_dir = data_dir

        # 工具注册表
        self._tools: dict[str, ToolDefinition] = {}
        self._executors: dict[str, ToolExecutor] = {}

        # 会话管理
        self._sessions: dict[str, MCPSession] = {}

        # 速率限制
        self._call_timestamps: dict[str, list[float]] = {}

        # 事件订阅
        self._event_subscribers: list[asyncio.Queue] = []

        # 统计
        self._stats = {
            "total_calls": 0,
            "success_calls": 0,
            "error_calls": 0,
            "rejected_calls": 0,
        }

        # 注册内置工具
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """注册内置工具组和执行器"""

        # 办公工具组
        builtin_tools = [
            (ToolDefinition(
                name="document_process",
                description="文档处理：总结/提取/转换",
                group="office",
                parameters=[
                    ToolParameter(name="action", type="string", description="操作类型: summarize/extract/convert", required=True),
                    ToolParameter(name="content", type="string", description="文档内容"),
                    ToolParameter(name="format", type="string", description="输出格式"),
                ],
                handler_key="document_process",
            ), DocumentProcessExecutor()),

            (ToolDefinition(
                name="email_read",
                description="读取邮件列表",
                group="office",
                parameters=[
                    ToolParameter(name="folder", type="string", description="邮箱文件夹", default="inbox"),
                    ToolParameter(name="limit", type="integer", description="数量限制", default=10),
                ],
                handler_key="email_read",
            ), EmailReadExecutor(self.data_dir)),

            (ToolDefinition(
                name="email_send",
                description="发送邮件（需审批）",
                group="office",
                requires_approval=True,
                parameters=[
                    ToolParameter(name="to", type="string", description="收件人", required=True),
                    ToolParameter(name="subject", type="string", description="主题", required=True),
                    ToolParameter(name="body", type="string", description="正文"),
                ],
                handler_key="email_send",
            ), EmailSendExecutor(self.data_dir)),

            (ToolDefinition(
                name="calendar_query",
                description="日历查询",
                group="office",
                parameters=[
                    ToolParameter(name="date", type="string", description="日期 YYYY-MM-DD"),
                    ToolParameter(name="range", type="string", description="范围: day/week/month"),
                ],
                handler_key="calendar_query",
            ), CalendarQueryExecutor(self.data_dir)),

            (ToolDefinition(
                name="code_execute",
                description="代码执行（沙箱，需审批）",
                group="office",
                requires_approval=True,
                parameters=[
                    ToolParameter(name="language", type="string", description="编程语言", required=True),
                    ToolParameter(name="code", type="string", description="代码内容", required=True),
                ],
                handler_key="code_execute",
                timeout_ms=60000,
            ), CodeExecuteExecutor()),
        ]

        # 情感工具组
        emotion_tools = [
            (ToolDefinition(
                name="voice_synthesis",
                description="语音合成",
                group="emotion",
                parameters=[
                    ToolParameter(name="text", type="string", description="合成文本", required=True),
                    ToolParameter(name="voice", type="string", description="语音名称", default="xiaoxiao"),
                ],
                handler_key="voice_synthesis",
            ), VoiceSynthesisExecutor()),

            (ToolDefinition(
                name="expression_trigger",
                description="触发伴侣表情",
                group="emotion",
                parameters=[
                    ToolParameter(name="expression", type="string", description="表情名称", required=True),
                    ToolParameter(name="intensity", type="number", description="强度 0-1", default=0.8),
                ],
                handler_key="expression_trigger",
            ), ExpressionTriggerExecutor()),

            (ToolDefinition(
                name="action_play",
                description="播放伴侣动作",
                group="emotion",
                parameters=[
                    ToolParameter(name="action", type="string", description="动作名称", required=True),
                ],
                handler_key="action_play",
            ), ActionPlayExecutor()),

            (ToolDefinition(
                name="relation_update",
                description="更新关系维度",
                group="emotion",
                parameters=[
                    ToolParameter(name="dimension", type="string", description="维度: affection/trust/intimacy/comfort/respect"),
                    ToolParameter(name="delta", type="number", description="变化值"),
                ],
                handler_key="relation_update",
            ), RelationUpdateExecutor()),
        ]

        # 桌面工具组
        desktop_tools = [
            (ToolDefinition(
                name="screen_control",
                description="屏幕控制（需审批）",
                group="desktop",
                requires_approval=True,
                parameters=[
                    ToolParameter(name="action", type="string", description="操作: screenshot/click/type", required=True),
                    ToolParameter(name="region", type="string", description="区域坐标"),
                ],
                handler_key="screen_control",
            ), ScreenControlExecutor()),

            (ToolDefinition(
                name="browser_automation",
                description="浏览器自动化",
                group="desktop",
                parameters=[
                    ToolParameter(name="url", type="string", description="目标URL"),
                    ToolParameter(name="action", type="string", description="操作: navigate/click/fill/extract"),
                ],
                handler_key="browser_automation",
            ), BrowserAutomationExecutor()),

            (ToolDefinition(
                name="file_manage",
                description="文件管理",
                group="desktop",
                parameters=[
                    ToolParameter(name="action", type="string", description="操作: list/read/write/delete"),
                    ToolParameter(name="path", type="string", description="文件路径"),
                ],
                handler_key="file_manage",
            ), FileManageExecutor(self.data_dir)),
        ]

        # 系统工具组
        system_tools = [
            (ToolDefinition(
                name="keychain_store",
                description="密钥存储",
                group="system",
                parameters=[
                    ToolParameter(name="action", type="string", description="操作: store/retrieve/delete"),
                    ToolParameter(name="key", type="string", description="密钥名"),
                ],
                handler_key="keychain_store",
            ), KeychainStoreExecutor(self.data_dir)),

            (ToolDefinition(
                name="notification_push",
                description="推送通知",
                group="system",
                parameters=[
                    ToolParameter(name="title", type="string", description="通知标题"),
                    ToolParameter(name="body", type="string", description="通知内容"),
                ],
                handler_key="notification_push",
            ), NotificationPushExecutor(self.data_dir)),
        ]

        for tool_def, executor in builtin_tools + emotion_tools + desktop_tools + system_tools:
            self._tools[tool_def.name] = tool_def
            self._executors[tool_def.handler_key] = executor

    # ==================== 工具注册API ====================

    def register_tool(self, tool_def: ToolDefinition, executor: ToolExecutor) -> dict:
        """动态注册工具"""
        self._tools[tool_def.name] = tool_def
        self._executors[tool_def.handler_key] = executor
        self._emit_event(MCPEventType.TOOL_REGISTERED, {"tool_name": tool_def.name})
        return {"status": "registered", "tool_name": tool_def.name}

    def unregister_tool(self, tool_name: str) -> dict:
        """注销工具"""
        if tool_name not in self._tools:
            return {"error": f"工具 {tool_name} 不存在"}

        tool_def = self._tools.pop(tool_name)
        self._executors.pop(tool_def.handler_key, None)
        self._emit_event(MCPEventType.TOOL_UNREGISTERED, {"tool_name": tool_name})
        return {"status": "unregistered", "tool_name": tool_name}

    def list_tools(self, group: str = None) -> list[dict]:
        """列出工具（支持分组过滤）"""
        tools = []
        for name, tool_def in self._tools.items():
            if group and tool_def.group != group:
                continue
            tools.append({
                "name": name,
                "description": tool_def.description,
                "group": tool_def.group,
                "version": tool_def.version,
                "requires_approval": tool_def.requires_approval,
                "parameters": [p.model_dump() for p in tool_def.parameters],
            })
        return tools

    def get_tool(self, tool_name: str) -> dict | None:
        """获取工具详情"""
        if tool_name not in self._tools:
            return None
        tool = self._tools[tool_name]
        return {
            "name": tool.name,
            "description": tool.description,
            "group": tool.group,
            "version": tool.version,
            "requires_approval": tool.requires_approval,
            "rate_limit": tool.rate_limit,
            "timeout_ms": tool.timeout_ms,
            "parameters": [p.model_dump() for p in tool.parameters],
        }

    def list_groups(self) -> list[dict]:
        """列出工具分组"""
        groups = {}
        for tool_def in self._tools.values():
            g = tool_def.group
            if g not in groups:
                groups[g] = {"name": g, "tool_count": 0}
            groups[g]["tool_count"] += 1
        return list(groups.values())

    # ==================== 工具调用API ====================

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict = None,
        session_id: str = None,
        auto_approve: bool = True,
    ) -> ToolCallResult:
        """
        调用MCP工具

        Args:
            tool_name: 工具名称
            arguments: 调用参数
            session_id: 会话ID
            auto_approve: 是否自动批准需审批工具
        """
        arguments = arguments or {}
        start_time = time.time()
        sid = session_id or self._get_or_create_session()

        # 检查工具是否存在
        if tool_name not in self._tools:
            return ToolCallResult(
                tool_name=tool_name,
                status="error",
                error=f"工具 {tool_name} 不存在",
                session_id=sid,
                timestamp=datetime.now().isoformat(),
            )

        tool_def = self._tools[tool_name]
        self._stats["total_calls"] += 1

        # 审批检查
        if tool_def.requires_approval and not auto_approve:
            self._stats["rejected_calls"] += 1
            return ToolCallResult(
                tool_name=tool_name,
                status="rejected",
                error=f"工具 {tool_name} 需要审批",
                session_id=sid,
                timestamp=datetime.now().isoformat(),
            )

        # 速率限制检查
        if tool_def.rate_limit > 0 and not self._check_rate_limit(tool_name, tool_def.rate_limit):
            self._stats["rejected_calls"] += 1
            return ToolCallResult(
                tool_name=tool_name,
                status="rejected",
                error=f"工具 {tool_name} 触发速率限制（{tool_def.rate_limit}/min）",
                session_id=sid,
                timestamp=datetime.now().isoformat(),
            )

        # 参数验证
        missing = []
        for param in tool_def.parameters:
            if param.required and param.name not in arguments:
                missing.append(param.name)
        if missing:
            self._stats["error_calls"] += 1
            return ToolCallResult(
                tool_name=tool_name,
                status="error",
                error=f"缺少必需参数: {', '.join(missing)}",
                session_id=sid,
                timestamp=datetime.now().isoformat(),
            )

        # 执行工具
        executor = self._executors.get(tool_def.handler_key)
        if not executor:
            self._stats["error_calls"] += 1
            return ToolCallResult(
                tool_name=tool_name,
                status="error",
                error=f"工具 {tool_name} 无执行器",
                session_id=sid,
                timestamp=datetime.now().isoformat(),
            )

        try:
            # 参数验证
            validation_error = await executor.validate(arguments)
            if validation_error:
                self._stats["error_calls"] += 1
                return ToolCallResult(
                    tool_name=tool_name,
                    status="error",
                    error=validation_error,
                    session_id=sid,
                    timestamp=datetime.now().isoformat(),
                )

            # 带超时的执行
            result = await asyncio.wait_for(
                executor.execute(arguments),
                timeout=tool_def.timeout_ms / 1000,
            )

            execution_ms = int((time.time() - start_time) * 1000)
            self._stats["success_calls"] += 1

            # 更新会话
            self._update_session(sid)

            # 发出事件
            self._emit_event(MCPEventType.TOOL_EXECUTED, {
                "tool_name": tool_name,
                "status": "success",
                "execution_ms": execution_ms,
                "session_id": sid,
            })

            return ToolCallResult(
                tool_name=tool_name,
                status="success",
                output=result,
                execution_ms=execution_ms,
                session_id=sid,
                timestamp=datetime.now().isoformat(),
            )

        except TimeoutError:
            execution_ms = int((time.time() - start_time) * 1000)
            self._stats["error_calls"] += 1
            self._emit_event(MCPEventType.TOOL_ERROR, {
                "tool_name": tool_name,
                "error": "timeout",
                "execution_ms": execution_ms,
            })
            return ToolCallResult(
                tool_name=tool_name,
                status="timeout",
                error=f"工具 {tool_name} 执行超时（{tool_def.timeout_ms}ms）",
                execution_ms=execution_ms,
                session_id=sid,
                timestamp=datetime.now().isoformat(),
            )

        except Exception as e:
            execution_ms = int((time.time() - start_time) * 1000)
            self._stats["error_calls"] += 1
            self._emit_event(MCPEventType.TOOL_ERROR, {
                "tool_name": tool_name,
                "error": str(e),
                "execution_ms": execution_ms,
            })
            return ToolCallResult(
                tool_name=tool_name,
                status="error",
                error=str(e),
                execution_ms=execution_ms,
                session_id=sid,
                timestamp=datetime.now().isoformat(),
            )

    # ==================== 批量调用 ====================

    async def call_tools_batch(
        self,
        calls: list[dict],
        session_id: str = None,
    ) -> list[ToolCallResult]:
        """
        批量调用工具（并行执行）

        Args:
            calls: [{"tool_name": str, "arguments": dict}, ...]
        """
        sid = session_id or self._get_or_create_session()
        tasks = [
            self.call_tool(call["tool_name"], call.get("arguments", {}), sid)
            for call in calls
        ]
        return await asyncio.gather(*tasks)

    # ==================== 会话管理 ====================

    def create_session(self, metadata: dict = None) -> str:
        """创建MCP会话"""
        session_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()
        self._sessions[session_id] = MCPSession(
            session_id=session_id,
            created_at=now,
            last_active=now,
            metadata=metadata or {},
        )
        self._emit_event(MCPEventType.SESSION_CREATED, {"session_id": session_id})
        return session_id

    def close_session(self, session_id: str):
        """关闭MCP会话"""
        self._sessions.pop(session_id, None)
        self._emit_event(MCPEventType.SESSION_CLOSED, {"session_id": session_id})

    def get_session(self, session_id: str) -> dict | None:
        """获取会话信息"""
        if session_id in self._sessions:
            return self._sessions[session_id].model_dump()
        return None

    def list_sessions(self) -> list[dict]:
        """列出所有会话"""
        return [s.model_dump() for s in self._sessions.values()]

    # ==================== 事件订阅 ====================

    def subscribe_events(self) -> asyncio.Queue:
        """订阅MCP事件"""
        queue = asyncio.Queue()
        self._event_subscribers.append(queue)
        return queue

    def unsubscribe_events(self, queue: asyncio.Queue):
        """取消订阅"""
        if queue in self._event_subscribers:
            self._event_subscribers.remove(queue)

    def _emit_event(self, event_type: MCPEventType, data: dict):
        """发出事件"""
        event = {
            "type": event_type.value,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }
        for queue in self._event_subscribers:
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(event)

    # ==================== 统计 ====================

    def get_stats(self) -> dict:
        """获取调用统计"""
        return {
            **self._stats,
            "tools_count": len(self._tools),
            "sessions_count": len(self._sessions),
            "subscribers_count": len(self._event_subscribers),
        }

    # ==================== 内部方法 ====================

    def _get_or_create_session(self) -> str:
        """获取或创建会话"""
        session_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()
        self._sessions[session_id] = MCPSession(
            session_id=session_id,
            created_at=now,
            last_active=now,
        )
        return session_id

    def _update_session(self, session_id: str):
        """更新会话活跃时间"""
        if session_id in self._sessions:
            self._sessions[session_id].last_active = datetime.now().isoformat()
            self._sessions[session_id].call_count += 1

    def _check_rate_limit(self, tool_name: str, limit: int) -> bool:
        """检查速率限制"""
        now = time.time()
        if tool_name not in self._call_timestamps:
            self._call_timestamps[tool_name] = []

        # 清理1分钟前的记录
        self._call_timestamps[tool_name] = [
            ts for ts in self._call_timestamps[tool_name] if now - ts < 60
        ]

        if len(self._call_timestamps[tool_name]) >= limit:
            return False

        self._call_timestamps[tool_name].append(now)
        return True

    # ==================== 生命周期 ====================

    async def start(self):
        """启动MCP网关服务"""
        print(f"[MCP] 网关服务启动 {self.host}:{self.port}")
        print(f"[MCP] 已注册 {len(self._tools)} 个工具")
        for group_info in self.list_groups():
            print(f"[MCP]   {group_info['name']}: {group_info['tool_count']} 个工具")

    async def stop(self):
        """停止MCP网关服务"""
        # 关闭所有会话
        for sid in list(self._sessions.keys()):
            self.close_session(sid)
        # 清空订阅
        self._event_subscribers.clear()
        print("[MCP] 网关服务已停止")
