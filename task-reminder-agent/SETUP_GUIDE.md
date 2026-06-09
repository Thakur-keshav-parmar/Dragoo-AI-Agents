# Dragoo Task Agent — Complete Setup Guide

> This document covers every step taken to build this agent from scratch.
> Anyone can follow this guide to recreate it manually.
> Items marked [AI GENERATED] were built automatically by Claude AI.
> Items marked [MANUAL] require you to do them yourself.

---

## What This Agent Does

- Add tasks using natural language or voice
- Set reminders with countdown timers or specific times
- Auto-sync tasks to Google Calendar
- Desktop popup notifications
- Futuristic terminal UI with colors and animations

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
- Internet connection (for Groq AI, Google Speech, Google Calendar)

---

## PART 2 — FOLDER STRUCTURE

### Step 4 — Create These Folders [MANUAL]
```
projects_folder/
└── Agents/
    └── task-reminder-agent/
```

Inside `task-reminder-agent/` you will create these files in the steps below:
```
agent.py
requirements.txt
.env
credentials.json        ← downloaded from Google Cloud
run_agent.bat
SETUP_GUIDE.md
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
1. Inside `task-reminder-agent/` create a file named `.env`
2. Paste this inside:
   ```
   GROQ_API_KEY=paste_your_groq_key_here
   ```
3. Save the file

> IMPORTANT: Never share this key publicly or paste it in any chat

---

## PART 4 — GOOGLE CALENDAR SETUP

### Step 8 — Create Google Cloud Project [MANUAL]
1. Go to: https://console.cloud.google.com
2. Sign in with your Google account
3. Click "Select a project" at the top left
4. Click "New Project"
5. Name: `Task Agent`
6. Click "Create"
7. Make sure the project is selected at the top

### Step 9 — Enable Google Calendar API [MANUAL]
1. In the search bar type: `Google Calendar API`
2. Click on it
3. Click the blue "Enable" button

### Step 10 — Configure OAuth Consent Screen [MANUAL]
1. Go to: APIs & Services → OAuth consent screen
2. Select "External" → Click "Create"
3. Fill in:
   - App name: `Task Agent`
   - User support email: your Gmail
   - Developer contact email: your Gmail
4. Click "Save and Continue" three times
5. Click "Back to Dashboard"

### Step 11 — Add Yourself as Test User [MANUAL]
1. Go to: APIs & Services → Audience
2. Scroll to "Test users"
3. Click "+ Add Users"
4. Enter your Gmail address
5. Click "Save"

### Step 12 — Create OAuth Credentials [MANUAL]
1. Go to: APIs & Services → Credentials
2. Click "+ Create Credentials" → "OAuth client ID"
3. Application type: "Desktop app" (NOT Web application)
4. Name: `Task Agent Desktop`
5. Click "Create"
6. Click "Download JSON"
7. Rename downloaded file to: `credentials.json`
8. Place it inside `task-reminder-agent/` folder

> Correct file starts with: `{"installed": ...}`
> Wrong file starts with: `{"web": ...}` — redo if this happens

---

## PART 5 — INSTALL LIBRARIES

### Step 13 — Open Terminal in Project Folder [MANUAL]
1. Open `task-reminder-agent/` in File Explorer
2. Click address bar → type `cmd` → press Enter

### Step 14 — Install All Libraries [MANUAL]
```
pip install groq python-dotenv plyer schedule google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client rich sounddevice scipy SpeechRecognition keyboard
```

---

## PART 6 — CREATE PROJECT FILES

---

### Step 15 — Create requirements.txt [AI GENERATED]

Create a file named `requirements.txt` and paste:

```
groq
python-dotenv
plyer
schedule
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
title Dragoo Task Agent
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
import schedule
import time
import threading
import tempfile
import wave
from datetime import datetime, timedelta
from dotenv import load_dotenv
from groq import Groq
from plyer import notification
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
from rich.style import Style

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
TASKS_FILE = "tasks.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]
console = Console()

BANNER = """
 ██████╗ ██████╗  █████╗  ██████╗  ██████╗  ██████╗     ████████╗ █████╗ ███████╗██╗  ██╗
 ██╔══██╗██╔══██╗██╔══██╗██╔════╝ ██╔═══██╗██╔═══██╗       ██╔══╝██╔══██╗██╔════╝██║ ██╔╝
 ██║  ██║██████╔╝███████║██║  ███╗██║   ██║██║   ██║       ██║   ███████║███████╗█████╔╝
 ██║  ██║██╔══██╗██╔══██║██║   ██║██║   ██║██║   ██║       ██║   ██╔══██║╚════██║██╔═██╗
 ██████╔╝██║  ██║██║  ██║╚██████╔╝╚██████╔╝╚██████╔╝       ██║   ██║  ██║███████║██║  ██╗
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝  ╚═════╝       ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
"""

# ── Google Calendar ────────────────────────────────────────────────────────────

def get_calendar_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=True)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)

def add_to_google_calendar(task_name, date_str, time_str, priority):
    try:
        service = get_calendar_service()
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")
        time_str = time_str or "09:00"
        start_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(hours=1)
        event = {
            "summary": f"[{priority.upper()}] {task_name}",
            "description": f"Added by Task Agent | Priority: {priority}",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Kolkata"},
            "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "Asia/Kolkata"},
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 10}]}
        }
        service.events().insert(calendarId="primary", body=event).execute()
        return True
    except Exception as e:
        console.print(f"[red]  ⚠ CALENDAR ERROR: {e}[/red]")
        return False

# ── Tasks ──────────────────────────────────────────────────────────────────────

def load_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r") as f:
            return json.load(f)
    return []

def save_tasks(tasks):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)

def notify_desktop(title, message):
    notification.notify(title=title, message=message, app_name="Dragoo Task Agent", timeout=10)

def remind_after_seconds(seconds, message):
    def _remind():
        time.sleep(seconds)
        notify_desktop("Task Reminder", message)
        console.print(f"\n[bold magenta]  ◈ REMINDER ►[/bold magenta] [bold white]{message}[/bold white]")
    threading.Thread(target=_remind, daemon=True).start()

# ── Voice Input ───────────────────────────────────────────────────────────────

SAMPLE_RATE = 16000

def record_until_release(key="space"):
    frames = []
    console.print(Panel(
        Align.center("[bold magenta]  ◈ LISTENING...  RELEASE [SPACE] TO STOP ◈  [/bold magenta]"),
        border_style="magenta", box=box.DOUBLE_EDGE
    ))

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
        text = recognizer.recognize_google(audio)
        return text
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        console.print(f"[red]  ✗ SPEECH API ERROR: {e}[/red]")
        return None
    finally:
        os.unlink(wav_path)

def get_voice_input():
    console.print(Panel(
        Align.center("[bold cyan]  ◈ HOLD [SPACE] TO SPEAK  ◈  [/bold cyan]"),
        border_style="cyan", box=box.DOUBLE_EDGE
    ))
    keyboard.wait("space")
    wav_path = record_until_release("space")
    if not wav_path:
        console.print("[red]  ✗ No audio recorded.[/red]")
        return None
    with console.status("[cyan dim]  ◈ TRANSCRIBING...[/cyan dim]", spinner="aesthetic"):
        text = transcribe(wav_path)
    if text:
        console.print(Panel(
            f"[bold white]  ◈ HEARD  ►  [/bold white][cyan]{text}[/cyan]",
            border_style="cyan", box=box.DOUBLE_EDGE
        ))
    else:
        console.print("[red]  ✗ Could not understand. Try again.[/red]")
    return text

# ── AI ─────────────────────────────────────────────────────────────────────────

def understand(user_input):
    tasks = load_tasks()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tasks_summary = json.dumps(tasks, indent=2) if tasks else "No tasks yet."
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": f"""You are a smart task manager agent. Current time: {now}.
Current tasks:
{tasks_summary}

Return ONLY a JSON with:
- "action": one of [add, list, done, delete, done_all, unknown]
- "task": task description (for add)
- "time": HH:MM 24hr or null
- "date": YYYY-MM-DD or null
- "seconds": integer or null (for "after X seconds/minutes")
- "priority": "low"/"medium"/"high" — never null, default "medium"
- "id": integer or null
- "reply": short confirmation

Rules:
- "after X seconds/minutes" → seconds field only
- "at Xpm" → time field only
- "mark all done" → done_all
- ANY add/set/remind/schedule → action "add"
- No time → default "09:00"
- No date → default {datetime.now().strftime('%Y-%m-%d')}
- ONLY JSON. No markdown."""
            },
            {"role": "user", "content": user_input}
        ]
    )
    raw = response.choices[0].message.content.strip().replace("```json","").replace("```","").strip()
    return json.loads(raw)

# ── UI ─────────────────────────────────────────────────────────────────────────

PRIORITY_COLOR = {"high": "bold red",    "medium": "bold yellow", "low": "bold green"}
PRIORITY_ICON  = {"high": "⬛ HIGH",     "medium": "🔶 MED",      "low": "🟢 LOW"}

def cyber_rule(label=""):
    console.print(Rule(f"[cyan dim]{label}[/cyan dim]", style="cyan dim"))

def show_task_added(task, seconds, date_label, time_label, priority, cal_ok):
    color = PRIORITY_COLOR.get(priority, "yellow")
    content = Text()
    content.append("\n  ◈ TASK      »  ", style="cyan dim")
    content.append(f"{task}\n", style="bold white")
    if seconds:
        content.append("  ◈ TRIGGER   »  ", style="cyan dim")
        content.append(f"T-minus {seconds} seconds\n", style="bold magenta")
    else:
        content.append("  ◈ SCHEDULED »  ", style="cyan dim")
        content.append(f"{date_label}  {time_label}\n", style="bold cyan")
        content.append("  ◈ CALENDAR  »  ", style="cyan dim")
        content.append("SYNCED ✓\n" if cal_ok else "NOT SYNCED ✗\n",
                       style="bold green" if cal_ok else "bold red")
    content.append("  ◈ PRIORITY  »  ", style="cyan dim")
    content.append(PRIORITY_ICON.get(priority, priority.upper()), style=color)
    content.append("\n")
    console.print(Panel(content, title="[bold green]  TASK LOGGED [/bold green]",
                        border_style="green", box=box.DOUBLE_EDGE, padding=(0, 1)))

def show_task_list(tasks):
    if not tasks:
        console.print(Panel(Align.center("[cyan dim]◈ NO ACTIVE TASKS IN DATABASE ◈[/cyan dim]"),
                            border_style="cyan", box=box.DOUBLE_EDGE,
                            title="[cyan bold] TASK DATABASE [/cyan bold]"))
        return

    table = Table(box=box.SIMPLE_HEAD, border_style="cyan", header_style="bold cyan",
                  show_lines=False, expand=True, padding=(0, 1))
    table.add_column("ID",        style="cyan dim",  width=4,  justify="center")
    table.add_column("STATUS",    width=10,           justify="center")
    table.add_column("TASK",      style="white",      ratio=3)
    table.add_column("SCHEDULED", style="cyan",       ratio=2)
    table.add_column("PRIORITY",  justify="center",   width=12)

    for t in tasks:
        status = "[bold green]● DONE[/bold green]" if t["done"] else "[bold yellow]○ PENDING[/bold yellow]"
        d = t.get("date") or datetime.now().strftime("%Y-%m-%d")
        reminder = f"{d}  {t['time']}" if t.get("time") else "[dim]──[/dim]"
        p = (t.get("priority") or "medium").lower()
        table.add_row(str(t["id"]), status, t["task"], reminder,
                      f"[{PRIORITY_COLOR.get(p,'white')}]{PRIORITY_ICON.get(p,p)}[/{PRIORITY_COLOR.get(p,'white')}]")

    console.print(Panel(table, title="[bold cyan] TASK DATABASE [/bold cyan]",
                        border_style="cyan", box=box.DOUBLE_EDGE))

# ── Actions ────────────────────────────────────────────────────────────────────

def run_action(parsed):
    action   = parsed.get("action")
    tasks    = load_tasks()
    priority = (parsed.get("priority") or "medium").lower()

    if action == "add":
        seconds    = parsed.get("seconds")
        date_label = parsed.get("date") or datetime.now().strftime("%Y-%m-%d")
        time_label = parsed.get("time") or "09:00"
        new_task = {
            "id":       len(tasks) + 1,
            "task":     parsed.get("task", "Unnamed task"),
            "time":     None if seconds else time_label,
            "date":     None if seconds else date_label,
            "priority": priority,
            "done":     False,
            "created":  datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        tasks.append(new_task)
        save_tasks(tasks)
        cal_ok = False
        if seconds:
            remind_after_seconds(seconds, new_task["task"])
        else:
            cal_ok = add_to_google_calendar(new_task["task"], date_label, time_label, priority)
        show_task_added(new_task["task"], seconds, date_label, time_label, priority, cal_ok)

    elif action == "list":
        show_task_list(tasks)

    elif action == "done":
        task_id = parsed.get("id")
        if task_id is None:
            console.print("[yellow]  ⚠ Specify task: 'mark task 1 as done'[/yellow]")
            return
        for t in tasks:
            if t["id"] == int(task_id):
                t["done"] = True
                save_tasks(tasks)
                console.print(Panel(f"[bold green]  ✓ TASK #{task_id} MARKED COMPLETE[/bold green]",
                                    border_style="green", box=box.DOUBLE_EDGE))
                return
        console.print(f"[red]  ✗ Task {task_id} not found in database.[/red]")

    elif action == "done_all":
        for t in tasks:
            t["done"] = True
        save_tasks(tasks)
        console.print(Panel(f"[bold green]  ✓ ALL {len(tasks)} TASKS MARKED COMPLETE[/bold green]",
                            border_style="green", box=box.DOUBLE_EDGE))

    elif action == "delete":
        task_id = parsed.get("id")
        if task_id is None:
            console.print("[yellow]  ⚠ Specify task: 'delete task 2'[/yellow]")
            return
        tasks = [t for t in tasks if t["id"] != int(task_id)]
        save_tasks(tasks)
        console.print(Panel(f"[bold red]  ✗ TASK #{task_id} REMOVED FROM DATABASE[/bold red]",
                            border_style="red", box=box.DOUBLE_EDGE))

    else:
        console.print(Panel(f"[cyan dim]  {parsed.get('reply','Unknown command. Try: remind me to X at Y time')}[/cyan dim]",
                            border_style="dim", box=box.DOUBLE_EDGE))

# ── Reminders ──────────────────────────────────────────────────────────────────

def check_reminders():
    tasks = load_tasks()
    now = datetime.now()
    for t in tasks:
        if t["done"] or not t.get("time"):
            continue
        task_date = t.get("date") or now.strftime("%Y-%m-%d")
        try:
            task_dt = datetime.strptime(f"{task_date} {t['time']}", "%Y-%m-%d %H:%M")
            if abs((task_dt - now).total_seconds()) <= 60:
                notify_desktop("Task Reminder", t["task"])
                console.print(f"\n[bold magenta]  ◈ REMINDER ►[/bold magenta] [bold white]{t['task']}[/bold white]")
        except Exception:
            pass

def start_reminder_thread():
    schedule.every(1).minutes.do(check_reminders)
    def run():
        while True:
            schedule.run_pending()
            time.sleep(30)
    threading.Thread(target=run, daemon=True).start()

# ── Boot ───────────────────────────────────────────────────────────────────────

def main():
    console.clear()
    console.print(Align.center(f"[bold cyan]{BANNER}[/bold cyan]"))
    console.print(Align.center("[dim cyan]◈  DRAGOO INTELLIGENT TASK MANAGEMENT SYSTEM  ◈[/dim cyan]"))
    console.print(Align.center(f"[dim]v1.0  •  {datetime.now().strftime('%Y-%m-%d %H:%M')}  •  GROQ AI ENGINE[/dim]"))
    console.print()
    cyber_rule("SYSTEM BOOT")
    console.print()

    with console.status("[cyan]  ESTABLISHING GOOGLE CALENDAR LINK...[/cyan]", spinner="aesthetic"):
        time.sleep(0.5)
        try:
            get_calendar_service()
            cal_status = "[bold green]  ✓ GOOGLE CALENDAR  ──  ONLINE[/bold green]"
        except Exception:
            cal_status = "[bold red]  ✗ GOOGLE CALENDAR  ──  OFFLINE[/bold red]"

    with console.status("[cyan]  LOADING AI ENGINE...[/cyan]", spinner="aesthetic"):
        time.sleep(0.3)
        ai_status = "[bold green]  ✓ GROQ AI ENGINE   ──  ONLINE[/bold green]"

    console.print(cal_status)
    console.print(ai_status)
    console.print(f"[bold green]  ✓ REMINDER DAEMON  ──  ONLINE[/bold green]")
    console.print()
    cyber_rule("COMMAND INTERFACE")
    console.print()

    hints = Table.grid(padding=(0, 3))
    hints.add_column(style="cyan dim", width=3)
    hints.add_column(style="white")
    hints.add_row("◈", "Remind me to call mom at 6pm")
    hints.add_row("◈", "Remind me to brush after 30 seconds")
    hints.add_row("◈", "Show my tasks  |  Mark task 1 as done  |  Delete task 2")
    hints.add_row("◈", "Type v + Enter for VOICE mode  |  quit to exit")
    console.print(Panel(hints, title="[cyan dim] COMMAND REFERENCE [/cyan dim]",
                        border_style="cyan dim", box=box.SIMPLE_HEAD))
    console.print()

    start_reminder_thread()

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
            with console.status("[cyan dim]  ◈ PROCESSING INPUT...[/cyan dim]", spinner="aesthetic"):
                parsed = understand(user_input)
            run_action(parsed)
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
3. Rename it to: `Dragoo Task Agent`

### Step 19 — Folder Shortcut [MANUAL]
Same as above but keep the shortcut inside the `task-reminder-agent/` folder.

---

## PART 8 — FIRST RUN

### Step 20 — Launch for the First Time [MANUAL]
1. Double-click "Dragoo Task Agent" shortcut
2. A browser window opens automatically
3. Sign in with your Google account
4. Click "Allow" to grant Calendar access
5. Browser shows "Authentication successful"
6. Go back to terminal — agent is running

> Google login happens only once. Saves a token.json file after that.

---

## PART 9 — USING THE AGENT

### Step 21 — Text Commands
Type naturally and press Enter:
```
Remind me to call mom at 6pm
Remind me to drink water after 30 seconds
Show my tasks
Mark task 1 as done
Mark all tasks as done
Delete task 2
quit
```

### Step 22 — Voice Commands
1. Type `v` → press Enter
2. Hold `Spacebar` and speak
3. Release Spacebar
4. Agent transcribes and processes

---

## PART 10 — HOW IT WORKS BEHIND THE SCENES

### Step 23 — Full Request Flow
```
You type or speak
        ↓
Text sent to Groq AI (llama-3.1-8b-instant model — free)
        ↓
Groq returns JSON: { action, task, time, date, priority }
        ↓
Agent reads JSON and executes action
        ↓
If time set    → adds event to Google Calendar
If seconds set → starts background countdown timer
Always         → shows result in terminal + desktop notification
```

---

## TROUBLESHOOTING

| Problem | Solution |
|---|---|
| Agent not starting | Check Python is installed and in PATH |
| Groq API error | Check .env file has correct GROQ_API_KEY |
| Calendar not syncing | Delete token.json and restart to re-authenticate |
| Voice not working | Check microphone is connected and not muted |
| Module not found | Run: pip install -r requirements.txt |
| credentials.json error | Make sure file says "installed" not "web" at start |
| Shortcut not working | Right-click → Properties → verify Target path |

---

## FILES SUMMARY

| File | Created By | Purpose |
|---|---|---|
| agent.py | AI Generated | Full agent code |
| requirements.txt | AI Generated | Python libraries list |
| .env | User — Manual | Stores Groq API key |
| credentials.json | Downloaded from Google Cloud | Google OAuth credentials |
| token.json | Auto-generated on first run | Saves Google login session |
| tasks.json | Auto-generated on first task | Stores all tasks locally |
| run_agent.bat | AI Generated | Double-click launcher |
| Dragoo Task Agent.lnk | AI Generated | Desktop/folder shortcut |

---

*Built with Claude Code AI — Dragoo Task Agent v1.0*
*Guide created: 2026-04-24*
