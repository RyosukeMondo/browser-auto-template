"""Tests for CLI commands."""

import pytest
from typer.testing import CliRunner
from pathlib import Path

from browser_research_agent.cli import app


runner = CliRunner()


class TestCLI:
    def test_version(self) -> None:
        result = runner.invoke(app, ["-V"])
        assert result.exit_code == 0
        assert "browser-research-agent" in result.stdout

    def test_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "investigate" in result.stdout
        assert "proxy" in result.stdout
        assert "browser" in result.stdout

    def test_investigate_help(self) -> None:
        result = runner.invoke(app, ["investigate", "--help"])
        assert result.exit_code == 0
        assert "URL to investigate" in result.stdout

    def test_proxy_help(self) -> None:
        result = runner.invoke(app, ["proxy", "--help"])
        assert result.exit_code == 0
        assert "--port" in result.stdout

    def test_sessions_empty(self) -> None:
        # Should not crash when no sessions exist
        result = runner.invoke(app, ["sessions"])
        # May show "No sessions found" or a table
        assert result.exit_code == 0


class TestAnalyzeCommand:
    def test_analyze_har(self, tmp_path: Path) -> None:
        # Create a minimal HAR file
        har_content = """{
            "log": {
                "version": "1.2",
                "entries": [
                    {
                        "request": {
                            "method": "GET",
                            "url": "https://api.example.com/v1/data",
                            "headers": []
                        },
                        "response": {
                            "status": 200,
                            "headers": [],
                            "content": {
                                "mimeType": "application/json"
                            }
                        }
                    }
                ]
            }
        }"""

        har_file = tmp_path / "test.har"
        har_file.write_text(har_content)

        result = runner.invoke(app, ["analyze", str(har_file)])
        assert result.exit_code == 0
        assert "Analysis" in result.stdout or "requests" in result.stdout.lower()

    def test_analyze_empty_har(self, tmp_path: Path) -> None:
        har_content = '{"log": {"entries": []}}'
        har_file = tmp_path / "empty.har"
        har_file.write_text(har_content)

        result = runner.invoke(app, ["analyze", str(har_file)])
        # Should handle gracefully
        assert result.exit_code == 0
