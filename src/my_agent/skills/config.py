"""Skill 配置定义"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Skill:
    """Skill 定义"""
    name: str                    # Skill 名称（不含 /）
    description: str             # 描述
    prompt: str                  # 执行时的提示词模板
    tools: Optional[List[str]] = None   # 限制可用工具（None = 所有工具）
    model: Optional[str] = None         # 指定模型
    namespace: Optional[str] = None     # 命名空间（如 "github:commit"）

    def __post_init__(self):
        """初始化后处理"""
        # 确保 name 不包含 /
        if self.name.startswith('/'):
            self.name = self.name[1:]


@dataclass
class SkillsConfig:
    """Skills 配置"""
    skills: Dict[str, Skill] = field(default_factory=dict)

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取 skill

        Args:
            name: skill 名称（可以带或不带 /）

        Returns:
            Skill 对象或 None
        """
        # 移除开头的 /
        if name.startswith('/'):
            name = name[1:]

        return self.skills.get(name)

    def get_all_skills(self) -> List[Skill]:
        """获取所有 skills"""
        return list(self.skills.values())

    def get_skill_names(self) -> List[str]:
        """获取所有 skill 名称"""
        return list(self.skills.keys())

    def add_skill(self, skill: Skill):
        """添加 skill"""
        self.skills[skill.name] = skill

    def has_skill(self, name: str) -> bool:
        """检查是否存在 skill"""
        if name.startswith('/'):
            name = name[1:]
        return name in self.skills