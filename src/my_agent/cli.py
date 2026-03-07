"""Claude Agent SDK Interactive CLI Tool - 主入口"""

import os
import sys
import signal
import anyio
from dotenv import load_dotenv

# 加载 .env 文件
# 优先级：当前目录 > 安装目录 > 用户主目录
env_loaded = False
env_paths = [
    os.path.join(os.getcwd(), '.env'),  # 当前工作目录
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env'),  # 安装目录
    os.path.expanduser('~/.claude/my-agent/.env'),  # My Agent 配置目录
    os.path.expanduser('~/.claude/.env'),  # 用户主目录
]

for env_path in env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        env_loaded = True
        break

if not env_loaded:
    # 如果都没找到，尝试默认加载
    load_dotenv()

from claude_agent_sdk import query, ClaudeAgentOptions
from claude_agent_sdk.types import HookMatcher


from .commands import (
    SLASH_COMMANDS,
    handle_clear_command,
    handle_compact_command,
    handle_rewind_command,
    CheckpointManager,
    update_slash_commands_with_skills,
)
from . import get_startup_cwd
from .ui import (
    print_banner,
    clear_screen,
    print_help,
    print_version,
    print_goodbye,
)
from .permissions import execute_bash, can_use_tool
from .highlight import format_text_with_code
from .input import (
    create_prompt_stream,
    create_session,
    get_image_path,
    reset_image_counter,
    get_image_count,
    print_separator,
)
from .image import analyze_image, analyze_images
from .mcp import load_mcp_config, get_mcp_servers, get_all_tool_names
from .mcp.server import get_mcp_servers_read_only, get_read_only_tool_names
from .plan_mode import (
    is_plan_mode,
    get_plan_mode_state,
    get_plan_mode_system_prompt,
    set_plan_content,
    set_exploration_complete,
    is_exploration_complete,
    reset_plan_mode,
)
from .plan_ui import (
    display_plan_approval,
    print_plan_approved,
    print_plan_cancelled,
)
from .skills import get_skill_manager, Skill
from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import FormattedText


# 全局变量，用于标记是否应该退出
_should_exit = False


def signal_handler(signum, frame):
    """处理 Ctrl+C 信号"""
    global _should_exit
    _should_exit = True
    print_goodbye()
    sys.exit(0)


async def process_message(message, first_response: bool) -> bool:
    """处理接收到的消息

    Args:
        message: 接收到的消息
        first_response: 是否是第一条响应

    Returns:
        更新后的 first_response 状态
    """
    if first_response:
        # 清除思考指示器
        print(" " * 30, end="\r")
        first_response = False

    message_type = type(message).__name__

    if message_type == 'AssistantMessage':
        for block in message.content:
            block_type = type(block).__name__
            if block_type == 'TextBlock':
                formatted_text = format_text_with_code(block.text)
                print(f"\n\033[1;35mClaude:\033[0m {formatted_text}")
            elif block_type == 'ThinkingBlock':
                # 处理 ThinkingBlock 类型
                if hasattr(block, 'thinking'):
                    print(f"\n\033[90m[思考] {block.thinking}\033[0m")
            elif block_type == 'ToolUseBlock':
                # 调试信息：打印工具名称和所有属性
                print(f"\n\033[1;33m[工具调用] {block.name}\033[0m")
            elif block_type == 'ToolResultBlock':
                print(f"\n\033[90m[工具结果] {block.content}\033[0m")

    elif message_type == 'ResultMessage':
        if message.is_error:
            print(f"\n\033[1;31m[错误] 会话结束\033[0m")
        elif message.result:
            print(f"\n\033[1;32m[结果] {message.result}\033[0m")

    return first_response


async def run():
    """运行交互式 CLI"""
    # 注册 Ctrl+C 信号处理器
    signal.signal(signal.SIGINT, signal_handler)

    # 打印启动界面
    print_banner()

    # 加载 MCP 配置
    mcp_config = load_mcp_config()
    mcp_servers = get_mcp_servers(mcp_config)

    # 获取所有可用的工具名称
    tool_names = get_all_tool_names(mcp_config)

    # 打印可用工具信息
    if tool_names:
        print(f"  可用工具: {', '.join(tool_names)}\n")

    # 加载 Skills 配置
    skill_manager = get_skill_manager()
    skills = skill_manager.load_skills()
    if skills:
        skill_names = skill_manager.get_skill_names()
        print(f"  可用 Skills: {', '.join('/' + s for s in skill_names)}\n")
        # 更新命令补全
        update_slash_commands_with_skills(skill_manager.get_slash_commands())

    # 会话控制
    continue_conversation = False

    # 工作目录 - 使用启动时捕获的目录
    work_dir = get_startup_cwd()

    # 打印启动目录
    print(f"  启动目录: {work_dir}\n")

    # 检查点管理器
    checkpoint_manager = CheckpointManager(work_dir)
    checkpoint_counter = 0

    hooks = {
        "pre_tool_use": [HookMatcher(matcher="", hooks=[])]
    }

    # 配置选项
    options = ClaudeAgentOptions(
        permission_mode='default',
        cwd=work_dir,
        allowed_tools=tool_names,
        continue_conversation=continue_conversation,
        can_use_tool=can_use_tool,
        #必须加上钩子，才能使用工具
        hooks=hooks,
        # 添加 MCP 服务器
        mcp_servers=mcp_servers,
    )

    # 创建输入会话
    session = create_session()

    while True:
        try:
            # 检查 Plan Mode 状态并动态调整工具
            current_plan_mode = is_plan_mode()
            if current_plan_mode:
                # Plan Mode: 使用只读工具
                read_only_tools = get_read_only_tool_names()
                read_only_servers = get_mcp_servers_read_only(mcp_config)
                options.allowed_tools = read_only_tools
                options.mcp_servers = read_only_servers
            else:
                # 正常模式: 使用所有工具
                options.allowed_tools = tool_names
                options.mcp_servers = mcp_servers

            # 获取用户输入
            # 打印上方分割线
            print_separator()
            prompt = await session.prompt_async("❯ ")
            # 立即打印下方分割线
            print_separator()
            prompt = prompt.strip()

            # 检查退出命令
            if prompt.lower() in ('quit', 'exit', 'q'):
                print_goodbye()
                break

            # Bash 命令 - Plan Mode 下禁止
            if prompt.startswith('!'):
                if current_plan_mode:
                    print("\n  \033[1;31m[Plan Mode] Bash 命令不可用\033[0m")
                    continue
                bash_command = prompt[1:]
                if bash_command.strip():
                    print("\n  正在执行 Bash 命令...")
                    execute_bash(bash_command)
                continue

            # 清屏命令
            if prompt.lower() == 'clear':
                clear_screen()
                print_banner()
                continue

            # /clear 命令
            if prompt.lower() == '/clear':
                if await handle_clear_command(options, create_prompt_stream):
                    continue_conversation = False
                    options.continue_conversation = False
                    reset_image_counter()  # 重置图片计数器
                    checkpoint_manager.clear()  # 清除检查点
                    reset_plan_mode()  # 重置 Plan Mode
                continue

            # /compact 命令
            if prompt.lower() == '/compact':
                await handle_compact_command(options, create_prompt_stream)
                continue

            # /rewind 命令
            if prompt.lower() == '/rewind':
                result = await handle_rewind_command(
                    checkpoint_manager,
                    options,
                    create_prompt_stream,
                )

                if result.get('should_reset_conversation'):
                    continue_conversation = False
                    options.continue_conversation = False
                    reset_image_counter()
                    reset_plan_mode()  # 重置 Plan Mode

                    # 如果有恢复的提示，显示给用户
                    if result.get('restored_prompt'):
                        print(f"  \033[90m恢复的提示:\033[0m {result['restored_prompt'][:100]}")
                        print(f"  \033[90m你可以重新发送或编辑后发送\033[0m\n")
                continue

            # Skill 命令处理（以 / 开头的非内置命令）
            if prompt.startswith('/') and prompt.lower() not in ('/clear', '/compact', '/rewind'):
                skill_manager = get_skill_manager()

                # 解析 skill 名称和参数
                parts = prompt[1:].split(None, 1)  # 按空格分割，最多分成两部分
                skill_name = parts[0] if parts else ""
                skill_args = parts[1] if len(parts) > 1 else ""

                skill = skill_manager.get_skill(skill_name)

                if skill:
                    # 渲染提示词
                    rendered_prompt = skill_manager.render_prompt(skill, skill_args)

                    # 显示思考指示器
                    print("\n\033[90m  ○ 执行 Skill: {0}...\033[0m".format(skill_name), end="\r")

                    # 配置选项
                    skill_options = ClaudeAgentOptions(
                        permission_mode=options.permission_mode,
                        cwd=get_startup_cwd(),
                        allowed_tools=options.allowed_tools,
                        mcp_servers=options.mcp_servers,
                        continue_conversation=continue_conversation,
                        can_use_tool=can_use_tool,
                        hooks=hooks,
                    )

                    # 如果 skill 指定了工具限制
                    if skill.tools:
                        skill_options.allowed_tools = skill.tools

                    # 如果 skill 指定了模型
                    if skill.model:
                        skill_options.model = skill.model

                    # 创建消息流
                    skill_prompt_stream = create_prompt_stream(rendered_prompt)

                    # 启动代理循环
                    first_response = True
                    async for message in query(prompt=skill_prompt_stream, options=skill_options):
                        first_response = await process_message(message, first_response)

                    if first_response:
                        print(" " * 30, end="\r")
                        print("\n\033[1;31m[警告] Skill 未返回任何响应\033[0m")

                    # 启用继续对话模式
                    if not continue_conversation:
                        continue_conversation = True
                        options.continue_conversation = True

                    # 添加检查点
                    checkpoint_counter += 1
                    checkpoint_manager.add_checkpoint(checkpoint_counter, prompt)

                    continue
                else:
                    # 未找到 skill，显示提示
                    print(f"\n  \033[1;31m[错误] 未找到 Skill: /{skill_name}\033[0m")
                    available_skills = skill_manager.get_skill_names()
                    if available_skills:
                        print(f"  \033[90m可用的 Skills: {', '.join('/' + s for s in available_skills)}\033[0m\n")
                    else:
                        print("  \033[90m提示: 可在 ~/.claude/skills.yaml 中配置自定义 Skills\033[0m\n")
                    continue

            # 帮助命令
            if prompt.lower() == 'help':
                print_help()
                continue

            # 版本命令
            if prompt.lower() == 'version':
                print_version()
                continue

            # 跳过空输入
            if not prompt:
                continue

            # 检查是否有图片输入，使用 Anthropic API 进行图片分析
            image_count = get_image_count()
            if image_count > 0:
                # 收集所有图片路径
                image_paths = []
                for i in range(1, image_count + 1):
                    img_path = get_image_path(i)
                    if img_path and os.path.exists(img_path):
                        image_paths.append(img_path)
                        file_size = os.path.getsize(img_path) / 1024
                        print(f"\n  📷 图片{i}: {os.path.basename(img_path)} ({file_size:.1f} KB)")

                if image_paths:
                    # 显示思考指示器
                    print("\n\033[90m  ○ 分析图片中...\033[0m", end="\r")

                    try:
                        # 使用 Anthropic API 分析图片
                        if len(image_paths) == 1:
                            result = analyze_image(prompt, image_paths[0])
                        else:
                            result = analyze_images(prompt, image_paths)

                        # 清除思考指示器
                        print(" " * 30, end="\r")

                        # 显示结果
                        formatted_text = format_text_with_code(result)
                        print(f"\n\033[1;35mClaude:\033[0m {formatted_text}\n")

                    except Exception as e:
                        print(" " * 30, end="\r")
                        print(f"\n\033[1;31m[错误] {e}\033[0m")

                    # 重置图片计数器
                    reset_image_counter()
                    continue

            # 显示思考指示器
            if current_plan_mode:
                print("\n\033[90m  ○ Plan Mode: 探索中...\033[0m", end="\r")
            else:
                print("\n\033[90m  ○ 思考中...\033[0m", end="\r")

            # 创建消息流
            prompt_stream = create_prompt_stream(prompt)

            # Plan Mode 下添加系统提示词
            if current_plan_mode:
                plan_system_prompt = get_plan_mode_system_prompt()
                # 在 prompt 前添加系统提示
                enhanced_prompt = f"{plan_system_prompt}\n\n用户任务: {prompt}"
                prompt_stream = create_prompt_stream(enhanced_prompt)

            # 启动代理循环
            first_response = True
            plan_text = ""  # 收集 Plan Mode 下的响应
            async for message in query(prompt=prompt_stream, options=options):
                first_response = await process_message(message, first_response)

                # Plan Mode 下收集响应文本
                if current_plan_mode:
                    message_type = type(message).__name__
                    if message_type == 'AssistantMessage':
                        for block in message.content:
                            block_type = type(block).__name__
                            if block_type == 'TextBlock':
                                plan_text += block.text + "\n"

            if first_response:
                print(" " * 30, end="\r")
                print("\n\033[1;31m[警告] 未收到任何响应\033[0m")

            # Plan Mode 下展示计划审批
            if current_plan_mode and plan_text.strip():
                set_plan_content(plan_text)
                approval = await display_plan_approval(plan_text)

                if approval == 'approve':
                    print_plan_approved()
                    # 用户批准后，关闭 Plan Mode 并执行
                    from .plan_mode import toggle_plan_mode
                    toggle_plan_mode()  # 关闭 Plan Mode

                    # 恢复完整工具集
                    options.allowed_tools = tool_names
                    options.mcp_servers = mcp_servers

                    # TODO: 这里可以添加自动执行计划的逻辑
                    print("  计划已批准，您可以输入任务开始执行。\n")
                else:
                    print_plan_cancelled()

            # 启用继续对话模式
            if not continue_conversation:
                continue_conversation = True
                options.continue_conversation = True

            # 添加检查点（保存用户提示）
            checkpoint_counter += 1
            checkpoint_manager.add_checkpoint(checkpoint_counter, prompt)

        except KeyboardInterrupt:
            print_goodbye()
            break
        except EOFError:
            print_goodbye()
            break


def main():
    """命令行入口点"""
    # 检查首次运行配置
    from .setup_wizard import (
        check_config_exists,
        run_setup_wizard,
        save_config,
        load_config_to_env,
    )

    if not check_config_exists():
        config = run_setup_wizard()
        save_config(config)
        # 加载新配置到环境变量
        load_config_to_env()

    anyio.run(run)


if __name__ == "__main__":
    main()