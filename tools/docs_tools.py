"""
tools/docs_tools.py
────────────────────────────────────────────────────────────────
All Google Docs MCP tools registered on the FastMCP server.

Tools exposed:
  • list_documents    – List recent Google Docs from Drive
  • get_document      – Fetch a doc's full content as Markdown
  • create_document   – Create a new Google Doc (optionally with content)
  • update_document   – Append text or replace document content
  • search_documents  – Search docs by title or full-text
  • share_document    – Share a doc with an email address
  • export_document   – Export a doc as PDF, DOCX, or plain text
  • delete_document   – Move a document to trash
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Literal, Optional

from mcp.server.fastmcp import FastMCP

from auth.google_auth import get_docs_service, get_drive_service
from utils.docs_parser import doc_to_markdown

logger = logging.getLogger(__name__)


def register_docs_tools(mcp: FastMCP) -> None:
    """Register all Google Docs tools on the given FastMCP instance."""

    # ─────────────────────────────────────────────────────────
    # list_documents
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def list_documents(
        max_results: int = 20,
        order_by: str = "modifiedTime desc",
        page_token: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        List Google Docs accessible to the authenticated user.

        Args:
            max_results: Number of documents to return (1–100). Default: 20.
            order_by:    Drive sort field. Examples:
                           "modifiedTime desc"  (default — most recently modified first)
                           "createdTime desc"   (newest first)
                           "name"               (alphabetical)
            page_token:  Pagination token for the next page.

        Returns:
            A dict with:
              - documents: list of {id, name, created_time, modified_time,
                           owners, web_view_link}
              - next_page_token
        """
        drive = get_drive_service()
        max_results = max(1, min(100, max_results))

        kwargs: dict[str, Any] = {
            "q": "mimeType='application/vnd.google-apps.document' and trashed=false",
            "pageSize": max_results,
            "orderBy": order_by,
            "fields": (
                "nextPageToken, files(id, name, createdTime, modifiedTime, "
                "owners, webViewLink, shared)"
            ),
        }
        if page_token:
            kwargs["pageToken"] = page_token

        result = drive.files().list(**kwargs).execute()
        files = result.get("files", [])

        documents = [
            {
                "id": f["id"],
                "name": f["name"],
                "created_time": f.get("createdTime", ""),
                "modified_time": f.get("modifiedTime", ""),
                "owners": [o.get("emailAddress", "") for o in f.get("owners", [])],
                "web_view_link": f.get("webViewLink", ""),
                "shared": f.get("shared", False),
            }
            for f in files
        ]

        return {
            "documents": documents,
            "count": len(documents),
            "next_page_token": result.get("nextPageToken"),
        }

    # ─────────────────────────────────────────────────────────
    # get_document
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def get_document(document_id: str) -> dict[str, Any]:
        """
        Fetch the full content of a Google Doc, converted to Markdown.

        Args:
            document_id: The Google Doc ID (the long string in its URL
                         e.g. https://docs.google.com/document/d/<document_id>/edit).

        Returns:
            A dict with:
              - id, title
              - content_markdown: full document body as Markdown
              - revision_id
              - document_style: {page_size, margin info}
        """
        docs = get_docs_service()
        doc = docs.documents().get(documentId=document_id).execute()

        return {
            "id": doc["documentId"],
            "title": doc.get("title", "Untitled"),
            "content_markdown": doc_to_markdown(doc),
            "revision_id": doc.get("revisionId", ""),
        }

    # ─────────────────────────────────────────────────────────
    # create_document
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def create_document(
        title: str,
        content: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Create a new Google Doc, optionally pre-populated with text content.

        Args:
            title:   The document title.
            content: Optional plain text to insert into the document body.

        Returns:
            A dict with the new document's id, title, and web_view_link.
        """
        docs = get_docs_service()
        drive = get_drive_service()

        # Create the document
        doc = docs.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]

        # Insert content if provided
        if content:
            docs.documents().batchUpdate(
                documentId=doc_id,
                body={
                    "requests": [
                        {
                            "insertText": {
                                "location": {"index": 1},
                                "text": content,
                            }
                        }
                    ]
                },
            ).execute()

        # Get web link from Drive
        file_meta = drive.files().get(
            fileId=doc_id, fields="webViewLink"
        ).execute()

        return {
            "id": doc_id,
            "title": title,
            "web_view_link": file_meta.get("webViewLink", ""),
            "status": "created",
        }

    # ─────────────────────────────────────────────────────────
    # update_document
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def update_document(
        document_id: str,
        text: str,
        mode: Literal["append", "prepend", "replace"] = "append",
    ) -> dict[str, Any]:
        """
        Insert or replace text in a Google Doc.

        Args:
            document_id: The Google Doc ID.
            text:        The text content to insert.
            mode:        How to insert the text:
                           "append"  – Add text at the end of the document (default).
                           "prepend" – Add text at the beginning of the document.
                           "replace" – Delete all existing content and insert fresh text.

        Returns:
            Confirmation dict with id, mode, and characters_written.
        """
        docs = get_docs_service()

        if mode == "replace":
            # First fetch the document to know its end index
            doc = docs.documents().get(documentId=document_id).execute()
            end_index = doc.get("body", {}).get("content", [{}])[-1].get(
                "endIndex", 1
            )
            requests = []
            if end_index > 1:
                requests.append({
                    "deleteContentRange": {
                        "range": {"startIndex": 1, "endIndex": end_index - 1}
                    }
                })
            requests.append({
                "insertText": {
                    "location": {"index": 1},
                    "text": text,
                }
            })
        elif mode == "prepend":
            requests = [{
                "insertText": {
                    "location": {"index": 1},
                    "text": text,
                }
            }]
        else:  # append
            doc = docs.documents().get(documentId=document_id).execute()
            end_index = doc.get("body", {}).get("content", [{}])[-1].get(
                "endIndex", 1
            )
            # Google Docs API requires insert index >= 1.
            # A fresh empty doc has end_index == 1, so end_index - 1 == 0
            # which the API rejects silently. Clamp to a minimum of 1.
            insert_index = max(1, end_index - 1)
            requests = [{
                "insertText": {
                    "location": {"index": insert_index},
                    "text": text,
                }
            }]
            logger.info(
                "update_document: mode=append doc=%s insert_index=%d text_len=%d",
                document_id, insert_index, len(text),
            )

        result = docs.documents().batchUpdate(
            documentId=document_id, body={"requests": requests}
        ).execute()
        logger.info(
            "batchUpdate executed: doc=%s replies=%s",
            document_id, result.get("replies", []),
        )

        return {
            "id": document_id,
            "mode": mode,
            "characters_written": len(text),
            "replies": result.get("replies", []),
            "status": "updated",
        }

    # ─────────────────────────────────────────────────────────
    # search_documents
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def search_documents(
        query: str,
        max_results: int = 20,
    ) -> dict[str, Any]:
        """
        Search Google Docs by title or full-text content.

        The query is matched against document titles and content using
        Google Drive's full-text search.

        Args:
            query:       Search term (e.g. "Q4 report", "meeting agenda 2024").
            max_results: Maximum results to return (1–100). Default: 20.

        Returns:
            Same structure as list_documents.
        """
        drive = get_drive_service()
        max_results = max(1, min(100, max_results))

        # Escape single quotes in query
        safe_query = query.replace("'", "\\'")
        drive_query = (
            f"mimeType='application/vnd.google-apps.document' "
            f"and trashed=false "
            f"and fullText contains '{safe_query}'"
        )

        result = drive.files().list(
            q=drive_query,
            pageSize=max_results,
            fields=(
                "files(id, name, createdTime, modifiedTime, "
                "owners, webViewLink, shared)"
            ),
        ).execute()

        files = result.get("files", [])
        documents = [
            {
                "id": f["id"],
                "name": f["name"],
                "created_time": f.get("createdTime", ""),
                "modified_time": f.get("modifiedTime", ""),
                "owners": [o.get("emailAddress", "") for o in f.get("owners", [])],
                "web_view_link": f.get("webViewLink", ""),
                "shared": f.get("shared", False),
            }
            for f in files
        ]

        return {
            "documents": documents,
            "count": len(documents),
            "query": query,
        }

    # ─────────────────────────────────────────────────────────
    # share_document
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def share_document(
        document_id: str,
        email: str,
        role: Literal["reader", "commenter", "writer", "owner"] = "reader",
        send_notification: bool = True,
        message: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Share a Google Doc with an email address.

        Args:
            document_id:       The Google Doc ID.
            email:             The email address to share with.
            role:              Permission level:
                                 "reader"    – View only (default)
                                 "commenter" – View and comment
                                 "writer"    – Edit
                                 "owner"     – Transfer ownership (irreversible!)
            send_notification: Whether to send an email notification. Default: True.
            message:           Optional message to include in the notification.

        Returns:
            A dict confirming the share with permission id and role.
        """
        drive = get_drive_service()

        body: dict[str, Any] = {
            "type": "user",
            "role": role,
            "emailAddress": email,
        }

        kwargs: dict[str, Any] = {
            "fileId": document_id,
            "body": body,
            "sendNotificationEmail": send_notification,
            "fields": "id, role, emailAddress",
        }
        if message:
            kwargs["emailMessage"] = message

        perm = drive.permissions().create(**kwargs).execute()

        return {
            "document_id": document_id,
            "shared_with": email,
            "role": role,
            "permission_id": perm["id"],
            "status": "shared",
        }

    # ─────────────────────────────────────────────────────────
    # export_document
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def export_document(
        document_id: str,
        export_format: Literal["pdf", "docx", "txt", "html", "odt"] = "pdf",
    ) -> dict[str, Any]:
        """
        Export a Google Doc as a file in the specified format.

        Args:
            document_id:   The Google Doc ID.
            export_format: Export format — one of:
                             "pdf"  – PDF document (default)
                             "docx" – Microsoft Word
                             "txt"  – Plain text
                             "html" – HTML with inline CSS
                             "odt"  – OpenDocument Text

        Returns:
            A dict with:
              - document_id
              - export_format
              - content_base64: base64-encoded file content
              - mime_type: MIME type of the exported file
              - size_bytes: size of the exported content
        """
        drive = get_drive_service()

        mime_map: dict[str, str] = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "txt": "text/plain",
            "html": "text/html",
            "odt": "application/vnd.oasis.opendocument.text",
        }
        mime_type = mime_map.get(export_format, "application/pdf")

        content = drive.files().export(
            fileId=document_id, mimeType=mime_type
        ).execute()

        encoded = base64.b64encode(content).decode("utf-8")

        return {
            "document_id": document_id,
            "export_format": export_format,
            "content_base64": encoded,
            "mime_type": mime_type,
            "size_bytes": len(content),
        }

    # ─────────────────────────────────────────────────────────
    # delete_document
    # ─────────────────────────────────────────────────────────
    @mcp.tool()
    def delete_document(document_id: str) -> dict[str, Any]:
        """
        Move a Google Doc to the Trash.

        Note: The document is NOT permanently deleted immediately — it
        remains in the Trash for 30 days before automatic deletion.

        Args:
            document_id: The Google Doc ID to trash.

        Returns:
            Confirmation dict with id and status.
        """
        drive = get_drive_service()
        drive.files().update(
            fileId=document_id, body={"trashed": True}
        ).execute()

        return {
            "id": document_id,
            "status": "trashed",
        }
