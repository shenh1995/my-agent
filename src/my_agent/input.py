"""输入处理功能"""

import os
import base64
import mimetypes
from collections.abc import AsyncIterable
from typing import Any

from prompt_toolkit import Application, PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.layout.containers import Window, HSplit, WindowAlign
from prompt_toolkit.layout.controls import FormattedTextControl, BufferControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.styles import Style

from .commands import CommandCompleter
from .ui import CUSTOM_STYLE
from .image import is_image_file, encode_image_to_base64
from .plan_mode import toggle_plan_mode, is_plan_mode


# 全局变量，用于防止无限循环
_transforming = False

# 会话内的图片计数器和映射
_image_counter = 0
_image_path_map = {}  # {image_number: image_path}


def reset_image_counter():
    """重置图片计数器（新会话时调用）"""
    global _image_counter, _image_path_map
    _image_counter = 0
    _image_path_map = {}


def add_image(path: str) -> int:
    """添加图片并返回编号

    Args:
        path: 图片路径

    Returns:
        图片编号
    """
    global _image_counter, _image_path_map
    _image_counter += 1
    _image_path_map[_image_counter] = path
    return _image_counter


def get_image_path(image_number: int) -> str:
    """获取图片路径

    Args:
        image_number: 图片编号

    Returns:
        图片路径
    """
    return _image_path_map.get(image_number, "")


def get_image_count() -> int:
    """获取当前图片数量

    Returns:
        图片数量
    """
    return _image_counter


def format_image_display(image_number: int) -> str:
    """格式化图片显示文本

    Args:
        image_number: 图片编号

    Returns:
        格式化的显示文本，如 [image1]
    """
    return f"[image{image_number}]"


def create_key_bindings_with_image_support():
    """创建支持图片路径转换的键绑定"""
    kb = KeyBindings()

    @kb.add('enter')
    def _(event):
        """Enter 提交输入"""
        event.current_buffer.validate_and_handle()

    @kb.add('c-j')
    def _(event):
        """Ctrl+J 插入换行"""
        event.current_buffer.insert_text('\n')

    @kb.add('s-tab')  # Shift+Tab
    def _(event):
        """Shift+Tab 切换 Plan Mode"""
        toggle_plan_mode()
        # 触发界面刷新以更新底部工具栏
        event.app.invalidate()

    return kb


def create_text_changed_handler(session):
    """创建文本变化处理函数"""
    def handler(buffer):
        global _transforming

        if _transforming:
            return

        text = buffer.text
        if not text:
            return

        # 移除可能的引号和空白
        stripped = text.strip()
        path_to_check = stripped

        if path_to_check.startswith("'") and path_to_check.endswith("'"):
            path_to_check = path_to_check[1:-1]
        elif path_to_check.startswith('"') and path_to_check.endswith('"'):
            path_to_check = path_to_check[1:-1]

        # 检查是否是图片文件
        if os.path.isfile(path_to_check) and is_image_file(path_to_check):
            # 添加图片并获取编号
            image_number = add_image(path_to_check)
            formatted = format_image_display(image_number)
            if text != formatted:
                _transforming = True
                try:
                    # 替换文本并移动光标到末尾
                    buffer.text = formatted
                    buffer.cursor_position = len(formatted)
                finally:
                    _transforming = False

    return handler


async def create_prompt_stream(prompt_text: str) -> AsyncIterable[dict[str, Any]]:
    """将字符串 prompt 转换为 AsyncIterable 格式，用于 streaming 模式。

    支持多模态消息，包括文本和图片。

    Args:
        prompt_text: 用户输入的提示文本，可能包含 [imageN] 标签

    Yields:
        格式化的用户消息字典
    """
    import re

    # 用于存储图片的 base64 数据
    image_data_map = {}  # {image_num: (base64_data, mime_type)}

    # 解析文本中的图片标签和普通文本
    content_blocks = []
    image_pattern = r'\[image(\d+)\]'

    # 分割文本，保留图片标签的位置
    last_end = 0
    for match in re.finditer(image_pattern, prompt_text):
        # 添加图片标签前的文本
        text_before = prompt_text[last_end:match.start()].strip()
        if text_before:
            content_blocks.append({"type": "text", "text": text_before})

        # 获取图片编号并添加图片内容块
        image_num = int(match.group(1))
        image_path = get_image_path(image_num)
        if image_path and os.path.exists(image_path):
            # 读取图片并编码为 base64，存储在内存中
            base64_data, mime_type = encode_image_to_base64(image_path)
            image_data_map[image_num] = (base64_data, mime_type)
            # 使用 Anthropic API 标准格式
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": base64_data
                }
            })
        else:
            # 如果图片路径无效，保留原始标签作为文本
            content_blocks.append({"type": "text", "text": match.group(0)})

        last_end = match.end()

    # 添加最后剩余的文本
    remaining_text = prompt_text[last_end:].strip()
    if remaining_text:
        content_blocks.append({"type": "text", "text": remaining_text})

    # 如果没有内容块，使用原始文本
    if not content_blocks:
        content_blocks = [{"type": "text", "text": prompt_text}]

    message = {
        "type": "user",
        "message": {"role": "user", "content": content_blocks},
        "parent_tool_use_id": None,
        "session_id": "",
    }

    yield message


def _get_bottom_toolbar():
    """获取底部工具栏内容，显示 Plan Mode 状态"""
    if is_plan_mode():
        return HTML('<style fg="ansicyan">📋 Plan Mode 已启用 - 只读探索模式</style>')
    # 非 Plan Mode 时返回 None，完全不显示工具栏
    return None


def create_session() -> PromptSession:
    """创建 prompt_toolkit 会话

    Returns:
        配置好的 PromptSession 实例
    """
    kb = create_key_bindings_with_image_support()

    session = PromptSession(
        completer=CommandCompleter(),
        style=CUSTOM_STYLE,
        complete_while_typing=True,
        history=InMemoryHistory(),
        key_bindings=kb,
        multiline=True,
        bottom_toolbar=_get_bottom_toolbar,
        include_default_pygments_style=False,
    )

    # 注册文本变化事件处理
    handler = create_text_changed_handler(session)
    session.default_buffer.on_text_changed += handler

    return session


def print_separator():
    """打印灰色分割线"""
    import os
    from prompt_toolkit import print_formatted_text
    from prompt_toolkit.formatted_text import FormattedText
    try:
        terminal_width = os.get_terminal_size().columns
    except OSError:
        terminal_width = 80
    print_formatted_text(FormattedText([("fg:ansibrightblack", "─" * terminal_width)]))


def get_bottom_separator_rprompt():
    """获取下方分割线作为 rprompt"""
    import os
    from prompt_toolkit.formatted_text import FormattedText
    try:
        terminal_width = os.get_terminal_size().columns
    except OSError:
        terminal_width = 80
    # 返回分割线作为 rprompt
    return FormattedText([
        ("", "\n"),
        ("fg:ansibrightblack", "─" * terminal_width),
    ])


# 分割线样式
SEPARATOR_STYLE = Style.from_dict({
    'separator': 'ansibrightblack',
})


def get_terminal_width() -> int:
    """获取终端宽度"""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


class BorderedInputApp:
    """带分割线边框的输入应用"""

    def __init__(self, session: PromptSession):
        self.session = session
        self.result = None
        self._buffer = None
        self._completer = None

    async def run_async(self) -> str:
        """运行输入应用并返回用户输入"""
        from prompt_toolkit.widgets import HorizontalLine

        # 创建按键绑定
        kb = KeyBindings()

        @kb.add('enter')
        def _(event):
            """Enter 提交输入"""
            buffer = event.app.current_buffer
            text = buffer.text
            self.result = text
            event.app.exit(result=text)

        @kb.add('c-j')
        def _(event):
            """Ctrl+J 插入换行"""
            event.current_buffer.insert_text('\n')

        @kb.add('s-tab')
        def _(event):
            """Shift+Tab 切换 Plan Mode"""
            toggle_plan_mode()
            event.app.invalidate()

        @kb.add('c-c')
        def _(event):
            """Ctrl+C 退出"""
            event.app.exit(exception=KeyboardInterrupt)

        @kb.add('tab')
        def _(event):
            """Tab 触发补全"""
            buffer = event.app.current_buffer
            completer = self._completer
            if completer:
                document = buffer.document
                completions = list(completer.get_completions(document, None))
                if completions:
                    completion = completions[0]
                    buffer.delete_before_cursor(-completion.start_position)
                    buffer.insert_text(completion.text)

        # 创建缓冲区
        self._completer = CommandCompleter()
        buffer = Buffer(
            history=self.session.history,
            completer=self._completer,
        )
        self._buffer = buffer

        # 注册文本变化事件处理（支持图片路径自动转换）
        text_changed_handler = create_text_changed_handler(self.session)
        buffer.on_text_changed += text_changed_handler

        # 布局
        root_container = HSplit([
            HorizontalLine(),  # 上方分割线
            Window(
                content=BufferControl(
                    buffer=buffer,
                    include_default_input_processors=True,
                ),
                height=1,
                get_line_prefix=lambda line_number, wrap_count: "❯ ",
            ),
            HorizontalLine(),  # 下方分割线
        ])

        # 创建应用
        app = Application(
            layout=Layout(root_container),
            key_bindings=kb,
            full_screen=False,
            mouse_support=True,
        )

        # 运行应用
        await app.run_async()

        return self.result or ""


async def prompt_with_borders(session: PromptSession, prompt_text: str = "❯ ") -> str:
    """显示带分割线边框的输入提示

    Args:
        session: PromptSession 实例（用于共享历史等）
        prompt_text: 提示文本（未使用，保留兼容性）

    Returns:
        用户输入的文本
    """
    app = BorderedInputApp(session)
    return await app.run_async()