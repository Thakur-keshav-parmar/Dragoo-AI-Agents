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
CONTACTS_FILE   = os.path.join(os.path.dirname(__file__), "email_contacts.json")
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

# ── Contacts ──────────────────────────────────────────────────────────────────

def load_contacts():
    if os.path.exists(CONTACTS_FILE):
        with open(CONTACTS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_contacts(contacts):
    with open(CONTACTS_FILE, "w") as f:
        json.dump(contacts, f, indent=2)

def resolve_contact(name_or_email):
    """
    Returns (resolved_email, display_name).
    If input is already an email → returns as-is.
    If it's a name → looks up contacts, handles fuzzy match and duplicates.
    If not found → returns (None, None).
    """
    raw = name_or_email.strip()
    if not raw:
        return None, None

    # Already a real email address
    if "@" in raw and "." in raw.split("@")[-1]:
        return raw, raw

    contacts = load_contacts()
    query    = raw.lower()

    # Pass 1: exact key or exact name match
    for key, data in contacts.items():
        if query == key.lower() or query == data.get("name", "").lower():
            return data["email"], data.get("name", key)

    # Pass 2: substring match (both directions — handles "my gf" → "gf", "send to ankit" → "ankit")
    matches = []
    for key, data in contacts.items():
        name    = data.get("name", key)
        key_l   = key.lower()
        name_l  = name.lower()
        if (query in key_l or query in name_l or
                key_l in query or name_l in query):
            matches.append((key, name, data["email"]))

    if not matches:
        return None, None

    if len(matches) == 1:
        return matches[0][2], matches[0][1]

    # Multiple matches — show list and ask
    console.print(Panel(
        f"[yellow]  Multiple contacts match \"[bold]{raw}[/bold]\" — pick one:[/yellow]",
        border_style="yellow", box=box.DOUBLE_EDGE
    ))
    for i, (_, name, email) in enumerate(matches, 1):
        console.print(f"  [cyan]{i}.[/cyan] [bold white]{name}[/bold white]  —  [dim]{email}[/dim]")
    choice = console.input("[bold cyan]  ◈ CHOOSE NUMBER  ►  [/bold cyan]").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(matches):
            return matches[idx][2], matches[idx][1]
    except ValueError:
        pass
    return None, None

def show_contacts():
    contacts = load_contacts()
    if not contacts:
        console.print(Panel(
            "[cyan dim]  No contacts saved yet.\n"
            "  Say: save Ankit as ankithakur@gmail.com[/cyan dim]",
            border_style="cyan", box=box.DOUBLE_EDGE
        ))
        return
    table = Table(
        title="[bold cyan]  SAVED CONTACTS  [/bold cyan]",
        border_style="cyan", box=box.DOUBLE_EDGE,
        show_header=True, header_style="bold cyan"
    )
    table.add_column("#",     style="cyan dim", width=4,  justify="center")
    table.add_column("Name",  style="bold white", min_width=20)
    table.add_column("Email", style="cyan",       min_width=28)
    for i, (key, data) in enumerate(contacts.items(), 1):
        table.add_row(str(i), data.get("name", key), data["email"])
    console.print(table)

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
    service.users().messages().list(userId="me", labelIds=["TRASH"], maxResults=500
    ).execute()
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
  "action": one of [read, search, draft, summarize, reply, forward, archive, delete, empty_trash, load_more, template_save, template_use, template_list, contact_add, contact_list, contact_delete, unknown],
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
- User wants to save/add a contact, remember someone's email → "contact_add", to = person's name, instruction = their email address
- User wants to see/list saved contacts → "contact_list"
- User wants to remove/delete a contact → "contact_delete", query = contact name

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
        raw_to = parsed.get("to", "").strip()
        if not raw_to:
            raw_to = console.input("[bold cyan]  ◈ FORWARD TO (name or email)  ►  [/bold cyan]").strip()
        to, display_name = resolve_contact(raw_to)
        if not to:
            console.print(Panel(f"[yellow]  Contact \"{raw_to}\" not found.[/yellow]",
                                border_style="yellow", box=box.DOUBLE_EDGE))
            to = console.input("[bold cyan]  ◈ ENTER FULL EMAIL ADDRESS  ►  [/bold cyan]").strip()
        else:
            console.print(Panel(
                f"[bold white]  Forwarding to [cyan]{display_name}[/cyan]  —  [dim]{to}[/dim][/bold white]",
                border_style="cyan dim", box=box.SIMPLE_HEAD
            ))
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

    # ── DRAFT / COMPOSE ──
    elif action == "draft":
        raw_to = parsed.get("to", "").strip()
        if not raw_to:
            raw_to = console.input("[bold cyan]  ◈ TO (name or email)  ►  [/bold cyan]").strip()
        to, display_name = resolve_contact(raw_to)
        if not to:
            # not in contacts and not an email — ask for full address
            console.print(Panel(
                f"[yellow]  Contact \"[bold]{raw_to}[/bold]\" not found in saved contacts.[/yellow]",
                border_style="yellow", box=box.DOUBLE_EDGE
            ))
            to = console.input("[bold cyan]  ◈ ENTER FULL EMAIL ADDRESS  ►  [/bold cyan]").strip()
            display_name = to
            # offer to save
            save_q = console.input(f"[bold cyan]  ◈ Save [white]{raw_to}[/white] as contact? (yes/no)  ►  [/bold cyan]").strip().lower()
            if save_q == "yes":
                contacts = load_contacts()
                contacts[raw_to.lower()] = {"name": raw_to, "email": to}
                save_contacts(contacts)
                console.print(Panel(f"[bold green]  ✓ CONTACT SAVED — {raw_to} → {to}[/bold green]",
                                    border_style="green", box=box.DOUBLE_EDGE))
        else:
            console.print(Panel(
                f"[bold white]  Sending to [cyan]{display_name}[/cyan]  —  [dim]{to}[/dim][/bold white]",
                border_style="cyan dim", box=box.SIMPLE_HEAD
            ))
        subject = parsed.get("subject", "").strip()
        if not subject:
            subject = console.input("[bold cyan]  ◈ SUBJECT  ►  [/bold cyan]").strip()
        instruction = parsed.get("instruction", "").strip()
        if not instruction:
            instruction = console.input("[bold cyan]  ◈ WHAT SHOULD THE EMAIL SAY?  ►  [/bold cyan]").strip()
        with console.status("[cyan dim]  ◈ COMPOSING EMAIL...[/cyan dim]", spinner="aesthetic"):
            body = ai_write(f"Write a professional email to {display_name} with subject '{subject}'. Content: {instruction}")
        show_email_preview(to, subject, body, "COMPOSE PREVIEW")
        send_flow(service, to, subject, body)

    # ── CONTACT ADD ──
    elif action == "contact_add":
        name  = parsed.get("to", "").strip()
        email = parsed.get("instruction", "").strip()
        if not name:
            name  = console.input("[bold cyan]  ◈ CONTACT NAME  ►  [/bold cyan]").strip()
        if not email or "@" not in email:
            email = console.input(f"[bold cyan]  ◈ EMAIL ADDRESS FOR {name.upper()}  ►  [/bold cyan]").strip()
        contacts = load_contacts()
        key = name.lower()
        if key in contacts:
            console.print(Panel(
                f"[yellow]  Contact \"[bold]{name}[/bold]\" already exists → [dim]{contacts[key]['email']}[/dim]\n"
                f"  Overwrite? (yes/no)[/yellow]",
                border_style="yellow", box=box.DOUBLE_EDGE
            ))
            if console.input("[bold cyan]  ◈  ►  [/bold cyan]").strip().lower() != "yes":
                console.print("[dim]  Cancelled.[/dim]"); return
        contacts[key] = {"name": name, "email": email}
        save_contacts(contacts)
        console.print(Panel(
            f"[bold green]  ✓ CONTACT SAVED\n"
            f"  [white]{name}[/white]  →  [cyan]{email}[/cyan][/bold green]",
            border_style="green", box=box.DOUBLE_EDGE
        ))

    # ── CONTACT LIST ──
    elif action == "contact_list":
        show_contacts()

    # ── CONTACT DELETE ──
    elif action == "contact_delete":
        name  = parsed.get("query", "").strip()
        if not name:
            name = console.input("[bold cyan]  ◈ WHICH CONTACT TO REMOVE?  ►  [/bold cyan]").strip()
        contacts = load_contacts()
        key      = name.lower()
        # try exact then fuzzy
        match_key = None
        if key in contacts:
            match_key = key
        else:
            for k in contacts:
                if key in k or key in contacts[k].get("name", "").lower():
                    match_key = k
                    break
        if not match_key:
            console.print(Panel(f"[yellow]  Contact \"{name}\" not found.[/yellow]",
                                border_style="yellow", box=box.DOUBLE_EDGE))
            return
        removed = contacts.pop(match_key)
        save_contacts(contacts)
        console.print(Panel(
            f"[bold red]  ✓ REMOVED  —  {removed['name']}  ({removed['email']})[/bold red]",
            border_style="red", box=box.DOUBLE_EDGE
        ))

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
    hints.add_row("◈", "save Ankit as ankit@gmail.com  ·  show contacts  ·  remove Ankit")
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
