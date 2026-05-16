"""
小说创作核心引擎 - Novel Writing Engines
包含全局一致性记忆引擎、精确字数控制引擎、叙事结构引擎
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Fact:
    """事实数据结构"""
    id: str
    content: str
    fact_type: str  # character, location, event, item
    confidence: float = 1.0
    source_chapter: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


class GlobalMemoryEngine:
    """
    全局一致性记忆引擎
    管理小说中的所有事实，检测和解决冲突
    """

    def __init__(self):
        self.facts: Dict[str, Fact] = {}
        self.relations: List[Dict] = []
        self.conflict_history: List[Dict] = []

    def load_from_project(self, project):
        """从项目加载记忆"""
        facts_dir = Path(project.id) / "facts"
        facts_file = facts_dir / "facts.json"
        if facts_file.exists():
            try:
                with open(facts_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for fact_data in data.get("facts", []):
                        fact = Fact(
                            id=fact_data["id"],
                            content=fact_data["content"],
                            fact_type=fact_data["fact_type"],
                            confidence=fact_data.get("confidence", 1.0),
                            source_chapter=fact_data.get("source_chapter", 0),
                            created_at=fact_data.get("created_at", datetime.now().isoformat()),
                            metadata=fact_data.get("metadata", {}),
                        )
                        self.facts[fact.id] = fact
            except Exception as e:
                logger.error(f"Failed to load facts: {e}")

    def add_fact(
        self,
        content: str,
        fact_type: str = "event",
        source_chapter: int = 0,
        confidence: float = 1.0,
    ) -> Fact:
        """添加新事实"""
        import uuid
        fact_id = str(uuid.uuid4())
        fact = Fact(
            id=fact_id,
            content=content,
            fact_type=fact_type,
            confidence=confidence,
            source_chapter=source_chapter,
        )
        self.facts[fact_id] = fact
        logger.info(f"Added fact: {fact_type} - {content[:50]}...")
        return fact

    def add_facts_from_content(self, content: str, chapter_number: int):
        """从内容中提取并添加事实"""
        # 简单的事实提取（实际应用中应使用更复杂的NLP）
        sentences = re.split(r'[。！？.!?]', content)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 10:
                # 识别人物提及
                if any(keyword in sentence for keyword in ['说', '道', '问', '答', '想', '心里']):
                    self.add_fact(sentence, "character", chapter_number, 0.8)
                # 识别地点提及
                elif any(keyword in sentence for keyword in ['在', '来到', '前往', '到达', '位于']):
                    self.add_fact(sentence, "location", chapter_number, 0.7)
                # 识别事件
                else:
                    self.add_fact(sentence, "event", chapter_number, 0.6)

    def validate_content(self, content: str) -> Dict[str, Any]:
        """验证内容是否与现有事实一致"""
        conflicts = []
        warnings = []

        # 简单的冲突检测（实际应用中应使用更复杂的NLP）
        for fact_id, fact in self.facts.items():
            # 检查是否有直接矛盾
            if self._check_conflict(content, fact.content):
                conflicts.append({
                    "fact_id": fact_id,
                    "fact_content": fact.content,
                    "fact_type": fact.fact_type,
                    "source_chapter": fact.source_chapter,
                    "confidence": fact.confidence,
                })

        return {
            "is_consistent": len(conflicts) == 0,
            "conflicts": conflicts,
            "warnings": warnings,
            "fact_count": len(self.facts),
        }

    def _check_conflict(self, content1: str, content2: str) -> bool:
        """检查两个内容是否冲突（简化实现）"""
        # 实际应用中应该使用更复杂的语义相似度和矛盾检测
        # 这里只是一个占位符
        return False

    def get_context_for_chapter(self, chapter_number: int, max_facts: int = 20) -> Dict:
        """获取章节的上下文记忆"""
        # 获取相关事实（最近章节的优先）
        relevant_facts = sorted(
            self.facts.values(),
            key=lambda f: (
                abs(f.source_chapter - chapter_number),
                -f.confidence,
            ),
        )[:max_facts]

        summary = "\n".join([
            f"- [{f.fact_type}] {f.content}"
            for f in relevant_facts
        ])

        return {
            "facts": [
                {
                    "id": f.id,
                    "content": f.content,
                    "type": f.fact_type,
                    "chapter": f.source_chapter,
                }
                for f in relevant_facts
            ],
            "summary": summary,
        }

    def resolve_conflict(self, fact_id: str, keep_fact: bool = True):
        """解决冲突"""
        if fact_id in self.facts:
            if not keep_fact:
                del self.facts[fact_id]
                logger.info(f"Removed conflicting fact: {fact_id}")
            self.conflict_history.append({
                "fact_id": fact_id,
                "resolution": "keep" if keep_fact else "remove",
                "timestamp": datetime.now().isoformat(),
            })


class WordCountEngine:
    """
    精确字数控制引擎
    规划和调控小说的字数
    """

    def __init__(self):
        self.tolerance = 0.003  # ±0.3% 误差

    def plan_chapter(self, target_words: int) -> Dict[str, Any]:
        """规划章节字数"""
        tolerance_words = int(target_words * self.tolerance)
        min_words = target_words - tolerance_words
        max_words = target_words + tolerance_words

        return {
            "target": target_words,
            "min": min_words,
            "max": max_words,
            "tolerance": tolerance_words,
            "tolerance_percent": self.tolerance * 100,
        }

    def plan_novel(
        self,
        total_words: int,
        chapter_count: int,
        structure_type: str = "three_act",
    ) -> Dict[str, Any]:
        """规划整部小说的字数分配"""
        chapter_plan = []

        if structure_type == "three_act":
            # 三幕式结构
            act1_chapters = max(1, chapter_count // 4)
            act2_chapters = chapter_count // 2
            act3_chapters = chapter_count - act1_chapters - act2_chapters

            act1_words = int(total_words * 0.25)
            act2_words = int(total_words * 0.5)
            act3_words = total_words - act1_words - act2_words

            # 分配到各章
            for i in range(act1_chapters):
                chapter_plan.append(self.plan_chapter(act1_words // act1_chapters))
            for i in range(act2_chapters):
                chapter_plan.append(self.plan_chapter(act2_words // act2_chapters))
            for i in range(act3_chapters):
                chapter_plan.append(self.plan_chapter(act3_words // act3_chapters))

        else:
            # 平均分配
            avg_words = total_words // chapter_count
            for i in range(chapter_count):
                chapter_plan.append(self.plan_chapter(avg_words))

        return {
            "total_words": total_words,
            "chapter_count": chapter_count,
            "chapters": chapter_plan,
            "structure_type": structure_type,
        }

    def adjust_content_to_target(self, content: str, target_words: int) -> str:
        """调整内容到目标字数"""
        current_words = len(content)
        tolerance = int(target_words * self.tolerance)

        if abs(current_words - target_words) <= tolerance:
            return content

        if current_words < target_words:
            # 需要扩展
            return self._expand_content(content, target_words)
        else:
            # 需要缩短
            return self._compress_content(content, target_words)

    def _expand_content(self, content: str, target_words: int) -> str:
        """扩展内容（简化实现）"""
        # 实际应用中应该使用更智能的扩展方法
        # 这里只是一个占位符
        return content

    def _compress_content(self, content: str, target_words: int) -> str:
        """压缩内容（简化实现）"""
        # 实际应用中应该使用更智能的压缩方法
        # 这里只是一个占位符
        return content[:target_words]


class NarrativeStructureEngine:
    """
    叙事结构引擎
    提供各种叙事结构模板和情节生成
    """

    def __init__(self):
        self.structures = self._load_structures()
        self.plot_templates = self._load_plot_templates()

    def _load_structures(self) -> Dict:
        """加载叙事结构模板"""
        return {
            "three_act": {
                "name": "三幕式结构",
                "description": "经典的开端、发展、高潮、结局结构",
                "acts": [
                    {"name": "第一幕", "percent": 25, "purpose": "建立世界观，引入人物，触发事件"},
                    {"name": "第二幕", "percent": 50, "purpose": "发展冲突，提升紧张感"},
                    {"name": "第三幕", "percent": 25, "purpose": "高潮与解决"},
                ],
            },
            "hero_journey": {
                "name": "英雄之旅",
                "description": "坎贝尔的英雄之旅结构",
                "stages": [
                    "平凡世界",
                    "冒险召唤",
                    "拒斥召唤",
                    "见导师",
                    "越过第一道边界",
                    "考验、伙伴、敌人",
                    "接近深层的洞穴",
                    "核心磨难",
                    "报酬",
                    "返回之路",
                    "复活",
                    "携万能药回归",
                ],
            },
            "web_novel": {
                "name": "网络小说结构",
                "description": "适合网络连载的爽文结构",
                "elements": [
                    "开篇 hook",
                    "金手指设定",
                    "第一个小高潮",
                    "升级体系",
                    "中期大高潮",
                    "最终决战",
                ],
            },
        }

    def _load_plot_templates(self) -> Dict:
        """加载情节模板"""
        return {
            "fantasy": [
                "英雄觉醒",
                "魔法学院",
                "魔王复苏",
                "上古神器",
                "种族战争",
            ],
            "xianxia": [
                "炼气筑基",
                "宗门大比",
                "秘境探险",
                "飞升之路",
                "三界争霸",
            ],
            "romance": [
                "初遇",
                "误会",
                "相知",
                "考验",
                "终成眷属",
            ],
            "scifi": [
                "太空探索",
                "外星接触",
                "科技危机",
                "时间穿越",
                "星际战争",
            ],
        }

    def get_structure_for_chapter(
        self,
        genre: str,
        chapter_number: int,
        total_chapters: int = 100,
    ) -> Dict[str, Any]:
        """获取章节的叙事结构指导"""
        progress = chapter_number / total_chapters if total_chapters > 0 else 0.5

        # 根据进度确定阶段
        if progress < 0.25:
            stage = "setup"
            stage_name = "开篇铺垫"
            purpose = "建立世界观，介绍主要人物，埋下伏笔"
        elif progress < 0.75:
            stage = "development"
            stage_name = "情节发展"
            purpose = "发展冲突，提升紧张感，推进主线"
        else:
            stage = "climax"
            stage_name = "高潮结局"
            purpose = "解决冲突，完成人物弧光，收尾"

        # 获取类型相关的情节建议
        plot_suggestions = self.plot_templates.get(genre, [])

        return {
            "stage": stage,
            "stage_name": stage_name,
            "purpose": purpose,
            "progress": progress,
            "plot_suggestions": plot_suggestions,
            "description": f"第{chapter_number}章处于{stage_name}阶段：{purpose}",
        }

    def generate_plot_outline(
        self,
        genre: str,
        chapter_count: int,
    ) -> List[Dict[str, Any]]:
        """生成情节大纲"""
        outline = []

        for i in range(1, chapter_count + 1):
            structure = self.get_structure_for_chapter(genre, i, chapter_count)
            outline.append({
                "chapter": i,
                "stage": structure["stage"],
                "stage_name": structure["stage_name"],
                "purpose": structure["purpose"],
                "suggestions": structure["plot_suggestions"],
            })

        return outline
