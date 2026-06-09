# Dragoo AI Agents

A suite of 6 AI-powered agents controlled by a master orchestrator. Speak or type naturally — the master agent figures out which agent to call and gets the job done.

Built with **Groq AI (free)**, **Python**, and **Google APIs**.

---

## What It Does

| Agent | What you can say | What it does |
|---|---|---|
| **Master Agent** | *(runs all others)* | Routes your request to the right agent automatically |
| **Email Agent** | "Check my inbox" / "Reply to email 2" | Reads, sends, replies, forwards, archives Gmail |
| **Task Agent** | "Remind me to call mom at 6pm" | Adds tasks, syncs to Google Calendar, desktop popups |
| **Activity Agent** | "What did I use most today?" | Tracks which apps you used and for how long |
| **WhatsApp Agent** | "Send gf a WhatsApp saying I'm home" | Sends WhatsApp messages by contact name |
| **Search Agent** | "Weather in Delhi" / "IPL score" | Live web search — news, weather, scores, facts |

All agents support **voice input** (hold SPACE to speak).

---

## Folder Structure

```
Dragoo-AI-Agents/
├── master-agent/          ← Start here — runs all agents together
├── email-agent/           ← Gmail management
├── task-reminder-agent/   ← Tasks + Google Calendar
├── activity-tracker-agent/← Desktop usage tracking
├── web-search-agent/      ← Web search
└── whatsapp-agent/        ← WhatsApp messaging
```

---

## Prerequisites

Before you start, make sure you have:

| Requirement | Why | How to get it |
|---|---|---|
| Python 3.9+ | Runs all agents | https://python.org/downloads — check "Add to PATH" |
| Node.js 18+ | WhatsApp bridge only | https://nodejs.org |
| Groq account (free) | AI engine for all agents | https://groq.com |
| Google account | Email + Calendar agents | You already have one |

---

## Step 1 — Get Your Groq API Key (Free)

1. Go to https://console.groq.com/keys
2. Click **Create API Key**
3. Copy the key — it looks like `gsk_xxxxxxxxxxxxxxxxxxxx`
4. Keep it safe — you will paste it into `.env` files below

> Groq is 100% free. No credit card needed.

---

## Step 2 — Clone the Repository

```bash
git clone https://github.com/Thakur-keshav-parmar/Dragoo-AI-Agents.git
cd Dragoo-AI-Agents
```

---

## Step 3 — Set Up Each Agent

### Master Agent + Email Agent + Search Agent + Activity Agent

Each of these agents needs a `.env` file with your Groq key.

Go into each folder and create a `.env` file:

```bash
cd master-agent
copy .env.example .env
```

Open `.env` and replace `your_groq_api_key_here` with your actual Groq key:

```
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
```

Repeat for `email-agent/`, `task-reminder-agent/` (already has `.env.example`).

> The `web-search-agent` and `activity-tracker-agent` share the master agent's Groq key automatically when run through master. If running standalone, create a `.env` in their folders too.

---

### Task Agent + Email Agent — Google Setup Required

These two agents connect to your Google account (Calendar and Gmail).

**Follow the full step-by-step guide inside:**
- `task-reminder-agent/SETUP_GUIDE.md` — Google Calendar setup
- `email-agent/SETUP_GUIDE.md` — Gmail setup

**Summary of what you will do:**
1. Create a free Google Cloud project
2. Enable the Calendar API and/or Gmail API
3. Create OAuth credentials (Desktop app type)
4. Download the `credentials.json` file
5. Place it inside `task-reminder-agent/` folder
6. On first run, a browser window opens — sign in and allow access
7. A `token.json` is saved automatically — you won't need to sign in again

---

### WhatsApp Agent — Node.js Setup Required

```bash
cd whatsapp-agent/bridge
npm install
```

On first run, a QR code appears in the terminal. Scan it with WhatsApp on your phone (Settings → Linked Devices → Link a Device).

**Full guide:** `whatsapp-agent/SETUP_GUIDE.md`

---

## Step 4 — Install Python Libraries

Run this from inside each agent folder, OR run it once from the root:

```bash
# Task Agent
cd task-reminder-agent
pip install -r requirements.txt

# Email Agent
cd ../email-agent
pip install -r requirements.txt

# Master Agent
cd ../master-agent
pip install -r requirements.txt

# Activity Tracker
cd ../activity-tracker-agent
pip install -r requirements.txt

# Web Search Agent
cd ../web-search-agent
pip install -r requirements.txt

# WhatsApp Agent
cd ../whatsapp-agent
pip install -r requirements.txt
```

---

## Step 5 — Run

### Run All Agents Together (Recommended)

```bash
cd master-agent
python agent.py
```

The master agent loads all sub-agents, connects to Gmail and Google Calendar, starts the WhatsApp bridge, and waits for your input.

### Run a Single Agent

```bash
cd email-agent
python agent.py

cd task-reminder-agent
python agent.py

cd web-search-agent
python agent.py
```

---

## How to Use

Type naturally and press Enter. Or type `v` + Enter to use voice (hold SPACE to speak, release to stop).

```
◈ INPUT ► check my inbox
◈ INPUT ► remind me to drink water at 8pm
◈ INPUT ► what did I use most today
◈ INPUT ► send mom a WhatsApp saying I reached home
◈ INPUT ► weather in Mumbai tomorrow
◈ INPUT ► reply to email 2 saying I'll get back by Friday
◈ INPUT ► v
```

Type `quit` to exit.

---

## Files Created Automatically (Not in Repo)

These files are created on first run and are safe — they are excluded from git:

| File | Location | What it stores |
|---|---|---|
| `.env` | Each agent folder | Your Groq API key |
| `credentials.json` | `task-reminder-agent/` | Google OAuth app credentials |
| `token.json` | `task-reminder-agent/` | Your Google Calendar login session |
| `gmail_token.json` | `email-agent/` | Your Gmail login session |
| `tasks.json` | `task-reminder-agent/` | Your saved tasks |
| `activity.db` | `activity-tracker-agent/` | Your desktop usage history |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` in that agent's folder |
| Groq API error | Check your `.env` file has the correct key |
| Google Calendar not syncing | Delete `token.json` and restart — re-authenticate |
| Gmail not connecting | Delete `gmail_token.json` and restart — re-authenticate |
| WhatsApp not connecting | Run `npm install` inside `whatsapp-agent/bridge/` then restart |
| Voice not working | Check microphone is connected and not muted |
| `credentials.json` error | File must start with `{"installed":` not `{"web":` — redo Google setup |

---

## Tech Stack

| Component | Technology |
|---|---|
| AI Engine | Groq API — Llama 3.1 8B Instant (free) |
| Email | Gmail API (Google Cloud) |
| Calendar | Google Calendar API (Google Cloud) |
| WhatsApp | whatsapp-web.js + Puppeteer (Node.js) |
| Web Search | DuckDuckGo (no API key needed) |
| Activity Tracking | win32gui + SQLite |
| Terminal UI | Rich (Python) |
| Voice Input | SpeechRecognition + sounddevice |
| Text to Speech | pyttsx3 (Windows TTS) |

---

*Built with Claude AI — Dragoo Master Agent Suite v1.0*
