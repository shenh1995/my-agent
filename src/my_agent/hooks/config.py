"""Hook 系统配置和管理

支持以下 Hook 事件：
- PreToolUse: 工具调用前
- PostToolUse: 工具调用后
- PostToolUseFailure: 工具调用失败后
- UserPromptSubmit: 用户提交提示时
- Stop: 会话停止时
- SubagentStart: 子智能体启动时
- SubagentStop: 子智能体停止时
- PreCompact: 压缩对话前
- Notification: 通知事件
- PermissionRequest: 权限请求时
"""

import json
import os
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Awaitable, Union, Literal

from claude_agent_sdk.types import (
    HookMatcher,
    HookContext,
    PreToolUseHookInput,
    PostToolUseHookInput,
    PostToolUseFailureHookInput,
    UserPromptSubmitHookInput,
    StopHookInput,
    SubagentStartHookInput,
    SubagentStopHookInput,
    PreCompactHookInput,
    NotificationHookInput,
    PermissionRequestHookInput,
    SyncHookJSONOutput,
    AsyncHookJSONOutput,
)


# Hook 事件类型
HookEventName = Literal[
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "UserPromptSubmit",
    "Stop",
    "SubagentStart",
    "SubagentStop",
    "PreCompact",
    "Notification",
    "PermissionRequest",
]


@dataclass
class HookConfig:
    """单个 Hook 配置"""
    matcher: str = ""  # 匹配器，可以是工具名或正则表达式
    command: Optional[str] = None  # 要执行的 shell 命令
    timeout: float = 60.0  # 超时时间（秒）
    enabled: bool = True  # 是否启用

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matcher": self.matcher,
            "command": self.command,
            "timeout": self.timeout,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HookConfig":
        return cls(
            matcher=data.get("matcher", ""),
            command=data.get("command"),
            timeout=data.get("timeout", 60.0),
            enabled=data.get("enabled", True),
        )


@dataclass
class HooksConfig:
    """所有 Hook 配置"""
    pre_tool_use: List[HookConfig] = field(default_factory=list)
    post_tool_use: List[HookConfig] = field(default_factory=list)
    post_tool_use_failure: List[HookConfig] = field(default_factory=list)
    user_prompt_submit: List[HookConfig] = field(default_factory=list)
    stop: List[HookConfig] = field(default_factory=list)
    subagent_start: List[HookConfig] = field(default_factory=list)
    subagent_stop: List[HookConfig] = field(default_factory=list)
    pre_compact: List[HookConfig] = field(default_factory=list)
    notification: List[HookConfig] = field(default_factory=list)
    permission_request: List[HookConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HooksConfig":
        """从字典创建配置"""
        def parse_hooks(hook_list: List) -> List[HookConfig]:
            if not hook_list:
                return []
            return [HookConfig.from_dict(h) if isinstance(h, dict) else h for h in hook_list]

        return cls(
            pre_tool_use=parse_hooks(data.get("PreToolUse", [])),
            post_tool_use=parse_hooks(data.get("PostToolUse", [])),
            post_tool_use_failure=parse_hooks(data.get("PostToolUseFailure", [])),
            user_prompt_submit=parse_hooks(data.get("UserPromptSubmit", [])),
            stop=parse_hooks(data.get("Stop", [])),
            subagent_start=parse_hooks(data.get("SubagentStart", [])),
            subagent_stop=parse_hooks(data.get("SubagentStop", [])),
            pre_compact=parse_hooks(data.get("PreCompact", [])),
            notification=parse_hooks(data.get("Notification", [])),
            permission_request=parse_hooks(data.get("PermissionRequest", [])),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "PreToolUse": [h.to_dict() for h in self.pre_tool_use],
            "PostToolUse": [h.to_dict() for h in self.post_tool_use],
            "PostToolUseFailure": [h.to_dict() for h in self.post_tool_use_failure],
            "UserPromptSubmit": [h.to_dict() for h in self.user_prompt_submit],
            "Stop": [h.to_dict() for h in self.stop],
            "SubagentStart": [h.to_dict() for h in self.subagent_start],
            "SubagentStop": [h.to_dict() for h in self.subagent_stop],
            "PreCompact": [h.to_dict() for h in self.pre_compact],
            "Notification": [h.to_dict() for h in self.notification],
            "PermissionRequest": [h.to_dict() for h in self.permission_request],
        }


# Hook 输入类型别名
HookInput = Union[
    PreToolUseHookInput,
    PostToolUseHookInput,
    PostToolUseFailureHookInput,
    UserPromptSubmitHookInput,
    StopHookInput,
    SubagentStartHookInput,
    SubagentStopHookInput,
    PreCompactHookInput,
    NotificationHookInput,
    PermissionRequestHookInput,
]


class HookExecutor:
    """Hook 执行器"""

    def __init__(self, config: HooksConfig):
        self.config = config

    async def execute_command(
        self,
        command: str,
        hook_input: HookInput,
        timeout: float = 60.0,
    ) -> Optional[SyncHookJSONOutput]:
        """执行 shell 命令作为 hook

        Args:
            command: 要执行的命令
            hook_input: hook 输入数据
            timeout: 超时时间

        Returns:
            hook 输出，如果命令失败返回 None
        """
        try:
            # 准备环境变量
            env = os.environ.copy()

            # 将 hook 输入作为环境变量传递
            env["CLAUDE_HOOK_EVENT"] = hook_input.get("hook_event_name", "")
            env["CLAUDE_SESSION_ID"] = hook_input.get("session_id", "")
            env["CLAUDE_CWD"] = hook_input.get("cwd", "")

            # 根据事件类型设置特定环境变量
            if "tool_name" in hook_input:
                env["CLAUDE_TOOL_NAME"] = hook_input["tool_name"]
            if "tool_input" in hook_input:
                env["CLAUDE_TOOL_INPUT"] = json.dumps(hook_input["tool_input"])
            if "prompt" in hook_input:
                env["CLAUDE_PROMPT"] = hook_input["prompt"]

            # 将完整输入作为 JSON 传递给 stdin
            input_json = json.dumps(hook_input)

            # 执行命令
            process = await asyncio.create_subprocess_shell(
                command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input_json.encode()),
                    timeout=timeout,
                )

                if process.returncode == 0:
                    # 尝试解析 JSON 输出
                    try:
                        output = json.loads(stdout.decode())
                        return output
                    except json.JSONDecodeError:
                        # 如果不是 JSON，返回成功
                        return {"continue_": True}
                else:
                    print(f"  \033[1;31m[Hook] 命令执行失败: {stderr.decode()}\033[0m")
                    return None

            except asyncio.TimeoutError:
                process.kill()
                print(f"  \033[1;31m[Hook] 命令超时 ({timeout}s)\033[0m")
                return None

        except Exception as e:
            print(f"  \033[1;31m[Hook] 执行错误: {e}\033[0m")
            return None

    def matches(self, pattern: str, value: str) -> bool:
        """检查值是否匹配模式

        Args:
            pattern: 模式（支持通配符 * 和正则）
            value: 要匹配的值

        Returns:
            是否匹配
        """
        if not pattern or pattern == "*":
            return True

        # 简单的通配符匹配
        if "*" in pattern and not pattern.startswith("^"):
            # 转换为简单的通配符匹配
            import fnmatch
            return fnmatch.fnmatch(value, pattern)

        # 尝试正则匹配
        try:
            import re
            return bool(re.match(pattern, value))
        except re.error:
            # 如果正则无效，使用简单字符串匹配
            return pattern == value

    def get_hooks_for_event(self, event_name: HookEventName) -> List[HookConfig]:
        """获取指定事件的所有 hook 配置

        Args:
            event_name: 事件名称

        Returns:
            hook 配置列表
        """
        event_map = {
            "PreToolUse": self.config.pre_tool_use,
            "PostToolUse": self.config.post_tool_use,
            "PostToolUseFailure": self.config.post_tool_use_failure,
            "UserPromptSubmit": self.config.user_prompt_submit,
            "Stop": self.config.stop,
            "SubagentStart": self.config.subagent_start,
            "SubagentStop": self.config.subagent_stop,
            "PreCompact": self.config.pre_compact,
            "Notification": self.config.notification,
            "PermissionRequest": self.config.permission_request,
        }
        return event_map.get(event_name, [])

    async def run_hooks(
        self,
        event_name: HookEventName,
        hook_input: HookInput,
        match_value: Optional[str] = None,
    ) -> List[SyncHookJSONOutput]:
        """运行指定事件的所有匹配 hooks

        Args:
            event_name: 事件名称
            hook_input: hook 输入数据
            match_value: 用于匹配的值（如工具名）

        Returns:
            所有 hook 的输出列表
        """
        results = []
        hooks = self.get_hooks_for_event(event_name)

        for hook_config in hooks:
            if not hook_config.enabled:
                continue

            if not hook_config.command:
                continue

            # 检查匹配器
            if match_value and not self.matches(hook_config.matcher, match_value):
                continue

            # 执行 hook
            result = await self.execute_command(
                hook_config.command,
                hook_input,
                hook_config.timeout,
            )

            if result:
                results.append(result)

                # 如果 hook 返回 block，停止执行后续 hooks
                if result.get("decision") == "block":
                    break

        return results


def get_default_hooks_config_paths() -> List[Path]:
    """获取默认 hooks 配置文件路径列表"""
    paths = []

    # 项目目录下的 settings.json
    project_settings = Path.cwd() / ".claude" / "settings.json"
    paths.append(project_settings)

    # 用户主目录下的 settings.json
    home_settings = Path.home() / ".claude" / "settings.json"
    paths.append(home_settings)

    # 项目目录下的 hooks.json（简化配置）
    project_hooks = Path.cwd() / ".claude" / "hooks.json"
    paths.append(project_hooks)

    # 用户主目录下的 hooks.json
    home_hooks = Path.home() / ".claude" / "hooks.json"
    paths.append(home_hooks)

    return paths


def load_hooks_config(config_path: Optional[str] = None) -> HooksConfig:
    """加载 hooks 配置

    Args:
        config_path: 指定的配置文件路径

    Returns:
        HooksConfig 对象
    """
    if config_path:
        path = Path(config_path)
        if path.exists():
            return _load_hooks_from_file(path)
        print(f"  ⚠️  Hooks 配置文件不存在: {config_path}")
        return HooksConfig()

    # 尝试默认路径
    for path in get_default_hooks_config_paths():
        if path.exists():
            return _load_hooks_from_file(path)

    return HooksConfig()


def _load_hooks_from_file(path: Path) -> HooksConfig:
    """从文件加载 hooks 配置"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 支持两种格式：
        # 1. {"hooks": {...}}
        # 2. 直接的 hooks 配置 {...}
        if "hooks" in data:
            hooks_data = data["hooks"]
        else:
            hooks_data = data

        config = HooksConfig.from_dict(hooks_data)

        # 统计加载的 hooks 数量
        total_hooks = sum(len(h) for h in [
            config.pre_tool_use,
            config.post_tool_use,
            config.post_tool_use_failure,
            config.user_prompt_submit,
            config.stop,
            config.subagent_start,
            config.subagent_stop,
            config.pre_compact,
            config.notification,
            config.permission_request,
        ])

        if total_hooks > 0:
            print(f"  ✓ 已加载 {total_hooks} 个 Hooks 配置: {path}")

        return config

    except json.JSONDecodeError as e:
        print(f"  ⚠️  Hooks 配置文件格式错误: {path} - {e}")
        return HooksConfig()
    except Exception as e:
        print(f"  ⚠️  加载 Hooks 配置失败: {path} - {e}")
        return HooksConfig()


def create_hook_callback(
    executor: HookExecutor,
    event_name: HookEventName,
) -> Callable[[HookInput, Optional[str], HookContext], Awaitable[SyncHookJSONOutput]]:
    """创建 hook 回调函数

    Args:
        executor: Hook 执行器
        event_name: 事件名称

    Returns:
        异步回调函数
    """
    async def callback(
        hook_input: HookInput,
        extra: Optional[str],
        context: HookContext,
    ) -> SyncHookJSONOutput:
        # 获取匹配值
        match_value = None
        if "tool_name" in hook_input:
            match_value = hook_input["tool_name"]

        # 运行 hooks
        results = await executor.run_hooks(event_name, hook_input, match_value)

        # 合并结果
        final_result: SyncHookJSONOutput = {}

        for result in results:
            # 如果有 block 决策，立即返回
            if result.get("decision") == "block":
                return result

            # 合并其他字段
            for key, value in result.items():
                if value is not None:
                    final_result[key] = value  # type: ignore

        return final_result

    return callback


def create_hook_matchers(executor: HookExecutor) -> Dict[str, List[HookMatcher]]:
    """创建所有事件的 HookMatcher

    Args:
        executor: Hook 执行器

    Returns:
        事件名到 HookMatcher 列表的映射
    """
    events: List[HookEventName] = [
        "PreToolUse",
        "PostToolUse",
        "PostToolUseFailure",
        "UserPromptSubmit",
        "Stop",
        "SubagentStart",
        "SubagentStop",
        "PreCompact",
        "Notification",
        "PermissionRequest",
    ]

    hooks_dict: Dict[str, List[HookMatcher]] = {}

    for event_name in events:
        callback = create_hook_callback(executor, event_name)
        # matcher="" 表示匹配所有
        hooks_dict[event_name] = [HookMatcher(matcher="", hooks=[callback])]

    return hooks_dict


# 全局 Hook 执行器实例
_hook_executor: Optional[HookExecutor] = None


def get_hook_executor(config: Optional[HooksConfig] = None) -> HookExecutor:
    """获取全局 Hook 执行器实例"""
    global _hook_executor
    if config is not None:
        _hook_executor = HookExecutor(config)
    elif _hook_executor is None:
        _hook_executor = HookExecutor(HooksConfig())
    return _hook_executor


def init_hooks_from_config() -> Dict[str, List[HookMatcher]]:
    """从配置文件初始化 hooks 并返回 HookMatcher 字典

    Returns:
        可用于 ClaudeAgentOptions.hooks 的字典
    """
    config = load_hooks_config()
    executor = get_hook_executor(config)
    return create_hook_matchers(executor)