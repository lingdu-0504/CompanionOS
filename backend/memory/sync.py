"""
CompanionOS 记忆同步
多源记忆同步（Hermes + Neuro-sama + Letta）
"""

import os
from datetime import datetime


class MemorySync:
    """多源记忆同步器"""

    def __init__(self, memory_bridge):
        self.bridge = memory_bridge

    async def sync_interaction(self, interaction: dict):
        """
        同步交互记忆

        Args:
            interaction: 交互记录 {
                "user_input": str,
                "intent": str,
                "response": str,
                "emotion": Optional[str],
            }
        """
        intent = interaction.get("intent", "")
        emotion = interaction.get("emotion")

        # 根据意图类型更新不同记忆块
        if intent in ("work", "mixed"):
            work_content = f"[{datetime.now().strftime('%H:%M')}] {interaction.get('user_input', '')}"
            self.bridge.append_to_block("work", work_content)

        if intent in ("emotional", "mixed") and emotion:
            emotion_content = f"[{datetime.now().strftime('%H:%M')}] 用户情绪: {emotion}"
            self.bridge.append_to_block("emotional", emotion_content)

    async def update_user_profile(self, key: str, value: str):
        """更新用户画像（LLM智能合并，降级到简单追加）"""
        current = self.bridge.get_block("human")
        existing = current.get("value", "")
        new_entry = f"{key}: {value}"

        if key in existing:
            return

        try:
            merged = await self._merge_with_llm(existing, key, value)
            if merged:
                self.bridge.save_block("human", merged)
                return
        except Exception:
            pass

        self.bridge.append_to_block("human", new_entry)

    async def _merge_with_llm(self, existing: str, key: str, value: str) -> str | None:
        """使用LLM智能合并用户画像信息"""
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return None

        import httpx

        api_base = os.getenv("OPENAI_API_BASE", "http://localhost:11434/v1")
        model = os.getenv("OPENAI_MODEL", "default")

        system_prompt = (
            "你是一个用户画像信息合并助手。你的任务是将新的用户信息智能合并到已有的用户画像中。\n"
            "规则：\n"
            "1. 去重：如果已有信息已包含相同内容，不要重复添加\n"
            "2. 更新：如果新信息是对已有信息的更新，替换旧信息\n"
            "3. 合并冲突：如果新旧信息有冲突，以新信息为准\n"
            "4. 保持格式：每行一个属性，格式为「属性名: 属性值」\n"
            "5. 只返回合并后的文本内容，不要添加任何解释或标记"
        )

        user_prompt = (
            "以下是当前的用户画像信息：\n"
            f"{existing}\n\n"
            f"需要合并的新信息：\n"
            f"{key}: {value}\n\n"
            "请将新信息智能合并到用户画像中，返回合并后的完整文本。"
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 1000,
                    },
                )
                if resp.status_code == 200:
                    result = resp.json()["choices"][0]["message"]["content"].strip()
                    if result:
                        return result
        except Exception:
            return None

        return None
