# Dragoo Email Agent — Complete Setup Guide

> This document covers every step taken to build this agent from scratch.
> Anyone can follow this guide to recreate it manually.
> Items marked [AI GENERATED] were built automatically by Claude AI.
> Items marked [MANUAL] require you to do them yourself.
> **This guide is kept in sync with agent.py. Any code change updates this file.**

---

## What This Agent Does

- Read and browse Gmail inbox with unread count
- Summarize any email in 3 bullet points using AI
- Reply to emails with AI-written responses
- Forward emails to anyone
- Compose and send new emails
- Create drafts and edit before sending
- Archive and delete emails
- Empty the trash bin
- Search emails by sender, keyword, or topic
- Save and reuse email templates
- Auto-refresh inbox every 5 minutes
- Push-to-talk voice input (hold Spacebar)

---

## PART 1 — SYSTEM REQUIREMENTS

### Step 1 — Install Python [MANUAL]
1. Go to: https://python.org/downloads
2. Download Python 3.9 or above
3. Run the installer
4. IMPORTANT: Check the box "Add Python to PATH" before clicking Install
5. Verify by opening terminal and typing:
   ```
   python --version
   ```

### Step 2 — Verify pip [MANUAL]
```
pip --version
```

### Step 3 — Requirements
- Working microphone (for voice input)
- Internet connection (for Groq AI, Google Speech, Gmail API)
- Gmail account (Google)
- Task Agent already set up (shares its credentials.json)

---

## PART 2 — FOLDER STRUCTURE

### Step 4 — Create These Folders [MANUAL]
```
projects_folder/
└── Agents/
    ├── task-reminder-agent/     ← must exist (shares credentials.json)
    │   └── credentials.json
    └── email-agent/
```

Inside `email-agent/` you will create these files in the steps below:
```
agent.py
requirements.txt
.env
run_agent.bat
SETUP_GUIDE.md
```

Auto-generated files (created on first run):
```
gmail_token.json         ← saved after first Gmail login
email_templates.json     ← saved when first template created
```

---

## PART 3 — GROQ API SETUP (Free AI Engine)

### Step 5 — Create Groq Account [MANUAL]
1. Go to: https://groq.com
2. Click "Start Building"
3. Sign up with your Google account
4. 100% free — no credit card needed

### Step 6 — Get Groq API Key [MANUAL]
1. Go to: https://console.groq.com/keys
2. Click "Create API Key"
3. Give it a name (example: dragoo-agent)
4. Copy the key — looks like: `gsk_xxxxxxxxxxxxxxxxxxxx`
5. Store it safely — shown only once

### Step 7 — Create .env File [MANUAL]
1. Inside `email-agent/` create a file named `.env`
2. Paste this inside:
   ```
   GROQ_API_KEY=paste_your_groq_key_here
   ```
3. Save the file

> IMPORTANT: Never share this key publicly or paste it in any chat
> You can reuse the same Groq key from the Task Agent

---

## PART 4 — GOOGLE GMAIL API SETUP

> If you already set up Google Cloud for the Task Agent, you can reuse the same
> project and credentials.json. Just enable Gmail API in the same project.

### Step 8 — Open Existing Google Cloud Project [MANUAL]
1. Go to: https://console.cloud.google.com
2. Select your existing project: `Task Agent` (or `task-agent-494218`)

### Step 9 — Enable Gmail API [MANUAL]
1. In the search bar type: `Gmail API`
2. Click on it
3. Click the blue "Enable" button

### Step 10 — Verify OAuth Consent Screen [MANUAL]
The consent screen was already configured for the Task Agent.
If starting fresh:
1. Go to: APIs & Services → OAuth consent screen
2. Select "External" → Click "Create"
3. Fill in:
   - App name: `Task Agent`
   - User support email: your Gmail
   - Developer contact email: your Gmail
4. Click "Save and Continue" three times

### Step 11 — Verify Test User [MANUAL]
1. Go to: APIs & Services → Audience
2. Scroll to "Test users"
3. Your Gmail should already be listed
4. If not, click "+ Add Users" and add your Gmail

### Step 12 — Credentials File [MANUAL]
The `credentials.json` file is **shared** from the Task Agent folder.
The email agent reads it from: `../task-reminder-agent/credentials.json`

No need to create a new one. The Task Agent's credentials.json works for both.

> Correct file starts with: `{"installed": ...}`
> Wrong file starts with: `{"web": ...}` — redo from Task Agent Step 12 if this happens

---

## PART 5 — INSTALL LIBRARIES

### Step 13 — Open Terminal in Email Agent Folder [MANUAL]
1. Open `email-agent/` in File Explorer
2. Click address bar → type `cmd` → press Enter

### Step 14 — Install All Libraries [MANUAL]
```
pip install groq python-dotenv google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client rich sounddevice scipy SpeechRecognition keyboard
```

---

## PART 6 — CREATE PROJECT FILES

---

### Step 15 — Create requirements.txt [AI GENERATED]

Create a file named `requirements.txt` and paste:

```
groq
python-dotenv
google-auth
google-auth-oauthlib
google-auth-httplib2
google-api-python-client
rich
sounddevice
scipy
SpeechRecognition
keyboard
```

---

### Step 16 — Create run_agent.bat [AI GENERATED]

Create a file named `run_agent.bat` and paste:

```bat
@echo off
title Dragoo Email Agent
cd /d "%~dp0"
python agent.py
pause
```

This allows you to double-click to launch the agent instead of using terminal.

---

### Step 17 — Create agent.py [AI GENERATED]

Create a file named `agent.py` and paste the full code below:

```python
import os
import json
import base64
import tempfile
import time
import threading
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from email.utils import parsedate_to_datetime
from dotenv import load_dotenv
from groq import Groq
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.align import Align
from rich.rule import Rule
import sounddevice as sd
import scipy.io.wavfile as wav
import speech_recognition as sr
import keyboard
import numpy as np

load_dotenv()

client     = Groq(api_key=os.environ.get("GROQ_API_KEY"))
SCOPES     = [
    "https://mail.google.com/",
]
CREDS_FILE      = os.path.join(os.path.dirname(__file__), "..", "task-reminder-agent", "credentials.json")
TOKEN_FILE      = os.path.join(os.path.dirname(__file__), "gmail_token.json")
TEMPLATES_FILE  = os.path.join(os.path.dirname(__file__), "email_templates.json")
console         = Console()
_refresh_lock   = threading.Lock()

BANNER = """
 ██████╗ ██████╗  █████╗  ██████╗  ██████╗  ██████╗     ███████╗███╗   ███╗ █████╗ ██╗██╗
 ██╔══██╗██╔══██╗██╔══██╗██╔════╝ ██╔═══██╗██╔═══██╗    ██╔════╝████╗ ████║██╔══██╗██║██║
 ██║  ██║██████╔╝███████║██║  ███╗██║   ██║██║   ██║    █████╗  ██╔████╔██║███████║██║██║
 ██║  ██║██╔══██╗██╔══██║██║   ██║██║   ██║██║   ██║    ██╔══╝  ██║╚██╔╝██║██╔══██║██║██║
 ██████╔╝██║  ██║██║  ██║╚██████╔╝╚██████╔╝╚██████╔╝    ███████╗██║ ╚═╝ ██║██║  ██║██║███████╗
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝  ╚═════╝    ╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝╚══════╝
"""

# ── Gmail Auth ─────────────────────────────────────────────────────────────────

def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=8081, open_browser=True)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

# ── Templates ──────────────────────────────────────────────────────────────────

def load_templates():
    if os.path.exists(TEMPLATES_FILE):
        with open(TEMPLATES_FILE, "r") as f:
            return json.load(f)
    return {}

def save_templates(templates):
    with open(TEMPLATES_FILE, "w") as f:
        json.dump(templates, f, indent=2)

# ── Email Helpers ──────────────────────────────────────────────────────────────

def format_date(raw_date):
    try:
        return parsedate_to_datetime(raw_date).strftime("%d %b  %H:%M")
    except Exception:
        return raw_date[:16] if raw_date else "—"

def has_attachments(payload):
    for part in payload.get("parts", []):
        mime = part.get("mimeType", "")
        if mime not in ("text/plain", "text/html", "multipart/alternative",
                        "multipart/related", "multipart/mixed") and part.get("filename"):
            return True
        if has_attachments(part):
            return True
    return False

def build_email_meta(service, msg):
    full    = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
    headers = {h["name"]: h["value"] for h in full["payload"]["headers"]}
    return {
        "id":        msg["id"],
        "thread_id": full.get("threadId", ""),
        "from":      headers.get("From", "Unknown"),
        "to":        headers.get("To", ""),
        "subject":   headers.get("Subject", "(No Subject)"),
        "date":      format_date(headers.get("Date", "")),
        "snippet":   full.get("snippet", ""),
        "labels":    full.get("labelIds", []),
        "attach":    has_attachments(full["payload"])
    }

def fetch_emails(service, label_ids=None, query=None, max_results=10, page_token=None):
    params = {"userId": "me", "maxResults": max_results}
    if label_ids:
        params["labelIds"] = label_ids
    if query:
        params["q"] = query
    if page_token:
        params["pageToken"] = page_token
    result   = service.users().messages().list(**params).execute()
    messages = result.get("messages", [])
    next_tok = result.get("nextPageToken")
    emails   = [build_email_meta(service, m) for m in messages]
    return emails, next_tok

def get_unread_count(service):
    result = service.users().messages().list(
        userId="me", labelIds=["INBOX", "UNREAD"], maxResults=1
    ).execute()
    return result.get("resultSizeEstimate", 0)

def get_email_body(service, msg_id):
    full = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    def extract(payload):
        mime = payload.get("mimeType", "")
        data = payload.get("body", {}).get("data")
        if mime == "text/plain" and data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        for part in payload.get("parts", []):
            r = extract(part)
            if r:
                return r
        if mime == "text/html" and data:
            html = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            return re.sub(r"<[^>]+>", " ", html).strip()
        return ""
    return extract(full["payload"])

def mark_as_read(service, msg_id):
    service.users().messages().modify(
        userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
    ).execute()

def archive_email(service, msg_id):
    service.users().messages().modify(
        userId="me", id=msg_id, body={"removeLabelIds": ["INBOX"]}
    ).execute()

def delete_email(service, msg_id):
    service.users().messages().trash(userId="me", id=msg_id).execute()

def empty_trash(service):
    result = service.users().messages().list(userId="me", labelIds=["TRASH"], maxResults=500).execute()
    messages = result.get("messages", [])
    for msg in messages:
        service.users().messages().delete(userId="me", id=msg["id"]).execute()
    return len(messages)

def send_email(service, to, subject, body, thread_id=None):
    message = MIMEMultipart()
    message["to"]      = to
    message["subject"] = subject
    message.attach(MIMEText(body, "plain"))
    raw          = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body_payload = {"raw": raw}
    if thread_id:
        body_payload["threadId"] = thread_id
    service.users().messages().send(userId="me", body=body_payload).execute()

def create_draft(service, to, subject, body):
    message = MIMEMultipart()
    message["to"]      = to
    message["subject"] = subject
    message.attach(MIMEText(body, "plain"))
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()

# ── AI ─────────────────────────────────────────────────────────────────────────

def understand(user_input):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": f"""You are an intelligent email assistant. Current time: {now}.

Your job is to understand what the user wants to do with their email — in ANY phrasing, casual or formal.
Think about the user's intent, not the exact words used.

Return ONLY a valid JSON object with these fields:
{{
  "action": one of [read, search, draft, summarize, reply, forward, archive, delete, empty_trash, load_more, template_save, template_use, template_list, unknown],
  "query": string — email number (as digit) for summarize/reply/forward/archive/delete, OR search term for search,
  "to": string — recipient email address for draft or forward,
  "subject": string — email subject for draft,
  "instruction": string — what the email or reply should say,
  "template_name": string — template name for save/use,
  "reply": string — only for unknown action, explain briefly what you can do
}}

How to determine intent:
- User wants to see emails / inbox / unread messages → "read"
- User wants more emails / next batch / see more → "load_more"
- User wants to find or look for specific emails by sender, keyword, topic → "search"
- User wants to read, open, understand, what does email N say, summarize, explain email N → "summarize", query = the number as a string
- User wants to write back, respond, answer email N → "reply", query = number
- User wants to pass along, send to someone else, forward email N → "forward", query = number
- User wants to remove from inbox, archive, clean up email N → "archive", query = number
- User wants to permanently remove, trash, get rid of email N → "delete", query = number
- User wants to empty trash, clear deleted emails, wipe trash bin → "empty_trash"
- User wants to compose, write, send a new email to someone → "draft"
- User wants to save a reusable email format → "template_save"
- User wants to use a saved format → "template_use"
- User wants to see their saved formats → "template_list"

Important:
- Numbers can be written as digits (1, 2), words (one, two), or ordinals (first, second, 1st, 2nd) — always convert to digit string
- Do not require exact command words — understand meaning from context
- If genuinely unclear, use "unknown" and explain in "reply" what you can help with
- Return ONLY the JSON. No markdown. No extra text."""
            },
            {"role": "user", "content": user_input}
        ]
    )
    raw = response.choices[0].message.content.strip().replace("```json","").replace("```","").strip()
    # Fix common AI JSON mistakes — trailing commas before } or ]
    raw = re.sub(r",\s*}", "}", raw)
    raw = re.sub(r",\s*]", "]", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"action": "unknown", "reply": "I had trouble understanding that. Could you rephrase?"}

def ai_write(prompt):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a professional email writer. Return ONLY the email body. No subject. No headers."},
            {"role": "user",   "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

def ai_summarize(body):
    if not body or len(body.strip()) < 20:
        return "• Email body could not be extracted (may be image-only or heavily formatted)."
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "Summarize this email in 3 bullet points. Be concise."},
            {"role": "user",   "content": body[:4000]}
        ]
    )
    return response.choices[0].message.content.strip()

# ── UI Helpers ─────────────────────────────────────────────────────────────────

def cyber_rule(label=""):
    console.print(Rule(f"[cyan dim]{label}[/cyan dim]", style="cyan dim"))

def show_email_list(emails, title="INBOX"):
    if not emails:
        console.print(Panel(Align.center("[cyan dim]◈ NO EMAILS FOUND ◈[/cyan dim]"),
                            border_style="cyan", box=box.DOUBLE_EDGE,
                            title=f"[bold cyan] {title} [/bold cyan]"))
        return
    table = Table(box=box.SIMPLE_HEAD, border_style="cyan", header_style="bold cyan",
                  show_lines=True, expand=True, padding=(0, 1))
    table.add_column("#",    style="cyan dim",   width=3,  justify="center")
    table.add_column("📎",   style="cyan",       width=3,  justify="center")
    table.add_column("DATE", style="cyan dim",   width=13, justify="center")
    table.add_column("FROM", style="bold white", ratio=2)
    table.add_column("SUBJECT", style="cyan",   ratio=3)
    table.add_column("PREVIEW", style="dim",    ratio=3)

    for i, e in enumerate(emails, 1):
        attach  = "📎" if e.get("attach") else ""
        sender  = e["from"].split("<")[0].strip()[:20]
        subject = e["subject"][:35]
        snippet = e["snippet"][:40] + "..." if len(e["snippet"]) > 40 else e["snippet"]
        table.add_row(str(i), attach, e["date"], sender, subject, snippet)

    console.print(Panel(table, title=f"[bold cyan] {title} [/bold cyan]",
                        border_style="cyan", box=box.DOUBLE_EDGE))
    console.print("[cyan dim]  ◈ summarize email 1  ·  reply to email 2  ·  forward email 3 to X  ·  archive/delete email N  ·  load more[/cyan dim]\n")

def show_email_preview(to, subject, body, title="PREVIEW"):
    content = Text()
    content.append("\n  ◈ TO       »  ", style="cyan dim"); content.append(f"{to}\n", style="bold white")
    content.append("  ◈ SUBJECT  »  ", style="cyan dim"); content.append(f"{subject}\n\n", style="bold cyan")
    content.append("  ◈ BODY     »\n\n", style="cyan dim"); content.append(f"{body}\n", style="white")
    console.print(Panel(content, title=f"[bold yellow]  {title} [/bold yellow]",
                        border_style="yellow", box=box.DOUBLE_EDGE, padding=(0, 2)))

def send_flow(service, to, subject, body, thread_id=None):
    console.print("[bold yellow]  ◈ Options: [green]send[/green] · [cyan]draft[/cyan] · [red]edit[/red] · [dim]cancel[/dim][/bold yellow]")
    while True:
        choice = console.input("[bold cyan]  ◈ DECISION  ►  [/bold cyan]").strip().lower()
        if choice == "send":
            with console.status("[cyan dim]  ◈ SENDING...[/cyan dim]", spinner="aesthetic"):
                send_email(service, to, subject, body, thread_id)
            console.print(Panel("[bold green]  ✓ EMAIL SENT[/bold green]", border_style="green", box=box.DOUBLE_EDGE))
            break
        elif choice == "draft":
            with console.status("[cyan dim]  ◈ SAVING DRAFT...[/cyan dim]", spinner="aesthetic"):
                create_draft(service, to, subject, body)
            console.print(Panel("[bold cyan]  ✓ SAVED TO GMAIL DRAFTS[/bold cyan]", border_style="cyan", box=box.DOUBLE_EDGE))
            break
        elif choice == "edit":
            edit_instr = console.input("[bold cyan]  ◈ DESCRIBE CHANGES  ►  [/bold cyan]").strip()
            if edit_instr:
                with console.status("[cyan dim]  ◈ REWRITING...[/cyan dim]", spinner="aesthetic"):
                    body = ai_write(f"Rewrite this email based on instruction: {edit_instr}\nOriginal: {body}")
                show_email_preview(to, subject, body, "UPDATED PREVIEW")
                console.print("[bold yellow]  ◈ Options: [green]send[/green] · [cyan]draft[/cyan] · [red]edit[/red] · [dim]cancel[/dim][/bold yellow]")
        elif choice == "cancel":
            console.print("[dim]  Cancelled.[/dim]")
            break
        else:
            console.print("[yellow]  ⚠ Type: send · draft · edit · cancel[/yellow]")

def get_active_emails(emails_cache):
    return emails_cache.get("inbox") or emails_cache.get("search") or []

def resolve_email(emails_cache, query):
    active = get_active_emails(emails_cache)
    if not active:
        return None, None, "No emails loaded. Say: check my inbox first."
    q = str(query).strip()
    if not q.isdigit() or not (1 <= int(q) <= len(active)):
        return None, None, f"{len(active)} emails loaded. Use a number from 1 to {len(active)}."
    return active[int(q) - 1], int(q), None

# ── Auto Refresh ───────────────────────────────────────────────────────────────

def start_auto_refresh(service, emails_cache, interval=300):
    def _refresh():
        while True:
            time.sleep(interval)
            try:
                with _refresh_lock:
                    count = get_unread_count(service)
                console.print(f"\n[bold magenta]  ◈ AUTO-REFRESH ►[/bold magenta] [cyan]{count} unread emails in inbox[/cyan]")
            except Exception:
                pass
    threading.Thread(target=_refresh, daemon=True).start()

# ── Actions ────────────────────────────────────────────────────────────────────

def run_action(parsed, service, emails_cache):
    action = parsed.get("action")

    # ── READ ──
    if action == "read":
        with console.status("[cyan dim]  ◈ FETCHING UNREAD EMAILS...[/cyan dim]", spinner="aesthetic"):
            emails, next_tok = fetch_emails(service, label_ids=["INBOX", "UNREAD"])
        emails_cache["inbox"]     = emails
        emails_cache["next_tok"]  = next_tok
        emails_cache["search"]    = []
        show_email_list(emails, "UNREAD INBOX")

    # ── LOAD MORE ──
    elif action == "load_more":
        tok = emails_cache.get("next_tok")
        if not tok:
            console.print(Panel("[yellow]  ⚠ No more emails to load.[/yellow]", border_style="yellow", box=box.DOUBLE_EDGE))
            return
        with console.status("[cyan dim]  ◈ LOADING MORE EMAILS...[/cyan dim]", spinner="aesthetic"):
            emails, next_tok = fetch_emails(service, label_ids=["INBOX", "UNREAD"], page_token=tok)
        existing = emails_cache.get("inbox", [])
        emails_cache["inbox"]    = existing + emails
        emails_cache["next_tok"] = next_tok
        show_email_list(emails_cache["inbox"], f"INBOX — {len(emails_cache['inbox'])} EMAILS")

    # ── SEARCH ──
    elif action == "search":
        query = parsed.get("query", "")
        if not query:
            console.print("[yellow]  ⚠ Say: find emails from John[/yellow]"); return
        with console.status(f"[cyan dim]  ◈ SEARCHING: {query}...[/cyan dim]", spinner="aesthetic"):
            emails, _ = fetch_emails(service, query=query)
        emails_cache["search"] = emails
        show_email_list(emails, f"SEARCH: {query.upper()}")

    # ── SUMMARIZE ──
    elif action == "summarize":
        email, idx, err = resolve_email(emails_cache, parsed.get("query"))
        if err:
            console.print(Panel(f"[yellow]  ⚠ {err}[/yellow]", border_style="yellow", box=box.DOUBLE_EDGE)); return
        with console.status(f"[cyan dim]  ◈ READING EMAIL {idx}...[/cyan dim]", spinner="aesthetic"):
            body    = get_email_body(service, email["id"])
            summary = ai_summarize(body)
            mark_as_read(service, email["id"])
        content = Text()
        content.append("\n  ◈ EMAIL #   »  ", style="cyan dim"); content.append(f"{idx}\n", style="bold white")
        content.append("  ◈ FROM      »  ", style="cyan dim"); content.append(f"{email['from']}\n", style="bold white")
        content.append("  ◈ DATE      »  ", style="cyan dim"); content.append(f"{email['date']}\n", style="cyan")
        content.append("  ◈ ATTACH    »  ", style="cyan dim"); content.append("Yes 📎\n" if email.get("attach") else "None\n", style="white")
        content.append("  ◈ SUBJECT   »  ", style="cyan dim"); content.append(f"{email['subject']}\n\n", style="bold cyan")
        content.append("  ◈ SUMMARY   »\n\n", style="cyan dim"); content.append(f"{summary}\n", style="white")
        console.print(Panel(content, title="[bold cyan]  EMAIL SUMMARY [/bold cyan]",
                            border_style="cyan", box=box.DOUBLE_EDGE, padding=(0, 2)))
        console.print(f"[cyan dim]  ◈ Marked as read. Say 'reply to email {idx}' or 'forward email {idx} to X@email.com'[/cyan dim]\n")

    # ── REPLY ──
    elif action == "reply":
        email, idx, err = resolve_email(emails_cache, parsed.get("query"))
        if err:
            console.print(Panel(f"[yellow]  ⚠ {err}[/yellow]", border_style="yellow", box=box.DOUBLE_EDGE)); return
        instruction = parsed.get("instruction", "")
        if not instruction:
            instruction = console.input("[bold cyan]  ◈ REPLY INSTRUCTION  ►  [/bold cyan]").strip()
        with console.status("[cyan dim]  ◈ DRAFTING REPLY...[/cyan dim]", spinner="aesthetic"):
            original = get_email_body(service, email["id"])
            body     = ai_write(f"Write a reply to this email from {email['from']}. Instruction: {instruction}\nOriginal:\n{original[:2000]}")
        to      = email["from"]
        subject = f"Re: {email['subject']}"
        show_email_preview(to, subject, body, "REPLY PREVIEW")
        send_flow(service, to, subject, body, thread_id=email.get("thread_id"))

    # ── FORWARD ──
    elif action == "forward":
        email, idx, err = resolve_email(emails_cache, parsed.get("query"))
        if err:
            console.print(Panel(f"[yellow]  ⚠ {err}[/yellow]", border_style="yellow", box=box.DOUBLE_EDGE)); return
        to = parsed.get("to", "")
        if not to:
            to = console.input("[bold cyan]  ◈ FORWARD TO (email address)  ►  [/bold cyan]").strip()
        with console.status("[cyan dim]  ◈ PREPARING FORWARD...[/cyan dim]", spinner="aesthetic"):
            original = get_email_body(service, email["id"])
            body     = f"---------- Forwarded message ----------\nFrom: {email['from']}\nDate: {email['date']}\nSubject: {email['subject']}\n\n{original}"
        subject = f"Fwd: {email['subject']}"
        show_email_preview(to, subject, body, "FORWARD PREVIEW")
        send_flow(service, to, subject, body)

    # ── ARCHIVE ──
    elif action == "archive":
        email, idx, err = resolve_email(emails_cache, parsed.get("query"))
        if err:
            console.print(Panel(f"[yellow]  ⚠ {err}[/yellow]", border_style="yellow", box=box.DOUBLE_EDGE)); return
        with console.status("[cyan dim]  ◈ ARCHIVING...[/cyan dim]", spinner="aesthetic"):
            archive_email(service, email["id"])
        active = get_active_emails(emails_cache)
        active.pop(idx - 1)
        console.print(Panel(f"[bold cyan]  ✓ EMAIL {idx} ARCHIVED[/bold cyan]", border_style="cyan", box=box.DOUBLE_EDGE))

    # ── DELETE ──
    elif action == "delete":
        email, idx, err = resolve_email(emails_cache, parsed.get("query"))
        if err:
            console.print(Panel(f"[yellow]  ⚠ {err}[/yellow]", border_style="yellow", box=box.DOUBLE_EDGE)); return
        console.print(f"[bold red]  ⚠ Move email {idx} to trash? Type [white]yes[/white] to confirm.[/bold red]")
        confirm = console.input("[bold cyan]  ◈ CONFIRM  ►  [/bold cyan]").strip().lower()
        if confirm == "yes":
            with console.status("[cyan dim]  ◈ DELETING...[/cyan dim]", spinner="aesthetic"):
                delete_email(service, email["id"])
            active = get_active_emails(emails_cache)
            active.pop(idx - 1)
            console.print(Panel(f"[bold red]  ✓ EMAIL {idx} MOVED TO TRASH[/bold red]", border_style="red", box=box.DOUBLE_EDGE))
        else:
            console.print("[dim]  Cancelled.[/dim]")

    # ── TEMPLATE SAVE ──
    elif action == "template_save":
        name = parsed.get("template_name", "")
        if not name:
            name = console.input("[bold cyan]  ◈ TEMPLATE NAME  ►  [/bold cyan]").strip()
        console.print("[bold cyan]  ◈ What should this template say? (describe the email)[/bold cyan]")
        instruction = console.input("[bold cyan]  ◈ TEMPLATE CONTENT  ►  [/bold cyan]").strip()
        templates = load_templates()
        templates[name] = {"instruction": instruction, "created": datetime.now().strftime("%Y-%m-%d %H:%M")}
        save_templates(templates)
        console.print(Panel(f"[bold green]  ✓ TEMPLATE '[white]{name}[/white]' SAVED[/bold green]",
                            border_style="green", box=box.DOUBLE_EDGE))

    # ── TEMPLATE USE ──
    elif action == "template_use":
        name = parsed.get("template_name", "")
        templates = load_templates()
        if name not in templates:
            console.print(Panel(f"[yellow]  ⚠ Template '{name}' not found. Say 'show templates' to see all.[/yellow]",
                                border_style="yellow", box=box.DOUBLE_EDGE)); return
        to = console.input("[bold cyan]  ◈ SEND TO (email address)  ►  [/bold cyan]").strip()
        subject = console.input("[bold cyan]  ◈ SUBJECT  ►  [/bold cyan]").strip()
        with console.status("[cyan dim]  ◈ GENERATING FROM TEMPLATE...[/cyan dim]", spinner="aesthetic"):
            body = ai_write(f"Write an email to {to} with subject '{subject}'. Instruction: {templates[name]['instruction']}")
        show_email_preview(to, subject, body, f"TEMPLATE: {name.upper()}")
        send_flow(service, to, subject, body)

    # ── TEMPLATE LIST ──
    elif action == "template_list":
        templates = load_templates()
        if not templates:
            console.print(Panel("[cyan dim]  ◈ No templates saved yet.\n  Say: save template as [name][/cyan dim]",
                                border_style="cyan", box=box.DOUBLE_EDGE)); return
        table = Table(box=box.SIMPLE_HEAD, border_style="cyan", header_style="bold cyan", expand=True)
        table.add_column("NAME",    style="bold white", ratio=2)
        table.add_column("CONTENT", style="cyan",       ratio=4)
        table.add_column("CREATED", style="dim",        width=16)
        for name, data in templates.items():
            table.add_row(name, data.get("instruction","")[:60], data.get("created",""))
        console.print(Panel(table, title="[bold cyan]  EMAIL TEMPLATES [/bold cyan]",
                            border_style="cyan", box=box.DOUBLE_EDGE))

    # ── EMPTY TRASH ──
    elif action == "empty_trash":
        console.print("[bold red]  ⚠ This will permanently delete ALL emails in trash. Type [white]yes[/white] to confirm.[/bold red]")
        confirm = console.input("[bold cyan]  ◈ CONFIRM  ►  [/bold cyan]").strip().lower()
        if confirm == "yes":
            with console.status("[cyan dim]  ◈ EMPTYING TRASH...[/cyan dim]", spinner="aesthetic"):
                count = empty_trash(service)
            console.print(Panel(f"[bold red]  ✓ TRASH EMPTIED — {count} EMAILS PERMANENTLY DELETED[/bold red]",
                                border_style="red", box=box.DOUBLE_EDGE))
        else:
            console.print("[dim]  Cancelled.[/dim]")

    # ── UNKNOWN ──
    else:
        reply = parsed.get("reply", "")
        content = Text()
        content.append("\n  ", style=""); content.append(f"{reply}\n\n" if reply else "I can help you with your emails.\n\n", style="white")
        content.append("  Here's what I can do:\n\n", style="cyan dim")
        examples = [
            ("Read emails",    "what's in my inbox? / any new mails?"),
            ("Summarize",      "what does the first email say? / open email 2"),
            ("Reply",          "write back to email 1 / respond to the second one"),
            ("Forward",        "forward email 3 to someone@email.com"),
            ("Compose",        "write an email to X about Y"),
            ("Search",         "any emails from John? / find invoice emails"),
            ("Manage",         "archive email 2 / delete email 3 / empty trash"),
            ("Templates",      "save this as a template / use my followup template"),
            ("Voice",          "type v and hold SPACE to speak"),
        ]
        for label, example in examples:
            content.append(f"  ◈ {label:<12}", style="bold cyan")
            content.append(f" — {example}\n", style="dim")
        console.print(Panel(content, title="[bold yellow]  I DIDN'T QUITE GET THAT [/bold yellow]",
                            border_style="yellow", box=box.DOUBLE_EDGE, padding=(0,2)))

# ── Voice Input ────────────────────────────────────────────────────────────────

SAMPLE_RATE = 16000

def record_until_release(key="space"):
    frames = []
    console.print(Panel(Align.center("[bold magenta]  ◈ LISTENING...  RELEASE [SPACE] TO STOP ◈  [/bold magenta]"),
                        border_style="magenta", box=box.DOUBLE_EDGE))
    def callback(indata, frame_count, time_info, status):
        frames.append(indata.copy())
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback):
        keyboard.wait(key, suppress=False)
        while keyboard.is_pressed(key):
            time.sleep(0.05)
    if not frames:
        return None
    audio_data = np.concatenate(frames, axis=0)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    wav.write(tmp.name, SAMPLE_RATE, audio_data)
    return tmp.name

def transcribe(wav_path):
    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_path) as source:
        audio = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        console.print(f"[red]  ✗ SPEECH ERROR: {e}[/red]")
        return None
    finally:
        os.unlink(wav_path)

def get_voice_input():
    console.print(Panel(Align.center("[bold cyan]  ◈ HOLD [SPACE] TO SPEAK  ◈  [/bold cyan]"),
                        border_style="cyan", box=box.DOUBLE_EDGE))
    keyboard.wait("space")
    wav_path = record_until_release("space")
    if not wav_path:
        console.print("[red]  ✗ No audio recorded.[/red]"); return None
    with console.status("[cyan dim]  ◈ TRANSCRIBING...[/cyan dim]", spinner="aesthetic"):
        text = transcribe(wav_path)
    if text:
        console.print(Panel(f"[bold white]  ◈ HEARD  ►  [/bold white][cyan]{text}[/cyan]",
                            border_style="cyan", box=box.DOUBLE_EDGE))
    else:
        console.print("[red]  ✗ Could not understand. Try again.[/red]")
    return text

# ── Boot ───────────────────────────────────────────────────────────────────────

def main():
    console.clear()
    console.print(Align.center(f"[bold cyan]{BANNER}[/bold cyan]"))
    console.print(Align.center("[dim cyan]◈  DRAGOO EMAIL MANAGEMENT SYSTEM  ◈[/dim cyan]"))
    console.print(Align.center(f"[dim]v2.0  •  {datetime.now().strftime('%Y-%m-%d %H:%M')}  •  GROQ AI ENGINE[/dim]"))
    console.print()
    cyber_rule("SYSTEM BOOT")
    console.print()

    with console.status("[cyan]  CONNECTING TO GMAIL...[/cyan]", spinner="aesthetic"):
        try:
            service = get_gmail_service()
            count   = get_unread_count(service)
            gmail_status = f"[bold green]  ✓ GMAIL            ──  ONLINE  ──  {count} UNREAD[/bold green]"
        except Exception as e:
            console.print(f"[red]  ✗ Gmail Error: {e}[/red]"); return

    with console.status("[cyan]  LOADING AI ENGINE...[/cyan]", spinner="aesthetic"):
        time.sleep(0.3)

    console.print(gmail_status)
    console.print("[bold green]  ✓ GROQ AI ENGINE   ──  ONLINE[/bold green]")
    console.print("[bold green]  ✓ VOICE INPUT      ──  READY (Hold SPACE)[/bold green]")
    console.print("[bold green]  ✓ AUTO-REFRESH     ──  EVERY 5 MINUTES[/bold green]")
    console.print()
    cyber_rule("COMMAND INTERFACE")
    console.print()

    hints = Table.grid(padding=(0, 3))
    hints.add_column(style="cyan dim", width=3)
    hints.add_column(style="white")
    hints.add_row("◈", "check my inbox  ·  load more")
    hints.add_row("◈", "find emails from John  ·  search invoice")
    hints.add_row("◈", "summarize email 1  ·  reply to email 2")
    hints.add_row("◈", "forward email 3 to name@email.com")
    hints.add_row("◈", "archive email 2  ·  delete email 3")
    hints.add_row("◈", "save template as followup  ·  use template followup  ·  show templates")
    hints.add_row("◈", "write email to name@email.com about [topic]")
    hints.add_row("◈", "type [bold cyan]v[/bold cyan] for VOICE  |  [bold cyan]quit[/bold cyan] to exit")
    console.print(Panel(hints, title="[cyan dim] COMMAND REFERENCE [/cyan dim]",
                        border_style="cyan dim", box=box.SIMPLE_HEAD))
    console.print()

    emails_cache = {}
    start_auto_refresh(service, emails_cache, interval=300)

    while True:
        try:
            user_input = console.input("[bold cyan]  ◈ INPUT  ►  [/bold cyan]").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                console.print()
                cyber_rule("SHUTDOWN")
                console.print(Align.center("\n[bold cyan]  ◈ SYSTEM OFFLINE — GOODBYE ◈  [/bold cyan]\n"))
                break
            if user_input.lower() in ("v", "voice"):
                voice_text = get_voice_input()
                if not voice_text:
                    continue
                user_input = voice_text
            console.print()
            with console.status("[cyan dim]  ◈ PROCESSING...[/cyan dim]", spinner="aesthetic"):
                parsed = understand(user_input)
            run_action(parsed, service, emails_cache)
            console.print()
        except Exception as e:
            console.print(f"[bold red]  ✗ SYSTEM ERROR: {e}[/bold red]")

if __name__ == "__main__":
    main()
```

---

## PART 7 — CREATING SHORTCUTS

### Step 18 — Desktop Shortcut [MANUAL]
1. Right-click `run_agent.bat`
2. Click "Send to" → "Desktop (create shortcut)"
3. Rename it to: `Dragoo Email Agent`

### Step 19 — Folder Shortcut [MANUAL]
Same as above but keep the shortcut inside the `email-agent/` folder.

---

## PART 8 — FIRST RUN

### Step 20 — Launch for the First Time [MANUAL]
1. Double-click "Dragoo Email Agent" shortcut
2. A browser window opens automatically
3. Sign in with your Google account
4. Click "Allow" to grant Gmail access
5. Browser shows "Authentication successful"
6. Go back to terminal — agent is running and shows unread count

> Google login happens only once. Saves a `gmail_token.json` file after that.
> If you see a scope error, delete `gmail_token.json` and restart to re-authenticate.

---

## PART 9 — USING THE AGENT

### Step 21 — Email Commands
Type naturally and press Enter:
```
check my inbox
what's new in my mail
load more
find emails from John
search for invoice
summarize email 1
what does the second email say
reply to email 1
write back to email 2 saying thank you
forward email 3 to someone@gmail.com
archive email 2
delete email 1
empty trash
write an email to name@gmail.com about the project update
save template as followup
use template followup
show my templates
quit
```

### Step 22 — Voice Commands
1. Type `v` → press Enter
2. Hold `Spacebar` and speak
3. Release Spacebar
4. Agent transcribes and processes

### Step 23 — Send Flow
After composing any email, you get three choices:
- `send` — sends immediately
- `draft` — saves to Gmail Drafts
- `edit` — describe changes and AI rewrites

---

## PART 10 — HOW IT WORKS BEHIND THE SCENES

### Step 24 — Full Request Flow
```
You type or speak
        ↓
Text sent to Groq AI (llama-3.1-8b-instant model — free)
        ↓
Groq returns JSON: { action, query, to, subject, instruction }
        ↓
Agent reads JSON and calls Gmail API
        ↓
Gmail API fetches/sends/archives/deletes
        ↓
Result shown in terminal with futuristic UI
        ↓
Auto-refresh checks unread count every 5 minutes in background
```

---

## TROUBLESHOOTING

| Problem | Solution |
|---|---|
| Agent not starting | Check Python is installed and in PATH |
| Groq API error | Check .env file has correct GROQ_API_KEY |
| Gmail not connecting | Delete gmail_token.json and restart to re-authenticate |
| 403 Permission error | Delete gmail_token.json, ensure scope is `https://mail.google.com/` |
| Voice not working | Check microphone is connected and not muted |
| Module not found | Run: pip install -r requirements.txt |
| credentials.json error | File must say "installed" not "web" at start |
| Empty email body | Email may be image-only or have no text content |
| "Web" credentials error | Recreate OAuth as "Desktop app" in Google Cloud Console |

---

## KEY DECISIONS

| Decision | Choice | Reason |
|---|---|---|
| AI Engine | Groq API | Free, no credit card, fast |
| AI Model | llama-3.1-8b-instant | Active free model |
| Email API | Gmail API (full scope) | User already has Gmail |
| OAuth Port | 8081 | Avoids conflict with Task Agent (8080) |
| Token File | gmail_token.json | Separate from Task Agent's token.json |
| Credentials | Shared from Task Agent | Same Google Cloud project |
| UI Style | Rich Terminal | Consistent with Task Agent |
| Theme | Futuristic Cyan | User preference |
| Voice Input | Google Speech + Push-to-Talk | Free + no false triggers |

---

## FILES SUMMARY

| File | Created By | Purpose |
|---|---|---|
| agent.py | AI Generated | Full agent code |
| requirements.txt | AI Generated | Python libraries list |
| .env | User — Manual | Stores Groq API key |
| ../task-reminder-agent/credentials.json | Shared from Task Agent | Google OAuth credentials |
| gmail_token.json | Auto-generated on first run | Saves Gmail login session |
| email_templates.json | Auto-generated on first template | Stores email templates |
| run_agent.bat | AI Generated | Double-click launcher |
| Dragoo Email Agent.lnk | AI Generated | Desktop/folder shortcut |

---

*Built with Claude Code AI — Dragoo Email Agent v2.0*
*Guide created: 2026-04-24*
