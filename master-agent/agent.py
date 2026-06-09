import os
import sys
import json
import time
import tempfile
import threading
import importlib.util
import re
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.align import Align
from rich.rule import Rule
from rich.table import Table
import sounddevice as sd
import scipy.io.wavfile as wav
import speech_recognition as sr
import keyboard
import numpy as np
import pyttsx3

load_dotenv()

client    = Groq(api_key=os.environ.get("GROQ_API_KEY"))
console   = Console()
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
TASK_PATH     = os.path.join(BASE_DIR, "..", "task-reminder-agent",    "agent.py")
MAIL_PATH     = os.path.join(BASE_DIR, "..", "email-agent",            "agent.py")
ACTIVITY_PATH  = os.path.join(BASE_DIR, "..", "activity-tracker-agent", "agent.py")
WHATSAPP_PATH  = os.path.join(BASE_DIR, "..", "whatsapp-agent",         "agent.py")
SEARCH_PATH    = os.path.join(BASE_DIR, "..", "web-search-agent",       "agent.py")

BANNER = """
 ██████╗ ██████╗  █████╗  ██████╗  ██████╗  ██████╗     ███╗   ███╗ █████╗ ███████╗████████╗███████╗██████╗
 ██╔══██╗██╔══██╗██╔══██╗██╔════╝ ██╔═══██╗██╔═══██╗    ████╗ ████║██╔══██╗██╔════╝╚══██╔══╝██╔════╝██╔══██╗
 ██║  ██║██████╔╝███████║██║  ███╗██║   ██║██║   ██║    ██╔████╔██║███████║███████╗   ██║   █████╗  ██████╔╝
 ██║  ██║██╔══██╗██╔══██║██║   ██║██║   ██║██║   ██║    ██║╚██╔╝██║██╔══██║╚════██║   ██║   ██╔══╝  ██╔══██╗
 ██████╔╝██║  ██║██║  ██║╚██████╔╝╚██████╔╝╚██████╔╝    ██║ ╚═╝ ██║██║  ██║███████║   ██║   ███████╗██║  ██║
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝  ╚═════╝    ╚═╝     ╚═╝╚═╝  ╚═╝╚══════╝   ╚═╝   ╚══════╝╚═╝  ╚═╝
"""

# ── Windows TTS ────────────────────────────────────────────────────────────────

_tts = pyttsx3.init()
_tts.setProperty("rate", 165)
_tts.setProperty("volume", 1.0)

def speak(text):
    try:
        _tts.say(text)
        _tts.runAndWait()
    except Exception:
        pass

# ── Module Loader ──────────────────────────────────────────────────────────────

def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# ── Voice Input ────────────────────────────────────────────────────────────────

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
        return recognizer.recognize_google(audio)
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        console.print(f"[red]  ✗ SPEECH ERROR: {e}[/red]")
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

# ── Routing AI ─────────────────────────────────────────────────────────────────

def route(user_input):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": """You are a master AI orchestrator that routes user requests to the right agent.

Available agents:
- task     : reminders, tasks, to-do, scheduling, Google Calendar, countdowns, timers
- email     : Gmail inbox, read emails, send, reply, forward, archive, delete, search, templates
- activity  : desktop activity tracking, app usage, time spent, what was open, screen time, productivity stats
- whatsapp  : send WhatsApp message, WhatsApp contacts, message someone on WhatsApp
- search    : web search, weather, news, current events, live scores, prices, facts, anything real-time

Return ONLY a valid JSON:
{
  "domain": "task" | "email" | "activity" | "whatsapp" | "search" | "general",
  "speak": "one short friendly sentence confirming what you are about to do"
}

Rules:
- Anything about tasks, reminders, timers, countdowns, calendar → task
- Anything about emails, inbox, Gmail, messages, send, reply, forward → email
- Anything about desktop usage, screen time, which app, how long, what was I using → activity
- Anything about WhatsApp, sending WhatsApp message, WhatsApp contacts → whatsapp
- Anything about weather, news, search, live scores, prices, current events, facts → search
- General questions or unclear intent → general
- speak must be natural (e.g. "Sure, let me check your inbox." / "Got it, adding that to your tasks.")
- ONLY JSON. No markdown. No extra text."""
            },
            {"role": "user", "content": user_input}
        ]
    )
    raw = response.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
    raw = re.sub(r",\s*}", "}", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"domain": "general", "speak": "Let me think about that."}

# ── UI Helpers ─────────────────────────────────────────────────────────────────

def cyber_rule(label=""):
    console.print(Rule(f"[cyan dim]{label}[/cyan dim]", style="cyan dim"))

DOMAIN_ICON  = {"task": "◈ TASK AGENT",  "email": "◈ EMAIL AGENT", "activity": "◈ ACTIVITY AGENT", "whatsapp": "◈ WHATSAPP AGENT", "search": "◈ SEARCH AGENT", "general": "◈ MASTER AI"}
DOMAIN_COLOR = {"task": "green",          "email": "blue",          "activity": "magenta",           "whatsapp": "green",            "search": "yellow",          "general": "yellow"}

def show_routing(domain, speak_text):
    icon  = DOMAIN_ICON.get(domain, "◈")
    color = DOMAIN_COLOR.get(domain, "cyan")
    console.print(Panel(
        f"[bold {color}]  {icon}  ►  [/bold {color}][white]{speak_text}[/white]",
        border_style=color, box=box.DOUBLE_EDGE
    ))

EMAIL_SPEAK = {
    "read":        "Here are your unread emails.",
    "summarize":   "Email summary ready.",
    "reply":       "Reply drafted.",
    "forward":     "Forward prepared.",
    "archive":     "Email archived.",
    "delete":      "Email moved to trash.",
    "empty_trash": "Trash has been emptied.",
    "search":      "Here are the search results.",
    "draft":       "Email draft is ready.",
    "load_more":   "More emails loaded.",
    "template_save":  "Template saved.",
    "template_use":   "Template loaded.",
    "template_list":  "Here are your templates.",
    "contact_add":    "Contact saved.",
    "contact_list":   "Here are your saved contacts.",
    "contact_delete": "Contact removed.",
}

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    console.clear()
    console.print(Align.center(f"[bold cyan]{BANNER}[/bold cyan]"))
    console.print(Align.center("[dim cyan]◈  DRAGOO MASTER ORCHESTRATOR SYSTEM  ◈[/dim cyan]"))
    console.print(Align.center(f"[dim]v1.0  •  {datetime.now().strftime('%Y-%m-%d %H:%M')}  •  GROQ AI ENGINE[/dim]"))
    console.print()
    cyber_rule("SYSTEM BOOT")
    console.print()

    # ── Load sub-agent modules
    with console.status("[cyan]  LOADING TASK AGENT...[/cyan]", spinner="aesthetic"):
        try:
            task_mod    = load_module(TASK_PATH, "task_agent")
            task_status = "[bold green]  ✓ TASK AGENT       ──  LOADED[/bold green]"
        except Exception as e:
            task_mod    = None
            task_status = f"[bold red]  ✗ TASK AGENT       ──  FAILED ({e})[/bold red]"

    with console.status("[cyan]  LOADING EMAIL AGENT...[/cyan]", spinner="aesthetic"):
        try:
            mail_mod    = load_module(MAIL_PATH, "email_agent")
            mail_status = "[bold green]  ✓ EMAIL AGENT      ──  LOADED[/bold green]"
        except Exception as e:
            mail_mod    = None
            mail_status = f"[bold red]  ✗ EMAIL AGENT      ──  FAILED ({e})[/bold red]"

    with console.status("[cyan]  LOADING ACTIVITY TRACKER...[/cyan]", spinner="aesthetic"):
        try:
            activity_mod    = load_module(ACTIVITY_PATH, "activity_agent")
            activity_status = "[bold green]  ✓ ACTIVITY TRACKER ──  LOADED[/bold green]"
        except Exception as e:
            activity_mod    = None
            activity_status = f"[bold red]  ✗ ACTIVITY TRACKER ──  FAILED ({e})[/bold red]"

    with console.status("[cyan]  LOADING WHATSAPP AGENT...[/cyan]", spinner="aesthetic"):
        try:
            wa_mod    = load_module(WHATSAPP_PATH, "whatsapp_agent")
            wa_status = "[bold green]  ✓ WHATSAPP AGENT   ──  LOADED[/bold green]"
        except Exception as e:
            wa_mod    = None
            wa_status = f"[bold red]  ✗ WHATSAPP AGENT   ──  FAILED ({e})[/bold red]"

    with console.status("[cyan]  LOADING SEARCH AGENT...[/cyan]", spinner="aesthetic"):
        try:
            search_mod    = load_module(SEARCH_PATH, "search_agent")
            search_status = "[bold green]  ✓ SEARCH AGENT     ──  LOADED[/bold green]"
        except Exception as e:
            search_mod    = None
            search_status = f"[bold red]  ✗ SEARCH AGENT     ──  FAILED ({e})[/bold red]"

    # ── Connect services
    gmail_service = None
    emails_cache  = {}

    with console.status("[cyan]  CONNECTING TO GMAIL...[/cyan]", spinner="aesthetic"):
        try:
            if mail_mod:
                gmail_service = mail_mod.get_gmail_service()
                count = mail_mod.get_unread_count(gmail_service)
                gmail_status = f"[bold green]  ✓ GMAIL            ──  ONLINE  ──  {count} UNREAD[/bold green]"
            else:
                gmail_status = "[bold red]  ✗ GMAIL            ──  OFFLINE[/bold red]"
        except Exception:
            gmail_status = "[bold red]  ✗ GMAIL            ──  OFFLINE[/bold red]"

    with console.status("[cyan]  CONNECTING TO GOOGLE CALENDAR...[/cyan]", spinner="aesthetic"):
        try:
            if task_mod:
                task_mod.get_calendar_service()
                cal_status = "[bold green]  ✓ GOOGLE CALENDAR  ──  ONLINE[/bold green]"
            else:
                cal_status = "[bold red]  ✗ GOOGLE CALENDAR  ──  OFFLINE[/bold red]"
        except Exception:
            cal_status = "[bold red]  ✗ GOOGLE CALENDAR  ──  OFFLINE[/bold red]"

    # ── Start WhatsApp bridge
    wa_bridge_status = "[bold yellow]  ◈ WHATSAPP BRIDGE  ──  STARTING (scan QR in popup)[/bold yellow]"
    if wa_mod:
        try:
            ok = wa_mod.start_bridge()
            if not ok:
                wa_bridge_status = "[bold red]  ✗ WHATSAPP BRIDGE  ──  FAILED (Node.js not installed?)[/bold red]"
        except Exception as e:
            wa_bridge_status = f"[bold red]  ✗ WHATSAPP BRIDGE  ──  FAILED ({e})[/bold red]"

    console.print(task_status)
    console.print(mail_status)
    console.print(activity_status)
    console.print(wa_status)
    console.print(search_status)
    console.print(gmail_status)
    console.print(cal_status)
    console.print(wa_bridge_status)
    console.print("[bold green]  ✓ GROQ AI ENGINE   ──  ONLINE[/bold green]")
    console.print("[bold green]  ✓ WINDOWS TTS      ──  ONLINE[/bold green]")
    console.print("[bold green]  ✓ VOICE INPUT      ──  READY (Hold SPACE)[/bold green]")
    console.print()
    cyber_rule("COMMAND INTERFACE")
    console.print()

    hints = Table.grid(padding=(0, 3))
    hints.add_column(style="cyan dim", width=3)
    hints.add_column(style="white")
    hints.add_row("◈", "Remind me to call mom at 6pm            [dim]→ Task Agent[/dim]")
    hints.add_row("◈", "Show my tasks  ·  Mark task 1 done      [dim]→ Task Agent[/dim]")
    hints.add_row("◈", "Check my inbox  ·  Summarize email 1    [dim]→ Email Agent[/dim]")
    hints.add_row("◈", "Reply to email 2  ·  Write email to X   [dim]→ Email Agent[/dim]")
    hints.add_row("◈", "What did I use most today  ·  Which websites did I visit  [dim]→ Activity Agent[/dim]")
    hints.add_row("◈", "What's open now  ·  PC uptime  ·  What at 3pm   [dim]→ Activity Agent[/dim]")
    hints.add_row("◈", "Send gf a WhatsApp  ·  WhatsApp mom I'm home  [dim]→ WhatsApp Agent[/dim]")
    hints.add_row("◈", "Weather in Delhi  ·  IPL score  ·  Latest AI news  [dim]→ Search Agent[/dim]")
    hints.add_row("◈", "Type [bold cyan]v[/bold cyan] + Enter for VOICE  |  [bold cyan]quit[/bold cyan] to exit")
    console.print(Panel(hints, title="[cyan dim] MASTER COMMAND REFERENCE [/cyan dim]",
                        border_style="cyan dim", box=box.SIMPLE_HEAD))
    console.print()

    # Start background threads
    if task_mod:
        task_mod.start_reminder_thread()
    if activity_mod:
        activity_mod.start_tracking()

    speak("Dragoo Master Agent is online. How can I help you?")

    while True:
        try:
            user_input = console.input("[bold cyan]  ◈ INPUT  ►  [/bold cyan]").strip()
            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                console.print()
                cyber_rule("SHUTDOWN")
                if wa_mod:
                    wa_mod.stop_bridge()
                console.print(Align.center("\n[bold cyan]  ◈ SYSTEM OFFLINE — GOODBYE ◈  [/bold cyan]\n"))
                speak("Goodbye. Master agent going offline.")
                break

            if user_input.lower() in ("v", "voice"):
                voice_text = get_voice_input()
                if not voice_text:
                    continue
                user_input = voice_text

            console.print()

            # ── Route the request
            with console.status("[cyan dim]  ◈ ROUTING...[/cyan dim]", spinner="aesthetic"):
                routing = route(user_input)

            domain     = routing.get("domain", "general")
            speak_text = routing.get("speak", "Processing your request.")

            show_routing(domain, speak_text)
            speak(speak_text)

            # ── Execute in the right agent
            if domain == "task" and task_mod:
                with console.status("[cyan dim]  ◈ TASK AGENT PROCESSING...[/cyan dim]", spinner="aesthetic"):
                    parsed = task_mod.understand(user_input)
                task_mod.run_action(parsed)
                reply = parsed.get("reply", "")
                if reply:
                    speak(reply)

            elif domain == "email" and mail_mod and gmail_service:
                with console.status("[cyan dim]  ◈ EMAIL AGENT PROCESSING...[/cyan dim]", spinner="aesthetic"):
                    parsed = mail_mod.understand(user_input)
                mail_mod.run_action(parsed, gmail_service, emails_cache)
                action = parsed.get("action", "")
                if action in EMAIL_SPEAK:
                    speak(EMAIL_SPEAK[action])

            elif domain == "whatsapp" and wa_mod:
                with console.status("[green dim]  ◈ WHATSAPP AGENT PROCESSING...[/green dim]", spinner="aesthetic"):
                    parsed = wa_mod.understand(user_input)
                result = wa_mod.run_action(parsed)
                if result and result not in ("done", "cancelled", "failed", "not connected"):
                    speak(result)

            elif domain == "search" and search_mod:
                with console.status("[yellow dim]  ◈ SEARCH AGENT PROCESSING...[/yellow dim]", spinner="aesthetic"):
                    parsed = search_mod.understand(user_input)
                answer = search_mod.run_action(parsed)
                if answer:
                    speak(answer[:200])

            elif domain == "activity" and activity_mod:
                with console.status("[magenta dim]  ◈ ACTIVITY AGENT PROCESSING...[/magenta dim]", spinner="aesthetic"):
                    parsed = activity_mod.understand(user_input)
                result = activity_mod.run_action(parsed)
                reply  = parsed.get("reply", "")
                if reply:
                    speak(reply)

            else:
                # General AI response
                resp = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": "You are Dragoo, a helpful AI assistant. Reply in 1-2 short sentences."},
                        {"role": "user",   "content": user_input}
                    ]
                )
                reply = resp.choices[0].message.content.strip()
                console.print(Panel(f"[white]  {reply}[/white]",
                                    border_style="yellow", box=box.DOUBLE_EDGE))
                speak(reply)

            console.print()

        except Exception as e:
            console.print(f"[bold red]  ✗ SYSTEM ERROR: {e}[/bold red]")

if __name__ == "__main__":
    main()
