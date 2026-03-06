"""UI 显示功能"""

import os
import sys
from datetime import datetime
from prompt_toolkit.styles import Style
from prompt_toolkit.key_binding import KeyBindings


# 自定义样式
CUSTOM_STYLE = Style.from_dict({
    'prompt': 'ansicyan bold',
    'completion': 'ansigreen',
    'completion.meta': 'ansibrightblack',
    'bottom-toolbar': 'noinherit',  # 透明背景
})


def create_key_bindings() -> KeyBindings:
    """创建自定义键绑定：Enter 提交，Ctrl+J 换行"""
    kb = KeyBindings()

    @kb.add('enter')
    def _(event):
        """Enter 提交输入"""
        event.current_buffer.validate_and_handle()

    @kb.add('c-j')  # Ctrl+J 插入换行
    def _(event):
        """Ctrl+J 插入换行"""
        event.current_buffer.insert_text('\n')

    return kb


def print_banner():
    """打印启动界面，类似 Claude Code CLI 的风格"""
    # 获取终端宽度，默认 80
    try:
        terminal_width = os.get_terminal_size().columns
    except OSError:
        terminal_width = 80

    # 当前工作目录
    cwd = os.getcwd()

    # 获取 Python 版本
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # 当前日期
    today = datetime.now().strftime("%Y-%m-%d")

    # 构建启动信息
    lines = []
    lines.append("")
    lines.append("╭────────────────────────────────────────────────────────────────────╮")
    lines.append("│                                                                    │")
    lines.append("│   ██████╗██╗      ██╗  ██╗   ██╗██╗███╗   ██╗ ██████╗             │")
    lines.append("│  ██╔════╝██║      ██║  ██║   ██║██║████╗  ██║██╔════╝             │")
    lines.append("│  ██║     ██║      ██║  ██║   ██║██║██╔██╗ ██║██║  ███╗            │")
    lines.append("│  ██║     ██║      ██║  ╚██╗ ██╔╝██║██║╚██╗██║██║   ██║            │")
    lines.append("│  ╚██████╗██║      ██║   ╚████╔╝ ██║██║ ╚████║╚██████╔╝            │")
    lines.append("│   ╚═════╝╚═╝      ╚═╝    ╚═══╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝             │")
    lines.append("│                                                                    │")
    lines.append("│                    Agent SDK - Interactive Mode                   │")
    lines.append("│                                                                    │")
    lines.append("╰────────────────────────────────────────────────────────────────────╯")
    lines.append("")
    lines.append(f"  当前目录: {cwd}")
    lines.append(f"  Python 版本: {python_version}")
    lines.append(f"  日期: {today}")
    lines.append("")
    lines.append("  ─────────────────────────────────────────────────────────────────")
    lines.append("")
    lines.append("  提示:")
    lines.append("    • 输入 quit 或 exit 退出")
    lines.append("    • 输入 clear 清屏")
    lines.append("    • 输入 help 查看帮助")
    lines.append("    • Ctrl+J 换行（多行输入）")
    lines.append("")
    lines.append("  ─────────────────────────────────────────────────────────────────")
    lines.append("")

    # 打印所有行
    for line in lines:
        print(line)


def clear_screen():
    """清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_help():
    """打印帮助信息"""
    print("")
    print("  可用命令:")
    print("    quit, exit, q  - 退出程序")
    print("    clear          - 清空屏幕")
    print("    /clear         - 清除对话历史，开始新对话")
    print("    /compact       - 压缩对话历史，保留重要上下文")
    print("    help           - 显示此帮助信息")
    print("    version        - 显示版本信息")
    print("    !<command>     - 执行 bash 命令 (例: !ls -la)")
    print("")
    print("  快捷键:")
    print("    Enter          - 发送消息")
    print("    Ctrl+J         - 换行（多行输入）")
    print("    Shift+Tab      - 切换 Plan Mode（只读探索模式）")
    print("")
    print("  Plan Mode:")
    print("    在 Plan Mode 下，Agent 将使用只读工具探索代码库，")
    print("    生成实施计划供您审批，批准后才会执行。")
    print("")
    print("  配置:")
    print("    权限模式: bypassPermissions")
    print(f"    工作目录: {os.getcwd()}")
    print("    允许工具: bash, read_file, write_file")
    print("")


def print_version():
    """打印版本信息"""
    print(f"\n  Claude Agent SDK v1.0.0")
    print(f"  Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print("")


def print_plan_mode_status(is_active: bool):
    """打印 Plan Mode 状态提示

    Args:
        is_active: True 表示 Plan Mode 已启用
    """
    if is_active:
        print("\n  📋 Plan Mode 已启用")
        print("  只读探索模式 - 生成计划后需批准执行")
        print("  可用工具: read_file, list_directory, glob, grep")
        print("  按 Shift+Tab 退出 Plan Mode\n")
    else:
        print("\n  ✓ Plan Mode 已关闭，恢复正常模式\n")


def print_goodbye():
    """打印告别信息"""
    print("\n  👋 再见！感谢使用 Claude Agent SDK。\n")