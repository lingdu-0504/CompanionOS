"""
小说创作核心引擎 - Novel Writing Core Engine
整合所有功能模块的核心控制器
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from .project import NovelProject
from .engine import GlobalMemoryEngine, WordCountEngine, NarrativeStructureEngine
from .platform import NovelPlatformPublisher
from .parallel import ParallelTaskManager

logger = logging.getLogger(__name__)


class NovelWriterCore:
    """
    小说创作核心引擎
    整合所有功能模块的主控制器
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path(__file__).parent.parent / "data" / "novels"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 初始化各个引擎
        self.memory_engine = GlobalMemoryEngine()
        self.word_count_engine = WordCountEngine()
        self.narrative_engine = NarrativeStructureEngine()
        self.platform_publisher = NovelPlatformPublisher()
        self.parallel_manager = ParallelTaskManager()

        # 项目存储
        self.projects: Dict[str, NovelProject] = {}
        self._load_projects()

    def _load_projects(self):
        """加载所有小说项目"""
        for project_dir in self.data_dir.iterdir():
            if project_dir.is_dir() and (project_dir / "config.json").exists():
                try:
                    project = NovelProject.load(project_dir)
                    self.projects[project.id] = project
                    logger.info(f"Loaded project: {project.name} ({project.id})")
                except Exception as e:
                    logger.error(f"Failed to load project from {project_dir}: {e}")

    def create_project(
        self,
        name: str,
        description: str = "",
        genre: str = "fantasy",
        target_word_count: int = 100000,
        **kwargs,
    ) -> NovelProject:
        """创建新的小说项目"""
        project = NovelProject(
            name=name,
            description=description,
            genre=genre,
            target_word_count=target_word_count,
            **kwargs,
        )
        project.save(self.data_dir)
        self.projects[project.id] = project
        logger.info(f"Created new project: {name} ({project.id})")
        return project

    def get_project(self, project_id: str) -> Optional[NovelProject]:
        """获取项目"""
        return self.projects.get(project_id)

    def list_projects(self) -> List[NovelProject]:
        """列出所有项目"""
        return list(self.projects.values())

    def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        if project_id in self.projects:
            project = self.projects[project_id]
            project_dir = self.data_dir / project.id
            if project_dir.exists():
                import shutil
                shutil.rmtree(project_dir)
            del self.projects[project_id]
            logger.info(f"Deleted project: {project_id}")
            return True
        return False

    async def generate_chapter(
        self,
        project_id: str,
        chapter_title: str,
        chapter_number: int,
        target_words: Optional[int] = None,
    ) -> Dict[str, Any]:
        """生成小说章节"""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        # 确保记忆引擎与项目关联
        self.memory_engine.load_from_project(project)

        # 获取目标字数
        if target_words is None:
            target_words = project.config.get("chapter_word_count", 3000)

        # 规划字数
        word_plan = self.word_count_engine.plan_chapter(target_words)

        # 获取叙事结构
        structure = self.narrative_engine.get_structure_for_chapter(
            project.genre, chapter_number
        )

        # 生成内容
        content = await self._generate_content_with_constraints(
            project=project,
            chapter_title=chapter_title,
            chapter_number=chapter_number,
            structure=structure,
            word_plan=word_plan,
        )

        # 验证一致性
        consistency_report = self.memory_engine.validate_content(content)

        # 保存章节
        project.add_chapter(
            title=chapter_title,
            number=chapter_number,
            content=content,
            word_count=len(content),
        )
        project.save(self.data_dir)

        return {
            "success": True,
            "project_id": project_id,
            "chapter_number": chapter_number,
            "title": chapter_title,
            "content": content,
            "word_count": len(content),
            "target_word_count": target_words,
            "consistency_report": consistency_report,
        }

    async def _generate_content_with_constraints(
        self,
        project: NovelProject,
        chapter_title: str,
        chapter_number: int,
        structure: Dict,
        word_plan: Dict,
    ) -> str:
        """
        带约束的内容生成
        结合记忆引擎、字数控制和叙事结构
        """
        # 获取上下文
        context = self.memory_engine.get_context_for_chapter(chapter_number)

        # 构建提示
        prompt = self._build_generation_prompt(
            project=project,
            chapter_title=chapter_title,
            chapter_number=chapter_number,
            structure=structure,
            word_plan=word_plan,
            context=context,
        )

        # 调用LLM生成内容（这里使用Hermes适配器）
        from ..agent_bridge.hermes_adapter import HermesAdapter

        hermes = HermesAdapter()
        response = await hermes.process(
            user_input=prompt,
            context={"project": project.config, "chapter": chapter_number},
        )

        content = response.get("content", "")

        # 精确调控字数
        content = self.word_count_engine.adjust_content_to_target(
            content, word_plan["target"]
        )

        # 更新记忆
        self.memory_engine.add_facts_from_content(content, chapter_number)

        return content

    def _build_generation_prompt(
        self,
        project: NovelProject,
        chapter_title: str,
        chapter_number: int,
        structure: Dict,
        word_plan: Dict,
        context: Dict,
    ) -> str:
        """构建生成提示"""
        prompt = f"""
请创作小说《{project.name}》的第{chapter_number}章：{chapter_title}

【小说背景】
{project.description}

【核心设定】
{project.config.get('world_setting', '')}
{project.config.get('character_setting', '')}

【叙事结构】
{structure.get('description', '')}

【字数要求】
目标字数：{word_plan['target']}字
允许误差：±{word_plan['tolerance']}字

【上下文记忆】
{context.get('summary', '')}

【重要要求】
1. 严格保持全局一致性，不得出现设定矛盾
2. 人物性格和行为符合设定
3. 情节推进自然
4. 控制在目标字数范围内

请开始创作：
"""
        return prompt

    async def auto_publish(
        self,
        project_id: str,
        platform_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """自动发布到小说平台"""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        return await self.platform_publisher.publish(
            project=project,
            platform_config=platform_config,
        )

    async def schedule_automatic_creation(
        self,
        project_id: str,
        schedule_config: Dict[str, Any],
    ) -> str:
        """安排自动创作任务"""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        task_id = await self.parallel_manager.schedule_task(
            task_type="auto_create",
            project_id=project_id,
            schedule_config=schedule_config,
        )
        return task_id

    async def run_parallel_tasks(self, task_ids: Optional[List[str]] = None):
        """运行并行任务"""
        await self.parallel_manager.run_tasks(task_ids)

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        return self.parallel_manager.get_task_status(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        return self.parallel_manager.cancel_task(task_id)
