# WhatsApp Agent — Claude Chat Log

**Session:** 2026-05-01
**Built by:** Claude Sonnet 4.6
**User:** Dragoo (your.email@gmail.com)

---

## Key Decisions Made

| Decision | Reason |
|---|---|
| whatsapp-web.js (Node.js) over PyWhatKit | More reliable, no browser opening on every send, stays connected |
| Bridge in separate terminal window | QR code needs its own space, keeps Master Agent terminal clean |
| No LocalAuth / session persistence | User explicitly requested: fresh QR every start or after 6h idle |
| 6-hour inactivity auto-disconnect | User requirement |
| HTTP bridge on port 3001 | Clean Python↔Node communication, avoids port conflicts |
| Separate whatsapp_contacts.json | Email contacts store emails, WhatsApp contacts store phone numbers — different data |
| Same fuzzy resolve_contact logic as Email Agent | Consistent UX — "my gf" resolves to "gf" in both agents |

---

## Files Created

| File | Purpose |
|---|---|
| `bridge/package.json` | Node.js dependencies |
| `bridge/index.js` | WhatsApp Web bridge — QR, send API, inactivity watchdog |
| `agent.py` | Python NLU + contact management + HTTP calls to bridge |
| `requirements.txt` | groq, dotenv, rich, requests |
| `SETUP_GUIDE.md` | Full setup instructions |
| `claude_chat_used.md` | This file |

## Master Agent Changes

| Change | Detail |
|---|---|
| Added `WHATSAPP_PATH` | Points to whatsapp-agent/agent.py |
| Added `wa_mod` loading | Boot sequence loads WhatsApp agent |
| Added `wa_mod.start_bridge()` | Opens bridge in new console window on boot |
| Updated routing prompt | Added "whatsapp" domain |
| Updated `DOMAIN_ICON/COLOR` | Green theme for WhatsApp |
| Added whatsapp handler | Routes to `wa_mod.understand()` + `run_action()` |
| Added `wa_mod.stop_bridge()` on quit | Kills Node.js process cleanly |
| Added hint row | "Send gf a WhatsApp · WhatsApp mom I'm home" |

---

## How to Test

1. Run `npm install` in `bridge/` folder (one-time)
2. Start Master Agent
3. Bridge window opens automatically — scan QR with WhatsApp
4. Say: `save gf WhatsApp as 9876543210`
5. Say: `send gf a WhatsApp saying hello`
6. Confirm preview → message sends

