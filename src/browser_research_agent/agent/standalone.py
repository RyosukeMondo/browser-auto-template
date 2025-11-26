"""Standalone tool runner for SUBSCRIPTION mode.

In SUBSCRIPTION mode, YOU (Claude Code) are the agent.
This module provides tools that can be called directly from Claude Code
without making API calls to Anthropic.

Usage from Claude Code:
    from browser_research_agent.agent.standalone import toolkit, run_tool

    # Start a session
    await run_tool("start_research_session", {
        "target_url": "https://example.com",
        "objective": "investigate automation options"
    })

    # Run other tools...
    await run_tool("start_proxy", {})
    await run_tool("start_browser", {"use_proxy": True})
"""

import asyncio
import json
import logging
from typing import Any

from .tools import AgentToolkit, execute_tool, create_tools

logger = logging.getLogger(__name__)

# Global toolkit instance for SUBSCRIPTION mode
toolkit = AgentToolkit()


async def run_tool(tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute a single tool and return result.

    This is the main entry point for SUBSCRIPTION mode.
    Call this from Claude Code to execute browser research tools.

    Args:
        tool_name: Name of the tool to execute
        params: Tool parameters (optional)

    Returns:
        Tool execution result as dict

    Example:
        result = await run_tool("start_proxy", {"port": 8080})
        print(result)  # {"success": True, "proxy_url": "http://127.0.0.1:8080", ...}
    """
    params = params or {}
    result = await execute_tool(toolkit, tool_name, params)
    return result


def run_tool_sync(tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Synchronous wrapper for run_tool."""
    return asyncio.run(run_tool(tool_name, params))


async def cleanup() -> None:
    """Clean up all resources (browser, proxy, etc)."""
    await toolkit.cleanup()


def cleanup_sync() -> None:
    """Synchronous cleanup."""
    asyncio.run(cleanup())


def get_available_tools() -> list[dict[str, Any]]:
    """Get list of available tools with their schemas.

    Returns tool definitions that describe what each tool does
    and what parameters it accepts.
    """
    return create_tools(toolkit)


def print_tools() -> None:
    """Print available tools in readable format."""
    tools = get_available_tools()
    print("\n" + "=" * 60)
    print("BROWSER RESEARCH AGENT - AVAILABLE TOOLS")
    print("=" * 60)

    for tool in tools:
        print(f"\n### {tool['name']}")
        print(f"    {tool['description']}")

        props = tool.get("input_schema", {}).get("properties", {})
        required = tool.get("input_schema", {}).get("required", [])

        if props:
            print("    Parameters:")
            for name, spec in props.items():
                req = "*" if name in required else ""
                desc = spec.get("description", "")
                default = spec.get("default", "")
                type_str = spec.get("type", "any")

                if default != "":
                    print(f"      - {name}{req} ({type_str}, default={default}): {desc}")
                else:
                    print(f"      - {name}{req} ({type_str}): {desc}")

    print("\n" + "=" * 60)


# Convenience functions for common workflows

async def quick_investigate(url: str, objective: str = "analyze site for automation") -> dict[str, Any]:
    """Quick investigation workflow - runs common tools in sequence.

    Args:
        url: Target URL to investigate
        objective: Research objective

    Returns:
        Analysis results
    """
    results = {}

    # Start session
    results["session"] = await run_tool("start_research_session", {
        "target_url": url,
        "objective": objective,
    })

    # Start proxy
    results["proxy"] = await run_tool("start_proxy", {})

    # Start browser with proxy
    results["browser"] = await run_tool("start_browser", {"use_proxy": True})

    # Navigate
    results["navigate"] = await run_tool("navigate", {"url": url})

    # Take screenshot
    results["screenshot"] = await run_tool("screenshot", {})

    # Detect technologies
    results["tech"] = await run_tool("detect_technologies", {})

    # Find forms
    results["forms"] = await run_tool("find_forms", {})

    # Get captured requests
    results["requests"] = await run_tool("get_captured_requests", {"api_only": True})

    # Analyze
    results["analysis"] = await run_tool("analyze_site", {})

    # Compare approaches
    results["comparison"] = await run_tool("compare_approaches", {})

    return results


async def capture_traffic(url: str, actions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Capture traffic while performing actions.

    Args:
        url: Starting URL
        actions: List of actions to perform, e.g.:
            [
                {"type": "click", "selector": "#search-btn"},
                {"type": "fill", "selector": "#query", "value": "test"},
                {"type": "navigate", "url": "https://..."},
            ]

    Returns:
        Captured requests and HAR export path
    """
    actions = actions or []

    await run_tool("start_proxy", {})
    await run_tool("start_browser", {"use_proxy": True})
    await run_tool("navigate", {"url": url})

    # Perform actions
    for action in actions:
        action_type = action.get("type")
        if action_type == "click":
            await run_tool("click", {"selector": action["selector"]})
        elif action_type == "fill":
            await run_tool("fill_form", {
                "selector": action["selector"],
                "value": action["value"],
            })
        elif action_type == "navigate":
            await run_tool("navigate", {"url": action["url"]})
        elif action_type == "wait":
            await asyncio.sleep(action.get("seconds", 1))

    # Export traffic
    export_result = await run_tool("export_traffic", {"format": "har"})
    requests_result = await run_tool("get_captured_requests", {})

    return {
        "har_path": export_result.get("path"),
        "requests": requests_result.get("requests", []),
        "total": requests_result.get("total_captured", 0),
    }


# Tool name aliases for convenience
TOOL_ALIASES = {
    "session": "start_research_session",
    "proxy": "start_proxy",
    "browser": "start_browser",
    "go": "navigate",
    "nav": "navigate",
    "shot": "screenshot",
    "tech": "detect_technologies",
    "forms": "find_forms",
    "links": "find_links",
    "requests": "get_captured_requests",
    "analyze": "analyze_site",
    "compare": "compare_approaches",
    "fill": "fill_form",
    "js": "execute_javascript",
    "cookies": "get_cookies",
    "export": "export_traffic",
    "report": "generate_report",
    "cdp": "start_cdp_chrome",
    "finish": "finish_research",
}


async def t(name: str, **params: Any) -> dict[str, Any]:
    """Shorthand tool runner with aliases.

    Example:
        await t("proxy")  # starts proxy
        await t("go", url="https://example.com")  # navigate
        await t("shot")  # screenshot
    """
    tool_name = TOOL_ALIASES.get(name, name)
    return await run_tool(tool_name, params)
