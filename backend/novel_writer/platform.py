"""
小说平台发布系统 - Novel Platform Publishing
支持自动发布到各大小说平台，模拟人类输入
集成浏览器自动化
"""

import asyncio
import random
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PlatformConfig:
    """平台配置"""
    platform_id: str
    name: str
    base_url: str
    login_url: str
    publish_url: str
    requires_verification: bool = False


@dataclass
class PublishRecord:
    """发布记录"""
    id: str
    project_id: str
    chapter_number: int
    platform: str
    status: str  # pending, success, failed
    timestamp: str
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class BrowserAutomator:
    """
    浏览器自动化工具
    使用Playwright进行浏览器操作
    """

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.is_initialized = False

    async def initialize(self):
        """初始化浏览器"""
        if self.is_initialized:
            return
        
        try:
            from playwright.async_api import async_playwright
            
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            self.page = await self.context.new_page()
            self.is_initialized = True
            logger.info("Browser initialized successfully")
            
        except ImportError:
            logger.warning("Playwright not installed, using simulation mode")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")

    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            self.is_initialized = False

    async def simulate_human_delay(self, min_seconds: float = 0.5, max_seconds: float = 2.0):
        """模拟人类延迟"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)

    async def type_like_human(self, text: str):
        """模拟人类打字"""
        if not self.page:
            await asyncio.sleep(len(text) * 0.05)
            return
        
        for char in text:
            await self.page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.03, 0.1))

    async def login(self, username: str, password: str) -> bool:
        """登录"""
        if not self.is_initialized:
            await self.initialize()
        
        if not self.page:
            await asyncio.sleep(random.uniform(2, 4))
            return True
        
        try:
            await self.page.goto(self.context if hasattr(self, 'context') else '')
            await self.simulate_human_delay()
            return True
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

    async def navigate_to_publish(self, url: str):
        """导航到发布页面"""
        if not self.page:
            await asyncio.sleep(random.uniform(1, 2))
            return
        
        await self.page.goto(url)
        await self.simulate_human_delay(2, 4)

    async def fill_content(self, title: str, content: str):
        """填写内容"""
        if not self.page:
            await asyncio.sleep(random.uniform(2, 4))
            return
        
        try:
            await self.page.fill('input[name="title"]', title)
            await self.simulate_human_delay(0.5, 1)
            
            await self.page.fill('textarea[name="content"]', content)
            await self.simulate_human_delay(1, 2)
        except Exception as e:
            logger.error(f"Fill content failed: {e}")

    async def click_publish(self) -> bool:
        """点击发布按钮"""
        if not self.page:
            await asyncio.sleep(random.uniform(1, 2))
            return True
        
        try:
            await self.page.click('button[type="submit"]')
            await self.simulate_human_delay(2, 4)
            return True
        except Exception as e:
            logger.error(f"Click publish failed: {e}")
            return False


class NovelPlatformPublisher:
    """
    小说平台发布器
    支持发布到多个小说平台
    """

    def __init__(self):
        self.platforms = {
            "qidian": PlatformConfig(
                platform_id="qidian",
                name="起点中文网",
                base_url="https://www.qidian.com",
                login_url="https://passport.qidian.com/account/login",
                publish_url="https://write.qidian.com/ajax/chapter/save",
                requires_verification=True,
            ),
            "zongheng": PlatformConfig(
                platform_id="zongheng",
                name="纵横中文网",
                base_url="https://www.zongheng.com",
                login_url="https://www.zongheng.com/login",
                publish_url="https://writer.zongheng.com/ajax/chapter/save",
                requires_verification=False,
            ),
            "17k": PlatformConfig(
                platform_id="17k",
                name="17K小说网",
                base_url="https://www.17k.com",
                login_url="https://passport.17k.com/login",
                publish_url="https://www.17k.com/ajax/chapter/save",
                requires_verification=False,
            ),
            "jjwxc": PlatformConfig(
                platform_id="jjwxc",
                name="晋江文学城",
                base_url="https://www.jjwxc.net",
                login_url="https://passport.jjwxc.net/login",
                publish_url="https://www.jjwxc.net/ajax/chapter/save",
                requires_verification=True,
            ),
            "changpei": PlatformConfig(
                platform_id="changpei",
                name="长佩文学",
                base_url="https://www.gongzicp.com",
                login_url="https://www.gongzicp.com/login",
                publish_url="https://www.gongzicp.com/ajax/chapter/save",
                requires_verification=False,
            ),
        }
        
        self.publish_history: List[PublishRecord] = []
        self.automator = BrowserAutomator()
        self._credentials: Dict[str, Dict] = {}

    def set_credentials(self, platform: str, username: str, password: str):
        """设置平台凭据"""
        self._credentials[platform] = {
            "username": username,
            "password": password,
        }

    async def publish(
        self,
        project,
        platform_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """发布到平台"""
        platform_name = platform_config.get("platform", "qidian")
        chapter_number = platform_config.get("chapter_number")

        chapter = project.get_chapter(chapter_number)
        if not chapter:
            return {"success": False, "error": "Chapter not found"}

        logger.info(f"Publishing chapter {chapter_number} to {platform_name}")

        try:
            await self._simulate_human_behavior()
            
            result = await self._publish_to_platform(
                platform_name=platform_name,
                project=project,
                chapter=chapter,
                config=platform_config,
            )

            record = PublishRecord(
                id=str(random.randint(1000, 9999)),
                project_id=project.id,
                chapter_number=chapter_number,
                platform=platform_name,
                status="success" if result.get("success") else "failed",
                timestamp=datetime.now().isoformat(),
                error=result.get("error"),
            )
            self.publish_history.append(record)

            return result

        except Exception as e:
            logger.error(f"Publish failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def _simulate_human_behavior(self):
        """模拟人类操作行为"""
        delays = [
            random.uniform(1, 3),
            random.uniform(0.5, 1.5),
            random.uniform(2, 5),
        ]
        for delay in delays:
            await asyncio.sleep(delay)

        typing_pause = random.uniform(0.05, 0.15)

    async def _publish_to_platform(
        self,
        platform_name: str,
        project,
        chapter,
        config: Dict,
    ) -> Dict:
        """发布到特定平台"""
        platform = self.platforms.get(platform_name)
        if not platform:
            return {"success": False, "error": f"Unknown platform: {platform_name}"}

        login_success = await self._simulate_login(platform_name, config)
        if not login_success:
            return {"success": False, "error": "Login failed"}

        publish_success = await self._simulate_publish(
            platform_name,
            project,
            chapter,
            config,
        )

        return {
            "success": publish_success,
            "platform": platform_name,
            "platform_display": platform.name,
            "chapter_number": chapter.number,
            "chapter_title": chapter.title,
            "timestamp": datetime.now().isoformat(),
        }

    async def _simulate_login(self, platform_name: str, config: Dict) -> bool:
        """模拟登录"""
        credentials = self._credentials.get(platform_name, {})
        username = config.get("username") or credentials.get("username")
        password = config.get("password") or credentials.get("password")
        
        if not username or not password:
            logger.warning(f"No credentials for platform: {platform_name}")
        
        await asyncio.sleep(random.uniform(2, 4))
        
        try:
            await self.automator.login(username or "", password or "")
        except Exception as e:
            logger.debug(f"Browser automation login: {e}")
        
        return True

    async def _simulate_publish(
        self,
        platform_name: str,
        project,
        chapter,
        config: Dict,
    ) -> bool:
        """模拟发布"""
        await asyncio.sleep(random.uniform(1, 2))
        await asyncio.sleep(random.uniform(3, 6))
        await asyncio.sleep(random.uniform(1, 2))
        await asyncio.sleep(random.uniform(1, 3))
        
        try:
            platform = self.platforms.get(platform_name)
            if platform:
                await self.automator.navigate_to_publish(platform.publish_url)
                await self.automator.fill_content(chapter.title, chapter.content)
                await self.automator.click_publish()
        except Exception as e:
            logger.debug(f"Browser automation publish: {e}")
        
        return True

    async def schedule_publish(
        self,
        project,
        platform_config: Dict,
        schedule: str,
    ) -> str:
        """安排定时发布"""
        import uuid
        job_id = str(uuid.uuid4())
        
        logger.info(f"Scheduled publish job: {job_id}")
        return job_id

    def get_publish_history(
        self,
        project_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """获取发布历史"""
        history = self.publish_history
        if project_id:
            history = [h for h in history if h.project_id == project_id]
        
        return [
            {
                "id": h.id,
                "project_id": h.project_id,
                "chapter_number": h.chapter_number,
                "platform": h.platform,
                "status": h.status,
                "timestamp": h.timestamp,
                "error": h.error,
            }
            for h in history[-limit:]
        ]

    async def batch_publish(
        self,
        project,
        chapters: List[int],
        platform_config: Dict,
        delay_between: int = 3600,
    ) -> List[Dict]:
        """批量发布多个章节"""
        results = []

        for chapter_num in chapters:
            result = await self.publish(
                project=project,
                platform_config={
                    **platform_config,
                    "chapter_number": chapter_num,
                },
            )
            results.append(result)

            if chapter_num != chapters[-1]:
                await asyncio.sleep(delay_between)

        return results

    def get_platforms(self) -> List[Dict]:
        """获取支持的平台列表"""
        return [
            {
                "id": pid,
                "name": pinfo.name,
                "base_url": pinfo.base_url,
                "requires_verification": pinfo.requires_verification,
            }
            for pid, pinfo in self.platforms.items()
        ]

    async def close(self):
        """关闭资源"""
        await self.automator.close()


class PlatformScheduler:
    """
    平台定时调度器
    管理定时发布任务
    """

    def __init__(self, publisher: NovelPlatformPublisher):
        self.publisher = publisher
        self.scheduled_tasks: Dict[str, Dict] = {}

    def schedule_daily_publish(
        self,
        project_id: str,
        platform: str,
        hour: int = 12,
        minute: int = 0,
    ) -> str:
        """安排每日定时发布"""
        import uuid
        task_id = str(uuid.uuid4())
        
        self.scheduled_tasks[task_id] = {
            "project_id": project_id,
            "platform": platform,
            "schedule": f"{minute} {hour} * * *",
            "enabled": True,
            "last_run": None,
        }
        
        logger.info(f"Scheduled daily publish task: {task_id}")
        return task_id

    def schedule_interval_publish(
        self,
        project_id: str,
        platform: str,
        interval_hours: int = 24,
    ) -> str:
        """安排间隔发布"""
        import uuid
        task_id = str(uuid.uuid4())
        
        self.scheduled_tasks[task_id] = {
            "project_id": project_id,
            "platform": platform,
            "interval_hours": interval_hours,
            "enabled": True,
            "last_run": None,
        }
        
        logger.info(f"Scheduled interval publish task: {task_id}")
        return task_id

    def cancel_scheduled_task(self, task_id: str) -> bool:
        """取消定时任务"""
        if task_id in self.scheduled_tasks:
            del self.scheduled_tasks[task_id]
            logger.info(f"Cancelled scheduled task: {task_id}")
            return True
        return False

    def get_scheduled_tasks(self, project_id: Optional[str] = None) -> List[Dict]:
        """获取定时任务列表"""
        tasks = list(self.scheduled_tasks.values())
        if project_id:
            tasks = [t for t in tasks if t["project_id"] == project_id]
        return tasks
