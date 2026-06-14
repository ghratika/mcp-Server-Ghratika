"""
server.py
────────────────────────────────────────────────────────────────
Google Workspace MCP Server

An MCP (Model Context Protocol) server that exposes Gmail and
Google Docs capabilities as tools, resources, and prompts.

Compatible with any MCP host:
  • Claude Desktop
  • Cursor
  • Any client implementing the MCP protocol

Transport modes:
  stdio (default) – for local process use with Claude Desktop / Cursor
  SSE             – run with --sse flag for HTTP-based remote access

Usage:
  # Run with stdio (default — for Claude Desktop)
  python server.py

  # Run with SSE transport on port 8000
  python server.py --sse

  # Run on a custom port
  python server.py --sse --port 9000

  # Test interactively with MCP Inspector
  mcp dev server.py
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

# ── Load environment variables ────────────────────────────────
load_dotenv()

# ── Reconstruct base64 credentials if running in Railway ────────
from auth.startup import reconstruct_credentials
reconstruct_credentials()

IS_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") is not None

# ── Configure logging (MUST use stderr for stdio transport) ───
log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logging.basicConfig(
    stream=sys.stderr,
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Create FastMCP server ─────────────────────────────────────
mcp = FastMCP(
    name="Google Workspace MCP Server",
    instructions=(
        "This server provides tools and resources for interacting with Gmail "
        "and Google Docs. You can read, search, send, and organise emails, "
        "as well as create, read, edit, share, and export Google Docs. "
        "Use the prompts for common workflows like daily email digests, "
        "document reviews, and reply drafting."
    ),
)

# ── Register all tools ────────────────────────────────────────
logger.info("Registering Gmail tools…")
from tools.gmail_tools import register_gmail_tools  # noqa: E402
register_gmail_tools(mcp)

logger.info("Registering Google Docs tools…")
from tools.docs_tools import register_docs_tools  # noqa: E402
register_docs_tools(mcp)

# ── Register all resources ────────────────────────────────────
logger.info("Registering Gmail resources…")
from resources.gmail_resources import register_gmail_resources  # noqa: E402
register_gmail_resources(mcp)

logger.info("Registering Google Docs resources…")
from resources.docs_resources import register_docs_resources  # noqa: E402
register_docs_resources(mcp)

# ── Register all prompts ──────────────────────────────────────
logger.info("Registering Google Workspace prompts…")
from prompts.google_prompts import register_google_prompts  # noqa: E402
register_google_prompts(mcp)

# ── Health check endpoint (required by Railway) ───────────────
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Railway healthcheck endpoint — returns 200 OK when server is running."""
    return JSONResponse({"status": "ok", "server": "Google Workspace MCP Server"})


# ═════════════════════════════════════════════════════════════════
# REST API routes — plain HTTP JSON endpoints (no MCP client needed)
#
# Base URL:  https://mcp-server-ghratika-production.up.railway.app
#
# ── Gmail ──────────────────────────────────────────────────────
#   GET  /api/gmail/emails              list inbox emails
#   GET  /api/gmail/email/{id}          fetch one email
#   POST /api/gmail/search              search emails
#   POST /api/gmail/send                send an email
#   POST /api/gmail/reply               reply to an email
#   POST /api/gmail/draft               save a draft
#   POST /api/gmail/trash               trash an email
#   GET  /api/gmail/labels              list labels
#   POST /api/gmail/label/add           add label to message
#   POST /api/gmail/label/remove        remove label from message
#
# ── Google Docs ────────────────────────────────────────────────
#   GET  /api/docs/list                 list documents
#   GET  /api/docs/{id}                 get document content
#   POST /api/docs/search               search documents
#   POST /api/docs/create               create a document
#   POST /api/docs/update               append/prepend/replace content
#   POST /api/docs/share                share a document
#   POST /api/docs/export               export as PDF/DOCX/etc
#   POST /api/docs/delete               trash a document
# ═════════════════════════════════════════════════════════════════

import json as _json  # noqa: E402  (stdlib, always available)
from auth.google_auth import (  # noqa: E402
    get_gmail_service, get_docs_service, get_drive_service
)

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

async def _body(request: Request) -> dict:
    """Parse JSON body; return empty dict on failure."""
    try:
        return await request.json()
    except Exception:
        return {}

def _err(msg: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status)


# ─────────────────────────────────────────────────────────────
# Gmail REST routes
# ─────────────────────────────────────────────────────────────

@mcp.custom_route("/api/gmail/emails", methods=["GET"])
async def rest_list_emails(request: Request) -> JSONResponse:
    """
    List inbox emails.
    Query params:
      label        (default: INBOX)
      max_results  (default: 20, max: 100)
      page_token
    """
    from tools.gmail_tools import _extract_body_and_attachments  # noqa: PLC0415
    params = dict(request.query_params)
    label = params.get("label", "INBOX")
    max_results = min(int(params.get("max_results", 20)), 100)
    page_token = params.get("page_token")

    service = get_gmail_service()
    kwargs: dict = {"userId": "me", "labelIds": [label], "maxResults": max_results}
    if page_token:
        kwargs["pageToken"] = page_token
    result = service.users().messages().list(**kwargs).execute()
    messages = result.get("messages", [])
    emails = []
    for msg in messages:
        meta = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["Subject", "From", "Date"]
        ).execute()
        headers = {h["name"]: h["value"] for h in meta.get("payload", {}).get("headers", [])}
        emails.append({
            "id": meta["id"], "thread_id": meta["threadId"],
            "subject": headers.get("Subject", "(No Subject)"),
            "from": headers.get("From", ""), "date": headers.get("Date", ""),
            "snippet": meta.get("snippet", ""), "label_ids": meta.get("labelIds", []),
        })
    return JSONResponse({"emails": emails, "next_page_token": result.get("nextPageToken"),
                         "result_size_estimate": result.get("resultSizeEstimate", 0)})


@mcp.custom_route("/api/gmail/email/{message_id}", methods=["GET"])
async def rest_get_email(request: Request) -> JSONResponse:
    """
    Get a single email by ID.
    Path param: message_id
    """
    import base64 as _b64  # noqa: PLC0415
    from utils.html_to_text import html_to_markdown  # noqa: PLC0415
    message_id = request.path_params["message_id"]
    service = get_gmail_service()
    msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    payload = msg.get("payload", {})
    headers = {h["name"]: h["value"] for h in payload.get("headers", [])}

    html_body = plain_body = ""
    attachments = []

    def _walk(part: dict) -> None:
        nonlocal html_body, plain_body
        mime = part.get("mimeType", "")
        body_data = part.get("body", {})
        fname = part.get("filename", "")
        if mime == "text/html" and not html_body:
            data = body_data.get("data", "")
            if data:
                html_body = _b64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif mime == "text/plain" and not plain_body:
            data = body_data.get("data", "")
            if data:
                plain_body = _b64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif fname and body_data.get("attachmentId"):
            attachments.append({"filename": fname, "mime_type": mime,
                                 "attachment_id": body_data["attachmentId"]})
        for sp in part.get("parts", []):
            _walk(sp)

    _walk(payload)
    body_md = html_to_markdown(html_body) if html_body else plain_body

    return JSONResponse({
        "id": msg["id"], "thread_id": msg["threadId"],
        "subject": headers.get("Subject", "(No Subject)"),
        "from": headers.get("From", ""), "to": headers.get("To", ""),
        "cc": headers.get("Cc", ""), "date": headers.get("Date", ""),
        "body_markdown": body_md, "attachments": attachments,
        "label_ids": msg.get("labelIds", []),
    })


@mcp.custom_route("/api/gmail/search", methods=["POST"])
async def rest_search_emails(request: Request) -> JSONResponse:
    """
    Search emails.
    Body: { "query": "from:someone@example.com", "max_results": 20, "page_token": null }
    """
    body = await _body(request)
    query = body.get("query")
    if not query:
        return _err("'query' is required")
    max_results = min(int(body.get("max_results", 20)), 100)
    page_token = body.get("page_token")
    service = get_gmail_service()
    kwargs: dict = {"userId": "me", "q": query, "maxResults": max_results}
    if page_token:
        kwargs["pageToken"] = page_token
    result = service.users().messages().list(**kwargs).execute()
    messages = result.get("messages", [])
    emails = []
    for msg in messages:
        meta = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["Subject", "From", "Date"]
        ).execute()
        headers = {h["name"]: h["value"] for h in meta.get("payload", {}).get("headers", [])}
        emails.append({
            "id": meta["id"], "thread_id": meta["threadId"],
            "subject": headers.get("Subject", "(No Subject)"),
            "from": headers.get("From", ""), "date": headers.get("Date", ""),
            "snippet": meta.get("snippet", ""), "label_ids": meta.get("labelIds", []),
        })
    return JSONResponse({"emails": emails, "query": query,
                         "next_page_token": result.get("nextPageToken"),
                         "result_size_estimate": result.get("resultSizeEstimate", 0)})


@mcp.custom_route("/api/gmail/send", methods=["POST"])
async def rest_send_email(request: Request) -> JSONResponse:
    """
    Send an email.
    Body: { "to": "...", "subject": "...", "body": "...", "cc": null, "bcc": null, "body_is_html": false }
    """
    import base64 as _b64  # noqa: PLC0415
    from email.mime.multipart import MIMEMultipart  # noqa: PLC0415
    from email.mime.text import MIMEText  # noqa: PLC0415
    body = await _body(request)
    to = body.get("to")
    subject = body.get("subject")
    text = body.get("body", "")
    if not to or not subject:
        return _err("'to' and 'subject' are required")
    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["Subject"] = subject
    if body.get("cc"):
        msg["Cc"] = body["cc"]
    if body.get("bcc"):
        msg["Bcc"] = body["bcc"]
    mime_type = "html" if body.get("body_is_html") else "plain"
    msg.attach(MIMEText(text, mime_type))
    raw = _b64.urlsafe_b64encode(msg.as_bytes()).decode()
    service = get_gmail_service()
    sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return JSONResponse({"id": sent["id"], "thread_id": sent.get("threadId", ""),
                         "label_ids": sent.get("labelIds", []), "status": "sent"})


@mcp.custom_route("/api/gmail/reply", methods=["POST"])
async def rest_reply_email(request: Request) -> JSONResponse:
    """
    Reply to an email thread.
    Body: { "message_id": "...", "body": "...", "body_is_html": false, "reply_all": false }
    """
    import base64 as _b64  # noqa: PLC0415
    from email.mime.multipart import MIMEMultipart  # noqa: PLC0415
    from email.mime.text import MIMEText  # noqa: PLC0415
    body = await _body(request)
    message_id = body.get("message_id")
    text = body.get("body", "")
    if not message_id:
        return _err("'message_id' is required")
    service = get_gmail_service()
    original = service.users().messages().get(
        userId="me", id=message_id, format="metadata",
        metadataHeaders=["Subject", "From", "To", "Cc", "Message-ID", "References"]
    ).execute()
    headers = {h["name"]: h["value"] for h in original.get("payload", {}).get("headers", [])}
    thread_id = original["threadId"]
    to = headers.get("From", "")
    subject = headers.get("Subject", "")
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["Subject"] = subject
    if body.get("reply_all"):
        cc_parts = [p for p in [headers.get("To", ""), headers.get("Cc", "")] if p]
        if cc_parts:
            msg["Cc"] = ", ".join(cc_parts)
    mime_type = "html" if body.get("body_is_html") else "plain"
    msg.attach(MIMEText(text, mime_type))
    msg_id = headers.get("Message-ID", "")
    references = headers.get("References", "")
    if msg_id:
        msg["In-Reply-To"] = msg_id
        msg["References"] = f"{references} {msg_id}".strip()
    raw = _b64.urlsafe_b64encode(msg.as_bytes()).decode()
    sent = service.users().messages().send(
        userId="me", body={"raw": raw, "threadId": thread_id}
    ).execute()
    return JSONResponse({"id": sent["id"], "thread_id": sent.get("threadId", ""),
                         "label_ids": sent.get("labelIds", []), "status": "sent"})


@mcp.custom_route("/api/gmail/draft", methods=["POST"])
async def rest_create_draft(request: Request) -> JSONResponse:
    """
    Save a Gmail draft without sending.
    Body: { "to": "...", "subject": "...", "body": "...", "cc": null, "bcc": null, "body_is_html": false }
    """
    import base64 as _b64  # noqa: PLC0415
    from email.mime.multipart import MIMEMultipart  # noqa: PLC0415
    from email.mime.text import MIMEText  # noqa: PLC0415
    body = await _body(request)
    to = body.get("to")
    subject = body.get("subject")
    text = body.get("body", "")
    if not to or not subject:
        return _err("'to' and 'subject' are required")
    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["Subject"] = subject
    if body.get("cc"):
        msg["Cc"] = body["cc"]
    if body.get("bcc"):
        msg["Bcc"] = body["bcc"]
    mime_type = "html" if body.get("body_is_html") else "plain"
    msg.attach(MIMEText(text, mime_type))
    raw = _b64.urlsafe_b64encode(msg.as_bytes()).decode()
    service = get_gmail_service()
    draft = service.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()
    return JSONResponse({"draft_id": draft["id"],
                         "message_id": draft.get("message", {}).get("id", ""),
                         "status": "draft_saved"})


@mcp.custom_route("/api/gmail/trash", methods=["POST"])
async def rest_trash_email(request: Request) -> JSONResponse:
    """
    Trash an email.
    Body: { "message_id": "..." }
    """
    body = await _body(request)
    message_id = body.get("message_id")
    if not message_id:
        return _err("'message_id' is required")
    service = get_gmail_service()
    result = service.users().messages().trash(userId="me", id=message_id).execute()
    return JSONResponse({"id": result["id"], "status": "trashed",
                         "label_ids": result.get("labelIds", [])})


@mcp.custom_route("/api/gmail/labels", methods=["GET"])
async def rest_list_labels(request: Request) -> JSONResponse:
    """List all Gmail labels."""
    service = get_gmail_service()
    result = service.users().labels().list(userId="me").execute()
    labels = []
    for lbl in result.get("labels", []):
        detail = service.users().labels().get(userId="me", id=lbl["id"]).execute()
        labels.append({
            "id": detail["id"], "name": detail["name"], "type": detail.get("type", "user"),
            "messages_total": detail.get("messagesTotal", 0),
            "messages_unread": detail.get("messagesUnread", 0),
        })
    return JSONResponse({"labels": labels, "count": len(labels)})


@mcp.custom_route("/api/gmail/label/add", methods=["POST"])
async def rest_add_label(request: Request) -> JSONResponse:
    """
    Add a label to a message.
    Body: { "message_id": "...", "label_id": "..." }
    """
    body = await _body(request)
    message_id = body.get("message_id")
    label_id = body.get("label_id")
    if not message_id or not label_id:
        return _err("'message_id' and 'label_id' are required")
    service = get_gmail_service()
    result = service.users().messages().modify(
        userId="me", id=message_id, body={"addLabelIds": [label_id]}
    ).execute()
    return JSONResponse({"id": result["id"], "label_ids": result.get("labelIds", []),
                         "status": "label_added"})


@mcp.custom_route("/api/gmail/label/remove", methods=["POST"])
async def rest_remove_label(request: Request) -> JSONResponse:
    """
    Remove a label from a message.
    Body: { "message_id": "...", "label_id": "..." }
    """
    body = await _body(request)
    message_id = body.get("message_id")
    label_id = body.get("label_id")
    if not message_id or not label_id:
        return _err("'message_id' and 'label_id' are required")
    service = get_gmail_service()
    result = service.users().messages().modify(
        userId="me", id=message_id, body={"removeLabelIds": [label_id]}
    ).execute()
    return JSONResponse({"id": result["id"], "label_ids": result.get("labelIds", []),
                         "status": "label_removed"})


# ─────────────────────────────────────────────────────────────
# Google Docs REST routes
# ─────────────────────────────────────────────────────────────

@mcp.custom_route("/api/docs/list", methods=["GET"])
async def rest_list_docs(request: Request) -> JSONResponse:
    """
    List Google Docs.
    Query params: max_results (default 20), order_by, page_token
    """
    params = dict(request.query_params)
    max_results = min(int(params.get("max_results", 20)), 100)
    order_by = params.get("order_by", "modifiedTime desc")
    page_token = params.get("page_token")
    drive = get_drive_service()
    kwargs: dict = {
        "q": "mimeType='application/vnd.google-apps.document' and trashed=false",
        "pageSize": max_results, "orderBy": order_by,
        "fields": "nextPageToken, files(id, name, createdTime, modifiedTime, owners, webViewLink, shared)",
    }
    if page_token:
        kwargs["pageToken"] = page_token
    result = drive.files().list(**kwargs).execute()
    files = result.get("files", [])
    documents = [{"id": f["id"], "name": f["name"],
                  "created_time": f.get("createdTime", ""),
                  "modified_time": f.get("modifiedTime", ""),
                  "owners": [o.get("emailAddress", "") for o in f.get("owners", [])],
                  "web_view_link": f.get("webViewLink", ""),
                  "shared": f.get("shared", False)} for f in files]
    return JSONResponse({"documents": documents, "count": len(documents),
                         "next_page_token": result.get("nextPageToken")})


@mcp.custom_route("/api/docs/{document_id}", methods=["GET"])
async def rest_get_doc(request: Request) -> JSONResponse:
    """
    Get full document content as Markdown.
    Path param: document_id
    """
    from utils.docs_parser import doc_to_markdown  # noqa: PLC0415
    document_id = request.path_params["document_id"]
    docs = get_docs_service()
    doc = docs.documents().get(documentId=document_id).execute()
    return JSONResponse({"id": doc["documentId"], "title": doc.get("title", "Untitled"),
                         "content_markdown": doc_to_markdown(doc),
                         "revision_id": doc.get("revisionId", "")})


@mcp.custom_route("/api/docs/search", methods=["POST"])
async def rest_search_docs(request: Request) -> JSONResponse:
    """
    Search Google Docs by full-text.
    Body: { "query": "meeting notes", "max_results": 20 }
    """
    body = await _body(request)
    query = body.get("query")
    if not query:
        return _err("'query' is required")
    max_results = min(int(body.get("max_results", 20)), 100)
    safe_query = query.replace("'", "\\'")
    drive = get_drive_service()
    result = drive.files().list(
        q=f"mimeType='application/vnd.google-apps.document' and trashed=false and fullText contains '{safe_query}'",
        pageSize=max_results,
        fields="files(id, name, createdTime, modifiedTime, owners, webViewLink, shared)",
    ).execute()
    files = result.get("files", [])
    documents = [{"id": f["id"], "name": f["name"],
                  "modified_time": f.get("modifiedTime", ""),
                  "web_view_link": f.get("webViewLink", "")} for f in files]
    return JSONResponse({"documents": documents, "count": len(documents), "query": query})


@mcp.custom_route("/api/docs/create", methods=["POST"])
async def rest_create_doc(request: Request) -> JSONResponse:
    """
    Create a new Google Doc.
    Body: { "title": "My Doc", "content": "Optional initial text" }
    """
    body = await _body(request)
    title = body.get("title")
    if not title:
        return _err("'title' is required")
    content = body.get("content")
    docs = get_docs_service()
    drive = get_drive_service()
    doc = docs.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]
    if content:
        docs.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]}
        ).execute()
    file_meta = drive.files().get(fileId=doc_id, fields="webViewLink").execute()
    return JSONResponse({"id": doc_id, "title": title,
                         "web_view_link": file_meta.get("webViewLink", ""),
                         "status": "created"})


@mcp.custom_route("/api/docs/update", methods=["POST"])
async def rest_update_doc(request: Request) -> JSONResponse:
    """
    Append, prepend, or replace text in a Google Doc.
    Body: { "document_id": "...", "text": "...", "mode": "append" }
    mode: "append" | "prepend" | "replace"
    """
    body = await _body(request)
    document_id = body.get("document_id")
    text = body.get("text", "")
    mode = body.get("mode", "append")
    if not document_id:
        return _err("'document_id' is required")
    if mode not in ("append", "prepend", "replace"):
        return _err("'mode' must be 'append', 'prepend', or 'replace'")
    docs = get_docs_service()
    if mode == "replace":
        doc = docs.documents().get(documentId=document_id).execute()
        end_index = doc.get("body", {}).get("content", [{}])[-1].get("endIndex", 1)
        requests = []
        if end_index > 1:
            requests.append({"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end_index - 1}}})
        requests.append({"insertText": {"location": {"index": 1}, "text": text}})
    elif mode == "prepend":
        requests = [{"insertText": {"location": {"index": 1}, "text": text}}]
    else:
        doc = docs.documents().get(documentId=document_id).execute()
        end_index = doc.get("body", {}).get("content", [{}])[-1].get("endIndex", 1)
        requests = [{"insertText": {"location": {"index": end_index - 1}, "text": text}}]
    docs.documents().batchUpdate(documentId=document_id, body={"requests": requests}).execute()
    return JSONResponse({"id": document_id, "mode": mode,
                         "characters_written": len(text), "status": "updated"})


@mcp.custom_route("/api/docs/share", methods=["POST"])
async def rest_share_doc(request: Request) -> JSONResponse:
    """
    Share a Google Doc.
    Body: { "document_id": "...", "email": "...", "role": "reader", "send_notification": true, "message": null }
    role: "reader" | "commenter" | "writer" | "owner"
    """
    body = await _body(request)
    document_id = body.get("document_id")
    email = body.get("email")
    if not document_id or not email:
        return _err("'document_id' and 'email' are required")
    role = body.get("role", "reader")
    send_notification = body.get("send_notification", True)
    message = body.get("message")
    drive = get_drive_service()
    kwargs: dict = {
        "fileId": document_id,
        "body": {"type": "user", "role": role, "emailAddress": email},
        "sendNotificationEmail": send_notification,
        "fields": "id, role, emailAddress",
    }
    if message:
        kwargs["emailMessage"] = message
    perm = drive.permissions().create(**kwargs).execute()
    return JSONResponse({"document_id": document_id, "shared_with": email,
                         "role": role, "permission_id": perm["id"], "status": "shared"})


@mcp.custom_route("/api/docs/export", methods=["POST"])
async def rest_export_doc(request: Request) -> JSONResponse:
    """
    Export a Google Doc as PDF, DOCX, TXT, HTML, or ODT.
    Body: { "document_id": "...", "export_format": "pdf" }
    """
    import base64 as _b64  # noqa: PLC0415
    body = await _body(request)
    document_id = body.get("document_id")
    export_format = body.get("export_format", "pdf")
    if not document_id:
        return _err("'document_id' is required")
    mime_map = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain", "html": "text/html",
        "odt": "application/vnd.oasis.opendocument.text",
    }
    mime_type = mime_map.get(export_format)
    if not mime_type:
        return _err(f"Invalid export_format. Choose from: {list(mime_map.keys())}")
    drive = get_drive_service()
    content = drive.files().export(fileId=document_id, mimeType=mime_type).execute()
    return JSONResponse({"document_id": document_id, "export_format": export_format,
                         "content_base64": _b64.b64encode(content).decode("utf-8"),
                         "mime_type": mime_type, "size_bytes": len(content)})


@mcp.custom_route("/api/docs/delete", methods=["POST"])
async def rest_delete_doc(request: Request) -> JSONResponse:
    """
    Trash a Google Doc.
    Body: { "document_id": "..." }
    """
    body = await _body(request)
    document_id = body.get("document_id")
    if not document_id:
        return _err("'document_id' is required")
    drive = get_drive_service()
    drive.files().update(fileId=document_id, body={"trashed": True}).execute()
    return JSONResponse({"id": document_id, "status": "trashed"})


logger.info(
    "✓ Google Workspace MCP Server ready  "
    "(18 tools · 7 resources · 6 prompts)"

)


# ─────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Google Workspace MCP Server"
    )
    parser.add_argument(
        "--sse",
        action="store_true",
        help="Run as an SSE (HTTP) server instead of stdio.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_SSE_PORT", "8000")),
        help="Port for SSE transport (default: 8000).",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host for SSE transport (default: 0.0.0.0).",
    )
    args = parser.parse_args()

    # Use SSE by default on Railway, stdio locally
    use_sse = args.sse or IS_RAILWAY

    if use_sse:
        logger.info("Starting SSE server on %s:%d …", args.host, args.port)
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.run(transport="sse")
    else:
        logger.info("Starting stdio server…")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
