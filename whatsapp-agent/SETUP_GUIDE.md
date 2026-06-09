# WhatsApp Agent — Setup Guide

**Agent:** WhatsApp Messenger
**Folder:** `Agents/whatsapp-agent/`
**Role:** Send WhatsApp messages by contact name using natural language
**Part of:** Dragoo Master Agent Suite

---

## Part 1 — What This Agent Does

- Sends WhatsApp messages to saved contacts by name
- Resolves nicknames ("gf", "mom", "boss") to phone numbers automatically
- Asks for confirmation if multiple contacts match
- Shows a preview before every send
- Auto-disconnects after **6 hours of inactivity**
- Disconnects cleanly when Master Agent is closed

### What you can say:
| Example | What happens |
|---|---|
| "Send gf a WhatsApp that I'll be late" | Resolves gf → sends instantly |
| "WhatsApp mom I'm coming home" | Finds mom in contacts → sends |
| "Message Rahul the meeting link" | Finds Rahul → you type message |
| "Save gf WhatsApp as 9876543210" | Adds to contacts |
| "Show WhatsApp contacts" | Lists all saved contacts |
| "WhatsApp status" | Shows connection + idle time |

---

## Part 2 — Prerequisites

### Step 1 — Node.js
Install from: https://nodejs.org (LTS version)
Check: `node --version`

### Step 2 — Install Node dependencies
```bash
cd "Agents/whatsapp-agent/bridge"
npm install
```
This installs: `whatsapp-web.js`, `express`, `qrcode-terminal`
(Takes 2-3 minutes, downloads Chromium)

### Step 3 — Python dependencies
```bash
cd "Agents/whatsapp-agent"
pip install -r requirements.txt
```
requirements: `groq`, `python-dotenv`, `rich`, `requests`

### Step 4 — No extra API keys needed
Uses your existing `GROQ_API_KEY` from Master Agent's `.env`

---

## Part 3 — File Structure

```
whatsapp-agent/
├── agent.py                  ← Python agent (NLU + contacts + HTTP calls)
├── bridge/
│   ├── index.js              ← Node.js WhatsApp bridge (HTTP API)
│   ├── package.json          ← Node dependencies
│   └── node_modules/         ← auto-created by npm install
├── whatsapp_contacts.json    ← saved contacts (auto-created)
├── requirements.txt
├── SETUP_GUIDE.md
└── claude_chat_used.md
```

---

## Part 4 — How It Works

```
Master Agent boots
    → loads whatsapp_agent module
    → calls wa_mod.start_bridge()
    → Node.js opens in NEW terminal window
    → QR code appears in that window

User scans QR with WhatsApp
    → bridge shows "CONNECTED"
    → ready to send

User says: "WhatsApp gf I'll be late"
    → Master Agent routes to "whatsapp" domain
    → wa_mod.understand() → Groq parses: {action: send, to: gf, message: "I'll be late"}
    → resolve_contact("gf") → finds phone number
    → shows preview → user confirms
    → Python POSTs to http://localhost:3001/send
    → Node.js sends via WhatsApp Web
```

### Session Rules:
- **Fresh QR every start** — no session saved to disk
- **6 hours idle** → auto-disconnect (bridge logs warning)
- **Agent closed** → bridge process terminated

---

## Part 5 — Phone Number Format

Numbers are stored and sent in `91XXXXXXXXXX` format (India):

| Input | Stored as |
|---|---|
| `9876543210` | `919876543210` |
| `09876543210` | `919876543210` |
| `+919876543210` | `919876543210` |

For international numbers, enter with full country code: `447911123456` (UK)

---

## Part 6 — Contacts

Saved in `whatsapp_contacts.json`:
```json
{
  "gf": {"name": "GF", "phone": "919876543210"},
  "mom": {"name": "Mom", "phone": "919876543211"},
  "rahul": {"name": "Rahul", "phone": "919876543212"}
}
```

**Fuzzy matching** — works both directions:
- Say "my gf" → finds contact "gf" ✓
- Say "rah" → finds "Rahul" ✓
- Multiple matches → shows numbered list, asks to pick

---

## Part 7 — Troubleshooting

| Problem | Fix |
|---|---|
| `node: command not found` | Install Node.js from nodejs.org |
| Bridge window doesn't open | Run `node index.js` manually in bridge/ folder |
| QR not appearing | Wait 30-60 seconds, Chromium is loading |
| "WhatsApp not connected" | Scan QR in the bridge window |
| QR expired | Restart Master Agent — fresh QR every start |
| Message fails to send | Check bridge window for error details |
| `npm install` fails | Run as Administrator, or delete node_modules and retry |

---

## Part 8 — Key Decisions

| Decision | Why |
|---|---|
| No session persistence | User wanted fresh QR every session or after 6h idle |
| Separate Node.js window | QR code is large — needs its own terminal |
| HTTP bridge pattern | Lets Python control Node.js cleanly |
| Port 3001 | Avoids conflict with other local services |
| Same contacts as Email Agent | Separate files — email needs email addresses, WhatsApp needs phone numbers |

---

## Part 9 — Update Rule

Per standing rule: **whenever agent.py or index.js changes, update SETUP_GUIDE.md and claude_chat_used.md too.**
