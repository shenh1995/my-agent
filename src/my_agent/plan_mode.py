"""Plan Mode 状态管理

Plan Mode 是一种只读探索模式，用于在执行复杂任务前：
1. 进行只读探索（使用只读工具）
2. 生成实施计划
3. 让用户审批后执行
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional


# 只读工具列表 - Plan Mode 下允许使用的工具
READ_ONLY_TOOLS = [
    "read_file",
    "list_directory",
    "glob",
    "grep",
]

# 写入工具列表 - Plan Mode 下禁止使用的工具
WRITE_TOOLS = [
    "write_file",
    "edit_file",
    "bash",
]


@dataclass
class PlanModeState:
    """Plan Mode 状态"""
    is_active: bool = False
    plan_file: str = ".claude/plans/plan.md"
    plan_content: str = ""
    exploration_complete: bool = False


# 全局状态实例
_plan_mode_state = PlanModeState()


def toggle_plan_mode() -> bool:
    """切换 Plan Mode 状态

    Returns:
        新的状态（True 表示 Plan Mode 已启用）
    """
    global _plan_mode_state
    _plan_mode_state.is_active = not _plan_mode_state.is_active

    # 如果关闭 Plan Mode，重置状态
    if not _plan_mode_state.is_active:
        _plan_mode_state.exploration_complete = False
        _plan_mode_state.plan_content = ""

    return _plan_mode_state.is_active


def is_plan_mode() -> bool:
    """检查是否在 Plan Mode

    Returns:
        True 表示在 Plan Mode
    """
    return _plan_mode_state.is_active


def get_plan_mode_state() -> PlanModeState:
    """获取 Plan Mode 状态对象

    Returns:
        PlanModeState 实例
    """
    return _plan_mode_state


def set_plan_content(content: str):
    """设置计划内容

    Args:
        content: 计划内容
    """
    _plan_mode_state.plan_content = content


def get_plan_content() -> str:
    """获取计划内容

    Returns:
        计划内容
    """
    return _plan_mode_state.plan_content


def set_exploration_complete(complete: bool = True):
    """设置探索完成状态

    Args:
        complete: 是否完成探索
    """
    _plan_mode_state.exploration_complete = complete


def is_exploration_complete() -> bool:
    """检查探索是否完成

    Returns:
        True 表示探索已完成
    """
    return _plan_mode_state.exploration_complete


def get_read_only_tools() -> List[str]:
    """获取只读工具列表

    Returns:
        只读工具名称列表
    """
    return READ_ONLY_TOOLS.copy()


def get_write_tools() -> List[str]:
    """获取写入工具列表

    Returns:
        写入工具名称列表
    """
    return WRITE_TOOLS.copy()


def is_tool_allowed_in_plan_mode(tool_name: str) -> bool:
    """检查工具是否在 Plan Mode 下允许使用

    Args:
        tool_name: 工具名称

    Returns:
        True 表示允许使用
    """
    # 检查是否是只读工具
    for allowed in READ_ONLY_TOOLS:
        if tool_name == allowed or tool_name.endswith(f"__{allowed}"):
            return True
    return False


def get_plan_file_path(work_dir: str = ".") -> str:
    """获取计划文件路径

    Args:
        work_dir: 工作目录

    Returns:
        计划文件的完整路径
    """
    return os.path.join(work_dir, _plan_mode_state.plan_file)


def save_plan_to_file(work_dir: str = ".") -> bool:
    """保存计划到文件

    Args:
        work_dir: 工作目录

    Returns:
        True 表示保存成功
    """
    plan_path = get_plan_file_path(work_dir)
    plan_dir = os.path.dirname(plan_path)

    try:
        # 确保目录存在
        os.makedirs(plan_dir, exist_ok=True)

        # 写入计划
        with open(plan_path, 'w', encoding='utf-8') as f:
            f.write(_plan_mode_state.plan_content)

        return True
    except Exception as e:
        print(f"  保存计划失败: {e}")
        return False


def load_plan_from_file(work_dir: str = ".") -> Optional[str]:
    """从文件加载计划

    Args:
        work_dir: 工作目录

    Returns:
        计划内容，如果文件不存在则返回 None
    """
    plan_path = get_plan_file_path(work_dir)

    try:
        if os.path.exists(plan_path):
            with open(plan_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception:
        pass

    return None


def get_plan_mode_system_prompt() -> str:
    """获取 Plan Mode 专用系统提示词

    Returns:
        系统提示词
    """
    return """# Plan Mode 指南

你正在 Plan Mode（计划模式）下工作。这是一个只读探索模式。

## 你的任务

1. **探索代码库**：使用只读工具（read_file, list_directory, glob, grep）来理解项目结构和现有代码
2. **分析需求**：仔细理解用户的任务需求
3. **生成计划**：在完成探索后，生成一个详细的实施计划

## 限制

- 你只能使用只读工具，不能修改任何文件
- 不能执行 bash 命令
- 探索完成后，使用 ExitPlanMode 工具提交计划供用户审批

## 计划格式

生成的计划应包含：
- **Context**: 任务背景和当前状态
- **Goal**: 明确的目标
- **Implementation Steps**: 具体的实施步骤
- **Key Files**: 涉及的关键文件
- **Dependencies**: 步骤之间的依赖关系

## 完成

当你完成探索并准备好计划时，调用 ExitPlanMode 工具提交计划。
"""


def reset_plan_mode():
    """重置 Plan Mode 状态"""
    global _plan_mode_state
    _plan_mode_state = PlanModeState()