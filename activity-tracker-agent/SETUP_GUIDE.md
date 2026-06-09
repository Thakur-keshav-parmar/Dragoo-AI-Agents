# Activity Tracker Agent — Setup Guide

**Agent:** Desktop Activity Tracker  
**Folder:** `Agents/activity-tracker-agent/`  
**Role:** Tracks which apps are open on the desktop, how long, and answers natural language queries about usage  
**Part of:** Dragoo Master Agent Suite

---

## Part 1 — What This Agent Does

- Runs a **background thread** that polls the active window every 2 seconds
- Stores sessions in a local **SQLite database** (`activity.db`) — no cloud, no external service
- Answers natural language questions via **Groq AI (llama-3.1-8b-instant)**
- Is loaded and started automatically by the **Master Orchestrator Agent** on boot
- Magenta color theme in the Rich terminal UI

### What you can ask (all natural language, no prefixes):
| Example Query | What it does |
|---|---|
| "What did I use most today?" | Top 10 apps by time, with percentage bar |
| "How much time on Chrome this week?" | Single app duration for the period |
| "Show me everything I did today" | Full timeline, latest first |
| "What was I using at 3pm?" | Looks up the active window at that time |
| "Aaj sabse zyada kya use kiya?" | Same as first — Groq handles any language |

---

## Part 2 — Prerequisites

### Step 1 — Python
Python 3.9+ installed. Check: `python --version`

### Step 2 — Groq API Key
Already set in `master-agent/.env`. The activity agent uses the same key via `load_dotenv()`.

### Step 3 — Install Dependencies
```bash
cd "Agents/activity-tracker-agent"
pip install -r requirements.txt
```

**requirements.txt includes:**
```
groq
python-dotenv
rich
pywin32
psutil
```

> `pywin32` — Windows-only. Provides `win32gui` and `win32process` to get the active window.  
> `psutil` — Cross-platform. Gets the process name (exe) from the window's PID.

### Step 4 — No .env needed here
The agent reads `GROQ_API_KEY` from environment. When run via the Master Agent, the Master Agent's `.env` is already loaded.

---

## Part 3 — File Structure

```
activity-tracker-agent/
├── agent.py          ← main agent (tracker + NLU + display)
├── activity.db       ← SQLite DB (auto-created on first run)
├── requirements.txt
├── SETUP_GUIDE.md    ← this file
└── claude_chat_used.md
```

> `activity.db` is created automatically the first time tracking starts. It persists across reboots — all your history stays.

---

## Part 4 — How It Works (Technical)

### Background Tracker Thread
```
Master Agent boots
    → activity_mod.start_tracking() called
    → daemon thread starts (tracker_loop)
    → polls every 2 seconds: get_active_window()
    → on window change: log previous session to SQLite
    → thread runs until process exits
```

### SQLite Schema
```sql
CREATE TABLE activity_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name     TEXT,       -- cleaned: "Google Chrome" not "chrome.exe"
    window_title TEXT,       -- exact window title
    start_time   TEXT,       -- ISO format: 2026-04-24T14:30:00
    end_time     TEXT,
    duration_sec INTEGER     -- seconds spent on this window
);
```

### NLU Flow
```
User says: "aaj chrome pe kitna time gaya"
    ↓
Master Agent routes to "activity" domain
    ↓
activity_mod.understand(text) → Groq AI
    → returns: {"query": "app_time", "period": "today", "app": "chrome", ...}
    ↓
activity_mod.run_action(parsed) → queries SQLite → Rich table display
    ↓
Master Agent speaks the result
```

### App Name Cleanup
Raw process names (`chrome.exe`, `code.exe`) are mapped to friendly names via `APP_NAMES` dict:
- `chrome` → `Google Chrome`
- `code` → `VS Code`
- `pycharm64` → `PyCharm`
- Unknown apps → title-cased exe name

---

## Part 5 — Key Functions

| Function | What it does |
|---|---|
| `start_tracking()` | Starts the background thread, inits DB |
| `tracker_loop()` | Polls every 2s, logs on window change |
| `understand(text)` | Groq NLU → returns parsed JSON intent |
| `run_action(parsed)` | Routes to correct query + display function |
| `query_top_apps(period)` | Top apps by total time for a period |
| `query_app_time(app, period)` | Time for a single app |
| `query_timeline(period)` | Full session list, latest first |
| `query_what_at_time(time_str)` | What was active at a specific time |
| `format_duration(seconds)` | `3661` → `"1h 1m"` |

---

## Part 6 — Periods Supported

| What user says | Period |
|---|---|
| "today" (default) | 12:00am to now |
| "yesterday" | Full previous day |
| "this week" / "week" | Monday to now |
| "this month" / "month" | 1st of month to now |

---

## Part 7 — Master Agent Integration

### In `master-agent/agent.py`:
```python
ACTIVITY_PATH = os.path.join(BASE_DIR, "..", "activity-tracker-agent", "agent.py")

# Boot:
activity_mod = load_module(ACTIVITY_PATH, "activity_agent")
activity_mod.start_tracking()   # starts background thread silently

# Routing prompt includes:
# "activity : desktop activity tracking, app usage, time spent, what was open"

# Handler:
elif domain == "activity" and activity_mod:
    parsed = activity_mod.understand(user_input)
    result = activity_mod.run_action(parsed)
    speak(parsed.get("reply", ""))
```

### Display theme: **Magenta** (distinct from task=green, email=blue, general=yellow)

---

## Part 8 — Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: win32gui` | `pip install pywin32` |
| `ModuleNotFoundError: psutil` | `pip install psutil` |
| All apps show as "Unknown" | pywin32 not installed or not working |
| `activity.db` not created | `start_tracking()` not called — check master agent boot |
| No data for query | Tracker just started, wait a few minutes |
| Groq JSON parse error | Rare — agent defaults to `top_apps/today` |

---

## Part 9 — Key Decisions

| Decision | Why |
|---|---|
| SQLite (not file/JSON) | Fast queries, persistent, zero server needed |
| 2-second poll interval | Low CPU overhead, sufficient granularity |
| Daemon thread | Auto-stops when master agent exits, no cleanup needed |
| App name map (APP_NAMES dict) | Raw exe names are ugly — maps to friendly names |
| Groq for NLU | Same AI engine as other agents, no extra cost |
| Magenta color | Distinct from all other agent colors |
| DB stored in agent folder | Self-contained, easy to backup or reset |

---

## Part 10 — Updating This Agent

Per the standing rule: **whenever agent.py changes, update this file and `claude_chat_used.md` too.**

Files to update on any code change:
1. `agent.py` — the change itself
2. `SETUP_GUIDE.md` — reflect any new functions, settings, or behaviors
3. `claude_chat_used.md` — log what was changed and why
