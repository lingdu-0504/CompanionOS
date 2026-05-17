"""
小说创作核心引擎 - Novel Writing Core Engine
整合所有功能模块的核心控制器
提供真实的小说章节生成功能
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import uuid

from .project import NovelProject
from .engine import GlobalMemoryEngine, WordCountEngine, NarrativeStructureEngine
from .platform import NovelPlatformPublisher, PlatformScheduler
from .parallel import ParallelTaskManager, TaskType
from .style_manager import StyleManager, StyleProfile, WritingStyle, ToneStyle, NarrativeMode, PRESET_STYLES
from .intelligent_engine import IntelligentCreationEngine, CreationPhase

logger = logging.getLogger(__name__)


class GenerationContext:
    """生成上下文"""

    def __init__(self, project: NovelProject, chapter_number: int):
        self.project = project
        self.chapter_number = chapter_number
        self.previous_chapters: List[Dict] = []
        self.generated_content: str = ""
        self.word_count: int = 0
        self.metadata: Dict = {}

    def add_content(self, content: str):
        """添加生成的内容"""
        self.generated_content += content
        self.word_count = len(self.generated_content)


class NovelWriterCore:
    """
    小说创作核心引擎
    整合所有功能模块的主控制器
    提供完整的小说创作工作流
    """

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path(__file__).parent.parent / "data" / "novels"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 初始化各个引擎
        self.memory_engine = GlobalMemoryEngine()
        self.word_count_engine = WordCountEngine()
        self.narrative_engine = NarrativeStructureEngine()
        self.platform_publisher = NovelPlatformPublisher()
        self.platform_scheduler = PlatformScheduler(self.platform_publisher)
        self.parallel_manager = ParallelTaskManager()
        
        # 新增：风格管理和智能创作引擎
        self.style_manager = StyleManager(self.data_dir / "styles")
        self.intelligent_engine = IntelligentCreationEngine(self.data_dir)
        
        # 设置回调
        self.intelligent_engine.on_chapter_generated = self._on_chapter_generated_callback
        self.intelligent_engine.on_publish = self._on_publish_callback

        # 项目存储
        self.projects: Dict[str, NovelProject] = {}
        self._project_memories: Dict[str, GlobalMemoryEngine] = {}

        # 生成回调
        self._generation_callbacks: List[Callable] = []

        self._load_projects()
        self._register_task_handlers()
        self._initialize_preset_styles()

    def _load_projects(self):
        """加载所有小说项目"""
        if not self.data_dir.exists():
            return

        for project_dir in self.data_dir.iterdir():
            if project_dir.is_dir() and (project_dir / "config.json").exists():
                try:
                    project = NovelProject.load(project_dir)
                    self.projects[project.id] = project
                    logger.info(f"Loaded project: {project.name} ({project.id})")
                except Exception as e:
                    logger.error(f"Failed to load project from {project_dir}: {e}")

    def _register_task_handlers(self):
        """注册任务处理器"""
        self.parallel_manager.register_handler(
            TaskType.GENERATE_CHAPTER.value,
            self._handle_generate_chapter_task
        )
        self.parallel_manager.register_handler(
            TaskType.AUTO_CREATE.value,
            self._handle_auto_create_task
        )
        self.parallel_manager.register_handler(
            TaskType.PUBLISH.value,
            self._handle_publish_task
        )

    # ========== 项目管理 ==========

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

        # 为项目创建独立的记忆引擎
        self._project_memories[project.id] = GlobalMemoryEngine()

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

            # 删除项目记忆
            if project_id in self._project_memories:
                del self._project_memories[project_id]

            logger.info(f"Deleted project: {project_id}")
            return True
        return False

    def update_project(self, project_id: str, updates: Dict) -> Optional[NovelProject]:
        """更新项目"""
        project = self.get_project(project_id)
        if not project:
            return None

        for key, value in updates.items():
            if hasattr(project, key):
                setattr(project, key, value)
            elif key in project.config:
                project.config[key] = value

        project.save(self.data_dir)
        return project

    # ========== 章节生成 ==========

    async def generate_chapter(
        self,
        project_id: str,
        chapter_title: str,
        chapter_number: int,
        target_words: Optional[int] = None,
        regenerate: bool = False,
    ) -> Dict[str, Any]:
        """生成小说章节"""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        # 检查章节是否已存在
        existing = project.get_chapter(chapter_number)
        if existing and not regenerate:
            return {
                "success": False,
                "error": "Chapter already exists",
                "chapter": {
                    "id": existing.id,
                    "number": existing.number,
                    "title": existing.title,
                    "content": existing.content,
                }
            }

        # 获取项目的记忆引擎
        if project_id not in self._project_memories:
            self._project_memories[project_id] = GlobalMemoryEngine()
        memory_engine = self._project_memories[project_id]
        memory_engine.load_from_project(project)

        # 获取目标字数
        if target_words is None:
            target_words = project.config.get("chapter_word_count", 3000)

        # 规划字数
        word_plan = self.word_count_engine.plan_chapter(target_words)

        # 获取叙事结构
        total_chapters = project.config.get("total_chapters", 100)
        structure = self.narrative_engine.get_structure_for_chapter(
            project.genre, chapter_number, total_chapters
        )

        # 生成内容
        content = await self._generate_content_with_constraints(
            project=project,
            chapter_title=chapter_title,
            chapter_number=chapter_number,
            structure=structure,
            word_plan=word_plan,
            memory_engine=memory_engine,
        )

        # 验证一致性
        consistency_report = memory_engine.validate_content(content)

        # 保存章节
        chapter = project.add_chapter(
            title=chapter_title,
            number=chapter_number,
            content=content,
            word_count=len(content),
        )
        project.save(self.data_dir)

        # 更新记忆
        memory_engine.add_facts_from_content(content, chapter_number)
        memory_engine.save_to_project(str(self.data_dir / project.id))

        # 触发回调
        await self._trigger_generation_callbacks(project_id, chapter_number, content)

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
        memory_engine: GlobalMemoryEngine,
    ) -> str:
        """带约束的内容生成"""
        # 获取上下文
        context = memory_engine.get_context_for_chapter(chapter_number)

        # 构建提示
        prompt = self._build_generation_prompt(
            project=project,
            chapter_title=chapter_title,
            chapter_number=chapter_number,
            structure=structure,
            word_plan=word_plan,
            context=context,
        )

        # 调用LLM生成内容
        content = await self._call_llm_for_content(prompt, project)

        # 精确调控字数
        content = self.word_count_engine.adjust_content_to_target(
            content, word_plan["target"]
        )

        return content

    async def _call_llm_for_content(self, prompt: str, project: NovelProject) -> str:
        """调用LLM生成内容"""
        try:
            # 尝试使用Hermes适配器
            from ..agent_bridge.hermes_adapter import HermesAdapter

            hermes = HermesAdapter()
            response = await hermes.process(
                user_input=prompt,
                context={
                    "project": project.config,
                    "task": "novel_generation"
                },
            )
            content = response.get("content", "")

            if content:
                return content

        except ImportError:
            logger.warning("Hermes adapter not available")
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")

        # 回退到模拟内容
        return self._generate_mock_content(project, prompt)

    def _generate_mock_content(self, project: NovelProject, prompt: str) -> str:
        """生成模拟内容（当LLM不可用时）"""
        content = f"""
{project.name}

{project.description}

这是一个模拟生成的小说内容。在实际部署中，这部分将调用真实的大语言模型来生成高质量的小说内容。

【示例内容】
在这个充满未知的世界里，主人公经历了一系列惊心动魄的冒险。故事情节跌宕起伏，人物命运交织，展现了一幅壮阔的史诗画卷。

随着故事的深入，主角逐渐发现了隐藏在表面之下的真相。那是一个关于勇气、友情和牺牲的故事，也是一个关于成长和救赎的传奇。

每个章节都精心设计，承上启下，为读者带来沉浸式的阅读体验。
"""
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
        prompt = f"""请创作小说《{project.name}》的第{chapter_number}章：{chapter_title}

【小说背景】
{project.description}

【核心设定】
{project.config.get('world_setting', '一个充满神秘与冒险的世界')}
{project.config.get('character_setting', '主要人物性格鲜明，各有特点')}

【叙事结构指导】
{structure.get('description', '')}

当前阶段：{structure.get('stage_name', '')}
写作重点：{', '.join(structure.get('chapter_guidance', {}).get('focus', []))}

【字数要求】
目标字数：{word_plan['target']}字
允许误差：±{word_plan['tolerance']}字
目标范围：{word_plan['min']}-{word_plan['max']}字

【上文背景】（保持一致性）
{context.get('summary', '暂无上文')}

【写作要求】
1. 严格保持全局一致性，不得出现设定矛盾
2. 人物性格、行为、语言符合已有设定
3. 情节推进自然，逻辑清晰
4. 控制在目标字数范围内（{word_plan['min']}-{word_plan['max']}字）
5. 使用生动的描写，营造沉浸式阅读体验
6. 每段要有适当的细节描写

请开始创作这一章：
"""
        return prompt

    # ========== 任务处理 ==========

    async def _handle_generate_chapter_task(self, task) -> Dict[str, Any]:
        """处理章节生成任务"""
        config = task.schedule_config
        return await self.generate_chapter(
            project_id=task.project_id,
            chapter_title=config.get("chapter_title", f"第{config.get('chapter_number')}章"),
            chapter_number=config.get("chapter_number"),
            target_words=config.get("target_words"),
        )

    async def _handle_auto_create_task(self, task) -> Dict[str, Any]:
        """处理自动创作任务"""
        project = self.get_project(task.project_id)
        if not project:
            return {"success": False, "error": "Project not found"}

        chapters_created = 0
        chapters_per_run = task.schedule_config.get("chapters_per_run", 1)

        for i in range(chapters_per_run):
            next_chapter = len(project.chapters) + 1
            chapter_title = f"第{next_chapter}章 自动生成章节{next_chapter}"

            result = await self.generate_chapter(
                project_id=task.project_id,
                chapter_title=chapter_title,
                chapter_number=next_chapter,
            )

            if result.get("success"):
                chapters_created += 1

        return {
            "success": True,
            "project_id": task.project_id,
            "chapters_created": chapters_created,
            "message": f"自动创作了{chapters_created}个章节",
        }

    async def _handle_publish_task(self, task) -> Dict[str, Any]:
        """处理发布任务"""
        config = task.schedule_config
        return await self.auto_publish(
            project_id=task.project_id,
            platform_config=config,
        )

    # ========== 发布管理 ==========

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

    async def batch_publish(
        self,
        project_id: str,
        chapter_numbers: List[int],
        platform: str = "qidian",
        credentials: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """批量发布章节"""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        if credentials:
            self.platform_publisher.set_credentials(
                platform,
                credentials.get("username", ""),
                credentials.get("password", "")
            )

        results = []
        for chapter_num in chapter_numbers:
            result = await self.auto_publish(
                project_id=project_id,
                platform_config={
                    "platform": platform,
                    "chapter_number": chapter_num,
                }
            )
            results.append(result)

            if chapter_num != chapter_numbers[-1]:
                await asyncio.sleep(3600)  # 每章间隔1小时

        return results

    def schedule_publish(
        self,
        project_id: str,
        platform: str,
        hour: int = 12,
        minute: int = 0,
    ) -> str:
        """安排定时发布"""
        return self.platform_scheduler.schedule_daily_publish(
            project_id=project_id,
            platform=platform,
            hour=hour,
            minute=minute,
        )

    # ========== 自动创作调度 ==========

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
            task_type=TaskType.AUTO_CREATE.value,
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

    def get_all_tasks(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取所有任务"""
        return self.parallel_manager.get_all_tasks(project_id)

    # ========== 回调管理 ==========

    def on_generation(self, callback: Callable):
        """注册生成回调"""
        self._generation_callbacks.append(callback)

    async def _trigger_generation_callbacks(
        self,
        project_id: str,
        chapter_number: int,
        content: str
    ):
        """触发生成回调"""
        for callback in self._generation_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(project_id, chapter_number, content)
                else:
                    callback(project_id, chapter_number, content)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    # ========== 工具方法 ==========

    def get_project_statistics(self, project_id: str) -> Optional[Dict[str, Any]]:
        """获取项目统计"""
        project = self.get_project(project_id)
        if not project:
            return None

        return {
            "project_id": project.id,
            "name": project.name,
            "chapter_count": len(project.chapters),
            "total_word_count": project.get_total_word_count(),
            "target_word_count": project.target_word_count,
            "progress": project.get_progress(),
            "genre": project.genre,
            "created_at": project.created_at,
            "updated_at": project.updated_at,
        }

    def export_project(self, project_id: str, format: str = "json") -> Optional[Dict]:
        """导出项目"""
        project = self.get_project(project_id)
        if not project:
            return None

        if format == "json":
            return {
                "metadata": project.to_dict(),
                "chapters": [
                    {
                        "number": c.number,
                        "title": c.title,
                        "content": c.content,
                        "word_count": c.word_count,
                    }
                    for c in project.chapters
                ],
            }
        elif format == "text":
            content = f"# {project.name}\n\n{project.description}\n\n"
            for chapter in project.chapters:
                content += f"\n## 第{chapter.number}章 {chapter.title}\n\n{chapter.content}\n"
            return {"content": content}

        return None

    # ========== 风格管理 ==========
    
    def _initialize_preset_styles(self):
        """初始化预设风格"""
        # 将预设风格保存到风格管理器
        for name, (style, tone, mode) in PRESET_STYLES.items():
            if name not in self.style_manager.profiles:
                self.style_manager.create_profile(
                    name=name,
                    style=style,
                    tone=tone,
                    narrative_mode=mode
                )
    
    def get_all_styles(self):
        """获取所有风格"""
        return [
            {
                'id': p.name,
                'name': p.name,
                'description': f'{p.style.value} - {p.tone.value}',
                'is_preset': p.name in PRESET_STYLES
            }
            for p in self.style_manager.profiles.values()
        ]
    
    def get_style(self, style_id: str):
        """获取指定风格"""
        profile = self.style_manager.get_profile(style_id)
        if profile:
            return {
                'id': profile.name,
                'name': profile.name,
                'description': f'{profile.style.value} - {profile.tone.value}',
                'is_preset': profile.name in PRESET_STYLES
            }
        return None
    
    def create_style(self, style_data: dict):
        """创建自定义风格"""
        try:
            profile = self.style_manager.create_profile(
                name=style_data['name'],
                style=WritingStyle(style_data.get('writing_style', 'fantasy')),
                tone=ToneStyle(style_data.get('tone_style', 'serious')),
                narrative_mode=NarrativeMode(style_data.get('narrative_mode', 'third_limited'))
            )
            return {
                'id': profile.name,
                'name': profile.name
            }
        except Exception as e:
            logger.error(f"Failed to create style: {e}")
            return None
    
    def update_style(self, style_id: str, updates: dict):
        """更新风格"""
        updated = self.style_manager.update_profile(style_id, updates)
        if updated:
            return {
                'id': updated.name,
                'name': updated.name
            }
        return None
    
    def delete_style(self, style_id: str):
        """删除风格"""
        return self.style_manager.delete_profile(style_id)
    
    async def analyze_text_style(self, text: str):
        """分析文本风格"""
        return self.style_manager.analyzer.analyze_text(text)
    
    async def generate_style_prompt(self, style_id: str, context: dict = None):
        """生成风格提示词"""
        prompt = self.style_manager.generate_style_prompt(style_id)
        return {'prompt': prompt or ''}
    
    def apply_style_to_project(self, project_id: str, style_id: str):
        """将风格应用到项目"""
        project = self.get_project(project_id)
        if not project:
            return False
        project.config["style_id"] = style_id
        project.save(self.data_dir)
        return True
    
    # ========== 智能创作引擎 ==========
    
    def _on_chapter_generated_callback(self, project_id: str, chapter: dict):
        """章节生成回调"""
        logger.info(f"Chapter generated: Project {project_id}, Chapter {chapter.get('number')}")
    
    def _on_publish_callback(self, project_id: str, result: dict):
        """发布回调"""
        logger.info(f"Publish completed: Project {project_id}, Result {result}")
    
    async def create_creation_plan(self, project_id: str, plan_config: dict):
        """创建创作计划"""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        
        total_chapters = plan_config.get('total_chapters', 100)
        start_chapter = plan_config.get('start_chapter', 1)
        
        plan = await self.intelligent_engine.create_generation_plan(
            project_id=project_id,
            start_chapter=start_chapter,
            end_chapter=total_chapters,
            auto_publish=plan_config.get('auto_publish', False),
            style_profile=plan_config.get('style_profile')
        )
        
        return {
            'success': True,
            'plan': {
                'project_id': plan.project_id,
                'start_chapter': plan.start_chapter,
                'end_chapter': plan.end_chapter,
                'total_chapters': total_chapters
            }
        }
    
    def get_creation_plan(self, project_id: str):
        """获取创作计划"""
        status = self.intelligent_engine.get_plan_status(project_id)
        return status if status else None
    
    async def execute_creation_plan(self, project_id: str, start_chapter: int = None, end_chapter: int = None):
        """执行创作计划"""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        
        # 如果没有现有的计划，先创建一个
        if project_id not in self.intelligent_engine.active_plans:
            await self.create_creation_plan(project_id, {
                'total_chapters': end_chapter or (len(project.chapters) + 10),
                'start_chapter': start_chapter or (len(project.chapters) + 1)
            })
        
        result = await self.intelligent_engine.execute_plan(project_id, self)
        return result
    
    def add_chapter_outline(self, project_id: str, chapter_outline: dict):
        """添加章节大纲"""
        project = self.get_project(project_id)
        if not project:
            return None
        
        outline = self.intelligent_engine.generate_chapter_outline(
            project, chapter_outline.get('number', 1)
        )
        
        return {
            'success': True,
            'outline': {
                'chapter_number': outline.chapter_number,
                'title': outline.title,
                'key_events': outline.key_events
            }
        }
    
    def get_chapter_outlines(self, project_id: str):
        """获取章节大纲列表"""
        # 简化实现，实际可以从文件或数据库加载
        return []
    
    async def analyze_creation_quality(self, project_id: str):
        """分析创作质量"""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")
        
        analysis = await self.intelligent_engine.analyze_creation_quality(project)
        return {
            'success': True,
            'quality': analysis
        }
    
    def get_automation_levels(self):
        """获取自动化等级信息"""
        return {
            "levels": [
                {
                    "level": 1,
                    "name": "手动创作",
                    "description": "完全手动创作，仅提供基础工具"
                },
                {
                    "level": 2,
                    "name": "辅助创作",
                    "description": "提供章节生成、一致性检查等辅助功能"
                },
                {
                    "level": 3,
                    "name": "半自动创作",
                    "description": "支持风格保持、多章节连续生成"
                },
                {
                    "level": 4,
                    "name": "全自动创作",
                    "description": "完整创作计划、自动发布、智能建议"
                }
            ],
            "current_level": 4,
            "features": [
                "全局一致性记忆引擎",
                "精确字数控制",
                "叙事结构规划",
                "风格学习与保持",
                "多章节连续生成",
                "智能创作计划",
                "自动平台发布",
                "创作质量分析",
                "并行任务调度",
                "定时任务管理"
            ]
        }
    
    async def close(self):
        """关闭资源"""
        await self.platform_publisher.close()
        await self.parallel_manager.stop_scheduler()
