"""TechCorp Playwright browser tool, allowlist, and sandbox desk."""

from techcorp.browser.playwright_tool import (
    ALLOWED_HOSTS,
    OUTAGE_LINE,
    build_browser_desk,
    fetch_status_page,
    is_url_allowed,
    read_status_page,
    read_status_page_ungated,
    serve_fixtures,
)
from techcorp.browser.sandbox import (
    PAGE_DATA_RULE,
    first_write_proposal,
    sandboxed_browser_desk,
    unguarded_browser_desk,
)

__all__ = [
    "ALLOWED_HOSTS",
    "OUTAGE_LINE",
    "PAGE_DATA_RULE",
    "build_browser_desk",
    "fetch_status_page",
    "first_write_proposal",
    "is_url_allowed",
    "read_status_page",
    "read_status_page_ungated",
    "sandboxed_browser_desk",
    "serve_fixtures",
    "unguarded_browser_desk",
]
