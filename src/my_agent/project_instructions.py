"""项目级指令支持

支持从项目目录中加载 CLAUDE.md 文件作为项目级指令。
指令会被注入到每次对话的系统提示中。

查找逻辑：
1. 从当前工作目录开始
2. 向上查找父目录，直到找到 CLAUDE.md 或到达根目录
3. 支持多个 CLAUDE.md 文件合并（子目录优先级更高）
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass


# 默认的指令文件名
DEFAULT_INSTRUCTION_FILE = "CLAUDE.md"

# 备选的指令文件名
ALT_INSTRUCTION_FILES = ["CLAUDE.md", ".claude.md", "claude.md"]

# 系统提示前缀
SYSTEM_PROMPT_PREFIX = """# 项目指令

以下是项目级别的自定义指令，请在所有后续交互中遵循这些指令：

"""

# 最大文件大小限制（防止读取超大文件）
MAX_FILE_SIZE = 100 * 1024  # 100KB


@dataclass
class InstructionFile:
    """指令文件信息"""
    path: str           # 文件路径
    content: str        # 文件内容
    relative_path: str  # 相对于工作目录的路径


def find_instruction_files(
    start_dir: str,
    max_depth: int = 10,
    stop_at_git_root: bool = True,
) -> List[InstructionFile]:
    """查找项目指令文件

    从 start_dir 开始，向上查找 CLAUDE.md 文件。

    Args:
        start_dir: 起始查找目录
        max_depth: 最大向上查找深度
        stop_at_git_root: 是否在 git 根目录停止

    Returns:
        找到的指令文件列表（按优先级从高到低排序，子目录优先）
    """
    found_files: List[InstructionFile] = []
    current_path = Path(start_dir).resolve()
    depth = 0

    # 记录起始目录用于计算相对路径
    start_path = Path(start_dir).resolve()

    while depth < max_depth:
        # 检查当前目录下的指令文件
        for filename in ALT_INSTRUCTION_FILES:
            file_path = current_path / filename
            if file_path.exists() and file_path.is_file():
                # 检查文件大小
                if file_path.stat().st_size > MAX_FILE_SIZE:
                    print(f"  \033[90m跳过过大的指令文件: {file_path}\033[0m")
                    continue

                try:
                    content = file_path.read_text(encoding='utf-8')
                    # 计算相对路径
                    try:
                        relative_path = str(file_path.relative_to(start_path))
                    except ValueError:
                        relative_path = str(file_path)

                    found_files.append(InstructionFile(
                        path=str(file_path),
                        content=content,
                        relative_path=relative_path,
                    ))
                    break  # 每个目录只取一个文件
                except Exception as e:
                    print(f"  \033[90m读取指令文件失败 {file_path}: {e}\033[0m")

        # 检查是否到达 git 根目录
        if stop_at_git_root and (current_path / '.git').exists():
            break

        # 移动到父目录
        parent = current_path.parent
        if parent == current_path:  # 到达根目录
            break
        current_path = parent
        depth += 1

    # 反转顺序，使子目录的指令优先级更高
    found_files.reverse()

    return found_files


def load_project_instructions(work_dir: str) -> Tuple[str, List[InstructionFile]]:
    """加载项目指令

    Args:
        work_dir: 工作目录

    Returns:
        (合并后的指令内容, 找到的指令文件列表)
    """
    instruction_files = find_instruction_files(work_dir)

    if not instruction_files:
        return "", []

    # 合并所有指令文件内容
    combined_parts = []

    for inst_file in instruction_files:
        # 添加文件来源注释
        combined_parts.append(f"<!-- 来源: {inst_file.relative_path} -->\n")
        combined_parts.append(inst_file.content)
        combined_parts.append("\n\n")

    combined_content = "".join(combined_parts)

    return combined_content, instruction_files


def build_system_prompt_with_instructions(
    instructions: str,
    user_prompt: str,
) -> str:
    """构建包含项目指令的系统提示

    Args:
        instructions: 项目指令内容
        user_prompt: 用户提示

    Returns:
        增强后的提示内容
    """
    if not instructions:
        return user_prompt

    return f"""{SYSTEM_PROMPT_PREFIX}

{instructions}

---

# 用户请求

{user_prompt}"""


def print_instruction_loading_info(instruction_files: List[InstructionFile]):
    """打印指令加载信息

    Args:
        instruction_files: 指令文件列表
    """
    if not instruction_files:
        return

    print("  \033[36m已加载项目指令:\033[0m")
    for inst_file in instruction_files:
        lines = inst_file.content.count('\n') + 1
        print(f"    \033[90m- {inst_file.relative_path} ({lines} 行)\033[0m")
    print()


class ProjectInstructionsManager:
    """项目指令管理器

    管理项目级别的 CLAUDE.md 指令文件。
    """

    def __init__(self, work_dir: str):
        """初始化管理器

        Args:
            work_dir: 工作目录
        """
        self.work_dir = work_dir
        self._instructions: Optional[str] = None
        self._instruction_files: Optional[List[InstructionFile]] = None
        self._loaded = False

    def load(self, force_reload: bool = False) -> str:
        """加载项目指令

        Args:
            force_reload: 是否强制重新加载

        Returns:
            合并后的指令内容
        """
        if self._loaded and not force_reload:
            return self._instructions or ""

        self._instructions, self._instruction_files = load_project_instructions(self.work_dir)
        self._loaded = True

        return self._instructions

    def get_instructions(self) -> str:
        """获取已加载的指令内容

        Returns:
            指令内容
        """
        if not self._loaded:
            self.load()
        return self._instructions or ""

    def get_instruction_files(self) -> List[InstructionFile]:
        """获取已加载的指令文件列表

        Returns:
            指令文件列表
        """
        if not self._loaded:
            self.load()
        return self._instruction_files or []

    def has_instructions(self) -> bool:
        """检查是否有项目指令

        Returns:
            是否有指令
        """
        if not self._loaded:
            self.load()
        return bool(self._instructions)

    def reload(self) -> str:
        """重新加载项目指令

        Returns:
            合并后的指令内容
        """
        return self.load(force_reload=True)

    def build_enhanced_prompt(self, user_prompt: str) -> str:
        """构建增强的提示

        Args:
            user_prompt: 用户提示

        Returns:
            包含项目指令的增强提示
        """
        instructions = self.get_instructions()
        if not instructions:
            return user_prompt

        return build_system_prompt_with_instructions(instructions, user_prompt)

    def print_info(self):
        """打印指令加载信息"""
        if not self._loaded:
            self.load()
        print_instruction_loading_info(self._instruction_files or [])


# 全局管理器实例
_global_manager: Optional[ProjectInstructionsManager] = None


def get_project_instructions_manager(work_dir: Optional[str] = None) -> ProjectInstructionsManager:
    """获取全局项目指令管理器

    Args:
        work_dir: 工作目录，如果为 None 则使用当前目录

    Returns:
        项目指令管理器实例
    """
    global _global_manager

    if work_dir is None:
        work_dir = os.getcwd()

    if _global_manager is None or _global_manager.work_dir != work_dir:
        _global_manager = ProjectInstructionsManager(work_dir)

    return _global_manager


def reload_project_instructions(work_dir: Optional[str] = None) -> str:
    """重新加载项目指令

    Args:
        work_dir: 工作目录

    Returns:
        合并后的指令内容
    """
    manager = get_project_instructions_manager(work_dir)
    return manager.reload()