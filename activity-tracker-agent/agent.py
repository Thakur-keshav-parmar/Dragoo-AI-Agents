import os
import re
import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from groq import Groq
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

try:
    import win32gui
    import win32process
    import psutil
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

try:
    import win32api
    WIN32API_AVAILABLE = True
except ImportError:
    WIN32API_AVAILABLE = False

load_dotenv()
client  = Groq(api_key=os.environ.get("GROQ_API_KEY"))
console = Console()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "activity.db")

# ── App name map ───────────────────────────────────────────────────────────────

APP_NAMES = {
    "chrome":          "Google Chrome",
    "firefox":         "Firefox",
    "msedge":          "Microsoft Edge",
    "opera":           "Opera",
    "brave":           "Brave",
    "code":            "VS Code",
    "pycharm64":       "PyCharm",
    "pycharm32":       "PyCharm",
    "explorer":        "File Explorer",
    "notepad":         "Notepad",
    "notepad++":       "Notepad++",
    "cmd":             "Command Prompt",
    "powershell":      "PowerShell",
    "windowsterminal": "Windows Terminal",
    "python":          "Python",
    "pythonw":         "Python",
    "vlc":             "VLC",
    "spotify":         "Spotify",
    "discord":         "Discord",
    "slack":           "Slack",
    "zoom":            "Zoom",
    "teams":           "Microsoft Teams",
    "excel":           "Excel",
    "winword":         "Word",
    "powerpnt":        "PowerPoint",
    "outlook":         "Outlook",
    "telegram":        "Telegram",
    "whatsapp":        "WhatsApp",
    "obs64":           "OBS Studio",
    "obs32":           "OBS Studio",
    "devenv":          "Visual Studio",
    "rider64":         "JetBrains Rider",
    "idea64":          "IntelliJ IDEA",
    "webstorm64":      "WebStorm",
    "xampp-control":   "XAMPP",
    "postman":         "Postman",
    "dbeaver":         "DBeaver",
    "winscp":          "WinSCP",
    "putty":           "PuTTY",
    "mstsc":           "Remote Desktop",
    "taskmgr":         "Task Manager",
    "mspaint":         "Paint",
    "snippingtool":    "Snipping Tool",
    "figma":           "Figma",
    "photoshop":       "Photoshop",
    "illustrator":     "Illustrator",
    "acrobat":         "Adobe Acrobat",
    "everything":      "Everything Search",
    "7zfm":            "7-Zip",
    "winrar":          "WinRAR",
}

BROWSERS = {"Google Chrome", "Firefox", "Microsoft Edge", "Opera", "Brave"}

BROWSER_SUFFIXES = [
    " - Google Chrome",   " – Google Chrome",
    " - Mozilla Firefox", " – Mozilla Firefox",
    " - Microsoft Edge",  " – Microsoft Edge",
    " - Opera",           " – Opera",
    " - Brave",           " – Brave",
    " | Mozilla Firefox",
]

SKIP_TITLES = {
    "", "Program Manager", "Windows Input Experience",
    "Microsoft Text Input Application", "Settings",
}

def clean_app_name(exe_name):
    if not exe_name:
        return "Unknown"
    base = os.path.splitext(exe_name.lower())[0]
    return APP_NAMES.get(base, exe_name.replace(".exe", "").title())

def extract_website(title, app_name):
    if app_name not in BROWSERS:
        return None
    for suffix in BROWSER_SUFFIXES:
        if title.endswith(suffix):
            site = title[:-len(suffix)].strip()
            return site if site and site not in ("New Tab", "Nouvel onglet") else None
    return title.strip() if title else None

# ── Database ───────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_PATH)
    # foreground sessions — what you were actively using
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name     TEXT,
            window_title TEXT,
            website      TEXT,
            is_browser   INTEGER DEFAULT 0,
            start_time   TEXT,
            end_time     TEXT,
            duration_sec INTEGER
        )
    """)
    # all-windows snapshots — everything open in background too
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp    TEXT,
            app_name     TEXT,
            window_title TEXT,
            website      TEXT,
            is_browser   INTEGER DEFAULT 0
        )
    """)
    # migrate old activity_log table if it exists
    conn.execute("""
        INSERT OR IGNORE INTO sessions (app_name, window_title, start_time, end_time, duration_sec)
        SELECT app_name, window_title, start_time, end_time, duration_sec
        FROM activity_log
    """) if _table_exists(conn, "activity_log") else None
    conn.commit()
    conn.close()

def _table_exists(conn, name):
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None

def log_session(app_name, window_title, website, is_browser, start_time, end_time):
    duration = int((end_time - start_time).total_seconds())
    if duration < 2:
        return
    if app_name == "Unknown" and not window_title:
        return  # skip garbage entries from before pywin32 was working
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO sessions (app_name, window_title, website, is_browser, start_time, end_time, duration_sec) "
        "VALUES (?,?,?,?,?,?,?)",
        (app_name, window_title, website, int(is_browser),
         start_time.isoformat(), end_time.isoformat(), duration)
    )
    conn.commit()
    conn.close()

def snapshot_windows(windows):
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    conn.executemany(
        "INSERT INTO snapshots (timestamp, app_name, window_title, website, is_browser) VALUES (?,?,?,?,?)",
        [(now, app, title, website, int(is_browser)) for app, title, website, is_browser in windows]
    )
    conn.commit()
    conn.close()

# ── Window functions ───────────────────────────────────────────────────────────

def get_active_window():
    if not WIN32_AVAILABLE:
        return "Unknown", "", None, False
    # get window title first — always works
    try:
        hwnd  = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
    except Exception:
        return "Unknown", "", None, False

    # get process name — may fail for protected system processes
    app = "Unknown"
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc   = psutil.Process(pid)
        app    = clean_app_name(proc.name())
    except Exception:
        # fall back: guess from window title
        if title:
            for suffix in BROWSER_SUFFIXES:
                if title.endswith(suffix):
                    browser = suffix.strip(" -–").strip()
                    app = browser
                    break

    site = extract_website(title, app)
    return app, title, site, (app in BROWSERS)

def get_all_windows():
    if not WIN32_AVAILABLE:
        return []
    found = []
    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd).strip()
        if not title or title in SKIP_TITLES or len(title) < 2:
            return
        app = "Unknown"
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc   = psutil.Process(pid)
            app    = clean_app_name(proc.name())
        except Exception:
            # guess from title for browsers
            for suffix in BROWSER_SUFFIXES:
                if title.endswith(suffix):
                    app = suffix.strip(" -–").strip()
                    break
        # skip truly unknown windows with no title context
        if app == "Unknown" and not any(title.endswith(s) for s in BROWSER_SUFFIXES):
            app = title.split(" - ")[-1].strip() or "Unknown"
        site = extract_website(title, app)
        found.append((app, title, site, app in BROWSERS))
    try:
        win32gui.EnumWindows(_cb, None)
    except Exception:
        pass
    seen, unique = set(), []
    for r in found:
        key = (r[0], r[1][:40])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique

def get_idle_seconds():
    if not WIN32API_AVAILABLE:
        return 0
    try:
        info = win32api.GetLastInputInfo()
        tick = win32api.GetTickCount()
        return max(0, (tick - info) / 1000.0)
    except Exception:
        return 0

def get_system_uptime():
    try:
        return int(time.time() - psutil.boot_time())
    except Exception:
        return 0

# ── Background threads ─────────────────────────────────────────────────────────

_tracking        = False
_tracker_thread  = None
_snapshot_thread = None

def _foreground_loop():
    global _tracking
    current_app  = None
    current_title = None
    current_site  = None
    current_is_browser = False
    session_start = None
    last_flush    = None
    FLUSH_EVERY   = 30

    while _tracking:
        app, title, site, is_browser = get_active_window()
        now = datetime.now()

        if app != current_app or title != current_title:
            # window changed — save previous session
            if current_app and session_start and last_flush:
                log_session(current_app, current_title, current_site,
                            current_is_browser, last_flush, now)
            current_app        = app
            current_title      = title
            current_site       = site
            current_is_browser = is_browser
            session_start      = now
            last_flush         = now
        else:
            # same window — heartbeat flush every 30s so DB is always fresh
            if session_start and last_flush and (now - last_flush).total_seconds() >= FLUSH_EVERY:
                log_session(current_app, current_title, current_site,
                            current_is_browser, last_flush, now)
                last_flush = now

        time.sleep(2)

    # flush on exit
    if current_app and last_flush:
        log_session(current_app, current_title, current_site,
                    current_is_browser, last_flush, datetime.now())

def _snapshot_loop():
    global _tracking
    while _tracking:
        try:
            windows = get_all_windows()
            if windows:
                snapshot_windows(windows)
        except Exception:
            pass
        time.sleep(60)  # snapshot all open windows every 60 seconds

def start_tracking():
    global _tracking, _tracker_thread, _snapshot_thread
    if _tracker_thread and _tracker_thread.is_alive():
        return
    init_db()
    _tracking        = True
    _tracker_thread  = threading.Thread(target=_foreground_loop, daemon=True)
    _snapshot_thread = threading.Thread(target=_snapshot_loop,   daemon=True)
    _tracker_thread.start()
    _snapshot_thread.start()

def stop_tracking():
    global _tracking
    _tracking = False

# ── Helpers ────────────────────────────────────────────────────────────────────

def get_period_range(period):
    now   = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "yesterday":
        return today - timedelta(days=1), today
    elif period == "week":
        return today - timedelta(days=today.weekday()), now
    elif period == "month":
        return today.replace(day=1), now
    else:
        return today, now

def format_duration(seconds):
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m {s}s"
    else:
        h, rem = divmod(seconds, 3600)
        return f"{h}h {rem // 60}m"

# ── Queries ────────────────────────────────────────────────────────────────────

def query_top_apps(period="today"):
    start, end = get_period_range(period)
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT app_name, SUM(duration_sec) AS total
        FROM sessions
        WHERE start_time >= ? AND start_time <= ?
        GROUP BY app_name ORDER BY total DESC LIMIT 12
    """, (start.isoformat(), end.isoformat())).fetchall()
    conn.close()
    return rows

def query_websites(period="today"):
    start, end = get_period_range(period)
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT website, app_name, SUM(duration_sec) AS total
        FROM sessions
        WHERE is_browser=1 AND website IS NOT NULL AND website != ''
          AND start_time >= ? AND start_time <= ?
        GROUP BY website ORDER BY total DESC LIMIT 15
    """, (start.isoformat(), end.isoformat())).fetchall()
    conn.close()
    return rows

def query_app_time(app_name, period="today"):
    start, end = get_period_range(period)
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute("""
        SELECT SUM(duration_sec) FROM sessions
        WHERE LOWER(app_name) LIKE ? AND start_time >= ? AND start_time <= ?
    """, (f"%{app_name.lower()}%", start.isoformat(), end.isoformat())).fetchone()
    conn.close()
    return row[0] or 0

def query_timeline(period="today"):
    start, end = get_period_range(period)
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT app_name, window_title, website, start_time, end_time, duration_sec
        FROM sessions
        WHERE start_time >= ? AND start_time <= ?
        ORDER BY start_time DESC LIMIT 60
    """, (start.isoformat(), end.isoformat())).fetchall()
    conn.close()
    return rows

def query_what_at_time(time_str):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        ts = time_str.strip().lower()
        if "am" in ts or "pm" in ts:
            ts2 = ts.replace("am", " AM").replace("pm", " PM")
            fmt = "%I:%M %p" if ":" in ts2 else "%I %p"
            t   = datetime.strptime(ts2.strip(), fmt)
        elif ":" in ts:
            h, m = ts.split(":")
            t = today.replace(hour=int(h), minute=int(m))
        else:
            t = today.replace(hour=int(ts), minute=0)
        target = today.replace(hour=t.hour, minute=t.minute, second=0)
    except Exception:
        return None
    conn = sqlite3.connect(DB_PATH)
    row  = conn.execute("""
        SELECT app_name, window_title, website FROM sessions
        WHERE start_time <= ? AND end_time >= ?
        ORDER BY duration_sec DESC LIMIT 1
    """, (target.isoformat(), target.isoformat())).fetchone()
    conn.close()
    return row

def query_open_now():
    conn    = sqlite3.connect(DB_PATH)
    latest  = conn.execute("SELECT MAX(timestamp) FROM snapshots").fetchone()[0]
    if not latest:
        conn.close()
        return [], None
    rows = conn.execute("""
        SELECT DISTINCT app_name, is_browser
        FROM snapshots WHERE timestamp = ?
        ORDER BY app_name
    """, (latest,)).fetchall()
    conn.close()
    return rows, latest

# ── Display ────────────────────────────────────────────────────────────────────

def _bar(pct, width=10):
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)

def show_top_apps(rows, period):
    if not rows:
        console.print(Panel("[yellow]  No activity recorded yet — give it 30 seconds.[/yellow]",
                            border_style="yellow", box=box.DOUBLE_EDGE))
        return
    total = sum(r[1] for r in rows)
    t = Table(title=f"[bold magenta]  TOP APPS — {period.upper()}  [/bold magenta]",
              border_style="magenta", box=box.DOUBLE_EDGE,
              show_header=True, header_style="bold magenta")
    t.add_column("#",           style="magenta dim", width=4,  justify="center")
    t.add_column("Application", style="bold white",  min_width=22)
    t.add_column("Time",        style="green",       width=12, justify="right")
    t.add_column("Share",       style="yellow",      width=8,  justify="right")
    t.add_column("Bar",         style="magenta",     width=12)
    for i, (app, secs) in enumerate(rows, 1):
        pct = (secs / total * 100) if total else 0
        t.add_row(f"#{i}", app, format_duration(secs), f"{pct:.1f}%", _bar(pct))
    console.print(); console.print(t)
    console.print(Panel(
        f"[bold white]  Total tracked: [magenta]{format_duration(total)}[/magenta]"
        f"  across [magenta]{len(rows)}[/magenta] apps[/bold white]",
        border_style="magenta dim", box=box.SIMPLE_HEAD
    ))

def show_websites(rows, period):
    if not rows:
        console.print(Panel(
            "[yellow]  No browser activity yet.\n"
            "  Note: website tracking reads the browser window title.\n"
            "  Switch browser tabs a few times to populate data.[/yellow]",
            border_style="yellow", box=box.DOUBLE_EDGE))
        return
    total = sum(r[2] for r in rows)
    t = Table(title=f"[bold magenta]  WEBSITES VISITED — {period.upper()}  [/bold magenta]",
              border_style="magenta", box=box.DOUBLE_EDGE,
              show_header=True, header_style="bold magenta")
    t.add_column("#",        style="magenta dim", width=4,  justify="center")
    t.add_column("Page / Site",  style="bold white",  min_width=30)
    t.add_column("Browser",  style="cyan",        width=16)
    t.add_column("Time",     style="green",       width=12, justify="right")
    t.add_column("Share",    style="yellow",      width=8,  justify="right")
    for i, (website, browser, secs) in enumerate(rows, 1):
        pct = (secs / total * 100) if total else 0
        t.add_row(f"#{i}", website[:40], browser, format_duration(secs), f"{pct:.1f}%")
    console.print(); console.print(t)
    console.print(Panel(
        f"[bold white]  Total browser time: [magenta]{format_duration(total)}[/magenta][/bold white]",
        border_style="magenta dim", box=box.SIMPLE_HEAD
    ))

def show_uptime():
    uptime_sec = get_system_uptime()
    idle_sec   = get_idle_seconds()
    boot_dt    = datetime.fromtimestamp(psutil.boot_time() if WIN32_AVAILABLE else time.time())
    console.print(Panel(
        f"[bold white]  PC turned on   [magenta]{boot_dt.strftime('%d %b %Y  %H:%M')}[/magenta]\n"
        f"  Uptime         [green]{format_duration(uptime_sec)}[/green]\n"
        f"  Idle right now [yellow]{format_duration(int(idle_sec))}[/yellow]"
        + (" [dim](AFK)[/dim]" if idle_sec > 120 else ""),
        title="[bold magenta]  SYSTEM STATUS  [/bold magenta]",
        border_style="magenta", box=box.DOUBLE_EDGE
    ))

def show_open_now(rows, timestamp):
    if not rows:
        console.print(Panel(
            "[yellow]  No snapshot yet — wait ~60 seconds after agent boots.[/yellow]",
            border_style="yellow", box=box.DOUBLE_EDGE))
        return
    dt = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
    t = Table(title=f"[bold magenta]  ALL OPEN APPS (snapshot at {dt})  [/bold magenta]",
              border_style="magenta", box=box.DOUBLE_EDGE,
              show_header=True, header_style="bold magenta")
    t.add_column("Application", style="bold white", min_width=24)
    t.add_column("Type",        style="cyan",       width=12)
    browsers = [(app, ib) for app, ib in rows if ib]
    others   = [(app, ib) for app, ib in rows if not ib]
    for app, _ in browsers:
        t.add_row(app, "[cyan]Browser[/cyan]")
    for app, _ in others:
        t.add_row(app, "App")
    console.print(); console.print(t)
    console.print(Panel(
        f"[bold white]  [magenta]{len(browsers)}[/magenta] browsers open  ·  "
        f"[magenta]{len(others)}[/magenta] other apps open[/bold white]",
        border_style="magenta dim", box=box.SIMPLE_HEAD
    ))

def show_app_time(app, secs, period):
    if secs == 0:
        console.print(Panel(f"[yellow]  No usage found for [bold]{app}[/bold] in {period}.[/yellow]",
                            border_style="yellow", box=box.DOUBLE_EDGE))
    else:
        console.print(Panel(
            f"[bold white]  [magenta]{app}[/magenta]  ►  [green]{format_duration(secs)}[/green]  ({period})[/bold white]",
            border_style="magenta", box=box.DOUBLE_EDGE
        ))

def show_timeline(rows, period):
    if not rows:
        console.print(Panel("[yellow]  No activity recorded yet.[/yellow]",
                            border_style="yellow", box=box.DOUBLE_EDGE))
        return
    t = Table(title=f"[bold magenta]  TIMELINE — {period.upper()} (latest first)  [/bold magenta]",
              border_style="magenta", box=box.DOUBLE_EDGE,
              show_header=True, header_style="bold magenta")
    t.add_column("Time",         style="magenta",    width=10)
    t.add_column("App",          style="bold white",  min_width=16)
    t.add_column("Website / Window", style="cyan",   min_width=30)
    t.add_column("Duration",     style="green",       width=12, justify="right")
    for app, title, website, start_time, _, dur in rows:
        dt      = datetime.fromisoformat(start_time).strftime("%H:%M:%S")
        display = website if website else (title[:38] + "…" if len(title) > 38 else title)
        t.add_row(dt, app, display, format_duration(dur))
    console.print(); console.print(t)

def show_what_at_time(row, time_str):
    if not row:
        console.print(Panel(f"[yellow]  No activity found at {time_str}.[/yellow]",
                            border_style="yellow", box=box.DOUBLE_EDGE))
    else:
        app, title, website = row
        display = website if website else title
        console.print(Panel(
            f"[bold white]  At [magenta]{time_str}[/magenta]  →  [green]{app}[/green]\n"
            f"  [cyan]{display}[/cyan][/bold white]",
            border_style="magenta", box=box.DOUBLE_EDGE
        ))

# ── NLU ────────────────────────────────────────────────────────────────────────

def understand(text):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": """You parse desktop activity tracker queries. Return ONLY valid JSON, no markdown.

{
  "query":  "top_apps" | "websites" | "app_time" | "timeline" | "what_at_time" | "open_now" | "uptime",
  "period": "today" | "yesterday" | "week" | "month",
  "app":    "<app name or null>",
  "time":   "<time string or null>",
  "reply":  "<one short sentence saying what you will show>"
}

Rules:
- most used / top apps / which app / what did I use → top_apps
- websites / browsing / which sites / internet / browser history → websites
- how much time on X / X usage / how long on X → app_time, fill app
- timeline / breakdown / full activity / what did I do → timeline
- what was I using at X / what was open at X → what_at_time, fill time
- what's open now / running apps / open software → open_now
- uptime / how long on / pc on since / system status / idle → uptime
- period defaults to today
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
        return {"query": "top_apps", "period": "today", "app": None, "time": None,
                "reply": "Let me check your activity."}

# ── Run Action ─────────────────────────────────────────────────────────────────

def run_action(parsed):
    query  = parsed.get("query",  "top_apps")
    period = parsed.get("period", "today")
    app    = parsed.get("app")
    t      = parsed.get("time")
    reply  = parsed.get("reply", "")

    if reply:
        console.print(Panel(f"[magenta dim]  {reply}[/magenta dim]",
                            border_style="magenta dim", box=box.SIMPLE_HEAD))

    if query == "top_apps":
        rows = query_top_apps(period)
        show_top_apps(rows, period)
        return rows[0][0] if rows else "no data yet"

    elif query == "websites":
        rows = query_websites(period)
        show_websites(rows, period)
        return f"{len(rows)} sites tracked"

    elif query == "app_time" and app:
        secs = query_app_time(app, period)
        show_app_time(app, secs, period)
        return format_duration(secs)

    elif query == "timeline":
        rows = query_timeline(period)
        show_timeline(rows, period)
        return f"{len(rows)} sessions"

    elif query == "what_at_time" and t:
        row = query_what_at_time(t)
        show_what_at_time(row, t)
        return row[0] if row else "nothing found"

    elif query == "open_now":
        rows, ts = query_open_now()
        show_open_now(rows, ts)
        return f"{len(rows)} apps open"

    elif query == "uptime":
        show_uptime()
        return format_duration(get_system_uptime())

    else:
        rows = query_top_apps(period)
        show_top_apps(rows, period)
        return "done"
