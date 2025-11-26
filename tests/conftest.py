"""Pytest configuration and fixtures."""

import asyncio
import pytest
from pathlib import Path
from typing import AsyncGenerator, Generator

from browser_research_agent.tools import ProxyCapture, BrowserController, SiteAnalyzer
from browser_research_agent.agent.tools import AgentToolkit


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Temporary data directory."""
    data = tmp_path / "data"
    data.mkdir()
    return data


@pytest.fixture
def analyzer() -> SiteAnalyzer:
    """Site analyzer instance."""
    return SiteAnalyzer()


@pytest.fixture
async def proxy() -> AsyncGenerator[ProxyCapture, None]:
    """Proxy capture instance (not started)."""
    proxy = ProxyCapture(port=18080)  # Use non-standard port for tests
    yield proxy
    try:
        await proxy.stop()
    except Exception:
        pass


@pytest.fixture
async def browser() -> AsyncGenerator[BrowserController, None]:
    """Browser controller instance (not started)."""
    browser = BrowserController(headless=True)
    yield browser
    try:
        await browser.stop()
    except Exception:
        pass


@pytest.fixture
def toolkit() -> AgentToolkit:
    """Agent toolkit instance."""
    return AgentToolkit()
