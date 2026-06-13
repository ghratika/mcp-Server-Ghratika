"""
tools/gmail_tools.py
────────────────────────────────────────────────────────────────
All Gmail MCP tools registered on the FastMCP server.

Tools exposed:
  • list_emails        – List emails from a mailbox label
  • get_email          – Fetch a single email (full body as Markdown)
  • search_emails      – Search emails with Gmail query syntax
  • send_email         – Compose and send a new email
  • reply_to_email     – Thread-aware reply to an existing email
  • create_draft       – Save a draft without sending
  • trash_email        – Move an email to trash
  • list_labels        – List all Gmail labels
  • add_label          – Apply a label to a message
  • remove_label       – Remove a label from a message
"""

from __future__ import annotations

import base64
import email as email_lib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

from auth.google_auth import get_gmail_service
from utils.html_to_text import html_to_markdown

logger = logging.getLogger(__name__)


def register_gmail_tools(mcp: FastMCP) -> None:
    """Register all Gmail tools on the given FastMCP instance."""

    # ─────────────────────────────────────────────────────────
    # list_emails
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def list_emails(
        label: str = "INBOX",
        max_results: int = 20,
        page_token: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        List emails from a Gmail mailbox label.

        Args:
            label:       Gmail label ID or name (e.g. "INBOX", "SENT", "STARRED",
                         or a custom label name). Default: "INBOX".
            max_results: Maximum number of emails to return (1–100). Default: 20.
            page_token:  Token for paginating through results.

        Returns:
            A dict with:
              - emails: list of {id, thread_id, subject, from, date, snippet}
              - next_page_token: pass this back to get the next page (may be null)
              - result_size_estimate: approximate total number of matching emails
        """
        service = get_gmail_service()
        max_results = max(1, min(100, max_results))

        kwargs: dict[str, Any] = {
            "userId": "me",
            "labelIds": [label],
            "maxResults": max_results,
        }
        if page_token:
            kwargs["pageToken"] = page_token

        result = service.users().messages().list(**kwargs).execute()
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

        return {
            "emails": emails,
            "next_page_token": result.get("nextPageToken"),
            "result_size_estimate": result.get("resultSizeEstimate", 0),
        }

    # ─────────────────────────────────────────────────────────
    # get_email
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def get_email(message_id: str) -> dict[str, Any]:
        """
        Fetch the full content of a single Gmail message.

        Args:
            message_id: The Gmail message ID (from list_emails or search_emails).

        Returns:
            A dict with:
              - id, thread_id
              - subject, from, to, cc, bcc, date
              - body_markdown: full email body converted to Markdown
              - attachments: list of {filename, mime_type, attachment_id}
              - label_ids
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

        body_markdown, attachments = _extract_body_and_attachments(payload)

        return {
            "id": msg["id"],
            "thread_id": msg["threadId"],
            "subject": headers.get("Subject", "(No Subject)"),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "cc": headers.get("Cc", ""),
            "bcc": headers.get("Bcc", ""),
            "date": headers.get("Date", ""),
            "body_markdown": body_markdown,
            "attachments": attachments,
            "label_ids": msg.get("labelIds", []),
        }

    # ─────────────────────────────────────────────────────────
    # search_emails
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def search_emails(
        query: str,
        max_results: int = 20,
        page_token: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Search Gmail using the full Gmail query syntax.

        Supports operators like:
          from:someone@example.com
          to:me
          subject:"meeting notes"
          has:attachment
          after:2024/01/01
          before:2024/12/31
          is:unread
          label:important
          in:inbox OR in:sent
          newer_than:7d

        Args:
            query:       Gmail search query string.
            max_results: Maximum results to return (1–100). Default: 20.
            page_token:  Pagination token for the next page.

        Returns:
            Same structure as list_emails.
        """
        service = get_gmail_service()
        max_results = max(1, min(100, max_results))

        kwargs: dict[str, Any] = {
            "userId": "me",
            "q": query,
            "maxResults": max_results,
        }
        if page_token:
            kwargs["pageToken"] = page_token

        result = service.users().messages().list(**kwargs).execute()
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

        return {
            "emails": emails,
            "query": query,
            "next_page_token": result.get("nextPageToken"),
            "result_size_estimate": result.get("resultSizeEstimate", 0),
        }

    # ─────────────────────────────────────────────────────────
    # send_email
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def send_email(
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        body_is_html: bool = False,
    ) -> dict[str, Any]:
        """
        Compose and immediately send a new email.

        Args:
            to:           Recipient email address(es), comma-separated.
            subject:      Email subject line.
            body:         Email body content (plain text or HTML).
            cc:           CC recipient(s), comma-separated (optional).
            bcc:          BCC recipient(s), comma-separated (optional).
            body_is_html: Set True if body is HTML; otherwise treated as plain text.

        Returns:
            A dict with: id, thread_id, label_ids of the sent message.
        """
        service = get_gmail_service()
        msg = _build_mime_message(
            to=to, subject=subject, body=body,
            cc=cc, bcc=bcc, body_is_html=body_is_html,
        )
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
        return {
            "id": sent["id"],
            "thread_id": sent.get("threadId", ""),
            "label_ids": sent.get("labelIds", []),
            "status": "sent",
        }

    # ─────────────────────────────────────────────────────────
    # reply_to_email
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def reply_to_email(
        message_id: str,
        body: str,
        body_is_html: bool = False,
        reply_all: bool = False,
    ) -> dict[str, Any]:
        """
        Send a thread-aware reply to an existing email.

        Args:
            message_id:  The ID of the message to reply to.
            body:        Reply body (plain text or HTML).
            body_is_html: Set True if body is HTML.
            reply_all:   If True, CC all original recipients.

        Returns:
            A dict with the sent reply's id, thread_id, and label_ids.
        """
        service = get_gmail_service()

        # Fetch original message headers
        original = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="metadata",
                 metadataHeaders=["Subject", "From", "To", "Cc",
                                  "Message-ID", "References"])
            .execute()
        )
        headers = {
            h["name"]: h["value"]
            for h in original.get("payload", {}).get("headers", [])
        }
        thread_id = original["threadId"]

        to = headers.get("From", "")
        subject = headers.get("Subject", "")
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        cc = None
        if reply_all:
            original_to = headers.get("To", "")
            original_cc = headers.get("Cc", "")
            cc_parts = [p for p in [original_to, original_cc] if p]
            cc = ", ".join(cc_parts) if cc_parts else None

        msg = _build_mime_message(
            to=to, subject=subject, body=body, cc=cc,
            body_is_html=body_is_html,
        )
        # Set threading headers
        msg_id = headers.get("Message-ID", "")
        references = headers.get("References", "")
        if msg_id:
            msg["In-Reply-To"] = msg_id
            msg["References"] = f"{references} {msg_id}".strip()

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw, "threadId": thread_id})
            .execute()
        )
        return {
            "id": sent["id"],
            "thread_id": sent.get("threadId", ""),
            "label_ids": sent.get("labelIds", []),
            "status": "sent",
        }

    # ─────────────────────────────────────────────────────────
    # create_draft
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def create_draft(
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        body_is_html: bool = False,
    ) -> dict[str, Any]:
        """
        Save a new draft email without sending it.

        Args:
            to:           Recipient email address(es), comma-separated.
            subject:      Email subject line.
            body:         Email body (plain text or HTML).
            cc:           CC recipients (optional).
            bcc:          BCC recipients (optional).
            body_is_html: True if body is HTML.

        Returns:
            A dict with the draft's id and the underlying message id.
        """
        service = get_gmail_service()
        msg = _build_mime_message(
            to=to, subject=subject, body=body,
            cc=cc, bcc=bcc, body_is_html=body_is_html,
        )
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        draft = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        return {
            "draft_id": draft["id"],
            "message_id": draft.get("message", {}).get("id", ""),
            "status": "draft_saved",
        }

    # ─────────────────────────────────────────────────────────
    # trash_email
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def trash_email(message_id: str) -> dict[str, Any]:
        """
        Move an email to the Trash.

        Args:
            message_id: The Gmail message ID to trash.

        Returns:
            Confirmation dict with id and status.
        """
        service = get_gmail_service()
        result = (
            service.users()
            .messages()
            .trash(userId="me", id=message_id)
            .execute()
        )
        return {
            "id": result["id"],
            "status": "trashed",
            "label_ids": result.get("labelIds", []),
        }

    # ─────────────────────────────────────────────────────────
    # list_labels
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def list_labels() -> dict[str, Any]:
        """
        List all Gmail labels (system and user-created).

        Returns:
            A dict with a 'labels' list, each item containing:
              id, name, type (system/user), messages_total,
              messages_unread, threads_total, threads_unread.
        """
        service = get_gmail_service()
        result = service.users().labels().list(userId="me").execute()
        labels = []
        for lbl in result.get("labels", []):
            # Fetch detailed counts for each label
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
        return {"labels": labels, "count": len(labels)}

    # ─────────────────────────────────────────────────────────
    # add_label
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def add_label(message_id: str, label_id: str) -> dict[str, Any]:
        """
        Apply a Gmail label to a message.

        Args:
            message_id: The Gmail message ID.
            label_id:   The label ID to apply (get IDs from list_labels).

        Returns:
            Updated label_ids for the message.
        """
        service = get_gmail_service()
        result = (
            service.users()
            .messages()
            .modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": [label_id]},
            )
            .execute()
        )
        return {
            "id": result["id"],
            "label_ids": result.get("labelIds", []),
            "status": "label_added",
        }

    # ─────────────────────────────────────────────────────────
    # remove_label
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def remove_label(message_id: str, label_id: str) -> dict[str, Any]:
        """
        Remove a Gmail label from a message.

        Args:
            message_id: The Gmail message ID.
            label_id:   The label ID to remove (get IDs from list_labels).

        Returns:
            Updated label_ids for the message.
        """
        service = get_gmail_service()
        result = (
            service.users()
            .messages()
            .modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": [label_id]},
            )
            .execute()
        )
        return {
            "id": result["id"],
            "label_ids": result.get("labelIds", []),
            "status": "label_removed",
        }


# ─────────────────────────────────────────────────────────────
# Private helpers (not MCP tools)
# ─────────────────────────────────────────────────────────────

def _build_mime_message(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    body_is_html: bool = False,
) -> MIMEMultipart:
    """Build a MIME email message object."""
    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc

    if body_is_html:
        msg.attach(MIMEText(body, "html"))
    else:
        msg.attach(MIMEText(body, "plain"))

    return msg


def _extract_body_and_attachments(
    payload: dict[str, Any],
) -> tuple[str, list[dict]]:
    """
    Recursively walk a Gmail message payload to extract the body and
    list attachment metadata.

    Returns:
        (body_markdown: str, attachments: list[dict])
    """
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
                "size_bytes": body_data.get("size", 0),
            })

        for subpart in part.get("parts", []):
            _walk(subpart)

    _walk(payload)

    if html_body:
        return html_to_markdown(html_body), attachments
    return plain_body, attachments
