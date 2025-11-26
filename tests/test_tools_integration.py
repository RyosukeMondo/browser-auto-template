"""Integration tests for browser tools.

These tests require actual browser/proxy - skip in CI without proper setup.
"""

import pytest
from pathlib import Path

from browser_research_agent.agent.tools import AgentToolkit, execute_tool


@pytest.mark.asyncio
class TestToolExecution:
    async def test_start_research_session(self, toolkit: AgentToolkit) -> None:
        result = await execute_tool(
            toolkit,
            "start_research_session",
            {
                "target_url": "https://example.com",
                "objective": "Test session",
            },
        )

        assert result["success"] is True
        assert "session_id" in result
        assert toolkit.session is not None
        assert toolkit.session.target_url == "https://example.com"

    async def test_tool_requires_browser(self, toolkit: AgentToolkit) -> None:
        # Tools that need browser should fail gracefully
        result = await execute_tool(toolkit, "navigate", {"url": "https://example.com"})
        assert result["success"] is False
        assert "error" in result
        assert "Browser not started" in result["error"]

    async def test_tool_requires_proxy(self, toolkit: AgentToolkit) -> None:
        result = await execute_tool(toolkit, "get_captured_requests", {})
        assert result["success"] is False
        assert "Proxy not started" in result["error"]

    async def test_finish_research_without_session(self, toolkit: AgentToolkit) -> None:
        result = await execute_tool(
            toolkit,
            "finish_research",
            {
                "conclusion": "Test",
                "recommended_tools": ["playwright"],
            },
        )
        assert result["success"] is False
        assert "No research session" in result["error"]

    async def test_finish_research_with_session(self, toolkit: AgentToolkit) -> None:
        # Start session first
        await execute_tool(
            toolkit,
            "start_research_session",
            {
                "target_url": "https://example.com",
                "objective": "Test",
            },
        )

        result = await execute_tool(
            toolkit,
            "finish_research",
            {
                "conclusion": "Use Playwright",
                "recommended_tools": ["playwright", "httpx"],
            },
        )

        assert result["success"] is True
        assert toolkit.session is not None
        assert toolkit.session.conclusion == "Use Playwright"


@pytest.mark.asyncio
@pytest.mark.integration
class TestBrowserIntegration:
    """Integration tests that actually start browser.

    Run with: pytest -m integration
    """

    async def test_browser_navigation(self, toolkit: AgentToolkit) -> None:
        try:
            # Start browser
            result = await execute_tool(
                toolkit,
                "start_browser",
                {"headless": True, "use_proxy": False},
            )
            assert result["success"] is True

            # Navigate
            result = await execute_tool(
                toolkit,
                "navigate",
                {"url": "https://example.com"},
            )
            assert result["success"] is True
            assert "url" in result

            # Detect tech
            result = await execute_tool(toolkit, "detect_technologies", {})
            assert result["success"] is True
            assert "technologies" in result

        finally:
            await toolkit.cleanup()

    async def test_form_detection(self, toolkit: AgentToolkit) -> None:
        try:
            await execute_tool(
                toolkit,
                "start_browser",
                {"headless": True, "use_proxy": False},
            )

            # Use a page with forms
            await execute_tool(
                toolkit,
                "navigate",
                {"url": "https://httpbin.org/forms/post"},
            )

            result = await execute_tool(toolkit, "find_forms", {})
            assert result["success"] is True
            assert "forms" in result

        finally:
            await toolkit.cleanup()


@pytest.mark.asyncio
@pytest.mark.integration
class TestProxyIntegration:
    """Integration tests for proxy capture."""

    async def test_proxy_capture(self, toolkit: AgentToolkit) -> None:
        try:
            # Start proxy
            result = await execute_tool(
                toolkit,
                "start_proxy",
                {"port": 18888},
            )
            assert result["success"] is True
            assert "proxy_url" in result

            # Start browser with proxy
            result = await execute_tool(
                toolkit,
                "start_browser",
                {"headless": True, "use_proxy": True},
            )
            assert result["success"] is True

            # Navigate
            await execute_tool(
                toolkit,
                "navigate",
                {"url": "https://httpbin.org/get"},
            )

            # Get captured requests
            result = await execute_tool(
                toolkit,
                "get_captured_requests",
                {},
            )
            assert result["success"] is True
            assert result["total_captured"] > 0

        finally:
            await toolkit.cleanup()
