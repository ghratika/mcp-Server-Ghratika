"""
resources/docs_resources.py
────────────────────────────────────────────────────────────────
MCP Resources for Google Docs.

Resources:
  gdocs://list                        – All accessible Google Docs (summary list)
  gdocs://document/{id}               – Full document content as Markdown
  gdocs://document/{id}/metadata      – Document metadata (title, owner, revision)
"""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from auth.google_auth import get_docs_service, get_drive_service
from utils.docs_parser import doc_to_markdown

logger = logging.getLogger(__name__)


def register_docs_resources(mcp: FastMCP) -> None:
    """Register all Google Docs resources on the given FastMCP instance."""

    # ─────────────────────────────────────────────────────────
    # gdocs://list
    # ─────────────────────────────────────────────────────────
    @mcp.resource("gdocs://list")
    def gdocs_list() -> str:
        """
        List of all accessible Google Docs (up to 50 most recently modified).

        Returns a JSON array of:
          [{id, name, created_time, modified_time, owners, web_view_link}]
        """
        drive = get_drive_service()
        result = drive.files().list(
            q="mimeType='application/vnd.google-apps.document' and trashed=false",
            pageSize=50,
            orderBy="modifiedTime desc",
            fields=(
                "files(id, name, createdTime, modifiedTime, owners, "
                "webViewLink, shared)"
            ),
        ).execute()

        files = result.get("files", [])
        documents = [
            {
                "id": f["id"],
                "name": f["name"],
                "created_time": f.get("createdTime", ""),
                "modified_time": f.get("modifiedTime", ""),
                "owners": [
                    o.get("emailAddress", "") for o in f.get("owners", [])
                ],
                "web_view_link": f.get("webViewLink", ""),
                "shared": f.get("shared", False),
            }
            for f in files
        ]
        return json.dumps(documents, indent=2, ensure_ascii=False)

    # ─────────────────────────────────────────────────────────
    # gdocs://document/{id}
    # ─────────────────────────────────────────────────────────
    @mcp.resource("gdocs://document/{document_id}")
    def gdocs_document(document_id: str) -> str:
        """
        Full content of a Google Doc, converted to Markdown.

        Returns a JSON object:
          {id, title, content_markdown, revision_id}
        """
        docs = get_docs_service()
        doc = docs.documents().get(documentId=document_id).execute()

        return json.dumps({
            "id": doc["documentId"],
            "title": doc.get("title", "Untitled"),
            "content_markdown": doc_to_markdown(doc),
            "revision_id": doc.get("revisionId", ""),
        }, indent=2, ensure_ascii=False)

    # ─────────────────────────────────────────────────────────
    # gdocs://document/{id}/metadata
    # ─────────────────────────────────────────────────────────
    @mcp.resource("gdocs://document/{document_id}/metadata")
    def gdocs_document_metadata(document_id: str) -> str:
        """
        Metadata for a Google Doc (no body content fetched).

        Returns a JSON object with title, owners, permissions, and timestamps.
        """
        drive = get_drive_service()
        file_meta = drive.files().get(
            fileId=document_id,
            fields=(
                "id, name, createdTime, modifiedTime, owners, "
                "webViewLink, shared, permissions, size"
            ),
        ).execute()

        permissions = [
            {
                "email": p.get("emailAddress", ""),
                "role": p.get("role", ""),
                "type": p.get("type", ""),
                "display_name": p.get("displayName", ""),
            }
            for p in file_meta.get("permissions", [])
        ]

        return json.dumps({
            "id": file_meta["id"],
            "title": file_meta.get("name", "Untitled"),
            "created_time": file_meta.get("createdTime", ""),
            "modified_time": file_meta.get("modifiedTime", ""),
            "owners": [
                o.get("emailAddress", "")
                for o in file_meta.get("owners", [])
            ],
            "web_view_link": file_meta.get("webViewLink", ""),
            "shared": file_meta.get("shared", False),
            "permissions": permissions,
        }, indent=2, ensure_ascii=False)
