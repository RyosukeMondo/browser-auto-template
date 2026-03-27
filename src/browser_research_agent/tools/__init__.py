"""Browser research tools for AI agent."""

from .analyzer import SiteAnalyzer
from .browser import BrowserController
from .cdp import CDPController
from .proxy import ProxyCapture

__all__ = ["ProxyCapture", "BrowserController", "CDPController", "SiteAnalyzer"]
