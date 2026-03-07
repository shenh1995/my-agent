"""My Agent - Claude Agent SDK Interactive CLI Tool"""

__version__ = "1.0.0"

# 全局状态：启动目录
_startup_cwd = None


def set_startup_cwd(cwd: str):
    """设置启动目录"""
    global _startup_cwd
    _startup_cwd = cwd


def get_startup_cwd() -> str:
    """获取启动目录，如果未设置则返回当前目录"""
    return _startup_cwd or _get_original_cwd()


def _get_original_cwd() -> str:
    """获取原始启动目录（从环境变量或当前目录）"""
    import os
    return os.environ.get('MY_AGENT_STARTUP_CWD', os.getcwd())