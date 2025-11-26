"""Tests for storage backends."""

import pytest
from pathlib import Path

from browser_research_agent.models import ResearchSession, SiteAnalysis
from browser_research_agent.storage import SQLiteStorage, JSONStorage, MarkdownExporter


class TestSQLiteStorage:
    @pytest.fixture
    def storage(self, data_dir: Path) -> SQLiteStorage:
        return SQLiteStorage(db_path=data_dir / "test.db")

    @pytest.mark.asyncio
    async def test_save_and_load_session(self, storage: SQLiteStorage) -> None:
        session = ResearchSession(
            id="test-session-001",
            target_url="https://example.com",
            objective="Test storage",
        )

        await storage.save_session(session)
        loaded = await storage.load_session("test-session-001")

        assert loaded is not None
        assert loaded.id == session.id
        assert loaded.target_url == session.target_url

    @pytest.mark.asyncio
    async def test_list_sessions(self, storage: SQLiteStorage) -> None:
        session1 = ResearchSession(
            id="session-1",
            target_url="https://example1.com",
            objective="Test 1",
        )
        session2 = ResearchSession(
            id="session-2",
            target_url="https://example2.com",
            objective="Test 2",
        )

        await storage.save_session(session1)
        await storage.save_session(session2)

        sessions = await storage.list_sessions()
        assert len(sessions) == 2
        ids = [s["id"] for s in sessions]
        assert "session-1" in ids
        assert "session-2" in ids

    @pytest.mark.asyncio
    async def test_load_nonexistent_session(self, storage: SQLiteStorage) -> None:
        result = await storage.load_session("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_save_session_with_analysis(self, storage: SQLiteStorage) -> None:
        analysis = SiteAnalysis(
            url="https://example.com",
            domain="example.com",
            technologies=["React"],
        )
        session = ResearchSession(
            id="session-with-analysis",
            target_url="https://example.com",
            objective="Test",
            analyses=[analysis],
        )

        await storage.save_session(session)
        loaded = await storage.load_session("session-with-analysis")

        assert loaded is not None
        assert len(loaded.analyses) == 1
        assert "React" in loaded.analyses[0].technologies


class TestJSONStorage:
    @pytest.fixture
    def storage(self, data_dir: Path) -> JSONStorage:
        return JSONStorage(data_dir=data_dir)

    @pytest.mark.asyncio
    async def test_save_and_load_session(self, storage: JSONStorage) -> None:
        session = ResearchSession(
            id="json-test-001",
            target_url="https://example.com",
            objective="Test JSON storage",
        )

        await storage.save_session(session)
        loaded = await storage.load_session("json-test-001")

        assert loaded is not None
        assert loaded.id == session.id

    @pytest.mark.asyncio
    async def test_list_sessions(self, storage: JSONStorage) -> None:
        session = ResearchSession(
            id="json-list-test",
            target_url="https://example.com",
            objective="Test",
        )

        await storage.save_session(session)
        sessions = await storage.list_sessions()

        assert len(sessions) >= 1
        assert any(s["id"] == "json-list-test" for s in sessions)


class TestMarkdownExporter:
    @pytest.fixture
    def exporter(self, data_dir: Path) -> MarkdownExporter:
        return MarkdownExporter(output_dir=data_dir / "reports")

    def test_export_basic_session(self, exporter: MarkdownExporter) -> None:
        session = ResearchSession(
            id="md-test-001",
            target_url="https://example.com",
            objective="Test markdown export",
            conclusion="Use Playwright for automation",
        )

        path = exporter.export(session)
        assert path.exists()

        content = path.read_text()
        assert "# Browser Automation Research Report" in content
        assert "https://example.com" in content
        assert "Use Playwright for automation" in content

    def test_export_session_with_analysis(self, exporter: MarkdownExporter) -> None:
        analysis = SiteAnalysis(
            url="https://example.com",
            domain="example.com",
            technologies=["React", "Next.js"],
            recommended_tools=["playwright", "httpx"],
            recommended_approach="Use Playwright for full automation",
        )
        session = ResearchSession(
            id="md-analysis-test",
            target_url="https://example.com",
            objective="Full analysis test",
            analyses=[analysis],
        )

        path = exporter.export(session)
        content = path.read_text()

        assert "React" in content
        assert "Next.js" in content
        assert "playwright" in content
