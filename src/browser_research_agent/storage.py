"""Storage backends for research data (SQLite, JSON, Markdown)."""

import logging
from pathlib import Path
from typing import Any

import aiosqlite

from .config import settings
from .models import ResearchSession, SiteAnalysis

logger = logging.getLogger(__name__)


class StorageBackend:
    """Base class for storage backends."""

    async def save_session(self, session: ResearchSession) -> None:
        raise NotImplementedError

    async def load_session(self, session_id: str) -> ResearchSession | None:
        raise NotImplementedError

    async def list_sessions(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class SQLiteStorage(StorageBackend):
    """SQLite storage backend."""

    def __init__(self, db_path: Path = settings.db_path) -> None:
        self.db_path = db_path

    async def _init_db(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    target_url TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    conclusion TEXT,
                    final_recommendation TEXT,
                    data JSON NOT NULL
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    data JSON NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    method TEXT NOT NULL,
                    url TEXT NOT NULL,
                    status INTEGER,
                    is_api BOOLEAN,
                    data JSON NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_analyses_session
                ON analyses(session_id)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_requests_session
                ON requests(session_id)
            """)

            await db.commit()
            logger.info(f"Database initialized: {self.db_path}")

    async def save_session(self, session: ResearchSession) -> None:
        """Save a research session."""
        await self._init_db()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO sessions
                (id, created_at, target_url, objective, conclusion, final_recommendation, data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.created_at.isoformat(),
                    session.target_url,
                    session.objective,
                    session.conclusion,
                    session.final_recommendation,
                    session.model_dump_json(),
                ),
            )

            # Save analyses
            for analysis in session.analyses:
                await db.execute(
                    """
                    INSERT INTO analyses
                    (session_id, url, domain, timestamp, data)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        session.id,
                        analysis.url,
                        analysis.domain,
                        analysis.timestamp.isoformat(),
                        analysis.model_dump_json(),
                    ),
                )

                # Save captured requests
                for req in analysis.captured_requests:
                    await db.execute(
                        """
                        INSERT OR IGNORE INTO requests
                        (id, session_id, timestamp, method, url, status, is_api, data)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            req.id,
                            session.id,
                            req.timestamp.isoformat(),
                            req.method.value,
                            req.url,
                            req.response_status,
                            req.is_api,
                            req.model_dump_json(),
                        ),
                    )

            await db.commit()
            logger.info(f"Session saved: {session.id}")

    async def load_session(self, session_id: str) -> ResearchSession | None:
        """Load a research session."""
        await self._init_db()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT data FROM sessions WHERE id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()

            if row:
                return ResearchSession.model_validate_json(row["data"])
            return None

    async def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions."""
        await self._init_db()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, created_at, target_url, objective, conclusion
                FROM sessions
                ORDER BY created_at DESC
                """
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def search_requests(
        self,
        session_id: str | None = None,
        url_pattern: str | None = None,
        method: str | None = None,
        is_api: bool | None = None,
    ) -> list[dict[str, Any]]:
        """Search captured requests."""
        await self._init_db()

        query = "SELECT * FROM requests WHERE 1=1"
        params: list[Any] = []

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if url_pattern:
            query += " AND url LIKE ?"
            params.append(f"%{url_pattern}%")
        if method:
            query += " AND method = ?"
            params.append(method)
        if is_api is not None:
            query += " AND is_api = ?"
            params.append(is_api)

        query += " ORDER BY timestamp DESC LIMIT 100"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


class JSONStorage(StorageBackend):
    """JSON file storage backend."""

    def __init__(self, data_dir: Path = settings.data_dir) -> None:
        self.data_dir = data_dir / "sessions"

    async def save_session(self, session: ResearchSession) -> None:
        """Save session to JSON file."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        path = self.data_dir / f"{session.id}.json"
        path.write_text(session.model_dump_json(indent=2))
        logger.info(f"Session saved: {path}")

    async def load_session(self, session_id: str) -> ResearchSession | None:
        """Load session from JSON file."""
        path = self.data_dir / f"{session_id}.json"
        if path.exists():
            return ResearchSession.model_validate_json(path.read_text())
        return None

    async def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions."""
        if not self.data_dir.exists():
            return []

        sessions = []
        for path in self.data_dir.glob("*.json"):
            try:
                session = ResearchSession.model_validate_json(path.read_text())
                sessions.append({
                    "id": session.id,
                    "created_at": session.created_at.isoformat(),
                    "target_url": session.target_url,
                    "objective": session.objective,
                })
            except Exception as e:
                logger.warning(f"Failed to load {path}: {e}")

        return sorted(sessions, key=lambda x: x["created_at"], reverse=True)


class MarkdownExporter:
    """Export research sessions to Markdown."""

    def __init__(self, output_dir: Path = settings.data_dir / "reports") -> None:
        self.output_dir = output_dir

    def export(self, session: ResearchSession) -> Path:
        """Export session to Markdown file."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"report_{session.id[:8]}.md"

        content = self._generate_markdown(session)
        path.write_text(content)
        logger.info(f"Report exported: {path}")
        return path

    def _generate_markdown(self, session: ResearchSession) -> str:
        """Generate Markdown content."""
        lines = [
            "# Browser Automation Research Report",
            "",
            "| Field | Value |",
            "|-------|-------|",
            f"| **Target URL** | {session.target_url} |",
            f"| **Objective** | {session.objective} |",
            f"| **Date** | {session.created_at.strftime('%Y-%m-%d %H:%M')} |",
            f"| **Session ID** | `{session.id}` |",
            "",
        ]

        for i, analysis in enumerate(session.analyses, 1):
            lines.extend(self._format_analysis(i, analysis))

        if session.conclusion:
            lines.extend([
                "## Conclusion",
                "",
                f"{session.conclusion}",
                "",
            ])

        if session.final_recommendation:
            lines.extend([
                "## Recommended Tools",
                "",
                "```",
                f"{session.final_recommendation}",
                "```",
                "",
            ])

        # Add quick start code
        lines.extend(self._generate_quickstart(session))

        return "\n".join(lines)

    def _format_analysis(self, index: int, analysis: SiteAnalysis) -> list[str]:
        """Format a single analysis."""
        lines = [
            f"## Site Analysis: {analysis.domain}",
            "",
        ]

        # Technologies table
        if analysis.technologies or analysis.anti_bot:
            lines.extend([
                "### Technologies & Protection",
                "",
                "| Category | Detected |",
                "|----------|----------|",
            ])
            if analysis.technologies:
                lines.append(f"| Frameworks | {', '.join(analysis.technologies)} |")
            if analysis.anti_bot:
                ab_names = [ab.value for ab in analysis.anti_bot]
                lines.append(f"| Anti-Bot | {', '.join(ab_names)} |")
            lines.append("")

        # Authentication
        lines.extend([
            "### Authentication",
            "",
            f"- **Required:** {'Yes' if analysis.requires_auth else 'No'}",
        ])
        if analysis.auth_methods:
            methods = [am.value for am in analysis.auth_methods]
            lines.append(f"- **Methods:** {', '.join(methods)}")
        if analysis.login_url:
            lines.append(f"- **Login URL:** `{analysis.login_url}`")
        lines.append("")

        # API Endpoints
        if analysis.discovered_endpoints:
            lines.extend([
                "### Discovered API Endpoints",
                "",
                "| Endpoint | Methods | Auth |",
                "|----------|---------|------|",
            ])
            for ep in analysis.discovered_endpoints[:15]:
                methods = ", ".join(m.value for m in ep.methods)
                auth = "Yes" if ep.auth_required else "No"
                lines.append(f"| `{ep.url_pattern}` | {methods} | {auth} |")
            lines.append("")

        # Recommendations
        if analysis.recommended_approach:
            lines.extend([
                "### Recommendations",
                "",
                f"{analysis.recommended_approach}",
                "",
                f"**Suggested Tools:** {', '.join(analysis.recommended_tools)}",
                "",
            ])

        return lines

    def _generate_quickstart(self, session: ResearchSession) -> list[str]:
        """Generate quickstart code based on recommendations."""
        if not session.analyses:
            return []

        analysis = session.analyses[-1]
        tools = analysis.recommended_tools

        lines = [
            "## Quick Start Code",
            "",
        ]

        # Playwright example
        if "playwright" in tools:
            lines.extend([
                "### Playwright",
                "",
                "```python",
                "from playwright.async_api import async_playwright",
                "",
                "async def main():",
                "    async with async_playwright() as p:",
                "        browser = await p.chromium.launch(headless=False)",
                "        page = await browser.new_page()",
                f"        await page.goto('{session.target_url}')",
                "        # Your automation code here",
                "        await browser.close()",
                "```",
                "",
            ])

        # httpx example for API
        if "httpx" in tools and analysis.discovered_endpoints:
            ep = analysis.discovered_endpoints[0]
            lines.extend([
                "### Direct HTTP (httpx)",
                "",
                "```python",
                "import httpx",
                "",
                "async def fetch_data():",
                "    async with httpx.AsyncClient() as client:",
                f"        response = await client.get('{ep.url_pattern}')",
                "        return response.json()",
                "```",
                "",
            ])

        # Anti-detect example
        if "camoufox" in tools:
            lines.extend([
                "### Anti-Detect (Camoufox)",
                "",
                "```python",
                "from camoufox.sync_api import Camoufox",
                "",
                "with Camoufox(headless=False) as browser:",
                "    page = browser.new_page()",
                f"    page.goto('{session.target_url}')",
                "    # Fingerprint is automatically randomized",
                "```",
                "",
            ])

        return lines
