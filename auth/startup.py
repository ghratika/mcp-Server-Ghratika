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

# Absolute path to the MCP-SERVER root (auth/startup.py → auth/ → MCP-SERVER/)
# Must match the anchor in auth/google_auth.py so that files written here
# are found at the same location that get_credentials() reads from.
_SERVER_ROOT = pathlib.Path(__file__).resolve().parent.parent

def reconstruct_credentials() -> None:
    """Decode base64 env vars and write JSON files before server starts."""
    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
    token_b64 = os.getenv("GOOGLE_TOKEN_B64")

    if creds_b64:
        path = os.getenv("GOOGLE_CREDENTIALS_PATH", str(_SERVER_ROOT / "credentials.json"))
        try:
            pathlib.Path(path).write_bytes(base64.b64decode(creds_b64))
            print(f"[startup] ✓ Credentials written to {path}", file=sys.stderr)
        except Exception as e:
            print(f"[startup] ✗ Error writing credentials: {e}", file=sys.stderr)

    if token_b64:
        path = os.getenv("GOOGLE_TOKEN_PATH", str(_SERVER_ROOT / "token.json"))
        try:
            pathlib.Path(path).write_bytes(base64.b64decode(token_b64))
            print(f"[startup] ✓ Token written to {path}", file=sys.stderr)
        except Exception as e:
            print(f"[startup] ✗ Error writing token: {e}", file=sys.stderr)
    
    if not creds_b64 and os.getenv("RAILWAY_ENVIRONMENT"):
        print("[startup] WARNING: GOOGLE_CREDENTIALS_B64 not set in Railway!", file=sys.stderr)
