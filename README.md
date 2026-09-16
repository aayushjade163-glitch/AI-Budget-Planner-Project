# Ledger - AI Budget Planner (Agent Chatbot)

A chatbot that plans your monthly budget. You talk to it in plain language and
it records your income, expenses and savings goals on its own, then tells you
where the money is going.

No database is used. Everything is stored in memory while the server runs, so
closing the server clears the budget.

---

## 1. What you need

* Python 3.9 or newer
* A **free** Groq API key from https://console.groq.com/keys (sign in with
  Google/GitHub, no card needed)
* Internet access (the app calls the API)

## 2. Add your API key

Open `app.py` and paste the key on line 21:

```python
API_KEY = "gsk_xxxxxxxxxxxxxxxxxxxx"
```

Or, if you prefer not to keep it in the file:

```bash
# Windows
set GROQ_API_KEY=gsk_xxxx
# macOS / Linux
export GROQ_API_KEY=gsk_xxxx
```

You can also change the model or currency in the same block:

```python
MODEL = "openai/gpt-oss-120b"
CURRENCY = "Rs."
```

Other free models you can swap in on Groq: `openai/gpt-oss-20b` (faster,
lighter), `qwen/qwen3.8-27b`, `groq/compound` (adds web search/code tools).
Note that Groq retired `llama-3.3-70b-versatile` and `llama-3.1-8b-instant`
from free/developer access in mid-2026 (they're now enterprise-only), so
don't use those. Check current names at https://console.groq.com/docs/models
since Groq periodically retires models.

## 3. Run it

**Quick way** - double click `run.bat` (Windows) or run `./run.sh` (macOS/Linux).

**Manual way:**

```bash
cd ai-budget-planner
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 in your browser.

## 4. Try these messages

* `I earn 45000 a month from my internship`
* `Rent is 12000, food about 8000, and I spend 3000 on travel`
* `Where is most of my money going?`
* `I want to save 60000 for a laptop in 8 months, is that possible?`
* `Cut my budget so I can save at least 20 percent`

Entries the agent creates appear instantly in the ledger on the left. You can
also add or delete entries yourself using the form in the sidebar.

---

## 5. How it works

```
Browser (chat UI)
      |  JSON over fetch()
      v
Flask app.py  ---- builds a prompt: system rules + budget snapshot + message
      |
      v
Groq Chat Completions API (OpenAI-compatible, free tier)
      |
      v
Reply as JSON: { "reply": "...", "actions": [ ... ] }
      |
      +--> reply text goes to the chat
      +--> actions are executed on the in-memory budget
```

The agent behaviour comes from `SYSTEM_PROMPT` in `app.py`. It forces the model
to answer with a single JSON object containing a message and a list of actions
such as `add_income`, `add_expense`, `add_goal`, `remove` and `clear`. The
backend validates each action before applying it, so a malformed action is
skipped instead of crashing the app. The last twelve chat turns are sent back
each time so the agent remembers the conversation.

## 6. Files

| File | Purpose |
|---|---|
| `app.py` | Flask server, API call, agent logic, in-memory budget |
| `templates/index.html` | Page layout |
| `static/style.css` | Styling |
| `static/app.js` | Chat behaviour and ledger rendering |
| `requirements.txt` | Python packages |
| `run.sh` / `run.bat` | One-step setup and start |

## 7. Common problems

| Message | Fix |
|---|---|
| "No API key found" | Key not pasted in `app.py` or env variable not set |
| `API error 401` | Key is wrong or expired |
| `API error 404` | Model name retired - use `openai/gpt-oss-120b` or check https://console.groq.com/docs/models |
| `API error 429` | Free-tier rate limit hit - wait a bit or switch to a smaller model like `openai/gpt-oss-20b` |
| Port already in use | Change `port=5000` at the bottom of `app.py` |
| Budget empty after restart | Expected - there is no database |

## 8. Ideas to extend it

* Save the budget to a JSON file so it survives a restart
* Add a pie chart of expense categories with Chart.js
* Let the agent compare this month against last month
* Add a monthly limit per category and warn when it is crossed
