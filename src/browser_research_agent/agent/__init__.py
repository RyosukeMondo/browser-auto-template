"""Claude Agent SDK integration."""

from .tools import create_tools, AgentToolkit
from .runner import ResearchAgent
from .standalone import (
    toolkit,
    run_tool,
    run_tool_sync,
    cleanup,
    cleanup_sync,
    get_available_tools,
    print_tools,
    quick_investigate,
    capture_traffic,
    t,
)

__all__ = [
    # API mode
    "create_tools",
    "AgentToolkit",
    "ResearchAgent",
    # SUBSCRIPTION mode (standalone)
    "toolkit",
    "run_tool",
    "run_tool_sync",
    "cleanup",
    "cleanup_sync",
    "get_available_tools",
    "print_tools",
    "quick_investigate",
    "capture_traffic",
    "t",
]
