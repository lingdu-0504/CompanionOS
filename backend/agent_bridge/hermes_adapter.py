"""
CompanionOS Hermes适配器 - Phase 2 增强
办公引擎适配层：自学习引擎骨架 + 工具注册到MCP + 上下文压缩 + 流式响应 + 会话管理
"""

import json
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from pydantic import BaseModel

# ==================== 数据模型 ====================


class HermesMessage(BaseModel):
    """Hermes消息"""
    role: str  # system | user | assistant | tool
    content: str
    name: str | None = None  # tool调用时的工具名
    tool_call_id: str | None = None


class HermesToolCall(BaseModel):
    """工具调用请求"""
    id: str
    name: str
    arguments: dict


class HermesResponse(BaseModel):
    """Hermes响应"""
    content: str
    engine: str = "hermes"
    tool_calls: list[HermesToolCall] = []
    usage: dict = {}
    model: str = ""
    finish_reason: str = "stop"  # stop | tool_calls | length


class SkillRecord(BaseModel):
    """自学习技能记录"""
    skill_id: str
    name: str
    description: str
    pattern: str  # 触发模式
    template: str  # 回复模板
    usage_count: int = 0
    success_rate: float = 1.0
    learned_at: str = ""
    last_used_at: str = ""


class SessionContext(BaseModel):
    """会话上下文"""
    session_id: str
    messages: list[dict] = []
    token_count: int = 0
    max_tokens: int = 8000
    created_at: str = ""
    last_active: str = ""


# ==================== 上下文压缩器 ====================


class ContextCompressor:
    """上下文压缩器 - 超出token限制时自动压缩历史"""

    def __init__(self, max_tokens: int = 8000, summary_ratio: float = 0.3):
        self.max_tokens = max_tokens
        self.summary_ratio = summary_ratio

    def estimate_tokens(self, messages: list[dict]) -> int:
        """估算token数（简化：1个中文字≈2token，1个英文词≈1.3token）"""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            # 粗略估算
            chinese_chars = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
            total += chinese_chars * 2 + (len(content) - chinese_chars) * 0.5
        return int(total)

    def compress(self, messages: list[dict]) -> list[dict]:
        """压缩历史消息"""
        if not messages:
            return messages

        tokens = self.estimate_tokens(messages)
        if tokens <= self.max_tokens:
            return messages

        # 保留system消息和最近的消息
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        # 压缩早期消息
        keep_count = max(2, int(len(non_system) * (1 - self.summary_ratio)))
        compressed = non_system[:len(non_system) - keep_count]
        recent = non_system[len(non_system) - keep_count:]

        # 生成摘要
        summary_text = self._generate_summary(compressed)
        summary_msg = {
            "role": "system",
            "content": f"[上下文摘要] {summary_text}",
        }

        return system_msgs + [summary_msg] + recent

    def _generate_summary(self, messages: list[dict]) -> str:
        """生成消息摘要（简化版，后续用LLM生成）"""
        if not messages:
            return ""

        topics = []
        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")
            if role == "user" and content:
                # 取用户消息的前30字作为主题
                topics.append(content[:30])
            if len(topics) >= 5:
                break

        if topics:
            return f"之前讨论了: {'; '.join(topics)}"
        return "之前的对话内容已压缩"


# ==================== 自学习引擎 ====================


class SelfLearningEngine:
    """自学习引擎 - 从交互中积累技能"""

    def __init__(self, data_dir: str = ""):
        self.skills: dict[str, SkillRecord] = {}
        self.data_dir = data_dir
        self._load_skills()

    def _load_skills(self):
        """加载已有技能"""
        if not self.data_dir:
            return
        skills_path = os.path.join(data_dir, "skills", "hermes_skills.json") if (data_dir := self.data_dir) else None
        if skills_path and os.path.exists(skills_path):
            try:
                with open(skills_path, encoding="utf-8") as f:
                    data = json.load(f)
                    for skill_data in data:
                        skill = SkillRecord(**skill_data)
                        self.skills[skill.skill_id] = skill
            except Exception as e:
                print(f"[Hermes-SL] 加载技能失败: {e}")

    def _save_skills(self):
        """保存技能"""
        if not self.data_dir:
            return
        skills_dir = os.path.join(self.data_dir, "skills")
        os.makedirs(skills_dir, exist_ok=True)
        skills_path = os.path.join(skills_dir, "hermes_skills.json")
        try:
            with open(skills_path, "w", encoding="utf-8") as f:
                json.dump(
                    [s.model_dump() for s in self.skills.values()],
                    f, ensure_ascii=False, indent=2,
                )
        except Exception as e:
            print(f"[Hermes-SL] 保存技能失败: {e}")

    def learn(self, name: str, pattern: str, template: str, description: str = "") -> SkillRecord:
        """学习新技能"""
        skill_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        skill = SkillRecord(
            skill_id=skill_id,
            name=name,
            description=description or name,
            pattern=pattern,
            template=template,
            learned_at=now,
            last_used_at=now,
        )
        self.skills[skill_id] = skill
        self._save_skills()
        return skill

    def match(self, message: str) -> SkillRecord | None:
        """匹配技能"""
        for skill in self.skills.values():
            if skill.pattern.lower() in message.lower():
                skill.usage_count += 1
                skill.last_used_at = datetime.now().isoformat()
                return skill
        return None

    def record_success(self, skill_id: str, success: bool):
        """记录技能使用结果"""
        if skill_id in self.skills:
            skill = self.skills[skill_id]
            # 简单移动平均更新成功率
            alpha = 0.1
            skill.success_rate = skill.success_rate * (1 - alpha) + (1.0 if success else 0.0) * alpha

    def list_skills(self) -> list[dict]:
        """列出所有技能"""
        return [s.model_dump() for s in self.skills.values()]


# ==================== Hermes适配器核心 ====================


class HermesAdapter:
    """Hermes办公引擎适配器 - Phase 2增强"""

    def __init__(self, data_dir: str = ""):
        self.api_base = os.getenv("HERMES_API_BASE", "http://localhost:11434/v1")
        self.model = os.getenv("HERMES_MODEL", "default")
        self._initialized = False

        # 上下文压缩
        self.context_compressor = ContextCompressor()

        # 自学习引擎
        self.self_learning = SelfLearningEngine(data_dir)

        # 会话管理
        self._sessions: dict[str, SessionContext] = {}

        # MCP工具注册回调
        self._mcp_register_callback: callable | None = None

        # 系统提示词
        self.system_prompt = (
            "你是CompanionOS的办公助手Hermes，专门帮助用户处理工作任务。\n"
            "核心能力：文档处理、邮件管理、日历查询、代码执行、数据分析。\n"
            "工作方式：\n"
            "- 直接高效地回答问题\n"
            "- 复杂任务提供分步方案\n"
            "- 主动建议优化方案\n"
            "- 需要执行操作时通过工具调用\n"
        )

    async def initialize(self):
        """初始化Hermes引擎"""
        if self._initialized:
            return

        self._initialized = True
        print("[Hermes] 办公引擎初始化完成")

        # 注册自带工具到MCP
        if self._mcp_register_callback:
            self._register_tools_to_mcp()

    def set_mcp_register_callback(self, callback: callable):
        """设置MCP工具注册回调"""
        self._mcp_register_callback = callback

    def _register_tools_to_mcp(self):
        """注册Hermes工具到MCP网关"""
        if not self._mcp_register_callback:
            return

        hermes_tools = [
            {
                "name": "hermes_learn_from_interaction",
                "description": "从交互中学习，更新Hermes的技能知识库",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "interaction": {"type": "string", "description": "用户交互内容"},
                        "response": {"type": "string", "description": "Hermes的回复"},
                        "feedback": {"type": "string", "description": "用户反馈（可选）"},
                    },
                    "required": ["interaction", "response"],
                },
                "handler": self._tool_learn_from_interaction,
            },
            {
                "name": "hermes_get_skills",
                "description": "获取Hermes已学习的技能列表",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
                "handler": self._tool_get_skills,
            },
            {
                "name": "hermes_forget_skill",
                "description": "删除指定的已学习技能",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "skill_id": {"type": "string", "description": "技能ID"},
                    },
                    "required": ["skill_id"],
                },
                "handler": self._tool_forget_skill,
            },
        ]

        for tool in hermes_tools:
            try:
                self._mcp_register_callback(
                    name=tool["name"],
                    description=tool["description"],
                    input_schema=tool["input_schema"],
                    handler=tool["handler"],
                    group="hermes",
                )
            except Exception as e:
                print(f"[Hermes] 注册工具失败 {tool['name']}: {e}")

    async def _tool_learn_from_interaction(self, params: dict) -> dict:
        """从交互中学习"""
        interaction = params.get("interaction", "")
        response = params.get("response", "")
        feedback = params.get("feedback", "")

        try:
            skill = self.self_learning.learn(
                name=f"interaction_{interaction[:20]}",
                pattern=interaction[:50],
                template=response,
                description=feedback or "从交互中自动学习",
            )
            return {"status": "success", "learned": True, "skill_id": skill.skill_id}
        except Exception as e:
            return {"status": "error", "learned": False, "error": str(e)[:100]}

    async def _tool_get_skills(self, params: dict) -> dict:
        """获取已学习的技能列表"""
        try:
            skills = self.self_learning.list_skills()
            return {"status": "success", "skills": skills[:50], "total": len(skills)}
        except Exception as e:
            return {"status": "error", "error": str(e)[:100]}

    async def _tool_forget_skill(self, params: dict) -> dict:
        """删除指定的技能"""
        skill_id = params.get("skill_id", "")
        if not skill_id:
            return {"status": "error", "error": "缺少 skill_id"}

        try:
            if skill_id in self.self_learning.skills:
                del self.self_learning.skills[skill_id]
                self.self_learning._save_skills()
                return {"status": "success", "forgotten": True}
            return {"status": "error", "forgotten": False, "error": f"技能 {skill_id} 不存在"}
        except Exception as e:
            return {"status": "error", "error": str(e)[:100]}

    # ==================== 会话管理 ====================

    def create_session(self, metadata: dict = None) -> str:
        """创建会话"""
        session_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()
        self._sessions[session_id] = SessionContext(
            session_id=session_id,
            messages=[{"role": "system", "content": self.system_prompt}],
            created_at=now,
            last_active=now,
        )
        return session_id

    def get_session(self, session_id: str) -> SessionContext | None:
        """获取会话"""
        return self._sessions.get(session_id)

    def close_session(self, session_id: str):
        """关闭会话"""
        self._sessions.pop(session_id, None)

    # ==================== 核心对话 ====================

    async def process(
        self,
        message: str,
        context: dict = None,
        session_id: str = None,
        stream: bool = False,
    ) -> dict:
        """
        处理办公类消息

        Args:
            message: 用户消息
            context: 上下文
            session_id: 会话ID
            stream: 是否流式返回

        Returns:
            dict: {"content": str, "engine": "hermes", "tool_calls": list, ...}
        """
        context = context or {}

        if not self._initialized:
            await self.initialize()

        # 获取或创建会话
        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
        else:
            session_id = self.create_session()
            session = self._sessions[session_id]

        # 添加用户消息
        session.messages.append({"role": "user", "content": message})
        session.last_active = datetime.now().isoformat()

        # 1. 检查自学习技能匹配
        skill = self.self_learning.match(message)
        if skill and skill.success_rate > 0.7:
            skill_content = skill.template.replace("{input}", message)
            session.messages.append({"role": "assistant", "content": skill_content})
            self.self_learning.record_success(skill.skill_id, True)
            return {
                "content": skill_content,
                "engine": "hermes",
                "tool_calls": [],
                "session_id": session_id,
                "source": "self_learning",
            }

        # 2. 上下文压缩
        session.messages = self.context_compressor.compress(session.messages)
        session.token_count = self.context_compressor.estimate_tokens(session.messages)

        # 3. 调用LLM API
        result = await self._call_llm(message, session, stream)

        # 4. 添加助手回复到会话
        session.messages.append({"role": "assistant", "content": result["content"]})

        result["session_id"] = session_id
        return result

    async def _call_llm(self, message: str, session: SessionContext, stream: bool = False) -> dict:
        """调用LLM API"""
        try:
            import httpx

            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                return self._fallback_response(message)

            async with httpx.AsyncClient(timeout=60.0) as client:
                payload = {
                    "model": self.model,
                    "messages": session.messages[-20:],  # 最近20条消息
                    "temperature": 0.7,
                    "max_tokens": 2000,
                }

                if stream:
                    payload["stream"] = True
                    # 流式调用由 stream_process 处理
                    return await self._call_llm_stream(message, session)

                resp = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=payload,
                )

                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]

                    # 提取工具调用
                    tool_calls = []
                    raw_tool_calls = data["choices"][0].get("message", {}).get("tool_calls", [])
                    for tc in raw_tool_calls:
                        tool_calls.append({
                            "id": tc.get("id", ""),
                            "name": tc["function"]["name"],
                            "arguments": json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"],
                        })

                    return {
                        "content": content,
                        "engine": "hermes",
                        "tool_calls": tool_calls,
                        "usage": data.get("usage", {}),
                        "model": data.get("model", self.model),
                        "finish_reason": data["choices"][0].get("finish_reason", "stop"),
                    }

        except Exception as e:
            print(f"[Hermes] API调用失败: {e}")

        return self._fallback_response(message)

    async def _call_llm_stream(self, message: str, session: SessionContext) -> dict:
        """流式调用LLM API（返回完整结果，流式由上层处理）"""
        # 流式实际由 server.py 的 SSE 接口处理
        # 这里返回普通结果
        return await self._call_llm(message, session, stream=False)

    async def stream_process(self, message: str, context: dict = None, session_id: str = None) -> AsyncGenerator[str, None]:
        """
        流式处理消息（逐token输出）

        Yields:
            str: SSE格式的数据片段
        """
        context = context or {}

        if not self._initialized:
            await self.initialize()

        if session_id and session_id in self._sessions:
            session = self._sessions[session_id]
        else:
            session_id = self.create_session()
            session = self._sessions[session_id]

        session.messages.append({"role": "user", "content": message})

        try:
            import httpx

            api_key = os.getenv("OPENAI_API_KEY", "")
            if api_key:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    messages = self.context_compressor.compress(session.messages[-20:])

                    async with client.stream(
                        "POST",
                        f"{self.api_base}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={
                            "model": self.model,
                            "messages": messages,
                            "temperature": 0.7,
                            "max_tokens": 2000,
                            "stream": True,
                        },
                    ) as resp:
                        if resp.status_code == 200:
                            full_content = ""
                            async for line in resp.aiter_lines():
                                if line.startswith("data: "):
                                    data_str = line[6:]
                                    if data_str == "[DONE]":
                                        break
                                    try:
                                        data = json.loads(data_str)
                                        delta = data.get("choices", [{}])[0].get("delta", {})
                                        token = delta.get("content", "")
                                        if token:
                                            full_content += token
                                            yield json.dumps({
                                                "type": "token",
                                                "content": token,
                                                "engine": "hermes",
                                            }, ensure_ascii=False)
                                    except json.JSONDecodeError:
                                        continue

                            session.messages.append({"role": "assistant", "content": full_content})

                            yield json.dumps({
                                "type": "done",
                                "content": full_content,
                                "engine": "hermes",
                                "session_id": session_id,
                            }, ensure_ascii=False)
                            return

        except Exception as e:
            print(f"[Hermes] 流式API调用失败: {e}")

        # 降级：非流式返回
        result = self._fallback_response(message)
        session.messages.append({"role": "assistant", "content": result["content"]})
        yield json.dumps({
            "type": "done",
            **result,
            "session_id": session_id,
        }, ensure_ascii=False)

    def _fallback_response(self, message: str) -> dict:
        """降级响应"""
        # 基于关键词的智能回复
        responses = {
            "总结": "好的，我来帮你总结。请提供需要总结的内容，我会生成简洁的摘要。",
            "报告": "我来帮你准备报告。请告诉我：1）报告类型 2）时间范围 3）关键指标",
            "邮件": "好的，请告诉我收件人、主题和主要内容，我来帮你处理邮件。",
            "周报": "好的，我来帮你生成周报。请提供本周的主要工作和成果。",
            "代码": "好的，我来帮你处理代码相关的问题。请描述你的需求。",
            "数据": "我来帮你分析数据。请提供数据来源和分析需求。",
            "翻译": "好的，请提供需要翻译的内容和目标语言。",
            "会议": "我来帮你管理会议。需要查询日程还是安排新会议？",
        }

        for keyword, reply in responses.items():
            if keyword in message:
                return {
                    "content": reply,
                    "engine": "hermes",
                    "tool_calls": [],
                }

        return {
            "content": f"[办公引擎] 已收到指令：{message}\n正在分析中...（API未配置，降级模式运行）",
            "engine": "hermes",
            "tool_calls": [],
        }

    # ==================== 自学习API ====================

    def learn_skill(self, name: str, pattern: str, template: str, description: str = "") -> dict:
        """学习新技能"""
        skill = self.self_learning.learn(name, pattern, template, description)
        return {"status": "learned", "skill_id": skill.skill_id, "name": skill.name}

    def list_skills(self) -> list[dict]:
        """列出已学技能"""
        return self.self_learning.list_skills()

    # ==================== 工具调用 ====================

    async def execute_tool(self, tool_name: str, arguments: dict, mcp_gateway=None) -> dict:
        """通过MCP网关执行工具"""
        if mcp_gateway:
            result = await mcp_gateway.call_tool(tool_name, arguments)
            return result.model_dump()

        return {
            "status": "error",
            "error": "MCP网关未连接",
        }
