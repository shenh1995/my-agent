"""MCP 文件操作工具"""

import os
from pathlib import Path
from typing import Dict, Any

from claude_agent_sdk import tool


def _resolve_path(file_path: str, base_dir: str = None) -> Path:
    """解析文件路径

    Args:
        file_path: 文件路径
        base_dir: 基础目录，如果为 None 则使用当前工作目录

    Returns:
        解析后的 Path 对象
    """
    path = Path(file_path)
    if not path.is_absolute():
        if base_dir:
            path = Path(base_dir) / path
        else:
            path = Path.cwd() / path
    return path.resolve()


def _is_safe_path(path: Path, allowed_dirs: list = None) -> bool:
    """检查路径是否安全（在允许的目录内）

    Args:
        path: 要检查的路径
        allowed_dirs: 允许的目录列表

    Returns:
        是否安全
    """
    if allowed_dirs is None:
        # 默认允许当前工作目录
        allowed_dirs = [Path.cwd().resolve()]

    resolved_path = path.resolve()
    for allowed_dir in allowed_dirs:
        allowed_path = Path(allowed_dir).resolve()
        try:
            resolved_path.relative_to(allowed_path)
            return True
        except ValueError:
            continue
    return False


@tool(
    "read_file",
    "读取文件内容。可以读取文本文件，返回文件的全部内容。对于大文件，建议使用 offset 和 limit 参数分批读取。",
    {
        "file_path": str,
        "offset": int,
        "limit": int,
    }
)
async def read_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """读取文件内容

    Args:
        file_path: 文件的绝对路径
        offset: 开始读取的行号（从 0 开始），默认为 0
        limit: 读取的行数，默认为 2000

    Returns:
        包含文件内容的字典
    """
    file_path = args.get("file_path")
    if not file_path:
        return {
            "content": [{"type": "text", "text": "错误：缺少 file_path 参数"}],
            "isError": True
        }

    offset = args.get("offset", 0)
    limit = args.get("limit", 2000)

    try:
        path = _resolve_path(file_path)

        if not path.exists():
            return {
                "content": [{"type": "text", "text": f"错误：文件不存在: {file_path}"}],
                "isError": True
            }

        if not path.is_file():
            return {
                "content": [{"type": "text", "text": f"错误：路径不是文件: {file_path}"}],
                "isError": True
            }

        # 读取文件内容
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # 应用 offset 和 limit
        total_lines = len(lines)
        start = min(offset, total_lines)
        end = min(offset + limit, total_lines)
        selected_lines = lines[start:end]

        # 格式化输出（带行号）
        result_lines = []
        for i, line in enumerate(selected_lines, start=offset + 1):
            # 去除末尾换行符，添加行号
            result_lines.append(f"{i:6}\t{line.rstrip()}")

        content = "\n".join(result_lines)

        # 添加元信息
        info = f"文件: {path}\n总行数: {total_lines}\n显示: 第 {start + 1} 行到第 {end} 行\n"
        if end < total_lines:
            info += f"（还有 {total_lines - end} 行未显示）\n"
        info += "\n" + "=" * 60 + "\n"

        return {
            "content": [{"type": "text", "text": info + content}],
        }

    except UnicodeDecodeError:
        return {
            "content": [{"type": "text", "text": f"错误：无法解码文件（可能是二进制文件）: {file_path}"}],
            "isError": True
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"读取文件失败: {str(e)}"}],
            "isError": True
        }


@tool(
    "write_file",
    "写入内容到文件。如果文件不存在会创建新文件，如果存在会覆盖原有内容。",
    {
        "file_path": str,
        "content": str,
    }
)
async def write_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """写入文件

    Args:
        file_path: 文件的绝对路径
        content: 要写入的内容

    Returns:
        操作结果
    """
    file_path = args.get("file_path")
    content = args.get("content", "")

    if not file_path:
        return {
            "content": [{"type": "text", "text": "错误：缺少 file_path 参数"}],
            "isError": True
        }

    try:
        path = _resolve_path(file_path)

        # 确保父目录存在
        path.parent.mkdir(parents=True, exist_ok=True)

        # 写入文件
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "content": [{"type": "text", "text": f"✓ 已写入文件: {path}"}],
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"写入文件失败: {str(e)}"}],
            "isError": True
        }


@tool(
    "edit_file",
    "编辑文件，通过精确的字符串替换来修改文件内容。必须提供 old_string（要替换的内容）和 new_string（替换后的内容）。",
    {
        "file_path": str,
        "old_string": str,
        "new_string": str,
        "replace_all": bool,
    }
)
async def edit_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """编辑文件（字符串替换）

    Args:
        file_path: 文件的绝对路径
        old_string: 要替换的字符串
        new_string: 替换后的字符串
        replace_all: 是否替换所有匹配项，默认为 False

    Returns:
        操作结果
    """
    file_path = args.get("file_path")
    old_string = args.get("old_string")
    new_string = args.get("new_string", "")
    replace_all = args.get("replace_all", False)

    if not file_path:
        return {
            "content": [{"type": "text", "text": "错误：缺少 file_path 参数"}],
            "isError": True
        }

    if old_string is None:
        return {
            "content": [{"type": "text", "text": "错误：缺少 old_string 参数"}],
            "isError": True
        }

    try:
        path = _resolve_path(file_path)

        if not path.exists():
            return {
                "content": [{"type": "text", "text": f"错误：文件不存在: {file_path}"}],
                "isError": True
            }

        # 读取文件内容
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # 检查 old_string 是否存在
        if old_string not in content:
            return {
                "content": [{"type": "text", "text": f"错误：未找到要替换的内容\n文件: {path}\n搜索内容:\n---\n{old_string}\n---"}],
                "isError": True
            }

        # 检查匹配次数
        count = content.count(old_string)
        if count > 1 and not replace_all:
            return {
                "content": [{"type": "text", "text": f"错误：找到 {count} 处匹配，但 replace_all=False。\n请提供更多上下文使匹配唯一，或设置 replace_all=True"}],
                "isError": True
            }

        # 执行替换
        if replace_all:
            new_content = content.replace(old_string, new_string)
            replaced_count = count
        else:
            new_content = content.replace(old_string, new_string, 1)
            replaced_count = 1

        # 写回文件
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return {
            "content": [{"type": "text", "text": f"✓ 已替换 {replaced_count} 处匹配\n文件: {path}"}],
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"编辑文件失败: {str(e)}"}],
            "isError": True
        }


@tool(
    "list_directory",
    "列出目录内容。返回目录中的文件和子目录列表。",
    {
        "path": str,
    }
)
async def list_directory(args: Dict[str, Any]) -> Dict[str, Any]:
    """列出目录内容

    Args:
        path: 目录路径，默认为当前工作目录

    Returns:
        目录内容列表
    """
    dir_path = args.get("path", ".")

    try:
        path = _resolve_path(dir_path)

        if not path.exists():
            return {
                "content": [{"type": "text", "text": f"错误：目录不存在: {dir_path}"}],
                "isError": True
            }

        if not path.is_dir():
            return {
                "content": [{"type": "text", "text": f"错误：路径不是目录: {dir_path}"}],
                "isError": True
            }

        # 获取目录内容
        items = []
        for item in sorted(path.iterdir()):
            if item.is_dir():
                items.append(f"📁 {item.name}/")
            else:
                size = item.stat().st_size
                if size < 1024:
                    size_str = f"{size} B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f} MB"
                items.append(f"📄 {item.name} ({size_str})")

        result = f"目录: {path}\n\n" + "\n".join(items)
        if not items:
            result += "(空目录)"

        return {
            "content": [{"type": "text", "text": result}],
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"列出目录失败: {str(e)}"}],
            "isError": True
        }