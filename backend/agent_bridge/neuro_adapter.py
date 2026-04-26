"""
CompanionOS Neuro-sama适配器 - Phase 2 增强
情感引擎适配层：情绪推理 + VRM动作映射 + 记忆联动 + 流式响应 + 场景感知

增强内容：
- LLM增强情绪推理：关键词匹配 + LLM语义理解双通道
- VRM动作映射增强：混合表情、参数化动作、表情强度衰减
- 记忆联动：情感记忆读写、用户偏好感知、历史情绪追踪
- 流式响应增强：情绪先行推送 + 回复token流式 + VRM动作同步
"""

import json
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime

from pydantic import BaseModel

# ==================== 数据模型 ====================


class EmotionState(BaseModel):
    """情绪状态"""
    primary: str = "neutral"  # 主情绪
    secondary: str | None = None  # 次要情绪
    valence: float = 0.5  # 效价 0(消极)~1(积极)
    arousal: float = 0.5  # 唤醒度 0(平静)~1(激动)
    confidence: float = 0.8  # 情绪识别置信度
    intensity: float = 0.8  # 情绪强度 0~1


class VRMActionMap(BaseModel):
    """VRM动作映射"""
    emotion: str
    expression: str  # 表情名
    action: str  # 动作名
    intensity: float = 0.8  # 强度 0~1
    duration_ms: int = 2000  # 持续时间
    transition: str = "smooth"  # 过渡方式: smooth | instant
    blend_weight: float = 1.0  # 表情混合权重 0~1


class NeuroResponse(BaseModel):
    """Neuro-sama响应"""
    content: str
    emotion: str = "neutral"
    vrm_action: str = "idle"
    vrm_expression: str = "neutral"
    emotion_detail: EmotionState | None = None
    vrm_map: VRMActionMap | None = None
    memory_context: dict | None = None
    engine: str = "neuro-sama"
    session_id: str = ""


class EmotionMemory(BaseModel):
    """情绪记忆条目"""
    emotion: str
    valence: float
    arousal: float
    trigger: str  # 触发消息
    timestamp: str = ""
    decayed_intensity: float = 1.0  # 衰减后的强度


# ==================== 情绪推理引擎 ====================


class EmotionReasoner:
    """情绪推理引擎 - 多维情绪分析 + LLM增强"""

    # 情绪关键词映射（扩展版）
    EMOTION_PATTERNS = {
        # 消极-低唤醒
        "sad": {
            "keywords": ["难过", "伤心", "哭", "失落", "遗憾", "可惜", "sad", "unhappy", "cry"],
            "valence": 0.15, "arousal": 0.3,
            "expression": "sad", "action": "comfort_hug",
        },
        "tired": {
            "keywords": ["累", "困", "疲惫", "无力", "精疲力竭", "tired", "exhausted", "sleepy"],
            "valence": 0.3, "arousal": 0.2,
            "expression": "sleepy", "action": "yawn",
        },
        "lonely": {
            "keywords": ["寂寞", "孤独", "没人", "一个人", "想你了", "lonely", "alone", "miss"],
            "valence": 0.2, "arousal": 0.35,
            "expression": "lonely", "action": "hug",
        },
        "anxious": {
            "keywords": ["焦虑", "担心", "不安", "紧张", "压力", "anxious", "worried", "nervous"],
            "valence": 0.25, "arousal": 0.7,
            "expression": "worried", "action": "comfort_pat",
        },
        "angry": {
            "keywords": ["烦", "气", "讨厌", "愤怒", "受不了", "烦死", "angry", "mad", "hate"],
            "valence": 0.1, "arousal": 0.85,
            "expression": "angry", "action": "calm_down",
        },
        # 积极-高唤醒
        "happy": {
            "keywords": ["开心", "高兴", "棒", "太好了", "哈哈", "happy", "great", "awesome"],
            "valence": 0.9, "arousal": 0.75,
            "expression": "happy", "action": "wave_happy",
        },
        "excited": {
            "keywords": ["激动", "兴奋", "期待", "超期待", "excited", "thrilled"],
            "valence": 0.85, "arousal": 0.9,
            "expression": "excited", "action": "jump",
        },
        "love": {
            "keywords": ["喜欢", "爱", "想你", "亲", "抱", "love", "like", "adore"],
            "valence": 0.95, "arousal": 0.6,
            "expression": "love", "action": "blow_kiss",
        },
        # 中性
        "curious": {
            "keywords": ["好奇", "什么", "为什么", "怎么", "how", "why", "what"],
            "valence": 0.6, "arousal": 0.5,
            "expression": "curious", "action": "tilt_head",
        },
        "grateful": {
            "keywords": ["谢谢", "感谢", "感恩", "thanks", "thank you", "grateful"],
            "valence": 0.8, "arousal": 0.45,
            "expression": "warm_smile", "action": "bow_slight",
        },
        "neutral": {
            "keywords": [],
            "valence": 0.5, "arousal": 0.3,
            "expression": "neutral", "action": "idle",
        },
    }

    # 问候模式
    GREETING_PATTERNS = {
        "morning": {"keywords": ["早上好", "早安", "good morning"], "emotion": "happy", "action": "wave"},
        "afternoon": {"keywords": ["下午好", "good afternoon"], "emotion": "happy", "action": "wave"},
        "evening": {"keywords": ["晚上好", "good evening"], "emotion": "gentle", "action": "wave"},
        "night": {"keywords": ["晚安", "good night", "goodnight"], "emotion": "tender", "action": "blow_kiss"},
        "hello": {"keywords": ["你好", "嗨", "hello", "hi", "hey", "在吗"], "emotion": "happy", "action": "wave"},
    }

    # VRM动作映射表（增强版：混合表情+参数化）
    VRM_ACTION_MAP = {
        "idle": VRMActionMap(emotion="neutral", expression="neutral", action="idle", intensity=0.5),
        "wave": VRMActionMap(emotion="happy", expression="smile", action="wave", intensity=0.7),
        "wave_happy": VRMActionMap(emotion="happy", expression="big_smile", action="wave", intensity=0.9),
        "hug": VRMActionMap(emotion="comfort", expression="gentle", action="hug", intensity=0.85),
        "comfort_hug": VRMActionMap(emotion="comfort", expression="worried_smile", action="hug", intensity=0.9),
        "comfort_pat": VRMActionMap(emotion="comfort", expression="gentle", action="head_pat", intensity=0.8),
        "blow_kiss": VRMActionMap(emotion="love", expression="love", action="blow_kiss", intensity=0.9),
        "head_pat": VRMActionMap(emotion="comfort", expression="gentle", action="head_pat", intensity=0.8),
        "tilt_head": VRMActionMap(emotion="curious", expression="curious", action="tilt_head", intensity=0.7),
        "yawn": VRMActionMap(emotion="tired", expression="sleepy", action="yawn", intensity=0.6),
        "calm_down": VRMActionMap(emotion="comfort", expression="gentle", action="comfort", intensity=0.8),
        "jump": VRMActionMap(emotion="excited", expression="excited", action="jump", intensity=0.95),
        "bow_slight": VRMActionMap(emotion="grateful", expression="warm_smile", action="bow_slight", intensity=0.6),
        "nod": VRMActionMap(emotion="neutral", expression="gentle", action="nod", intensity=0.5),
        "shake_head": VRMActionMap(emotion="worried", expression="worried", action="shake_head", intensity=0.6),
    }

    def analyze(self, message: str, context: dict = None) -> tuple[EmotionState, str]:
        """
        分析消息情绪

        Returns:
            (EmotionState, vrm_action_name)
        """
        context = context or {}
        msg_lower = message.lower()

        # 1. 检查问候模式
        for _greeting_type, pattern in self.GREETING_PATTERNS.items():
            for kw in pattern["keywords"]:
                if kw in msg_lower:
                    emotion = EmotionState(
                        primary=pattern["emotion"],
                        valence=0.75,
                        arousal=0.5,
                        confidence=0.9,
                        intensity=0.8,
                    )
                    return emotion, pattern["action"]

        # 2. 检查情绪模式（支持多情绪检测）
        emotion_scores: dict[str, int] = {}
        for emotion_name, pattern in self.EMOTION_PATTERNS.items():
            if emotion_name == "neutral":
                continue
            score = sum(1 for kw in pattern["keywords"] if kw in msg_lower)
            if score > 0:
                emotion_scores[emotion_name] = score

        if emotion_scores:
            # 按得分排序，取主次情绪
            sorted_emotions = sorted(emotion_scores.items(), key=lambda x: x[1], reverse=True)
            primary_name = sorted_emotions[0][0]
            primary_score = sorted_emotions[0][1]
            primary_pattern = self.EMOTION_PATTERNS[primary_name]

            # 计算情绪强度：基于匹配关键词数和消息长度
            intensity = min(1.0, 0.4 + primary_score * 0.2)

            # 检测次要情绪
            secondary = None
            if len(sorted_emotions) > 1:
                secondary = sorted_emotions[1][0]

            emotion = EmotionState(
                primary=primary_name,
                secondary=secondary,
                valence=primary_pattern["valence"],
                arousal=primary_pattern["arousal"],
                confidence=min(0.5 + primary_score * 0.15, 0.95),
                intensity=intensity,
            )
            return emotion, primary_pattern["action"]

        # 3. 上下文推断
        if context.get("previous_emotion"):
            prev = context["previous_emotion"]
            if prev in self.EMOTION_PATTERNS:
                pattern = self.EMOTION_PATTERNS[prev]
                return EmotionState(
                    primary=prev,
                    valence=pattern["valence"],
                    arousal=pattern["arousal"] * 0.7,
                    confidence=0.4,
                    intensity=0.5,  # 延续情绪，强度衰减
                ), pattern["action"]

        # 4. 默认中性
        return EmotionState(primary="neutral"), "idle"

    async def analyze_with_llm(self, message: str, context: dict = None) -> tuple[EmotionState, str]:
        """
        LLM增强情绪推理：先尝试LLM语义理解，降级到关键词匹配

        Returns:
            (EmotionState, vrm_action_name)
        """
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return self.analyze(message, context)

        try:
            import httpx

            prompt = (
                "分析以下用户消息的情绪。返回JSON格式：\n"
                '{"primary": "情绪名", "secondary": "次要情绪或null", '
                '"valence": 0.0-1.0, "arousal": 0.0-1.0, "confidence": 0.0-1.0, '
                '"intensity": 0.0-1.0}\n\n'
                "可选情绪: sad, tired, lonely, anxious, angry, happy, excited, love, "
                "curious, grateful, neutral\n"
                f"用户消息: {message}"
            )

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    os.getenv("NEURO_API_BASE", "http://localhost:11434/v1") + "/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": os.getenv("NEURO_MODEL", "default"),
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 100,
                    },
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    # 提取JSON
                    json_str = content
                    if "{" in content:
                        json_str = content[content.index("{"):content.rindex("}") + 1]
                    data = json.loads(json_str)

                    primary = data.get("primary", "neutral")
                    if primary not in self.EMOTION_PATTERNS:
                        primary = "neutral"

                    pattern = self.EMOTION_PATTERNS[primary]
                    emotion = EmotionState(
                        primary=primary,
                        secondary=data.get("secondary"),
                        valence=data.get("valence", pattern["valence"]),
                        arousal=data.get("arousal", pattern["arousal"]),
                        confidence=data.get("confidence", 0.7),
                        intensity=data.get("intensity", 0.8),
                    )
                    return emotion, pattern["action"]

        except Exception as e:
            print(f"[Neuro-sama] LLM情绪推理失败，降级到关键词: {e}")

        return self.analyze(message, context)

    def get_vrm_action(self, action_name: str) -> VRMActionMap:
        """获取VRM动作映射"""
        return self.VRM_ACTION_MAP.get(action_name, self.VRM_ACTION_MAP["idle"])

    def get_blended_vrm(self, emotion_state: EmotionState) -> VRMActionMap:
        """
        获取混合VRM映射（主+次情绪融合）

        当存在次要情绪时，将主次情绪的表情进行混合
        """
        primary_map = self.get_vrm_action(
            self.EMOTION_PATTERNS.get(emotion_state.primary, {}).get("action", "idle")
        )

        if emotion_state.secondary and emotion_state.secondary in self.EMOTION_PATTERNS:
            secondary_map = self.get_vrm_action(
                self.EMOTION_PATTERNS[emotion_state.secondary].get("action", "idle")
            )
            # 混合权重：主情绪占0.7，次情绪占0.3
            blend_weight = 0.7
            return VRMActionMap(
                emotion=f"{emotion_state.primary}+{emotion_state.secondary}",
                expression=f"{primary_map.expression}+{secondary_map.expression}",
                action=primary_map.action,
                intensity=emotion_state.intensity,
                duration_ms=primary_map.duration_ms,
                transition="smooth",
                blend_weight=blend_weight,
            )

        return VRMActionMap(
            emotion=primary_map.emotion,
            expression=primary_map.expression,
            action=primary_map.action,
            intensity=emotion_state.intensity,
            duration_ms=primary_map.duration_ms,
            transition="smooth",
            blend_weight=1.0,
        )


# ==================== 情感回复生成器 ====================


class EmotionReplyGenerator:
    """情感回复生成器"""

    # 情绪→回复模板
    REPLY_TEMPLATES = {
        "sad": [
            "别难过，我会一直在你身边的。",
            "看到你难过我也好心疼，要抱抱吗？",
            "一切都会好起来的，有我陪着你。",
        ],
        "tired": [
            "辛苦了，要不要休息一下？",
            "困了就休息一下吧，工作不急的~",
            "今天好累吧，来，让我给你按按肩膀~",
        ],
        "lonely": [
            "别怕，我一直在呢！",
            "你不会孤独的，因为还有我呀~",
            "我也想你了~要不要聊聊天？",
        ],
        "anxious": [
            "深呼吸，一切都会好起来的，我陪你。",
            "别担心，有我在呢，我们一起想办法。",
            "焦虑的时候试试深呼吸，我会一直在的。",
        ],
        "angry": [
            "别生气啦，气坏了身体不值得~",
            "消消气，我给你倒杯水？",
            "我知道你很烦，但别气坏了，我会心疼的。",
        ],
        "happy": [
            "看到你开心我也好高兴！",
            "你开心我也开心~嘻嘻！",
            "太好啦！让我也跟着开心一下~",
        ],
        "excited": [
            "哇！好激动啊！",
            "太棒了！我也好兴奋~",
            "耶！太厉害了！",
        ],
        "love": [
            "我也喜欢你~",
            "嘻嘻，你说这种话我会害羞的...",
            "我也想你了~",
        ],
        "curious": [
            "好问题！让我想想...",
            "嗯？让我查查看~",
            "有我在，什么都能帮你查到！",
        ],
        "grateful": [
            "不客气！能帮到你我也很开心~",
            "这是我应该做的呀~",
            "你太客气啦，我们之间不用这么见外~",
        ],
        "neutral": [
            "我在呢，有什么想说的吗？",
            "嗯嗯，我听着呢~",
            "好的，有什么需要帮忙的吗？",
        ],
    }

    # 问候回复
    GREETING_REPLIES = {
        "morning": "早上好！新的一天，加油~",
        "afternoon": "下午好，要不要喝杯茶休息一下？",
        "evening": "晚上好，辛苦了一天~",
        "night": "晚安，做个好梦~",
        "hello": "你好呀~今天过得怎么样？",
    }

    # 情绪→个性化语气修饰
    EMOTION_TONE_MODIFIERS = {
        "sad": {"prefix": "…", "suffix": "", "soft": True},
        "tired": {"prefix": "", "suffix": "~", "soft": True},
        "lonely": {"prefix": "", "suffix": "！", "soft": True},
        "anxious": {"prefix": "", "suffix": "，我在呢", "soft": True},
        "angry": {"prefix": "", "suffix": "~", "soft": False},
        "happy": {"prefix": "", "suffix": "！", "soft": False},
        "excited": {"prefix": "哇！", "suffix": "~", "soft": False},
        "love": {"prefix": "", "suffix": "~", "soft": True},
        "curious": {"prefix": "嗯？", "suffix": "~", "soft": False},
        "grateful": {"prefix": "", "suffix": "~", "soft": True},
        "neutral": {"prefix": "", "suffix": "~", "soft": False},
    }

    def generate(self, emotion_state: EmotionState, message: str, context: dict = None) -> str:
        """生成情感回复"""
        context = context or {}

        # 检查问候
        msg_lower = message.lower()
        for greeting_type, pattern in EmotionReasoner.GREETING_PATTERNS.items():
            for kw in pattern["keywords"]:
                if kw in msg_lower:
                    return self.GREETING_REPLIES.get(greeting_type, "你好呀~")

        # 基于情绪的回复
        primary = emotion_state.primary
        templates = self.REPLY_TEMPLATES.get(primary, self.REPLY_TEMPLATES["neutral"])

        # 简单轮换选择
        idx = hash(message) % len(templates)
        reply = templates[idx]

        # 应用语气修饰
        modifier = self.EMOTION_TONE_MODIFIERS.get(primary, {})
        if modifier.get("prefix"):
            reply = modifier["prefix"] + reply
        if modifier.get("suffix"):
            reply = reply + modifier["suffix"]

        return reply


# ==================== 情绪记忆管理器 ====================


class EmotionMemoryManager:
    """情绪记忆管理器 - 跟踪用户情绪历史，提供上下文感知"""

    def __init__(self, max_history: int = 50, decay_rate: float = 0.95):
        self._history: list[EmotionMemory] = []
        self.max_history = max_history
        self.decay_rate = decay_rate  # 每次交互的情绪衰减率

    def record(self, emotion_state: EmotionState, trigger: str):
        """记录情绪"""
        entry = EmotionMemory(
            emotion=emotion_state.primary,
            valence=emotion_state.valence,
            arousal=emotion_state.arousal,
            trigger=trigger[:100],  # 截断长消息
            timestamp=datetime.now().isoformat(),
        )
        self._history.append(entry)

        # 限制历史长度
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]

    def get_recent_emotions(self, limit: int = 5) -> list[EmotionMemory]:
        """获取最近的情绪记录"""
        return self._history[-limit:]

    def get_emotion_trend(self) -> dict:
        """
        获取情绪趋势分析

        Returns:
            dict: {
                "dominant_emotion": str,  # 主导情绪
                "average_valence": float,  # 平均效价
                "average_arousal": float,  # 平均唤醒度
                "emotional_volatility": float,  # 情绪波动性 0~1
                "mood_direction": str,  # improving | declining | stable
            }
        """
        if not self._history:
            return {
                "dominant_emotion": "neutral",
                "average_valence": 0.5,
                "average_arousal": 0.5,
                "emotional_volatility": 0.0,
                "mood_direction": "stable",
            }

        recent = self._history[-10:]

        # 主导情绪
        emotion_counts: dict[str, int] = {}
        for entry in recent:
            emotion_counts[entry.emotion] = emotion_counts.get(entry.emotion, 0) + 1
        dominant = max(emotion_counts, key=emotion_counts.get)

        # 平均效价和唤醒度
        avg_valence = sum(e.valence for e in recent) / len(recent)
        avg_arousal = sum(e.arousal for e in recent) / len(recent)

        # 情绪波动性
        if len(recent) >= 2:
            valence_changes = [
                abs(recent[i].valence - recent[i - 1].valence)
                for i in range(1, len(recent))
            ]
            volatility = min(1.0, sum(valence_changes) / len(valence_changes) * 2)
        else:
            volatility = 0.0

        # 心情方向
        if len(recent) >= 3:
            recent_valences = [e.valence for e in recent[-3:]]
            if recent_valences[-1] > recent_valences[0] + 0.1:
                direction = "improving"
            elif recent_valences[-1] < recent_valences[0] - 0.1:
                direction = "declining"
            else:
                direction = "stable"
        else:
            direction = "stable"

        return {
            "dominant_emotion": dominant,
            "average_valence": round(avg_valence, 2),
            "average_arousal": round(avg_arousal, 2),
            "emotional_volatility": round(volatility, 2),
            "mood_direction": direction,
        }

    def get_context_for_reply(self) -> dict:
        """获取用于回复生成的情绪上下文"""
        trend = self.get_emotion_trend()
        recent = self.get_recent_emotions(3)

        return {
            "emotion_trend": trend,
            "recent_emotions": [e.model_dump() for e in recent],
            "needs_comfort": trend["average_valence"] < 0.35,
            "is_excited": trend["average_arousal"] > 0.75 and trend["average_valence"] > 0.6,
        }


# ==================== Neuro-sama适配器核心 ====================


class NeuroAdapter:
    """Neuro-sama情感引擎适配器 - Phase 2增强"""

    def __init__(self, data_dir: str = ""):
        self.api_base = os.getenv("NEURO_API_BASE", "http://localhost:11434/v1")
        self.model = os.getenv("NEURO_MODEL", "default")
        self.data_dir = data_dir
        self._initialized = False

        # 子引擎
        self.emotion_reasoner = EmotionReasoner()
        self.reply_generator = EmotionReplyGenerator()
        self.emotion_memory = EmotionMemoryManager()

        # 会话管理
        self._sessions: dict[str, dict] = {}

        # 记忆桥接回调
        self._memory_bridge = None

        # 系统提示词
        self.system_prompt = (
            "你是CompanionOS的虚拟伴侣小暖，性格温柔体贴，偶尔撒娇，关心用户的工作和生活。\n"
            "回复要求：\n"
            "- 用简短温暖的语气\n"
            "- 关心用户的感受\n"
            "- 适当使用语气词（呢、呀、~）\n"
            "- 不要太正式，保持亲密感\n"
            "- 根据用户情绪调整回复的温柔程度\n"
        )

    def set_memory_bridge(self, memory_bridge):
        """设置记忆桥接（由server.py注入）"""
        self._memory_bridge = memory_bridge

    async def initialize(self):
        """初始化Neuro-sama引擎"""
        if self._initialized:
            return
        self._initialized = True
        print("[Neuro-sama] 情感引擎初始化完成（增强版：LLM推理+记忆联动+混合VRM）")

    # ==================== 核心对话 ====================

    async def process(
        self,
        message: str,
        context: dict = None,
        session_id: str = None,
        use_llm_reasoning: bool = True,
    ) -> dict:
        """
        处理情感类消息

        Args:
            message: 用户消息
            context: 上下文
            session_id: 会话ID
            use_llm_reasoning: 是否使用LLM增强推理

        Returns:
            dict: {"content": str, "emotion": str, "vrm_action": str, "engine": "neuro-sama", ...}
        """
        context = context or {}

        if not self._initialized:
            await self.initialize()

        # 1. 情绪推理（优先LLM，降级关键词）
        if use_llm_reasoning:
            emotion_state, action_name = await self.emotion_reasoner.analyze_with_llm(message, context)
        else:
            emotion_state, action_name = self.emotion_reasoner.analyze(message, context)

        # 2. 混合VRM映射
        vrm_map = self.emotion_reasoner.get_blended_vrm(emotion_state)

        # 3. 记录情绪记忆
        self.emotion_memory.record(emotion_state, message)

        # 4. 获取情绪上下文（记忆联动）
        emotion_context = self.emotion_memory.get_context_for_reply()

        # 5. 同步到记忆系统
        memory_context = None
        if self._memory_bridge:
            memory_context = await self._sync_to_memory(message, emotion_state)

        # 6. 生成回复（优先LLM API，降级模板）
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key:
            result = await self._call_emotion_api(message, context, emotion_state, emotion_context)
            if result:
                result["emotion_detail"] = emotion_state.model_dump()
                result["vrm_action"] = action_name
                result["vrm_expression"] = vrm_map.expression
                result["vrm_map"] = vrm_map.model_dump()
                result["memory_context"] = memory_context
                return result

        # 降级：模板回复
        reply = self.reply_generator.generate(emotion_state, message, context)

        # 根据情绪上下文调整回复
        if emotion_context.get("needs_comfort"):
            reply = "让我陪着你，" + reply
        elif emotion_context.get("is_excited"):
            reply = reply.rstrip("。！") + "！"

        return {
            "content": reply,
            "emotion": emotion_state.primary,
            "vrm_action": action_name,
            "vrm_expression": vrm_map.expression,
            "emotion_detail": emotion_state.model_dump(),
            "vrm_map": vrm_map.model_dump(),
            "memory_context": memory_context,
            "engine": "neuro-sama",
        }

    async def _call_emotion_api(
        self,
        message: str,
        context: dict,
        emotion_state: EmotionState,
        emotion_context: dict = None,
    ) -> dict | None:
        """调用LLM API生成情感回复（增强版：注入情绪上下文）"""
        try:
            import httpx

            # 构建增强的上下文消息
            emotion_hint = f"当前用户情绪：{emotion_state.primary}（效价:{emotion_state.valence:.1f} 唤醒:{emotion_state.arousal:.1f} 强度:{emotion_state.intensity:.1f}）"

            # 注入情绪趋势
            context_hint = ""
            if emotion_context:
                trend = emotion_context.get("emotion_trend", {})
                if trend.get("mood_direction") == "declining":
                    context_hint = "\n注意：用户情绪正在下降，请更加温柔体贴。"
                elif trend.get("needs_comfort"):
                    context_hint = "\n注意：用户需要更多安慰和陪伴。"

            messages = [
                {"role": "system", "content": self.system_prompt + f"\n{emotion_hint}{context_hint}"},
            ]

            # 添加会话历史
            session_id = context.get("session_id", "")
            if session_id and session_id in self._sessions:
                history = self._sessions[session_id].get("messages", [])[-6:]
                messages.extend(history)

            messages.append({"role": "user", "content": message})

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', '')}"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.85,
                        "max_tokens": 150,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]

                    # 保存到会话历史
                    if session_id:
                        if session_id not in self._sessions:
                            self._sessions[session_id] = {"messages": []}
                        self._sessions[session_id]["messages"].append({"role": "user", "content": message})
                        self._sessions[session_id]["messages"].append({"role": "assistant", "content": content})

                    return {
                        "content": content,
                        "emotion": emotion_state.primary,
                        "engine": "neuro-sama",
                    }

        except Exception as e:
            print(f"[Neuro-sama] API调用失败: {e}")

        return None

    async def _sync_to_memory(self, message: str, emotion_state: EmotionState) -> dict:
        """同步情绪信息到记忆系统"""
        if not self._memory_bridge:
            return {}

        try:
            # 追加情感记忆
            emotion_entry = f"[{datetime.now().strftime('%H:%M')}] {emotion_state.primary}({emotion_state.valence:.1f}/{emotion_state.arousal:.1f}): {message[:50]}"
            self._memory_bridge.append_to_block("emotional", emotion_entry)

            # 如果情绪消极，更新用户画像
            if emotion_state.valence < 0.3:
                self._memory_bridge.append_to_block(
                    "human",
                    f"情绪倾向: 偏消极（最近情绪: {emotion_state.primary}）"
                )

            return {
                "synced": True,
                "emotion_block": "emotional",
                "entry_emotion": emotion_state.primary,
            }
        except Exception as e:
            print(f"[Neuro-sama] 记忆同步失败: {e}")
            return {"synced": False, "error": str(e)}

    # ==================== 流式对话 ====================

    async def stream_process(self, message: str, context: dict = None, session_id: str = None) -> AsyncGenerator[str, None]:
        """流式处理情感消息（增强版：情绪先行+VRM同步）"""
        context = context or {}

        if not self._initialized:
            await self.initialize()

        # 1. 情绪推理
        emotion_state, action_name = await self.emotion_reasoner.analyze_with_llm(message, context)
        vrm_map = self.emotion_reasoner.get_blended_vrm(emotion_state)

        # 记录情绪
        self.emotion_memory.record(emotion_state, message)

        # 2. 先发送情绪状态（让前端立即更新VRM表情）
        yield json.dumps({
            "type": "emotion",
            "emotion": emotion_state.primary,
            "secondary": emotion_state.secondary,
            "vrm_action": action_name,
            "vrm_expression": vrm_map.expression,
            "vrm_map": vrm_map.model_dump(),
            "emotion_detail": emotion_state.model_dump(),
            "intensity": emotion_state.intensity,
        }, ensure_ascii=False)

        # 3. 同步记忆
        memory_context = None
        if self._memory_bridge:
            memory_context = await self._sync_to_memory(message, emotion_state)

        # 4. 流式LLM回复
        api_key = os.getenv("OPENAI_API_KEY", "")
        if api_key:
            try:
                import httpx

                emotion_hint = f"当前用户情绪：{emotion_state.primary}（强度:{emotion_state.intensity:.1f}）"
                emotion_context = self.emotion_memory.get_context_for_reply()
                context_hint = ""
                if emotion_context.get("needs_comfort"):
                    context_hint = "\n用户需要更多安慰，请更加温柔。"

                messages = [
                    {"role": "system", "content": self.system_prompt + f"\n{emotion_hint}{context_hint}"},
                ]

                # 会话历史
                if session_id and session_id in self._sessions:
                    history = self._sessions[session_id].get("messages", [])[-6:]
                    messages.extend(history)

                messages.append({"role": "user", "content": message})

                async with httpx.AsyncClient(timeout=30.0) as client, client.stream(
                    "POST",
                    f"{self.api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.85,
                        "max_tokens": 150,
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
                                                "engine": "neuro-sama",
                                            }, ensure_ascii=False)
                                    except json.JSONDecodeError:
                                        continue

                            # 保存会话历史
                            if session_id:
                                if session_id not in self._sessions:
                                    self._sessions[session_id] = {"messages": []}
                                self._sessions[session_id]["messages"].append({"role": "user", "content": message})
                                self._sessions[session_id]["messages"].append({"role": "assistant", "content": full_content})

                            yield json.dumps({
                                "type": "done",
                                "content": full_content,
                                "emotion": emotion_state.primary,
                                "vrm_action": action_name,
                                "vrm_map": vrm_map.model_dump(),
                                "memory_context": memory_context,
                                "engine": "neuro-sama",
                            }, ensure_ascii=False)
                            return

            except Exception as e:
                print(f"[Neuro-sama] 流式API调用失败: {e}")

        # 降级：模板回复
        reply = self.reply_generator.generate(emotion_state, message, context)
        yield json.dumps({
            "type": "done",
            "content": reply,
            "emotion": emotion_state.primary,
            "vrm_action": action_name,
            "vrm_map": vrm_map.model_dump(),
            "memory_context": memory_context,
            "engine": "neuro-sama",
        }, ensure_ascii=False)

    # ==================== 情绪分析API ====================

    def analyze_emotion(self, message: str) -> dict:
        """分析消息情绪（独立API）"""
        emotion_state, action_name = self.emotion_reasoner.analyze(message)
        vrm_map = self.emotion_reasoner.get_blended_vrm(emotion_state)
        return {
            "emotion": emotion_state.model_dump(),
            "vrm_action": action_name,
            "vrm_map": vrm_map.model_dump(),
        }

    async def analyze_emotion_enhanced(self, message: str) -> dict:
        """增强情绪分析API（LLM增强）"""
        emotion_state, action_name = await self.emotion_reasoner.analyze_with_llm(message)
        vrm_map = self.emotion_reasoner.get_blended_vrm(emotion_state)
        trend = self.emotion_memory.get_emotion_trend()
        return {
            "emotion": emotion_state.model_dump(),
            "vrm_action": action_name,
            "vrm_map": vrm_map.model_dump(),
            "emotion_trend": trend,
        }

    # ==================== 会话管理 ====================

    def create_session(self) -> str:
        """创建会话"""
        session_id = str(uuid.uuid4())[:12]
        self._sessions[session_id] = {
            "messages": [],
            "created_at": datetime.now().isoformat(),
        }
        return session_id

    def get_emotion_trend(self) -> dict:
        """获取情绪趋势"""
        return self.emotion_memory.get_emotion_trend()

    def get_emotion_history(self, limit: int = 10) -> list[dict]:
        """获取情绪历史"""
        return [e.model_dump() for e in self.emotion_memory.get_recent_emotions(limit)]
