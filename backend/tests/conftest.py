"""
CompanionOS E2E测试 - 公共固件
启动真实FastAPI服务，使用httpx AsyncClient进行HTTP测试
"""

import sys
from pathlib import Path

# 将项目根目录加入 sys.path，确保能 import server
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from server import app


@pytest.fixture(scope="session")
def event_loop():
    """创建session级别的事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """创建AsyncClient，使用ASGI传输直接调用FastAPI"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
