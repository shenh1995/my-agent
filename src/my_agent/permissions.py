"""权限管理功能"""

import os
import sys
import tty
import termios
from typing import Dict, Any

from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext

from .mcp.tools.bash import (
    execute_bash_streaming,
    check_dangerous_command,
    check_confirm_command,
    DEFAULT_TIMEOUT,
)

# 项目目录（需要确认写入的目录）- 使用当前工作目录
PROJECT_DIR = os.getcwd()

def confirm_write(file_path: str) -> bool:
    """确认是否允许写入文件，支持上下键选择

    Args:
        file_path: 要写入的文件路径

    Returns:
        bool: True 表示同意写入，False 表示拒绝
    """
    options = ["是", "否"]
    selected = 0  # 默认选中"是"

    print(f"\n  ⚠️  检测到写入文件请求: {file_path}")
    print("  是否允许写入？")

    # 保存终端设置
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    def render_options():
        """渲染选项列表"""
        # 移动光标到选项区域开始，清除并重新渲染
        output = "\033[2K\r"  # 清除当前行并回到行首
        for i, option in enumerate(options):
            if i == selected:
                # 2空格 + > + 空格 = 4个字符到选项
                output += f"  \033[1;32m❯ {option}\033[0m"
            else:
                output += "    " + option  # 4个空格对齐
            output += "\n\033[2K\r"  # 换行并清除新行
        # 移动光标回到选项区域第一行
        output += f"\033[{len(options)}A"
        sys.stdout.write(output)
        sys.stdout.flush()

    try:
        # 设置终端为原始模式
        tty.setraw(fd)

        # 初始渲染 - 直接调用 render_options
        render_options()

        while True:
            ch = sys.stdin.read(1)

            if ch == '\x1b':  # ESC 序列（方向键）
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A':  # 上箭头
                        selected = (selected - 1) % len(options)
                        render_options()
                    elif ch3 == 'B':  # 下箭头
                        selected = (selected + 1) % len(options)
                        render_options()
            elif ch == '\r' or ch == '\n':  # Enter 键
                # 先下移到选项后面
                print(f"\033[{len(options)}B", end="")
                print()
                break
            elif ch == 'q' or ch == '\x03':  # q 或 Ctrl+C 取消
                print(f"\033[{len(options)}B", end="")  # 下移到选项后面
                print("\n  ✗ 已取消写入\n")
                return False

    finally:
        # 恢复终端设置
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    if selected == 0:
        print("  ✓ 已同意写入文件\n")
        return True
    else:
        print("  ✗ 已拒绝写入文件\n")
        return False


async def can_use_tool(tool_name: str, tool_args: Dict[str, Any], context: ToolPermissionContext) -> PermissionResultAllow | PermissionResultDeny:
    """权限回调函数，决定是否允许执行工具

    Args:
        tool_name: 工具名称
        tool_args: 工具参数
        context: 权限上下文

    Returns:
        PermissionResultAllow 或 PermissionResultDeny
    """
    # 检查是否是写入文件的操作
    if tool_name.lower() in ('write_file', 'write', 'mcp__write_file', 'mcp__write'):
        file_path = tool_args.get('file_path') or tool_args.get('path') or tool_args.get('filename')
        print(f"  写入文件: {file_path}")
        if file_path:
            if confirm_write(file_path):
                return PermissionResultAllow()
            else:
                return PermissionResultDeny(message="用户拒绝了写入请求")

    # 其他工具默认允许
    return PermissionResultAllow()


def execute_bash(command: str, timeout: int = DEFAULT_TIMEOUT) -> int:
    """执行 bash 命令并实时输出结果

    包含危险命令检测和超时控制。

    Args:
        command: 要执行的 bash 命令
        timeout: 超时时间（毫秒），默认 120000

    Returns:
        命令的退出码
    """
    # 检查危险命令
    is_dangerous, danger_reason = check_dangerous_command(command)
    if is_dangerous:
        print(f"\n\033[1;31m🚫 危险命令被阻止: {danger_reason}\033[0m")
        return 1

    # 检查需要确认的命令
    need_confirm, confirm_reason = check_confirm_command(command)
    if need_confirm:
        print(f"\n  ⚠️  检测到风险操作: {confirm_reason}")
        print(f"  命令: {command}")
        if not confirm_action("是否继续执行此命令？"):
            print("  ✗ 已取消执行\n")
            return 1

    print(f"\n\033[1;33m➜\033[0m {command}")
    print("\033[90m" + "─" * 60 + "\033[0m")

    # 使用新的执行函数
    result = execute_bash_streaming(command, timeout)

    print("\033[90m" + "─" * 60 + "\033[0m")

    if result.timed_out:
        print(f"\033[1;31m⏱️ {result.error}\033[0m")
    elif result.exit_code == 0:
        print(f"\033[90m退出码: {result.exit_code}\033[0m")
    else:
        print(f"\033[1;31m退出码: {result.exit_code}\033[0m")

    return result.exit_code


def confirm_action(prompt: str) -> bool:
    """确认操作，支持上下键选择

    Args:
        prompt: 提示信息

    Returns:
        bool: True 表示同意，False 表示拒绝
    """
    options = ["是", "否"]
    selected = 0  # 默认选中"是"

    print(f"\n  {prompt}")

    # 保存终端设置
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    def render_options():
        """渲染选项列表"""
        output = "\033[2K\r"
        for i, option in enumerate(options):
            if i == selected:
                output += f"  \033[1;32m❯ {option}\033[0m"
            else:
                output += "    " + option
            output += "\n\033[2K\r"
        output += f"\033[{len(options)}A"
        sys.stdout.write(output)
        sys.stdout.flush()

    try:
        tty.setraw(fd)
        render_options()

        while True:
            ch = sys.stdin.read(1)

            if ch == '\x1b':
                ch2 = sys.stdin.read(1)
                if ch2 == '[':
                    ch3 = sys.stdin.read(1)
                    if ch3 == 'A':
                        selected = (selected - 1) % len(options)
                        render_options()
                    elif ch3 == 'B':
                        selected = (selected + 1) % len(options)
                        render_options()
            elif ch == '\r' or ch == '\n':
                print(f"\033[{len(options)}B", end="")
                print()
                break
            elif ch == 'q' or ch == '\x03':
                print(f"\033[{len(options)}B", end="")
                return False

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return selected == 0