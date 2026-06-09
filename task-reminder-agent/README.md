# Task Reminder Agent

AI-powered task manager with natural language input and Windows desktop notifications.

## Setup (Do this once)

1. Install Python from python.org if not installed
2. Open terminal in this folder
3. Run: pip install -r requirements.txt
4. Copy .env.example to .env
5. Paste your Groq API key in .env

## Run

```
python agent.py
```

## Usage Examples

When you type `add`, you can say things like:
- "Remind me to call mom at 6pm"
- "Add a high priority task to submit report tomorrow at 10am"
- "Buy groceries today at 5:30pm"

## Commands

| Command | What it does |
|---------|-------------|
| add     | Add task using natural language |
| list    | See all tasks |
| done    | Mark a task complete |
| delete  | Remove a task |
| quit    | Exit the agent |
