"""
auth/google_auth.py
────────────────────────────────────────────────────────────────
Handles the complete OAuth2 lifecycle for Google APIs.

Flow:
  1. Read credential/token paths from environment variables.
  2. If a saved token exists → load and auto-refresh if expired.
  3. If no token (first run) → launch browser consent flow and
     save the resulting token for future runs.

Environment variables (see .env.example):
  GOOGLE_CREDENTIALS_PATH  Path to credentials.json  (default: credentials.json)
  GOOGLE_TOKEN_PATH        Path to token.json         (default: token.json)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# OAuth2 Scopes
# All scopes the server requires. They are requested together
# in a single consent screen so the user only logs in once.
# ─────────────────────────────────────────────────────────────
SCOPES: list[str] = [
    # Gmail
    "https://www.googleapis.com/auth/gmail.modify",          # read + labels
    "https://www.googleapis.com/auth/gmail.compose",         # compose/send/draft
    "https://www.googleapis.com/auth/gmail.send",            # send
    # Google Docs
    "https://www.googleapis.com/auth/documents",             # read + write docs
    # Google Drive (needed to list/create/share/delete docs)
    "https://www.googleapis.com/auth/drive",
]

_CREDENTIALS_PATH = Path(
    os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
)
_TOKEN_PATH = Path(os.getenv("GOOGLE_TOKEN_PATH", "token.json"))


def get_credentials() -> Credentials:
    """
    Return a valid Google OAuth2 Credentials object.

    On the very first call (no token.json present) this will open a
    browser window for the user to authorise the application.
    All subsequent calls load and auto-refresh the stored token.

    Raises:
        FileNotFoundError: If credentials.json is missing.
        google.auth.exceptions.RefreshError: If the token cannot be refreshed.
    """
    if not _CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Google credentials file not found at '{_CREDENTIALS_PATH}'.\n"
            "Download it from Google Cloud Console → APIs & Services → "
            "Credentials and place it at the path configured by "
            "GOOGLE_CREDENTIALS_PATH (default: credentials.json)."
        )

    creds: Credentials | None = None

    # ── Load existing token ───────────────────────────────────
    if _TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(
                str(_TOKEN_PATH), SCOPES
            )
            logger.debug("Loaded token from %s", _TOKEN_PATH)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load token (%s) – re-authorising.", exc)
            creds = None

    # ── Refresh or re-authorise ───────────────────────────────
    if creds and creds.expired and creds.refresh_token:
        logger.info("Refreshing expired Google token…")
        creds.refresh(Request())
    elif not creds or not creds.valid:
        logger.info(
            "No valid token found. Starting OAuth2 browser flow…\n"
            "(If running headlessly, set GOOGLE_TOKEN_PATH to a pre-generated "
            "token.json.)"
        )
        flow = InstalledAppFlow.from_client_secrets_file(
            str(_CREDENTIALS_PATH), SCOPES
        )
        creds = flow.run_local_server(port=0)

    # ── Persist token for next run ────────────────────────────
    _TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    logger.debug("Token saved to %s", _TOKEN_PATH)

    return creds


# ─────────────────────────────────────────────────────────────
# Service builders (cached at module level for efficiency)
# ─────────────────────────────────────────────────────────────
_gmail_service = None
_docs_service = None
_drive_service = None


def get_gmail_service():
    """Return a cached Gmail API service client."""
    global _gmail_service  # noqa: PLW0603
    if _gmail_service is None:
        _gmail_service = build("gmail", "v1", credentials=get_credentials())
        logger.debug("Gmail service initialised.")
    return _gmail_service


def get_docs_service():
    """Return a cached Google Docs API service client."""
    global _docs_service  # noqa: PLW0603
    if _docs_service is None:
        _docs_service = build("docs", "v1", credentials=get_credentials())
        logger.debug("Docs service initialised.")
    return _docs_service


def get_drive_service():
    """Return a cached Google Drive API service client (used for file ops)."""
    global _drive_service  # noqa: PLW0603
    if _drive_service is None:
        _drive_service = build("drive", "v3", credentials=get_credentials())
        logger.debug("Drive service initialised.")
    return _drive_service


# ─────────────────────────────────────────────────────────────
# CLI helper: run as `python auth/google_auth.py` to bootstrap
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    creds = get_credentials()
    print(f"✓ Authenticated successfully! Token saved to {_TOKEN_PATH}")
    print(f"  Valid: {creds.valid}  | Expiry: {creds.expiry}")
