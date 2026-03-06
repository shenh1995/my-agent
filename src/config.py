"""Claude Agent SDK 应用程序配置"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AppConfig:
    """应用程序配置类"""

    # 工作目录 - 默认使用当前目录
    work_directory: str = "."

    # 权限模式
    permission_mode: str = "default"

    # 允许的工具列表
    allowed_tools: list[str] = field(
        default_factory=lambda: ["bash", "read_file", "write_file", "write"]
    )

    # 应用版本
    version: str = "1.0.0"

    # 调试模式
    debug_mode: bool = False

    @property
    def absolute_work_directory(self) -> str:
        """获取工作目录的绝对路径"""
        return os.path.abspath(self.work_directory)


# 全局配置实例
config = AppConfig()