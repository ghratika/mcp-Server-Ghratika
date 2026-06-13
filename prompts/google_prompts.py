"""
prompts/google_prompts.py
────────────────────────────────────────────────────────────────
Pre-built MCP Prompt templates for common Google Workspace workflows.

Prompts:
  • summarize_email_thread  – Summarize an email thread by ID
  • draft_reply             – Draft a context-aware reply to an email
  • review_document         – Review a Google Doc and suggest edits
  • generate_document       – Generate a full document from a topic
  • email_to_doc            – Convert an email into a structured Google Doc
  • daily_digest            – Summarize today's unread inbox emails
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent


def register_google_prompts(mcp: FastMCP) -> None:
    """Register all Google Workspace prompts on the given FastMCP instance."""

    # ─────────────────────────────────────────────────────────
    # summarize_email_thread
    # ─────────────────────────────────────────────────────────
    @mcp.prompt()
    def summarize_email_thread(
        thread_id: str,
        style: str = "bullet_points",
    ) -> list[TextContent]:
        """
        Generate a prompt to summarise a Gmail email thread.

        Args:
            thread_id: The Gmail thread ID to summarise.
            style:     Output style — "bullet_points" (default), "paragraph",
                       or "executive_summary".

        The caller should use the resource gmail://thread/{thread_id} to
        load the thread content and supply it to the LLM.
        """
        style_instructions = {
            "bullet_points": "Use concise bullet points for each key point.",
            "paragraph": "Write a flowing paragraph summary.",
            "executive_summary": (
                "Write a short executive summary (2–3 sentences) followed by "
                "a bulleted list of action items."
            ),
        }.get(style, "Use concise bullet points.")

        return [
            TextContent(
                type="text",
                text=(
                    f"Please summarise the email thread with ID `{thread_id}`.\n\n"
                    "Instructions:\n"
                    f"- {style_instructions}\n"
                    "- Identify the main topic, key decisions, and any outstanding action items.\n"
                    "- Note who sent each important message.\n"
                    "- Flag any urgent items or deadlines.\n\n"
                    f"To load the thread, use the resource: `gmail://thread/{thread_id}`"
                ),
            )
        ]

    # ─────────────────────────────────────────────────────────
    # draft_reply
    # ─────────────────────────────────────────────────────────
    @mcp.prompt()
    def draft_reply(
        message_id: str,
        tone: str = "professional",
        key_points: str = "",
    ) -> list[TextContent]:
        """
        Generate a prompt to draft a contextually-aware email reply.

        Args:
            message_id: The Gmail message ID to reply to.
            tone:       Desired tone — "professional" (default), "friendly",
                        "formal", or "concise".
            key_points: Comma-separated list of points to include in the reply.

        The caller should load the original email with `gmail://message/{message_id}`
        and include it in context before running this prompt.
        """
        tone_map = {
            "professional": "professional and courteous",
            "friendly": "warm and friendly",
            "formal": "formal and respectful",
            "concise": "brief and to-the-point (3 sentences max)",
        }
        tone_desc = tone_map.get(tone, "professional and courteous")

        points_section = ""
        if key_points.strip():
            points = [p.strip() for p in key_points.split(",") if p.strip()]
            points_section = "\n\nKey points to address in the reply:\n" + "\n".join(
                f"- {p}" for p in points
            )

        return [
            TextContent(
                type="text",
                text=(
                    f"Draft a reply to the email with ID `{message_id}`.\n\n"
                    f"Tone: {tone_desc}\n"
                    f"{points_section}\n\n"
                    "Instructions:\n"
                    "- Begin with an appropriate greeting.\n"
                    "- Address all questions or requests in the original email.\n"
                    "- Be clear and avoid unnecessary filler text.\n"
                    "- End with an appropriate sign-off.\n"
                    "- Do NOT include a subject line — only the body.\n\n"
                    f"Load the original email first: `gmail://message/{message_id}`"
                ),
            )
        ]

    # ─────────────────────────────────────────────────────────
    # review_document
    # ─────────────────────────────────────────────────────────
    @mcp.prompt()
    def review_document(
        document_id: str,
        focus: str = "overall",
    ) -> list[TextContent]:
        """
        Generate a prompt to review a Google Doc and suggest improvements.

        Args:
            document_id: The Google Doc ID to review.
            focus:       Review focus:
                           "overall"    – Full review (default)
                           "grammar"    – Grammar and spelling only
                           "structure"  – Document structure and flow
                           "clarity"    – Clarity and conciseness
                           "tone"       – Tone and voice consistency

        The caller should load the document with `gdocs://document/{document_id}`.
        """
        focus_instructions = {
            "overall": (
                "Perform a comprehensive review covering grammar, structure, "
                "clarity, tone, and any factual/logical issues."
            ),
            "grammar": "Focus exclusively on grammar, spelling, and punctuation errors.",
            "structure": (
                "Focus on document structure: heading hierarchy, paragraph flow, "
                "logical ordering of ideas, and use of lists/tables."
            ),
            "clarity": (
                "Focus on clarity and conciseness: identify verbose sentences, "
                "jargon, ambiguous language, and suggest rewrites."
            ),
            "tone": (
                "Focus on tone and voice: ensure consistency, identify inappropriate "
                "formality shifts, and suggest adjustments."
            ),
        }.get(focus, "Perform a comprehensive review.")

        return [
            TextContent(
                type="text",
                text=(
                    f"Review the Google Doc with ID `{document_id}`.\n\n"
                    f"Review focus: {focus_instructions}\n\n"
                    "Output format:\n"
                    "1. **Summary**: 2–3 sentence overall assessment.\n"
                    "2. **Issues Found**: Numbered list of specific issues with "
                    "   the exact location (paragraph/section) and suggested fix.\n"
                    "3. **Revised Sections** (optional): If major rewrites are needed, "
                    "   provide the revised text.\n\n"
                    f"Load the document: `gdocs://document/{document_id}`"
                ),
            )
        ]

    # ─────────────────────────────────────────────────────────
    # generate_document
    # ─────────────────────────────────────────────────────────
    @mcp.prompt()
    def generate_document(
        topic: str,
        document_type: str = "report",
        audience: str = "general",
        length: str = "medium",
    ) -> list[TextContent]:
        """
        Generate a prompt to create a full Google Doc on a given topic.

        Args:
            topic:         The topic or title of the document.
            document_type: Type of document:
                             "report", "proposal", "memo", "blog_post",
                             "meeting_notes", "technical_spec", "email_template"
            audience:      Target audience ("general", "technical", "executive").
            length:        Approximate length:
                             "short" (~300 words), "medium" (~800 words),
                             "long" (~2000 words).

        After generating, use the create_document tool to save it to Google Docs.
        """
        length_map = {
            "short": "approximately 300 words",
            "medium": "approximately 800 words",
            "long": "approximately 2000 words",
        }
        length_desc = length_map.get(length, "approximately 800 words")

        type_instructions = {
            "report": "Include an executive summary, findings, analysis, and recommendations.",
            "proposal": "Include a problem statement, proposed solution, timeline, and budget estimate.",
            "memo": "Use a formal memo format: To, From, Date, Subject, and body.",
            "blog_post": "Use an engaging introduction, subheadings, and a conclusion with a call to action.",
            "meeting_notes": "Include attendees, agenda items, discussion points, decisions, and action items.",
            "technical_spec": "Include overview, requirements, architecture, API/interface definitions, and edge cases.",
            "email_template": "Write a reusable email template with [PLACEHOLDER] fields clearly marked.",
        }.get(document_type, "Structure the document appropriately for its type.")

        return [
            TextContent(
                type="text",
                text=(
                    f"Write a {document_type} about: **{topic}**\n\n"
                    f"Target audience: {audience}\n"
                    f"Length: {length_desc}\n\n"
                    f"Structure: {type_instructions}\n\n"
                    "Additional guidelines:\n"
                    "- Use clear headings and subheadings.\n"
                    "- Write in a professional, polished style.\n"
                    "- Include relevant examples or data where appropriate.\n"
                    "- Ensure the content is accurate and well-organised.\n\n"
                    "Once written, use the `create_document` tool to save it to Google Docs."
                ),
            )
        ]

    # ─────────────────────────────────────────────────────────
    # email_to_doc
    # ─────────────────────────────────────────────────────────
    @mcp.prompt()
    def email_to_doc(
        message_id: str,
        doc_title: str = "",
    ) -> list[TextContent]:
        """
        Generate a prompt to convert an email into a structured Google Doc.

        Args:
            message_id: The Gmail message ID to convert.
            doc_title:  Optional title for the resulting Google Doc.
                        If empty, a title is generated from the email subject.

        Use gmail://message/{message_id} to load the email, then
        create_document to save the result.
        """
        title_instruction = (
            f'Title the document "{doc_title}".'
            if doc_title
            else "Derive an appropriate document title from the email subject."
        )

        return [
            TextContent(
                type="text",
                text=(
                    f"Convert the email with ID `{message_id}` into a well-structured Google Doc.\n\n"
                    f"{title_instruction}\n\n"
                    "Conversion guidelines:\n"
                    "1. Extract the key information from the email.\n"
                    "2. Organise it with appropriate headings and sections.\n"
                    "3. Convert any lists in the email body to proper bullet points.\n"
                    "4. Highlight action items in a dedicated 'Action Items' section.\n"
                    "5. Include a 'Document created from email' note at the top with "
                    "   the original sender, date, and subject.\n\n"
                    "Steps to follow:\n"
                    f"1. Load the email: `gmail://message/{message_id}`\n"
                    "2. Generate the document content per the guidelines above.\n"
                    "3. Use the `create_document` tool to save it to Google Docs.\n"
                    "4. Return the new document's URL."
                ),
            )
        ]

    # ─────────────────────────────────────────────────────────
    # daily_digest
    # ─────────────────────────────────────────────────────────
    @mcp.prompt()
    def daily_digest(
        max_emails: int = 20,
        include_categories: str = "all",
    ) -> list[TextContent]:
        """
        Generate a prompt to create a daily digest of unread inbox emails.

        Args:
            max_emails:          Number of emails to include (default: 20).
            include_categories:  Which emails to include:
                                   "all" (default), "unread", "important".

        Use the list_emails or search_emails tool to fetch the emails first.
        """
        query_map = {
            "all": "is:inbox newer_than:1d",
            "unread": "is:inbox is:unread newer_than:1d",
            "important": "is:inbox is:important newer_than:1d",
        }
        query = query_map.get(include_categories, "is:inbox newer_than:1d")

        return [
            TextContent(
                type="text",
                text=(
                    "Create a daily email digest for today.\n\n"
                    "Steps:\n"
                    f"1. Use the `search_emails` tool with query: `{query}` "
                    f"   and max_results: {max_emails}\n"
                    "2. For each email, note the sender, subject, and key content.\n"
                    "3. Organise the digest into these sections:\n\n"
                    "   **📧 Today's Email Digest**\n"
                    "   - **🔴 Urgent / Action Required**: Emails needing immediate response.\n"
                    "   - **📋 For Review**: Important emails to read.\n"
                    "   - **📰 FYI / Informational**: Newsletters, notifications, updates.\n"
                    "   - **🗑️ Low Priority**: Emails that can be archived or ignored.\n\n"
                    "4. For each email, provide:\n"
                    "   - Subject and sender\n"
                    "   - One-line summary\n"
                    "   - Suggested action (reply, archive, forward, etc.)\n\n"
                    "5. End with a count: X urgent, Y for review, Z informational."
                ),
            )
        ]
