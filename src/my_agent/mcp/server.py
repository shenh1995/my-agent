"""MCP 服务器创建和管理"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List

from claude_agent_sdk import create_sdk_mcp_server
from claude_agent_sdk.types import (
    McpSdkServerConfig,
    McpStdioServerConfig,
    McpSSEServerConfig,
    McpHttpServerConfig,
)

from .tools import (
    read_file,
    write_file,
    edit_file,
    list_directory,
    glob_files,
    grep_content,
    bash_tool,
    web_fetch,
    task_create,
    task_update,
    task_list,
    task_get,
    task_output,
    task_stop,
    task_tool,
)
from .config import MCPConfig, MCPServerConfig


# 内置工具列表
BUILTIN_TOOLS = [
    read_file,
    write_file,
    edit_file,
    list_directory,
    glob_files,
    grep_content,
    bash_tool,
    web_fetch,
    task_create,
    task_update,
    task_list,
    task_get,
    task_output,
    task_stop,
    task_tool,
]

# 内置工具名称
BUILTIN_TOOL_NAMES = [
    "read_file",
    "write_file",
    "edit_file",
    "list_directory",
    "glob",
    "grep",
    "bash",
    "web_fetch",
    "task_create",
    "task_update",
    "task_list",
    "task_get",
    "task_output",
    "task_stop",
    "task",
]

# 只读工具列表（用于 Plan Mode）
READ_ONLY_TOOLS = [
    read_file,
    list_directory,
    glob_files,
    grep_content,
]

# 只读工具名称
READ_ONLY_TOOL_NAMES = [
    "read_file",
    "list_directory",
    "glob",
    "grep",
]


def create_builtin_mcp_server(
    name: str = "builtin",
    tools: Optional[List] = None,
) -> McpSdkServerConfig:
    """创建内置 MCP 服务器

    Args:
        name: 服务器名称
        tools: 要包含的工具列表，如果为 None 则包含所有内置工具

    Returns:
        McpSdkServerConfig 配置对象
    """
    if tools is None:
        tools = BUILTIN_TOOLS

    return create_sdk_mcp_server(
        name=name,
        version="1.0.0",
        tools=tools,
    )


def create_external_server_config(server_config: MCPServerConfig) -> Optional[Any]:
    """创建外部 MCP 服务器配置

    Args:
        server_config: 服务器配置信息

    Returns:
        SDK 服务器配置对象
    """
    config_type = server_config.type
    config_data = server_config.config

    if config_type == "stdio":
        return McpStdioServerConfig(
            command=config_data.get("command", ""),
            args=config_data.get("args", []),
            env=config_data.get("env"),
        )
    elif config_type == "sse":
        return McpSSEServerConfig(
            url=config_data.get("url", ""),
            headers=config_data.get("headers"),
        )
    elif config_type == "http":
        return McpHttpServerConfig(
            url=config_data.get("url", ""),
            headers=config_data.get("headers"),
        )
    else:
        print(f"  ⚠️  未知的 MCP 服务器类型: {config_type}")
        return None


def get_mcp_servers(
    mcp_config: Optional[MCPConfig] = None,
    include_builtin: bool = True,
    builtin_server_name: str = "builtin",
) -> Dict[str, Any]:
    """获取 MCP 服务器配置字典

    Args:
        mcp_config: MCP 配置对象
        include_builtin: 是否包含内置服务器
        builtin_server_name: 内置服务器名称

    Returns:
        服务器配置字典，可直接用于 ClaudeAgentOptions.mcp_servers
    """
    servers = {}

    # 添加内置服务器
    if include_builtin:
        servers[builtin_server_name] = create_builtin_mcp_server(builtin_server_name)

    # 添加外部服务器
    if mcp_config:
        for server in mcp_config.servers:
            if server.type == "sdk":
                # SDK 类型服务器需要特殊处理
                # 这里假设配置中指定了要使用的工具名称
                tool_names = server.config.get("tools", [])
                tools = []
                for tool_name in tool_names:
                    if tool_name in BUILTIN_TOOL_NAMES:
                        # 根据名称找到对应的工具函数
                        tool_map = {
                            "read_file": read_file,
                            "write_file": write_file,
                            "edit_file": edit_file,
                            "list_directory": list_directory,
                            "glob": glob_files,
                            "grep": grep_content,
                            "bash": bash_tool,
                            "web_fetch": web_fetch,
                            "task_create": task_create,
                            "task_update": task_update,
                            "task_list": task_list,
                            "task_get": task_get,
                            "task_output": task_output,
                            "task_stop": task_stop,
                            "task": task_tool,
                        }
                        if tool_name in tool_map:
                            tools.append(tool_map[tool_name])

                if tools:
                    servers[server.name] = create_sdk_mcp_server(
                        name=server.name,
                        tools=tools,
                    )
            else:
                # 外部服务器
                config = create_external_server_config(server)
                if config:
                    servers[server.name] = config

    return servers


def get_all_tool_names(mcp_config: Optional[MCPConfig] = None) -> List[str]:
    """获取所有可用的工具名称

    Args:
        mcp_config: MCP 配置对象

    Returns:
        工具名称列表
    """
    tool_names = list(BUILTIN_TOOL_NAMES)

    # 添加外部 MCP 服务器的工具名称（使用通配符）
    # MCP 工具的命名格式为: mcp__<server_name>__<tool_name>
    if mcp_config:
        for server in mcp_config.servers:
            # 对于外部服务器，添加通配符允许所有工具
            # SDK 会在运行时动态发现工具
            tool_names.append(f"mcp__{server.name}")

    return tool_names


def create_read_only_mcp_server(name: str = "read_only") -> McpSdkServerConfig:
    """创建只读工具的 MCP 服务器（用于 Plan Mode）

    Args:
        name: 服务器名称

    Returns:
        McpSdkServerConfig 配置对象
    """
    return create_sdk_mcp_server(
        name=name,
        version="1.0.0",
        tools=READ_ONLY_TOOLS,
    )


def get_read_only_tool_names() -> List[str]:
    """获取只读工具名称列表

    Returns:
        只读工具名称列表
    """
    return list(READ_ONLY_TOOL_NAMES)


def get_mcp_servers_read_only(
    mcp_config: Optional[MCPConfig] = None,
    builtin_server_name: str = "read_only",
) -> Dict[str, Any]:
    """获取只读模式的 MCP 服务器配置字典（用于 Plan Mode）

    Args:
        mcp_config: MCP 配置对象
        builtin_server_name: 内置服务器名称

    Returns:
        服务器配置字典，只包含只读工具
    """
    servers = {}

    # 添加只读服务器
    servers[builtin_server_name] = create_read_only_mcp_server(builtin_server_name)

    return servers