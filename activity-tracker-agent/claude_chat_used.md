# Activity Tracker Agent — Claude Chat Log

**Session:** 2026-04-24  
**Built by:** Claude Sonnet 4.6 (claude-sonnet-4-6)  
**User:** Dragoo (your.email@gmail.com)

---

## Chat Summary

### Exchange 1 — Agent Idea

**User:** "suggest me my new agent"

**Claude:** Suggested 5 agents (Web Search, WhatsApp, File Organizer, Notes, Browser). Recommended Web Search as next.

**User:** "no i want agent who tracks my desktop activity and shows me what i have used most and how much time"

---

### Exchange 2 — Natural Language Requirement

**Claude:** Proposed architecture with example queries listed with prefix commands.

**User:** "i dont want prefix commands i want that master agent should understand natural language and then ask this agent and this agent should also understand natural language"

**Claude:** Confirmed — same NLU pattern as Task + Email agents. Groq AI routes in master, Groq AI parses intent in activity agent. No keywords, no prefixes.

---

### Exchange 3 — Build

**Claude built:**

1. `activity-tracker-agent/agent.py` — full agent
2. `activity-tracker-agent/requirements.txt`
3. Updated `master-agent/agent.py` — added activity domain + routing
4. `activity-tracker-agent/SETUP_GUIDE.md`
5. `activity-tracker-agent/claude_chat_used.md` (this file)

---

## What Was Built

### agent.py — Key Design Decisions

**Background tracker thread:**
- `start_tracking()` called by master agent on boot
- Daemon thread — auto-exits when master agent exits
- Polls every 2 seconds via `win32gui.GetForegroundWindow()`
- On window change: logs previous session to SQLite with duration

**SQLite database (`activity.db`):**
- Auto-created in agent folder on first run
- Schema: `app_name, window_title, start_time, end_time, duration_sec`
- Persistent across reboots — full history retained

**App name cleanup:**
- `APP_NAMES` dict maps raw exe names → friendly names
- `chrome.exe` → `Google Chrome`, `code.exe` → `VS Code`, etc.
- Unknown apps: title-cased exe name

**NLU via Groq:**
- `understand(text)` calls `llama-3.1-8b-instant`
- Returns: `{"query": "top_apps"|"app_time"|"timeline"|"what_at_time", "period": "today"|"yesterday"|"week"|"month", "app": null|"appname", "time": null|"HH:MM"}`
- Handles any language / phrasing naturally

**4 query types:**
| Query type | Function | Display |
|---|---|---|
| `top_apps` | `query_top_apps()` | Rich table with % bar |
| `app_time` | `query_app_time()` | Single panel with duration |
| `timeline` | `query_timeline()` | Full session table, latest first |
| `what_at_time` | `query_what_at_time()` | Panel showing app + window title |

**Color theme:** Magenta (distinct from green/blue/yellow used by other agents)

---

### master-agent/agent.py Changes

1. Added `ACTIVITY_PATH` constant
2. Added `activity_mod = load_module(ACTIVITY_PATH, "activity_agent")` in boot
3. Added `activity_mod.start_tracking()` after `task_mod.start_reminder_thread()`
4. Updated routing prompt — added `activity` domain description
5. Updated `DOMAIN_ICON` and `DOMAIN_COLOR` — magenta for activity
6. Added routing handler block for `domain == "activity"`
7. Added hint row in the command reference table

---

## Files Changed This Session

| File | Action |
|---|---|
| `activity-tracker-agent/agent.py` | Created |
| `activity-tracker-agent/requirements.txt` | Created |
| `activity-tracker-agent/SETUP_GUIDE.md` | Created |
| `activity-tracker-agent/claude_chat_used.md` | Created |
| `master-agent/agent.py` | Updated (activity routing added) |

---

## Install Command

```bash
cd "Agents/activity-tracker-agent"
pip install -r requirements.txt
```

---

## Future Ideas (not built yet)

- Daily productivity report (spoken on boot: "Yesterday you spent 3h on VS Code")
- Idle time detection (no active window)
- Category grouping (Work / Entertainment / Social / System)
- Export to CSV for deeper analysis

