"""任务状态管理模块

提供任务管理功能，包括：
- 任务的创建、更新、删除
- 任务状态跟踪
- 任务依赖关系管理
- 后台任务管理
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELETED = "deleted"


@dataclass
class Task:
    """任务数据结构"""
    id: str
    subject: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    owner: Optional[str] = None
    blockedBy: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    activeForm: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "owner": self.owner,
            "blockedBy": self.blockedBy,
            "blocks": self.blocks,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "activeForm": self.activeForm,
        }

    def summary(self) -> Dict[str, Any]:
        """返回任务摘要（用于列表显示）"""
        return {
            "id": self.id,
            "subject": self.subject,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
            "owner": self.owner,
            "blockedBy": self.blockedBy,
        }


@dataclass
class BackgroundTask:
    """后台任务数据结构"""
    id: str
    task: Optional[asyncio.Task] = None
    output_file: Optional[str] = None
    status: str = "running"  # running, completed, failed, cancelled
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


class TaskManager:
    """全局任务管理器

    管理所有任务状态和后台任务执行
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._tasks: Dict[str, Task] = {}
        self._background_tasks: Dict[str, BackgroundTask] = {}
        self._task_counter = 0

    def _generate_id(self) -> str:
        """生成任务ID"""
        self._task_counter += 1
        return str(self._task_counter)

    def create_task(
        self,
        subject: str,
        description: str,
        activeForm: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Task:
        """创建新任务

        Args:
            subject: 任务标题（命令式）
            description: 详细描述
            activeForm: 进行中时的显示文本
            metadata: 额外元数据

        Returns:
            创建的任务对象
        """
        task_id = self._generate_id()
        task = Task(
            id=task_id,
            subject=subject,
            description=description,
            activeForm=activeForm,
            metadata=metadata or {},
        )
        self._tasks[task_id] = task
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务

        Args:
            task_id: 任务ID

        Returns:
            任务对象，不存在则返回 None
        """
        return self._tasks.get(task_id)

    def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        subject: Optional[str] = None,
        description: Optional[str] = None,
        owner: Optional[str] = None,
        activeForm: Optional[str] = None,
        addBlockedBy: Optional[List[str]] = None,
        addBlocks: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Task]:
        """更新任务

        Args:
            task_id: 任务ID
            status: 新状态
            subject: 新标题
            description: 新描述
            owner: 执行者
            activeForm: 进行中时的显示文本
            addBlockedBy: 添加依赖的任务ID
            addBlocks: 添加被依赖的任务ID
            metadata: 要合并的元数据

        Returns:
            更新后的任务对象，不存在则返回 None
        """
        task = self._tasks.get(task_id)
        if not task:
            return None

        if status is not None:
            task.status = TaskStatus(status)

        if subject is not None:
            task.subject = subject

        if description is not None:
            task.description = description

        if owner is not None:
            task.owner = owner

        if activeForm is not None:
            task.activeForm = activeForm

        if addBlockedBy:
            for dep_id in addBlockedBy:
                if dep_id not in task.blockedBy:
                    task.blockedBy.append(dep_id)

        if addBlocks:
            for dep_id in addBlocks:
                if dep_id not in task.blocks:
                    task.blocks.append(dep_id)

        if metadata:
            task.metadata.update(metadata)
            # 清除值为 None 的键
            task.metadata = {k: v for k, v in task.metadata.items() if v is not None}

        task.updated_at = time.time()
        return task

    def delete_task(self, task_id: str) -> bool:
        """删除任务（标记为 deleted）

        Args:
            task_id: 任务ID

        Returns:
            是否成功删除
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        task.status = TaskStatus.DELETED
        task.updated_at = time.time()
        return True

    def list_tasks(
        self,
        status: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> List[Task]:
        """列出任务

        Args:
            status: 过滤状态
            owner: 过滤执行者

        Returns:
            任务列表
        """
        tasks = list(self._tasks.values())

        # 过滤已删除的任务（除非明确要求）
        if status != "deleted":
            tasks = [t for t in tasks if t.status != TaskStatus.DELETED]

        if status:
            tasks = [t for t in tasks if t.status == TaskStatus(status)]

        if owner:
            tasks = [t for t in tasks if t.owner == owner]

        # 按 ID 排序
        tasks.sort(key=lambda t: int(t.id))
        return tasks

    def can_start_task(self, task_id: str) -> bool:
        """检查任务是否可以开始（所有依赖已完成）

        Args:
            task_id: 任务ID

        Returns:
            是否可以开始
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        for dep_id in task.blockedBy:
            dep_task = self._tasks.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False

        return True

    def get_available_tasks(self) -> List[Task]:
        """获取可以开始的任务（无依赖或依赖已完成）

        Returns:
            可用任务列表
        """
        available = []
        for task in self._tasks.values():
            if task.status == TaskStatus.PENDING and self.can_start_task(task.id):
                available.append(task)
        return available

    # ========== 后台任务管理 ==========

    def register_background_task(
        self,
        task_id: str,
        async_task: asyncio.Task,
        output_file: Optional[str] = None,
    ) -> BackgroundTask:
        """注册后台任务

        Args:
            task_id: 任务ID
            async_task: asyncio.Task 对象
            output_file: 输出文件路径

        Returns:
            BackgroundTask 对象
        """
        bg_task = BackgroundTask(
            id=task_id,
            task=async_task,
            output_file=output_file,
        )
        self._background_tasks[task_id] = bg_task
        return bg_task

    def get_background_task(self, task_id: str) -> Optional[BackgroundTask]:
        """获取后台任务

        Args:
            task_id: 任务ID

        Returns:
            BackgroundTask 对象
        """
        return self._background_tasks.get(task_id)

    def update_background_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[BackgroundTask]:
        """更新后台任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            result: 执行结果
            error: 错误信息

        Returns:
            更新后的 BackgroundTask 对象
        """
        bg_task = self._background_tasks.get(task_id)
        if not bg_task:
            return None

        if status is not None:
            bg_task.status = status

        if result is not None:
            bg_task.result = result

        if error is not None:
            bg_task.error = error

        if status in ("completed", "failed", "cancelled"):
            bg_task.completed_at = time.time()

        return bg_task

    def stop_background_task(self, task_id: str) -> bool:
        """停止后台任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功停止
        """
        bg_task = self._background_tasks.get(task_id)
        if not bg_task or not bg_task.task:
            return False

        if bg_task.status != "running":
            return False

        try:
            bg_task.task.cancel()
            bg_task.status = "cancelled"
            bg_task.completed_at = time.time()
            return True
        except Exception:
            return False

    def clear_completed_background_tasks(self) -> int:
        """清理已完成的后台任务

        Returns:
            清理的任务数量
        """
        to_remove = [
            task_id for task_id, bg_task in self._background_tasks.items()
            if bg_task.status in ("completed", "failed", "cancelled")
        ]
        for task_id in to_remove:
            del self._background_tasks[task_id]
        return len(to_remove)


# 全局单例
task_manager = TaskManager()