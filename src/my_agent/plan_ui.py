"""Plan Mode 审批 UI

提供计划审批界面，让用户可以：
- 查看生成的计划
- 批准执行
- 取消操作
"""

from typing import Optional
from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from .commands import create_selector_app


# 计划审批样式
PLAN_STYLE = Style.from_dict({
    'title': 'ansicyan bold',
    'plan': 'ansidefault',
    'selected': 'ansigreen bold',
    'unselected': 'ansidefault',
    'hint': 'ansibrightblack',
    'pointer': 'ansigreen bold',
    'header': 'ansiyellow bold',
})


def format_plan_display(plan_content: str, max_width: int = 80) -> list:
    """格式化计划显示

    Args:
        plan_content: 计划内容
        max_width: 最大宽度

    Returns:
        格式化的文本块列表
    """
    result = []

    # 分行处理
    lines = plan_content.split('\n')

    result.append(('class:title', '\n  📋 生成的计划\n'))
    result.append(('', '  ' + '─' * (max_width - 4) + '\n'))

    for line in lines:
        # 处理每行
        if line.startswith('#'):
            result.append(('class:header', f'  {line}\n'))
        elif line.strip().startswith('-') or line.strip().startswith('*'):
            result.append(('class:plan', f'  {line}\n'))
        elif line.strip().startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
            result.append(('class:plan', f'  {line}\n'))
        else:
            result.append(('', f'  {line}\n'))

    result.append(('', '  ' + '─' * (max_width - 4) + '\n'))

    return result


async def display_plan_approval(plan_content: str) -> str:
    """展示计划并获取用户审批

    Args:
        plan_content: 计划内容

    Returns:
        "approve" - 批准执行
        "edit" - 编辑计划（暂未实现）
        "cancel" - 取消
    """
    # 先打印计划内容
    print("\n" + "═" * 60)
    print("📋 生成的计划")
    print("═" * 60)
    print()
    print(plan_content)
    print()
    print("═" * 60)

    # 显示选择菜单
    items = [
        {
            'text': '批准并执行',
            'description': '批准此计划并开始执行',
            'value': 'approve',
        },
        {
            'text': '取消',
            'description': '取消计划，返回 Plan Mode',
            'value': 'cancel',
        },
    ]

    app = create_selector_app(items, '请选择操作')

    try:
        result = await app.run_async()

        if result is None:
            return 'cancel'

        return items[result]['value']

    except KeyboardInterrupt:
        return 'cancel'


async def display_plan_mode_welcome():
    """显示 Plan Mode 欢迎信息"""
    print("\n" + "─" * 60)
    print("  📋 Plan Mode 已启用")
    print("─" * 60)
    print()
    print("  在此模式下，Agent 将：")
    print("  1. 使用只读工具探索代码库")
    print("  2. 生成详细的实施计划")
    print("  3. 等待您审批后执行")
    print()
    print("  可用工具：read_file, list_directory, glob, grep")
    print("  不可用工具：write_file, edit_file, bash")
    print()
    print("  输入任务开始探索，或按 Shift+Tab 退出 Plan Mode")
    print("─" * 60)
    print()


async def display_plan_mode_exit():
    """显示 Plan Mode 退出信息"""
    print("\n  ✓ Plan Mode 已关闭，恢复正常模式\n")


def print_plan_saved(file_path: str):
    """打印计划已保存信息

    Args:
        file_path: 计划文件路径
    """
    print(f"\n  📄 计划已保存到: {file_path}\n")


def print_plan_approved():
    """打印计划已批准信息"""
    print("\n  ✓ 计划已批准，开始执行...\n")


def print_plan_cancelled():
    """打印计划已取消信息"""
    print("\n  ✗ 计划已取消\n")