"""Skill 系统

提供可配置的 Skill 功能，用户可以通过斜杠命令执行预定义的任务。
"""

from .config import Skill, SkillsConfig
from .manager import SkillManager, get_skill_manager

__all__ = [
    'Skill',
    'SkillsConfig',
    'SkillManager',
    'get_skill_manager',
]