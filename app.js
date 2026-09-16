const CUR = document.body.dataset.currency || "Rs.";
const thread = document.getElementById("thread");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");

const money = n => CUR + Number(n).toLocaleString(undefined, {maximumFractionDigits: 2});

/* ---------- rendering the ledger ---------- */
function renderList(el, items, nameKey, listName) {
  el.innerHTML = "";
  if (!items.length) {
    el.innerHTML = '<li class="empty">Nothing here yet.</li>';
    return;
  }
  items.forEach(item => {
    const li = document.createElement("li");
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = item[nameKey] + (item.note ? " - " + item.note : "");
    const amt = document.createElement("span");
    amt.className = "amt";
    amt.textContent = money(item.amount);
    const del = document.createElement("button");
    del.textContent = "x";
    del.title = "Remove";
    del.onclick = () => post("/api/delete", {list: listName, id: item.id}).then(paint);
    li.append(name, amt, del);
    el.appendChild(li);
  });
}

function paint(b) {
  document.getElementById("t-income").textContent = money(b.totals.income);
  document.getElementById("t-expense").textContent = money(b.totals.expenses);
  document.getElementById("t-balance").textContent = money(b.totals.balance);
  document.getElementById("t-rate").textContent = b.totals.savings_rate + "%";
  document.getElementById("headline").textContent = money(b.totals.balance);

  const bal = document.getElementById("t-balance");
  bal.className = b.totals.balance < 0 ? "debit" : "credit";

  renderList(document.getElementById("list-income"), b.income, "source", "income");
  renderList(document.getElementById("list-expenses"), b.expenses, "category", "expenses");

  const goalsBlock = document.getElementById("goals-block");
  goalsBlock.hidden = !b.goals.length;
  if (b.goals.length) {
    const el = document.getElementById("list-goals");
    el.innerHTML = "";
    b.goals.forEach(g => {
      const li = document.createElement("li");
      li.innerHTML = `<span class="name">${g.name}</span>
                      <span class="amt">${money(g.saved)} / ${money(g.target)}</span>`;
      el.appendChild(li);
    });
  }
}

/* ---------- messages ---------- */
function bubble(cls, text, applied) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  text.split(/\n{2,}/).forEach(part => {
    const p = document.createElement("p");
    p.textContent = part;
    div.appendChild(p);
  });
  if (applied && applied.length) {
    const note = document.createElement("div");
    note.className = "applied";
    note.textContent = "ledger updated: " + applied.join(", ");
    div.appendChild(note);
  }
  thread.appendChild(div);
  thread.scrollTop = thread.scrollHeight;
  return div;
}

function typing() {
  const div = document.createElement("div");
  div.className = "msg bot typing";
  div.innerHTML = "<span></span><span></span><span></span>";
  thread.appendChild(div);
  thread.scrollTop = thread.scrollHeight;
  return div;
}

/* ---------- network ---------- */
async function post(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body || {})
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Something went wrong.");
  return data;
}

/* ---------- events ---------- */
document.getElementById("composer").addEventListener("submit", async e => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  bubble("me", text);
  input.value = "";
  input.style.height = "auto";
  sendBtn.disabled = true;
  const dots = typing();
  try {
    const data = await post("/api/chat", {message: text});
    dots.remove();
    bubble("bot", data.reply || "(empty reply)", data.applied);
    paint(data.budget);
  } catch (err) {
    dots.remove();
    bubble("err", err.message);
  }
  sendBtn.disabled = false;
  input.focus();
});

input.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    document.getElementById("composer").requestSubmit();
  }
});
input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 140) + "px";
});

document.querySelectorAll("[data-kind]").forEach(btn => {
  btn.onclick = async () => {
    const label = document.getElementById("m-label").value;
    const amount = document.getElementById("m-amount").value;
    try {
      const b = await post("/api/manual", {kind: btn.dataset.kind, label, amount});
      paint(b);
      document.getElementById("m-label").value = "";
      document.getElementById("m-amount").value = "";
    } catch (err) {
      bubble("err", err.message);
    }
  };
});

document.getElementById("reset").onclick = async () => {
  paint(await post("/api/reset"));
  thread.querySelectorAll(".msg:not(:first-child)").forEach(m => m.remove());
};

/* ---------- start ---------- */
fetch("/api/budget").then(r => r.json()).then(paint);
