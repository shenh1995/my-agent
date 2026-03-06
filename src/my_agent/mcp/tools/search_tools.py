"""MCP 搜索工具"""

import os
import re
import fnmatch
from pathlib import Path
from typing import Dict, Any, List

from claude_agent_sdk import tool


def _resolve_path(file_path: str, base_dir: str = None) -> Path:
    """解析文件路径"""
    path = Path(file_path)
    if not path.is_absolute():
        if base_dir:
            path = Path(base_dir) / path
        else:
            path = Path.cwd() / path
    return path.resolve()


@tool(
    "glob",
    "使用通配符模式搜索文件。支持 ** 递归匹配、* 匹配任意字符、? 匹配单个字符等模式。",
    {
        "pattern": str,
        "path": str,
    }
)
async def glob_files(args: Dict[str, Any]) -> Dict[str, Any]:
    """使用 glob 模式搜索文件

    Args:
        pattern: glob 模式，如 "*.py"、"**/*.txt"、"src/**/*.js"
        path: 搜索的起始目录，默认为当前工作目录

    Returns:
        匹配的文件列表
    """
    pattern = args.get("pattern", "*")
    search_path = args.get("path", ".")

    try:
        base_path = _resolve_path(search_path)

        if not base_path.exists():
            return {
                "content": [{"type": "text", "text": f"错误：目录不存在: {search_path}"}],
                "isError": True
            }

        if not base_path.is_dir():
            return {
                "content": [{"type": "text", "text": f"错误：路径不是目录: {search_path}"}],
                "isError": True
            }

        # 使用 pathlib 的 glob 功能
        matches = list(base_path.glob(pattern))

        # 按修改时间排序
        matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        # 格式化输出
        results = []
        for match in matches[:100]:  # 限制结果数量
            try:
                rel_path = match.relative_to(base_path)
                if match.is_dir():
                    results.append(f"📁 {rel_path}/")
                else:
                    results.append(f"📄 {rel_path}")
            except ValueError:
                results.append(f"📄 {match}")

        total = len(matches)
        shown = min(len(results), 100)

        output = f"模式: {pattern}\n目录: {base_path}\n找到 {total} 个匹配"
        if total > 100:
            output += f"（显示前 100 个）"
        output += "\n\n" + "\n".join(results[:100])

        return {
            "content": [{"type": "text", "text": output}],
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"搜索失败: {str(e)}"}],
            "isError": True
        }


@tool(
    "grep",
    "在文件内容中搜索匹配正则表达式的行。支持多种输出模式。",
    {
        "pattern": str,
        "path": str,
        "output_mode": str,
        "glob": str,
        "-i": bool,
        "-n": bool,
        "head_limit": int,
    }
)
async def grep_content(args: Dict[str, Any]) -> Dict[str, Any]:
    """在文件内容中搜索

    Args:
        pattern: 正则表达式模式
        path: 搜索的文件或目录路径
        output_mode: 输出模式 - "content" 显示匹配行, "files_with_matches" 只显示文件名, "count" 显示匹配计数
        glob: 文件名过滤模式，如 "*.py"、"*.js"
        -i: 是否忽略大小写
        -n: 是否显示行号
        head_limit: 结果数量限制

    Returns:
        搜索结果
    """
    pattern = args.get("pattern")
    search_path = args.get("path", ".")
    output_mode = args.get("output_mode", "content")
    glob_pattern = args.get("glob")
    ignore_case = args.get("-i", False)
    show_line_numbers = args.get("-n", True)
    head_limit = args.get("head_limit", 100)

    if not pattern:
        return {
            "content": [{"type": "text", "text": "错误：缺少 pattern 参数"}],
            "isError": True
        }

    try:
        base_path = _resolve_path(search_path)

        if not base_path.exists():
            return {
                "content": [{"type": "text", "text": f"错误：路径不存在: {search_path}"}],
                "isError": True
            }

        # 编译正则表达式
        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return {
                "content": [{"type": "text", "text": f"错误：无效的正则表达式: {e}"}],
                "isError": True
            }

        # 确定要搜索的文件
        files_to_search = []
        if base_path.is_file():
            files_to_search = [base_path]
        else:
            # 递归搜索目录
            for root, dirs, files in os.walk(base_path):
                # 跳过隐藏目录和常见的忽略目录
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__', 'venv', '.git')]

                for file in files:
                    file_path = Path(root) / file
                    if glob_pattern:
                        if fnmatch.fnmatch(file, glob_pattern):
                            files_to_search.append(file_path)
                    else:
                        files_to_search.append(file_path)

        # 搜索内容
        results = []
        files_with_matches = set()
        match_counts = {}

        for file_path in files_to_search[:1000]:  # 限制文件数量
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            files_with_matches.add(file_path)
                            match_counts[str(file_path)] = match_counts.get(str(file_path), 0) + 1

                            if output_mode == "content" and len(results) < head_limit:
                                rel_path = file_path.relative_to(base_path) if file_path.is_relative_to(base_path) else file_path
                                if show_line_numbers:
                                    results.append(f"{rel_path}:{line_num}:{line.rstrip()}")
                                else:
                                    results.append(f"{rel_path}:{line.rstrip()}")

            except (IOError, OSError):
                continue

        # 格式化输出
        if output_mode == "files_with_matches":
            output_lines = [str(f.relative_to(base_path) if f.is_relative_to(base_path) else f) for f in sorted(files_with_matches)]
            output = f"模式: {pattern}\n目录: {base_path}\n找到 {len(files_with_matches)} 个匹配文件\n\n" + "\n".join(output_lines[:head_limit])
        elif output_mode == "count":
            output_lines = [f"{f}: {c}" for f, c in sorted(match_counts.items())]
            output = f"模式: {pattern}\n目录: {base_path}\n匹配计数:\n\n" + "\n".join(output_lines[:head_limit])
        else:
            output = f"模式: {pattern}\n目录: {base_path}\n找到 {len(files_with_matches)} 个文件，{sum(match_counts.values())} 处匹配\n\n" + "\n".join(results[:head_limit])

        return {
            "content": [{"type": "text", "text": output}],
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"搜索失败: {str(e)}"}],
            "isError": True
        }