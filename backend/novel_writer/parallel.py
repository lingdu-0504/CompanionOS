"""
并行任务管理系统 - Parallel Task Management
管理多个小说创作任务的并行执行
"""

import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Task:
    """任务数据结构"""
    id: str
    project_id: str
    task_type: str
    status: str  # pending, running, completed, failed, cancelled
    schedule_config: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ParallelTaskManager:
    """
    并行任务管理器
    管理和调度多个小说创作任务
    """

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.scheduled_jobs: Dict[str, Any] = {}  # 定时任务

    async def schedule_task(
        self,
        task_type: str,
        project_id: str,
        schedule_config: Dict[str, Any],
    ) -> str:
        """安排新任务"""
        task_id = str(uuid.uuid4())
        task = Task(
            id=task_id,
            project_id=project_id,
            task_type=task_type,
            status="pending",
            schedule_config=schedule_config,
        )
        self.tasks[task_id] = task
        logger.info(f"Scheduled task: {task_type} for project {project_id}")
        return task_id

    async def run_tasks(self, task_ids: Optional[List[str]] = None):
        """运行任务"""
        if task_ids is None:
            # 运行所有 pending 任务
            task_ids = [t.id for t in self.tasks.values() if t.status == "pending"]

        for task_id in task_ids:
            if task_id in self.tasks and task_id not in self.running_tasks:
                await self._run_single_task(task_id)

    async def _run_single_task(self, task_id: str):
        """运行单个任务"""
        task = self.tasks.get(task_id)
        if not task:
            return

        task.status = "running"
        task.started_at = datetime.now().isoformat()

        try:
            # 创建异步任务
            async_task = asyncio.create_task(
                self._execute_task(task)
            )
            self.running_tasks[task_id] = async_task
            await async_task

        except Exception as e:
            logger.error(f"Task failed: {e}")
            task.status = "failed"
            task.error = str(e)
        finally:
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]

    async def _execute_task(self, task: Task):
        """执行任务（实际逻辑）"""
        # 这里应该根据 task_type 执行不同的操作
        # 例如：自动创建章节、发布到平台等

        # 模拟任务执行
        await asyncio.sleep(2)

        # 任务完成
        task.status = "completed"
        task.completed_at = datetime.now().isoformat()
        task.result = {"success": True, "message": "Task completed"}
        logger.info(f"Task completed: {task.id}")

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        if not task:
            return None

        return {
            "id": task.id,
            "project_id": task.project_id,
            "type": task.task_type,
            "status": task.status,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "error": task.error,
            "result": task.result,
        }

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            del self.running_tasks[task_id]

        if task_id in self.tasks:
            self.tasks[task_id].status = "cancelled"
            logger.info(f"Cancelled task: {task_id}")
            return True

        return False

    def get_all_tasks(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取所有任务"""
        tasks = list(self.tasks.values())
        if project_id:
            tasks = [t for t in tasks if t.project_id == project_id]

        return [
            {
                "id": t.id,
                "project_id": t.project_id,
                "type": t.task_type,
                "status": t.status,
                "created_at": t.created_at,
            }
            for t in tasks
        ]

    async def schedule_auto_creation(
        self,
        project_id: str,
        schedule: str,  # cron expression
        chapters_per_run: int = 1,
    ) -> str:
        """安排自动创作任务"""
        # 这是一个简化的实现
        # 实际应用中应该使用类似 APScheduler 的库
        task_id = await self.schedule_task(
            task_type="auto_create",
            project_id=project_id,
            schedule_config={
                "cron": schedule,
                "chapters_per_run": chapters_per_run,
            },
        )
        return task_id

    def cleanup_completed_tasks(self, older_than_days: int = 7):
        """清理已完成的任务"""
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=older_than_days)
        to_remove = []

        for task_id, task in self.tasks.items():
            if task.completed_at:
                completed_at = datetime.fromisoformat(task.completed_at)
                if completed_at < cutoff:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self.tasks[task_id]
            logger.info(f"Cleaned up task: {task_id}")
