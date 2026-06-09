import os
import re
import json
import time
import subprocess
import requests
from groq import Groq
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

load_dotenv()
client  = Groq(api_key=os.environ.get("GROQ_API_KEY"))
console = Console()

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
BRIDGE_DIR    = os.path.join(BASE_DIR, "bridge")
CONTACTS_FILE = os.path.join(BASE_DIR, "whatsapp_contacts.json")
BRIDGE_URL    = "http://localhost:3001"

_bridge_proc = None

# ── Bridge Control ─────────────────────────────────────────────────────────────

def start_bridge():
    global _bridge_proc
    # If already running, skip
    try:
        r = requests.get(f"{BRIDGE_URL}/status", timeout=2)
        if r.status_code == 200:
            return True
    except Exception:
        pass
    # Start Node.js bridge in a new terminal window
    try:
        _bridge_proc = subprocess.Popen(
            ["node", "index.js"],
            cwd=BRIDGE_DIR,
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
        return True
    except FileNotFoundError:
        return False  # Node.js not installed

def stop_bridge():
    global _bridge_proc
    if _bridge_proc:
        try:
            _bridge_proc.terminate()
        except Exception:
            pass
        _bridge_proc = None

def get_status():
    try:
        r = requests.get(f"{BRIDGE_URL}/status", timeout=3)
        return r.json()
    except Exception:
        return {"connected": False}

def send_whatsapp(phone, message):
    try:
        r = requests.post(
            f"{BRIDGE_URL}/send",
            json={"phone": phone, "message": message},
            timeout=20
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# ── Contacts ───────────────────────────────────────────────────────────────────

def load_contacts():
    if os.path.exists(CONTACTS_FILE):
        with open(CONTACTS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_contacts(contacts):
    with open(CONTACTS_FILE, "w") as f:
        json.dump(contacts, f, indent=2)

def normalize_phone(phone):
    p = re.sub(r"[^\d]", "", phone)
    if len(p) == 10:
        return f"91{p}"
    if len(p) == 11 and p.startswith("0"):
        return f"91{p[1:]}"
    if len(p) == 12 and p.startswith("91"):
        return p
    if len(p) == 13 and p.startswith("091"):
        return p[1:]
    return p

def resolve_contact(name_or_phone):
    raw = name_or_phone.strip()
    if not raw:
        return None, None

    # Already a phone number
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 10:
        return normalize_phone(raw), raw

    contacts = load_contacts()
    query    = raw.lower()

    # Exact match first
    for key, data in contacts.items():
        if query == key.lower() or query == data.get("name", "").lower():
            return data["phone"], data.get("name", key)

    # Substring match — both directions (handles "my gf" → "gf")
    matches = []
    for key, data in contacts.items():
        name  = data.get("name", key)
        key_l = key.lower()
        nam_l = name.lower()
        if (query in key_l or query in nam_l or
                key_l in query or nam_l in query):
            matches.append((key, name, data["phone"]))

    if not matches:
        return None, None
    if len(matches) == 1:
        return matches[0][2], matches[0][1]

    # Multiple matches — ask user to pick
    console.print(Panel(
        f"[yellow]  Multiple contacts match \"[bold]{raw}[/bold]\" — pick one:[/yellow]",
        border_style="yellow", box=box.DOUBLE_EDGE
    ))
    for i, (_, name, phone) in enumerate(matches, 1):
        console.print(f"  [green]{i}.[/green] [bold white]{name}[/bold white]  —  [dim]{phone}[/dim]")
    choice = console.input("[bold green]  ◈ CHOOSE NUMBER  ►  [/bold green]").strip()
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
            "[green dim]  No WhatsApp contacts saved yet.\n"
            "  Say: save gf WhatsApp as 9876543210[/green dim]",
            border_style="green", box=box.DOUBLE_EDGE
        ))
        return
    t = Table(
        title="[bold green]  WHATSAPP CONTACTS  [/bold green]",
        border_style="green", box=box.DOUBLE_EDGE,
        show_header=True, header_style="bold green"
    )
    t.add_column("#",     style="green dim", width=4, justify="center")
    t.add_column("Name",  style="bold white", min_width=20)
    t.add_column("Phone", style="green",      min_width=16)
    for i, (_, data) in enumerate(contacts.items(), 1):
        t.add_row(str(i), data.get("name", ""), data["phone"])
    console.print(t)

# ── NLU ────────────────────────────────────────────────────────────────────────

def understand(text):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": """You parse WhatsApp message requests. Return ONLY valid JSON (no markdown):
{
  "action":  "send" | "contact_add" | "contact_list" | "contact_delete" | "status",
  "to":      "<contact name or nickname — null if not applicable>",
  "message": "<exact message text to send — null if not sending>",
  "phone":   "<phone number if user mentioned one — null otherwise>",
  "reply":   "<one short sentence confirming what you will do>"
}

Rules:
- Send/WhatsApp/message to someone → send, fill to + message
- Save/add/remember someone's WhatsApp number → contact_add, fill to (name) + phone
- Show/list/see contacts → contact_list
- Remove/delete contact → contact_delete, fill to
- Status/connection/check → status
- message: write EXACTLY what should be sent as the WhatsApp message
- ONLY JSON, nothing else."""
            },
            {"role": "user", "content": text}
        ]
    )
    raw = response.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
    raw = re.sub(r",\s*}", "}", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"action": "send", "to": None, "message": None,
                "phone": None, "reply": "Let me help with that WhatsApp message."}

# ── Run Action ─────────────────────────────────────────────────────────────────

def run_action(parsed):
    action  = parsed.get("action", "send")
    to      = parsed.get("to")
    message = parsed.get("message")
    phone   = parsed.get("phone")
    reply   = parsed.get("reply", "")

    if reply:
        console.print(Panel(
            f"[green dim]  {reply}[/green dim]",
            border_style="green dim", box=box.SIMPLE_HEAD
        ))

    # ── SEND ──────────────────────────────────────────────────────────────────
    if action == "send":
        raw_to = (to or "").strip()
        if not raw_to:
            raw_to = console.input("[bold green]  ◈ SEND TO (name or number)  ►  [/bold green]").strip()

        phone_resolved, display_name = resolve_contact(raw_to)

        if not phone_resolved:
            console.print(Panel(
                f"[yellow]  \"[bold]{raw_to}[/bold]\" not found in WhatsApp contacts.[/yellow]",
                border_style="yellow", box=box.DOUBLE_EDGE
            ))
            phone_resolved = normalize_phone(
                console.input("[bold green]  ◈ ENTER PHONE NUMBER  ►  [/bold green]").strip()
            )
            display_name = raw_to
            save_q = console.input(
                f"[bold green]  ◈ Save [white]{raw_to}[/white] as contact? (yes/no)  ►  [/bold green]"
            ).strip().lower()
            if save_q == "yes":
                contacts = load_contacts()
                contacts[raw_to.lower()] = {"name": raw_to, "phone": phone_resolved}
                save_contacts(contacts)
                console.print(Panel(
                    f"[bold green]  ✓ SAVED — {raw_to} → {phone_resolved}[/bold green]",
                    border_style="green", box=box.DOUBLE_EDGE
                ))
        else:
            console.print(Panel(
                f"[bold white]  To  [green]{display_name}[/green]  [dim]({phone_resolved})[/dim][/bold white]",
                border_style="green dim", box=box.SIMPLE_HEAD
            ))

        if not message:
            message = console.input("[bold green]  ◈ MESSAGE  ►  [/bold green]").strip()

        # Preview
        console.print(Panel(
            f"[bold white]  To       [green]{display_name}[/green]  [dim]{phone_resolved}[/dim]\n"
            f"  Message  [white]{message}[/white][/bold white]",
            title="[bold green]  WHATSAPP PREVIEW  [/bold green]",
            border_style="green", box=box.DOUBLE_EDGE
        ))
        confirm = console.input("[bold green]  ◈ Send? (yes / no)  ►  [/bold green]").strip().lower()
        if confirm != "yes":
            console.print("[dim]  Cancelled.[/dim]")
            return "cancelled"

        # Check connection
        status = get_status()
        if not status.get("connected"):
            console.print(Panel(
                "[red]  ✗ WhatsApp not connected.\n"
                "  Check the WhatsApp Bridge window — scan the QR code first.[/red]",
                border_style="red", box=box.DOUBLE_EDGE
            ))
            return "not connected"

        with console.status("[green dim]  ◈ SENDING...[/green dim]", spinner="aesthetic"):
            result = send_whatsapp(phone_resolved, message)

        if result.get("success"):
            console.print(Panel(
                f"[bold green]  ✓ MESSAGE SENT TO {display_name.upper()}[/bold green]",
                border_style="green", box=box.DOUBLE_EDGE
            ))
            return f"sent to {display_name}"
        else:
            console.print(Panel(
                f"[red]  ✗ FAILED — {result.get('error', 'Unknown error')}[/red]",
                border_style="red", box=box.DOUBLE_EDGE
            ))
            return "failed"

    # ── CONTACT ADD ───────────────────────────────────────────────────────────
    elif action == "contact_add":
        name = (to or "").strip()
        num  = (phone or "").strip()
        if not name:
            name = console.input("[bold green]  ◈ CONTACT NAME  ►  [/bold green]").strip()
        if not num:
            num  = console.input(f"[bold green]  ◈ PHONE NUMBER FOR {name.upper()}  ►  [/bold green]").strip()
        num      = normalize_phone(num)
        contacts = load_contacts()
        key      = name.lower()
        if key in contacts:
            console.print(Panel(
                f"[yellow]  Already saved: {contacts[key]['name']} → {contacts[key]['phone']}\n"
                f"  Overwrite? (yes/no)[/yellow]",
                border_style="yellow", box=box.DOUBLE_EDGE
            ))
            if console.input("[bold green]  ◈  ►  [/bold green]").strip().lower() != "yes":
                console.print("[dim]  Cancelled.[/dim]")
                return "cancelled"
        contacts[key] = {"name": name, "phone": num}
        save_contacts(contacts)
        console.print(Panel(
            f"[bold green]  ✓ CONTACT SAVED\n  [white]{name}[/white]  →  [green]{num}[/green][/bold green]",
            border_style="green", box=box.DOUBLE_EDGE
        ))
        return f"saved {name}"

    # ── CONTACT LIST ──────────────────────────────────────────────────────────
    elif action == "contact_list":
        show_contacts()
        return "done"

    # ── CONTACT DELETE ────────────────────────────────────────────────────────
    elif action == "contact_delete":
        name = (to or "").strip()
        if not name:
            name = console.input("[bold green]  ◈ WHICH CONTACT TO REMOVE?  ►  [/bold green]").strip()
        contacts  = load_contacts()
        match_key = None
        key       = name.lower()
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
            return "not found"
        removed = contacts.pop(match_key)
        save_contacts(contacts)
        console.print(Panel(
            f"[bold red]  ✓ REMOVED — {removed['name']} ({removed['phone']})[/bold red]",
            border_style="red", box=box.DOUBLE_EDGE
        ))
        return "removed"

    # ── STATUS ────────────────────────────────────────────────────────────────
    elif action == "status":
        status = get_status()
        if status.get("connected"):
            idle      = status.get("idle_minutes", 0)
            remaining = status.get("remaining_minutes", 360)
            console.print(Panel(
                f"[bold white]  WhatsApp       [green]CONNECTED ✓[/green]\n"
                f"  Idle for       [yellow]{idle} min[/yellow]\n"
                f"  Auto-off in    [cyan]{remaining} min[/cyan][/bold white]",
                title="[bold green]  WHATSAPP STATUS  [/bold green]",
                border_style="green", box=box.DOUBLE_EDGE
            ))
        else:
            console.print(Panel(
                "[red]  WhatsApp  DISCONNECTED ✗\n"
                "  Check the Bridge window and scan the QR code.[/red]",
                border_style="red", box=box.DOUBLE_EDGE
            ))
        return "done"

    return "done"
