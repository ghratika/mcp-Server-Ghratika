"""
utils/html_to_text.py
────────────────────────────────────────────────────────────────
Converts HTML email bodies to clean, readable plain text / Markdown.

Uses BeautifulSoup to strip tags and markdownify to preserve
basic formatting (bold, links, lists) where possible.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def html_to_markdown(html: str) -> str:
    """
    Convert an HTML string to clean Markdown text.

    Args:
        html: Raw HTML content (e.g. an email body).

    Returns:
        A cleaned, readable Markdown string.
    """
    if not html or not html.strip():
        return ""

    try:
        # Use markdownify for rich conversion if available
        import markdownify  # noqa: PLC0415

        md = markdownify.markdownify(html, heading_style="ATX", strip=["img"])
        return _clean_whitespace(md)
    except ImportError:
        pass

    # Fallback: pure BeautifulSoup text extraction
    soup = BeautifulSoup(html, "lxml")

    # Remove non-content tags
    for tag in soup(["script", "style", "head", "meta", "link"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    return _clean_whitespace(text)


def _clean_whitespace(text: str) -> str:
    """Collapse excessive blank lines and strip trailing spaces."""
    # Replace 3+ consecutive newlines with 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing whitespace on each line
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def extract_plain_text(html: str) -> str:
    """
    Extract plain text from HTML, discarding all formatting.
    Useful for short previews/snippets.
    """
    soup = BeautifulSoup(html, "lxml")
    return _clean_whitespace(soup.get_text(separator=" "))
