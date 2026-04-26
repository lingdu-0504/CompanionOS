"""
CompanionOS 伴侣引擎
Utsuwa关系/情绪引擎 - 8阶段关系进阶 + 多维情绪追踪
"""


# 8阶段关系等级定义（来自Utsuwa）
RELATION_LEVELS = [
    {"level": 1, "name": "陌生人", "threshold": 0, "icon": "🤝"},
    {"level": 2, "name": "熟人", "threshold": 10, "icon": "👋"},
    {"level": 3, "name": "朋友", "threshold": 25, "icon": "😊"},
    {"level": 4, "name": "密友", "threshold": 45, "icon": "😄"},
    {"level": 5, "name": "知己", "threshold": 65, "icon": "🤗"},
    {"level": 6, "name": "恋人", "threshold": 80, "icon": "❤️"},
    {"level": 7, "name": "伴侣", "threshold": 90, "icon": "💑"},
    {"level": 8, "name": "灵魂伴侣", "threshold": 95, "icon": "💞"},
]


class CompanionState:
    """伴侣状态"""

    def __init__(self):
        self.name: str = "小暖"
        self.affection: float = 0.0   # 好感
        self.trust: float = 0.0       # 信任
        self.intimacy: float = 0.0    # 亲密
        self.comfort: float = 0.0     # 舒适
        self.respect: float = 0.0     # 尊重
        self.current_emotion: str = "neutral"

    @property
    def relation_level(self) -> int:
        """当前关系等级"""
        total = self._total_score
        for i in range(len(RELATION_LEVELS) - 1, -1, -1):
            if total >= RELATION_LEVELS[i]["threshold"]:
                return RELATION_LEVELS[i]["level"]
        return 1

    @property
    def relation_name(self) -> str:
        """当前关系名称"""
        for rl in reversed(RELATION_LEVELS):
            if self._total_score >= rl["threshold"]:
                return rl["name"]
        return "陌生人"

    @property
    def _total_score(self) -> float:
        return (self.affection + self.trust + self.intimacy + self.comfort + self.respect) / 5

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "relation_level": self.relation_level,
            "relation_name": self.relation_name,
            "affection": self.affection,
            "trust": self.trust,
            "intimacy": self.intimacy,
            "comfort": self.comfort,
            "respect": self.respect,
            "current_emotion": self.current_emotion,
        }


class UtsuwaEngine:
    """Utsuwa关系/情绪引擎"""

    # 交互类型 → 维度影响映射
    INTERACTION_MAP = {
        "work_complete": {"respect": 2.0, "trust": 0.5},
        "chat": {"affection": 0.5, "comfort": 0.3},
        "comfort": {"trust": 1.0, "comfort": 1.0},
        "praise": {"affection": 1.0, "intimacy": 0.5},
        "long_session": {"comfort": 0.8, "trust": 0.3},
        "emotional_support": {"trust": 1.5, "intimacy": 1.0},
        "greeting": {"affection": 0.2, "comfort": 0.1},
        "task_fail": {"respect": -0.5},
        "negative_response": {"comfort": -0.5, "trust": -0.3},
    }

    def __init__(self, state: CompanionState | None = None):
        self.state = state or CompanionState()
        self._last_milestone_level = self.state.relation_level

    def update_relation(self, interaction_type: str, delta: float = 1.0):
        """更新关系值"""
        if interaction_type in self.INTERACTION_MAP:
            for dimension, base_delta in self.INTERACTION_MAP[interaction_type].items():
                new_value = getattr(self.state, dimension) + base_delta * delta
                setattr(self.state, dimension, max(0, min(100, new_value)))

        milestone = self.get_milestone()
        if milestone:
            print(f"[Utsuwa] {milestone['message']}")

    def set_emotion(self, emotion: str):
        """设置当前情绪"""
        self.state.current_emotion = emotion

    def get_milestone(self) -> dict | None:
        """检查是否达到关系里程碑"""
        current_level = self.state.relation_level

        if self._last_milestone_level < current_level:
            milestone = None
            for rl in RELATION_LEVELS:
                if rl["level"] == current_level:
                    milestone = {
                        "type": "relation_upgrade",
                        "from_level": self._last_milestone_level,
                        "to_level": current_level,
                        "name": rl["name"],
                        "icon": rl["icon"],
                        "message": f"关系升级：{rl['icon']} {rl['name']}",
                        "timestamp": __import__('datetime').datetime.now().isoformat(),
                    }
                    break

            self._last_milestone_level = current_level

            if milestone:
                return milestone

        return None

    def get_state(self) -> dict:
        """获取伴侣状态"""
        return self.state.to_dict()
