"""
创作风格管理系统
支持风格配置、学习和保持
"""
import json
import re
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass, field, asdict
from enum import Enum


class WritingStyle(Enum):
    """写作风格类型"""
    XUANHUAN = "xuanhuan"  # 玄幻仙侠
    XIANXIA = "xianxia"  # 修仙
    WUXIA = "wuxia"  # 武侠
    MODERN = "modern"  # 都市
    ROMANCE = "romance"  # 言情
    SCIFI = "scifi"  # 科幻
    FANTASY = "fantasy"  # 西方奇幻
    HISTORICAL = "historical"  # 历史
    GAME = "game"  # 游戏竞技
    MYSTERY = "mystery"  # 悬疑


class ToneStyle(Enum):
    """语气风格"""
    LIGHT = "light"  # 轻松搞笑
    SERIOUS = "serious"  # 严肃深沉
    ROMANTIC = "romantic"  # 浪漫温馨
    EXCITING = "exciting"  # 紧张刺激
    PHILOSOPHICAL = "philosophical"  # 哲理思辨
    WARM = "warm"  # 温暖治愈


class NarrativeMode(Enum):
    """叙事模式"""
    FIRST_PERSON = "first_person"  # 第一人称
    THIRD_PERSON_LIMITED = "third_limited"  # 第三人称有限
    THIRD_PERSON_OMNISCIENT = "third_omniscient"  # 第三人称全知


@dataclass
class StyleProfile:
    """风格配置文件"""
    name: str
    style: WritingStyle
    tone: ToneStyle
    narrative_mode: NarrativeMode
    word_count_per_chapter: int = 3000
    
    # 语言特征
    vocabulary_richness: float = 0.7  # 词汇丰富度 0-1
    sentence_length_avg: int = 20  # 平均句长
    description_ratio: float = 0.3  # 描写占比
    dialogue_ratio: float = 0.4  # 对话占比
    
    # 节奏控制
    action_scenes_ratio: float = 0.35  # 动作场景占比
    cliffhanger_probability: float = 0.8  # 章节末尾设置悬念概率
    
    # 主题偏好
    common_themes: List[str] = field(default_factory=list)
    forbidden_words: List[str] = field(default_factory=list)
    
    # 学习到的模式
    learned_patterns: Dict[str, Any] = field(default_factory=dict)
    character_dialogue_styles: Dict[str, Any] = field(default_factory=dict)
    
    created_at: str = field(default_factory=lambda: __import__('datetime').datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: __import__('datetime').datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            **asdict(self),
            'style': self.style.value,
            'tone': self.tone.value,
            'narrative_mode': self.narrative_mode.value,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'StyleProfile':
        """从字典创建"""
        return cls(
            name=data['name'],
            style=WritingStyle(data['style']),
            tone=ToneStyle(data['tone']),
            narrative_mode=NarrativeMode(data['narrative_mode']),
            word_count_per_chapter=data.get('word_count_per_chapter', 3000),
            vocabulary_richness=data.get('vocabulary_richness', 0.7),
            sentence_length_avg=data.get('sentence_length_avg', 20),
            description_ratio=data.get('description_ratio', 0.3),
            dialogue_ratio=data.get('dialogue_ratio', 0.4),
            action_scenes_ratio=data.get('action_scenes_ratio', 0.35),
            cliffhanger_probability=data.get('cliffhanger_probability', 0.8),
            common_themes=data.get('common_themes', []),
            forbidden_words=data.get('forbidden_words', []),
            learned_patterns=data.get('learned_patterns', {}),
            character_dialogue_styles=data.get('character_dialogue_styles', {}),
            created_at=data.get('created_at', None),
            updated_at=data.get('updated_at', None),
        )


class StyleAnalyzer:
    """风格分析器
    分析文本的语言特征、节奏模式等
    """
    
    def __init__(self):
        self.pattern_cache = {}
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """分析文本特征"""
        if not text or len(text.strip()) == 0:
            return {}
        
        analysis = {}
        
        # 基础统计
        analysis['word_count'] = len(text)
        analysis['character_count'] = len(text)
        analysis['paragraph_count'] = text.count('\n\n') + 1
        
        # 句子分析
        sentences = self._split_sentences(text)
        analysis['sentence_count'] = len(sentences)
        analysis['avg_sentence_length'] = sum(len(s) for s in sentences) / len(sentences) if sentences else 0
        analysis['max_sentence_length'] = max(len(s) for s in sentences) if sentences else 0
        analysis['min_sentence_length'] = min(len(s) for s in sentences) if sentences else 0
        
        # 词汇分析
        analysis['vocabulary_richness'] = self._calculate_vocabulary_richness(text)
        
        # 对话分析
        dialogue_text = self._extract_dialogue(text)
        analysis['dialogue_ratio'] = len(dialogue_text) / len(text) if text else 0
        analysis['dialogue_count'] = dialogue_text.count('\n')
        
        # 描写分析
        analysis['description_ratio'] = self._estimate_description_ratio(text)
        
        # 情感倾向（简化）
        analysis['tone_indicators'] = self._detect_tone_indicators(text)
        
        return analysis
    
    def learn_style_from_texts(self, texts: List[str]) -> Dict[str, Any]:
        """从文本中学习风格模式"""
        if not texts:
            return {}
        
        all_analyses = [self.analyze_text(t) for t in texts if t.strip()]
        
        if not all_analyses:
            return {}
        
        # 计算平均特征
        learned = {
            'avg_sentence_length': sum(a['avg_sentence_length'] for a in all_analyses) / len(all_analyses),
            'avg_dialogue_ratio': sum(a['dialogue_ratio'] for a in all_analyses) / len(all_analyses),
            'avg_description_ratio': sum(a['description_ratio'] for a in all_analyses) / len(all_analyses),
            'avg_vocabulary_richness': sum(a['vocabulary_richness'] for a in all_analyses) / len(all_analyses),
            'sample_count': len(all_analyses),
        }
        
        return learned
    
    def compare_styles(self, analysis1: Dict, analysis2: Dict) -> float:
        """比较两个文本的风格相似度 (0-1)"""
        if not analysis1 or not analysis2:
            return 0.5
        
        # 计算各个维度的差异
        sentence_length_diff = abs(analysis1.get('avg_sentence_length', 20) - analysis2.get('avg_sentence_length', 20)) / 20
        dialogue_diff = abs(analysis1.get('dialogue_ratio', 0.4) - analysis2.get('dialogue_ratio', 0.4))
        description_diff = abs(analysis1.get('description_ratio', 0.3) - analysis2.get('description_ratio', 0.3))
        vocab_diff = abs(analysis1.get('vocabulary_richness', 0.7) - analysis2.get('vocabulary_richness', 0.7))
        
        # 加权平均相似度
        similarity = 1 - (sentence_length_diff * 0.3 + dialogue_diff * 0.3 + description_diff * 0.2 + vocab_diff * 0.2)
        return max(0, min(1, similarity))
    
    def _split_sentences(self, text: str) -> List[str]:
        """分割句子"""
        return [s.strip() for s in re.split(r'[。！？!?]', text) if s.strip()]
    
    def _calculate_vocabulary_richness(self, text: str) -> float:
        """计算词汇丰富度（简化版）"""
        chars = set(text)
        total_chars = len(text)
        return min(1, len(chars) / max(total_chars, 100))
    
    def _extract_dialogue(self, text: str) -> str:
        """提取对话文本"""
        dialogue = []
        # 简单引号匹配
        quote_pattern = r'[“"](.*?)[”"]'
        matches = re.findall(quote_pattern, text)
        return '\n'.join(matches)
    
    def _estimate_description_ratio(self, text: str) -> float:
        """估算描写占比（简化版）"""
        # 统计写景、抒情等描述性词汇
        desc_words = ['的', '在', '有', '是', '像', '如同', '仿佛', '只见', '只见', '忽然', '突然']
        total_words = len(text)
        desc_count = sum(text.count(word) for word in desc_words)
        return min(1, desc_count / max(total_words, 1))
    
    def _detect_tone_indicators(self, text: str) -> Dict[str, float]:
        """检测语气指标（简化版）"""
        indicators = {
            'exclamations': text.count('！'),
            'questions': text.count('？'),
            'laugh_words': text.count('哈哈'),
            'serious_words': sum(text.count(w) for w in ['咬牙', '愤怒', '狰狞', '冷酷']),
            'romantic_words': sum(text.count(w) for w in ['温柔', '爱恋', '心', '喜欢']),
        }
        return indicators


class StyleGenerator:
    """风格提示词生成器
    根据风格配置生成提示词
    """
    
    def __init__(self):
        self.style_templates = self._init_style_templates()
        self.tone_templates = self._init_tone_templates()
    
    def generate_prompt(self, profile: StyleProfile) -> str:
        """生成风格提示词"""
        parts = []
        
        # 基础风格
        parts.append(self.style_templates.get(profile.style, ""))
        
        # 语气风格
        parts.append(self.tone_templates.get(profile.tone, ""))
        
        # 叙事模式
        parts.append(self._get_narrative_mode_prompt(profile.narrative_mode))
        
        # 语言特征
        parts.append(self._get_language_prompt(profile))
        
        # 节奏控制
        parts.append(self._get_pacing_prompt(profile))
        
        # 主题和禁忌
        if profile.common_themes:
            parts.append(f"请围绕以下主题创作：{', '.join(profile.common_themes)}")
        if profile.forbidden_words:
            parts.append(f"请避免使用以下词汇：{', '.join(profile.forbidden_words)}")
        
        return '\n\n'.join(filter(None, parts))
    
    def generate_style_feedback(self, generated_text: str, profile: StyleProfile, 
                               analyzer: StyleAnalyzer) -> str:
        """生成风格反馈和调整建议"""
        analysis = analyzer.analyze_text(generated_text)
        
        feedback_parts = []
        
        # 检查对话占比
        dialogue_diff = analysis['dialogue_ratio'] - profile.dialogue_ratio
        if abs(dialogue_diff) > 0.1:
            if dialogue_diff > 0:
                feedback_parts.append("对话内容较多，建议适当增加情节推进和描写")
            else:
                feedback_parts.append("对话内容较少，建议增加角色互动")
        
        # 检查描写占比
        desc_diff = analysis['description_ratio'] - profile.description_ratio
        if abs(desc_diff) > 0.1:
            if desc_diff > 0:
                feedback_parts.append("描写篇幅较长，建议加快叙事节奏")
            else:
                feedback_parts.append("描写较少，建议适当增加环境和细节描写")
        
        # 检查句长
        sent_diff = analysis['avg_sentence_length'] - profile.sentence_length_avg
        if abs(sent_diff) > 5:
            if sent_diff > 0:
                feedback_parts.append("句子偏长，建议拆分部分长句")
            else:
                feedback_parts.append("句子偏短，可适当增加复合句")
        
        if not feedback_parts:
            return "风格保持良好！"
        
        return "风格调整建议：\n" + "\n".join(f"- {p}" for p in feedback_parts)
    
    def _init_style_templates(self) -> Dict[WritingStyle, str]:
        """初始化风格模板"""
        return {
            WritingStyle.XUANHUAN: """创作玄幻小说风格：
- 世界观宏大，修炼体系清晰
- 情节跌宕起伏，反转不断
- 战斗场面精彩，层次分明
- 主角成长线清晰，升级爽点密集
- 境界划分明确（如：炼气、筑基、金丹...）
- 法宝、丹药、功法、灵兽元素丰富
- 语言大气磅礴，富有想象力""",
            
            WritingStyle.XIANXIA: """创作仙侠小说风格：
- 仙气缥缈，意境悠远
- 追求大道，哲理思辨
- 门派林立，江湖恩怨
- 飞剑法宝，斗法精彩
- 炼丹制器，阵法符箓
- 语言优雅，用词考究
- 有诗有词，古风浓郁""",
            
            WritingStyle.WUXIA: """创作武侠小说风格：
- 江湖气重，快意恩仇
- 武功招式有板有眼
- 侠骨柔情，爱恨情仇
- 门派纷争，盟主争霸
- 轻功、内力、剑法、掌法
- 语言简洁有力，节奏感强""",
            
            WritingStyle.MODERN: """创作都市小说风格：
- 贴近现实，接地气
- 职场奋斗、商战、都市生活
- 主角从底层崛起，打脸升级
- 都市异能、重生、系统元素
- 语言生活化，对话自然
- 节奏明快，爽点密集""",
            
            WritingStyle.ROMANCE: """创作言情小说风格：
- 情感细腻，描写动人
- 互动甜蜜，撒糖不断
- 误会、和解、告白情节
- 心理描写丰富
- 语言温柔，氛围浪漫""",
            
            WritingStyle.SCIFI: """创作科幻小说风格：
- 设定严谨，科幻元素丰富
- 未来感强，技术细节真实
- 太空探索、外星文明、人工智能
- 世界观宏大，逻辑自洽
- 语言理性，同时富有想象力""",
            
            WritingStyle.FANTASY: """创作西方奇幻风格：
- 魔法、剑与魔法、中世纪
- 龙、精灵、矮人、兽人
- 史诗感强，冒险征途
- 魔法体系清晰
- 语言华丽，描写细腻""",
        }
    
    def _init_tone_templates(self) -> Dict[ToneStyle, str]:
        """初始化语气模板"""
        return {
            ToneStyle.LIGHT: """整体语气轻松搞笑：
- 偶尔加入吐槽和段子
- 主角性格幽默风趣
- 情节有喜剧元素
- 对话轻松有趣""",
            
            ToneStyle.SERIOUS: """整体语气严肃深沉：
- 主题深刻，冲突沉重
- 描写真实，少喜剧元素
- 人物性格沉稳
- 氛围凝重""",
            
            ToneStyle.ROMANTIC: """整体语气浪漫温馨：
- 氛围温暖美好
- 情感描写细腻
- 景色描写衬托心情
- 对话温情脉脉""",
            
            ToneStyle.EXCITING: """整体语气紧张刺激：
- 节奏快，紧迫感强
- 危机不断，悬念重重
- 战斗描写精彩
- 让读者心跳加速""",
            
            ToneStyle.PHILOSOPHICAL: """整体语气富有哲理：
- 探讨人生、命运、大道
- 思想深度
- 对话有思辨性
- 主题有深度""",
            
            ToneStyle.WARM: """整体语气温暖治愈：
- 小确幸，日常温暖
- 人物关系和睦
- 描写有烟火气
- 给人治愈感""",
        }
    
    def _get_narrative_mode_prompt(self, mode: NarrativeMode) -> str:
        """获取叙事模式提示"""
        prompts = {
            NarrativeMode.FIRST_PERSON: """使用第一人称叙事：
- 以"我"的视角讲述
- 侧重内心独白
- 读者跟随主角亲身经历""",
            
            NarrativeMode.THIRD_PERSON_LIMITED: """使用第三人称有限视角：
- 主要跟随主角视角
- 描写主角的所见所闻所感
- 适当切换但不频繁""",
            
            NarrativeMode.THIRD_PERSON_OMNISCIENT: """使用第三人称全知视角：
- 可以描写多个角色的内心
- 展现全局视角
- 多条线索并行""",
        }
        return prompts.get(mode, "")
    
    def _get_language_prompt(self, profile: StyleProfile) -> str:
        """获取语言风格提示"""
        return f"""语言风格要求：
- 平均每句约{profile.sentence_length_avg}字
- 描写占比约{int(profile.description_ratio * 100)}%
- 对话占比约{int(profile.dialogue_ratio * 100)}%
- 词汇丰富度：{'较高' if profile.vocabulary_richness > 0.7 else '适中' if profile.vocabulary_richness > 0.5 else '简洁'}"""
    
    def _get_pacing_prompt(self, profile: StyleProfile) -> str:
        """获取节奏控制提示"""
        pacing = []
        
        if profile.action_scenes_ratio > 0.4:
            pacing.append("加快节奏，增加战斗和行动场景")
        elif profile.action_scenes_ratio < 0.2:
            pacing.append("放缓节奏，多描写和文戏")
        
        if profile.cliffhanger_probability > 0.7:
            pacing.append("每章结尾设置悬念，吸引读者继续阅读")
        
        return '\n'.join(pacing) if pacing else ""


class StyleManager:
    """风格管理器
    管理风格配置文件、学习风格等
    """
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.profiles: Dict[str, StyleProfile] = {}
        self.analyzer = StyleAnalyzer()
        self.generator = StyleGenerator()
        self._load_profiles()
    
    def create_profile(self, name: str, style: WritingStyle, 
                      tone: ToneStyle = ToneStyle.SERIOUS,
                      narrative_mode: NarrativeMode = NarrativeMode.THIRD_PERSON_LIMITED) -> StyleProfile:
        """创建风格配置文件"""
        profile = StyleProfile(
            name=name,
            style=style,
            tone=tone,
            narrative_mode=narrative_mode,
        )
        self.profiles[name] = profile
        self._save_profile(profile)
        return profile
    
    def get_profile(self, name: str) -> Optional[StyleProfile]:
        """获取风格配置"""
        return self.profiles.get(name)
    
    def list_profiles(self) -> List[Dict]:
        """列出所有风格配置"""
        return [
            {
                'name': p.name,
                'style': p.style.value,
                'tone': p.tone.value,
                'updated_at': p.updated_at,
            }
            for p in self.profiles.values()
        ]
    
    def update_profile(self, name: str, updates: Dict) -> Optional[StyleProfile]:
        """更新风格配置"""
        if name not in self.profiles:
            return None
        
        profile = self.profiles[name]
        
        # 更新字段
        for key, value in updates.items():
            if key == 'style':
                profile.style = WritingStyle(value)
            elif key == 'tone':
                profile.tone = ToneStyle(value)
            elif key == 'narrative_mode':
                profile.narrative_mode = NarrativeMode(value)
            elif hasattr(profile, key):
                setattr(profile, key, value)
        
        profile.updated_at = __import__('datetime').datetime.now().isoformat()
        self._save_profile(profile)
        return profile
    
    def delete_profile(self, name: str) -> bool:
        """删除风格配置"""
        if name not in self.profiles:
            return False
        
        del self.profiles[name]
        profile_file = self.data_dir / f"style_{name}.json"
        if profile_file.exists():
            profile_file.unlink()
        return True
    
    def learn_style_from_examples(self, profile_name: str, 
                                example_texts: List[str]) -> StyleProfile:
        """从示例文本中学习风格"""
        profile = self.profiles.get(profile_name)
        if not profile:
            raise ValueError(f"Profile {profile_name} not found")
        
        # 分析示例文本
        learned = self.analyzer.learn_style_from_texts(example_texts)
        
        # 更新配置
        if learned:
            profile.sentence_length_avg = int(learned['avg_sentence_length'])
            profile.dialogue_ratio = learned['avg_dialogue_ratio']
            profile.description_ratio = learned['avg_description_ratio']
            profile.vocabulary_richness = learned['avg_vocabulary_richness']
            profile.learned_patterns = learned
            profile.updated_at = __import__('datetime').datetime.now().isoformat()
            self._save_profile(profile)
        
        return profile
    
    def generate_style_prompt(self, profile_name: str) -> Optional[str]:
        """生成风格提示词"""
        profile = self.profiles.get(profile_name)
        if not profile:
            return None
        return self.generator.generate_prompt(profile)
    
    def analyze_style_consistency(self, profile_name: str, 
                                 chapter_text: str) -> Dict[str, Any]:
        """分析风格一致性"""
        profile = self.profiles.get(profile_name)
        if not profile:
            return {'consistent': False, 'error': 'Profile not found'}
        
        # 分析当前章节
        chapter_analysis = self.analyzer.analyze_text(chapter_text)
        
        # 生成反馈
        feedback = self.generator.generate_style_feedback(
            chapter_text, profile, self.analyzer
        )
        
        return {
            'consistent': True,  # 简化版
            'analysis': chapter_analysis,
            'feedback': feedback,
        }
    
    def _load_profiles(self):
        """加载所有风格配置"""
        for profile_file in self.data_dir.glob("style_*.json"):
            try:
                with open(profile_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    profile = StyleProfile.from_dict(data)
                    self.profiles[profile.name] = profile
            except Exception as e:
                print(f"Failed to load profile {profile_file}: {e}")
    
    def _save_profile(self, profile: StyleProfile):
        """保存风格配置"""
        profile_file = self.data_dir / f"style_{profile.name}.json"
        with open(profile_file, 'w', encoding='utf-8') as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)


# 预设风格配置
PRESET_STYLES = {
    '玄幻爽文': (WritingStyle.XUANHUAN, ToneStyle.EXCITING, NarrativeMode.THIRD_PERSON_LIMITED),
    '古典仙侠': (WritingStyle.XIANXIA, ToneStyle.PHILOSOPHICAL, NarrativeMode.THIRD_PERSON_OMNISCIENT),
    '都市言情': (WritingStyle.MODERN, ToneStyle.ROMANTIC, NarrativeMode.THIRD_PERSON_LIMITED),
    '轻松搞笑': (WritingStyle.MODERN, ToneStyle.LIGHT, NarrativeMode.FIRST_PERSON),
    '硬科幻': (WritingStyle.SCIFI, ToneStyle.SERIOUS, NarrativeMode.THIRD_PERSON_LIMITED),
}
