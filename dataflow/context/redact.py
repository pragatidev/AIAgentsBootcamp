"""Secrets and email addresses are masked before text enters the window.

Section 32 holds the full PII policy on a LangChain agent; this is the two masks the context desk needs.
"""

from __future__ import annotations

import re

SECRET_RE = re.compile(r"sk-[A-Za-z0-9_\-]{20,}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def redact(text: str) -> str:
    """The text with every sk- key and every email address replaced by a marker."""
    text = SECRET_RE.sub("[secret removed]", text or "")
    return EMAIL_RE.sub("[email removed]", text)
