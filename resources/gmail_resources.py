"""
resources/gmail_resources.py
────────────────────────────────────────────────────────────────
MCP Resources for Gmail — these expose readable data endpoints
that MCP hosts can attach to context without calling a tool.

Resources:
  gmail://inbox              – Latest 20 inbox emails (structured JSON)
  gmail://message/{id}       – Single email by ID (full body as Markdown)
  gmail://thread/{id}        – Full email thread (all messages in order)
  gmail://labels             – All Gmail labels with unread counts
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from auth.google_auth import get_gmail_service
from utils.html_to_text import html_to_markdown

logger = logging.getLogger(__name__)


def register_gmail_resources(mcp: FastMCP) -> None:
    """Register all Gmail resources on the given FastMCP instance."""

    # ─────────────────────────────────────────────────────────
    # gmail://inbox
    # ─────────────────────────────────────────────────────────
    @mcp.resource("gmail://inbox")
    def gmail_inbox() -> str:
        """
        Latest 20 inbox emails.

        Returns a JSON array of email summaries:
          [{id, thread_id, subject, from, date, snippet, label_ids}]
        """
        service = get_gmail_service()
        result = service.users().messages().list(
            userId="me", labelIds=["INBOX"], maxResults=20
        ).execute()
        messages = result.get("messages", [])

        emails = []
        for msg in messages:
            meta = (
                service.users()
                .messages()
                .get(userId="me", id=msg["id"], format="metadata",
                     metadataHeaders=["Subject", "From", "Date"])
                .execute()
            )
            headers = {
                h["name"]: h["value"]
                for h in meta.get("payload", {}).get("headers", [])
            }
            emails.append({
                "id": meta["id"],
                "thread_id": meta["threadId"],
                "subject": headers.get("Subject", "(No Subject)"),
                "from": headers.get("From", ""),
                "date": headers.get("Date", ""),
                "snippet": meta.get("snippet", ""),
                "label_ids": meta.get("labelIds", []),
            })

        return json.dumps(emails, indent=2, ensure_ascii=False)

    # ─────────────────────────────────────────────────────────
    # gmail://message/{id}
    # ─────────────────────────────────────────────────────────
    @mcp.resource("gmail://message/{message_id}")
    def gmail_message(message_id: str) -> str:
        """
        Full content of a single Gmail message, as Markdown.

        Returns a JSON object:
          {id, thread_id, subject, from, to, date, body_markdown, attachments}
        """
        service = get_gmail_service()
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        payload = msg.get("payload", {})
        headers = {
            h["name"]: h["value"]
            for h in payload.get("headers", [])
        }

        body_md, attachments = _extract_body(payload)

        data = {
            "id": msg["id"],
            "thread_id": msg["threadId"],
            "subject": headers.get("Subject", "(No Subject)"),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "cc": headers.get("Cc", ""),
            "date": headers.get("Date", ""),
            "body_markdown": body_md,
            "attachments": attachments,
            "label_ids": msg.get("labelIds", []),
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    # ─────────────────────────────────────────────────────────
    # gmail://thread/{id}
    # ─────────────────────────────────────────────────────────
    @mcp.resource("gmail://thread/{thread_id}")
    def gmail_thread(thread_id: str) -> str:
        """
        All messages in a Gmail thread, ordered chronologically.

        Returns a JSON object:
          {thread_id, subject, message_count, messages: [...]}
        Each message has: id, from, date, body_markdown.
        """
        service = get_gmail_service()
        thread = (
            service.users()
            .threads()
            .get(userId="me", id=thread_id, format="full")
            .execute()
        )
        messages = thread.get("messages", [])

        thread_subject = ""
        parsed_messages = []

        for msg in messages:
            payload = msg.get("payload", {})
            headers = {
                h["name"]: h["value"]
                for h in payload.get("headers", [])
            }
            if not thread_subject:
                thread_subject = headers.get("Subject", "(No Subject)")

            body_md, _ = _extract_body(payload)
            parsed_messages.append({
                "id": msg["id"],
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "date": headers.get("Date", ""),
                "body_markdown": body_md,
                "label_ids": msg.get("labelIds", []),
            })

        return json.dumps({
            "thread_id": thread_id,
            "subject": thread_subject,
            "message_count": len(parsed_messages),
            "messages": parsed_messages,
        }, indent=2, ensure_ascii=False)

    # ─────────────────────────────────────────────────────────
    # gmail://labels
    # ─────────────────────────────────────────────────────────
    @mcp.resource("gmail://labels")
    def gmail_labels() -> str:
        """
        All Gmail labels with message and unread counts.

        Returns a JSON array of label objects.
        """
        service = get_gmail_service()
        result = service.users().labels().list(userId="me").execute()
        labels = []
        for lbl in result.get("labels", []):
            detail = (
                service.users()
                .labels()
                .get(userId="me", id=lbl["id"])
                .execute()
            )
            labels.append({
                "id": detail["id"],
                "name": detail["name"],
                "type": detail.get("type", "user"),
                "messages_total": detail.get("messagesTotal", 0),
                "messages_unread": detail.get("messagesUnread", 0),
                "threads_total": detail.get("threadsTotal", 0),
                "threads_unread": detail.get("threadsUnread", 0),
            })
        return json.dumps(labels, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────

def _extract_body(payload: dict[str, Any]) -> tuple[str, list[dict]]:
    """Extract body markdown and attachment list from a Gmail payload."""
    html_body = ""
    plain_body = ""
    attachments: list[dict] = []

    def _walk(part: dict) -> None:
        nonlocal html_body, plain_body
        mime = part.get("mimeType", "")
        body_data = part.get("body", {})
        filename = part.get("filename", "")

        if mime == "text/html" and not html_body:
            data = body_data.get("data", "")
            if data:
                html_body = base64.urlsafe_b64decode(data).decode(
                    "utf-8", errors="replace"
                )
        elif mime == "text/plain" and not plain_body:
            data = body_data.get("data", "")
            if data:
                plain_body = base64.urlsafe_b64decode(data).decode(
                    "utf-8", errors="replace"
                )
        elif filename and body_data.get("attachmentId"):
            attachments.append({
                "filename": filename,
                "mime_type": mime,
                "attachment_id": body_data["attachmentId"],
            })

        for subpart in part.get("parts", []):
            _walk(subpart)

    _walk(payload)

    if html_body:
        return html_to_markdown(html_body), attachments
    return plain_body, attachments
