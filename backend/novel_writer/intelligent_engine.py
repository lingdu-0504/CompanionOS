"""
智能创作引擎 - 支持多章节连续生成和智能规划
"""
import asyncio
import logging
import random
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path

from .project import NovelProject, Chapter
from .engine import GlobalMemoryEngine, WordCountEngine, NarrativeStructureEngine
from .style_manager import StyleManager, StyleProfile
from .parallel import ParallelTaskManager, TaskType, TaskStatus


logger = logging.getLogger(__name__)


class CreationPhase(Enum):
    """创作阶段"""
    PLANNING = "planning"  # 规划阶段
    DRAFTING = "drafting"  # 草稿阶段
    REVIEWING = "reviewing"  # 审核阶段
    PUBLISHING = "publishing"  # 发布阶段


@dataclass
class GenerationPlan:
    """创作计划"""
    project_id: str
    start_chapter: int
    end_chapter: int
    target_word_count: int = 3000
    auto_publish: bool = False
    publish_interval: int = 86400  # 秒，默认1天
    style_profile: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    current_chapter: int = 0
    status: str = "pending"  # pending, running, completed, failed
    tasks: List[Dict] = field(default_factory=list)


@dataclass
class ChapterOutline:
    """章节大纲"""
    chapter_number: int
    title: str
    key_events: List[str] = field(default_factory=list)
    character_arcs: Dict[str, str] = field(default_factory=dict)
    cliffhanger: Optional[str] = None
    target_word_count: int = 3000
    plot_beat: str = ""  # 情节节点


class IntelligentCreationEngine:
    """
    智能创作引擎
    支持多章节连续生成、智能规划、自动发布
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 核心引擎
        self.memory_engine = GlobalMemoryEngine()
        self.word_engine = WordCountEngine()
        self.structure_engine = NarrativeStructureEngine()
        self.style_manager = StyleManager(data_dir / "styles")
        self.task_manager = ParallelTaskManager()
        
        # 运行中的计划
        self.active_plans: Dict[str, GenerationPlan] = {}
        self.creation_tasks: Dict[str, asyncio.Task] = {}
        
        # 回调
        self.on_chapter_generated: Optional[Callable] = None
        self.on_publish: Optional[Callable] = None
    
    async def create_generation_plan(
        self,
        project_id: str,
        start_chapter: int,
        end_chapter: int,
        auto_publish: bool = False,
        publish_interval: int = 86400,
        style_profile: Optional[str] = None,
    ) -> GenerationPlan:
        """创建创作计划"""
        plan = GenerationPlan(
            project_id=project_id,
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            auto_publish=auto_publish,
            publish_interval=publish_interval,
            style_profile=style_profile,
        )
        
        self.active_plans[project_id] = plan
        
        logger.info(f"Created generation plan for project {project_id}: chapters {start_chapter}-{end_chapter}")
        return plan
    
    async def execute_plan(
        self,
        project_id: str,
        novel_core,  # 核心引擎实例
    ) -> Dict[str, Any]:
        """执行创作计划"""
        plan = self.active_plans.get(project_id)
        if not plan:
            return {'success': False, 'error': 'No active plan found'}
        
        if plan.status == "running":
            return {'success': False, 'error': 'Plan already running'}
        
        plan.status = "running"
        logger.info(f"Starting execution of generation plan for project {project_id}")
        
        # 开始执行任务
        task = asyncio.create_task(
            self._run_plan(plan, novel_core)
        )
        self.creation_tasks[project_id] = task
        
        return {'success': True, 'plan_id': project_id}
    
    async def _run_plan(self, plan: GenerationPlan, novel_core):
        """运行创作计划"""
        try:
            project = novel_core.get_project(plan.project_id)
            if not project:
                raise ValueError(f"Project {plan.project_id} not found")
            
            # 获取风格提示词
            style_prompt = ""
            if plan.style_profile:
                style_prompt = self.style_manager.generate_style_prompt(plan.style_profile) or ""
            
            for chapter_num in range(plan.start_chapter, plan.end_chapter + 1):
                plan.current_chapter = chapter_num
                
                logger.info(f"Generating chapter {chapter_num} for project {plan.project_id}")
                
                try:
                    # 生成章节标题
                    chapter_title = f"第{chapter_num}章"
                    
                    # 生成章节
                    result = await novel_core.generate_chapter(
                        project_id=plan.project_id,
                        chapter_title=chapter_title,
                        chapter_number=chapter_num,
                        target_words=plan.target_word_count,
                    )
                    
                    if result.get('success'):
                        chapter = project.get_chapter(chapter_num)
                        if chapter:
                            # 检查风格一致性
                            if plan.style_profile:
                                style_check = self.style_manager.analyze_style_consistency(
                                    plan.style_profile, chapter.content
                                )
                                logger.info(f"Style check result: {style_check}")
                            
                            # 回调
                            if self.on_chapter_generated:
                                await self.on_chapter_generated(plan.project_id, {
                                    'number': chapter_num,
                                    'title': chapter.title
                                })
                            
                            # 自动发布
                            if plan.auto_publish:
                                await asyncio.sleep(2)  # 短暂延迟
                                await self._publish_chapter(project, chapter_num, novel_core)
                            
                            plan.tasks.append({
                                'chapter': chapter_num,
                                'success': True,
                                'timestamp': datetime.now().isoformat(),
                            })
                    
                    # 章节之间的延迟（模拟人类创作）
                    if chapter_num < plan.end_chapter:
                        delay = random.randint(300, 1800)  # 5-30分钟
                        logger.info(f"Waiting {delay}s before next chapter...")
                        await asyncio.sleep(delay)
                
                except Exception as e:
                    logger.error(f"Error generating chapter {chapter_num}: {e}")
                    plan.tasks.append({
                        'chapter': chapter_num,
                        'success': False,
                        'error': str(e),
                        'timestamp': datetime.now().isoformat(),
                    })
            
            # 计划完成
            plan.status = "completed"
            logger.info(f"Generation plan completed for project {plan.project_id}")
            
        except Exception as e:
            logger.error(f"Plan execution failed: {e}")
            plan.status = "failed"
            plan.error = str(e)
    
    async def _publish_chapter(self, project, chapter_num: int, novel_core):
        """发布章节"""
        try:
            result = await novel_core.auto_publish(
                project_id=project.id,
                platform_config={
                    'platform': 'qidian',
                    'chapter_number': chapter_num,
                },
            )
            
            if result.get('success'):
                logger.info(f"Published chapter {chapter_num}")
                if self.on_publish:
                    await self.on_publish(plan.project_id, {
                        'chapter': chapter_num,
                        'success': True
                    })
            else:
                logger.warning(f"Failed to publish chapter {chapter_num}: {result}")
        
        except Exception as e:
            logger.error(f"Error publishing chapter {chapter_num}: {e}")
    
    async def stop_plan(self, project_id: str) -> bool:
        """停止创作计划"""
        if project_id not in self.creation_tasks:
            return False
        
        task = self.creation_tasks[project_id]
        if not task.done():
            task.cancel()
        
        if project_id in self.active_plans:
            self.active_plans[project_id].status = "stopped"
        
        del self.creation_tasks[project_id]
        logger.info(f"Stopped generation plan for project {project_id}")
        return True
    
    def get_plan_status(self, project_id: str) -> Optional[Dict]:
        """获取计划状态"""
        plan = self.active_plans.get(project_id)
        if not plan:
            return None
        
        return {
            'start_chapter': plan.start_chapter,
            'end_chapter': plan.end_chapter,
            'current_chapter': plan.current_chapter,
            'status': plan.status,
            'tasks_completed': len([t for t in plan.tasks if t.get('success')]),
            'total_tasks': len(plan.tasks),
            'progress': (plan.current_chapter - plan.start_chapter + 1) / (plan.end_chapter - plan.start_chapter + 1),
        }
    
    def generate_chapter_outline(
        self,
        project: NovelProject,
        chapter_num: int,
    ) -> ChapterOutline:
        """生成章节大纲"""
        # 获取叙事结构建议
        structure = self.structure_engine.get_structure_for_chapter(
            project.genre, chapter_num, 100
        )
        
        outline = ChapterOutline(
            chapter_number=chapter_num,
            title=f"第{chapter_num}章",
            target_word_count=project.config.get('chapter_word_count', 3000),
            plot_beat=structure.get('stage_name', ''),
        )
        
        # 根据章节位置决定内容
        progress = chapter_num / 100
        
        if progress < 0.1:
            outline.key_events = [
                "场景介绍，人物出场",
                "世界观铺垫",
                "核心冲突初现",
            ]
        elif progress < 0.5:
            outline.key_events = [
                "情节发展",
                "矛盾升级",
                "人物关系变化",
            ]
        elif progress < 0.8:
            outline.key_events = [
                "关键转折",
                "真相揭示",
                "大战/高潮前准备",
            ]
        else:
            outline.key_events = [
                "高潮爆发",
                "问题解决",
                "结局/伏笔",
            ]
        
        # 建议在章节结尾设置悬念
        if chapter_num % 5 == 0 or progress > 0.7:
            outline.cliffhanger = "在高潮处戛然而止，留下悬念"
        
        return outline
    
    def get_generation_suggestions(
        self,
        project: NovelProject,
        current_chapter: Optional[Chapter] = None,
    ) -> List[Dict[str, Any]]:
        """获取创作建议"""
        suggestions = []
        
        # 检查记忆一致性
        if current_chapter:
            consistency = self.memory_engine.validate_content(current_chapter.content)
            if not consistency.get('is_consistent'):
                suggestions.append({
                    'type': 'consistency',
                    'priority': 'high',
                    'message': '发现潜在的一致性问题，建议检查事实',
                    'details': consistency.get('conflicts', []),
                })
        
        # 检查字数
        if current_chapter and len(current_chapter.content) < 2000:
            suggestions.append({
                'type': 'length',
                'priority': 'medium',
                'message': '章节字数偏少，建议补充细节',
                'current': len(current_chapter.content),
                'target': 3000,
            })
        
        # 情节发展建议
        chapter_count = len(project.chapters)
        if chapter_count % 10 == 0 and chapter_count > 0:
            suggestions.append({
                'type': 'plot',
                'priority': 'medium',
                'message': '建议在本章安排小高潮或重要转折',
            })
        
        # 建议埋设伏笔
        if chapter_count == 15:
            suggestions.append({
                'type': 'foreshadow',
                'priority': 'low',
                'message': '可以开始为中期主线埋设伏笔',
            })
        
        return suggestions
    
    def create_quick_start_presets(self) -> Dict[str, Dict]:
        """创建快速启动预设"""
        presets = {
            '玄幻爽文': {
                'genre': 'xuanhuan',
                'style_profile': '玄幻爽文',
                'chapter_word_count': 3000,
                'auto_publish': True,
                'publish_interval': 86400,
                'suggested_plots': [
                    '觉醒金手指',
                    '打脸第一章',
                    '获得宝物',
                    '秘境修炼',
                    '宗门大比',
                ],
            },
            '都市系统': {
                'genre': 'modern',
                'style_profile': '轻松搞笑',
                'chapter_word_count': 2500,
                'auto_publish': True,
                'publish_interval': 43200,  # 12小时
                'suggested_plots': [
                    '系统觉醒',
                    '新手任务',
                    '打脸富二代',
                    '神豪生活',
                ],
            },
            '古典仙侠': {
                'genre': 'xianxia',
                'style_profile': '古典仙侠',
                'chapter_word_count': 3500,
                'auto_publish': False,
                'suggested_plots': [
                    '拜师入门',
                    '炼气筑基',
                    '下山历练',
                    '宗门大比',
                ],
            },
        }
        
        return presets
    
    async def analyze_creation_quality(
        self,
        project: NovelProject,
    ) -> Dict[str, Any]:
        """分析创作质量"""
        analysis = {
            'project_name': project.name,
            'chapter_count': len(project.chapters),
            'total_words': project.get_total_word_count(),
            'avg_words_per_chapter': 0,
            'consistency_score': 0.9,
            'pacing_score': 0.8,
            'style_consistency': 0.85,
            'suggestions': [],
        }
        
        # 计算平均字数
        if project.chapters:
            analysis['avg_words_per_chapter'] = int(
                project.get_total_word_count() / len(project.chapters)
            )
        
        # 字数一致性检查
        word_counts = [len(c.content) for c in project.chapters if c.content]
        if word_counts:
            avg = sum(word_counts) / len(word_counts)
            variance = sum((w - avg) ** 2 for w in word_counts) / len(word_counts)
            if variance > 500000:  # 字数波动较大
                analysis['suggestions'].append({
                    'type': 'word_count',
                    'message': '章节字数波动较大，建议保持相对稳定',
                })
        
        # 创作节奏检查
        if len(project.chapters) >= 10:
            analysis['suggestions'].append({
                'type': 'pacing',
                'message': '建议在每5-10章设置一个小高潮',
            })
        
        # 风格分析
        if project.chapters:
            # 这里可以加入更详细的风格分析
            analysis['suggestions'].append({
                'type': 'style',
                'message': '建议使用风格学习功能，帮助AI保持一致风格',
            })
        
        return analysis
