"""Bash 命令执行工具

提供安全的 shell 命令执行功能，包括：
- 超时控制
- 危险命令检测
- 实时输出
- 后台运行支持
"""

import os
import sys
import re
import subprocess
import signal
import threading
import queue
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from claude_agent_sdk import tool


# 默认超时时间（毫秒）
DEFAULT_TIMEOUT = 120000  # 2 分钟
MAX_TIMEOUT = 600000  # 10 分钟

# 项目目录
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../my_project"))


@dataclass
class BashResult:
    """Bash 命令执行结果"""
    exit_code: int
    output: str
    timed_out: bool = False
    error: Optional[str] = None


# 危险命令模式列表 - 直接阻止
DANGEROUS_PATTERNS = [
    # 文件系统破坏
    (r'\brm\s+(-[rf]+\s+)*(/|\*|/\*)', "删除根目录或所有文件"),
    (r'\brm\s+(-[rf]+\s+)*~', "删除用户主目录"),
    (r'\bmkfs\b', "格式化磁盘"),
    (r'\bfdisk\b', "磁盘分区操作"),
    (r'\bdd\s+.*of=/dev/', "直接写入磁盘设备"),

    # 系统破坏
    (r':\(\)\s*\{\s*:\|:&\s*\}\s*;:', "Fork 炸弹"),
    (r'\bchmod\s+(-R\s+)?000\s+/', "移除根目录权限"),
    (r'\bchown\s+(-R\s+)?\S+\s+/', "修改根目录所有者"),

    # 网络危险操作
    (r'\biptables\s+-F', "清空防火墙规则"),
    (r'\bip\s+route\s+del\s+default', "删除默认路由"),

    # 权限提升
    (r'\bchmod\s+[ug]*s\b', "设置 SUID/SGID 位"),

    # 覆盖重要文件
    (r'>\s*/dev/sd[a-z]', "覆盖磁盘设备"),

    # 系统关机/重启
    (r'\b(shutdown|reboot|poweroff|halt)\b', "系统关机/重启"),
]

# 需要确认的命令模式 - 危险但可能有用
CONFIRM_PATTERNS = [
    (r'\brm\s+(-[rf]+\s+)*\S+', "删除文件/目录"),
    (r'\bgit\s+push\s+.*--force', "强制推送"),
    (r'\bgit\s+reset\s+--hard', "硬重置（丢失未提交更改）"),
    (r'\bgit\s+clean\s+-[fd]', "清理未跟踪文件"),
    (r'\bnpm\s+publish', "发布 npm 包"),
    (r'\bpip\s+uninstall', "卸载 Python 包"),
    (r'\bdocker\s+(rm|rmi|system\s+prune)', "删除 Docker 容器/镜像"),
    (r'\bkill\s+-9', "强制终止进程"),
]


def check_dangerous_command(command: str) -> Tuple[bool, Optional[str]]:
    """检查命令是否危险（直接阻止）

    Args:
        command: 要检查的命令

    Returns:
        (是否危险, 危险原因)
    """
    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True, reason
    return False, None


def check_confirm_command(command: str) -> Tuple[bool, Optional[str]]:
    """检查命令是否需要用户确认

    Args:
        command: 要检查的命令

    Returns:
        (需要确认, 原因)
    """
    for pattern, reason in CONFIRM_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True, reason
    return False, None


def execute_bash_internal(
    command: str,
    timeout: int = DEFAULT_TIMEOUT,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> BashResult:
    """执行 Bash 命令（内部实现，带超时控制）

    Args:
        command: 要执行的命令
        timeout: 超时时间（毫秒）
        cwd: 工作目录
        env: 环境变量

    Returns:
        BashResult 执行结果
    """
    # 转换超时时间为秒
    timeout_seconds = min(timeout, MAX_TIMEOUT) / 1000

    try:
        # 准备环境
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        # 确定工作目录
        work_dir = cwd or PROJECT_DIR
        if not os.path.exists(work_dir):
            work_dir = os.getcwd()

        # 启动进程
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=work_dir,
            env=process_env,
        )

        try:
            # 等待完成，带超时
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            exit_code = process.returncode

            output = stdout
            if stderr:
                output += f"\n[stderr]\n{stderr}"

            return BashResult(
                exit_code=exit_code,
                output=output.strip(),
            )

        except subprocess.TimeoutExpired:
            # 超时，终止进程
            process.kill()
            process.wait()

            # 尝试获取部分输出
            try:
                stdout, stderr = process.communicate()
                partial_output = (stdout or "") + (stderr or "")
            except:
                partial_output = ""

            return BashResult(
                exit_code=-1,
                output=partial_output,
                timed_out=True,
                error=f"命令执行超时（超过 {timeout_seconds:.0f} 秒）",
            )

    except Exception as e:
        return BashResult(
            exit_code=-1,
            output="",
            error=f"执行错误: {str(e)}",
        )


def execute_bash_streaming(
    command: str,
    timeout: int = DEFAULT_TIMEOUT,
    cwd: Optional[str] = None,
) -> BashResult:
    """执行 Bash 命令并实时输出到终端（用于 CLI 显示）

    Args:
        command: 要执行的命令
        timeout: 超时时间（毫秒）
        cwd: 工作目录

    Returns:
        BashResult 执行结果
    """
    timeout_seconds = min(timeout, MAX_TIMEOUT) / 1000

    output_lines = []

    try:
        # 确定工作目录
        work_dir = cwd or PROJECT_DIR
        if not os.path.exists(work_dir):
            work_dir = os.getcwd()

        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=work_dir,
        )

        # 使用线程读取输出
        output_queue = queue.Queue()
        reader_finished = threading.Event()

        def read_output():
            try:
                for line in process.stdout:
                    output_queue.put(line)
            finally:
                reader_finished.set()

        reader_thread = threading.Thread(target=read_output, daemon=True)
        reader_thread.start()

        # 收集输出，带超时
        start_time = time.time()
        while True:
            try:
                line = output_queue.get(timeout=0.1)
                output_lines.append(line)
                print("  " + line, end='')
                sys.stdout.flush()
            except queue.Empty:
                pass

            # 检查超时
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                process.kill()
                process.wait()
                print(f"\n\033[1;31m⏱️ 命令执行超时（{timeout_seconds:.0f}秒）\033[0m")
                return BashResult(
                    exit_code=-1,
                    output="".join(output_lines),
                    timed_out=True,
                    error=f"命令执行超时（{timeout_seconds:.0f}秒）",
                )

            # 检查进程是否结束
            if reader_finished.is_set() and output_queue.empty():
                break

        process.wait()
        return BashResult(
            exit_code=process.returncode,
            output="".join(output_lines),
        )

    except Exception as e:
        return BashResult(
            exit_code=-1,
            output="".join(output_lines),
            error=f"执行错误: {str(e)}",
        )


@tool(
    "bash",
    "执行 shell 命令。支持超时控制和危险命令检测。危险命令会被阻止，某些命令需要用户确认。",
    {
        "command": str,
        "description": str,
        "timeout": int,
    }
)
async def bash_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """执行 Bash 命令

    Args:
        command: 要执行的命令
        description: 命令描述（可选，帮助用户理解命令用途）
        timeout: 超时时间（毫秒），默认 120000，最大 600000

    Returns:
        执行结果
    """
    command = args.get("command", "")
    description = args.get("description", "")
    timeout = args.get("timeout", DEFAULT_TIMEOUT)

    if not command:
        return {
            "content": [{"type": "text", "text": "错误：缺少 command 参数"}],
            "isError": True
        }

    # 验证超时时间
    if timeout > MAX_TIMEOUT:
        return {
            "content": [{"type": "text", "text": f"错误：超时时间不能超过 {MAX_TIMEOUT} 毫秒（10分钟）"}],
            "isError": True
        }

    # 检查危险命令（直接阻止）
    is_dangerous, danger_reason = check_dangerous_command(command)
    if is_dangerous:
        return {
            "content": [{
                "type": "text",
                "text": f"🚫 危险命令被阻止\n\n原因: {danger_reason}\n命令: {command}\n\n此命令可能对系统造成不可逆的损害，已被安全策略阻止。"
            }],
            "isError": True
        }

    # 检查需要确认的命令
    need_confirm, confirm_reason = check_confirm_command(command)
    if need_confirm:
        # 返回特殊标记，让调用方处理确认逻辑
        return {
            "content": [{
                "type": "text",
                "text": f"⚠️ 需要确认\n\n原因: {confirm_reason}\n命令: {command}\n\n此操作具有一定风险，请确认是否继续执行。"
            }],
            "isError": False,
            "requiresConfirmation": True,
            "confirmReason": confirm_reason,
            "command": command,
        }

    # 执行命令
    result = execute_bash_internal(command, timeout)

    # 构建输出
    output_parts = []

    if description:
        output_parts.append(f"描述: {description}")
    output_parts.append(f"命令: {command}")
    output_parts.append("")

    if result.timed_out:
        output_parts.append(f"⏱️ {result.error}")
        if result.output:
            output_parts.append("\n部分输出:")
            output_parts.append(result.output)
    elif result.error:
        output_parts.append(f"❌ {result.error}")
    else:
        if result.output:
            output_parts.append(result.output)

    if result.exit_code != 0 and not result.timed_out:
        output_parts.append(f"\n退出码: {result.exit_code}")

    return {
        "content": [{"type": "text", "text": "\n".join(output_parts)}],
        "isError": result.exit_code != 0 or result.error is not None,
    }


# 导出函数供 CLI 直接使用
__all__ = [
    "bash_tool",
    "execute_bash_internal",
    "execute_bash_streaming",
    "check_dangerous_command",
    "check_confirm_command",
    "BashResult",
    "DEFAULT_TIMEOUT",
    "MAX_TIMEOUT",
]