"""Tests for data models."""

from datetime import datetime

from browser_research_agent.models import (
    AntiBot,
    AuthMethod,
    CapturedRequest,
    DiscoveredEndpoint,
    RequestMethod,
    ResearchSession,
    SiteAnalysis,
)


class TestCapturedRequest:
    def test_create_basic_request(self) -> None:
        req = CapturedRequest(
            id="test-1",
            method=RequestMethod.GET,
            url="https://example.com/api/data",
        )
        assert req.id == "test-1"
        assert req.method == RequestMethod.GET
        assert req.url == "https://example.com/api/data"
        assert req.is_api is False
        assert req.headers == {}

    def test_create_api_request(self) -> None:
        req = CapturedRequest(
            id="test-2",
            method=RequestMethod.POST,
            url="https://example.com/api/v1/users",
            headers={"content-type": "application/json"},
            body='{"name": "test"}',
            response_status=201,
            content_type="application/json",
            is_api=True,
        )
        assert req.is_api is True
        assert req.response_status == 201
        assert "content-type" in req.headers

    def test_request_serialization(self) -> None:
        req = CapturedRequest(
            id="test-3",
            method=RequestMethod.GET,
            url="https://example.com",
        )
        data = req.model_dump()
        assert data["id"] == "test-3"
        assert data["method"] == "GET"

        # Deserialize
        req2 = CapturedRequest.model_validate(data)
        assert req2.id == req.id


class TestDiscoveredEndpoint:
    def test_create_endpoint(self) -> None:
        ep = DiscoveredEndpoint(
            url_pattern="https://api.example.com/v1/users/{id}",
            methods=[RequestMethod.GET, RequestMethod.PUT],
            auth_required=True,
            auth_method=AuthMethod.BEARER,
        )
        assert ep.auth_required is True
        assert len(ep.methods) == 2
        assert AuthMethod.BEARER == ep.auth_method


class TestSiteAnalysis:
    def test_create_analysis(self) -> None:
        analysis = SiteAnalysis(
            url="https://example.com",
            domain="example.com",
            technologies=["React", "Node.js"],
            anti_bot=[AntiBot.CLOUDFLARE],
            requires_auth=True,
            auth_methods=[AuthMethod.COOKIE],
        )
        assert analysis.domain == "example.com"
        assert "React" in analysis.technologies
        assert AntiBot.CLOUDFLARE in analysis.anti_bot

    def test_analysis_with_endpoints(self) -> None:
        ep = DiscoveredEndpoint(
            url_pattern="/api/data",
            methods=[RequestMethod.GET],
        )
        analysis = SiteAnalysis(
            url="https://example.com",
            domain="example.com",
            discovered_endpoints=[ep],
        )
        assert len(analysis.discovered_endpoints) == 1


class TestResearchSession:
    def test_create_session(self) -> None:
        session = ResearchSession(
            id="session-123",
            target_url="https://example.com",
            objective="Test automation",
        )
        assert session.id == "session-123"
        assert session.target_url == "https://example.com"
        assert isinstance(session.created_at, datetime)

    def test_session_with_analyses(self) -> None:
        analysis = SiteAnalysis(
            url="https://example.com",
            domain="example.com",
        )
        session = ResearchSession(
            id="session-456",
            target_url="https://example.com",
            objective="Test",
            analyses=[analysis],
            conclusion="Use Playwright",
        )
        assert len(session.analyses) == 1
        assert session.conclusion == "Use Playwright"
