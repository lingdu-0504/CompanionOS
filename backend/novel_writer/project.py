"""
小说项目管理系统 - Novel Project Management
管理小说项目的创建、配置、保存和加载
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field, asdict


@dataclass
class Chapter:
    """章节数据结构"""
    id: str
    number: int
    title: str
    content: str = ""
    word_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "draft"  # draft, reviewing, published
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NovelProject:
    """
    小说项目数据结构
    包含所有小说相关的配置、章节和元数据
    """
    id: str
    name: str
    description: str
    genre: str
    target_word_count: int
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    config: Dict[str, Any] = field(default_factory=dict)
    chapters: List[Chapter] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        name: str,
        description: str = "",
        genre: str = "fantasy",
        target_word_count: int = 100000,
        **kwargs,
    ):
        self.id = kwargs.get("id", str(uuid.uuid4()))
        self.name = name
        self.description = description
        self.genre = genre
        self.target_word_count = target_word_count
        self.created_at = kwargs.get("created_at", datetime.now().isoformat())
        self.updated_at = kwargs.get("updated_at", datetime.now().isoformat())
        self.config = kwargs.get("config", {})
        self.chapters = kwargs.get("chapters", [])
        self.metadata = kwargs.get("metadata", {})

        # 设置默认配置
        self._set_default_config()

    def _set_default_config(self):
        """设置默认配置"""
        defaults = {
            "chapter_word_count": 3000,
            "language": "zh-CN",
            "tone": "formal",
            "world_setting": "",
            "character_setting": "",
            "plot_outline": "",
            "themes": [],
            "keywords": [],
            "platforms": [],
            "auto_publish": False,
            "publish_schedule": None,
        }
        for key, value in defaults.items():
            if key not in self.config:
                self.config[key] = value

    def save(self, base_dir: Path):
        """保存项目到文件"""
        project_dir = base_dir / self.id
        project_dir.mkdir(parents=True, exist_ok=True)

        # 保存配置
        config_file = project_dir / "config.json"
        config_data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "genre": self.genre,
            "target_word_count": self.target_word_count,
            "created_at": self.created_at,
            "updated_at": datetime.now().isoformat(),
            "config": self.config,
            "metadata": self.metadata,
        }
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        # 保存章节
        chapters_dir = project_dir / "chapters"
        chapters_dir.mkdir(exist_ok=True)
        for chapter in self.chapters:
            chapter_file = chapters_dir / f"chapter_{chapter.number:04d}.json"
            with open(chapter_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "id": chapter.id,
                        "number": chapter.number,
                        "title": chapter.title,
                        "content": chapter.content,
                        "word_count": chapter.word_count,
                        "created_at": chapter.created_at,
                        "updated_at": chapter.updated_at,
                        "status": chapter.status,
                        "metadata": chapter.metadata,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

        self.updated_at = datetime.now().isoformat()

    @classmethod
    def load(cls, project_dir: Path) -> "NovelProject":
        """从文件加载项目"""
        config_file = project_dir / "config.json"
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        with open(config_file, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        # 加载章节
        chapters = []
        chapters_dir = project_dir / "chapters"
        if chapters_dir.exists():
            for chapter_file in sorted(chapters_dir.glob("chapter_*.json")):
                with open(chapter_file, "r", encoding="utf-8") as f:
                    chapter_data = json.load(f)
                    chapter = Chapter(
                        id=chapter_data["id"],
                        number=chapter_data["number"],
                        title=chapter_data["title"],
                        content=chapter_data.get("content", ""),
                        word_count=chapter_data.get("word_count", 0),
                        created_at=chapter_data.get(
                            "created_at", datetime.now().isoformat()
                        ),
                        updated_at=chapter_data.get(
                            "updated_at", datetime.now().isoformat()
                        ),
                        status=chapter_data.get("status", "draft"),
                        metadata=chapter_data.get("metadata", {}),
                    )
                    chapters.append(chapter)

        return cls(
            id=config_data["id"],
            name=config_data["name"],
            description=config_data.get("description", ""),
            genre=config_data.get("genre", "fantasy"),
            target_word_count=config_data.get("target_word_count", 100000),
            created_at=config_data.get("created_at", datetime.now().isoformat()),
            updated_at=config_data.get("updated_at", datetime.now().isoformat()),
            config=config_data.get("config", {}),
            chapters=chapters,
            metadata=config_data.get("metadata", {}),
        )

    def add_chapter(
        self,
        title: str,
        number: int,
        content: str = "",
        word_count: int = 0,
    ) -> Chapter:
        """添加新章节"""
        # 检查章节号是否已存在
        existing = next((c for c in self.chapters if c.number == number), None)
        if existing:
            # 更新现有章节
            existing.title = title
            existing.content = content
            existing.word_count = word_count or len(content)
            existing.updated_at = datetime.now().isoformat()
            return existing

        chapter = Chapter(
            id=str(uuid.uuid4()),
            number=number,
            title=title,
            content=content,
            word_count=word_count or len(content),
        )
        self.chapters.append(chapter)
        self.chapters.sort(key=lambda c: c.number)
        return chapter

    def get_chapter(self, number: int) -> Optional[Chapter]:
        """获取指定章节"""
        return next((c for c in self.chapters if c.number == number), None)

    def get_chapter_by_id(self, chapter_id: str) -> Optional[Chapter]:
        """通过ID获取章节"""
        return next((c for c in self.chapters if c.id == chapter_id), None)

    def delete_chapter(self, number: int) -> bool:
        """删除章节"""
        initial_count = len(self.chapters)
        self.chapters = [c for c in self.chapters if c.number != number]
        return len(self.chapters) < initial_count

    def get_total_word_count(self) -> int:
        """获取总字数"""
        return sum(c.word_count for c in self.chapters)

    def get_progress(self) -> float:
        """获取创作进度（百分比）"""
        if self.target_word_count <= 0:
            return 0.0
        return min(100.0, (self.get_total_word_count() / self.target_word_count) * 100)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "genre": self.genre,
            "target_word_count": self.target_word_count,
            "current_word_count": self.get_total_word_count(),
            "progress": self.get_progress(),
            "chapter_count": len(self.chapters),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "config": self.config,
            "metadata": self.metadata,
        }
