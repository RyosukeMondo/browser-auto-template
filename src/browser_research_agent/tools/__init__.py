"""Browser research tools for AI agent."""

from .proxy import ProxyCapture
from .browser import BrowserController
from .cdp import CDPController
from .analyzer import SiteAnalyzer

__all__ = ["ProxyCapture", "BrowserController", "CDPController", "SiteAnalyzer"]
