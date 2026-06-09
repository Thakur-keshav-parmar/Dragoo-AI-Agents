import os
import re
import json
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv
from duckduckgo_search import DDGS
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich import box

load_dotenv()
client  = Groq(api_key=os.environ.get("GROQ_API_KEY"))
console = Console()

# ── Search ─────────────────────────────────────────────────────────────────────

def web_search(query, max_results=5):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results
    except Exception as e:
        return []

def news_search(query, max_results=5):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
        return results
    except Exception as e:
        return []

# ── AI Summarizer ──────────────────────────────────────────────────────────────

def summarize(query, results, query_type):
    if not results:
        return "Sorry, I couldn't find any results for that.", []

    # Build context from search results
    context = ""
    sources = []
    for i, r in enumerate(results, 1):
        title   = r.get("title", "")
        body    = r.get("body", r.get("excerpt", ""))
        url     = r.get("url", r.get("link", ""))
        date    = r.get("date", "")
        context += f"[{i}] {title}\n{body}\n"
        if url:
            sources.append({"title": title[:60], "url": url, "date": date})

    now = datetime.now().strftime("%d %B %Y, %H:%M")

    if query_type == "weather":
        system = (
            f"Today is {now}. You are a helpful assistant. "
            "From the search results, extract the weather information clearly. "
            "Give temperature, conditions, and any forecast. Be concise and clear. "
            "If the results don't have exact weather data, summarize what's available."
        )
    elif query_type == "news":
        system = (
            f"Today is {now}. You are a news summarizer. "
            "From these search results, give a clear summary of the latest news on this topic. "
            "Mention key facts and dates. Keep it under 5 sentences."
        )
    else:
        system = (
            f"Today is {now}. You are a helpful search assistant. "
            "Answer the user's question using ONLY the information from these search results. "
            "Be direct, clear, and concise. If results don't fully answer it, say so. "
            "Do not make up information not present in the results."
        )

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": f"Question: {query}\n\nSearch results:\n{context}"}
            ]
        )
        return response.choices[0].message.content.strip(), sources
    except Exception as e:
        return f"Search completed but summary failed: {e}", sources

# ── NLU ────────────────────────────────────────────────────────────────────────

def understand(text):
    now = datetime.now().strftime("%d %B %Y")
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": f"""Today is {now}. You parse web search requests.

Return ONLY valid JSON (no markdown):
{{
  "query_type": "weather" | "news" | "web",
  "query":      "<optimized search query to use — in English>",
  "reply":      "<one short sentence saying what you will search>"
}}

Rules:
- Weather / temperature / forecast → weather, query = "city name weather today"
- News / latest / current events / scores / live → news
- Everything else → web
- query: make it a good search query (add context like year/country if helpful)
- If user wrote in Hindi/Hinglish, translate the query to English for better results
- ONLY JSON."""
            },
            {"role": "user", "content": text}
        ]
    )
    raw = response.choices[0].message.content.strip().replace("```json", "").replace("```", "").strip()
    raw = re.sub(r",\s*}", "}", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"query_type": "web", "query": text, "reply": "Let me search that for you."}

# ── Display ────────────────────────────────────────────────────────────────────

def show_answer(query, answer, sources, query_type):
    # Answer panel
    icon = {"weather": "🌤", "news": "📰", "web": "🔍"}.get(query_type, "🔍")
    console.print(Panel(
        f"[bold white]{answer}[/bold white]",
        title=f"[bold yellow]  {icon}  {query.upper()}  [/bold yellow]",
        border_style="yellow", box=box.DOUBLE_EDGE,
        padding=(1, 2)
    ))

    # Sources table
    if sources:
        t = Table(
            title="[dim yellow]  SOURCES  [/dim yellow]",
            border_style="yellow dim", box=box.SIMPLE_HEAD,
            show_header=True, header_style="dim yellow"
        )
        t.add_column("#",      style="yellow dim", width=3, justify="center")
        t.add_column("Title",  style="white dim",  min_width=40)
        t.add_column("Date",   style="dim",        width=12)
        for i, s in enumerate(sources[:5], 1):
            date = s.get("date", "")[:10] if s.get("date") else "—"
            t.add_row(str(i), s["title"], date)
        console.print(t)

# ── Run Action ─────────────────────────────────────────────────────────────────

def run_action(parsed):
    query_type = parsed.get("query_type", "web")
    query      = parsed.get("query", "")
    reply      = parsed.get("reply", "")

    if not query:
        console.print(Panel("[yellow]  No search query found.[/yellow]",
                            border_style="yellow", box=box.DOUBLE_EDGE))
        return ""

    if reply:
        console.print(Panel(
            f"[yellow dim]  {reply}[/yellow dim]",
            border_style="yellow dim", box=box.SIMPLE_HEAD
        ))

    # Search
    with console.status(f"[yellow dim]  ◈ SEARCHING: {query}...[/yellow dim]", spinner="aesthetic"):
        if query_type == "news":
            results = news_search(query, max_results=5)
            if not results:
                results = web_search(query, max_results=5)
        else:
            results = web_search(query, max_results=5)

    if not results:
        console.print(Panel(
            "[yellow]  No results found. Try rephrasing your question.[/yellow]",
            border_style="yellow", box=box.DOUBLE_EDGE
        ))
        return ""

    # Summarize
    with console.status("[yellow dim]  ◈ SUMMARIZING...[/yellow dim]", spinner="aesthetic"):
        answer, sources = summarize(query, results, query_type)

    show_answer(query, answer, sources, query_type)
    return answer
