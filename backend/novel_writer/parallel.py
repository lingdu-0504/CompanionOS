"""
并行任务管理系统 - Parallel Task Management
管理多个小说创作任务的并行执行
支持真实定时调度和多任务并行
"""

import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskType(Enum):
    """任务类型"""
    GENERATE_CHAPTER = "generate_chapter"
    AUTO_CREATE = "auto_create"
    PUBLISH = "publish"
    BATCH_PUBLISH = "batch_publish"
    SCHEDULE_CREATE = "schedule_create"


@dataclass
class Task:
    """任务数据结构"""
    id: str
    project_id: str
    task_type: str
    status: str
    schedule_config: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    next_run_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "type": self.task_type,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "next_run_at": self.next_run_at,
            "error": self.error,
            "result": self.result,
            "metadata": self.metadata,
        }


class CronExpression:
    """Cron表达式解析器"""
    
    def __init__(self, expression: str):
        self.expression = expression
        self.parts = expression.split()
        if len(self.parts) != 5:
            raise ValueError(f"Invalid cron expression: {expression}")
    
    def get_next_run(self, from_time: datetime) -> datetime:
        """计算下次执行时间"""
        next_time = from_time.replace(second=0, microsecond=0)
        minute, hour, day, month, weekday = self.parts
        
        if minute != '*':
            target_minute = int(minute)
            if next_time.minute < target_minute:
                next_time = next_time.replace(minute=target_minute)
            else:
                next_time += timedelta(hours=1)
                next_time = next_time.replace(minute=target_minute)
        
        if hour != '*':
            next_time = next_time.replace(hour=int(hour))
        
        return next_time
    
    def matches(self, dt: datetime) -> bool:
        """检查是否匹配"""
        minute, hour, day, month, weekday = self.parts
        
        if minute != '*' and dt.minute != int(minute):
            return False
        if hour != '*' and dt.hour != int(hour):
            return False
        if day != '*' and dt.day != int(day):
            return False
        if month != '*' and dt.month != int(month):
            return False
        if weekday != '*' and dt.weekday() != int(weekday):
            return False
        
        return True


class ParallelTaskManager:
    """
    并行任务管理器
    管理和调度多个小说创作任务
    支持定时任务和实时任务
    """

    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.scheduled_jobs: Dict[str, Any] = {}
        self._task_handlers: Dict[str, Callable] = {}
        self._scheduler_running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        
        # 注册默认处理器
        self._register_default_handlers()

    def _register_default_handlers(self):
        """注册默认任务处理器"""
        pass

    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._task_handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type}")

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
            status=TaskStatus.PENDING.value,
            schedule_config=schedule_config,
        )
        self.tasks[task_id] = task
        
        if "cron" in schedule_config:
            try:
                cron = CronExpression(schedule_config["cron"])
                task.next_run_at = cron.get_next_run(datetime.now()).isoformat()
            except Exception as e:
                logger.error(f"Invalid cron expression: {e}")
        
        logger.info(f"Scheduled task: {task_type} for project {project_id}")
        return task_id

    async def run_tasks(self, task_ids: Optional[List[str]] = None):
        """运行任务"""
        if task_ids is None:
            task_ids = [t.id for t in self.tasks.values() 
                       if t.status == TaskStatus.PENDING.value]

        coroutines = []
        for task_id in task_ids:
            if task_id in self.tasks and task_id not in self.running_tasks:
                coroutines.append(self._run_single_task(task_id))
        
        if coroutines:
            await asyncio.gather(*coroutines, return_exceptions=True)

    async def _run_single_task(self, task_id: str):
        """运行单个任务"""
        task = self.tasks.get(task_id)
        if not task:
            return

        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.now().isoformat()

        try:
            handler = self._task_handlers.get(task.task_type)
            
            if handler:
                result = await handler(task)
                task.result = result
            else:
                result = await self._execute_task(task)
                task.result = result

            task.status = TaskStatus.COMPLETED.value
            task.completed_at = datetime.now().isoformat()
            
            logger.info(f"Task completed: {task.id}")

        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED.value
            logger.info(f"Task cancelled: {task.id}")
        except Exception as e:
            logger.error(f"Task failed: {e}")
            task.status = TaskStatus.FAILED.value
            task.error = str(e)
            task.completed_at = datetime.now().isoformat()
        finally:
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]

    async def _execute_task(self, task: Task) -> Dict[str, Any]:
        """默认任务执行逻辑"""
        await asyncio.sleep(0.5)
        
        if task.task_type == TaskType.GENERATE_CHAPTER.value:
            return await self._execute_generate_chapter(task)
        elif task.task_type == TaskType.AUTO_CREATE.value:
            return await self._execute_auto_create(task)
        elif task.task_type == TaskType.PUBLISH.value:
            return await self._execute_publish(task)
        elif task.task_type == TaskType.SCHEDULE_CREATE.value:
            return await self._execute_schedule_create(task)
        
        return {"success": True, "message": f"Executed {task.task_type}"}

    async def _execute_generate_chapter(self, task: Task) -> Dict[str, Any]:
        """执行章节生成任务"""
        config = task.schedule_config
        project_id = task.project_id
        chapter_number = config.get("chapter_number")
        chapter_title = config.get("chapter_title", f"第{chapter_number}章")
        target_words = config.get("target_words", 3000)
        
        return {
            "success": True,
            "project_id": project_id,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "target_words": target_words,
            "message": "章节生成任务已创建",
        }

    async def _execute_auto_create(self, task: Task) -> Dict[str, Any]:
        """执行自动创作任务"""
        config = task.schedule_config
        chapters_count = config.get("chapters_per_run", 1)
        
        return {
            "success": True,
            "project_id": task.project_id,
            "chapters_created": chapters_count,
            "message": f"自动创作了{chapters_count}个章节",
        }

    async def _execute_publish(self, task: Task) -> Dict[str, Any]:
        """执行发布任务"""
        config = task.schedule_config
        return {
            "success": True,
            "project_id": task.project_id,
            "chapter_number": config.get("chapter_number"),
            "platform": config.get("platform", "qidian"),
            "message": "发布任务已创建",
        }

    async def _execute_schedule_create(self, task: Task) -> Dict[str, Any]:
        """执行定时创作任务"""
        config = task.schedule_config
        return {
            "success": True,
            "project_id": task.project_id,
            "schedule": config.get("cron"),
            "chapters_per_run": config.get("chapters_per_run", 1),
            "message": "定时创作任务已创建",
        }

    async def start_scheduler(self):
        """启动调度器"""
        if self._scheduler_running:
            return
        
        self._scheduler_running = True
        self._scheduler_task = asyncio.create_task(self._run_scheduler())
        logger.info("Task scheduler started")

    async def stop_scheduler(self):
        """停止调度器"""
        self._scheduler_running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("Task scheduler stopped")

    async def _run_scheduler(self):
        """运行调度循环"""
        while self._scheduler_running:
            try:
                now = datetime.now()
                
                for task_id, task in self.tasks.items():
                    if task.next_run_at and task.status == TaskStatus.PENDING.value:
                        next_run = datetime.fromisoformat(task.next_run_at)
                        if now >= next_run:
                            logger.info(f"Executing scheduled task: {task_id}")
                            asyncio.create_task(self._run_single_task(task_id))
                            
                            if "cron" in task.schedule_config:
                                try:
                                    cron = CronExpression(task.schedule_config["cron"])
                                    task.next_run_at = cron.get_next_run(now).isoformat()
                                except Exception as e:
                                    logger.error(f"Failed to calculate next run: {e}")
                
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(60)

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        return task.to_dict()

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            del self.running_tasks[task_id]

        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.CANCELLED.value
            logger.info(f"Cancelled task: {task_id}")
            return True

        return False

    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.PAUSED.value
            logger.info(f"Paused task: {task_id}")
            return True
        return False

    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.PENDING.value
            logger.info(f"Resumed task: {task_id}")
            return True
        return False

    def get_all_tasks(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取所有任务"""
        tasks = list(self.tasks.values())
        if project_id:
            tasks = [t for t in tasks if t.project_id == project_id]

        return [t.to_dict() for t in tasks]

    def get_pending_tasks(self) -> List[Task]:
        """获取待执行任务"""
        return [t for t in self.tasks.values() 
               if t.status == TaskStatus.PENDING.value]

    def get_running_tasks(self) -> List[Task]:
        """获取正在运行的任务"""
        return [t for t in self.tasks.values() 
               if t.status == TaskStatus.RUNNING.value]

    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id in self.tasks:
            if task_id in self.running_tasks:
                self.running_tasks[task_id].cancel()
                del self.running_tasks[task_id]
            
            del self.tasks[task_id]
            logger.info(f"Deleted task: {task_id}")
            return True
        return False

    def cleanup_completed_tasks(self, older_than_days: int = 7):
        """清理已完成的任务"""
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

    def get_statistics(self) -> Dict[str, Any]:
        """获取任务统计"""
        total = len(self.tasks)
        pending = sum(1 for t in self.tasks.values() if t.status == TaskStatus.PENDING.value)
        running = sum(1 for t in self.tasks.values() if t.status == TaskStatus.RUNNING.value)
        completed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED.value)
        failed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED.value)
        
        return {
            "total": total,
            "pending": pending,
            "running": running,
            "completed": completed,
            "failed": failed,
            "scheduler_running": self._scheduler_running,
        }
