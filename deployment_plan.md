# 🚀 Railway Deployment Plan — Google Workspace MCP Server

## Overview

Railway is a cloud PaaS (Platform as a Service) that will host the MCP server in **SSE (Server-Sent Events) transport mode**, making it accessible to any remote MCP client over HTTP instead of only local stdio clients.

```
Before (local):  Claude Desktop ──stdio──► python server.py  (your machine)
After (Railway): Any MCP client ──HTTP──► https://your-app.railway.app/sse
```

---

## Architecture on Railway

```
Railway Container
├── Dockerfile         → defines the Python 3.12 environment
├── start.sh           → decodes base64 credentials → starts SSE server
├── server.py          → FastMCP in SSE mode, reads PORT from env
└── All other modules  → unchanged from local version

Environment Variables (Railway Dashboard)
├── GOOGLE_CREDENTIALS_B64   → base64(credentials.json)
├── GOOGLE_TOKEN_B64         → base64(token.json)
├── PORT                     → injected automatically by Railway
└── LOG_LEVEL                → INFO
```

> [!IMPORTANT]
> The credentials.json and token.json are **NOT copied into the Docker image**. They are stored as base64-encoded Railway environment variables and decoded at container startup. This keeps secrets out of your git repo and Docker image entirely.

---

## Files to Create / Modify

### Phase 1 — New files to create

| File | Purpose |
|---|---|
| `Dockerfile` | Container build instructions |
| `railway.toml` | Railway-specific config (start command, health check) |
| `start.sh` | Startup script: decode credentials → launch server |
| `auth/startup.py` | Python helper that reconstructs JSON files from env vars |

### Phase 2 — Files to modify

| File | Change |
|---|---|
| `server.py` | Default transport → SSE on Railway (detect via env var) |
| `.gitignore` | Already correct — credentials/token excluded ✅ |

---

## Step-by-Step Implementation

---

### Step 1 — Create `auth/startup.py`

Reconstructs `credentials.json` and `token.json` from base64 env vars at startup.

```python
# auth/startup.py
import base64, os, pathlib, sys

def reconstruct_credentials():
    """Decode base64 env vars → write JSON files before server starts."""
    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
    token_b64 = os.getenv("GOOGLE_TOKEN_B64")

    if creds_b64:
        path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
        pathlib.Path(path).write_bytes(base64.b64decode(creds_b64))
        print(f"[startup] credentials.json written to {path}", file=sys.stderr)

    if token_b64:
        path = os.getenv("GOOGLE_TOKEN_PATH", "token.json")
        pathlib.Path(path).write_bytes(base64.b64decode(token_b64))
        print(f"[startup] token.json written to {path}", file=sys.stderr)
    
    if not creds_b64:
        print("[startup] WARNING: GOOGLE_CREDENTIALS_B64 not set!", file=sys.stderr)
```

---

### Step 2 — Modify `server.py`

Add two changes:
1. Call `reconstruct_credentials()` before anything else
2. Auto-detect Railway environment and default to SSE

```python
# Add at the very top of server.py, after load_dotenv():
from auth.startup import reconstruct_credentials
reconstruct_credentials()

# Modify the main() function — change the default transport logic:
IS_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") is not None

def main():
    ...
    # Use SSE by default on Railway, stdio locally
    use_sse = args.sse or IS_RAILWAY
    port = int(os.getenv("PORT", args.port))  # Railway injects PORT

    if use_sse:
        mcp.run(transport="sse")   # FastMCP reads PORT from env automatically
    else:
        mcp.run(transport="stdio")
```

---

### Step 3 — Create `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (credentials NOT copied — injected via env vars)
COPY server.py .
COPY auth/ auth/
COPY tools/ tools/
COPY resources/ resources/
COPY prompts/ prompts/
COPY utils/ utils/

# Startup script
COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]
```

---

### Step 4 — Create `start.sh`

```bash
#!/bin/sh
# Decode credentials from env vars, then start the SSE server
python -c "from auth.startup import reconstruct_credentials; reconstruct_credentials()"
exec python server.py --sse --port ${PORT:-8000}
```

---

### Step 5 — Create `railway.toml`

```toml
[build]
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "./start.sh"
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3

[deploy.variables]
LOG_LEVEL = "INFO"
PYTHONUNBUFFERED = "1"
```

---

## Railway Dashboard Setup

### Step A — Get your base64 credentials

Run these commands locally to get the values to paste into Railway:

```powershell
# In MCP-SERVER directory:
python -c "import base64, pathlib; print(base64.b64encode(pathlib.Path('credentials.json').read_bytes()).decode())"
```
→ Copy the output → this is your `GOOGLE_CREDENTIALS_B64`

```powershell
python -c "import base64, pathlib; print(base64.b64encode(pathlib.Path('token.json').read_bytes()).decode())"
```
→ Copy the output → this is your `GOOGLE_TOKEN_B64`

---

### Step B — Create Railway project

1. Go to [railway.app](https://railway.app) and sign up / log in
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Connect your GitHub account and select the `MCP-SERVER` repository

> [!IMPORTANT]
> If the repo isn't on GitHub yet, push it first:
> ```powershell
> cd "C:\Users\Lavanya gupta\OneDrive\Documents\Ghratika\MCP-SERVER"
> git init
> git add .
> git commit -m "Initial commit: Google Workspace MCP Server"
> # Then push to GitHub
> ```
> `.gitignore` already excludes `credentials.json`, `token.json`, and `.env` ✅

---

### Step C — Set Environment Variables in Railway Dashboard

In your Railway service → **Variables** tab, add:

| Variable | Value |
|---|---|
| `GOOGLE_CREDENTIALS_B64` | *(output of credentials.json base64 command above)* |
| `GOOGLE_TOKEN_B64` | *(output of token.json base64 command above)* |
| `GOOGLE_CREDENTIALS_PATH` | `/app/credentials.json` |
| `GOOGLE_TOKEN_PATH` | `/app/token.json` |
| `LOG_LEVEL` | `INFO` |
| `PYTHONUNBUFFERED` | `1` |

> Railway automatically injects `PORT` — do **not** set it manually.

---

### Step D — Deploy

1. Railway will auto-detect the `Dockerfile` and build the container
2. Monitor the **Deploy Logs** tab — you should see:
   ```
   [startup] credentials.json written to /app/credentials.json
   [startup] token.json written to /app/token.json
   INFO: Registering Gmail tools…
   INFO: ✓ Google Workspace MCP Server ready (18 tools · 7 resources · 6 prompts)
   ```
3. Railway provides a public URL like: `https://mcp-server-production.railway.app`

---

### Step E — Get your public SSE URL

In Railway Dashboard → your service → **Settings** → **Networking**:
- Click **"Generate Domain"**
- Your SSE endpoint will be: `https://<your-app>.railway.app/sse`

---

## Connecting Remote Clients

### Claude Desktop (remote SSE)
```json
{
  "mcpServers": {
    "google-workspace": {
      "url": "https://<your-app>.railway.app/sse"
    }
  }
}
```

### Any MCP client
```
SSE URL: https://<your-app>.railway.app/sse
```

---

## Token Refresh Strategy

> [!WARNING]
> The OAuth `token.json` expires and gets a new access token every hour. The refresh token itself is long-lived but if it ever gets revoked, you'll need to re-run the local auth flow and update `GOOGLE_TOKEN_B64` in Railway.

**Recommended approach**: After any local re-authentication, update the Railway env var:
```powershell
# Re-encode updated token.json
python -c "import base64, pathlib; print(base64.b64encode(pathlib.Path('token.json').read_bytes()).decode())"
# Paste output into Railway Dashboard → Variables → GOOGLE_TOKEN_B64 → Redeploy
```

The google-auth library automatically refreshes the access token using the stored refresh token during normal operation — no intervention needed for day-to-day use.

---

## Cost Estimate

Railway's **Hobby plan** ($5/month) is more than sufficient:
- The MCP server is lightweight (event-driven, no polling)
- Typical usage: < 100MB RAM, < 0.1 vCPU at idle
- Railway's free tier provides $5 of credits/month (may cover this entirely)

---

## Security Checklist

- [x] `credentials.json` excluded from git via `.gitignore`
- [x] `token.json` excluded from git via `.gitignore`  
- [x] Credentials stored as Railway encrypted environment variables
- [x] Credentials decoded into container memory at runtime only
- [x] `Dockerfile` does not `COPY credentials.json` or `token.json`
- [ ] *(Optional)* Add `Authorization` header validation to restrict who can call the SSE endpoint

---

## Verification After Deployment

```bash
# Test SSE endpoint is reachable
curl -N https://<your-app>.railway.app/sse

# Should stream:
# data: {"jsonrpc":"2.0","method":"..."}
```
