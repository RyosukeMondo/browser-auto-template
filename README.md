# Browser Research Agent

AI-agent-driven browser automation research framework. Ask an AI agent to investigate websites and recommend the best automation approach.

## Features

- **AI-Powered Investigation**: Claude agent autonomously analyzes websites
- **Traffic Capture**: mitmproxy integration for full HTTP/HTTPS traffic capture
- **Browser Automation**: Playwright for cross-browser control
- **CDP Direct**: Chrome DevTools Protocol for low-level access
- **Anti-Bot Detection**: Identifies Cloudflare, DataDome, Akamai, etc.
- **API Discovery**: Automatically finds and documents API endpoints
- **Multi-Format Export**: Markdown, JSON, SQLite, HAR

## Installation

```bash
# Clone and install
cd browser-automation
pip install -e .

# Install Playwright browsers
playwright install chromium

# Copy and configure environment
cp .env.example .env
# Edit .env with your Anthropic API key
```

## Quick Start

### AI Agent Investigation

```bash
# Let AI investigate a site and recommend automation approach
bra investigate https://example.com -o "automate user registration flow"

# With headless browser
bra investigate https://example.com --headless
```

### Manual Tools

```bash
# Start proxy to capture traffic
bra proxy --port 8080

# Launch browser through proxy
bra browser https://example.com --proxy 8080

# Launch Chrome with CDP
bra chrome --port 9222

# Analyze a HAR file
bra analyze traffic.har

# List research sessions
bra sessions

# Export session report
bra export <session-id> --format markdown
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Claude AI Agent                          │
│  - Receives research task                                    │
│  - Orchestrates tools                                        │
│  - Generates recommendations                                 │
├─────────────────────────────────────────────────────────────┤
│                        Tools                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Proxy   │  │ Browser  │  │   CDP    │  │ Analyzer │    │
│  │(mitmproxy)│  │(Playwright)│ │ (Chrome) │  │          │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
├─────────────────────────────────────────────────────────────┤
│                       Storage                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │  SQLite  │  │   JSON   │  │ Markdown │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

## Python API

```python
import asyncio
from browser_research_agent.agent import ResearchAgent

async def main():
    agent = ResearchAgent()

    result = await agent.run("""
        Investigate https://example.com

        I want to automate:
        1. Login flow
        2. Data extraction from dashboard

        Determine the best approach and tools.
    """)

    print(result)

asyncio.run(main())
```

### Using Individual Tools

```python
import asyncio
from browser_research_agent.tools import (
    ProxyCapture,
    BrowserController,
    SiteAnalyzer,
)

async def capture_traffic():
    # Start proxy
    proxy = ProxyCapture(port=8080)
    await proxy.start()

    # Start browser through proxy
    browser = BrowserController(proxy_url="http://127.0.0.1:8080")
    await browser.start()

    # Navigate and capture
    await browser.navigate("https://example.com")

    # Analyze
    requests = proxy.get_api_requests()
    analyzer = SiteAnalyzer()
    analysis = analyzer.analyze(
        url="https://example.com",
        requests=requests,
        tech_detection=await browser.detect_technologies(),
    )

    print(f"Found {len(analysis.discovered_endpoints)} API endpoints")
    print(f"Recommended tools: {analysis.recommended_tools}")

    # Export
    proxy.export_har(Path("./traffic.har"))

    # Cleanup
    await browser.stop()
    await proxy.stop()

asyncio.run(capture_traffic())
```

## Tool Recommendations

The agent recommends tools based on site characteristics:

| Scenario | Recommended Tools |
|----------|-------------------|
| Simple site, no protection | playwright, httpx |
| SPA (React/Vue/Angular) | playwright (with waits) |
| Cloudflare protected | cloudscraper, camoufox |
| Heavy anti-bot (DataDome/Akamai) | camoufox, undetected-chromedriver |
| Clear API structure | httpx (direct API calls) |
| Complex auth flow | playwright + session management |

## Related OSS Projects

This framework integrates with or recommends:

- [mitmproxy](https://mitmproxy.org/) - Traffic capture
- [Playwright](https://playwright.dev/python/) - Browser automation
- [Camoufox](https://github.com/daijro/camoufox) - Anti-detect browser
- [cloudscraper](https://github.com/VeNoMouS/cloudscraper) - Cloudflare bypass
- [httpx](https://www.python-httpx.org/) - Async HTTP client

## License

MIT
