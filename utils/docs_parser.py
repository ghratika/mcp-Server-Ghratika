"""
utils/docs_parser.py
────────────────────────────────────────────────────────────────
Converts the Google Docs API JSON response into clean Markdown.

The Google Docs API returns documents as a structured JSON object
with a `body.content` array of `StructuralElement` objects.  This
module walks that tree and reconstructs the document as Markdown.

Supported elements:
  • Paragraphs (with HEADING_1–6, TITLE, SUBTITLE, NORMAL_TEXT)
  • Inline text runs (bold, italic, underline, strikethrough, link)
  • Ordered and unordered lists
  • Horizontal rules
  • Tables (rendered as GitHub-flavored Markdown tables)
  • Inline images (noted as [Image] placeholder)
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Docs API paragraph style → Markdown heading prefix
_HEADING_MAP: dict[str, str] = {
    "TITLE": "# ",
    "SUBTITLE": "## ",
    "HEADING_1": "# ",
    "HEADING_2": "## ",
    "HEADING_3": "### ",
    "HEADING_4": "#### ",
    "HEADING_5": "##### ",
    "HEADING_6": "###### ",
    "NORMAL_TEXT": "",
}


def doc_to_markdown(doc: dict[str, Any]) -> str:
    """
    Convert a full Google Docs API document object to Markdown.

    Args:
        doc: The dict returned by ``docs.documents().get(documentId=…).execute()``.

    Returns:
        A Markdown string representing the document content.
    """
    body = doc.get("body", {})
    content = body.get("content", [])
    lists_info = doc.get("lists", {})

    lines: list[str] = []
    _walk_content(content, lists_info, lines)

    return "\n".join(lines).strip()


# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _walk_content(
    content: list[dict],
    lists_info: dict,
    out: list[str],
) -> None:
    for element in content:
        if "paragraph" in element:
            _handle_paragraph(element["paragraph"], lists_info, out)
        elif "table" in element:
            _handle_table(element["table"], lists_info, out)
        elif "sectionBreak" in element:
            out.append("\n---\n")


def _handle_paragraph(
    para: dict[str, Any],
    lists_info: dict,
    out: list[str],
) -> None:
    style_name = (
        para.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
    )
    prefix = _HEADING_MAP.get(style_name, "")

    # Check if this paragraph is part of a list
    list_props = para.get("bullet")
    if list_props:
        prefix = _get_list_prefix(list_props, lists_info)

    # Build inline text
    text = _render_inline_elements(para.get("elements", []))

    if not text.strip():
        out.append("")
        return

    out.append(prefix + text)


def _render_inline_elements(elements: list[dict]) -> str:
    parts: list[str] = []
    for el in elements:
        if "textRun" in el:
            parts.append(_render_text_run(el["textRun"]))
        elif "inlineObjectElement" in el:
            parts.append("[Image]")
        elif "horizontalRule" in el:
            parts.append("\n---\n")
    return "".join(parts)


def _render_text_run(run: dict[str, Any]) -> str:
    content = run.get("content", "")
    # Strip the trailing newline that Docs API adds to every paragraph
    content = content.rstrip("\n")
    if not content:
        return ""

    style = run.get("textStyle", {})
    bold = style.get("bold", False)
    italic = style.get("italic", False)
    strikethrough = style.get("strikethrough", False)
    underline = style.get("underline", False)
    link = style.get("link", {}).get("url", "")

    # Apply formatting (order matters for correct nesting)
    if strikethrough:
        content = f"~~{content}~~"
    if bold and italic:
        content = f"***{content}***"
    elif bold:
        content = f"**{content}**"
    elif italic:
        content = f"*{content}*"
    if link:
        content = f"[{content}]({link})"

    return content


def _get_list_prefix(bullet: dict, lists_info: dict) -> str:
    list_id = bullet.get("listId", "")
    nesting = bullet.get("nestingLevel", 0)
    indent = "  " * nesting

    list_info = lists_info.get(list_id, {})
    props = list_info.get("listProperties", {})
    levels = props.get("nestingLevels", [])

    if nesting < len(levels):
        glyph_type = levels[nesting].get("glyphType", "BULLET")
        if glyph_type in ("DECIMAL", "ALPHA", "ROMAN"):
            return f"{indent}1. "

    return f"{indent}- "


def _handle_table(table: dict, lists_info: dict, out: list[str]) -> None:
    rows = table.get("tableRows", [])
    if not rows:
        return

    md_rows: list[list[str]] = []
    for row in rows:
        cells = row.get("tableCells", [])
        row_texts: list[str] = []
        for cell in cells:
            cell_content = cell.get("content", [])
            cell_lines: list[str] = []
            _walk_content(cell_content, lists_info, cell_lines)
            cell_text = " ".join(l.strip() for l in cell_lines if l.strip())
            row_texts.append(cell_text)
        md_rows.append(row_texts)

    if not md_rows:
        return

    # Determine column count
    col_count = max(len(r) for r in md_rows)

    # Header row
    header = md_rows[0]
    header += [""] * (col_count - len(header))
    out.append("| " + " | ".join(header) + " |")
    out.append("| " + " | ".join(["---"] * col_count) + " |")

    # Data rows
    for row in md_rows[1:]:
        row += [""] * (col_count - len(row))
        out.append("| " + " | ".join(row) + " |")

    out.append("")
