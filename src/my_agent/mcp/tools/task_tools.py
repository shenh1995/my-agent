"""Task 任务管理工具

提供任务管理功能，包括：
- 创建和管理结构化任务列表
- 启动子智能体并行执行复杂任务
- 追踪任务进度和依赖关系
- 支持后台任务执行
"""

import asyncio
import os
import time
from typing import Dict, Any, Optional, List

from claude_agent_sdk import tool
from claude_agent_sdk.types import ClaudeAgentOptions

from ... import get_startup_cwd
from ...task_manager import (
    TaskManager,
    TaskStatus,
    task_manager,
)


# 子智能体类型定义
SUBAGENT_TYPES = {
    "general-purpose": {
        "description": "通用任务代理，用于研究复杂问题、搜索代码和执行多步骤任务",
        "tools": "all",  # 所有工具
    },
    "Explore": {
        "description": "快速探索代码库的专用代理，用于查找文件、搜索代码或回答代码库问题",
        "tools": "read_only",  # 只读工具
    },
    "Plan": {
        "description": "软件架构代理，用于设计实现方案，识别关键文件并考虑架构权衡",
        "tools": "read_only",  # 只读工具
    },
}


@tool(
    "task_create",
    "创建一个新的结构化任务。用于跟踪和管理多步骤任务。",
    {
        "subject": str,
        "description": str,
        "activeForm": str,
    }
)
async def task_create(args: Dict[str, Any]) -> Dict[str, Any]:
    """创建新任务

    Args:
        subject: 任务标题（命令式，如"实现用户认证"）
        description: 详细描述，包括上下文和验收标准
        activeForm: 进行中时的显示文本（如"正在实现用户认证"）

    Returns:
        创建的任务信息
    """
    subject = args.get("subject", "")
    description = args.get("description", "")
    activeForm = args.get("activeForm")

    if not subject:
        return {
            "content": [{"type": "text", "text": "错误：缺少 subject 参数"}],
            "isError": True
        }

    if not description:
        return {
            "content": [{"type": "text", "text": "错误：缺少 description 参数"}],
            "isError": True
        }

    task = task_manager.create_task(
        subject=subject,
        description=description,
        activeForm=activeForm,
    )

    return {
        "content": [{
            "type": "text",
            "text": f"✓ 已创建任务 #{task.id}\n\n标题: {task.subject}\n描述: {task.description}\n状态: {task.status.value}"
        }],
    }


@tool(
    "task_update",
    "更新任务状态、标题、描述等。用于跟踪任务进度和依赖关系。",
    {
        "taskId": str,
        "status": str,
        "subject": str,
        "description": str,
        "owner": str,
        "activeForm": str,
        "addBlockedBy": list,
        "addBlocks": list,
        "metadata": dict,
    }
)
async def task_update(args: Dict[str, Any]) -> Dict[str, Any]:
    """更新任务

    Args:
        taskId: 任务ID
        status: 新状态 (pending, in_progress, completed, deleted)
        subject: 新标题
        description: 新描述
        owner: 执行者ID
        activeForm: 进行中时的显示文本
        addBlockedBy: 添加依赖的任务ID列表
        addBlocks: 添加被依赖的任务ID列表
        metadata: 要合并的元数据

    Returns:
        更新后的任务信息
    """
    task_id = args.get("taskId")

    if not task_id:
        return {
            "content": [{"type": "text", "text": "错误：缺少 taskId 参数"}],
            "isError": True
        }

    # 检查任务是否存在
    existing_task = task_manager.get_task(task_id)
    if not existing_task:
        return {
            "content": [{"type": "text", "text": f"错误：任务 #{task_id} 不存在"}],
            "isError": True
        }

    # 验证状态值
    status = args.get("status")
    if status and status not in ["pending", "in_progress", "completed", "deleted"]:
        return {
            "content": [{"type": "text", "text": f"错误：无效的状态值 '{status}'。有效值: pending, in_progress, completed, deleted"}],
            "isError": True
        }

    # 更新任务
    task = task_manager.update_task(
        task_id=task_id,
        status=status,
        subject=args.get("subject"),
        description=args.get("description"),
        owner=args.get("owner"),
        activeForm=args.get("activeForm"),
        addBlockedBy=args.get("addBlockedBy"),
        addBlocks=args.get("addBlocks"),
        metadata=args.get("metadata"),
    )

    if not task:
        return {
            "content": [{"type": "text", "text": f"错误：更新任务 #{task_id} 失败"}],
            "isError": True
        }

    # 构建响应
    response_parts = [f"✓ 已更新任务 #{task_id}", f"状态: {task.status.value}"]

    if task.blockedBy:
        response_parts.append(f"依赖: {', '.join('#' + d for d in task.blockedBy)}")

    if task.blocks:
        response_parts.append(f"阻塞: {', '.join('#' + d for d in task.blocks)}")

    return {
        "content": [{"type": "text", "text": "\n".join(response_parts)}],
    }


@tool(
    "task_list",
    "列出所有任务。用于查看整体进度和查找可用任务。",
    {}
)
async def task_list(args: Dict[str, Any]) -> Dict[str, Any]:
    """列出所有任务

    Returns:
        任务摘要列表
    """
    tasks = task_manager.list_tasks()

    if not tasks:
        return {
            "content": [{"type": "text", "text": "暂无任务。使用 task_create 创建新任务。"}],
        }

    # 构建任务列表
    lines = ["# 任务列表\n"]

    # 按状态分组
    by_status = {
        TaskStatus.PENDING: [],
        TaskStatus.IN_PROGRESS: [],
        TaskStatus.COMPLETED: [],
    }

    for task in tasks:
        if task.status in by_status:
            by_status[task.status].append(task)

    # 显示进行中的任务
    if by_status[TaskStatus.IN_PROGRESS]:
        lines.append("## 进行中")
        for task in by_status[TaskStatus.IN_PROGRESS]:
            owner_info = f" (执行者: {task.owner})" if task.owner else ""
            blocked_info = f" ⚠️ 被阻塞" if not task_manager.can_start_task(task.id) else ""
            lines.append(f"  #{task.id}: {task.subject}{owner_info}{blocked_info}")
        lines.append("")

    # 显示待处理的任务
    if by_status[TaskStatus.PENDING]:
        lines.append("## 待处理")
        for task in by_status[TaskStatus.PENDING]:
            blocked_info = f" ⚠️ 等待: #{', #'.join(task.blockedBy)}" if task.blockedBy else ""
            lines.append(f"  #{task.id}: {task.subject}{blocked_info}")
        lines.append("")

    # 显示已完成的任务
    if by_status[TaskStatus.COMPLETED]:
        lines.append("## 已完成")
        for task in by_status[TaskStatus.COMPLETED]:
            lines.append(f"  #{task.id}: {task.subject} ✓")
        lines.append("")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
    }


@tool(
    "task_get",
    "获取单个任务的完整详情。用于了解任务详情和依赖关系。",
    {"taskId": str}
)
async def task_get(args: Dict[str, Any]) -> Dict[str, Any]:
    """获取任务详情

    Args:
        taskId: 任务ID

    Returns:
        任务完整信息
    """
    task_id = args.get("taskId")

    if not task_id:
        return {
            "content": [{"type": "text", "text": "错误：缺少 taskId 参数"}],
            "isError": True
        }

    task = task_manager.get_task(task_id)

    if not task:
        return {
            "content": [{"type": "text", "text": f"错误：任务 #{task_id} 不存在"}],
            "isError": True
        }

    # 构建详情
    lines = [
        f"# 任务 #{task.id}",
        f"**标题**: {task.subject}",
        f"**状态**: {task.status.value}",
        "",
        f"**描述**: {task.description}",
    ]

    if task.activeForm:
        lines.append(f"**进行中显示**: {task.activeForm}")

    if task.owner:
        lines.append(f"**执行者**: {task.owner}")

    if task.blockedBy:
        lines.append(f"**依赖任务**: {', '.join('#' + d for d in task.blockedBy)}")

    if task.blocks:
        lines.append(f"**阻塞任务**: {', '.join('#' + d for d in task.blocks)}")

    if task.metadata:
        lines.append("\n**元数据**:")
        for key, value in task.metadata.items():
            lines.append(f"  - {key}: {value}")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
    }


@tool(
    "task_output",
    "获取后台任务的输出。用于检查后台运行任务的状态和结果。",
    {
        "taskId": str,
        "block": bool,
        "timeout": int,
    }
)
async def task_output(args: Dict[str, Any]) -> Dict[str, Any]:
    """获取后台任务输出

    Args:
        taskId: 任务ID
        block: 是否等待完成，默认为 true
        timeout: 最长等待时间（毫秒），默认 30000

    Returns:
        任务状态和输出
    """
    task_id = args.get("taskId")
    block = args.get("block", True)
    timeout = args.get("timeout", 30000)

    if not task_id:
        return {
            "content": [{"type": "text", "text": "错误：缺少 taskId 参数"}],
            "isError": True
        }

    bg_task = task_manager.get_background_task(task_id)

    if not bg_task:
        return {
            "content": [{"type": "text", "text": f"错误：后台任务 #{task_id} 不存在"}],
            "isError": True
        }

    # 如果需要等待完成
    if block and bg_task.status == "running" and bg_task.task:
        try:
            result = await asyncio.wait_for(
                bg_task.task,
                timeout=timeout / 1000
            )
            # 任务完成，更新状态
            task_manager.update_background_task(task_id, status="completed", result=str(result))
            bg_task = task_manager.get_background_task(task_id)
        except asyncio.TimeoutError:
            return {
                "content": [{
                    "type": "text",
                    "text": f"后台任务 #{task_id} 仍在运行中\n\n等待超时（{timeout}ms）。可以稍后再次查询或使用 block=false 检查状态。"
                }],
            }
        except asyncio.CancelledError:
            task_manager.update_background_task(task_id, status="cancelled")
            bg_task = task_manager.get_background_task(task_id)
        except Exception as e:
            task_manager.update_background_task(task_id, status="failed", error=str(e))
            bg_task = task_manager.get_background_task(task_id)

    # 构建响应
    lines = [
        f"# 后台任务 #{task_id}",
        f"**状态**: {bg_task.status}",
    ]

    if bg_task.result:
        lines.append(f"\n**结果**:\n{bg_task.result}")

    if bg_task.error:
        lines.append(f"\n**错误**:\n{bg_task.error}")

    if bg_task.output_file and os.path.exists(bg_task.output_file):
        lines.append(f"\n**输出文件**: {bg_task.output_file}")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
    }


@tool(
    "task_stop",
    "停止正在运行的后台任务。",
    {"taskId": str}
)
async def task_stop(args: Dict[str, Any]) -> Dict[str, Any]:
    """停止后台任务

    Args:
        taskId: 任务ID

    Returns:
        操作结果
    """
    task_id = args.get("taskId")

    if not task_id:
        return {
            "content": [{"type": "text", "text": "错误：缺少 taskId 参数"}],
            "isError": True
        }

    success = task_manager.stop_background_task(task_id)

    if success:
        return {
            "content": [{"type": "text", "text": f"✓ 已停止后台任务 #{task_id}"}],
        }
    else:
        return {
            "content": [{"type": "text", "text": f"错误：无法停止任务 #{task_id}（任务不存在或已完成）"}],
            "isError": True
        }


@tool(
    "task",
    "启动子智能体执行复杂任务。子智能体可以独立执行多步骤任务并返回结果。",
    {
        "description": str,
        "prompt": str,
        "subagent_type": str,
        "model": str,
        "run_in_background": bool,
        "isolation": str,
        "resume": str,
    }
)
async def task_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """启动子智能体执行任务

    Args:
        description: 简短描述（3-5词）
        prompt: 详细任务描述
        subagent_type: 智能体类型 (general-purpose, Explore, Plan)
        model: 可选的模型选择 (sonnet, opus, haiku)
        run_in_background: 是否后台运行
        isolation: 隔离模式 (worktree)
        resume: 恢复之前的智能体ID

    Returns:
        智能体ID和执行结果
    """
    description = args.get("description", "")
    prompt = args.get("prompt", "")
    subagent_type = args.get("subagent_type", "general-purpose")
    model = args.get("model")
    run_in_background = args.get("run_in_background", False)
    isolation = args.get("isolation")
    resume = args.get("resume")

    if not prompt:
        return {
            "content": [{"type": "text", "text": "错误：缺少 prompt 参数"}],
            "isError": True
        }

    # 验证子智能体类型
    if subagent_type not in SUBAGENT_TYPES:
        available = ", ".join(SUBAGENT_TYPES.keys())
        return {
            "content": [{"type": "text", "text": f"错误：未知的智能体类型 '{subagent_type}'\n可用类型: {available}"}],
            "isError": True
        }

    # 生成智能体ID
    agent_id = f"agent_{int(time.time() * 1000)}"

    try:
        # 导入必要的模块（延迟导入避免循环依赖）
        from claude_agent_sdk import query
        from claude_agent_sdk.types import ClaudeAgentOptions

        # 配置智能体选项
        options = ClaudeAgentOptions()

        # 设置工作目录为启动目录
        startup_cwd = get_startup_cwd()
        options.cwd = startup_cwd
        print(f"  子智能体工作目录: {startup_cwd}")

        # 设置模型
        if model:
            model_map = {
                "sonnet": "claude-sonnet-4-6",
                "opus": "claude-opus-4-6",
                "haiku": "claude-haiku-4-5-20251001",
            }
            options.model = model_map.get(model, model)

        # 根据智能体类型配置工具
        agent_config = SUBAGENT_TYPES[subagent_type]
        if agent_config["tools"] == "read_only":
            # 只读模式 - 只使用只读工具
            from ..server import create_read_only_mcp_server
            options.mcp_servers = {
                "read_only": create_read_only_mcp_server("read_only")
            }
            options.allowed_tools = [
                "read_file", "list_directory", "glob", "grep", "mcp__read_only__*"
            ]
        else:
            # 完整工具模式
            from ..server import create_builtin_mcp_server
            options.mcp_servers = {
                "builtin": create_builtin_mcp_server("builtin")
            }

        # 执行智能体的内部函数
        async def run_agent():
            result_parts = []
            async for message in query(prompt=prompt, options=options):
                # 收集结果
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            result_parts.append(block.text)
            return "\n".join(result_parts)

        if run_in_background:
            # 后台运行
            async_task = asyncio.create_task(run_agent())
            task_manager.register_background_task(agent_id, async_task)

            return {
                "content": [{
                    "type": "text",
                    "text": f"✓ 已在后台启动 {subagent_type} 智能体\n\n智能体ID: {agent_id}\n描述: {description or prompt[:50]}...\n\n使用 task_output 查询结果。"
                }],
            }
        else:
            # 同步执行
            result = await run_agent()

            return {
                "content": [{
                    "type": "text",
                    "text": f"✓ {subagent_type} 智能体执行完成\n\n**结果**:\n{result}"
                }],
                "agent_id": agent_id,
            }

    except ImportError as e:
        return {
            "content": [{"type": "text", "text": f"错误：无法导入必要的模块: {str(e)}"}],
            "isError": True
        }
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"执行智能体时出错: {str(e)}"}],
            "isError": True
        }


# 导出所有工具
__all__ = [
    "task_create",
    "task_update",
    "task_list",
    "task_get",
    "task_output",
    "task_stop",
    "task_tool",
    "SUBAGENT_TYPES",
]