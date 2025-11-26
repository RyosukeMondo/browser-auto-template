"""Direct Chrome DevTools Protocol control."""

import asyncio
import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger(__name__)


class CDPController:
    """Direct CDP control for Chrome browser."""

    def __init__(
        self,
        port: int = settings.cdp_port,
        proxy_url: str | None = None,
        headless: bool = settings.headless,
    ) -> None:
        self.port = port
        self.proxy_url = proxy_url
        self.headless = headless
        self._process: subprocess.Popen[bytes] | None = None
        self._ws_url: str | None = None
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> str:
        """Start Chrome with remote debugging and return WebSocket URL."""
        chrome_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        ]

        chrome_path = None
        for path in chrome_paths:
            if Path(path).exists():
                chrome_path = path
                break

        if not chrome_path:
            raise RuntimeError("Chrome not found. Please install Chrome or Chromium.")

        args = [
            chrome_path,
            f"--remote-debugging-port={self.port}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-client-side-phishing-detection",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-hang-monitor",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--disable-sync",
            "--disable-translate",
            "--metrics-recording-only",
            "--safebrowsing-disable-auto-update",
        ]

        if self.headless:
            args.append("--headless=new")

        if self.proxy_url:
            args.append(f"--proxy-server={self.proxy_url}")

        # User data dir to avoid conflicts
        user_data_dir = Path(settings.data_dir) / "chrome-profile"
        user_data_dir.mkdir(parents=True, exist_ok=True)
        args.append(f"--user-data-dir={user_data_dir}")

        self._process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for Chrome to start and get WebSocket URL
        self._client = httpx.AsyncClient()
        for _ in range(30):
            try:
                response = await self._client.get(f"http://127.0.0.1:{self.port}/json/version")
                data = response.json()
                self._ws_url = data.get("webSocketDebuggerUrl")
                if self._ws_url:
                    logger.info(f"Chrome started with CDP on port {self.port}")
                    return self._ws_url
            except Exception:
                await asyncio.sleep(0.5)

        raise RuntimeError("Failed to connect to Chrome CDP")

    async def stop(self) -> None:
        """Stop Chrome."""
        if self._client:
            await self._client.aclose()
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=5)
        logger.info("Chrome stopped")

    async def get_targets(self) -> list[dict[str, Any]]:
        """Get all browser targets (tabs)."""
        if not self._client:
            raise RuntimeError("CDP not started")
        response = await self._client.get(f"http://127.0.0.1:{self.port}/json/list")
        return response.json()

    async def new_tab(self, url: str = "about:blank") -> dict[str, Any]:
        """Open new tab."""
        if not self._client:
            raise RuntimeError("CDP not started")
        response = await self._client.put(
            f"http://127.0.0.1:{self.port}/json/new?{url}"
        )
        return response.json()

    async def close_tab(self, target_id: str) -> None:
        """Close a tab."""
        if not self._client:
            raise RuntimeError("CDP not started")
        await self._client.get(
            f"http://127.0.0.1:{self.port}/json/close/{target_id}"
        )

    async def activate_tab(self, target_id: str) -> None:
        """Activate (focus) a tab."""
        if not self._client:
            raise RuntimeError("CDP not started")
        await self._client.get(
            f"http://127.0.0.1:{self.port}/json/activate/{target_id}"
        )

    @property
    def ws_url(self) -> str:
        """Get WebSocket URL for CDP connection."""
        if not self._ws_url:
            raise RuntimeError("CDP not started")
        return self._ws_url

    def get_launch_command(self) -> str:
        """Get the command to launch Chrome manually with CDP enabled."""
        cmd_parts = [
            "google-chrome",
            f"--remote-debugging-port={self.port}",
        ]
        if self.headless:
            cmd_parts.append("--headless=new")
        if self.proxy_url:
            cmd_parts.append(f"--proxy-server={self.proxy_url}")
        return " ".join(cmd_parts)


class CDPSession:
    """WebSocket session for CDP commands."""

    def __init__(self, ws_url: str) -> None:
        self.ws_url = ws_url
        self._ws: Any = None
        self._id = 0
        self._responses: dict[int, asyncio.Future[dict[str, Any]]] = {}

    async def connect(self) -> None:
        """Connect to CDP WebSocket."""
        try:
            import websockets
            self._ws = await websockets.connect(self.ws_url)
            asyncio.create_task(self._receive_loop())
            logger.info("CDP WebSocket connected")
        except ImportError:
            logger.warning("websockets not installed, CDP WebSocket unavailable")

    async def _receive_loop(self) -> None:
        """Receive messages from CDP."""
        if not self._ws:
            return
        async for message in self._ws:
            data = json.loads(message)
            if "id" in data:
                msg_id = data["id"]
                if msg_id in self._responses:
                    self._responses[msg_id].set_result(data)

    async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send CDP command."""
        if not self._ws:
            raise RuntimeError("WebSocket not connected")

        self._id += 1
        message = {"id": self._id, "method": method}
        if params:
            message["params"] = params

        future: asyncio.Future[dict[str, Any]] = asyncio.Future()
        self._responses[self._id] = future

        await self._ws.send(json.dumps(message))
        result = await asyncio.wait_for(future, timeout=30)
        del self._responses[self._id]

        return result.get("result", {})

    async def disconnect(self) -> None:
        """Disconnect from CDP."""
        if self._ws:
            await self._ws.close()

    # Common CDP commands
    async def navigate(self, url: str) -> None:
        """Navigate to URL."""
        await self.send("Page.navigate", {"url": url})

    async def enable_network(self) -> None:
        """Enable network domain."""
        await self.send("Network.enable")

    async def enable_page(self) -> None:
        """Enable page domain."""
        await self.send("Page.enable")

    async def get_cookies(self) -> list[dict[str, Any]]:
        """Get all cookies."""
        result = await self.send("Network.getAllCookies")
        return result.get("cookies", [])

    async def screenshot(self, format: str = "png") -> str:
        """Take screenshot, returns base64."""
        result = await self.send("Page.captureScreenshot", {"format": format})
        return result.get("data", "")

    async def evaluate(self, expression: str) -> Any:
        """Evaluate JavaScript."""
        result = await self.send(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True},
        )
        return result.get("result", {}).get("value")
