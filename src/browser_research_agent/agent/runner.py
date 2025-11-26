"""Research agent runner using Claude API."""

import asyncio
import json
import logging
from typing import Any

from anthropic import Anthropic

from ..config import settings
from .tools import AgentToolkit, create_tools, execute_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a browser automation research agent. Your job is to investigate websites and determine the best approach for automating interactions with them.

You have access to tools for:
1. **Traffic Capture** - Start a proxy to capture all HTTP/HTTPS traffic
2. **Browser Control** - Launch and control a browser via Playwright
3. **Page Analysis** - Detect technologies, find forms, analyze structure
4. **Recommendations** - Generate reports with recommended automation approaches

## Research Workflow

For any website investigation, follow this workflow:

1. **Start Session** - Call `start_research_session` with the target URL and objective
2. **Start Proxy** - Call `start_proxy` to begin capturing traffic
3. **Start Browser** - Call `start_browser` with `use_proxy=true`
4. **Navigate** - Go to the target URL
5. **Investigate**:
   - Take screenshots
   - Detect technologies and anti-bot systems
   - Find forms (especially login forms)
   - Capture API requests
   - Try interacting with the site if needed
6. **Analyze** - Call `analyze_site` to get comprehensive analysis
7. **Compare** - Call `compare_approaches` to see trade-offs
8. **Report** - Generate a report with findings
9. **Conclude** - Call `finish_research` with your recommendations

## Key Considerations

When making recommendations, consider:
- **Anti-bot detection**: Does the site use Cloudflare, DataDome, etc.?
- **Authentication**: Cookie-based, token-based, or API keys?
- **SPA vs traditional**: Is JavaScript rendering required?
- **API availability**: Can we use direct HTTP instead of browser automation?
- **Rate limiting**: Are there signs of rate limiting?

## Output Format

Always provide clear, actionable recommendations:
- Which tools to use (playwright, httpx, camoufox, etc.)
- What approach to take (browser automation vs direct API)
- Any special considerations (auth handling, anti-bot bypass)
- Code snippets or configuration suggestions when helpful

Be thorough but efficient. Capture enough traffic to understand the site's behavior without unnecessary navigation."""


class ResearchAgent:
    """Agent that uses Claude to investigate websites."""

    def __init__(self, api_key: str | None = None) -> None:
        self.client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self.toolkit = AgentToolkit()
        self.tools = create_tools(self.toolkit)
        self.messages: list[dict[str, Any]] = []
        self.model = settings.model

    async def run(self, task: str) -> str:
        """Run the agent with a research task."""
        self.messages = [{"role": "user", "content": task}]

        try:
            while True:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=self.tools,
                    messages=self.messages,
                )

                # Check if we need to execute tools
                if response.stop_reason == "tool_use":
                    # Process all tool calls
                    assistant_content = response.content
                    tool_results = []

                    for block in assistant_content:
                        if block.type == "tool_use":
                            logger.info(f"Executing tool: {block.name}")
                            result = await execute_tool(
                                self.toolkit,
                                block.name,
                                block.input,
                            )
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result, default=str),
                            })
                            logger.info(f"Tool result: {result.get('success', False)}")

                    # Add assistant message and tool results
                    self.messages.append({"role": "assistant", "content": assistant_content})
                    self.messages.append({"role": "user", "content": tool_results})

                elif response.stop_reason == "end_turn":
                    # Extract final text response
                    final_text = ""
                    for block in response.content:
                        if hasattr(block, "text"):
                            final_text += block.text

                    return final_text

                else:
                    logger.warning(f"Unexpected stop reason: {response.stop_reason}")
                    break

        finally:
            await self.toolkit.cleanup()

        return "Research completed."

    async def run_interactive(self, task: str) -> None:
        """Run agent interactively, printing progress."""
        print(f"\n🔍 Starting research: {task}\n")
        print("-" * 60)

        self.messages = [{"role": "user", "content": task}]

        try:
            while True:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=self.tools,
                    messages=self.messages,
                )

                if response.stop_reason == "tool_use":
                    assistant_content = response.content
                    tool_results = []

                    # Print any text before tools
                    for block in assistant_content:
                        if hasattr(block, "text") and block.text:
                            print(f"\n💭 {block.text}")

                    for block in assistant_content:
                        if block.type == "tool_use":
                            print(f"\n🔧 {block.name}: {json.dumps(block.input, indent=2)}")

                            result = await execute_tool(
                                self.toolkit,
                                block.name,
                                block.input,
                            )

                            status = "✅" if result.get("success") else "❌"
                            print(f"{status} Result: {json.dumps(result, indent=2, default=str)[:500]}")

                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result, default=str),
                            })

                    self.messages.append({"role": "assistant", "content": assistant_content})
                    self.messages.append({"role": "user", "content": tool_results})

                elif response.stop_reason == "end_turn":
                    print("\n" + "-" * 60)
                    print("\n📋 Final Report:\n")
                    for block in response.content:
                        if hasattr(block, "text"):
                            print(block.text)
                    break

                else:
                    print(f"⚠️ Unexpected stop: {response.stop_reason}")
                    break

        finally:
            await self.toolkit.cleanup()
            print("\n✨ Research complete!")
