"""MCP 配置管理"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from claude_agent_sdk.types import (
    McpStdioServerConfig,
    McpSSEServerConfig,
    McpHttpServerConfig,
    McpSdkServerConfig,
)


@dataclass
class MCPServerConfig:
    """MCP 服务器配置"""
    name: str
    type: str  # "stdio", "sse", "http", "sdk"
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MCPConfig:
    """MCP 配置"""
    servers: List[MCPServerConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPConfig":
        """从字典创建配置"""
        servers = []
        mcp_servers = data.get("mcpServers", {})

        for name, server_config in mcp_servers.items():
            server_type = server_config.get("type", "stdio")
            servers.append(MCPServerConfig(
                name=name,
                type=server_type,
                config=server_config,
            ))

        return cls(servers=servers)

    def to_sdk_config(self) -> Dict[str, Any]:
        """转换为 SDK 配置格式"""
        result = {}
        for server in self.servers:
            if server.type == "stdio":
                result[server.name] = McpStdioServerConfig(
                    command=server.config.get("command", ""),
                    args=server.config.get("args", []),
                    env=server.config.get("env"),
                )
            elif server.type == "sse":
                result[server.name] = McpSSEServerConfig(
                    url=server.config.get("url", ""),
                    headers=server.config.get("headers"),
                )
            elif server.type == "http":
                result[server.name] = McpHttpServerConfig(
                    url=server.config.get("url", ""),
                    headers=server.config.get("headers"),
                )
            # SDK 类型需要单独处理，在 server.py 中创建
        return result


def get_default_config_paths() -> List[Path]:
    """获取默认配置文件路径列表"""
    paths = []

    # 项目目录下的 .mcp.json
    project_config = Path.cwd() / ".mcp.json"
    paths.append(project_config)

    # 用户主目录下的 .claude/mcp.json
    home_config = Path.home() / ".claude" / "mcp.json"
    paths.append(home_config)

    return paths


def load_mcp_config(config_path: Optional[str] = None) -> MCPConfig:
    """加载 MCP 配置

    Args:
        config_path: 指定的配置文件路径，如果为 None 则使用默认路径

    Returns:
        MCPConfig 对象
    """
    if config_path:
        # 使用指定路径
        path = Path(config_path)
        if not path.exists():
            print(f"  ⚠️  MCP 配置文件不存在: {config_path}")
            return MCPConfig()

        return _load_config_from_file(path)

    # 尝试默认路径
    for path in get_default_config_paths():
        if path.exists():
            return _load_config_from_file(path)

    # 没有找到配置文件，返回空配置
    return MCPConfig()


def _load_config_from_file(path: Path) -> MCPConfig:
    """从文件加载配置"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        config = MCPConfig.from_dict(data)
        print(f"  ✓ 已加载 MCP 配置: {path}")
        return config

    except json.JSONDecodeError as e:
        print(f"  ⚠️  MCP 配置文件格式错误: {path} - {e}")
        return MCPConfig()
    except Exception as e:
        print(f"  ⚠️  加载 MCP 配置失败: {path} - {e}")
        return MCPConfig()