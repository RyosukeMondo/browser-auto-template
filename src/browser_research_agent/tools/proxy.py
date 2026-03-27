"""Mitmproxy-based traffic capture and analysis."""

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from mitmproxy import http, options
from mitmproxy.tools import dump

from ..config import settings
from ..models import CapturedRequest, RequestMethod

logger = logging.getLogger(__name__)


class RequestCaptureAddon:
    """Mitmproxy addon to capture and store requests."""

    def __init__(self) -> None:
        self.requests: list[CapturedRequest] = []
        self._lock = asyncio.Lock()

    def request(self, flow: http.HTTPFlow) -> None:
        """Called when a request is received."""
        pass  # We capture on response for complete data

    def response(self, flow: http.HTTPFlow) -> None:
        """Called when a response is received."""
        try:
            request = flow.request
            response = flow.response

            # Parse query params
            query_params = dict(request.query) if request.query else {}

            # Determine content types
            req_content_type = request.headers.get("content-type", "")
            resp_content_type = response.headers.get("content-type", "") if response else ""

            # Check if API/XHR
            is_api = any(
                t in resp_content_type.lower() for t in ["application/json", "application/xml"]
            )
            is_xhr = request.headers.get("x-requested-with", "").lower() == "xmlhttprequest"

            # Get bodies (limit size)
            max_body_size = 1024 * 100  # 100KB
            req_body = None
            if request.content and len(request.content) < max_body_size:
                try:
                    req_body = request.content.decode("utf-8", errors="replace")
                except Exception:
                    req_body = "<binary>"

            resp_body = None
            if response and response.content and len(response.content) < max_body_size:
                try:
                    resp_body = response.content.decode("utf-8", errors="replace")
                except Exception:
                    resp_body = "<binary>"

            captured = CapturedRequest(
                id=str(uuid4()),
                timestamp=datetime.now(tz=UTC),
                method=RequestMethod(request.method),
                url=request.pretty_url,
                headers=dict(request.headers),
                query_params=query_params,
                body=req_body,
                response_status=response.status_code if response else None,
                response_headers=dict(response.headers) if response else {},
                response_body=resp_body,
                response_time_ms=flow.response.timestamp_end - flow.request.timestamp_start
                if flow.response
                else None,
                content_type=resp_content_type,
                is_api=is_api,
                is_xhr=is_xhr,
            )
            self.requests.append(captured)
            logger.debug(f"Captured: {request.method} {request.pretty_url}")
        except Exception as e:
            logger.error(f"Error capturing request: {e}")

    def get_requests(self) -> list[CapturedRequest]:
        """Get all captured requests."""
        return self.requests.copy()

    def clear(self) -> None:
        """Clear captured requests."""
        self.requests.clear()

    def get_api_requests(self) -> list[CapturedRequest]:
        """Get only API/XHR requests."""
        return [r for r in self.requests if r.is_api or r.is_xhr]


class ProxyCapture:
    """Manage mitmproxy for traffic capture."""

    def __init__(
        self,
        host: str = settings.proxy_host,
        port: int = settings.proxy_port,
    ) -> None:
        self.host = host
        self.port = port
        self.addon = RequestCaptureAddon()
        self._master: dump.DumpMaster | None = None
        self._task: asyncio.Task[Any] | None = None

    async def start(self) -> None:
        """Start the proxy server."""
        opts = options.Options(listen_host=self.host, listen_port=self.port)
        self._master = dump.DumpMaster(opts)
        self._master.addons.add(self.addon)

        logger.info(f"Starting proxy on {self.host}:{self.port}")
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        """Run the proxy server."""
        if self._master:
            await self._master.run()

    async def stop(self) -> None:
        """Stop the proxy server."""
        if self._master:
            self._master.shutdown()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Proxy stopped")

    def get_requests(self) -> list[CapturedRequest]:
        """Get all captured requests."""
        return self.addon.get_requests()

    def get_api_requests(self) -> list[CapturedRequest]:
        """Get API/XHR requests only."""
        return self.addon.get_api_requests()

    def clear(self) -> None:
        """Clear captured requests."""
        self.addon.clear()

    def export_har(self, path: Path) -> None:
        """Export captured requests to HAR format."""
        requests = self.get_requests()
        har = {
            "log": {
                "version": "1.2",
                "creator": {"name": "browser-research-agent", "version": "0.1.0"},
                "entries": [self._request_to_har_entry(r) for r in requests],
            }
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(har, indent=2, default=str))
        logger.info(f"Exported {len(requests)} requests to {path}")

    def export_json(self, path: Path) -> None:
        """Export captured requests to JSON."""
        requests = self.get_requests()
        data = [r.model_dump() for r in requests]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))
        logger.info(f"Exported {len(requests)} requests to {path}")

    def _request_to_har_entry(self, req: CapturedRequest) -> dict[str, Any]:
        """Convert CapturedRequest to HAR entry format."""
        return {
            "startedDateTime": req.timestamp.isoformat(),
            "time": req.response_time_ms or 0,
            "request": {
                "method": req.method.value,
                "url": req.url,
                "headers": [{"name": k, "value": v} for k, v in req.headers.items()],
                "queryString": [{"name": k, "value": v} for k, v in req.query_params.items()],
                "postData": {"text": req.body} if req.body else None,
            },
            "response": {
                "status": req.response_status or 0,
                "headers": [{"name": k, "value": v} for k, v in req.response_headers.items()],
                "content": {"text": req.response_body, "mimeType": req.content_type or ""},
            },
        }

    def get_proxy_url(self) -> str:
        """Get proxy URL for browser configuration."""
        return f"http://{self.host}:{self.port}"
