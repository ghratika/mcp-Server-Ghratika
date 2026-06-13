# 🔧 Google Workspace MCP Server

A complete **Model Context Protocol (MCP) server** in Python that integrates Gmail and Google Docs into any MCP-compatible AI host (Claude Desktop, Cursor, etc.).

---

## ✨ Features

### Gmail Tools (10)
| Tool | Description |
|---|---|
| `list_emails` | List emails from any mailbox label |
| `get_email` | Fetch full email body (HTML → Markdown) |
| `search_emails` | Search with Gmail query syntax |
| `send_email` | Compose and send a new email |
| `reply_to_email` | Thread-aware reply |
| `create_draft` | Save a draft without sending |
| `trash_email` | Move to trash |
| `list_labels` | List all Gmail labels with counts |
| `add_label` | Apply a label to a message |
| `remove_label` | Remove a label from a message |

### Google Docs Tools (8)
| Tool | Description |
|---|---|
| `list_documents` | List recent Google Docs |
| `get_document` | Fetch doc content as Markdown |
| `create_document` | Create a new doc (with optional content) |
| `update_document` | Append, prepend, or replace content |
| `search_documents` | Full-text search across all docs |
| `share_document` | Share with reader/writer/owner role |
| `export_document` | Export as PDF, DOCX, TXT, HTML, ODT |
| `delete_document` | Move to trash |

### Resources (7)
| URI | Description |
|---|---|
| `gmail://inbox` | Latest 20 inbox emails |
| `gmail://message/{id}` | Single email as Markdown |
| `gmail://thread/{id}` | Full email thread |
| `gmail://labels` | All Gmail labels |
| `gdocs://list` | All accessible Google Docs |
| `gdocs://document/{id}` | Full doc as Markdown |
| `gdocs://document/{id}/metadata` | Doc title, owners, permissions |

### Prompt Templates (6)
| Prompt | Description |
|---|---|
| `summarize_email_thread` | Summarise a thread (bullet, paragraph, exec summary) |
| `draft_reply` | Draft a context-aware reply |
| `review_document` | Review a doc (grammar, structure, clarity, tone) |
| `generate_document` | Generate a full doc from a topic |
| `email_to_doc` | Convert an email into a Google Doc |
| `daily_digest` | Create a digest of today's emails |

---

## 🚀 Setup Guide

### Step 1 — Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Give it a name (e.g. `MCP Workspace`) and click **Create**

### Step 2 — Enable Required APIs

In the Cloud Console, go to **APIs & Services → Library** and enable:
- ✅ **Gmail API**
- ✅ **Google Docs API**
- ✅ **Google Drive API**

### Step 3 — Create OAuth 2.0 Credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth 2.0 Client ID**
3. If prompted, configure the OAuth consent screen:
   - User Type: **External** (or Internal for Workspace orgs)
   - Add your email as a test user
   - Add these scopes:
     - `https://www.googleapis.com/auth/gmail.modify`
     - `https://www.googleapis.com/auth/gmail.compose`
     - `https://www.googleapis.com/auth/gmail.send`
     - `https://www.googleapis.com/auth/documents`
     - `https://www.googleapis.com/auth/drive`
4. Application type: **Desktop app**
5. Click **Create** → **Download JSON**
6. Rename the downloaded file to `credentials.json` and place it in the `MCP-SERVER` directory

### Step 4 — Install Dependencies

```powershell
cd "C:\Users\Lavanya gupta\OneDrive\Documents\Ghratika\MCP-SERVER"
pip install -r requirements.txt
```

Or using a virtual environment (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Step 5 — Configure Environment Variables

Copy the example `.env` file and fill it in:

```powershell
copy .env.example .env
```

The defaults work out of the box if `credentials.json` is in the project root.

### Step 6 — Run the First-Time Auth Flow

```powershell
python auth/google_auth.py
```

This will:
1. Open your browser to the Google OAuth consent screen
2. Ask you to log in and grant permissions
3. Save a `token.json` file for future runs (no browser needed after this)

### Step 7 — Test with MCP Inspector

```powershell
mcp dev server.py
```

This opens an interactive web UI where you can:
- Browse all 18 tools, 7 resources, and 6 prompts
- Call tools and see responses in real-time
- Test authentication before connecting to Claude Desktop

---

## 🖥️ Claude Desktop Integration

1. Open Claude Desktop's config file:
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

2. Merge in the contents of `claude_desktop_config.json` from this project:

```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "python",
      "args": [
        "C:/Users/Lavanya gupta/OneDrive/Documents/Ghratika/MCP-SERVER/server.py"
      ],
      "env": {
        "GOOGLE_CREDENTIALS_PATH": "C:/Users/Lavanya gupta/OneDrive/Documents/Ghratika/MCP-SERVER/credentials.json",
        "GOOGLE_TOKEN_PATH": "C:/Users/Lavanya gupta/OneDrive/Documents/Ghratika/MCP-SERVER/token.json",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

3. **Restart Claude Desktop** — the Google Workspace tools will appear in the tools list.

> **Tip**: If using a virtual environment, replace `"python"` with the full path to your venv Python:
> `"C:/Users/Lavanya gupta/OneDrive/Documents/Ghratika/MCP-SERVER/.venv/Scripts/python.exe"`

---

## 🌐 SSE (Remote HTTP) Mode

To run the server as an HTTP endpoint (e.g. for Cursor or remote clients):

```powershell
python server.py --sse --port 8000
```

The server will be available at `http://localhost:8000/sse`.

---

## 📁 Project Structure

```
MCP-SERVER/
├── server.py                  ← Main entrypoint
├── credentials.json           ← Your OAuth2 client credentials (DO NOT COMMIT)
├── token.json                 ← Auto-generated after first login (DO NOT COMMIT)
├── .env                       ← Your environment variables (DO NOT COMMIT)
├── .env.example               ← Environment variable template
├── requirements.txt           ← Python dependencies
├── claude_desktop_config.json ← Ready-to-paste Claude Desktop config
├── auth/
│   └── google_auth.py         ← OAuth2 lifecycle manager
├── tools/
│   ├── gmail_tools.py         ← Gmail MCP tools
│   └── docs_tools.py          ← Google Docs MCP tools
├── resources/
│   ├── gmail_resources.py     ← Gmail MCP resources
│   └── docs_resources.py      ← Google Docs MCP resources
├── prompts/
│   └── google_prompts.py      ← MCP prompt templates
└── utils/
    ├── html_to_text.py        ← HTML → Markdown converter
    └── docs_parser.py         ← Google Docs JSON → Markdown parser
```

---

## 🔒 Security Notes

> ⚠️ **Never commit these files to version control:**
> - `credentials.json` — your OAuth2 client secret
> - `token.json` — your personal access token
> - `.env` — your environment configuration

Add them to `.gitignore`:

```
credentials.json
token.json
.env
```

---

## 🔧 Troubleshooting

### "credentials.json not found"
Download it from Google Cloud Console → APIs & Services → Credentials.

### "Access blocked: This app's request is invalid"
Make sure the OAuth consent screen is configured and your email is added as a test user.

### "Token has been expired or revoked"
Delete `token.json` and run `python auth/google_auth.py` again.

### "ModuleNotFoundError: No module named 'mcp'"
Install dependencies: `pip install -r requirements.txt`

### Tools not appearing in Claude Desktop
- Verify the path in `claude_desktop_config.json` uses forward slashes
- Check Claude Desktop logs at `%APPDATA%\Claude\logs\`
- Make sure Python is in your PATH

---

## 📖 Example Workflows

### Summarise unread emails
> "Check my unread emails and give me a daily digest"
→ Uses `search_emails` + `daily_digest` prompt

### Draft and send a reply
> "Reply to the latest email from john@example.com — say I'll be there"
→ Uses `search_emails` + `get_email` + `send_email`

### Create a document from an email
> "Turn this email thread into a Google Doc summary"
→ Uses `get_email` + `create_document`

### Find and review a document
> "Find my Q4 report document and review its structure"
→ Uses `search_documents` + `get_document` + `review_document` prompt
