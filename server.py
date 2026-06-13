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
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        logger.info("Starting stdio server…")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
