"""
AI Budget Planner - Agent Chatbot
---------------------------------
A small Flask app where you chat with an AI budgeting agent.
The agent can read your budget and add/remove entries itself.

No database. All data lives in memory and is cleared when the server stops.
"""

import json
import os
import re
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template, request

# ---------------------------------------------------------------------------
# 1. CONFIGURATION  --  PUT YOUR FREE GROQ API KEY HERE
# ---------------------------------------------------------------------------
# Groq gives free API access to fast open-weight models (Llama, etc).
# Get a free key at https://console.groq.com/keys (just needs a Google/GitHub
# login, no card required at time of writing).
#
# Either paste the key between the quotes below, or set the environment
# variable GROQ_API_KEY before starting the server.

API_KEY = "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"          # <-- paste your key here, e.g. "gsk_..."

MODEL = "openai/gpt-oss-120b"   # free Groq model; see console.groq.com/docs/models
API_URL = "https://api.groq.com/openai/v1/chat/completions"
CURRENCY = "Rs."               # change to "$", "EUR " etc.
MAX_TOKENS = 1200

API_KEY = API_KEY or os.environ.get("GROQ_API_KEY", "")

app = Flask(__name__)

# ---------------------------------------------------------------------------
# 2. IN-MEMORY STATE (no database)
# ---------------------------------------------------------------------------
STATE = {
    "income": [],       # {id, source, amount}
    "expenses": [],     # {id, category, amount, note}
    "goals": [],        # {id, name, target, saved}
    "history": [],      # chat turns sent back to the model
}
_counter = {"n": 0}


def new_id():
    _counter["n"] += 1
    return _counter["n"]


def totals():
    inc = sum(i["amount"] for i in STATE["income"])
    exp = sum(e["amount"] for e in STATE["expenses"])
    return {
        "income": round(inc, 2),
        "expenses": round(exp, 2),
        "balance": round(inc - exp, 2),
        "savings_rate": round((inc - exp) / inc * 100, 1) if inc else 0.0,
    }


def snapshot():
    return {
        "income": STATE["income"],
        "expenses": STATE["expenses"],
        "goals": STATE["goals"],
        "totals": totals(),
    }


# ---------------------------------------------------------------------------
# 3. THE AGENT
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = f"""You are Ledger, a personal budget planning agent.

You help one user plan, track and improve a monthly budget. Money is shown in
{CURRENCY}. Today is {{today}}.

You do not just talk - you act. Whenever the user mentions money coming in,
money going out, or a savings goal, record it yourself instead of asking them
to type it somewhere. Never invent numbers the user did not give you.

The user's current budget is given to you as JSON before each message.

You must reply with a single JSON object and nothing else. No markdown fences,
no text outside the object. The shape is:

{{{{
  "reply": "what you say to the user, plain text, 1-6 short sentences",
  "actions": [ ... zero or more actions ... ]
}}}}

Allowed actions:
  {{{{"type": "add_income",  "source": "Salary",   "amount": 45000}}}}
  {{{{"type": "add_expense", "category": "Rent",   "amount": 12000, "note": "flat"}}}}
  {{{{"type": "add_goal",    "name": "Laptop",     "target": 60000, "saved": 5000}}}}
  {{{{"type": "remove",      "list": "expenses",   "id": 3}}}}
  {{{{"type": "clear",       "list": "expenses"}}}}

Rules for the reply text:
- Be concrete. Quote real figures from the budget, not vague advice.
- When the budget is in deficit, say so plainly and name the two or three
  categories worth cutting first.
- Keep a friendly, practical tone. No bullet lists longer than four items.
- If the user asks something unrelated to money, answer briefly and steer back.
"""


def call_groq(user_message):
    """Send the conversation plus budget snapshot to the Groq API."""
    if not API_KEY:
        raise RuntimeError(
            "No API key found. Open app.py and paste your key into API_KEY, "
            "or set the GROQ_API_KEY environment variable."
        )

    context = json.dumps(snapshot(), indent=None)
    system_msg = {
        "role": "system",
        "content": SYSTEM_PROMPT.format(today=datetime.now().strftime("%d %B %Y")),
    }
    messages = [system_msg] + STATE["history"][-12:] + [{
        "role": "user",
        "content": f"[current budget]\n{context}\n\n[user]\n{user_message}",
    }]

    response = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "messages": messages,
            "response_format": {"type": "json_object"},
        },
        timeout=90,
    )

    if response.status_code != 200:
        raise RuntimeError(f"API error {response.status_code}: {response.text[:300]}")

    data = response.json()
    return data["choices"][0]["message"]["content"]


def parse_agent_output(text):
    """The model is asked for pure JSON, but be forgiving if it wraps it."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned, flags=re.MULTILINE).strip()
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            return {"reply": cleaned or "I did not get a usable reply.", "actions": []}
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"reply": cleaned, "actions": []}
    return {
        "reply": obj.get("reply", ""),
        "actions": obj.get("actions", []) or [],
    }


def apply_actions(actions):
    """Run the agent's actions against the in-memory budget."""
    applied = []
    for act in actions:
        kind = act.get("type")
        try:
            if kind == "add_income":
                item = {
                    "id": new_id(),
                    "source": str(act.get("source", "Income"))[:40],
                    "amount": round(float(act["amount"]), 2),
                }
                STATE["income"].append(item)
                applied.append(f"income +{item['amount']}")

            elif kind == "add_expense":
                item = {
                    "id": new_id(),
                    "category": str(act.get("category", "Other"))[:40],
                    "amount": round(float(act["amount"]), 2),
                    "note": str(act.get("note", ""))[:60],
                }
                STATE["expenses"].append(item)
                applied.append(f"expense +{item['amount']}")

            elif kind == "add_goal":
                item = {
                    "id": new_id(),
                    "name": str(act.get("name", "Goal"))[:40],
                    "target": round(float(act.get("target", 0)), 2),
                    "saved": round(float(act.get("saved", 0)), 2),
                }
                STATE["goals"].append(item)
                applied.append(f"goal {item['name']}")

            elif kind == "remove":
                lst = act.get("list")
                if lst in ("income", "expenses", "goals"):
                    before = len(STATE[lst])
                    STATE[lst] = [x for x in STATE[lst] if x["id"] != int(act["id"])]
                    if len(STATE[lst]) < before:
                        applied.append(f"removed from {lst}")

            elif kind == "clear":
                lst = act.get("list")
                if lst in ("income", "expenses", "goals"):
                    STATE[lst] = []
                    applied.append(f"cleared {lst}")
        except (KeyError, TypeError, ValueError):
            continue        # ignore a malformed action, keep the rest
    return applied


# ---------------------------------------------------------------------------
# 4. ROUTES
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", currency=CURRENCY, has_key=bool(API_KEY))


@app.route("/api/budget")
def get_budget():
    return jsonify(snapshot())


@app.route("/api/chat", methods=["POST"])
def chat():
    user_message = (request.json or {}).get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Type a message first."}), 400

    try:
        raw = call_groq(user_message)
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 400
    except requests.RequestException:
        return jsonify({"error": "Could not reach the API. Check your connection."}), 502

    result = parse_agent_output(raw)
    applied = apply_actions(result["actions"])

    STATE["history"].append({"role": "user", "content": user_message})
    STATE["history"].append({"role": "assistant", "content": result["reply"]})

    return jsonify({
        "reply": result["reply"],
        "applied": applied,
        "budget": snapshot(),
    })


@app.route("/api/manual", methods=["POST"])
def manual_add():
    """Add an entry from the form in the sidebar, without the AI."""
    body = request.json or {}
    kind = body.get("kind")
    try:
        amount = round(float(body.get("amount", 0)), 2)
    except (TypeError, ValueError):
        return jsonify({"error": "Amount must be a number."}), 400
    label = str(body.get("label", "")).strip()[:40]
    if not label or amount <= 0:
        return jsonify({"error": "Add a name and an amount above zero."}), 400

    if kind == "income":
        STATE["income"].append({"id": new_id(), "source": label, "amount": amount})
    elif kind == "expense":
        STATE["expenses"].append(
            {"id": new_id(), "category": label, "amount": amount, "note": ""})
    else:
        return jsonify({"error": "Unknown entry type."}), 400
    return jsonify(snapshot())


@app.route("/api/delete", methods=["POST"])
def delete_entry():
    body = request.json or {}
    lst, entry_id = body.get("list"), body.get("id")
    if lst not in ("income", "expenses", "goals"):
        return jsonify({"error": "Unknown list."}), 400
    STATE[lst] = [x for x in STATE[lst] if x["id"] != entry_id]
    return jsonify(snapshot())


@app.route("/api/reset", methods=["POST"])
def reset():
    STATE["income"].clear()
    STATE["expenses"].clear()
    STATE["goals"].clear()
    STATE["history"].clear()
    return jsonify(snapshot())


if __name__ == "__main__":
    print("\n  AI Budget Planner running at http://127.0.0.1:5000")
    if not API_KEY:
        print("  No API key set - open app.py and fill in API_KEY (get one free")
        print("  at https://console.groq.com/keys).\n")
    app.run(debug=True, port=5000)
