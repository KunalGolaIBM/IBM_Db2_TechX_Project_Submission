// Customer chat demo. Every reply goes through POST /api/assistant/ask: the demo assistant drafts, AsOf checks
// the draft against the policy in force on the booking date, and only what AsOf released (or its holding reply)
// is shown. All text from the API is set with textContent, never parsed as HTML.

const $ = (sel) => document.querySelector(sel);
const TOKEN_KEY = "asof-api-token";  // shared with the console (app.js)
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
  "November", "December"];
const state = { bookings: [], booking: null, replay: false, busy: false };

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) el.append(c instanceof Node ? c : String(c));
  return el;
}
const svg = (path) => {
  const s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true");
  const p = document.createElementNS("http://www.w3.org/2000/svg", "path");
  p.setAttribute("d", path); s.append(p); return s;
};
const ICON = {
  PASS: "M5 12.5l4.5 4.5L19 7",
  CORRECTED: "M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4",
  ESCALATED: "M12 3a9 9 0 100 18 9 9 0 000-18zM12 7v6M12 16.5v.5",
};

function fmt(d) {
  if (!d || String(d).startsWith("9999")) return "open-ended";
  const [y, m, day] = String(d).slice(0, 10).split("-").map(Number);
  return `${day} ${MONTHS[m - 1]} ${y}`;
}
function short(d) {
  const [y, m, day] = String(d).slice(0, 10).split("-").map(Number);
  return `${day} ${MONTHS[m - 1].slice(0, 3)} ${y}`;
}
function token() { try { return sessionStorage.getItem(TOKEN_KEY) || ""; } catch { return ""; } }

async function call(path, body) {
  const headers = { "content-type": "application/json" };
  if (token()) headers.authorization = `Bearer ${token()}`;
  const res = await fetch(path, body ? { method: "POST", headers, body: JSON.stringify(body) } : { headers });
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (res.status === 401) {
    askToken();
    throw new Error("This AsOf server needs an API token. Enter it at the top of the page.");
  }
  // A held answer is a 503 that carries the full decision; anything else that is not 2xx is an error.
  if (!res.ok && !(res.status === 503 && data && data.decision)) {
    throw new Error((data && (data.error || (typeof data.detail === "string" && data.detail))) || `Request failed (${res.status})`);
  }
  return data;
}

function askToken() {
  if ($("#token")) return;
  const input = h("input", { id: "token-in", type: "password", autocomplete: "off", required: true, "aria-label": "API token" });
  const form = h("form", { id: "token", class: "token-bar", onsubmit: (e) => {
    e.preventDefault();
    try { sessionStorage.setItem(TOKEN_KEY, input.value.trim()); } catch { /* private mode */ }
    form.remove();
  } }, h("span", { text: "This AsOf server needs an API token (with the checker role)." }), input,
  h("button", { type: "submit", text: "Use token" }));
  document.body.prepend(form);
}

// ---------- bookings ----------
function renderBookings() {
  const root = $("#bookings");
  root.replaceChildren(...state.bookings.map((b) => h("button", {
    type: "button", role: "radio", "aria-checked": String(b === state.booking), class: `booking ${b === state.booking ? "on" : ""}`,
    onclick: () => choose(b),
  }, h("span", { class: "b-ref", text: b.ref }), h("span", { class: "b-route", text: b.route }),
  h("span", { class: "b-date", text: `Booked ${fmt(b.booked)}` }))));
}
function choose(b, quiet = false) {
  if (state.booking === b) return;
  state.booking = b;
  renderBookings();
  $("#w-sub").textContent = `Checked by AsOf · ${b.ref}, booked ${short(b.booked)}`;
  if (!quiet) log(h("div", { class: "divider" }, h("span", { text: `Now helping with ${b.ref}, booked ${fmt(b.booked)}` })));
  renderSuggestions();
}
function renderSuggestions() {
  // Each booking suggests the questions recorded for its date, so they also work in replay mode; a live model
  // answers anything typed.
  const own = state.booking ? state.booking.questions : [];
  $("#suggest").replaceChildren(...own.map((q) => h("button", { type: "button", class: "chip", text: q, onclick: () => ask(q) })));
}

// ---------- messages ----------
function log(node) {
  const el = $("#log");
  el.append(node);
  el.scrollTop = el.scrollHeight;
  return node;
}
function bubble(who, ...children) { return h("div", { class: `msg ${who}` }, h("div", { class: "bubble" }, ...children)); }

const STRIP = {
  PASS: (asOf) => ["Checked", `Every policy claim matches the policy in force on ${fmt(asOf)}.`],
  CORRECTED: (asOf) => ["Corrected before sending", `The first draft contradicted the policy in force on ${fmt(asOf)}; this reply was rewritten from the clause and checked again.`],
  ESCALATED: () => ["Passed to a specialist", "AsOf could not confirm every claim against the policy, so the draft was not sent."],
};

function citations(r) {
  // The clauses behind what the customer actually reads: the re-checked rewrite if there was one, else the draft.
  const pass = r.decision === "CORRECTED" ? 2 : 1;
  const seen = new Map();
  for (const c of r.claims) {
    if (c.pass_no === pass && c.verdict === "SUPPORTED" && c.clause_id && !seen.has(c.clause_id)) seen.set(c.clause_id, c);
  }
  return [...seen.values()];
}

function reply(r, asOf) {
  const strip = STRIP[r.decision] || STRIP.ESCALATED;
  const [title, detail] = strip(asOf);
  const cites = r.decision === "ESCALATED" ? [] : citations(r);
  // AsOf appends "Policy references: ..." to a released answer (what the ledger records). The widget shows that
  // line as source chips, built from the same supported claims.
  const at = cites.length ? r.final_answer.lastIndexOf("\n\nPolicy references: ") : -1;
  const body = at >= 0 ? r.final_answer.slice(0, at) : r.final_answer;
  const behind = h("div", { class: "behind" },
    h("div", { class: "bh-row" }, h("span", { class: "bh-k", text: "Assistant's draft" }),
      h("p", { class: `bh-draft ${r.decision === "PASS" ? "" : "struck"}`, text: (r.assistant && r.assistant.draft) || "" })),
    r.claims.filter((c) => c.pass_no === 1).length
      ? h("div", { class: "bh-row" }, h("span", { class: "bh-k", text: "Claims checked" }),
        h("ul", { class: "bh-claims" }, ...r.claims.filter((c) => c.pass_no === 1).map((c) => h("li", {},
          h("span", { class: `v ${c.verdict.toLowerCase()}`, text: c.verdict.replace("_", " ") }),
          h("span", { text: c.text }),
          c.clause_id ? h("span", { class: "bh-src", text: `${c.clause_id} ${c.clause_version}` }) : null,
          c.rule_check === "MISMATCH" ? h("span", { class: "bh-src", text: "rule check: mismatch" }) : null))))
      : h("div", { class: "bh-row" }, h("span", { class: "bh-k", text: "Claims checked" }), h("p", { text: "No policy claims." })),
    h("div", { class: "bh-row" }, h("span", { class: "bh-k", text: "Audit record" }),
      r.ledger_id
        ? h("p", {}, h("a", { href: `./#/ledger/${r.ledger_id}`, target: "_blank", rel: "noopener", text: `Ledger entry #${r.ledger_id}` }),
          ` · receipt ${String(r.row_hash || "").slice(0, 16)}… · ${r.model}`)
        : h("p", { text: "Not recorded (the check failed closed)." })));
  behind.hidden = !$("#w-behind").checked;
  return bubble("bot",
    h("p", { class: "text", text: body }),
    cites.length ? h("div", { class: "cites" }, h("span", { class: "cites-k", text: "Sources" }), ...cites.map((c) => h("span", { class: "cite", title: c.clause_title || "" },
      h("b", { text: c.clause_id }), h("i", { text: c.clause_version }),
      h("span", { text: `in force ${short(c.effective_from)} to ${c.effective_to && !String(c.effective_to).startsWith("9999") ? short(c.effective_to) : "now"}` })))) : null,
    h("div", { class: `strip ${r.decision.toLowerCase()}` }, svg(ICON[r.decision] || ICON.ESCALATED),
      h("div", {}, h("b", { text: title }), h("span", { text: ` ${detail}` }))),
    behind);
}

function typing(asOf) {
  const steps = ["Drafting an answer", `Checking each claim against the policy for ${fmt(asOf)}`, "Writing the audit record"];
  const label = h("span", { class: "t-label", text: steps[0] });
  const node = bubble("bot typing", h("span", { class: "dots", "aria-hidden": "true" }, h("i"), h("i"), h("i")), label);
  let i = 0;
  const timer = setInterval(() => { i = Math.min(i + 1, steps.length - 1); label.textContent = steps[i]; }, 2600);
  return { node: log(node), stop: () => { clearInterval(timer); node.remove(); } };
}

async function ask(question) {
  question = String(question || "").trim();
  if (!question || state.busy || !state.booking) return;
  state.busy = true;
  $("#send").disabled = true;
  $("#q").value = "";
  log(bubble("me", h("p", { class: "text", text: question })));
  const asOf = state.booking.booked;
  const t = typing(asOf);
  try {
    const r = await call("/api/assistant/ask", { question, as_of_date: asOf, doc_id: "AURELIA-CSP", channel: "chat" });
    t.stop();
    log(reply(r, asOf));
  } catch (err) {
    t.stop();
    log(h("div", { class: "msg note" }, h("p", { text: err.message })));
  } finally {
    state.busy = false;
    $("#send").disabled = false;
    $("#q").focus();
  }
}

// ---------- start ----------
async function start() {
  $("#ask").addEventListener("submit", (e) => { e.preventDefault(); ask($("#q").value); });
  $("#w-behind").addEventListener("change", (e) => {
    document.querySelectorAll(".behind").forEach((el) => { el.hidden = !e.target.checked; });
  });
  try {
    const health = await call("/healthz");
    state.replay = Boolean(health.replay);
  } catch { /* the first question will report the problem */ }
  try {
    const res = await fetch("scenarios.json");
    state.bookings = ((await res.json()).chat || {}).bookings || [];
  } catch { state.bookings = []; }
  if (!state.bookings.length) state.bookings = [{ ref: "AUR-7Q2K", route: "Boston to Lisbon", booked: "2026-03-10", questions: [] }];
  log(bubble("bot", h("p", { class: "text", text: "Hi, I'm the Aurelia Air assistant. Ask me about fares, bags, refunds or travel credits for your booking." })));
  if (state.replay) {
    log(h("div", { class: "msg note" }, h("p", { text: "Replay mode: this server answers the suggested questions from recorded model outputs, while the Db2 checks and the audit record run live. Other questions need a model (OPENROUTER_API_KEY or Ollama)." })));
  }
  choose(state.bookings[0], true);
}
start();
