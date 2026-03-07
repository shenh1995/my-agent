"""My Agent - Claude Agent SDK Interactive CLI Tool"""

import os

__version__ = "1.0.0"

# 全局状态：启动目录 - 在模块加载时立即捕获
_startup_cwd = os.getcwd()


def set_startup_cwd(cwd: str):
    """设置启动目录"""
    global _startup_cwd
    _startup_cwd = cwd


def get_startup_cwd() -> str:
    """获取启动目录"""
    return _startup_cwd