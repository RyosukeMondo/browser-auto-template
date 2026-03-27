"""Data models for browser research."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RequestMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


class AntiBot(str, Enum):
    NONE = "none"
    CLOUDFLARE = "cloudflare"
    AKAMAI = "akamai"
    DATADOME = "datadome"
    PERIMETER_X = "perimeterx"
    RECAPTCHA = "recaptcha"
    HCAPTCHA = "hcaptcha"
    UNKNOWN = "unknown"


class AuthMethod(str, Enum):
    NONE = "none"
    COOKIE = "cookie"
    BEARER = "bearer"
    BASIC = "basic"
    API_KEY = "api_key"
    OAUTH = "oauth"
    CUSTOM = "custom"


class CapturedRequest(BaseModel):
    """Single captured HTTP request/response."""

    id: str = Field(description="Unique request ID")
    timestamp: datetime = Field(default_factory=datetime.now)
    method: RequestMethod
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    query_params: dict[str, str] = Field(default_factory=dict)
    body: str | None = None
    response_status: int | None = None
    response_headers: dict[str, str] = Field(default_factory=dict)
    response_body: str | None = None
    response_time_ms: float | None = None
    content_type: str | None = None
    is_api: bool = False
    is_xhr: bool = False


class DiscoveredEndpoint(BaseModel):
    """Discovered API endpoint from traffic analysis."""

    url_pattern: str = Field(description="URL pattern with path params")
    methods: list[RequestMethod] = Field(default_factory=list)
    auth_required: bool = False
    auth_method: AuthMethod = AuthMethod.NONE
    request_content_type: str | None = None
    response_content_type: str | None = None
    sample_request: CapturedRequest | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class SiteAnalysis(BaseModel):
    """Analysis results for a website."""

    url: str
    domain: str
    timestamp: datetime = Field(default_factory=datetime.now)
    title: str | None = None

    # Technical details
    technologies: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    anti_bot: list[AntiBot] = Field(default_factory=list)

    # Authentication
    auth_methods: list[AuthMethod] = Field(default_factory=list)
    login_url: str | None = None
    requires_auth: bool = False

    # API Discovery
    discovered_endpoints: list[DiscoveredEndpoint] = Field(default_factory=list)
    api_base_url: str | None = None

    # Captured traffic
    captured_requests: list[CapturedRequest] = Field(default_factory=list)

    # Recommendations
    recommended_approach: str | None = None
    recommended_tools: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ResearchSession(BaseModel):
    """A complete research session."""

    id: str
    created_at: datetime = Field(default_factory=datetime.now)
    target_url: str
    objective: str
    analyses: list[SiteAnalysis] = Field(default_factory=list)
    conclusion: str | None = None
    final_recommendation: str | None = None
