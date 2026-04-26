"""
CompanionOS 守护进程
Accomplish daemon模式 - 文件监听 + 定时调度 + 后台任务
"""

import asyncio
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path


class FileWatcher:
    """文件监听器 - 基于轮询的文件变更检测"""

    def __init__(self, watch_dir: Path, callback: Callable = None, poll_interval: float = 2.0):
        self.watch_dir = watch_dir
        self.callback = callback
        self.poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None
        self._known_files: dict[str, float] = {}

    async def start(self):
        """启动文件监听"""
        self._running = True
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self._scan_directory()
        print(f"[FileWatcher] 监听目录: {self.watch_dir} (轮询间隔: {self.poll_interval}s)")
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self):
        """停止文件监听"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        print("[FileWatcher] 已停止")

    def _scan_directory(self):
        """扫描目录，记录当前文件状态"""
        if not self.watch_dir.exists():
            return
        for f in self.watch_dir.iterdir():
            if f.is_file():
                self._known_files[str(f)] = f.stat().st_mtime

    async def _poll_loop(self):
        """轮询检测文件变更"""
        while self._running:
            await asyncio.sleep(self.poll_interval)
            try:
                self._check_changes()
            except Exception as e:
                print(f"[FileWatcher] 检测异常: {e}")

    def _check_changes(self):
        """检查文件变更（新增、修改、删除）"""
        if not self.watch_dir.exists():
            return

        current_files: dict[str, float] = {}
        for f in self.watch_dir.iterdir():
            if not f.is_file():
                continue
            fpath = str(f)
            mtime = f.stat().st_mtime
            current_files[fpath] = mtime

            if fpath not in self._known_files:
                print(f"[FileWatcher] 新增文件: {f.name}")
                if self.callback:
                    self.callback("created", fpath)
            elif abs(mtime - self._known_files[fpath]) > 0.1:
                print(f"[FileWatcher] 文件修改: {f.name}")
                if self.callback:
                    self.callback("modified", fpath)

        for fpath in self._known_files:
            if fpath not in current_files:
                fname = Path(fpath).name
                print(f"[FileWatcher] 文件删除: {fname}")
                if self.callback:
                    self.callback("deleted", fpath)

        self._known_files = current_files


class CronScheduler:
    """定时调度器 - 基于简易cron表达式"""

    def __init__(self, check_interval: float = 10.0):
        self.tasks: list[dict] = []
        self._running = False
        self._task: asyncio.Task | None = None
        self.check_interval = check_interval

    def add_task(self, name: str, schedule: str, action: Callable, enabled: bool = True):
        """
        添加定时任务

        Args:
            name: 任务名称
            schedule: Cron表达式 (格式: "分 时 日 月 周"，*表示任意)
            action: 执行函数
            enabled: 是否启用
        """
        self.tasks.append({
            "name": name,
            "schedule": schedule,
            "action": action,
            "enabled": enabled,
            "last_run": None,
        })

    def remove_task(self, name: str):
        """移除定时任务"""
        self.tasks = [t for t in self.tasks if t["name"] != name]

    def list_tasks(self) -> list[dict]:
        """列出所有定时任务"""
        return [
            {"name": t["name"], "schedule": t["schedule"], "enabled": t["enabled"], "last_run": t["last_run"]}
            for t in self.tasks
        ]

    async def start(self):
        """启动调度器"""
        self._running = True
        print(f"[CronScheduler] 调度器启动 (检查间隔: {self.check_interval}s)")
        self._task = asyncio.create_task(self._schedule_loop())

    async def stop(self):
        """停止调度器"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        print("[CronScheduler] 已停止")

    def _parse_cron(self, expr: str) -> list[list[int]]:
        """解析cron表达式，返回 [分钟, 小时, 日, 月, 周] 的允许值列表"""
        fields = expr.strip().split()
        if len(fields) != 5:
            raise ValueError(f"无效的cron表达式: {expr}，需要5个字段")

        ranges = [
            (0, 59),   # 分钟
            (0, 23),   # 小时
            (1, 31),   # 日
            (1, 12),   # 月
            (0, 6),    # 周 (0=周日)
        ]

        result = []
        for i, field in enumerate(fields):
            low, high = ranges[i]
            if field == "*":
                result.append(list(range(low, high + 1)))
            else:
                values = []
                for part in field.split(","):
                    if "-" in part:
                        a, b = part.split("-")
                        values.extend(range(int(a), int(b) + 1))
                    else:
                        values.append(int(part))
                result.append(values)
        return result

    def _matches(self, parsed: list[list[int]], now: time.struct_time) -> bool:
        """检查当前时间是否匹配cron表达式"""
        checks = [
            now.tm_min in parsed[0],
            now.tm_hour in parsed[1],
            now.tm_mday in parsed[2],
            now.tm_mon in parsed[3],
            now.tm_wday in parsed[4],
        ]
        return all(checks)

    async def _schedule_loop(self):
        """调度主循环"""
        while self._running:
            await asyncio.sleep(self.check_interval)
            now = time.localtime()
            for task in self.tasks:
                if not task["enabled"]:
                    continue
                try:
                    parsed = self._parse_cron(task["schedule"])
                    if self._matches(parsed, now):
                        last_run = task.get("last_run")
                        if last_run:
                            last_dt = datetime.fromisoformat(last_run)
                            if datetime.now() - last_dt < timedelta(seconds=self.check_interval + 1):
                                continue
                        print(f"[CronScheduler] 执行定时任务: {task['name']}")
                        action = task["action"]
                        if asyncio.iscoroutinefunction(action):
                            await action()
                        else:
                            action()
                        task["last_run"] = datetime.now().isoformat()
                except Exception as e:
                    print(f"[CronScheduler] 任务 '{task['name']}' 执行失败: {e}")


class TaskQueue:
    """后台任务队列"""

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._workers: list[asyncio.Task] = []

    async def enqueue(self, name: str, action: Callable, priority: int = 0):
        """入队任务"""
        await self.queue.put({
            "name": name,
            "action": action,
            "priority": priority,
            "enqueued_at": datetime.now().isoformat(),
        })

    async def start(self):
        """启动工作线程"""
        self._running = True
        for i in range(self.max_concurrent):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
        print(f"[TaskQueue] 启动 {self.max_concurrent} 个工作线程")

    async def stop(self):
        """停止工作线程"""
        self._running = False
        for w in self._workers:
            w.cancel()
        self._workers.clear()
        print("[TaskQueue] 已停止")

    async def _worker(self, worker_id: int):
        """工作线程"""
        while self._running:
            try:
                task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                action = task["action"]
                if asyncio.iscoroutinefunction(action):
                    await action()
                else:
                    action()
            except TimeoutError:
                continue
            except Exception as e:
                print(f"[TaskQueue:Worker-{worker_id}] 任务执行失败: {e}")


class DaemonManager:
    """守护进程管理器"""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.file_watcher = FileWatcher(data_dir / "watch")
        self.cron_scheduler = CronScheduler()
        self.task_queue = TaskQueue()

    async def start(self):
        """启动所有守护服务"""
        await self.file_watcher.start()
        await self.cron_scheduler.start()
        await self.task_queue.start()
        print("[Daemon] 守护进程已启动")

    async def stop(self):
        """停止所有守护服务"""
        await self.file_watcher.stop()
        await self.cron_scheduler.stop()
        await self.task_queue.stop()
        print("[Daemon] 守护进程已停止")
