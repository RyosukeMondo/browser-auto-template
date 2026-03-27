"""Tests for site analyzer."""


from browser_research_agent.models import (
    AntiBot,
    AuthMethod,
    CapturedRequest,
    RequestMethod,
)
from browser_research_agent.tools.analyzer import SiteAnalyzer


class TestSiteAnalyzer:
    def test_analyzer_creation(self, analyzer: SiteAnalyzer) -> None:
        assert analyzer is not None

    def test_analyze_empty_site(self, analyzer: SiteAnalyzer) -> None:
        analysis = analyzer.analyze(
            url="https://example.com",
            requests=[],
        )
        assert analysis.url == "https://example.com"
        assert analysis.domain == "example.com"
        assert analysis.requires_auth is False

    def test_analyze_with_tech_detection(self, analyzer: SiteAnalyzer) -> None:
        tech = {
            "frameworks": ["React", "Next.js"],
            "libraries": ["jQuery"],
            "anti_bot": ["Cloudflare"],
        }
        analysis = analyzer.analyze(
            url="https://example.com",
            requests=[],
            tech_detection=tech,
        )
        assert "React" in analysis.technologies
        assert "Next.js" in analysis.technologies
        assert AntiBot.CLOUDFLARE in analysis.anti_bot

    def test_analyze_with_login_form(self, analyzer: SiteAnalyzer) -> None:
        forms = [
            {
                "action": "https://example.com/login",
                "method": "post",
                "fields": [
                    {"name": "username", "type": "text"},
                    {"name": "password", "type": "password"},
                ],
            }
        ]
        analysis = analyzer.analyze(
            url="https://example.com",
            requests=[],
            forms=forms,
        )
        assert analysis.requires_auth is True
        assert analysis.login_url == "https://example.com/login"

    def test_discover_endpoints(self, analyzer: SiteAnalyzer) -> None:
        requests = [
            CapturedRequest(
                id="1",
                method=RequestMethod.GET,
                url="https://api.example.com/v1/users",
                response_status=200,
                content_type="application/json",
                is_api=True,
            ),
            CapturedRequest(
                id="2",
                method=RequestMethod.GET,
                url="https://api.example.com/v1/users/123",
                response_status=200,
                content_type="application/json",
                is_api=True,
            ),
            CapturedRequest(
                id="3",
                method=RequestMethod.POST,
                url="https://api.example.com/v1/users",
                headers={"authorization": "Bearer token123"},
                response_status=201,
                content_type="application/json",
                is_api=True,
            ),
        ]
        analysis = analyzer.analyze(
            url="https://api.example.com",
            requests=requests,
        )
        # Should normalize /users/123 to /users/{id}
        endpoints = analysis.discovered_endpoints
        assert len(endpoints) >= 1

        # Check methods are collected
        urls = [ep.url_pattern for ep in endpoints]
        assert any("/users" in url for url in urls)

    def test_detect_bearer_auth(self, analyzer: SiteAnalyzer) -> None:
        requests = [
            CapturedRequest(
                id="1",
                method=RequestMethod.GET,
                url="https://api.example.com/data",
                headers={"Authorization": "Bearer abc123"},
                response_status=200,
                is_api=True,
            ),
        ]
        analysis = analyzer.analyze(
            url="https://api.example.com",
            requests=requests,
        )
        assert analysis.requires_auth is True
        assert AuthMethod.BEARER in analysis.auth_methods

    def test_detect_cookie_auth(self, analyzer: SiteAnalyzer) -> None:
        requests = [
            CapturedRequest(
                id="1",
                method=RequestMethod.GET,
                url="https://example.com/dashboard",
                headers={"Cookie": "session_id=abc123; user_token=xyz"},
                response_status=200,
            ),
        ]
        analysis = analyzer.analyze(
            url="https://example.com",
            requests=requests,
        )
        assert AuthMethod.COOKIE in analysis.auth_methods

    def test_filter_static_resources(self, analyzer: SiteAnalyzer) -> None:
        requests = [
            CapturedRequest(
                id="1",
                method=RequestMethod.GET,
                url="https://example.com/api/data",
                is_api=True,
            ),
            CapturedRequest(
                id="2",
                method=RequestMethod.GET,
                url="https://example.com/static/app.js",
            ),
            CapturedRequest(
                id="3",
                method=RequestMethod.GET,
                url="https://example.com/images/logo.png",
            ),
        ]
        analysis = analyzer.analyze(
            url="https://example.com",
            requests=requests,
        )
        # Static resources should not be in discovered endpoints
        for ep in analysis.discovered_endpoints:
            assert ".js" not in ep.url_pattern
            assert ".png" not in ep.url_pattern


class TestRecommendations:
    def test_recommend_playwright_for_simple_site(self, analyzer: SiteAnalyzer) -> None:
        analysis = analyzer.analyze(
            url="https://example.com",
            requests=[],
            tech_detection={"frameworks": [], "anti_bot": []},
        )
        assert "playwright" in analysis.recommended_tools

    def test_recommend_antidetect_for_cloudflare(self, analyzer: SiteAnalyzer) -> None:
        analysis = analyzer.analyze(
            url="https://example.com",
            requests=[],
            tech_detection={"frameworks": [], "anti_bot": ["Cloudflare"]},
        )
        # Should recommend anti-detection tools
        assert any(
            tool in analysis.recommended_tools
            for tool in ["cloudscraper", "camoufox"]
        )

    def test_recommend_httpx_for_api(self, analyzer: SiteAnalyzer) -> None:
        requests = [
            CapturedRequest(
                id="1",
                method=RequestMethod.GET,
                url="https://api.example.com/api/v1/data",
                is_api=True,
                content_type="application/json",
            ),
        ]
        analysis = analyzer.analyze(
            url="https://api.example.com",
            requests=requests,
        )
        assert "httpx" in analysis.recommended_tools

    def test_compare_approaches(self, analyzer: SiteAnalyzer) -> None:
        analysis = analyzer.analyze(
            url="https://example.com",
            requests=[],
            tech_detection={"frameworks": ["React"], "anti_bot": []},
        )
        comparison = analyzer.compare_approaches(analysis)

        assert "playwright" in comparison
        assert "httpx" in comparison
        assert "camoufox" in comparison
        assert "mitmproxy" in comparison

        # Playwright should be suitable for React SPA
        assert comparison["playwright"]["suitable"] is True
