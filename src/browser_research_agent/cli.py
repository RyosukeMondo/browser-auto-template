"""CLI interface for browser research agent."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from .agent import ResearchAgent
from .config import settings
from .storage import JSONStorage, MarkdownExporter, SQLiteStorage
from .tools import BrowserController, CDPController, ProxyCapture

_VERSION_CALLBACK_HANDLED = "version_handled"

app = typer.Typer(
    name="bra",
    help="Browser Research Agent - AI-driven browser automation investigation",
    add_completion=False,
)
console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@app.command()
def investigate(
    url: str = typer.Argument(..., help="URL to investigate"),
    objective: str = typer.Option(
        "Analyze the site and recommend the best automation approach",
        "--objective",
        "-o",
        help="Research objective",
    ),
    headless: bool = typer.Option(False, "--headless", "-H", help="Run browser in headless mode"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    """Investigate a website using AI agent."""
    setup_logging(verbose)

    task = f"""Investigate the website: {url}

Objective: {objective}

Please:
1. Start a research session
2. Start the proxy and browser
3. Navigate to the site
4. Analyze technologies, anti-bot protection, and authentication
5. Capture and analyze API traffic
6. Provide recommendations for automation approach
7. Generate a comprehensive report"""

    async def run() -> None:
        agent = ResearchAgent()
        await agent.run_interactive(task)

    asyncio.run(run())


@app.command()
def proxy(
    port: int = typer.Option(8080, "--port", "-p", help="Proxy port"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output HAR file"),
) -> None:
    """Start mitmproxy for traffic capture."""
    setup_logging()

    async def run() -> None:
        proxy_instance = ProxyCapture(port=port)
        await proxy_instance.start()

        console.print(f"[green]Proxy running on http://127.0.0.1:{port}[/green]")
        console.print("\nConfigure your browser to use this proxy.")
        console.print("Press Ctrl+C to stop and export traffic.\n")

        try:
            while True:
                await asyncio.sleep(1)
                req_count = len(proxy_instance.get_requests())
                console.print(f"\r[dim]Captured: {req_count} requests[/dim]", end="")
        except KeyboardInterrupt:
            console.print("\n")

            if output:
                if output.suffix == ".json":
                    proxy_instance.export_json(output)
                else:
                    proxy_instance.export_har(output)
                console.print(f"[green]Traffic exported to: {output}[/green]")
            else:
                # Auto-export
                from uuid import uuid4
                har_path = settings.data_dir / "exports" / f"traffic_{uuid4().hex[:8]}.har"
                proxy_instance.export_har(har_path)
                console.print(f"[green]Traffic exported to: {har_path}[/green]")

            await proxy_instance.stop()

    asyncio.run(run())


@app.command()
def browser(
    url: Optional[str] = typer.Argument(None, help="URL to open"),
    headless: bool = typer.Option(False, "--headless", "-H", help="Headless mode"),
    proxy_port: Optional[int] = typer.Option(None, "--proxy", "-p", help="Proxy port to use"),
    har: Optional[Path] = typer.Option(None, "--har", help="Record HAR to file"),
) -> None:
    """Launch browser with Playwright."""
    setup_logging()

    async def run() -> None:
        proxy_url = f"http://127.0.0.1:{proxy_port}" if proxy_port else None
        browser_instance = BrowserController(headless=headless, proxy_url=proxy_url)

        page = await browser_instance.start()

        if har:
            await browser_instance.record_har(har)
            page = browser_instance.page

        if url:
            await browser_instance.navigate(url)
            info = await browser_instance.get_page_info()
            console.print(f"[green]Loaded: {info['title']}[/green]")

        console.print("\nBrowser running. Press Ctrl+C to close.\n")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass

        if har:
            console.print(f"[green]HAR saved to: {har}[/green]")

        await browser_instance.stop()

    asyncio.run(run())


@app.command()
def chrome(
    url: Optional[str] = typer.Argument(None, help="URL to open"),
    port: int = typer.Option(9222, "--port", "-p", help="CDP port"),
    headless: bool = typer.Option(False, "--headless", "-H", help="Headless mode"),
    proxy_port: Optional[int] = typer.Option(None, "--proxy", help="Proxy port"),
) -> None:
    """Launch Chrome with CDP enabled."""
    setup_logging()

    async def run() -> None:
        proxy_url = f"http://127.0.0.1:{proxy_port}" if proxy_port else None
        cdp = CDPController(port=port, headless=headless, proxy_url=proxy_url)

        ws_url = await cdp.start()

        console.print(f"[green]Chrome started with CDP on port {port}[/green]")
        console.print(f"\nWebSocket URL: {ws_url}")
        console.print(f"\nManual launch command:")
        console.print(f"  {cdp.get_launch_command()}")

        if url:
            targets = await cdp.get_targets()
            if targets:
                console.print(f"\nOpen tabs: {len(targets)}")

        console.print("\nPress Ctrl+C to close Chrome.\n")

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass

        await cdp.stop()

    asyncio.run(run())


@app.command()
def sessions(
    storage: str = typer.Option("sqlite", "--storage", "-s", help="Storage backend: sqlite, json"),
) -> None:
    """List research sessions."""
    setup_logging()

    async def run() -> None:
        if storage == "sqlite":
            store = SQLiteStorage()
        else:
            store = JSONStorage()

        sessions_list = await store.list_sessions()

        if not sessions_list:
            console.print("[yellow]No sessions found[/yellow]")
            return

        table = Table(title="Research Sessions")
        table.add_column("ID", style="cyan")
        table.add_column("Date", style="green")
        table.add_column("Target URL")
        table.add_column("Objective")

        for s in sessions_list:
            table.add_row(
                s["id"][:8],
                s["created_at"][:16],
                s["target_url"][:40],
                (s.get("objective") or "")[:30],
            )

        console.print(table)

    asyncio.run(run())


@app.command()
def export(
    session_id: str = typer.Argument(..., help="Session ID (first 8 chars ok)"),
    format: str = typer.Option("markdown", "--format", "-f", help="Format: markdown, json"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
) -> None:
    """Export a research session."""
    setup_logging()

    async def run() -> None:
        # Try both storage backends
        store = SQLiteStorage()
        sessions_list = await store.list_sessions()

        # Find matching session
        session_full_id = None
        for s in sessions_list:
            if s["id"].startswith(session_id):
                session_full_id = s["id"]
                break

        if not session_full_id:
            # Try JSON storage
            store = JSONStorage()
            sessions_list = await store.list_sessions()
            for s in sessions_list:
                if s["id"].startswith(session_id):
                    session_full_id = s["id"]
                    break

        if not session_full_id:
            console.print(f"[red]Session not found: {session_id}[/red]")
            raise typer.Exit(1)

        session = await store.load_session(session_full_id)
        if not session:
            console.print(f"[red]Failed to load session[/red]")
            raise typer.Exit(1)

        if format == "markdown":
            exporter = MarkdownExporter()
            path = exporter.export(session)
        else:
            path = output or (settings.data_dir / "exports" / f"{session_full_id[:8]}.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(session.model_dump_json(indent=2))

        console.print(f"[green]Exported to: {path}[/green]")

    asyncio.run(run())


@app.command()
def analyze(
    har_file: Path = typer.Argument(..., help="HAR file to analyze"),
) -> None:
    """Analyze a HAR file for API endpoints."""
    import json
    from .tools.analyzer import SiteAnalyzer
    from .models import CapturedRequest, RequestMethod

    setup_logging()

    data = json.loads(har_file.read_text())
    entries = data.get("log", {}).get("entries", [])

    requests = []
    for entry in entries:
        req = entry.get("request", {})
        resp = entry.get("response", {})

        try:
            captured = CapturedRequest(
                id=str(len(requests)),
                method=RequestMethod(req.get("method", "GET")),
                url=req.get("url", ""),
                headers={h["name"]: h["value"] for h in req.get("headers", [])},
                response_status=resp.get("status"),
                response_headers={h["name"]: h["value"] for h in resp.get("headers", [])},
                content_type=resp.get("content", {}).get("mimeType", ""),
                is_api="json" in resp.get("content", {}).get("mimeType", "").lower(),
            )
            requests.append(captured)
        except Exception:
            continue

    if not requests:
        console.print("[yellow]No requests found in HAR file[/yellow]")
        return

    analyzer = SiteAnalyzer()

    analysis = analyzer.analyze(
        url=requests[0].url,
        requests=requests,
    )

    # Print results
    console.print(f"\n[bold]Analysis of {har_file.name}[/bold]\n")
    console.print(f"Total requests: {len(requests)}")
    console.print(f"API requests: {len([r for r in requests if r.is_api])}")

    if analysis.discovered_endpoints:
        ep_count = len(analysis.discovered_endpoints)
        console.print(f"\n[bold]Discovered Endpoints ({ep_count}):[/bold]")
        for ep in analysis.discovered_endpoints[:20]:
            methods = ", ".join(m.value for m in ep.methods)
            auth = "[auth]" if ep.auth_required else ""
            console.print(f"  {methods:10} {ep.url_pattern} {auth}")

    if analysis.recommended_approach:
        console.print("\n[bold]Recommendations:[/bold]")
        console.print(analysis.recommended_approach)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", help="Show version"),
) -> None:
    """Browser Research Agent - AI-driven browser automation investigation."""
    if version:
        from . import __version__

        console.print(f"browser-research-agent v{__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


if __name__ == "__main__":
    app()
