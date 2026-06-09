# Web Search Agent — Setup Guide

**Agent:** Web Search
**Folder:** `Agents/web-search-agent/`
**Role:** Real-time web search — weather, news, scores, facts, prices
**Part of:** Dragoo Master Agent Suite

---

## Part 1 — What This Agent Does

Answers anything that requires current/live information by searching the web via DuckDuckGo and summarizing the results using Groq AI.

| You ask | What happens |
|---|---|
| "Weather in Delhi today" | Searches + summarizes weather |
| "IPL score today" | Searches latest news |
| "Latest news about AI" | News search + summary |
| "Price of iPhone 15 in India" | Web search + summary |
| "Who won the election?" | News search + answer |
| "What is quantum computing?" | Web search + explanation |

---

## Part 2 — Prerequisites

### Step 1 — Install Python dependency
```bash
pip install duckduckgo-search
```
No API key needed. Completely free and unlimited.

### Step 2 — Groq API key
Already available from Master Agent's `.env` — no extra setup.

---

## Part 3 — File Structure

```
web-search-agent/
├── agent.py          ← NLU + DuckDuckGo search + Groq summarizer
├── requirements.txt  ← groq, dotenv, rich, duckduckgo-search
├── SETUP_GUIDE.md
└── claude_chat_used.md
```

---

## Part 4 — How It Works

```
User: "What's the weather in Mumbai?"
    ↓
Master Agent routes to "search" domain
    ↓
search_mod.understand() → Groq parses:
  {query_type: "weather", query: "Mumbai weather today"}
    ↓
DuckDuckGo returns 5 web results
    ↓
Groq reads results → clean summarized answer
    ↓
Rich panel display + TTS speaks the answer
```

### Query Types:
| Type | When used |
|---|---|
| `weather` | Weather/temperature/forecast queries |
| `news` | Latest news, live scores, current events |
| `web` | Everything else — facts, prices, info |

---

## Part 5 — Key Decisions

| Decision | Why |
|---|---|
| DuckDuckGo over Google/Serper | Free, no API key, no rate limits |
| Groq summarizes results | Raw search snippets are messy — AI gives clean answers |
| Yellow color theme | Distinct from all other agents |
| Hindi/Hinglish queries translated | DuckDuckGo works better with English queries |
| Sources shown after answer | Transparency — user can verify |

---

## Part 6 — Update Rule

Per standing rule: **whenever agent.py changes, update SETUP_GUIDE.md and claude_chat_used.md too.**
