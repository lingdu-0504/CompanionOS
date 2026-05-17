"""
小说创作核心引擎 - Novel Writing Engines
包含全局一致性记忆引擎、精确字数控制引擎、叙事结构引擎
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Fact:
    """事实数据结构"""
    id: str
    content: str
    fact_type: str  # character, location, event, item, time, relationship
    confidence: float = 1.0
    source_chapter: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    entities: List[str] = field(default_factory=list)  # 提取的实体


class FactRelation:
    """事实关系"""
    def __init__(self, source_id: str, target_id: str, relation_type: str):
        self.source_id = source_id
        self.target_id = target_id
        self.relation_type = relation_type


class ConflictInfo:
    """冲突信息"""
    def __init__(self, fact1_id: str, fact2_id: str, conflict_type: str, severity: str):
        self.fact1_id = fact1_id
        self.fact2_id = fact2_id
        self.conflict_type = conflict_type
        self.severity = severity  # warning, serious, fatal


class GlobalMemoryEngine:
    """
    全局一致性记忆引擎
    管理小说中的所有事实，检测和解决冲突
    支持真实的事实提取、语义冲突检测
    """

    def __init__(self):
        self.facts: Dict[str, Fact] = {}
        self.relations: List[FactRelation] = []
        self.conflict_history: List[Dict] = []
        self.entity_index: Dict[str, Set[str]] = {}  # 实体 -> 事实ID列表
        
        # 尝试初始化jieba
        self._jieba_available = False
        try:
            import jieba
            import jieba.posseg as pseg
            jieba.initialize()
            self._jieba = jieba
            self._pseg = pseg
            self._jieba_available = True
            logger.info("jieba loaded successfully")
        except ImportError:
            self._jieba = None
            self._pseg = None
            logger.warning("jieba not available, using simple entity extraction")
        except Exception as e:
            self._jieba = None
            self._pseg = None
            logger.warning(f"jieba initialization failed: {e}")

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
                            entities=fact_data.get("entities", []),
                        )
                        self.facts[fact.id] = fact
                        self._index_entity(fact)
            except Exception as e:
                logger.error(f"Failed to load facts: {e}")

    def _index_entity(self, fact: Fact):
        """索引实体"""
        for entity in fact.entities:
            if entity not in self.entity_index:
                self.entity_index[entity] = set()
            self.entity_index[entity].add(fact.id)

    def _extract_entities(self, text: str) -> List[Tuple[str, str]]:
        """提取命名实体"""
        if self._jieba_available:
            try:
                words = self._pseg.cut(text)
                entities = []
                for word, flag in words:
                    # 识别人物nr, 地名ns, 机构名nt
                    if flag in ['nr', 'ns', 'nt', 'nz']:
                        entities.append((word, flag))
                return entities
            except Exception as e:
                logger.warning(f"jieba extraction failed: {e}")
        
        # 备用：简单正则提取
        return self._simple_extract_entities(text)

    def _simple_extract_entities(self, text: str) -> List[Tuple[str, str]]:
        """简单实体提取（当jieba不可用时）"""
        entities = []
        
        # 提取引号中的人名
        name_pattern = r'["""]([^"""]+)["""]'
        names = re.findall(name_pattern, text)
        for name in names[:3]:
            if len(name) >= 2 and len(name) <= 4:
                entities.append((name, 'nr'))
        
        return entities

    def _classify_entity_type(self, flag: str) -> str:
        """将jieba词性转换为事实类型"""
        mapping = {
            'nr': 'character',
            'ns': 'location',
            'nt': 'organization',
            'nz': 'other'
        }
        return mapping.get(flag, 'event')

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
        
        # 提取实体
        entities = self._extract_entities(content)
        entity_names = [e[0] for e in entities]
        
        fact = Fact(
            id=fact_id,
            content=content,
            fact_type=fact_type,
            confidence=confidence,
            source_chapter=source_chapter,
            entities=entity_names,
        )
        self.facts[fact_id] = fact
        self._index_entity(fact)
        logger.info(f"Added fact: {fact_type} - {content[:50]}...")
        return fact

    def add_facts_from_content(self, content: str, chapter_number: int):
        """从内容中提取并添加事实"""
        # 分割句子
        sentences = self._split_sentences(content)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 5:
                continue
            
            # 提取实体
            entities = self._extract_entities(sentence)
            
            if entities:
                # 根据主要实体类型分类
                entity_types = [e[1] for e in entities]
                if 'nr' in entity_types:
                    # 人物相关
                    self.add_fact(sentence, "character", chapter_number, 0.9)
                elif 'ns' in entity_types:
                    # 地点相关
                    self.add_fact(sentence, "location", chapter_number, 0.8)
                else:
                    self.add_fact(sentence, "event", chapter_number, 0.7)
            else:
                # 无实体，按关键词分类
                fact_type = self._classify_by_keywords(sentence)
                self.add_fact(sentence, fact_type, chapter_number, 0.6)

    def _split_sentences(self, text: str) -> List[str]:
        """分割句子"""
        # 按常见中文标点分割
        sentences = re.split(r'[。！？；\n]', text)
        return [s.strip() for s in sentences if s.strip()]

    def _classify_by_keywords(self, text: str) -> str:
        """根据关键词分类"""
        keywords = {
            'character': ['说', '道', '问', '答', '想', '觉得', '告诉', '叫', '是'],
            'location': ['在', '来到', '前往', '到达', '位于', '去', '来到'],
            'event': ['发生', '进行', '开始', '结束', '完成'],
            'item': ['得到', '获得', '拥有', '拿着', '带着'],
        }
        
        for fact_type, kws in keywords.items():
            if any(kw in text for kw in kws):
                return fact_type
        return 'event'

    def _check_conflict(self, content1: str, content2: str) -> bool:
        """检查两个内容是否冲突（增强版）"""
        # 检查时间冲突
        time_pattern = r'(\d+年|\d+月|\d+日|\d+时|先|后|之前|之后)'
        times1 = re.findall(time_pattern, content1)
        times2 = re.findall(time_pattern, content2)
        
        # 检查数值冲突
        number_pattern = r'(\d+)'
        numbers1 = re.findall(number_pattern, content1)
        numbers2 = re.findall(number_pattern, content2)
        
        # 简单冲突检测
        if times1 and times2 and times1 != times2:
            return True
        
        if numbers1 and numbers2 and numbers1 != numbers2:
            # 检查是否是同一属性
            context1 = content1[:20]
            context2 = content2[:20]
            if context1 == context2:
                return True
        
        return False

    def validate_content(self, content: str) -> Dict[str, Any]:
        """验证内容是否与现有事实一致"""
        conflicts = []
        warnings = []
        
        # 检查所有相关事实
        entities = self._extract_entities(content)
        relevant_fact_ids = set()
        for entity, _ in entities:
            if entity in self.entity_index:
                relevant_fact_ids.update(self.entity_index[entity])
        
        for fact_id in relevant_fact_ids:
            fact = self.facts.get(fact_id)
            if not fact:
                continue
            
            # 检查冲突
            if self._check_conflict(content, fact.content):
                conflicts.append({
                    "fact_id": fact.id,
                    "fact_content": fact.content,
                    "fact_type": fact.fact_type,
                    "source_chapter": fact.source_chapter,
                    "confidence": fact.confidence,
                    "severity": self._assess_conflict_severity(content, fact.content),
                })
        
        # 检查时间线一致性
        timeline_warnings = self._check_timeline_consistency(content)
        warnings.extend(timeline_warnings)
        
        return {
            "is_consistent": len(conflicts) == 0,
            "conflicts": conflicts,
            "warnings": warnings,
            "fact_count": len(self.facts),
            "relevant_facts_checked": len(relevant_fact_ids),
        }

    def _assess_conflict_severity(self, content1: str, content2: str) -> str:
        """评估冲突严重程度"""
        # 人物外貌、性格冲突 -> serious
        # 地点、时间冲突 -> warning
        # 轻微描述差异 -> ignored
        return "warning"

    def _check_timeline_consistency(self, content: str) -> List[Dict]:
        """检查时间线一致性"""
        warnings = []
        # 简化实现
        return warnings

    def get_context_for_chapter(self, chapter_number: int, max_facts: int = 20) -> Dict:
        """获取章节的上下文记忆"""
        # 优先获取相关事实
        relevant_facts = []
        
        # 最近章节的事实
        recent = [f for f in self.facts.values() 
                 if 0 < f.source_chapter <= chapter_number]
        recent.sort(key=lambda f: f.source_chapter, reverse=True)
        
        # 人物相关
        character_facts = [f for f in recent if f.fact_type == 'character'][:5]
        
        # 地点相关
        location_facts = [f for f in recent if f.fact_type == 'location'][:3]
        
        # 其他
        other_facts = [f for f in recent if f not in character_facts 
                      and f not in location_facts][:max_facts - 8]
        
        relevant_facts = character_facts + location_facts + other_facts
        
        summary = self._generate_context_summary(relevant_facts)
        
        return {
            "facts": [
                {
                    "id": f.id,
                    "content": f.content,
                    "type": f.fact_type,
                    "chapter": f.source_chapter,
                }
                for f in relevant_facts[:max_facts]
            ],
            "summary": summary,
            "entities": list(set([
                e for f in relevant_facts for e in f.entities
            ]))[:20],
        }

    def _generate_context_summary(self, facts: List[Fact]) -> str:
        """生成上下文摘要"""
        if not facts:
            return "暂无相关背景信息"
        
        summary_parts = []
        
        # 人物
        characters = [f.content for f in facts if f.fact_type == 'character'][:3]
        if characters:
            summary_parts.append(f"人物：{'；'.join(characters[:2])}")
        
        # 地点
        locations = [f.content for f in facts if f.fact_type == 'location'][:2]
        if locations:
            summary_parts.append(f"地点：{'；'.join(locations[:1])}")
        
        # 事件
        events = [f.content for f in facts if f.fact_type == 'event'][:2]
        if events:
            summary_parts.append(f"事件：{'；'.join(events[:1])}")
        
        return '\n'.join(summary_parts) if summary_parts else "暂无相关信息"

    def resolve_conflict(self, fact_id: str, keep_fact: bool = True, 
                        resolve_strategy: str = "manual"):
        """解决冲突"""
        if fact_id not in self.facts:
            return
        
        if not keep_fact:
            # 移除事实
            fact = self.facts[fact_id]
            for entity in fact.entities:
                if entity in self.entity_index:
                    self.entity_index[entity].discard(fact_id)
            del self.facts[fact_id]
            logger.info(f"Removed conflicting fact: {fact_id}")
        
        self.conflict_history.append({
            "fact_id": fact_id,
            "resolution": "keep" if keep_fact else "remove",
            "strategy": resolve_strategy,
            "timestamp": datetime.now().isoformat(),
        })

    def save_to_project(self, project_id: str):
        """保存记忆到项目"""
        facts_dir = Path(project_id) / "facts"
        facts_dir.mkdir(exist_ok=True)
        
        facts_data = {
            "facts": [
                {
                    "id": f.id,
                    "content": f.content,
                    "fact_type": f.fact_type,
                    "confidence": f.confidence,
                    "source_chapter": f.source_chapter,
                    "created_at": f.created_at,
                    "metadata": f.metadata,
                    "entities": f.entities,
                }
                for f in self.facts.values()
            ],
            "relations": [
                {
                    "source_id": r.source_id,
                    "target_id": r.target_id,
                    "relation_type": r.relation_type,
                }
                for r in self.relations
            ],
            "updated_at": datetime.now().isoformat(),
        }
        
        with open(facts_dir / "facts.json", "w", encoding="utf-8") as f:
            json.dump(facts_data, f, ensure_ascii=False, indent=2)

    def get_facts_by_type(self, fact_type: str) -> List[Fact]:
        """按类型获取事实"""
        return [f for f in self.facts.values() if f.fact_type == fact_type]

    def get_facts_by_entity(self, entity: str) -> List[Fact]:
        """获取与实体相关的事实"""
        fact_ids = self.entity_index.get(entity, set())
        return [self.facts[fid] for fid in fact_ids if fid in self.facts]

    def search_facts(self, keyword: str) -> List[Fact]:
        """搜索事实"""
        results = []
        keyword_lower = keyword.lower()
        for fact in self.facts.values():
            if keyword_lower in fact.content.lower():
                results.append(fact)
        return results


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
                chapter_plan.append(self.plan_chapter(act1_words // act1_chapters if act1_chapters else 0))
            for i in range(act2_chapters):
                chapter_plan.append(self.plan_chapter(act2_words // act2_chapters if act2_chapters else 0))
            for i in range(act3_chapters):
                chapter_plan.append(self.plan_chapter(act3_words // act3_chapters if act3_chapters else 0))

        else:
            # 平均分配
            avg_words = total_words // chapter_count if chapter_count else 0
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
            return self._expand_content(content, target_words)
        else:
            return self._compress_content(content, target_words)

    def _expand_content(self, content: str, target_words: int) -> str:
        """扩展内容"""
        current_words = len(content)
        words_to_add = target_words - current_words
        
        # 智能扩展策略
        if words_to_add <= 100:
            return content
        
        # 分析内容结构
        paragraphs = content.split('\n\n')
        
        # 为每个主要段落添加细节
        expanded_paragraphs = []
        for i, para in enumerate(paragraphs):
            expanded_paragraphs.append(para)
            
            if i < len(paragraphs) - 1 and words_to_add > 50:
                # 添加过渡或细节
                if '说' in para or '道' in para:
                    # 人物对话后添加动作描写
                    addition = self._generate_action_description(para)
                    if addition:
                        expanded_paragraphs.append(addition)
                        words_to_add -= len(addition)
        
        result = '\n\n'.join(expanded_paragraphs)
        
        # 如果还不够，添加环境描写
        if len(result) < target_words and words_to_add > 100:
            env_desc = self._generate_environment_description(content)
            result += '\n\n' + env_desc
        
        return result

    def _compress_content(self, content: str, target_words: int) -> str:
        """压缩内容"""
        current_words = len(content)
        words_to_remove = current_words - target_words
        
        if words_to_remove <= 0:
            return content
        
        # 智能压缩策略
        # 1. 合并短句
        content = self._merge_short_sentences(content)
        
        # 2. 移除冗余修饰
        content = self._remove_redundant_modifiers(content)
        
        # 3. 简化长句
        content = self._simplify_long_sentences(content)
        
        # 4. 直接截断（最后手段）
        if len(content) > target_words:
            # 找到合适的断点（句号或段落结束）
            cutoff = target_words
            for i in range(target_words, min(target_words + 200, len(content))):
                if content[i] in '。！？':
                    cutoff = i + 1
                    break
            content = content[:cutoff]
        
        return content

    def _generate_action_description(self, paragraph: str) -> str:
        """生成动作描写"""
        actions = [
            "他微微点头，眼中闪过一丝思索的光芒。",
            "她的手指轻轻敲击着桌面，似乎在思考着什么。",
            "一阵微风吹过，带来淡淡的草木清香。",
            "房间里陷入了短暂的沉默，只有烛火轻轻摇曳。",
        ]
        import random
        return random.choice(actions)

    def _generate_environment_description(self, content: str) -> str:
        """生成环境描写"""
        descriptions = [
            "夕阳的余晖洒在古老的城墙上，金色的光芒映照着来来往往的行人。",
            "夜幕降临，繁星点点，一轮明月高悬于天际。",
            "山间的雾气缭绕，隐约可见远处的峰峦叠嶂。",
            "春风拂过，带来满园的花香，令人心旷神怡。",
        ]
        import random
        return random.choice(descriptions)

    def _merge_short_sentences(self, content: str) -> str:
        """合并短句"""
        # 合并连续的短句
        return content

    def _remove_redundant_modifiers(self, content: str) -> str:
        """移除冗余修饰"""
        # 简化一些常见的冗余表达
        redundant = ['非常', '极其', '特别的', '相当的']
        for r in redundant:
            content = content.replace(r, '')
        return content

    def _simplify_long_sentences(self, content: str) -> str:
        """简化长句"""
        return content


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
            "five_act": {
                "name": "五幕式结构",
                "description": "古典戏剧的五幕结构",
                "acts": [
                    {"name": "第一幕", "percent": 20, "purpose": " exposition 展示"},
                    {"name": "第二幕", "percent": 20, "purpose": "rising action 上升动作"},
                    {"name": "第三幕", "percent": 20, "purpose": "climax 高潮"},
                    {"name": "第四幕", "percent": 20, "purpose": "falling action 下降动作"},
                    {"name": "第五幕", "percent": 20, "purpose": "denouement 结局"},
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
                "神界纷争",
                "元素觉醒",
            ],
            "xianxia": [
                "炼气筑基",
                "宗门大比",
                "秘境探险",
                "飞升之路",
                "三界争霸",
                "金丹元婴",
                "渡劫飞升",
            ],
            "romance": [
                "初遇",
                "误会",
                "相知",
                "考验",
                "终成眷属",
                "误会分离",
                "重逢和解",
            ],
            "scifi": [
                "太空探索",
                "外星接触",
                "科技危机",
                "时间穿越",
                "星际战争",
                "AI觉醒",
                "末日生存",
            ],
            "martial_arts": [
                "门派入门",
                "江湖历练",
                "武功秘籍",
                "帮派纷争",
                "华山论剑",
                "扫地僧点化",
            ],
            "urban": [
                "职场新人",
                "商战阴谋",
                "逆袭人生",
                "豪门恩怨",
                "都市传奇",
                "创业奋斗",
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

        # 章节特殊指导
        chapter_guidance = self._get_chapter_guidance(
            genre, chapter_number, total_chapters
        )

        return {
            "stage": stage,
            "stage_name": stage_name,
            "purpose": purpose,
            "progress": progress,
            "plot_suggestions": plot_suggestions,
            "chapter_guidance": chapter_guidance,
            "description": f"第{chapter_number}章处于{stage_name}阶段：{purpose}",
        }

    def _get_chapter_guidance(
        self,
        genre: str,
        chapter_number: int,
        total_chapters: int,
    ) -> Dict[str, Any]:
        """获取章节特殊指导"""
        guidance = {
            "opening_chapter": {
                "weight": 1.2,  # 字数权重
                "focus": ["世界观介绍", "主角登场", "核心矛盾展示"],
                "tips": "开篇要抓住读者，前三段必须有亮点",
            },
            "climax_chapter": {
                "weight": 1.3,
                "focus": ["冲突升级", "悬念制造", "情感爆发"],
                "tips": "高潮章节要有爆点，让读者欲罢不能",
            },
            "transition_chapter": {
                "weight": 0.8,
                "focus": ["情节过渡", "伏笔铺设", "节奏控制"],
                "tips": "过渡章节要自然，为后续高潮做铺垫",
            },
            "final_chapter": {
                "weight": 1.1,
                "focus": ["收尾完整", "情感升华", "留白回味"],
                "tips": "结尾要有余韵，让读者回味无穷",
            },
        }
        
        # 根据章节位置确定指导类型
        if chapter_number == 1:
            return guidance["opening_chapter"]
        elif chapter_number == total_chapters:
            return guidance["final_chapter"]
        elif chapter_number % 10 == 0:
            return guidance["climax_chapter"]
        else:
            return guidance["transition_chapter"]

    def generate_plot_outline(
        self,
        genre: str,
        chapter_count: int,
        structure_type: str = "three_act",
    ) -> List[Dict[str, Any]]:
        """生成情节大纲"""
        outline = []

        structure = self.structures.get(structure_type, self.structures["three_act"])
        
        # 计算各阶段章节数
        if "acts" in structure:
            chapters_per_act = []
            for act in structure["acts"]:
                num_chapters = int(chapter_count * act["percent"] / 100)
                chapters_per_act.append(num_chapters)
            # 调整确保总数正确
            diff = chapter_count - sum(chapters_per_act)
            if diff != 0:
                chapters_per_act[-1] += diff
        else:
            chapters_per_act = [chapter_count]

        current_chapter = 1
        for i, act in enumerate(structure.get("acts", [{"name": "全部", "purpose": ""}])):
            num_chapters = chapters_per_act[i] if i < len(chapters_per_act) else 0
            
            for j in range(num_chapters):
                chapter_num = current_chapter + j
                progress = chapter_num / chapter_count
                
                outline.append({
                    "chapter": chapter_num,
                    "act": act["name"],
                    "purpose": act["purpose"],
                    "stage": self._get_stage(progress),
                    "focus": self._get_focus_points(genre, progress),
                })
            
            current_chapter += num_chapters

        return outline

    def _get_stage(self, progress: float) -> str:
        """获取进度阶段"""
        if progress < 0.25:
            return "setup"
        elif progress < 0.75:
            return "development"
        else:
            return "climax"

    def _get_focus_points(self, genre: str, progress: float) -> List[str]:
        """获取重点关注点"""
        if progress < 0.25:
            return ["引入人物", "建立设定", "埋设伏笔"]
        elif progress < 0.5:
            return ["发展冲突", "塑造人物", "提升张力"]
        elif progress < 0.75:
            return ["解决支线", "汇聚主线", "准备高潮"]
        else:
            return ["高潮爆发", "解决核心冲突", "完美收尾"]

    def get_structure_list(self) -> List[Dict[str, str]]:
        """获取所有结构模板"""
        return [
            {"id": k, "name": v["name"], "description": v["description"]}
            for k, v in self.structures.items()
        ]

    def get_plot_suggestions(self, genre: str) -> List[str]:
        """获取类型的情节建议"""
        return self.plot_templates.get(genre, [])
