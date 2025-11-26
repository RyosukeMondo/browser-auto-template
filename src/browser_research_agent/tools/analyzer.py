"""Site analysis and recommendation engine."""

import logging
import re
from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

from ..models import (
    AntiBot,
    AuthMethod,
    CapturedRequest,
    DiscoveredEndpoint,
    RequestMethod,
    SiteAnalysis,
)

logger = logging.getLogger(__name__)


class SiteAnalyzer:
    """Analyze captured traffic and site structure."""

    def __init__(self) -> None:
        self._patterns: dict[str, re.Pattern[str]] = {
            "api_path": re.compile(r"/api/|/v\d+/|/graphql"),
            "auth_header": re.compile(r"authorization|x-api-key|x-auth-token", re.I),
            "json_content": re.compile(r"application/json"),
            "session_cookie": re.compile(r"session|token|auth|jwt", re.I),
        }

    def analyze(
        self,
        url: str,
        requests: list[CapturedRequest],
        tech_detection: dict[str, list[str]] | None = None,
        forms: list[dict[str, Any]] | None = None,
    ) -> SiteAnalysis:
        """Perform comprehensive site analysis."""
        parsed = urlparse(url)

        analysis = SiteAnalysis(
            url=url,
            domain=parsed.netloc,
        )

        # Analyze technologies
        if tech_detection:
            analysis.technologies = (
                tech_detection.get("frameworks", [])
                + tech_detection.get("libraries", [])
            )
            analysis.frameworks = tech_detection.get("frameworks", [])
            analysis.anti_bot = [
                AntiBot(ab.lower()) if ab.lower() in [e.value for e in AntiBot] else AntiBot.UNKNOWN
                for ab in tech_detection.get("anti_bot", [])
            ]

        # Analyze requests
        if requests:
            analysis.captured_requests = requests
            analysis.discovered_endpoints = self._discover_endpoints(requests, parsed.netloc)
            auth_methods = self._detect_auth_methods(requests)
            analysis.auth_methods = auth_methods
            analysis.requires_auth = len(auth_methods) > 0 and AuthMethod.NONE not in auth_methods

            # Find API base URL
            api_requests = [r for r in requests if r.is_api]
            if api_requests:
                api_urls = [urlparse(r.url) for r in api_requests]
                common_paths = self._find_common_prefix([u.path for u in api_urls])
                if common_paths:
                    analysis.api_base_url = f"{parsed.scheme}://{parsed.netloc}{common_paths}"

        # Analyze forms for login detection
        if forms:
            for form in forms:
                fields = form.get("fields", [])
                field_names = [f.get("name", "").lower() for f in fields]
                field_types = [f.get("type", "").lower() for f in fields]

                if "password" in field_types or any("pass" in n for n in field_names):
                    analysis.login_url = form.get("action") or url
                    analysis.requires_auth = True
                    break

        # Generate recommendations
        analysis.recommended_approach, analysis.recommended_tools = self._generate_recommendations(
            analysis
        )

        return analysis

    def _discover_endpoints(
        self, requests: list[CapturedRequest], domain: str
    ) -> list[DiscoveredEndpoint]:
        """Discover and categorize API endpoints."""
        endpoints: dict[str, DiscoveredEndpoint] = {}

        for req in requests:
            parsed = urlparse(req.url)

            # Skip external domains
            if domain not in parsed.netloc:
                continue

            # Skip static resources
            if self._is_static_resource(parsed.path):
                continue

            # Normalize path (replace IDs with placeholders)
            pattern = self._normalize_path(parsed.path)

            if pattern not in endpoints:
                endpoints[pattern] = DiscoveredEndpoint(
                    url_pattern=f"{parsed.scheme}://{parsed.netloc}{pattern}",
                    methods=[],
                    request_content_type=req.headers.get("content-type"),
                    response_content_type=req.content_type,
                )

            ep = endpoints[pattern]
            if req.method not in ep.methods:
                ep.methods.append(req.method)

            # Check auth
            if not ep.auth_required:
                ep.auth_required, ep.auth_method = self._check_request_auth(req)

            # Store sample
            if not ep.sample_request:
                ep.sample_request = req

        return list(endpoints.values())

    def _normalize_path(self, path: str) -> str:
        """Replace dynamic path segments with placeholders."""
        segments = path.split("/")
        normalized = []
        for seg in segments:
            if not seg:
                normalized.append(seg)
            elif seg.isdigit():
                normalized.append("{id}")
            elif re.match(r"^[a-f0-9-]{32,}$", seg, re.I):  # UUID-like
                normalized.append("{uuid}")
            elif re.match(r"^[a-f0-9]{24}$", seg, re.I):  # MongoDB ObjectId
                normalized.append("{id}")
            else:
                normalized.append(seg)
        return "/".join(normalized)

    def _is_static_resource(self, path: str) -> bool:
        """Check if path is a static resource."""
        static_extensions = {
            ".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg",
            ".ico", ".woff", ".woff2", ".ttf", ".eot", ".map",
        }
        return any(path.lower().endswith(ext) for ext in static_extensions)

    def _check_request_auth(self, req: CapturedRequest) -> tuple[bool, AuthMethod]:
        """Check if request uses authentication."""
        headers_lower = {k.lower(): v for k, v in req.headers.items()}

        # Bearer token
        auth_header = headers_lower.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            return True, AuthMethod.BEARER
        if auth_header.lower().startswith("basic "):
            return True, AuthMethod.BASIC

        # API Key
        for key in ["x-api-key", "api-key", "apikey"]:
            if key in headers_lower:
                return True, AuthMethod.API_KEY

        # Cookie-based (check for session cookies)
        cookie = headers_lower.get("cookie", "")
        if self._patterns["session_cookie"].search(cookie):
            return True, AuthMethod.COOKIE

        return False, AuthMethod.NONE

    def _detect_auth_methods(self, requests: list[CapturedRequest]) -> list[AuthMethod]:
        """Detect all authentication methods used."""
        methods: set[AuthMethod] = set()

        for req in requests:
            has_auth, method = self._check_request_auth(req)
            if has_auth:
                methods.add(method)

        return list(methods) if methods else [AuthMethod.NONE]

    def _find_common_prefix(self, paths: list[str]) -> str:
        """Find common path prefix."""
        if not paths:
            return ""

        # Split paths and find common segments
        split_paths = [p.split("/") for p in paths]
        if not split_paths:
            return ""

        common = []
        for segments in zip(*split_paths):
            if len(set(segments)) == 1:
                common.append(segments[0])
            else:
                break

        return "/".join(common)

    def _generate_recommendations(
        self, analysis: SiteAnalysis
    ) -> tuple[str, list[str]]:
        """Generate tool recommendations based on analysis."""
        tools: list[str] = []
        approach_parts: list[str] = []

        # Anti-bot handling
        if analysis.anti_bot and AntiBot.NONE not in analysis.anti_bot:
            anti_bot_names = [ab.value for ab in analysis.anti_bot if ab != AntiBot.NONE]
            approach_parts.append(f"Site uses anti-bot: {', '.join(anti_bot_names)}")

            if AntiBot.CLOUDFLARE in analysis.anti_bot:
                tools.append("cloudscraper")
                tools.append("camoufox")
            elif any(ab in analysis.anti_bot for ab in [AntiBot.DATADOME, AntiBot.AKAMAI]):
                tools.append("camoufox")
                tools.append("undetected-chromedriver")

            approach_parts.append("Recommend: Anti-detect browser or stealth mode")
        else:
            approach_parts.append("No significant anti-bot detected")
            tools.append("playwright")

        # API vs browser automation
        api_endpoints = [ep for ep in analysis.discovered_endpoints if "/api" in ep.url_pattern]
        if api_endpoints:
            approach_parts.append(f"Found {len(api_endpoints)} API endpoints")
            tools.append("httpx")
            approach_parts.append("Consider: Direct API calls may be more efficient")
        else:
            approach_parts.append("No clear API structure - browser automation recommended")

        # Authentication handling
        if analysis.requires_auth:
            auth_names = [am.value for am in analysis.auth_methods if am != AuthMethod.NONE]
            approach_parts.append(f"Authentication required: {', '.join(auth_names)}")

            if AuthMethod.COOKIE in analysis.auth_methods:
                approach_parts.append("Session management needed - use browser with cookie persistence")
            if AuthMethod.BEARER in analysis.auth_methods:
                approach_parts.append("Token-based auth - can use direct HTTP after login")

        # Traffic capture recommendation
        if len(analysis.captured_requests) > 0:
            approach_parts.append(f"Captured {len(analysis.captured_requests)} requests for analysis")
            tools.append("mitmproxy")

        # SPA detection
        if "React" in analysis.frameworks or "Vue" in analysis.frameworks:
            approach_parts.append(f"SPA detected ({', '.join(analysis.frameworks)})")
            approach_parts.append("Wait for dynamic content - use networkidle or explicit waits")

        # Ensure playwright is primary if no special requirements
        if "playwright" not in tools:
            tools.insert(0, "playwright")

        approach = "\n".join(f"- {p}" for p in approach_parts)

        return approach, tools

    def compare_approaches(
        self, analysis: SiteAnalysis
    ) -> dict[str, dict[str, Any]]:
        """Compare different automation approaches for this site."""
        comparisons: dict[str, dict[str, Any]] = {}

        # Playwright
        playwright_pros = ["Cross-browser", "Built-in waits", "Good for SPAs"]
        playwright_cons = []
        if analysis.anti_bot and AntiBot.NONE not in analysis.anti_bot:
            playwright_cons.append("May be detected by anti-bot")
        comparisons["playwright"] = {
            "suitable": len(playwright_cons) == 0,
            "pros": playwright_pros,
            "cons": playwright_cons,
            "effort": "low",
        }

        # Direct HTTP
        http_pros = ["Fast", "Low resource usage", "Easy to parallelize"]
        http_cons = []
        if analysis.frameworks:
            http_cons.append("SPA - may need JS rendering")
        if analysis.requires_auth and AuthMethod.COOKIE in analysis.auth_methods:
            http_cons.append("Cookie auth - need session management")
        comparisons["httpx"] = {
            "suitable": len(http_cons) == 0,
            "pros": http_pros,
            "cons": http_cons,
            "effort": "low" if not http_cons else "medium",
        }

        # Anti-detect browser
        antidetect_pros = ["Bypasses fingerprinting", "Real browser behavior"]
        antidetect_cons = ["Slower", "More complex setup"]
        if not analysis.anti_bot or AntiBot.NONE in analysis.anti_bot:
            antidetect_cons.append("Overkill for this site")
        comparisons["camoufox"] = {
            "suitable": bool(analysis.anti_bot and AntiBot.NONE not in analysis.anti_bot),
            "pros": antidetect_pros,
            "cons": antidetect_cons,
            "effort": "medium",
        }

        # Proxy capture
        comparisons["mitmproxy"] = {
            "suitable": True,
            "pros": ["Full traffic visibility", "API discovery", "Debug any approach"],
            "cons": ["Additional setup", "HTTPS cert handling"],
            "effort": "low",
            "note": "Recommended for initial research regardless of final approach",
        }

        return comparisons
