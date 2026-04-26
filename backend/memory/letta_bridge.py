"""
CompanionOS 记忆系统
Letta记忆中枢桥接 + 多源记忆同步
"""

import json
from datetime import datetime
from pathlib import Path


class MemoryBridge:
    """记忆桥接器 - 统一记忆接口"""

    # 记忆块类型定义
    BLOCK_TYPES = ["human", "persona", "work", "emotional", "skills"]

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir / "memories"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._init_default_blocks()

    def _init_default_blocks(self):
        """初始化默认记忆块"""
        defaults = {
            "human": "用户信息待填充",
            "persona": "我是小暖，温柔体贴的桌面女友，关心用户的工作和生活",
            "work": "",
            "emotional": "",
            "skills": "",
        }
        for block_type, value in defaults.items():
            path = self.data_dir / f"{block_type}.json"
            if not path.exists():
                self.save_block(block_type, value)

    def get_block(self, block_type: str) -> dict:
        """获取记忆块"""
        if block_type not in self.BLOCK_TYPES:
            return {"error": f"未知记忆块类型: {block_type}"}

        path = self.data_dir / f"{block_type}.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return {"label": block_type, "value": ""}

    def save_block(self, block_type: str, value: str) -> dict:
        """保存记忆块"""
        if block_type not in self.BLOCK_TYPES:
            return {"error": f"未知记忆块类型: {block_type}"}

        data = {
            "label": block_type,
            "value": value,
            "updated_at": datetime.now().isoformat(),
        }
        path = self.data_dir / f"{block_type}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return data

    def get_all_blocks(self) -> dict:
        """获取所有记忆块"""
        return {
            block_type: self.get_block(block_type)
            for block_type in self.BLOCK_TYPES
        }

    def append_to_block(self, block_type: str, content: str) -> dict:
        """追加内容到记忆块"""
        current = self.get_block(block_type)
        existing = current.get("value", "")
        new_value = f"{existing}\n{content}" if existing else content
        return self.save_block(block_type, new_value)
