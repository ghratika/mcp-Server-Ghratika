"""
auth/startup.py
────────────────────────────────────────────────────────────────
Helper script for Railway deployments.
Reconstructs credentials.json and token.json from base64 environment
variables so the server can authenticate when running in a container.
"""

import base64
import os
import pathlib
import sys

def reconstruct_credentials() -> None:
    """Decode base64 env vars and write JSON files before server starts."""
    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
    token_b64 = os.getenv("GOOGLE_TOKEN_B64")

    if creds_b64:
        path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        try:
            pathlib.Path(path).write_bytes(base64.b64decode(creds_b64))
            print(f"[startup] ✓ Credentials written to {path}", file=sys.stderr)
        except Exception as e:
            print(f"[startup] ✗ Error writing credentials: {e}", file=sys.stderr)

    if token_b64:
        path = os.getenv("GOOGLE_TOKEN_PATH", "token.json")
        try:
            pathlib.Path(path).write_bytes(base64.b64decode(token_b64))
            print(f"[startup] ✓ Token written to {path}", file=sys.stderr)
        except Exception as e:
            print(f"[startup] ✗ Error writing token: {e}", file=sys.stderr)
    
    if not creds_b64 and os.getenv("RAILWAY_ENVIRONMENT"):
        print("[startup] WARNING: GOOGLE_CREDENTIALS_B64 not set in Railway!", file=sys.stderr)
