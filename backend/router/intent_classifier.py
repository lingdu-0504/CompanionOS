"""
CompanionOS 意图分类器 - Phase 2 升级
基于规则的轻量级意图识别 + LLM增强（可选）

增强内容：
- 扩展关键词覆盖
- LLM语义理解（降级到关键词）
- 多意图检测
- 置信度校准
"""

import json
import os
from enum import StrEnum


class IntentType(StrEnum):
    """意图类型枚举"""
    WORK = "work"
    EMOTIONAL = "emotional"
    MIXED = "mixed"
    GREETING = "greeting"


# 办公关键词（扩展版）
WORK_KEYWORDS = [
    "总结", "报告", "周报", "邮件", "文档", "Excel", "PPT", "会议",
    "日程", "任务", "待办", "翻译", "数据分析", "代码", "部署",
    "API", "数据库", "SQL", "服务器", "运维", "监控", "日志",
    "搜索", "查询", "编写", "生成", "转换", "格式化", "计算",
    "截图", "浏览器", "自动化", "脚本", "爬虫", "抓取",
    "help me", "summarize", "report", "email", "document", "schedule",
    "work", "task", "translate", "code", "deploy", "search", "create",
    "generate", "analyze", "convert", "automate", "script",
]

# 情感关键词（扩展版）
EMOTION_KEYWORDS = [
    "好累", "开心", "难过", "无聊", "烦", "想你了", "辛苦", "加班",
    "讨厌", "喜欢", "寂寞", "压力大", "焦虑", "伤心", "孤独",
    "烦死了", "不想", "好烦", "好困", "饿了", "无聊",
    "生气", "感动", "幸福", "温暖", "害怕", "担心", "紧张",
    "安慰", "陪伴", "撒娇", "依赖", "在乎", "心疼",
    "tired", "happy", "sad", "bored", "miss you", "stressed",
    "lonely", "anxious", "hungry", "angry", "scared", "worried",
    "comfort", "lonely", "love", "hug", "miss",
]

# 问候关键词
GREETING_KEYWORDS = [
    "你好", "嗨", "早上好", "晚安", "hello", "hi", "hey",
    "在吗", "你在", "下午好", "晚上好", "早安", "早",
    "good morning", "good night", "good evening",
]

# Eigent相关关键词（用于判断是否需要Agent执行）
EIGENT_BROWSER_KEYWORDS = ["搜索", "查找", "浏览", "网页", "search", "browse", "scrape", "crawl", "打开网址"]
EIGENT_DOCUMENT_KEYWORDS = ["文档", "写", "报告", "转换", "格式化", "document", "create", "format", "生成报告", "周报"]
EIGENT_DEVELOPER_KEYWORDS = ["代码", "运行", "执行", "debug", "code", "run", "execute", "deploy", "编程", "脚本"]
EIGENT_MULTIMODAL_KEYWORDS = ["图片", "照片", "视频", "音频", "image", "video", "audio", "ocr", "识别"]


def classify_intent(message: str) -> dict:
    """
    分类用户意图

    Returns:
        dict: {
            "intent": "work" | "emotional" | "mixed" | "greeting",
            "confidence": float,
            "keywords_matched": list[str],
            "eigent_agents": list[str]  # 建议调用的Eigent Agent
        }
    """
    msg_lower = message.lower()

    work_matches = [kw for kw in WORK_KEYWORDS if kw in msg_lower]
    emotion_matches = [kw for kw in EMOTION_KEYWORDS if kw in msg_lower]
    greeting_matches = [kw for kw in GREETING_KEYWORDS if kw in msg_lower]

    # 判断Eigent Agent需求
    eigent_agents = []
    if any(kw in msg_lower for kw in EIGENT_BROWSER_KEYWORDS):
        eigent_agents.append("browser")
    if any(kw in msg_lower for kw in EIGENT_DOCUMENT_KEYWORDS):
        eigent_agents.append("document")
    if any(kw in msg_lower for kw in EIGENT_DEVELOPER_KEYWORDS):
        eigent_agents.append("developer")
    if any(kw in msg_lower for kw in EIGENT_MULTIMODAL_KEYWORDS):
        eigent_agents.append("multimodal")

    is_work = len(work_matches) > 0
    is_emotion = len(emotion_matches) > 0
    is_greeting = len(greeting_matches) > 0 and not is_work and not is_emotion

    if is_greeting:
        return {
            "intent": IntentType.GREETING.value,
            "confidence": 0.9,
            "keywords_matched": greeting_matches,
            "eigent_agents": [],
        }
    elif is_work and is_emotion:
        return {
            "intent": IntentType.MIXED.value,
            "confidence": 0.7,
            "keywords_matched": work_matches + emotion_matches,
            "eigent_agents": eigent_agents,
        }
    elif is_work:
        return {
            "intent": IntentType.WORK.value,
            "confidence": min(0.6 + len(work_matches) * 0.08, 0.95),
            "keywords_matched": work_matches,
            "eigent_agents": eigent_agents,
        }
    elif is_emotion:
        return {
            "intent": IntentType.EMOTIONAL.value,
            "confidence": min(0.6 + len(emotion_matches) * 0.1, 0.95),
            "keywords_matched": emotion_matches,
            "eigent_agents": [],
        }
    else:
        # 默认混合处理，交给双引擎
        return {
            "intent": IntentType.MIXED.value,
            "confidence": 0.5,
            "keywords_matched": [],
            "eigent_agents": eigent_agents,
        }


async def classify_intent_with_llm(message: str) -> dict:
    """
    LLM增强意图分类：先尝试LLM语义理解，降级到关键词匹配

    Returns:
        dict: 同 classify_intent 格式，额外包含 "llm_enhanced": bool
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        result = classify_intent(message)
        result["llm_enhanced"] = False
        return result

    try:
        import httpx

        prompt = (
            "分类以下用户消息的意图。返回JSON格式：\n"
            '{"intent": "work|emotional|mixed|greeting", "confidence": 0.0-1.0, '
            '"eigent_agents": ["browser"|"document"|"developer"|"multimodal"], '
            '"reason": "分类理由"}\n\n'
            f"用户消息: {message}\n\n"
            "分类标准:\n"
            "- work: 工作相关（文档、代码、搜索、数据分析等）\n"
            "- emotional: 情感相关（心情、感受、需要安慰等）\n"
            "- mixed: 同时包含工作和情感\n"
            "- greeting: 纯问候"
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                os.getenv("OPENAI_API_BASE", "http://localhost:11434/v1") + "/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": os.getenv("OPENAI_MODEL", "default"),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 200,
                },
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                # 提取JSON
                json_str = content
                if "{" in content:
                    json_str = content[content.index("{"):content.rindex("}") + 1]
                data = json.loads(json_str)

                intent = data.get("intent", "mixed")
                if intent not in ("work", "emotional", "mixed", "greeting"):
                    intent = "mixed"

                # 用关键词匹配补充 eigent_agents
                msg_lower = message.lower()
                eigent_agents = []
                if any(kw in msg_lower for kw in EIGENT_BROWSER_KEYWORDS):
                    eigent_agents.append("browser")
                if any(kw in msg_lower for kw in EIGENT_DOCUMENT_KEYWORDS):
                    eigent_agents.append("document")
                if any(kw in msg_lower for kw in EIGENT_DEVELOPER_KEYWORDS):
                    eigent_agents.append("developer")
                if any(kw in msg_lower for kw in EIGENT_MULTIMODAL_KEYWORDS):
                    eigent_agents.append("multimodal")

                # 合并LLM识别的eigent_agents
                for agent in data.get("eigent_agents", []):
                    if agent not in eigent_agents:
                        eigent_agents.append(agent)

                return {
                    "intent": intent,
                    "confidence": data.get("confidence", 0.7),
                    "keywords_matched": [],
                    "eigent_agents": eigent_agents,
                    "llm_enhanced": True,
                    "llm_reason": data.get("reason", ""),
                }

    except Exception as e:
        print(f"[IntentClassifier] LLM分类失败，降级到关键词: {e}")

    result = classify_intent(message)
    result["llm_enhanced"] = False
    return result
