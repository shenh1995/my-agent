"""命令定义和处理功能"""

from typing import Dict, List, Optional
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit import PromptSession
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import HSplit, Window, FloatContainer, Float
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import FormattedText
from claude_agent_sdk import query, ClaudeAgentOptions

from . import get_startup_cwd


# 定义内置斜杠命令
BUILTIN_SLASH_COMMANDS: Dict[str, str] = {
    "/clear": "清除对话历史，开始新对话",
    "/compact": "压缩对话历史，保留重要上下文",
    "/rewind": "回滚对话到之前的某个状态",
    "/reload": "重新加载项目指令 (CLAUDE.md)",
}

# 动态 skill 命令（从配置文件加载）
SKILL_COMMANDS: Dict[str, str] = {}

# 完整的斜杠命令列表（内置 + skills）
SLASH_COMMANDS: Dict[str, str] = BUILTIN_SLASH_COMMANDS.copy()

# 定义其他可用命令（用于非斜杠命令的补全）
REGULAR_COMMANDS: Dict[str, str] = {
    "quit": "退出程序",
    "exit": "退出程序",
    "q": "退出程序",
    "clear": "清空屏幕",
    "help": "显示帮助信息",
    "version": "显示版本信息",
}


def update_slash_commands_with_skills(skill_commands: Dict[str, str]):
    """用 skills 更新斜杠命令列表

    Args:
        skill_commands: skill 名称到描述的字典，格式为 {"/skill_name": "description"}
    """
    global SKILL_COMMANDS, SLASH_COMMANDS
    SKILL_COMMANDS = skill_commands.copy()
    # 合并内置命令和 skill 命令
    SLASH_COMMANDS = BUILTIN_SLASH_COMMANDS.copy()
    SLASH_COMMANDS.update(SKILL_COMMANDS)


class CommandCompleter(Completer):
    """自定义命令补全器"""

    def get_completions(self, document, complete_event):
        """获取补全建议"""
        text = document.text_before_cursor

        # 斜杠命令补全
        if text.startswith('/'):
            for cmd, desc in SLASH_COMMANDS.items():
                if cmd.startswith(text):
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=f"{cmd}",
                        display_meta=desc,
                    )
        # 普通命令补全（仅当输入是命令开头时）
        elif not ' ' in text and text:
            for cmd, desc in REGULAR_COMMANDS.items():
                if cmd.startswith(text.lower()):
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=f"{cmd}",
                        display_meta=desc,
                    )


async def handle_clear_command(options: ClaudeAgentOptions, prompt_stream_factory) -> bool:
    """处理 /clear 命令

    Args:
        options: 当前配置选项
        prompt_stream_factory: 创建 prompt stream 的工厂函数

    Returns:
        是否需要重置会话
    """
    print("\n  正在清除对话历史...")

    clear_options = ClaudeAgentOptions(
        permission_mode=options.permission_mode,
        cwd=get_startup_cwd(),
        allowed_tools=options.allowed_tools,
        mcp_servers=options.mcp_servers,
        max_turns=1,
    )

    clear_done = False
    prompt_stream = prompt_stream_factory("/clear")
    async for message in query(prompt=prompt_stream, options=clear_options):
        if clear_done:
            continue
        message_type = type(message).__name__
        if message_type == 'SystemMessage':
            if hasattr(message, 'subtype') and message.subtype == 'init':
                print(f"\n  ✓ 对话已清除，新会话已开始")
                if hasattr(message, 'session_id') and message.session_id:
                    print(f"  会话 ID: {message.session_id}\n")
                else:
                    print()
                clear_done = True

    if not clear_done:
        print("\n  ✓ 已清除对话历史\n")

    return True


async def handle_compact_command(options: ClaudeAgentOptions, prompt_stream_factory):
    """处理 /compact 命令

    Args:
        options: 当前配置选项
        prompt_stream_factory: 创建 prompt stream 的工厂函数
    """
    print("\n  正在压缩对话历史...")

    compact_options = ClaudeAgentOptions(
        permission_mode=options.permission_mode,
        cwd=get_startup_cwd(),
        allowed_tools=options.allowed_tools,
        mcp_servers=options.mcp_servers,
        max_turns=1,
    )

    compact_done = False
    prompt_stream = prompt_stream_factory("/compact")
    async for message in query(prompt=prompt_stream, options=compact_options):
        if compact_done:
            continue
        message_type = type(message).__name__
        if message_type == 'SystemMessage':
            if hasattr(message, 'subtype') and message.subtype == 'compact_boundary':
                print(f"\n  ✓ 对话历史已压缩")
                if hasattr(message, 'compact_metadata') and message.compact_metadata:
                    metadata = message.compact_metadata
                    if hasattr(metadata, 'pre_tokens'):
                        print(f"  压缩前 token 数: {metadata.pre_tokens}")
                print()
                compact_done = True

    if not compact_done:
        print("\n  ✓ 对话历史压缩完成\n")


class CheckpointManager:
    """检查点管理器，用于管理对话历史和代码状态"""

    def __init__(self, work_dir: str = "."):
        self.checkpoints: List[Dict] = []
        self.file_snapshots: Dict[str, Dict[int, str]] = {}  # {file_path: {checkpoint_id: content}}
        self.work_dir = work_dir
        self.initial_files: set = set()  # 初始存在的文件集合
        self.files_at_checkpoint: Dict[int, set] = {}  # 每个检查点时刻存在的文件

    def set_work_dir(self, work_dir: str):
        """设置工作目录"""
        self.work_dir = work_dir

    def scan_files(self) -> Dict[str, str]:
        """扫描工作目录中的所有文件并返回其内容"""
        import os
        result = {}
        work_path = os.path.abspath(self.work_dir)

        if not os.path.exists(work_path):
            return result

        for root, dirs, files in os.walk(work_path):
            # 跳过隐藏目录和常见的忽略目录
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.git']]

            for file in files:
                if file.startswith('.'):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    result[file_path] = content
                except (UnicodeDecodeError, IOError):
                    # 跳过二进制文件或无法读取的文件
                    pass
        return result

    def capture_file_state(self) -> Dict[str, str]:
        """捕获当前文件状态"""
        return self.scan_files()

    def add_checkpoint(self, checkpoint_id: int, user_prompt: str, file_states: Optional[Dict[str, str]] = None):
        """添加一个检查点

        Args:
            checkpoint_id: 检查点ID
            user_prompt: 用户的提示内容
            file_states: 文件状态字典 {file_path: content}，如果不提供则自动捕获
        """
        # 如果没有提供文件状态，自动捕获
        if file_states is None:
            file_states = self.capture_file_state()

        self.checkpoints.append({
            'id': checkpoint_id,
            'prompt': user_prompt,
            'timestamp': __import__('time').time(),
        })

        # 记录这个检查点时刻存在的文件
        self.files_at_checkpoint[checkpoint_id] = set(file_states.keys())

        # 如果是第一个检查点，记录初始文件集合
        if not self.initial_files:
            self.initial_files = set(file_states.keys())

        # 保存文件快照
        if file_states:
            for file_path, content in file_states.items():
                if file_path not in self.file_snapshots:
                    self.file_snapshots[file_path] = {}
                self.file_snapshots[file_path][checkpoint_id] = content

    def get_checkpoints(self) -> List[Dict]:
        """获取所有检查点"""
        return self.checkpoints

    def get_checkpoint_by_index(self, index: int) -> Optional[Dict]:
        """通过索引获取检查点"""
        if 0 <= index < len(self.checkpoints):
            return self.checkpoints[index]
        return None

    def get_file_state_at_checkpoint(self, checkpoint_id: int) -> Dict[str, str]:
        """获取指定检查点的文件状态"""
        result = {}
        for file_path, snapshots in self.file_snapshots.items():
            # 找到小于等于 checkpoint_id 的最新快照
            available_ids = [cid for cid in snapshots.keys() if cid <= checkpoint_id]
            if available_ids:
                latest_id = max(available_ids)
                result[file_path] = snapshots[latest_id]
        return result

    def get_files_at_checkpoint(self, checkpoint_id: int) -> set:
        """获取指定检查点时刻存在的文件集合"""
        return self.files_at_checkpoint.get(checkpoint_id, set())

    def truncate_after_checkpoint(self, checkpoint_index: int):
        """截断指定索引之后的检查点"""
        # 删除之后的检查点
        removed_checkpoints = self.checkpoints[checkpoint_index + 1:]
        self.checkpoints = self.checkpoints[:checkpoint_index + 1]

        # 删除对应的文件快照
        removed_ids = [cp['id'] for cp in removed_checkpoints]
        for file_path in self.file_snapshots:
            for removed_id in removed_ids:
                self.file_snapshots[file_path].pop(removed_id, None)

    def clear(self):
        """清除所有检查点"""
        self.checkpoints = []
        self.file_snapshots = {}

    def __len__(self):
        return len(self.checkpoints)


# 选择器样式
SELECTOR_STYLE = Style.from_dict({
    'title': 'ansicyan bold',
    'selected': 'ansigreen bold',
    'unselected': 'ansidefault',
    'hint': 'ansibrightblack',
    'pointer': 'ansigreen bold',
})


def create_selector_app(items: List[Dict], title: str) -> Application:
    """创建一个交互式选择器应用

    Args:
        items: 选择项列表，每项包含 'text' 和可选的 'description'
        title: 标题文本

    Returns:
        prompt_toolkit Application 对象
    """
    selected_index = [0]  # 使用列表以便在闭包中修改

    def get_text():
        """生成显示文本"""
        result = []
        result.append(('', '\n'))
        result.append(('class:title', f'  {title}\n'))
        result.append(('', '\n'))

        for i, item in enumerate(items):
            if i == selected_index[0]:
                result.append(('class:pointer', '  ❯ '))
                result.append(('class:selected', item['text']))
            else:
                result.append(('class:unselected', '    '))
                result.append(('class:unselected', item['text']))

            # 添加描述（如果有）
            if 'description' in item:
                result.append(('', '\n'))
                if i == selected_index[0]:
                    result.append(('class:hint', f'      {item["description"]}'))
                else:
                    result.append(('class:hint', f'      {item["description"]}'))

            result.append(('', '\n'))

        result.append(('', '\n'))
        result.append(('class:hint', '  ↑/↓ 选择  Enter 确认  Esc 取消'))
        return result

    kb = KeyBindings()

    @kb.add('up')
    def _(event):
        selected_index[0] = max(0, selected_index[0] - 1)

    @kb.add('down')
    def _(event):
        selected_index[0] = min(len(items) - 1, selected_index[0] + 1)

    @kb.add('enter')
    def _(event):
        event.app.exit(result=selected_index[0])

    @kb.add('escape')
    def _(event):
        event.app.exit(result=None)

    @kb.add('c-c')
    def _(event):
        event.app.exit(result=None)

    layout = Layout(
        HSplit([
            Window(
                content=FormattedTextControl(get_text),
                always_hide_cursor=True,
            ),
        ])
    )

    return Application(
        layout=layout,
        key_bindings=kb,
        style=SELECTOR_STYLE,
        full_screen=False,
    )


async def display_rewind_menu(checkpoints: List[Dict]) -> Optional[int]:
    """显示回滚菜单并获取用户选择（使用箭头键导航）

    Args:
        checkpoints: 检查点列表

    Returns:
        选择的检查点索引，或 None 表示取消
    """
    if not checkpoints:
        print("\n  \033[90m没有可用的检查点\033[0m\n")
        return None

    # 准备选择项
    items = []
    for i, cp in enumerate(checkpoints):
        prompt_text = cp['prompt']
        # 截断过长的提示
        if len(prompt_text) > 60:
            prompt_text = prompt_text[:57] + "..."

        # 获取时间戳信息
        timestamp = cp.get('timestamp', 0)
        if timestamp:
            from datetime import datetime
            time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S')
            desc = f"时间: {time_str}"
        else:
            desc = f"检查点 #{i + 1}"

        items.append({
            'text': prompt_text,
            'description': desc,
        })

    # 添加取消选项
    items.append({
        'text': '取消',
        'description': '不进行任何操作',
    })

    app = create_selector_app(items, '选择要恢复的检查点')

    try:
        result = await app.run_async()

        if result is None or result == len(items) - 1:
            return None

        return result
    except KeyboardInterrupt:
        return None


async def display_rewind_action_menu() -> Optional[str]:
    """显示操作菜单并获取用户选择（使用箭头键导航）

    Returns:
        选择的操作类型: 'restore_both', 'restore_conversation', 'restore_code', 'summarize', None
    """
    items = [
        {
            'text': '恢复对话和代码',
            'description': '回滚对话历史并恢复该点的代码状态',
            'value': 'restore_both',
        },
        {
            'text': '仅恢复对话',
            'description': '回滚对话历史，保留当前代码',
            'value': 'restore_conversation',
        },
        {
            'text': '仅恢复代码',
            'description': '恢复该点的代码状态，保留对话历史',
            'value': 'restore_code',
        },
        {
            'text': '从此处压缩',
            'description': '将该点之后的对话压缩为摘要',
            'value': 'summarize',
        },
        {
            'text': '取消',
            'description': '不进行任何操作',
            'value': None,
        },
    ]

    app = create_selector_app(items, '选择操作')

    try:
        result = await app.run_async()

        if result is None or result == len(items) - 1:
            return None

        return items[result]['value']
    except KeyboardInterrupt:
        return None


async def handle_rewind_command(
    checkpoint_manager: CheckpointManager,
    options: ClaudeAgentOptions,
    prompt_stream_factory,
    on_restore_callback=None
) -> Dict:
    """处理 /rewind 命令

    Args:
        checkpoint_manager: 检查点管理器
        options: 当前配置选项
        prompt_stream_factory: 创建 prompt stream 的工厂函数
        on_restore_callback: 恢复时的回调函数，用于通知 cli.py 更新状态

    Returns:
        包含操作结果的字典:
        - action: 执行的操作
        - checkpoint_index: 检查点索引
        - should_reset_conversation: 是否需要重置会话
        - restored_prompt: 恢复的提示内容（如果有）
    """
    checkpoints = checkpoint_manager.get_checkpoints()

    # 显示检查点选择菜单
    selected_index = await display_rewind_menu(checkpoints)

    if selected_index is None:
        return {'action': 'cancel'}

    selected_checkpoint = checkpoints[selected_index]

    # 显示操作选择菜单
    action = await display_rewind_action_menu()

    if action is None or action == 'cancel':
        print("\n  \033[90m已取消\033[0m\n")
        return {'action': 'cancel'}

    result = {
        'action': action,
        'checkpoint_index': selected_index,
        'restored_prompt': selected_checkpoint['prompt'],
    }

    if action == 'restore_both':
        # 恢复对话和代码
        print(f"\n  \033[90m正在恢复到检查点 {selected_index + 1}...\033[0m")

        # 截断检查点历史
        checkpoint_manager.truncate_after_checkpoint(selected_index)

        # 获取该检查点的文件状态和文件列表
        file_states = checkpoint_manager.get_file_state_at_checkpoint(selected_checkpoint['id'])
        files_at_checkpoint = checkpoint_manager.get_files_at_checkpoint(selected_checkpoint['id'])

        result['should_reset_conversation'] = True
        result['file_states'] = file_states

        # 恢复文件内容
        import os
        restored_count = 0
        for file_path, content in file_states.items():
            try:
                # 确保目录存在
                dir_path = os.path.dirname(file_path)
                if dir_path and not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                restored_count += 1
            except Exception as e:
                print(f"  \033[1;31m警告: 无法恢复 {file_path}: {e}\033[0m")

        # 删除检查点之后新创建的文件
        deleted_count = 0
        current_files = set(checkpoint_manager.scan_files().keys())
        for file_path in current_files - files_at_checkpoint:
            try:
                os.remove(file_path)
                deleted_count += 1
                # 尝试删除空目录
                dir_path = os.path.dirname(file_path)
                if dir_path and dir_path != checkpoint_manager.work_dir:
                    try:
                        os.removedirs(dir_path)
                    except OSError:
                        pass  # 目录不为空，忽略
            except Exception as e:
                print(f"  \033[1;31m警告: 无法删除 {file_path}: {e}\033[0m")

        print(f"\n  ✓ 已恢复到检查点 {selected_index + 1}")
        print(f"  提示: {selected_checkpoint['prompt'][:50]}...")
        if restored_count > 0:
            print(f"  恢复了 {restored_count} 个文件")
        if deleted_count > 0:
            print(f"  删除了 {deleted_count} 个新创建的文件")
        print()

        # 调用回调通知状态更新
        if on_restore_callback:
            await on_restore_callback(action, result)

    elif action == 'restore_conversation':
        # 仅恢复对话
        print(f"\n  \033[90m正在回滚对话历史...\033[0m")

        checkpoint_manager.truncate_after_checkpoint(selected_index)

        result['should_reset_conversation'] = True

        print(f"\n  ✓ 对话已回滚到检查点 {selected_index + 1}")
        print(f"  提示: {selected_checkpoint['prompt'][:50]}...\n")

        if on_restore_callback:
            await on_restore_callback(action, result)

    elif action == 'restore_code':
        # 仅恢复代码
        print(f"\n  \033[90m正在恢复代码状态...\033[0m")

        file_states = checkpoint_manager.get_file_state_at_checkpoint(selected_checkpoint['id'])

        result['file_states'] = file_states

        # 写入文件
        restored_count = 0
        for file_path, content in file_states.items():
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                restored_count += 1
            except Exception as e:
                print(f"  \033[1;31m警告: 无法恢复 {file_path}: {e}\033[0m")

        print(f"\n  ✓ 已恢复 {restored_count} 个文件")
        print(f"  注意: 对话历史保持不变\n")

        if on_restore_callback:
            await on_restore_callback(action, result)

    elif action == 'summarize':
        # 从该点压缩对话
        print(f"\n  \033[90m正在压缩对话...\033[0m")

        # 使用 SDK 的 compact 功能
        compact_options = ClaudeAgentOptions(
            permission_mode=options.permission_mode,
            cwd=options.cwd,
            allowed_tools=options.allowed_tools,
            mcp_servers=options.mcp_servers,
            max_turns=1,
        )

        compact_done = False
        prompt_stream = prompt_stream_factory("/compact")
        async for message in query(prompt=prompt_stream, options=compact_options):
            if compact_done:
                continue
            message_type = type(message).__name__
            if message_type == 'SystemMessage':
                if hasattr(message, 'subtype') and message.subtype == 'compact_boundary':
                    compact_done = True

        if compact_done:
            print(f"\n  ✓ 对话已从检查点 {selected_index + 1} 开始压缩\n")
        else:
            print("\n  ✓ 对话压缩完成\n")

        result['should_compact'] = True

        if on_restore_callback:
            await on_restore_callback(action, result)

    return result