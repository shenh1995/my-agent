"""Skill 管理器"""

import os
import re
from typing import Dict, List, Optional

import yaml

from .config import Skill, SkillsConfig


class SkillManager:
    """Skill 管理器

    管理 Skill 的加载、查找和执行
    """

    def __init__(self):
        self.config = SkillsConfig()
        self._loaded = False

    def load_skills(self) -> Dict[str, Skill]:
        """从配置文件加载 skills

        配置文件路径按优先级：
        1. ./.skills.yaml - 项目目录
        2. ~/.claude/skills.yaml - 用户全局配置

        Returns:
            加载的 skills 字典
        """
        if self._loaded:
            return self.config.skills

        config_paths = self._get_config_paths()

        for path in config_paths:
            if os.path.exists(path):
                try:
                    self._load_from_file(path)
                except Exception as e:
                    print(f"  \033[90m加载 skills 配置失败 ({path}): {e}\033[0m")

        self._loaded = True
        return self.config.skills

    def _get_config_paths(self) -> List[str]:
        """获取配置文件路径列表（按优先级）"""
        paths = []

        # 项目目录配置
        project_config = os.path.join(os.getcwd(), ".skills.yaml")
        paths.append(project_config)

        # 用户全局配置
        home = os.path.expanduser("~")
        global_config = os.path.join(home, ".claude", "skills.yaml")
        paths.append(global_config)

        return paths

    def _load_from_file(self, path: str):
        """从 YAML 文件加载配置

        Args:
            path: 配置文件路径
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data or 'skills' not in data:
            return

        skills_data = data['skills']

        for name, skill_data in skills_data.items():
            if isinstance(skill_data, dict):
                skill = Skill(
                    name=name,
                    description=skill_data.get('description', ''),
                    prompt=skill_data.get('prompt', ''),
                    tools=skill_data.get('tools'),
                    model=skill_data.get('model'),
                    namespace=skill_data.get('namespace'),
                )
                self.config.add_skill(skill)

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取 skill

        Args:
            name: skill 名称（可以带或不带 /）

        Returns:
            Skill 对象或 None
        """
        if not self._loaded:
            self.load_skills()

        return self.config.get_skill(name)

    def has_skill(self, name: str) -> bool:
        """检查是否存在 skill

        Args:
            name: skill 名称

        Returns:
            是否存在
        """
        if not self._loaded:
            self.load_skills()

        return self.config.has_skill(name)

    def render_prompt(self, skill: Skill, args: Optional[str] = None) -> str:
        """渲染提示词模板，注入变量

        支持的变量：
        - {{args}} - 命令行参数
        - {{date}} - 当前日期
        - {{cwd}} - 当前工作目录

        Args:
            skill: Skill 对象
            args: 命令行参数

        Returns:
            渲染后的提示词
        """
        prompt = skill.prompt

        # 替换变量
        variables = {
            'args': args or '',
            'date': self._get_current_date(),
            'cwd': os.getcwd(),
        }

        for var_name, var_value in variables.items():
            placeholder = '{{' + var_name + '}}'
            prompt = prompt.replace(placeholder, var_value)

        # 如果有参数，追加到提示词末尾
        if args and '{{args}}' not in skill.prompt:
            prompt = f"{prompt}\n\n参数: {args}"

        return prompt

    def _get_current_date(self) -> str:
        """获取当前日期字符串"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d')

    def get_available_skills(self) -> List[Skill]:
        """获取所有可用 skills"""
        if not self._loaded:
            self.load_skills()

        return self.config.get_all_skills()

    def get_skill_names(self) -> List[str]:
        """获取所有 skill 名称"""
        if not self._loaded:
            self.load_skills()

        return self.config.get_skill_names()

    def get_slash_commands(self) -> Dict[str, str]:
        """获取斜杠命令字典（用于命令补全）

        Returns:
            命令名到描述的字典
        """
        if not self._loaded:
            self.load_skills()

        commands = {}
        for skill in self.config.get_all_skills():
            commands[f"/{skill.name}"] = skill.description

        return commands

    def reload(self):
        """重新加载配置"""
        self._loaded = False
        self.config = SkillsConfig()
        self.load_skills()


# 全局 Skill 管理器实例
_skill_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    """获取全局 Skill 管理器实例"""
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
    return _skill_manager