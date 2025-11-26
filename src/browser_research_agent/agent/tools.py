"""Tool definitions for Claude Agent SDK."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..config import settings
from ..models import ResearchSession, SiteAnalysis
from ..tools.analyzer import SiteAnalyzer
from ..tools.browser import BrowserController
from ..tools.cdp import CDPController
from ..tools.proxy import ProxyCapture

logger = logging.getLogger(__name__)


class AgentToolkit:
    """Manages all browser research tools for the agent."""

    def __init__(self) -> None:
        self.proxy: ProxyCapture | None = None
        self.browser: BrowserController | None = None
        self.cdp: CDPController | None = None
        self.analyzer = SiteAnalyzer()
        self.session: ResearchSession | None = None

    async def cleanup(self) -> None:
        """Clean up all resources."""
        if self.browser:
            await self.browser.stop()
        if self.proxy:
            await self.proxy.stop()
        if self.cdp:
            await self.cdp.stop()


def create_tools(toolkit: AgentToolkit) -> list[dict[str, Any]]:
    """Create tool definitions for Claude Agent SDK."""

    tools = [
        {
            "name": "start_research_session",
            "description": "Start a new research session for investigating a website. Call this first before any other tools.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "target_url": {
                        "type": "string",
                        "description": "The URL of the website to investigate",
                    },
                    "objective": {
                        "type": "string",
                        "description": "What you want to achieve (e.g., 'automate login and data extraction')",
                    },
                },
                "required": ["target_url", "objective"],
            },
        },
        {
            "name": "start_proxy",
            "description": "Start the mitmproxy to capture all HTTP/HTTPS traffic. Use this to see all requests made by the browser.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "port": {
                        "type": "integer",
                        "description": "Port for proxy (default: 8080)",
                        "default": 8080,
                    },
                },
                "required": [],
            },
        },
        {
            "name": "start_browser",
            "description": "Start a browser (Chromium via Playwright). Can connect through the proxy if running.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "headless": {
                        "type": "boolean",
                        "description": "Run in headless mode (no visible window)",
                        "default": False,
                    },
                    "use_proxy": {
                        "type": "boolean",
                        "description": "Route traffic through mitmproxy",
                        "default": True,
                    },
                },
                "required": [],
            },
        },
        {
            "name": "navigate",
            "description": "Navigate the browser to a URL and wait for the page to load.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to navigate to",
                    },
                    "wait_until": {
                        "type": "string",
                        "enum": ["load", "domcontentloaded", "networkidle"],
                        "description": "When to consider navigation complete",
                        "default": "networkidle",
                    },
                },
                "required": ["url"],
            },
        },
        {
            "name": "screenshot",
            "description": "Take a screenshot of the current page.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Filename for screenshot (default: auto-generated)",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "detect_technologies",
            "description": "Detect technologies, frameworks, and anti-bot systems on the current page.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "find_forms",
            "description": "Find all forms on the current page, including login forms.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "find_links",
            "description": "Find all links on the current page.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "internal_only": {
                        "type": "boolean",
                        "description": "Only return links to the same domain",
                        "default": False,
                    },
                },
                "required": [],
            },
        },
        {
            "name": "get_captured_requests",
            "description": "Get all HTTP requests captured by the proxy.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "api_only": {
                        "type": "boolean",
                        "description": "Only return API/XHR requests",
                        "default": False,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of requests to return",
                        "default": 50,
                    },
                },
                "required": [],
            },
        },
        {
            "name": "analyze_site",
            "description": "Perform comprehensive analysis of the site based on captured traffic and page content. Returns recommendations.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "compare_approaches",
            "description": "Compare different automation approaches (Playwright, HTTP, anti-detect) for this site.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "fill_form",
            "description": "Fill a form field with a value.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for the form field",
                    },
                    "value": {
                        "type": "string",
                        "description": "Value to enter",
                    },
                },
                "required": ["selector", "value"],
            },
        },
        {
            "name": "click",
            "description": "Click an element on the page.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for the element to click",
                    },
                },
                "required": ["selector"],
            },
        },
        {
            "name": "execute_javascript",
            "description": "Execute JavaScript code in the browser context.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "JavaScript code to execute",
                    },
                },
                "required": ["code"],
            },
        },
        {
            "name": "get_cookies",
            "description": "Get all cookies from the browser.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "export_traffic",
            "description": "Export captured traffic to file (HAR or JSON format).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["har", "json"],
                        "description": "Export format",
                        "default": "har",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Output filename (default: auto-generated)",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "generate_report",
            "description": "Generate a comprehensive research report with analysis and recommendations.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "format": {
                        "type": "string",
                        "enum": ["markdown", "json"],
                        "description": "Report format",
                        "default": "markdown",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "start_cdp_chrome",
            "description": "Start Chrome with CDP (Chrome DevTools Protocol) for low-level control.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "headless": {
                        "type": "boolean",
                        "description": "Run in headless mode",
                        "default": False,
                    },
                    "use_proxy": {
                        "type": "boolean",
                        "description": "Route traffic through mitmproxy",
                        "default": True,
                    },
                },
                "required": [],
            },
        },
        {
            "name": "finish_research",
            "description": "Finish the research session and provide final conclusions.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "conclusion": {
                        "type": "string",
                        "description": "Your conclusion about the best approach",
                    },
                    "recommended_tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of recommended tools/libraries",
                    },
                },
                "required": ["conclusion", "recommended_tools"],
            },
        },
    ]

    return tools


async def execute_tool(
    toolkit: AgentToolkit,
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    """Execute a tool and return the result."""

    try:
        if tool_name == "start_research_session":
            toolkit.session = ResearchSession(
                id=str(uuid4()),
                target_url=tool_input["target_url"],
                objective=tool_input["objective"],
            )
            return {
                "success": True,
                "session_id": toolkit.session.id,
                "message": f"Research session started for {tool_input['target_url']}",
            }

        elif tool_name == "start_proxy":
            port = tool_input.get("port", settings.proxy_port)
            toolkit.proxy = ProxyCapture(port=port)
            await toolkit.proxy.start()
            return {
                "success": True,
                "proxy_url": toolkit.proxy.get_proxy_url(),
                "message": f"Proxy started on port {port}",
            }

        elif tool_name == "start_browser":
            headless = tool_input.get("headless", settings.headless)
            use_proxy = tool_input.get("use_proxy", True)
            proxy_url = toolkit.proxy.get_proxy_url() if toolkit.proxy and use_proxy else None

            toolkit.browser = BrowserController(
                headless=headless,
                proxy_url=proxy_url,
            )
            await toolkit.browser.start()
            return {
                "success": True,
                "headless": headless,
                "proxy_enabled": proxy_url is not None,
            }

        elif tool_name == "navigate":
            if not toolkit.browser:
                return {"success": False, "error": "Browser not started"}
            await toolkit.browser.navigate(
                tool_input["url"],
                wait_until=tool_input.get("wait_until", "networkidle"),
            )
            info = await toolkit.browser.get_page_info()
            return {"success": True, **info}

        elif tool_name == "screenshot":
            if not toolkit.browser:
                return {"success": False, "error": "Browser not started"}
            filename = tool_input.get("filename", f"screenshot_{uuid4().hex[:8]}.png")
            path = settings.data_dir / "screenshots" / filename
            await toolkit.browser.screenshot(path)
            return {"success": True, "path": str(path)}

        elif tool_name == "detect_technologies":
            if not toolkit.browser:
                return {"success": False, "error": "Browser not started"}
            tech = await toolkit.browser.detect_technologies()
            return {"success": True, "technologies": tech}

        elif tool_name == "find_forms":
            if not toolkit.browser:
                return {"success": False, "error": "Browser not started"}
            forms = await toolkit.browser.find_forms()
            return {"success": True, "forms": forms, "count": len(forms)}

        elif tool_name == "find_links":
            if not toolkit.browser:
                return {"success": False, "error": "Browser not started"}
            links = await toolkit.browser.find_links(
                internal_only=tool_input.get("internal_only", False)
            )
            return {"success": True, "links": links, "count": len(links)}

        elif tool_name == "get_captured_requests":
            if not toolkit.proxy:
                return {"success": False, "error": "Proxy not started"}
            api_only = tool_input.get("api_only", False)
            limit = tool_input.get("limit", 50)

            if api_only:
                requests = toolkit.proxy.get_api_requests()
            else:
                requests = toolkit.proxy.get_requests()

            requests = requests[-limit:]
            return {
                "success": True,
                "requests": [
                    {
                        "method": r.method.value,
                        "url": r.url,
                        "status": r.response_status,
                        "is_api": r.is_api,
                        "content_type": r.content_type,
                    }
                    for r in requests
                ],
                "total_captured": len(toolkit.proxy.get_requests()),
            }

        elif tool_name == "analyze_site":
            if not toolkit.browser:
                return {"success": False, "error": "Browser not started"}

            info = await toolkit.browser.get_page_info()
            tech = await toolkit.browser.detect_technologies()
            forms = await toolkit.browser.find_forms()
            requests = toolkit.proxy.get_requests() if toolkit.proxy else []

            analysis = toolkit.analyzer.analyze(
                url=info["url"],
                requests=requests,
                tech_detection=tech,
                forms=forms,
            )

            if toolkit.session:
                toolkit.session.analyses.append(analysis)

            return {
                "success": True,
                "analysis": {
                    "url": analysis.url,
                    "domain": analysis.domain,
                    "technologies": analysis.technologies,
                    "anti_bot": [ab.value for ab in analysis.anti_bot],
                    "requires_auth": analysis.requires_auth,
                    "auth_methods": [am.value for am in analysis.auth_methods],
                    "api_endpoints_found": len(analysis.discovered_endpoints),
                    "recommended_approach": analysis.recommended_approach,
                    "recommended_tools": analysis.recommended_tools,
                },
            }

        elif tool_name == "compare_approaches":
            if not toolkit.session or not toolkit.session.analyses:
                return {"success": False, "error": "No analysis available. Run analyze_site first."}

            latest_analysis = toolkit.session.analyses[-1]
            comparison = toolkit.analyzer.compare_approaches(latest_analysis)
            return {"success": True, "comparison": comparison}

        elif tool_name == "fill_form":
            if not toolkit.browser:
                return {"success": False, "error": "Browser not started"}
            await toolkit.browser.fill_form({tool_input["selector"]: tool_input["value"]})
            return {"success": True}

        elif tool_name == "click":
            if not toolkit.browser:
                return {"success": False, "error": "Browser not started"}
            await toolkit.browser.click(tool_input["selector"])
            return {"success": True}

        elif tool_name == "execute_javascript":
            if not toolkit.browser:
                return {"success": False, "error": "Browser not started"}
            result = await toolkit.browser.execute_script(tool_input["code"])
            return {"success": True, "result": result}

        elif tool_name == "get_cookies":
            if not toolkit.browser:
                return {"success": False, "error": "Browser not started"}
            cookies = await toolkit.browser.get_cookies()
            return {"success": True, "cookies": cookies}

        elif tool_name == "export_traffic":
            if not toolkit.proxy:
                return {"success": False, "error": "Proxy not started"}

            fmt = tool_input.get("format", "har")
            filename = tool_input.get(
                "filename",
                f"traffic_{uuid4().hex[:8]}.{fmt}",
            )
            path = settings.data_dir / "exports" / filename

            if fmt == "har":
                toolkit.proxy.export_har(path)
            else:
                toolkit.proxy.export_json(path)

            return {"success": True, "path": str(path)}

        elif tool_name == "generate_report":
            if not toolkit.session:
                return {"success": False, "error": "No research session"}

            fmt = tool_input.get("format", "markdown")

            if fmt == "markdown":
                report = _generate_markdown_report(toolkit.session)
                filename = f"report_{toolkit.session.id[:8]}.md"
            else:
                report = toolkit.session.model_dump_json(indent=2)
                filename = f"report_{toolkit.session.id[:8]}.json"

            path = settings.data_dir / "reports" / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(report)

            return {"success": True, "path": str(path), "format": fmt}

        elif tool_name == "start_cdp_chrome":
            headless = tool_input.get("headless", settings.headless)
            use_proxy = tool_input.get("use_proxy", True)
            proxy_url = toolkit.proxy.get_proxy_url() if toolkit.proxy and use_proxy else None

            toolkit.cdp = CDPController(
                headless=headless,
                proxy_url=proxy_url,
            )
            ws_url = await toolkit.cdp.start()
            return {
                "success": True,
                "ws_url": ws_url,
                "launch_command": toolkit.cdp.get_launch_command(),
            }

        elif tool_name == "finish_research":
            if not toolkit.session:
                return {"success": False, "error": "No research session"}

            toolkit.session.conclusion = tool_input["conclusion"]
            toolkit.session.final_recommendation = ", ".join(tool_input["recommended_tools"])

            return {
                "success": True,
                "session_id": toolkit.session.id,
                "conclusion": toolkit.session.conclusion,
            }

        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.exception(f"Tool execution error: {tool_name}")
        return {"success": False, "error": str(e)}


def _generate_markdown_report(session: ResearchSession) -> str:
    """Generate markdown report from research session."""
    lines = [
        f"# Browser Research Report",
        f"",
        f"**Target:** {session.target_url}",
        f"**Objective:** {session.objective}",
        f"**Date:** {session.created_at.isoformat()}",
        f"**Session ID:** {session.id}",
        f"",
    ]

    for i, analysis in enumerate(session.analyses, 1):
        lines.extend([
            f"## Analysis {i}: {analysis.domain}",
            f"",
            f"### Technologies Detected",
            f"",
        ])

        if analysis.technologies:
            for tech in analysis.technologies:
                lines.append(f"- {tech}")
        else:
            lines.append("- None detected")

        lines.extend([
            f"",
            f"### Anti-Bot Protection",
            f"",
        ])

        if analysis.anti_bot:
            for ab in analysis.anti_bot:
                lines.append(f"- {ab.value}")
        else:
            lines.append("- None detected")

        lines.extend([
            f"",
            f"### Authentication",
            f"",
            f"- Required: {'Yes' if analysis.requires_auth else 'No'}",
        ])

        if analysis.auth_methods:
            lines.append(f"- Methods: {', '.join(am.value for am in analysis.auth_methods)}")

        if analysis.login_url:
            lines.append(f"- Login URL: {analysis.login_url}")

        lines.extend([
            f"",
            f"### API Endpoints Discovered",
            f"",
        ])

        if analysis.discovered_endpoints:
            for ep in analysis.discovered_endpoints[:10]:
                methods = ", ".join(m.value for m in ep.methods)
                lines.append(f"- `{ep.url_pattern}` [{methods}]")
        else:
            lines.append("- No API endpoints discovered")

        lines.extend([
            f"",
            f"### Recommendation",
            f"",
            f"{analysis.recommended_approach or 'No specific recommendation'}",
            f"",
            f"**Recommended Tools:** {', '.join(analysis.recommended_tools)}",
            f"",
        ])

    if session.conclusion:
        lines.extend([
            f"## Conclusion",
            f"",
            f"{session.conclusion}",
            f"",
        ])

    if session.final_recommendation:
        lines.extend([
            f"## Final Recommendation",
            f"",
            f"**Tools:** {session.final_recommendation}",
        ])

    return "\n".join(lines)
