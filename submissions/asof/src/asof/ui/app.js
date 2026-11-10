// AsOf UI. Plain ES modules, no dependencies. Every value from the API or the LLM is
// HTML-escaped by the html`` template below; only markup written here is trusted.

// ---------- tiny safe templating ----------
class Raw { constructor(s) { this.s = s; } }
const raw = (s) => new Raw(s);
const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const esc = (v) => String(v).replace(/[&<>"']/g, (c) => ESC[c]);
function out(v) {
  if (v instanceof Raw) return v.s;
  if (Array.isArray(v)) return v.map(out).join("");
  if (v === null || v === undefined || v === false) return "";
  return esc(v);
}
function html(strings, ...vals) {
  let s = strings[0];
  vals.forEach((v, i) => { s += out(v) + strings[i + 1]; });
  return raw(s);
}
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
function mount(el, view) {
  el.innerHTML = out(view);
  // Geometry is applied through the CSSOM, so the page needs no inline style attributes (CSP).
  $$("[data-left]", el).forEach((n) => { n.style.left = n.dataset.left + "%"; });
  $$("[data-width]", el).forEach((n) => { n.style.width = n.dataset.width + "%"; });
}

// ---------- API ----------
// Optional API token (ASOF_API_TOKEN on the server): asked for once per tab, kept in sessionStorage.
const TOKEN_KEY = "asof-api-token";
function savedToken() { try { return sessionStorage.getItem(TOKEN_KEY) || ""; } catch { return ""; } }
function askToken() {
  if ($("#token-form")) return;
  const form = document.createElement("form");
  form.id = "token-form";
  form.className = "token-bar";
  form.innerHTML = '<label for="api-token">This AsOf server needs an API token (yours, if it has per-user tokens)</label>'
    + '<input id="api-token" type="password" autocomplete="off" required><button class="btn sm" type="submit">Use token</button>';
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    try { sessionStorage.setItem(TOKEN_KEY, $("#api-token").value.trim()); } catch { /* private mode: ask again next time */ }
    form.remove();
    status().then(route);
  });
  document.body.prepend(form);
}
async function api(path, options = {}) {
  const { held, ...init } = options;
  const headers = { "content-type": "application/json" };
  const token = savedToken();
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(path, { ...init, headers });
  if (res.status === 401) { askToken(); throw new Error("This AsOf server needs an API token: enter it at the top of the page."); }
  let body = null;
  try { body = await res.json(); } catch { /* empty body */ }
  // A check that held its answer is a 503 that carries the full result. Any other non-2xx, including a 503
  // without a decision (no model, Db2 down, a replay miss), is an error for the caller to show.
  if (!res.ok && !(held && res.status === 503 && body && body.decision)) throw new Error(errorText(body, res.status));
  return { status: res.status, body };
}
function errorText(body, status) {
  if (!body) return `Request failed (${status})`;
  if (body.error) return body.error;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) return body.detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
  return `Request failed (${status})`;
}
const post = (path, data, extra = {}) => api(path, { method: "POST", body: JSON.stringify(data), ...extra });

// ---------- formatting ----------
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function fmtDate(d) {
  if (!d) return "";
  if (String(d).startsWith("9999")) return "open-ended";
  const [y, m, day] = String(d).slice(0, 10).split("-").map(Number);
  return `${day} ${MONTHS[m - 1]} ${y}`;
}
// Db2 stamps rows with its own clock; /healthz reports its zone (CURRENT TIMEZONE), so each timestamp says which.
const sqlTs = (t) => String(t || "").replace("T", " ").slice(0, 19);
function fmtTs(t) {
  if (!t) return "";
  return health.clock ? `${sqlTs(t)} ${health.clock}` : sqlTs(t);
}
const period = (from, to) => (to ? `${fmtDate(from)} → ${String(to).startsWith("9999") ? "open-ended" : fmtDate(to)}` : `from ${fmtDate(from)}`);  // no end known: say only the start
const lower = (s) => String(s || "").toLowerCase();
// Claims in quotes, without their own closing stop, so a sentence can carry them.
const quoted = (xs) => xs.map((x) => `“${String(x).replace(/[.!?]+$/, "")}”`).join("; ");
const today = () => new Date().toISOString().slice(0, 10);
const shortHash = (h) => (h || "").slice(0, 12);
// Carbon tags use sentence case. Only enum values (CONTRADICTED, NEEDS_REVIEW) are recased; free text keeps its own case.
const sentence = (v) => {
  const s = String(v);
  if (!/^[A-Z0-9_ ]+$/.test(s)) return s.charAt(0).toUpperCase() + s.slice(1);
  const t = s.replaceAll("_", " ").toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
};
const pill = (value, cls) => html`<span class="pill ${cls || lower(value)}">${sentence(value)}</span>`;
function clauseRef(id, version, from, to) {
  return html`<span class="clause-ref"><b>${id}</b><i>${version}</i><span>${period(from, to)}</span></span>`;
}
function highlight(text, quote) {
  if (!text) return "";
  const q = String(quote || "").trim().replace(/^["']|["'.]$/g, "");
  const i = q.length >= 8 ? text.toLowerCase().indexOf(q.toLowerCase()) : -1;
  if (i < 0) return html`${text}`;
  return html`${text.slice(0, i)}<mark>${text.slice(i, i + q.length)}</mark>${text.slice(i + q.length)}`;
}
const ICONS = {
  PASS: raw('<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7"/></svg>'),
  CORRECTED: raw('<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="M13.5 6.5l4 4"/></svg>'),
  ESCALATED: raw('<svg viewBox="0 0 24 24"><path d="M12 8v5"/><path d="M12 16.5v.5"/><path d="M10.3 3.9L2.6 17.3A2 2 0 004.3 20h15.4a2 2 0 001.7-2.7L13.7 3.9a2 2 0 00-3.4 0z"/></svg>'),
  REVIEWED: raw('<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="3.5"/><path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5"/></svg>'),
};

// ---------- shell ----------
const view = $("#view");
const routes = { playground: Playground, timeline: Timeline, intake: Intake, ledger: Ledger, inbox: Inbox, ask: Ask, impact: Impact, backtest: Backtest, analytics: Analytics };
async function route() {
  const [name, arg] = location.hash.replace(/^#\/?/, "").split("/");
  const key = routes[name] ? name : "playground";
  $$(".tabs a").forEach((a) => a.classList.toggle("active", a.dataset.route === key));
  try {
    await routes[key](arg);
  } catch (err) {
    mount(view, html`<div class="error-box">${err.message}</div>`);
  }
  view.focus({ preventScroll: true });
}
window.addEventListener("hashchange", route);

const health = { replay: false, live: null, clock: null, headline: [], demo: false };
// The public demo's live checks: "on", "paused" (the banner says why) or "unavailable".
const liveTag = (b) => (b.live_checks === "on" ? `replay + live: ${String(b.live_model).split("/").pop()}`
  : `replay only: live checks ${b.live_checks}`);
async function status() {
  try {
    const { body } = await api("/healthz");
    mount($("#status"), html`
      <span class="tag db2 ${body.db2 === "ok" ? "ok" : "warn"}" title="IBM Db2 connection as the least-privilege user"><i aria-hidden="true"></i><span class="label">Db2 ${body.db2 === "ok" ? "connected" : "unavailable"}</span></span>
      <span class="tag ${body.llm_ready ? (body.replay && body.live_checks !== "on" ? "warn" : "brand") : "warn"}" title="LLM provider and model: ${body.live_model ? `${body.llm}, and ${body.live_model} for live checks` : body.llm}">${body.llm_ready ? (body.live_checks ? liveTag(body) : body.replay ? "replay: recorded model outputs" : String(body.llm).split("/").pop()) : "no model configured"}</span>`);
    health.replay = Boolean(body.replay);
    // The public demo with live checks: a check's new input goes live (or is refused while live checks are paused),
    // never held as a replay miss. Policy intake and the inbox's reply check stay replay-only.
    health.live = body.live_checks || null;
    health.headline = Array.isArray(body.headline) ? body.headline : [];  // measured results, from the result files
    health.clock = body.db2_clock || null;
    if (body.replay && $("#replay-mode") && body.public_demo_notice) $("#replay-mode").textContent = body.public_demo_notice;
    health.demo = Boolean(body.public_demo);
    if (body.replay && !$("#replay-mode")) {
      const bar = document.createElement("div");
      bar.id = "replay-mode";
      bar.className = "token-bar notice";
      bar.textContent = body.public_demo_notice || "Replay mode: no language model is called. The built-in scenarios replay the model outputs recorded "
        + `from ${body.replay_model || "a hosted model"}; Db2 retrieval, the rule checks, the decision and the ledger run live. `
        + "Any other input is held for a specialist (fail closed). To check your own answers, add OPENROUTER_API_KEY "
        + "and set LLM_PROVIDER=openrouter in .env (or use Ollama), then restart.";
      document.body.prepend(bar);
    }
    if (!body.llm_ready && !$("#no-model")) {
      const bar = document.createElement("div");
      bar.id = "no-model";
      bar.className = "token-bar";
      bar.textContent = "No language model is configured, so answers cannot be checked yet. "
        + "Add OPENROUTER_API_KEY to .env, or set LLM_PROVIDER=ollama with Ollama running, then restart. "
        + "The policy timeline, ledger, replay and change impact work without a model.";
      document.body.prepend(bar);
    }
  } catch { mount($("#status"), html`<span class="tag warn">API unavailable</span>`); }
}

// ---------- Playground ----------
const QUESTION_MOFFATT = "My grandmother just died. Can I get the bereavement fare after I travel?";
const AIRLINE = "AURELIA-CSP";
const BANK = "FERNHOLLOW-FEES";
const DOC_NAME = { [AIRLINE]: "Aurelia Air", [BANK]: "Fernhollow Bank" };
let SCENARIOS = [];  // the playground chips, from scenarios.json (replay mode has recordings for exactly these)
const play = { mode: "ask", doc: AIRLINE, question: QUESTION_MOFFATT, draft: "", as_of: "2026-03-10", scenario: 0, result: null };

const HEADLINE = {
  PASS: "Released as written",
  CORRECTED: "Corrected before release",
  ESCALATED: "Held for a specialist",
  REVIEWED: "Answered by a specialist",
};
function explain(r, asOf) {
  const contradicted = r.claims.filter((c) => c.pass_no === 1 && c.verdict === "CONTRADICTED").length;
  const date = fmtDate(asOf);
  switch (r.reason_code) {
    case "ALL_SUPPORTED": return `Every policy claim is supported by the clause version in force on ${date}.`;
    case "NO_POLICY_CLAIMS": return "The answer makes no policy claims, so there is nothing to check.";
    case "CORRECTED_FROM_CLAUSES": return `${contradicted} claim${contradicted === 1 ? "" : "s"} contradicted the policy in force on ${date}. The answer was rewritten from the clause text and passed a full re-check.`;
    case "NOT_COVERED": return `No clause in force on ${date} covers at least one claim, so a person has to answer.`;
    case "UNCHECKED_DETAILS": return `The draft states ${(r.unchecked || []).join(", ") || "details"} that the claim check never covered, so it was held rather than sent unchecked.`;
    case "CORRECTION_FAILED": return "The answer contradicted the policy, and the rewrite did not pass the re-check, so it was held back.";
    case "TOO_MANY_CLAIMS": return "The answer makes more than 8 policy claims; long answers go to a person.";
    case "ERROR_FAIL_CLOSED": return "A check could not complete, so the answer was held (fail closed)."
      + (health.replay && !health.live ? " In replay mode this is what happens to any input without a recorded model output." : "");
    case "LEDGER_UNAVAILABLE": return "The decision could not be recorded in the ledger, so nothing was released.";
    case "RELEASE_REFUSED": return `Db2 refused to record this release: a claim was not quoted from a clause version in force on ${date}. It was held instead.`;
    case "ROUTE_UNCERTAIN": return "AsOf could not tell which policy document this is about, so it did not guess: a specialist picks the document and answers, in the inbox.";
    default: return r.reason_code;
  }
}

// The headline: the two strongest measured results, each linking to its evaluation (served by /healthz, read from the
// published result files). A number the server could not compute is simply not there.
function headlineView() {
  if (!health.headline.length) return "";
  return html`<div class="headline" aria-label="Measured results">${health.headline.map((h, i) => html`${i ? html`<span class="hl-sep" aria-hidden="true">·</span>` : ""}<a href="${h.href}" target="_blank" rel="noopener"><span class="hl-long">${h.text}</span><span class="hl-short">${h.short}</span></a>`)}</div>`;
}

async function Playground() {
  renderPlayground();
}
function renderPlayground() {
  const s = play;
  mount(view, html`
    <div class="page-head">
      <div>
        <h1>Check an answer against the policy in force on a date</h1>
        <p>The naive demo assistant answers from a stale FAQ with no idea which policy applied when. AsOf checks every claim in its draft against the clause version in force on the customer's date, in Db2. Two fictional policy documents: Aurelia Air's customer service plan and Fernhollow Bank's fee schedule.</p>
        ${headlineView()}
      </div>
    </div>
    <div class="grid-2">
      <form class="card" id="play-form" autocomplete="off">
        <div class="field">
          <label>Scenarios</label>
          <div class="chips">${SCENARIOS.map((x, i) => html`<button type="button" class="chip ${i === s.scenario ? "on" : ""}" data-scenario="${i}">${x.label}</button>`)}</div>
        </div>
        <div class="sep"></div>
        <div class="field">
          <div class="seg" role="tablist">
            <button type="button" data-mode="ask" class="${s.mode === "ask" ? "on" : ""}">Ask the demo assistant (airline)</button>
            <button type="button" data-mode="draft" class="${s.mode === "draft" ? "on" : ""}">Check my own draft</button>
          </div>
        </div>
        <div class="field">
          <label for="q">Customer question</label>
          <textarea id="q" name="question" rows="3" maxlength="2000" required>${s.question}</textarea>
        </div>
        <div class="field" ${s.mode === "ask" ? raw("hidden") : ""}>
          <label for="doc">Policy document</label>
          <select id="doc">${[AIRLINE, BANK].map((d) => html`<option value="${d}" ${d === s.doc ? raw("selected") : ""}>${DOC_NAME[d]} (${d})</option>`)}
            <option value="auto" ${s.doc === "auto" ? raw("selected") : ""}>Let AsOf decide (routing)</option></select>
        </div>
        <div class="field" ${s.mode === "ask" ? raw("hidden") : ""}>
          <label for="d">Assistant draft to check</label>
          <textarea id="d" name="draft" rows="5" maxlength="4000">${s.draft}</textarea>
        </div>
        <div class="field">
          <label for="asof">Customer's date</label>
          <input id="asof" name="as_of" type="date" min="2020-01-01" max="2035-12-31" value="${s.as_of}" required>
          <div class="hint">The booking or travel date from your booking system. AsOf never lets the model guess it.</div>
        </div>
        <div class="field"><button class="btn block" id="run" type="submit">Check answer</button></div>
      </form>
      <section id="play-result">${s.result ? resultView(s.result, s.result._as_of) : html`
        <div class="empty"><h3>No answer checked yet</h3><p>Pick a scenario and press <strong>Check answer</strong>. Try the March booking, then the same question for June.</p></div>`}
      </section>
    </div>`);
  const form = $("#play-form");
  form.addEventListener("click", (e) => {
    const sc = e.target.closest("[data-scenario]");
    if (sc) {
      const x = SCENARIOS[Number(sc.dataset.scenario)];
      Object.assign(play, { scenario: Number(sc.dataset.scenario), mode: x.mode, doc: x.doc || AIRLINE, question: x.question,
        draft: x.draft || "", as_of: x.as_of });
      renderPlayground();
    }
    const m = e.target.closest("[data-mode]");
    if (m) { syncPlay(); play.mode = m.dataset.mode; if (play.mode === "ask") play.doc = AIRLINE; renderPlayground(); }
  });
  form.addEventListener("submit", (e) => { e.preventDefault(); runCheck(); });
}
function syncPlay() {
  play.question = $("#q").value;
  play.draft = $("#d") ? $("#d").value : play.draft;
  play.as_of = $("#asof").value;
  play.doc = play.mode === "ask" ? AIRLINE : ($("#doc") ? $("#doc").value : play.doc);
}
async function runCheck() {
  syncPlay();
  const box = $("#play-result");
  const btn = $("#run");
  btn.disabled = true;
  mount(box, html`<div class="card"><div class="loading"><div class="spinner"></div><div>
    <strong>Checking against the policy in force on ${fmtDate(play.as_of)}</strong>
    <div class="steps">${play.mode === "ask" ? html`<span>Demo assistant drafts</span>` : ""}<span>Redact</span><span>Extract claims</span><span>Db2: clauses as of the date</span><span>Judge + rule check</span><span>Db2: hash-chained ledger</span></div>
  </div></div></div>`);
  try {
    const { body } = play.mode === "ask"
      ? await post("/api/assistant/ask", { question: play.question, as_of_date: play.as_of }, { held: true })
      : await post("/api/gate", { question: play.question, draft_answer: play.draft, as_of_date: play.as_of, doc_id: play.doc }, { held: true });
    body._as_of = play.as_of;
    body._draft = play.mode === "ask" ? body.assistant?.draft : play.draft;
    play.result = body;
    mount(box, resultView(body, play.as_of));
  } catch (err) {
    mount(box, html`<div class="error-box">${err.message}</div>`);
  } finally {
    btn.disabled = false;
    if (health.live) status();  // the banner shows today's live-check count, or why live checks paused
  }
}
function claimCard(c) {
  const overridden = c.llm_verdict === "SUPPORTED" && c.verdict === "CONTRADICTED";
  return html`
    <div class="claim ${lower(c.verdict)}">
      <div class="claim-top">${pill(c.verdict)}<div class="claim-text">${c.text}</div>${overridden ? html`<span class="override">Rule check overruled the judge</span>` : ""}</div>
      <div class="claim-checks">
        <span>Judge: <strong>${(c.llm_verdict || "none").replaceAll("_", " ")}</strong></span>
        <span>Rule check: <strong>${c.rule_check.replaceAll("_", " ")}</strong></span>
        ${c.rule_details.length ? html`<span>${c.rule_details.join("; ")}</span>` : ""}
      </div>
      ${c.clause_id ? html`
        <div class="clause-box">
          <div class="row wrap">${clauseRef(c.clause_id, c.clause_version, c.effective_from, c.effective_to)}<span class="small muted">${c.clause_title}</span></div>
          <p>${highlight(c.clause_text, c.quoted_span)}</p>
        </div>` : ""}
      <div class="reason">${c.reason}</div>
    </div>`;
}
function routeBanner(rt) {
  if (!rt) return "";
  const dist = Object.entries(rt.distances).map(([d, v]) => `${DOC_NAME[d] || d} ${Number(v).toFixed(2)}`).join(", ");
  const how = rt.method === "db2" ? "Db2's vote alone" : rt.method === "db2+agent" ? "Db2's vote, confirmed by the routing agent" : "";
  return rt.doc_id
    ? html`<div class="banner ok"><strong>Routed to ${DOC_NAME[rt.doc_id]}.</strong><span>By ${how}: nearest clause distance ${dist} (lead ${Number(rt.margin).toFixed(2)}).</span></div>`
    : html`<div class="banner fix"><strong>Asked a person instead of guessing.</strong><span>${rt.reason.charAt(0).toUpperCase() + rt.reason.slice(1)}. Nearest clause distance ${dist}. Held for the <a href="#/inbox">specialist inbox</a>.</span></div>`;
}
function resultView(r, asOf) {
  const first = r.claims.filter((c) => c.pass_no === 1);
  const second = r.claims.filter((c) => c.pass_no === 2);
  const draft = r._draft ?? r.assistant?.draft;
  return html`${routeBanner(r.route)}
    <div class="decision ${lower(r.decision)}">
      <div class="icon">${ICONS[r.decision]}</div>
      <div><div class="row">${pill(r.decision)}<h2>${HEADLINE[r.decision]}</h2></div><p>${explain(r, asOf)}</p></div>
      <div class="meta">${(r.latency_ms / 1000).toFixed(1)} s · ${r.model}<br>
        ${r.ledger_id ? html`<a href="#/ledger/${r.ledger_id}">Ledger entry #${r.ledger_id} →</a><br><span class="hash" title="Receipt (ledger row hash): ${r.row_hash || ""}">receipt ${shortHash(r.row_hash)}…</span>` : html`<span>Not recorded</span>`}</div>
    </div>
    <div class="cols-2">
      <div class="card"><div class="eyebrow">${r.assistant ? "Demo assistant's draft" : "Draft"}</div><div class="sep"></div>
        <div class="answer ${r.decision === "PASS" ? "" : "struck"}">${draft}</div></div>
      <div class="card"><div class="eyebrow">What the customer receives</div><div class="sep"></div>
        <div class="answer final">${r.final_answer}</div></div>
    </div>
    <div class="card">
      <div class="card-head"><h2>Claims in the draft</h2><span class="sub">checked against the clauses in force on ${fmtDate(asOf)}</span></div>
      ${first.length ? html`<div class="claims">${first.map(claimCard)}</div>` : html`<p class="muted">${r.reason_code === "ROUTE_UNCERTAIN" ? "No check ran: the specialist picks the policy document first." : "No policy claims found."}</p>`}
    </div>
    ${second.length ? html`<div class="card">
      <div class="card-head"><h2>Re-check of the corrected answer</h2><span class="sub">every claim must be supported before it is released</span></div>
      <div class="claims">${second.map(claimCard)}</div></div>` : ""}`;
}

// ---------- Policy timeline ----------
const AREAS = {
  [AIRLINE]: ["bereavement", "cancellation", "change_fee", "baggage", "refund", "delay", "travel_credit", "pets"],
  [BANK]: ["overdraft", "fee_refund", "monthly_fee", "foreign_transaction", "wire_transfer", "atm", "dispute", "account_closure", "checks"],
};
const AREA_LABEL = { bereavement: "Bereavement", cancellation: "Cancellation", change_fee: "Changes", baggage: "Baggage",
  refund: "Refunds", delay: "Delays", travel_credit: "Travel credits", pets: "Pets", other: "Other",
  overdraft: "Overdraft", fee_refund: "Fee refunds", monthly_fee: "Monthly fees", foreign_transaction: "Foreign transactions",
  wire_transfer: "Wire transfers", atm: "ATMs", dispute: "Disputes", account_closure: "Closing an account", checks: "Checks" };
const tl = { data: null, doc: AIRLINE, asOf: today(), filter: "changed", sel: null };
const DAY = 86400000;
const toMs = (d) => Date.parse(String(d).slice(0, 10) + "T00:00:00Z");

function keyParam(v) {
  const p = v.params || {};
  const usd = (n) => `$${Number(n).toFixed(0)}`;
  if ("retroactive_allowed" in p) return p.retroactive_allowed === "true" ? `retroactive, ${p.request_window_days} days` : "before travel only";
  if ("first_bag_fee_usd" in p) return usd(p.first_bag_fee_usd);
  if ("second_bag_fee_usd" in p) return usd(p.second_bag_fee_usd);
  if ("change_fee_usd" in p) return Number(p.change_fee_usd) === 0 ? "no change fee" : `${usd(p.change_fee_usd)} fee`;
  if ("pet_fee_usd" in p) return `${usd(p.pet_fee_usd)} each way`;
  if ("cancellation_fee_usd" in p) return `${usd(p.cancellation_fee_usd)} fee`;
  if ("compensation_usd" in p) return usd(p.compensation_usd);
  if ("min_days_before_departure" in p) return Number(p.min_days_before_departure) > 0 ? `booked ${p.min_days_before_departure}+ days out` : "any booking";
  if ("discount_pct" in p) return `${Number(p.discount_pct)}% off`;
  if ("credit_validity_months" in p) return `${p.credit_validity_months} months`;
  if ("max_passengers" in p) return `up to ${p.max_passengers}`;
  // The bank's fee schedule, read straight from RULE_JSON.
  const r = v.rule || {};
  if ("courtesy_refunds_per_year" in r) return `${r.courtesy_refunds_per_year} refund${r.courtesy_refunds_per_year === 1 ? "" : "s"}, ${r.request_window_days} days`;
  if ("min_daily_balance_usd" in r) return `waived at $${Number(r.min_daily_balance_usd).toLocaleString("en-US")}`;
  for (const [k, val] of Object.entries(r)) {
    if (k.endsWith("_usd") && typeof val === "number") return val === 0 ? "free" : `$${val.toLocaleString("en-US")}`;
    if (k.endsWith("_pct") && typeof val === "number") return `${val}%`;
  }
  return "";
}

async function Timeline() {
  if (!tl.data) {
    mount(view, html`<div class="loading"><div class="spinner"></div>Loading policy versions from Db2...</div>`);
    tl.data = (await api("/api/policy/timeline")).body;
  }
  renderTimeline();
}
function renderTimeline() {
  const data = tl.data.filter((c) => c.doc_id === tl.doc);
  const changed = data.filter((c) => c.versions.length > 1);
  const shown = tl.filter === "changed" ? changed : data;
  const start = toMs("2026-01-01");
  const latest = Math.max(...data.flatMap((c) => c.versions.map((v) => toMs(v.from))));
  // End the axis on the 1st of a month between two labelled ticks (Jan, Mar, ...), so the last label never sits on
  // the panel's edge, and the axis looks the same before and after a change near the end.
  const e = new Date(Math.max(toMs("2027-04-01"), latest + 120 * DAY));
  if (e.getUTCDate() !== 1) { e.setUTCDate(1); e.setUTCMonth(e.getUTCMonth() + 1); }
  if (e.getUTCMonth() % 2 === 0) e.setUTCMonth(e.getUTCMonth() + 1);
  const end = e.getTime();
  const pos = (ms) => Math.max(0, Math.min(100, ((ms - start) / (end - start)) * 100));
  const ticks = [];
  for (let d = new Date(start); d.getTime() <= end; d.setUTCMonth(d.getUTCMonth() + 2)) {
    ticks.push({ left: pos(d.getTime()).toFixed(3), label: `${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}` });
  }
  const asOfMs = toMs(tl.asOf);
  const inForce = (v) => toMs(v.from) <= asOfMs && asOfMs < toMs(v.to);
  if (!tl.sel) {
    const c = changed.find((x) => x.clause_id === (tl.doc === BANK ? "FRV-001" : "BRV-002")) || shown[0];
    tl.sel = { id: c.clause_id, version: (c.versions.find(inForce) || c.versions[0]).version };
  }
  const groups = AREAS[tl.doc].concat(["other"]).map((a) => ({ area: a, items: shown.filter((c) => c.area === a) })).filter((g) => g.items.length);
  const markerLeft = pos(asOfMs).toFixed(3);
  mount(view, html`<div id="tl-root">
    <div class="page-head">
      <div><h1>Policy timeline</h1>
        <p>Every clause version on its business-time period, straight from the bitemporal <code>POLICY_CLAUSE</code> table. Key numbers come out of <code>RULE_JSON</code> through the Db2 view <code>V_POLICY_TIMELINE</code> (<code>JSON_TABLE</code>). Click a version for its text and its system-time history.</p></div>
      <div class="tl-controls">
        <div class="seg">${[AIRLINE, BANK].map((d) => html`<button type="button" data-doc="${d}" class="${tl.doc === d ? "on" : ""}">${DOC_NAME[d]}</button>`)}</div>
        <div class="seg">
          <button type="button" data-filter="changed" class="${tl.filter === "changed" ? "on" : ""}">Changed clauses (${changed.length})</button>
          <button type="button" data-filter="all" class="${tl.filter === "all" ? "on" : ""}">All clauses (${data.length})</button>
        </div>
        <div><input type="date" id="tl-asof" value="${tl.asOf}" min="2026-01-01" max="2027-12-31" aria-label="As of date"></div>
      </div>
    </div>
    <div class="tl-layout">
      <div class="card">
        <div class="tl">
          <div class="tl-axis"><div class="eyebrow">Clause</div><div class="tl-scale">${ticks.map((t) => html`<span class="tl-tick ${t.left > 94 ? "end" : ""}" data-left="${t.left}">${t.label}</span>`)}<i class="tl-marker ${markerLeft > 88 ? "end" : ""}" data-left="${markerLeft}" data-label="as of ${fmtDate(tl.asOf)}"></i></div></div>
          ${groups.map((g) => html`
            <div class="tl-area">${AREA_LABEL[g.area] || g.area}</div>
            ${g.items.map((c) => html`
              <div class="tl-row">
                <div class="tl-name" title="${c.clause_id} ${c.title}"><code>${c.clause_id}</code><span>${c.title}</span></div>
                <div class="tl-track">
                  ${ticks.map((t) => html`<i class="tl-grid" data-left="${t.left}"></i>`)}
                  <i class="tl-marker" data-left="${markerLeft}"></i>
                  ${c.versions.map((v, i) => {
                    const l = pos(toMs(v.from)); const w = Math.max(0.6, pos(toMs(v.to)) - l);
                    const sel = tl.sel.id === c.clause_id && tl.sel.version === v.version;
                    return html`<button type="button" class="tl-seg tone${(i % 4) + 1} ${sel ? "selected" : ""}" data-left="${l.toFixed(3)}" data-width="${w.toFixed(3)}"
                      data-clause="${c.clause_id}" data-version="${v.version}" title="${c.clause_id} ${v.version}: ${period(v.from, v.to)}">
                      <span>${v.version}</span><span>${keyParam(v)}</span>${String(v.to).startsWith("9999") ? html`<span class="open">→</span>` : ""}</button>`;
                  })}
                </div>
              </div>`)}`)}
        </div>
      </div>
      <aside class="drawer card" id="tl-drawer"></aside>
    </div></div>`);
  // The root is replaced on every render, so its listener never outlives it.
  $("#tl-root").addEventListener("click", onTimelineClick);
  $("#tl-asof").addEventListener("change", (e) => { tl.asOf = e.target.value || today(); tl.sel = null; renderTimeline(); });
  renderDrawer();
}
function onTimelineClick(e) {
  const seg = e.target.closest(".tl-seg");
  const f = e.target.closest("[data-filter]");
  const d = e.target.closest("[data-doc]");
  if (d) { tl.doc = d.dataset.doc; tl.sel = null; renderTimeline(); return; }
  if (seg) { tl.sel = { id: seg.dataset.clause, version: seg.dataset.version }; renderTimeline(); return; }
  if (f) { tl.filter = f.dataset.filter; tl.sel = null; renderTimeline(); }
}
async function renderDrawer() {
  const box = $("#tl-drawer");
  const c = tl.data.find((x) => x.clause_id === tl.sel.id);
  const v = c.versions.find((x) => x.version === tl.sel.version);
  const asOfMs = toMs(tl.asOf);
  const live = toMs(v.from) <= asOfMs && asOfMs < toMs(v.to);
  mount(box, html`
    <div class="row wrap">${clauseRef(c.clause_id, v.version, v.from, v.to)}${live ? pill(`in force ${fmtDate(tl.asOf)}`, "pass") : pill("not in force on that date", "neutral")}</div>
    <h2 class="drawer-title">${c.title}</h2>
    <p class="answer">${v.text}</p>
    <dl class="kv">
      <dt>Applies</dt><dd>${period(v.from, v.to)}</dd>
      <dt>Changed by</dt><dd><code>${v.changed_by}</code></dd>
      <dt>Recorded in Db2</dt><dd>${fmtTs(v.recorded_at)}</dd>
      ${v.change_note ? html`<dt>Note</dt><dd>${v.change_note}</dd>` : ""}
    </dl>
    <div><div class="eyebrow">RULE_JSON (checked deterministically)</div><pre class="json">${JSON.stringify(v.rule, null, 2)}</pre></div>
    <div><div class="eyebrow">System-time history in Db2</div><div class="hist" id="tl-hist"><div class="muted small">Loading...</div></div></div>
    <div class="compare" id="tl-compare"></div>`);
  box.classList.add("stack");
  // Remember which panel this request is for: a slower response for a clause selected
  // earlier must not overwrite the panel of the clause selected now.
  const target = $("#tl-hist");
  try {
    const hist = (await api(`/api/policy/clauses/${encodeURIComponent(c.clause_id)}/history`)).body;
    if (!target.isConnected) return;
    mount(target, hist.map((h) => html`
      <div class="hist-item ${h.current ? "current" : ""}">
        <div class="row"><strong>${h.version}</strong><span class="muted">${period(h.from, h.to)}</span>${h.current ? pill("current record", "ok") : pill("superseded record", "neutral")}</div>
        <div class="muted">held ${fmtTs(h.recorded_at)} → ${h.current ? "now" : fmtTs(h.superseded_at)} · by <code>${h.changed_by}</code></div>
      </div>`));
    renderCompare(c.clause_id, v, hist);
  } catch (err) { if (target.isConnected) mount(target, html`<div class="error-box">${err.message}</div>`); }
}
// ---------- Version diff: any two rows Db2 ever held for a clause ----------
function histLabel(h) { return `${h.version} from ${fmtDate(h.from)}${h.current ? "" : ", superseded"}`; }
function renderCompare(clauseId, v, hist) {
  const box = $("#tl-compare");
  if (!box || hist.length < 2) { if (box) mount(box, ""); return; }
  // Default: the selected version as Db2 holds it now, against the row before it in time.
  const after = hist.find((h) => h.current && h.version === v.version && h.from === v.from) || hist[hist.length - 1];
  const before = [...hist].reverse().find((h) => h.ref !== after.ref && (h.version !== after.version || !h.current)) || hist[0];
  mount(box, html`<div class="eyebrow">Compare two versions</div>
    <div class="compare-pick"><select id="cmp-a" aria-label="Older row">${hist.map((h) => html`<option value="${h.ref}" ${h.ref === before.ref ? raw("selected") : ""}>${histLabel(h)}</option>`)}</select>
      <span class="muted">→</span>
      <select id="cmp-b" aria-label="Newer row">${hist.map((h) => html`<option value="${h.ref}" ${h.ref === after.ref ? raw("selected") : ""}>${histLabel(h)}</option>`)}</select></div>
    <div id="cmp-out"><div class="muted small">Loading...</div></div>`);
  const load = async () => {
    const out = $("#cmp-out");
    try {
      const d = (await api(`/api/policy/clauses/${encodeURIComponent(clauseId)}/diff?a=${encodeURIComponent($("#cmp-a").value)}&b=${encodeURIComponent($("#cmp-b").value)}`)).body;
      if (out.isConnected) mount(out, diffView(d));
    } catch (err) { if (out.isConnected) mount(out, html`<div class="error-box">${err.message}</div>`); }
  };
  $("#cmp-a").addEventListener("change", load);
  $("#cmp-b").addEventListener("change", load);
  load();
}
function diffView(d) {
  const sm = d.summary;
  const fmtVal = (x) => (x === null || x === undefined ? "none" : typeof x === "object" ? JSON.stringify(x) : String(x));
  return html`
    <div class="row wrap small">${pill(sm.text_changed ? "text changed" : "same text", sm.text_changed ? "corrected" : "neutral")}
      ${pill(`${sm.rules_changed} rule value${sm.rules_changed === 1 ? "" : "s"} changed`, sm.rules_changed ? "corrected" : "neutral")}
      ${sm.period_changed ? pill("period changed", "corrected") : ""}
      <span class="muted" title="VECTOR_DISTANCE(A.EMBEDDING, B.EMBEDDING, COSINE), computed in the same Db2 query">embedding distance ${sm.embedding_distance.toFixed(4)}</span></div>
    <p class="answer diff">${d.text.map((x) => (x.op === "equal" ? x.text : x.op === "insert" ? html`<ins>${x.text}</ins>` : html`<del>${x.text}</del>`))}</p>
    <table class="rule-diff"><thead><tr><th>RULE_JSON</th><th>${d.before.version}</th><th>${d.after.version}</th></tr></thead>
      <tbody>${d.rule.map((r) => html`<tr class="${r.status}"><td><code>${r.key}</code></td><td>${fmtVal(r.before)}</td><td>${fmtVal(r.after)}</td></tr>`)}</tbody></table>`;
}

// ---------- Ledger & replay ----------
const led = { decision: null };
async function Ledger(id) {
  if (id) return LedgerEntry(Number(id));
  mount(view, html`
    <div class="page-head">
      <div><h1>Audit ledger</h1>
        <p>Every decision, appended by the SQL PL procedure <code>APPEND_LEDGER</code>. Rows are hash-chained with SHA-256 computed inside Db2, and triggers reject any UPDATE or DELETE, even by the owner. The app's own Db2 user can only read and call the procedures.</p></div>
      <button class="btn ghost" id="verify">Verify hash chain</button>
    </div>
    <div id="chain"></div>
    <form class="card receipt" id="receipt-form" autocomplete="off"><div class="card-head"><h2>Check a receipt</h2>
      <span class="sub">Every check returns its ledger row hash. Kept outside Db2, it proves the record was not rewritten, even by an owner who rebuilt the whole chain.</span></div>
      <div class="row"><input id="rc-id" type="number" min="1" placeholder="Ledger #" required><input id="rc-hash" class="grow code" type="text" pattern="[0-9a-fA-F]{64}" placeholder="64-character row hash" required>
      <button class="btn ghost" type="submit">Check</button></div><div id="rc-out"></div></form>
    <div class="card"><div class="card-head"><div class="chips" id="dec-filter">
      ${[null, "PASS", "CORRECTED", "ESCALATED", "REVIEWED"].map((d) => html`<button type="button" class="chip ${led.decision === d ? "on" : ""}" data-dec="${d || ""}">${d ? sentence(d) : "All decisions"}</button>`)}
    </div></div><div id="ledger-table"><div class="loading"><div class="spinner"></div>Loading ledger...</div></div></div>`);
  $("#verify").addEventListener("click", verifyChain);
  $("#receipt-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const out = $("#rc-out");
    try {
      const { body } = await post("/api/ledger/receipt", { ledger_id: Number($("#rc-id").value), row_hash: $("#rc-hash").value.trim() });
      const says = {
        INTACT: ["ok", "Intact.", `Entry #${body.ledger_id} is the record this receipt was issued for, and the chain verifies.`],
        MISMATCH: ["bad", "Does not match.", `Entry #${body.ledger_id} is not the record this receipt was issued for: it was rewritten, the ledger was reset, or the receipt is from another ledger or mistyped.`],
        MISSING: ["bad", "Missing.", `The ledger has no entry #${body.ledger_id}.`],
        CHAIN_BROKEN: ["bad", "Chain broken.", `The row matches, but VERIFY_CHAIN fails at entry #${body.first_bad_ledger_id}.`],
      }[body.verdict];
      mount(out, html`<div class="banner ${says[0]}"><strong>${says[1]}</strong><span>${says[2]}</span></div>`);
    } catch (err) { mount(out, html`<div class="error-box">${err.message}</div>`); }
  });
  $("#dec-filter").addEventListener("click", (e) => { const b = e.target.closest("[data-dec]"); if (b) { led.decision = b.dataset.dec || null; Ledger(); } });
  verifyChain();
  const q = led.decision ? `?limit=100&decision=${led.decision}` : "?limit=100";
  let rows;
  try { rows = (await api(`/api/ledger${q}`)).body; }
  catch (err) { mount($("#ledger-table"), html`<div class="error-box">${err.message}</div>`); return; }  // keep the page and its controls
  mount($("#ledger-table"), rows.length ? html`
    <table><thead><tr><th>#</th><th>Recorded</th><th>Customer date</th><th>Decision</th><th>Reason</th><th>Question</th><th>Row hash</th></tr></thead>
    <tbody>${rows.map((r) => html`<tr class="click" data-id="${r.ledger_id}">
      <td class="num"><a href="#/ledger/${r.ledger_id}">${r.ledger_id}</a></td><td class="ts">${sqlTs(r.created_at).slice(0, 10)}<br><span class="muted small">${fmtTs(r.created_at).slice(11)}</span></td><td>${fmtDate(r.as_of_date)}</td>
      <td>${pill(r.decision)}${r.channel === "backtest" ? html` <span class="pill neutral plain" title="A past answer checked by a backtest: not an answer AsOf released">Backtest</span>` : ""}</td><td class="small muted">${sentence(r.reason_code)}${r.uncovered && r.uncovered.length ? html`<div class="trunc reason-claim" title="No clause covers ${quoted(r.uncovered)}">${quoted(r.uncovered)}</div>` : ""}</td>
      <td class="trunc" title="${r.question_redacted}">${r.question_redacted}</td><td class="hash nowrap">${shortHash(r.row_hash)}</td></tr>`)}</tbody></table>`
    : html`<div class="empty"><h3>No decisions recorded yet</h3><p>Check an answer in the <a href="#/playground">Playground</a>.</p></div>`);
  $("#ledger-table").addEventListener("click", (e) => { const tr = e.target.closest("tr[data-id]"); if (tr) location.hash = `#/ledger/${tr.dataset.id}`; });
}
async function verifyChain() {
  const box = $("#chain");
  if (!box) return;
  mount(box, html`<div class="banner ok"><div class="spinner"></div>Running VERIFY_CHAIN in Db2...</div>`);
  try {
    const s = (await api("/api/chain/verify")).body;
    const chain = s.status === "OK"
      ? html`<div class="banner ok"><strong>Chain intact.</strong><span>VERIFY_CHAIN recomputed ${s.rows_checked} row hash${s.rows_checked === 1 ? "" : "es"}: ${s.detail}.</span></div>`
      : html`<div class="banner bad"><strong>Chain broken at entry #${s.first_bad_ledger_id}.</strong><span>${s.detail}</span></div>`;
    mount(box, chain);
    const a = (await api("/api/chain/anchors")).body;
    mount(box, html`${chain}${anchorBanner(a)}`);
  } catch (err) { mount(box, html`<div class="banner bad">${err.message}</div>`); }
}
// Chain-head anchors kept outside Db2: they catch a ledger rebuilt consistently, which VERIFY_CHAIN cannot.
function anchorBanner(a) {
  if (a.status === "OK" && !a.unanchored_rows)
    return html`<div class="banner ok"><strong>Anchors match.</strong><span>${a.anchors} chain-head anchor${a.anchors === 1 ? "" : "s"} kept outside Db2 cover entries 1 to ${a.covered_through}, so they were not rebuilt since.</span></div>`;
  if (a.status === "OK")
    return html`<div class="banner fix"><strong>Anchors match up to #${a.covered_through}.</strong><span>${a.detail}</span></div>`;
  if (a.status === "OFF" || a.status === "NO_ANCHORS")
    return html`<div class="banner fix"><strong>${a.status === "OFF" ? "Anchoring is off." : "No anchors yet."}</strong><span>${a.status === "OFF" ? "Set ASOF_ANCHOR_KEY (setup generates one) to anchor the chain head outside Db2." : "The next recorded check writes the first chain-head anchor."}</span></div>`;
  return html`<div class="banner bad"><strong>Anchor check: ${a.status.replaceAll("_", " ").toLowerCase()}${a.first_bad_anchor ? ` at anchor ${a.first_bad_anchor}` : ""}.</strong><span>${a.detail}</span></div>`;
}
function sqlBlock(createdAt, asOf, clauseId) {
  return raw(`<pre class="sql"><span class="kw">SELECT</span> VERSION_LABEL, CLAUSE_TEXT
<span class="kw">FROM</span> ASOF.POLICY_CLAUSE
  <span class="kw">FOR SYSTEM_TIME AS OF</span> '${esc(sqlTs(createdAt))}'   <span class="cm">-- what Db2 held when the answer was given${health.clock ? ` (${esc(health.clock)})` : ""}</span>
  <span class="kw">FOR BUSINESS_TIME AS OF</span> '${esc(String(asOf))}'          <span class="cm">-- the customer's date</span>
<span class="kw">WHERE</span> CLAUSE_ID = '${esc(clauseId)}'</pre>`);
}
function replayCol(title, when, row, changed) {
  return html`<div class="replay-col ${changed ? "changed" : ""}">
    <h3>${title}</h3><div class="when">${when}</div>
    ${row ? html`<div class="row wrap">${clauseRef(row.clause_id, row.version_label, row.bus_start, row.bus_end)}</div><div class="sep"></div><p>${row.clause_text}</p>`
      : html`<p class="muted">No row.</p>`}</div>`;
}
async function LedgerEntry(id) {
  mount(view, html`<div class="loading"><div class="spinner"></div>Loading entry #${id} and replaying it in Db2...</div>`);
  const [{ body: e }, { body: rp }] = await Promise.all([api(`/api/ledger/${id}`), api(`/api/ledger/${id}/replay`)]);
  mount(view, html`
    <div class="page-head">
      <div><a href="#/ledger">← Ledger</a><h1>Ledger entry #${e.ledger_id}</h1>
        <p>Recorded ${fmtTs(e.created_at)} for a customer date of ${fmtDate(e.as_of_date)} via ${e.channel}. Model <code>${e.model_info}</code>, prompt version <code>${e.prompt_version}</code>, ${(e.latency_ms / 1000).toFixed(1)} s.</p></div>
      <div class="row">${pill(e.decision)}<button class="btn ghost sm" id="evidence" title="The decision, its claims and clause versions, the replay, the chain check and the receipt, in one JSON file for a dispute">Evidence pack</button><button class="btn ghost sm" id="verify">Verify hash chain</button></div>
    </div>
    <div id="chain"></div>
    ${reviewLink(e)}
    <div class="card">
      <div class="card-head"><h2>Replay</h2><span class="sub">What did the policy say for ${fmtDate(e.as_of_date)}, what did Db2 hold when we answered, and what applies today?</span></div>
      ${rp.clauses.length ? html`<div class="replay-sql">${sqlBlock(rp.created_at, rp.as_of_date, rp.clauses[0].clause_id)}</div>` : ""}
      ${rp.clauses.length ? rp.clauses.map((c) => html`
        <div class="stack">
          <div class="row">${pill(c.status)}<strong><code>${c.clause_id}</code></strong>
            <span class="muted small">${c.status === "UNCHANGED" ? "The version in force for that date is still the one this decision used." : "The policy for that customer date has changed since this decision."}</span></div>
          <div class="cols-3">
            ${replayCol("Row the decision used", c.used ? `recorded in Db2 ${fmtTs(c.used.sys_start)}` : "", c.used, false)}
            ${replayCol("Db2 at decision time", `FOR SYSTEM_TIME AS OF ${fmtTs(rp.created_at)}`, c.held_at_decision, false)}
            ${replayCol("In force today for that date", `FOR BUSINESS_TIME AS OF ${rp.as_of_date}`, c.in_force_now, c.status !== "UNCHANGED")}
          </div>
        </div><div class="sep"></div>`) : html`<p class="muted">This decision cited no clause.</p>`}
    </div>
    <div class="cols-2">
      <div class="card"><div class="eyebrow">Question (redacted)</div><div class="sep"></div><div class="answer">${e.question_redacted}</div>
        <div class="sep"></div><div class="eyebrow">Draft (redacted)</div><div class="sep"></div><div class="answer struck">${e.draft_redacted}</div></div>
      <div class="card"><div class="eyebrow">Released to the customer</div><div class="sep"></div><div class="answer final">${e.final_answer}</div>
        <div class="sep"></div><dl class="kv"><dt>Previous hash</dt><dd class="hash">${e.prev_hash}</dd><dt>Row hash</dt><dd class="hash">${e.row_hash}</dd><dt>Reason</dt><dd>${sentence(e.reason_code)}${e.uncovered && e.uncovered.length ? `: no clause in force on ${fmtDate(e.as_of_date)} covers ${quoted(e.uncovered)}` : ""}</dd></dl></div>
    </div>
    <div class="card"><div class="card-head"><h2>Claim citations</h2><span class="sub">CLAIM_CITATION rows, shredded from the hashed verdict JSON by JSON_TABLE</span></div>
      <table><thead><tr><th>Check</th><th>#</th><th>Claim</th><th>Verdict</th><th>Judge</th><th>Rule</th><th>Clause</th></tr></thead>
      <tbody>${e.citations.map((c) => html`<tr><td>${c.pass_no === 1 ? "draft" : "rewrite"}</td><td>${c.claim_no}</td><td>${c.claim_text}</td>
        <td>${pill(c.verdict)}</td><td class="small">${(c.llm_verdict || "").replaceAll("_", " ").toLowerCase()}</td><td class="small">${c.rule_check.replaceAll("_", " ").toLowerCase()}</td>
        <td>${c.clause_id ? html`<code>${c.clause_id}</code> ${c.clause_version}` : html`<span class="muted">none</span>`}</td></tr>`)}</tbody></table></div>`);
  $("#verify").addEventListener("click", verifyChain);
  $("#evidence").addEventListener("click", async () => {
    const btn = $("#evidence"); btn.disabled = true;
    try {
      const { body } = await api(`/api/ledger/${e.ledger_id}/evidence`);
      const url = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: "application/json" }));
      const a = Object.assign(document.createElement("a"), { href: url, download: `asof-evidence-${e.ledger_id}.json` });
      document.body.append(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) { mount($("#chain"), html`<div class="error-box">${err.message}</div>`); }
    finally { btn.disabled = false; }
  });
}

// ---------- Specialist inbox ----------
// Held decisions wait here for a person. The reply is checked like any other answer and appended to the ledger
// by RESOLVE_ESCALATION as a REVIEWED decision; Db2 refuses a reply that contradicts the policy in force.
let REVIEW_REPLIES = [];  // suggested replies for the built-in held scenarios (scenarios.json; replay mode has them)
const inb = { id: null, reply: "", note: "", check: null, busy: false, sent: null };
const WHY_HELD = {
  NOT_COVERED: "No clause in force on the customer's date covers at least one claim.",
  UNCHECKED_DETAILS: "The draft states details the claim check never covered.",
  CORRECTION_FAILED: "The draft contradicted the policy, and the rewrite did not pass the re-check.",
  TOO_MANY_CLAIMS: "The draft makes more than 8 policy claims.",
  ERROR_FAIL_CLOSED: "A check step failed, so the answer was held (fail closed).",
  LEDGER_UNAVAILABLE: "The decision could not be recorded, so nothing was released.",
  RELEASE_REFUSED: "Db2 refused to record the release: a claim lacked a quoted clause version in force on the customer's date.",
  ROUTE_UNCERTAIN: "AsOf could not tell which policy document the question is about, so it did not guess.",
};
function reviewLink(e) {
  if (!e.review) return "";
  if (e.decision === "ESCALATED")
    return html`<div class="banner ok"><strong>Answered by a specialist.</strong><span>Ledger entry <a href="#/ledger/${e.review.review_ledger_id}">#${e.review.review_ledger_id}</a> holds the reply${e.review.reviewer ? html` from <code>${e.review.reviewer}</code>` : ""} (${String(e.review.outcome).replaceAll("_", " ").toLowerCase()}).</span></div>`;
  return html`<div class="banner ok"><strong>A specialist's reply.</strong><span>It answers held decision <a href="#/ledger/${e.review.escalated_ledger_id}">#${e.review.escalated_ledger_id}</a>${e.review.reviewer ? html`, from <code>${e.review.reviewer}</code>` : ""}. ${e.review.note ? html`Note on record: ${e.review.note}` : "Every claim in it was supported by the policy in force on the customer's date."}</span></div>`;
}
const waited = (m) => (m < 60 ? `${m} min` : m < 2880 ? `${Math.round(m / 60)} h` : `${Math.round(m / 1440)} days`);
async function Inbox(id) {
  const target = id ? Number(id) : null;
  if (target !== inb.id) Object.assign(inb, { id: target, reply: "", note: "", doc: null, check: null, sent: null });
  mount(view, html`
    <div class="page-head"><div><h1>Specialist inbox</h1>
      <p>Answers AsOf held back wait here for a person. The specialist reads every claim and the clause version it was checked against, writes the reply, and AsOf checks it against the policy in force on the customer's date before it goes out. The SQL PL procedure <code>RESOLVE_ESCALATION</code> appends it to the hash-chained ledger as a <code>REVIEWED</code> decision linked to the held one. Db2 refuses a reply that contradicts the policy, and keeps the specialist's note when no clause covers it.</p></div></div>
    <div class="grid-2 inbox">
      <section id="inbox-list"><div class="loading"><div class="spinner"></div>Loading the queue from Db2...</div></section>
      <section id="inbox-detail">${inb.id ? html`<div class="loading"><div class="spinner"></div>Loading held decision #${inb.id}...</div>`
        : html`<div class="empty"><h3>Pick a held answer</h3><p>The oldest is at the top. Held answers come from the playground, the customer chat and the API whenever a check could not release a draft.</p></div>`}</section>
    </div>
    <section id="inbox-notices" class="inbox-notices"></section>`);
  const { body: q } = await api("/api/reviews");
  mount($("#inbox-list"), html`
    <div class="card">
      <div class="inbox-stats"><div><b>${q.counts.open}</b><span>waiting</span></div><div><b>${q.counts.open ? waited(q.counts.oldest_open_minutes) : "none"}</b><span>oldest wait</span></div><div><b>${q.counts.answered}</b><span>answered</span></div></div>
      <div class="sep"></div>
      ${q.open.length ? html`<div class="inbox-items">${q.open.map((i) => inboxItem(i, false))}</div>` : html`<p class="muted">Nothing is waiting. A check that cannot release a draft lands here.</p>`}
    </div>
    ${q.answered.length ? html`<div class="card"><div class="card-head"><h2>Answered</h2><span class="sub">latest first</span></div>
      <div class="inbox-items">${q.answered.slice(0, 12).map((i) => inboxItem(i, true))}</div></div>` : ""}`);
  loadInboxNotices();
  if (inb.id) await renderReview();
  else if (!q.open.length) mount($("#inbox-detail"), html`<div class="empty"><h3>Nothing to review</h3><p>Every check so far was released or already answered. Held answers come from the playground, the customer chat and the API whenever a check could not release a draft.</p></div>`);
}
async function loadInboxNotices(message) {
  const el = $("#inbox-notices");
  if (!el) return;
  let list;
  try { list = (await api("/api/notices?status=PENDING")).body || []; } catch (err) { mount(el, html`<div class="error-box">${err.message}</div>`); return; }
  if (!list.length && !message) { mount(el, ""); return; }
  mount(el, html`${message ? html`<div class="banner ok"><span>${message}</span></div>` : ""}<div class="card"><div class="card-head"><h2>Correction notices to approve</h2><span class="sub">drafted after a policy change; <a href="#/impact">Change impact</a> drafts them</span></div>
    ${list.length ? list.map(noticeCard) : html`<p class="muted">No notice is waiting.</p>`}</div>`);
}
function inboxItem(i, done) {
  const uncovered = !done && i.uncovered && i.uncovered.length ? quoted(i.uncovered) : "";
  return html`<a class="inbox-item ${inb.id === i.ledger_id ? "on" : ""}" href="#/inbox/${i.ledger_id}">
    <div class="row"><b>#${i.ledger_id}</b>${pill(done ? i.outcome : i.reason_code, done ? "reviewed" : "escalated")}</div>
    <div class="muted small">${DOC_NAME[i.doc_id] || i.doc_id} · ${fmtDate(i.as_of_date)} · ${i.channel}</div>
    <div class="trunc" title="${i.question}">${i.question}</div>
    ${uncovered ? html`<div class="trunc small reason-claim" title="No clause covers ${uncovered}">No clause covers ${uncovered}</div>` : ""}
    <div class="muted small">${done ? html`answered in ${waited(i.minutes_to_answer)} as #${i.review_ledger_id}${i.reviewer ? ` by ${i.reviewer}` : ""}` : `waiting ${waited(i.waiting_minutes)}`}</div></a>`;
}
function reviewClaim(c) {
  return html`<div class="claim ${lower(c.verdict)}">
    <div class="claim-top">${pill(c.verdict)}<div class="claim-text">${c.text}</div></div>
    ${c.clause_id ? html`<div class="row wrap small">${clauseRef(c.clause_id, c.clause_version, c.effective_from || c.clause_bus_start, c.effective_to)}</div>` : ""}
    <div class="reason">${c.reason}</div></div>`;
}
async function renderReview() {
  const box = $("#inbox-detail");
  let d;
  try { d = (await api(`/api/reviews/${inb.id}`)).body; } catch (err) { mount(box, html`<div class="error-box">${err.message}</div>`); return; }
  if (!box.isConnected) return;
  const suggested = REVIEW_REPLIES.find((r) => r.question === d.question);
  if (!inb.reply && !d.answered) inb.reply = d.rewrite || "";
  const first = d.claims.filter((c) => c.pass === 1);
  mount(box, html`
    <div class="decision escalated"><div class="icon">${ICONS.ESCALATED}</div>
      <div><div class="row">${pill("ESCALATED")}<h2>Held decision #${d.ledger_id}</h2></div>
        <p>${d.reason_code === "NOT_COVERED" && d.uncovered && d.uncovered.length
          ? `No clause in force on the customer's date covers ${d.uncovered.length === 1 ? "this claim" : "these claims"}: ${quoted(d.uncovered)}.`
          : WHY_HELD[d.reason_code] || d.reason_code} Customer date ${fmtDate(d.as_of_date)}, ${DOC_NAME[d.doc_id] || d.doc_id}, via ${d.channel}.</p></div>
      <div class="meta">held ${fmtTs(d.created_at)}<br><a href="#/ledger/${d.ledger_id}">Ledger entry #${d.ledger_id} →</a></div></div>
    <div class="cols-2">
      <div class="card"><div class="eyebrow">Customer question (redacted)</div><div class="sep"></div><div class="answer">${d.question}</div>
        <div class="sep"></div><div class="eyebrow">Assistant's draft, not sent</div><div class="sep"></div><div class="answer struck">${d.draft}</div>
        ${d.unchecked.length ? html`<p class="small muted">Details no claim covered: ${d.unchecked.join(", ")}</p>` : ""}</div>
      <div class="card"><div class="eyebrow">Policy in force on ${fmtDate(d.as_of_date)}, nearest the question</div><div class="sep"></div>
        <div class="stack">${d.in_force.map((c) => html`<div><div class="row wrap">${clauseRef(c.clause_id, c.version, c.from, c.to)}<span class="small muted">${c.title}</span></div><p class="small">${c.text}</p></div>`)}</div></div>
    </div>
    <div class="card"><div class="card-head"><h2>Why the check held it</h2><span class="sub">each claim of the draft and the clause version it was checked against</span></div>
      ${first.length ? html`<div class="claims">${first.map(reviewClaim)}</div>` : html`<p class="muted">No claims were judged before the check stopped.</p>`}</div>
    ${d.answered && inb.sent && inb.sent.ledger_id === d.answered.review_ledger_id ? html`<div class="card" id="reply-result">${sentView(inb.sent)}</div>`
      : d.answered ? html`<div class="banner ok"><strong>Answered.</strong><span>Ledger entry <a href="#/ledger/${d.answered.review_ledger_id}">#${d.answered.review_ledger_id}</a> holds the reply${d.answered.reviewer ? ` from ${d.answered.reviewer}` : ""}, sent ${fmtTs(d.answered.answered_at)}. ${d.answered.note ? `Note: ${d.answered.note}` : ""}</span></div>`
      : html`<form class="card" id="reply-form" autocomplete="off">
      <div class="card-head"><h2>Reply to the customer</h2><span class="sub">checked against the policy in force on ${fmtDate(d.as_of_date)} before it is sent</span></div>
      ${suggested ? html`<div class="field"><div class="chips"><button type="button" class="chip" id="use-suggested">Use the suggested reply for this scenario</button></div></div>` : ""}
      ${d.reason_code === "ROUTE_UNCERTAIN" ? html`<div class="field"><label for="reply-doc">Policy document to check the reply against</label>
        <select id="reply-doc">${[AIRLINE, BANK].map((x) => html`<option value="${x}" ${x === (inb.doc || d.doc_id) ? raw("selected") : ""}>${DOC_NAME[x]}</option>`)}</select>
        <div class="hint">The router could not tell; you decide. The reply is checked against this document's clauses for ${fmtDate(d.as_of_date)}.</div></div>` : ""}
      <div class="field"><label for="reply">Reply</label><textarea id="reply" rows="5" maxlength="3500" required>${inb.reply}</textarea>
        <div class="hint">Policy statements in the reply are checked like the assistant's. ${d.rewrite ? "Started from AsOf's rewrite, which did not pass on its own." : ""}</div></div>
      <div class="field"><label for="note">Note for the record</label><textarea id="note" rows="2" maxlength="1000">${inb.note}</textarea>
        <div class="hint">Required when no clause covers part of the reply: your judgment, kept with it in the ledger.</div></div>
      <div class="field row"><button class="btn ghost" type="button" id="check-reply" ${inb.busy ? raw("disabled") : ""}>Check reply</button>
        <button class="btn" type="submit" id="send-reply" ${inb.busy ? raw("disabled") : ""}>Check and send</button></div>
      <div id="reply-result">${inb.sent ? sentView(inb.sent) : inb.check ? replyCheckView(inb.check) : ""}</div>
    </form>`}`);
  const form = $("#reply-form");
  if (!form) return;
  const sync = () => { inb.reply = $("#reply").value; inb.note = $("#note").value; inb.doc = $("#reply-doc") ? $("#reply-doc").value : null; };
  if (suggested) $("#use-suggested").addEventListener("click", () => {  // fill in place: a re-render could race a quick send
    inb.reply = suggested.reply; inb.note = suggested.note || "";
    $("#reply").value = inb.reply; $("#note").value = inb.note; $("#reply").focus();
  });
  const run = async (send) => {
    sync();
    inb.busy = true;
    mount($("#reply-result"), html`<div class="loading"><div class="spinner"></div>Checking the reply against Db2's clauses for ${fmtDate(d.as_of_date)}...</div>`);
    $$("#reply-form button").forEach((b) => { b.disabled = true; });
    try {
      const res = await fetchReply(send, { reply: inb.reply, note: inb.note || null, ...(inb.doc ? { doc_id: inb.doc } : {}) });
      if (res.sent) { inb.sent = res.body; inb.check = res.body.check; } else { inb.check = res.body.check || res.body; inb.checkError = res.error; }
    } catch (err) { inb.check = null; mount($("#reply-result"), html`<div class="error-box">${err.message}</div>`); inb.busy = false; return; }
    inb.busy = false;
    if (inb.sent) { Inbox(String(inb.id)); return; }
    renderReview();
  };
  $("#check-reply").addEventListener("click", () => run(false));
  form.addEventListener("submit", (e) => { e.preventDefault(); run(true); });
}
async function fetchReply(send, data) {
  // A refused reply is a 409 or 422 that carries the reply's check; show it rather than a bare error.
  const headers = { "content-type": "application/json" };
  const token = savedToken();
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(`/api/reviews/${inb.id}/${send ? "resolve" : "check"}`, { method: "POST", headers, body: JSON.stringify(data) });
  if (res.status === 401) { askToken(); throw new Error("This AsOf server needs an API token: enter it at the top of the page."); }
  let body = null;
  try { body = await res.json(); } catch { /* empty */ }
  if (res.ok) return { sent: send, body };
  if (body && body.check) return { sent: false, body: { ...body.check, message: body.error }, error: body.error };
  throw new Error(errorText(body, res.status));
}
function replyCheckView(c) {
  const head = c.sendable
    ? (c.needs_note ? html`<div class="banner fix"><strong>Sendable with a note.</strong><span>${c.note_reason}</span></div>`
      : html`<div class="banner ok"><strong>Passes the check.</strong><span>${c.claims.length ? "Every policy claim in the reply is supported by the clause version in force." : "The reply makes no policy claims."} Nothing has been sent yet.</span></div>`)
    : html`<div class="banner bad"><strong>Cannot be sent.</strong><span>${c.message}</span></div>`;
  return html`${head}${c.claims.length ? html`<div class="claims">${c.claims.map(reviewClaim)}</div>` : ""}`;
}
function sentView(s) {
  return html`<div class="banner ok"><strong>Sent.</strong><span>Recorded as ledger entry <a href="#/ledger/${s.ledger_id}">#${s.ledger_id}</a> (${s.outcome.replaceAll("_", " ").toLowerCase()}).</span></div>
    <div class="answer final">${s.final_answer}</div>`;
}

// ---------- Ask the ledger ----------
let ASK_EXAMPLES = [];  // from scenarios.json
const ask = { question: "", result: null, busy: false, scope: "all", scopes: null };
async function Ask() {
  if (!ask.scopes) {
    try { ask.scopes = (await api("/api/ledger/ask/scopes")).body; } catch { ask.scopes = [{ key: "all", label: "All domains", user: "asofread", doc_ids: [] }]; }
  }
  const scope = ask.scopes.find((s) => s.key === ask.scope) || ask.scopes[0];
  mount(view, html`
    <div class="page-head"><div><h1>Ask the ledger</h1>
      <p>Plain-English questions for auditors, answered by a LangChain SQL chain over SQLAlchemy (<code>ibm_db_sa</code>). It runs as a read-only Db2 analyst, which can only SELECT six audit views: <code>asofread</code> for every domain, or one domain's own analyst. SQLGlot checks every generated query before it runs, Db2's column masks hide the customer's question and our reply, and Db2's row permissions return a domain analyst only that domain's decisions.</p></div></div>
    <div class="grid-2">
      <form class="card" id="ask-form" autocomplete="off">
        <div class="field"><label>Scope</label>
          <div class="seg" role="group" aria-label="Scope">${ask.scopes.map((s) => html`<button type="button" data-scope="${s.key}" class="${s.key === scope.key ? "on" : ""}">${s.label}</button>`)}</div>
          <div class="hint">Runs as <code>${scope.user}</code>${scope.key === "all" ? "" : html`, which Db2 lets see ${scope.doc_ids.join(", ")} only, whatever the SQL asks for`}.</div></div>
        <div class="sep"></div>
        <div class="field"><label>Examples</label>
          <div class="chips">${ASK_EXAMPLES.map((x, i) => html`<button type="button" class="chip ${x === ask.question ? "on" : ""}" data-ex="${i}">${x}</button>`)}</div></div>
        <div class="sep"></div>
        <div class="field"><label for="aq">Question</label>
          <textarea id="aq" rows="3" minlength="3" maxlength="500" required>${ask.question}</textarea>
          <div class="hint">Only one SELECT on the audit views can run. Nothing here can change the ledger.</div></div>
        <div class="field"><button class="btn block" id="ask-run" type="submit" ${ask.busy ? raw("disabled") : ""}>${ask.busy ? "Asking..." : "Ask"}</button></div>
      </form>
      <section id="ask-result">${ask.result ? askView(ask.result) : html`<div class="empty"><h3>No question asked yet</h3><p>Pick an example or write your own. The SQL that ran is shown with every answer.</p></div>`}</section>
    </div>`);
  const form = $("#ask-form");
  form.addEventListener("click", (e) => {
    const b = e.target.closest("[data-ex]");
    if (b) { ask.question = ASK_EXAMPLES[Number(b.dataset.ex)]; Ask(); }
    const s = e.target.closest("[data-scope]");
    if (s) { ask.question = $("#aq").value; ask.scope = s.dataset.scope; Ask(); }
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    ask.question = $("#aq").value.trim();
    ask.busy = true;
    mount($("#ask-result"), html`<div class="loading"><div class="spinner"></div>Writing SQL, checking it, running it in Db2 as ${scope.user}...</div>`);
    $("#ask-run").disabled = true;
    try {
      ask.result = (await post("/api/ledger/ask", { question: ask.question, scope: scope.key })).body;
    } catch (err) {
      ask.result = { status: "ERROR", reason: err.message, attempts: [], rows: [], columns: [] };
    }
    ask.busy = false;
    Ask();
  });
}
function askView(r) {
  const head = {
    ANSWERED: html`<div class="banner ok"><strong>Answered.</strong><span>${r.rows.length} row${r.rows.length === 1 ? "" : "s"}${r.truncated ? " (capped)" : ""} in ${(r.latency_ms / 1000).toFixed(1)} s, as ${r.runs_as}.${r.scope_applied ? html` Scope Db2 applied: ${r.scope_applied.length ? r.scope_applied.join(", ") : "no policy document"}.` : ""}</span></div>`,
    REFUSED: html`<div class="banner bad"><strong>Refused.</strong><span>No query ran. ${r.reason}</span></div>`,
    FAILED: html`<div class="banner bad"><strong>Db2 rejected the query.</strong><span>${r.reason}</span></div>`,
    ERROR: html`<div class="banner bad"><strong>Not available.</strong><span>${r.reason}</span></div>`,
  }[r.status];
  const attempts = (r.attempts || []).filter((a) => a.refused || a.db2_error);
  return html`${head}
    ${r.answer ? html`<div class="card"><div class="eyebrow">Answer</div><div class="sep"></div><div class="answer final">${r.answer}</div>
      ${r.explanation ? html`<div class="sep"></div><p class="small muted">${r.explanation}</p>` : ""}</div>` : ""}
    ${r.sql ? html`<div class="card"><div class="card-head"><h2>SQL that ran</h2><span class="sub">regenerated by SQLGlot from the checked parse tree</span></div><pre class="sql">${r.sql}</pre>
      ${r.limit_added ? html`<p class="small muted">AsOf appended <code>FETCH FIRST ${r.row_cap + 1} ROWS ONLY</code> because the query set no limit: at most ${r.row_cap} rows are shown, and the one extra row only tells AsOf whether there were more.</p>` : ""}</div>` : ""}
    ${r.columns && r.columns.length ? html`<div class="card"><div class="card-head"><h2>Rows</h2><span class="sub">straight from Db2; [masked] is Db2's column mask</span></div>
      <div class="scroll-x"><table><thead><tr>${r.columns.map((c) => html`<th>${c}</th>`)}</tr></thead>
      <tbody>${r.rows.map((row) => html`<tr>${row.map((v) => html`<td class="${v === "[masked]" ? "muted" : ""}">${v === null ? "null" : v}</td>`)}</tr>`)}</tbody></table></div></div>` : ""}
    ${attempts.length ? html`<div class="card"><div class="card-head"><h2>Attempts that did not run</h2><span class="sub">the model gets one retry with the reason</span></div>
      ${attempts.map((a) => html`<pre class="sql">${a.proposed_sql}</pre><p class="small">${a.refused ? html`<strong>Refused by the SQLGlot check:</strong> ${a.refused}` : html`<strong>Db2:</strong> ${a.db2_error}`}</p>`)}</div>` : ""}`;
}

// ---------- Change impact ----------
let PRESETS = [];  // from scenarios.json
const imp = { clause: "PET-001", form: null, result: null, applied: null };
function nextVersion(c) { return `v${Math.max(...c.versions.map((v) => Number(v.version.slice(1)))) + 1}`; }
async function Impact() {
  if (!tl.data) tl.data = (await api("/api/policy/timeline")).body;
  const c = tl.data.find((x) => x.clause_id === imp.clause);
  const last = c.versions[c.versions.length - 1];
  if (!imp.form || imp.form.clause !== imp.clause) {
    imp.form = { clause: imp.clause, from: "", to: "", version: nextVersion(c), text: last.text, rule: JSON.stringify(last.rule), note: "" };
  }
  const f = imp.form;
  mount(view, html`
    <div class="page-head"><div><h1>Change impact</h1>
      <p>Preview or apply a policy change as the editor user <code>asofedit</code>. <code>APPLY_POLICY_CHANGE</code> runs <code>UPDATE ... FOR PORTION OF BUSINESS_TIME</code>, so Db2 splits the version and keeps the replaced row in history. <code>CHANGE_IMPACT</code> then finds every released answer and help-centre answer that relied on the clause, and tells stale from historically valid.</p></div></div>
    <div class="grid-2">
      <form class="card" id="imp-form" autocomplete="off">
        <div class="field"><label>Presets</label><div class="chips">${PRESETS.map((p, i) => html`<button type="button" class="chip" data-preset="${i}">${p.label}</button>`)}</div></div>
        <div class="sep"></div>
        <div class="field"><label for="imp-clause">Clause</label>
          <select id="imp-clause">${tl.data.map((x) => html`<option value="${x.clause_id}" ${x.clause_id === imp.clause ? raw("selected") : ""}>${x.clause_id} · ${x.title}</option>`)}</select>
          <div class="hint" id="imp-versions">${c.versions.map((v) => `${v.version}: ${period(v.from, v.to)}`).join(" · ")}</div></div>
        <div class="field row"><div class="grow"><label for="imp-from">Effective from</label><input id="imp-from" type="date" value="${f.from}" required></div>
          <div class="grow"><label for="imp-to">Until (optional)</label><input id="imp-to" type="date" value="${f.to}"></div>
          <div><label for="imp-ver">Version</label><input id="imp-ver" type="text" value="${f.version}" size="4" required></div></div>
        <div class="field"><label for="imp-text">New clause text</label><textarea id="imp-text" rows="4" required>${f.text}</textarea></div>
        <div class="field"><label for="imp-rule">Rule parameters (RULE_JSON)</label><textarea id="imp-rule" class="code" rows="3" required>${f.rule}</textarea></div>
        <div class="field"><label for="imp-note">Change note</label><input id="imp-note" type="text" value="${f.note}" maxlength="400" required></div>
        <div class="field"><button class="btn block" id="imp-apply" type="submit">Apply change as asofedit</button></div>
        <div class="field row"><button class="btn ghost grow" id="imp-preview" type="button" title="Db2 applies the change and computes its impact in one transaction, then rolls it back">Preview impact</button><button class="btn ghost" id="imp-show" type="button">Impact only</button></div>
      </form>
      <section id="imp-result">${imp.result ? impactView(imp.result, imp.applied) : html`<div class="empty"><h3>Nothing applied yet</h3>
        <p>Record a couple of answers about pets in the <a href="#/playground">Playground</a> (the December pet-fee scenario, and the same question for a November date), then apply the pet fee preset.</p></div>`}</section>
    </div>`);
  if (imp.result) loadSuggestions();
  const form = $("#imp-form");
  const sync = () => Object.assign(imp.form, { from: $("#imp-from").value, to: $("#imp-to").value, version: $("#imp-ver").value.trim(),
    text: $("#imp-text").value, rule: $("#imp-rule").value, note: $("#imp-note").value });
  form.addEventListener("click", (e) => {
    const p = e.target.closest("[data-preset]");
    if (!p) return;
    const x = PRESETS[Number(p.dataset.preset)];
    const cl = tl.data.find((y) => y.clause_id === x.clause);
    imp.clause = x.clause;
    imp.form = { clause: x.clause, from: x.from, to: "", version: nextVersion(cl), text: x.text, rule: JSON.stringify(x.rule), note: x.note };
    Impact();
  });
  $("#imp-clause").addEventListener("change", (e) => { imp.clause = e.target.value; imp.form = null; imp.result = null; Impact(); });
  $("#imp-preview").addEventListener("click", async () => {
    sync();
    const btn = $("#imp-preview"); btn.disabled = true;
    try {
      let rule;
      try { rule = JSON.parse(imp.form.rule); } catch { throw new Error("Rule parameters must be valid JSON."); }
      const { body } = await post("/api/policy/preview", { clause_id: imp.clause, effective_from: imp.form.from,
        effective_to: imp.form.to || null, version_label: imp.form.version, clause_text: imp.form.text, rule, change_note: imp.form.note });
      imp.result = body.impact; imp.applied = body;
      mount($("#imp-result"), impactView(imp.result, imp.applied));
    } catch (err) {
      mount($("#imp-result"), html`<div class="error-box">${err.message}</div>`);
    } finally { btn.disabled = false; }
  });
  $("#imp-show").addEventListener("click", async () => {
    sync();
    imp.result = (await api(`/api/impact/${imp.clause}`)).body; imp.applied = null;
    mount($("#imp-result"), impactView(imp.result, null));
    loadSuggestions();
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault(); sync();
    const btn = $("#imp-apply"); btn.disabled = true;
    try {
      let rule;
      try { rule = JSON.parse(imp.form.rule); } catch { throw new Error("Rule parameters must be valid JSON."); }
      const { body } = await post("/api/policy/change", { clause_id: imp.clause, effective_from: imp.form.from,
        effective_to: imp.form.to || null, version_label: imp.form.version, clause_text: imp.form.text, rule, change_note: imp.form.note });
      imp.result = body.impact; imp.applied = body;
      tl.data = null; tl.sel = null;
      tl.data = (await api("/api/policy/timeline")).body;
      // The clause now has one more version: show it, and offer the next label for another change.
      const fresh = tl.data.find((x) => x.clause_id === imp.clause);
      if (fresh) {
        $("#imp-versions").textContent = fresh.versions.map((v) => `${v.version}: ${period(v.from, v.to)}`).join(" · ");
        imp.form.version = nextVersion(fresh); $("#imp-ver").value = imp.form.version;
      }
      mount($("#imp-result"), impactView(imp.result, imp.applied));
      loadSuggestions();
    } catch (err) {
      mount($("#imp-result"), html`<div class="error-box">${err.message}</div>`);
    } finally { btn.disabled = false; }
  });
}
function impactView(rows, applied) {
  const answers = rows.filter((r) => r.kind === "ANSWER");
  const pubs = rows.filter((r) => r.kind === "PUBLISHED");
  const n = (arr, s) => arr.filter((r) => r.status === s).length;
  return html`
    ${applied && applied.preview ? html`<div class="banner fix"><strong>Preview only: nothing was saved.</strong><span>Db2 applied the change with FOR PORTION OF BUSINESS_TIME, ran CHANGE_IMPACT on the result and rolled the transaction back. ${applied.published_flagged} help-centre answer${applied.published_flagged === 1 ? " would" : "s would"} be flagged for review. Apply the change to make it real.</span></div>` : ""}
    ${applied && !applied.preview ? html`<div class="banner ok"><strong>Change applied.</strong><span>Db2 split ${applied.rows_changed} row${applied.rows_changed === 1 ? "" : "s"} with FOR PORTION OF BUSINESS_TIME; the replaced row moved to POLICY_CLAUSE_HIST. ${applied.published_flagged} help-centre answer${applied.published_flagged === 1 ? " was" : "s were"} flagged for review. <a href="#/timeline">See it on the timeline →</a></span></div>` : ""}
    <div class="cols-3 impact-stats">
      <div class="stat bad"><div class="n">${n(answers, "STALE")}</div><div class="l">released answers now stale</div></div>
      <div class="stat good"><div class="n">${n(answers, "HISTORICALLY_VALID")}</div><div class="l">answers still right for their date</div></div>
      <div class="stat warn"><div class="n">${n(pubs, "NEEDS_REVIEW")}</div><div class="l">help-centre answers to review</div></div>
    </div>
    <div class="card"><div class="card-head"><h2>Released answers that cited ${imp.clause}</h2><span class="sub">judged against the policy as it stands now</span></div>
      ${answers.length ? html`<table><thead><tr><th>Entry</th><th>Customer date</th><th>Cited</th><th>Now in force</th><th>Status</th></tr></thead><tbody>
        ${answers.map((r) => html`<tr><td><a href="#/ledger/${r.ref_id}">#${r.ref_id}</a></td><td>${fmtDate(r.for_from)}</td><td>${r.cited_version}</td><td>${r.current_version}</td>
          <td>${pill(r.status)}<div class="small muted">${r.status === "STALE" ? "the customer was told the old policy for a date it no longer covers" : "correct for the customer's date"}</div></td></tr>`)}
      </tbody></table>` : html`<p class="muted">No released answers cite ${imp.clause} yet.</p>`}</div>
    <div class="card"><div class="card-head"><h2>Help-centre answers citing ${imp.clause}</h2><span class="sub">PUBLISHED_ANSWER</span></div>
      ${pubs.length ? html`<table><thead><tr><th>Answer</th><th>Covers</th><th>Cited</th><th>Versions in that range now</th><th>Status</th></tr></thead><tbody>
        ${pubs.map((r) => html`<tr><td><code>${r.ref_id}</code></td><td>${period(r.for_from, r.for_to)}</td><td>${r.cited_version}</td><td>${r.current_version}</td>
          <td>${pill(r.status)}${r.stale_from ? html`<div class="small muted">wrong from ${fmtDate(r.stale_from)}</div>` : ""}</td></tr>`)}
      </tbody></table>` : html`<p class="muted">No help-centre answer cites ${imp.clause}.</p>`}</div>
    <section id="imp-notices"></section>
    <section id="imp-sugg"></section>`;
}

// Correction notices: for each released answer now stale for its customer's date, the agent drafts a correction,
// the full check runs on that date, and a specialist approves it for sending (AsOf sends nothing itself).
const ntc = { list: [] };
async function loadNotices() {
  const el = $("#imp-notices");
  if (!el) return;
  try { ntc.list = (await api(`/api/notices?clause_id=${imp.clause}`)).body || []; } catch (err) { mount(el, html`<div class="error-box">${err.message}</div>`); return; }
  mount(el, noticesView());
}
function noticesView() {
  const open = new Set(ntc.list.filter((n) => n.status !== "REJECTED").map((n) => `${n.ledger_id}/${n.current_version}`));
  const stale = (imp.result || []).filter((r) => r.kind === "ANSWER" && r.status === "STALE" && !open.has(`${r.ref_id}/${r.current_version}`));
  return html`<div class="card"><div class="card-head"><h2>Correction notices for customers</h2><span class="sub">change-impact agent · a specialist approves each one before it counts as sent</span></div>
    ${stale.length ? html`<p class="muted">${stale.length} released answer${stale.length === 1 ? " is" : "s are"} now wrong for the customer's date. For each, the agent looks up what else the answer relied on, drafts a correction from the clause text now in force for that date, and runs the full check on it. Db2's <code>ADD_NOTICE</code> verifies the claims made about each notice before storing it.</p>
      <button class="btn" id="notice-run" type="button">Draft correction notices with the agent</button>` : ""}
    ${ntc.list.length ? ntc.list.map(noticeCard) : stale.length ? "" : html`<p class="muted">No answer citing ${imp.clause} is stale for its customer's date, so no customer needs a correction.</p>`}
  </div>`;
}
function noticeCard(n) {
  const released = n.check_decision === "PASS" || n.check_decision === "CORRECTED";
  const looked = (n.agent_trace || []).filter((t) => t.tool).map((t) => `${t.tool}(${Object.values(t.args || {}).join(", ")})`);
  return html`<div class="sugg notice">
    <div class="sugg-head"><a href="#/ledger/${n.ledger_id}">answer #${n.ledger_id}</a><span class="when">customer date ${fmtDate(n.as_of_date)}, ${n.clause_id} ${n.cited_version} → ${n.current_version}</span>
      ${pill(n.check_decision)}${pill(n.status)}${n.check_ledger_id ? html`<a class="small" href="#/ledger/${n.check_ledger_id}">check #${n.check_ledger_id} →</a>` : ""}</div>
    <p class="sugg-text">${n.notice}</p>
    ${looked.length ? html`<div class="small muted">Agent looked up: ${looked.join(" · ")}</div>` : ""}
    ${n.status === "PENDING" ? html`<div class="row"><button class="btn" type="button" data-notice-approve="${n.notice_id}" ${released ? "" : raw("disabled")}>Approve and mark sent</button>
      <button class="btn ghost" type="button" data-notice-reject="${n.notice_id}">Reject</button>${released ? "" : html`<span class="small muted">The check did not release this correction, so it cannot be sent.</span>`}</div>`
      : html`<div class="small muted">${n.status === "SENT" ? "approved for sending" : "rejected"}${n.decided_by_user ? ` by ${n.decided_by_user}` : ""} at ${fmtTs(n.decided_at)}</div>`}
  </div>`;
}
document.addEventListener("click", async (e) => {
  const run = e.target.closest("#notice-run");
  const approve = e.target.closest("[data-notice-approve]");
  const reject = e.target.closest("[data-notice-reject]");
  if (!run && !approve && !reject) return;
  const btn = run || approve || reject;
  btn.disabled = true;
  const done = async (message) => {
    if ($("#imp-notices")) { await loadNotices(); mount($("#imp-notices"), html`<div class="banner ok"><span>${message}</span></div>${noticesView()}`); }
    else if ($("#inbox-notices")) { await loadInboxNotices(message); }
  };
  try {
    if (run) {
      btn.textContent = "Drafting and checking...";
      const { body } = await post("/api/notices/draft", { clause_id: imp.clause });
      const ok = body.drafted.filter((d) => !d.error).length;
      const failed = body.drafted.length - ok;
      await done(`The agent drafted ${ok} notice${ok === 1 ? "" : "s"}; each correction went through the full check on its customer's date.${failed ? ` ${failed} could not be drafted (see the server log).` : ""}`);
    } else {
      const id = (approve || reject).dataset.noticeApprove || (approve || reject).dataset.noticeReject;
      await post(`/api/notices/${id}/decision`, { approve: Boolean(approve) });
      await done(approve ? "Approved: the notice is marked sent. AsOf records the decision; your messaging system delivers it." : "Notice rejected; the agent can draft a new one.");
    }
  } catch (err) {
    const el = $("#imp-notices") || $("#inbox-notices");
    if (el) mount(el, html`<div class="error-box">${err.message}</div>`);
  }
});

// Drafted corrections: the change-impact agent drafts, the check runs on each, the editor decides.
const sug = { list: [] };
async function loadSuggestions() {
  loadNotices();
  const el = $("#imp-sugg");
  if (!el) return;
  sug.list = (await api(`/api/suggestions?clause_id=${imp.clause}`)).body || [];
  mount(el, suggestionsView());
}
function suggestionsView() {
  const pending = new Set(sug.list.filter((s) => s.status === "PENDING").map((s) => s.answer_id));
  const needs = (imp.result || []).some((r) => r.kind === "PUBLISHED" && r.status === "NEEDS_REVIEW" && !pending.has(r.ref_id));
  return html`<div class="card"><div class="card-head"><h2>Drafted corrections</h2><span class="sub">change-impact agent · nothing is published until the editor approves</span></div>
    ${needs ? html`<p class="muted">For each help-centre answer that needs review, the agent looks up what else it relies on with Db2 tools, drafts a correction from the clause text in force from the date it went wrong, and runs the full check on that date. Only a draft the check released can be approved; approval keeps the old answer for the dates before the change.</p>
      <button class="btn" id="sugg-run" type="button">Draft corrections with the agent</button>` : ""}
    ${sug.list.length ? sug.list.map(suggestionCard) : needs ? "" : html`<p class="muted">No help-centre answer citing ${imp.clause} needs a correction.</p>`}
    ${!needs && pending.size ? html`<p class="small muted">Every answer that needs review has a draft waiting for a decision.</p>` : ""}
  </div>`;
}
function suggestionCard(s) {
  const released = s.check_decision === "PASS" || s.check_decision === "CORRECTED";
  const looked = (s.agent_trace || []).filter((t) => t.tool).map((t) => `${t.tool}(${Object.values(t.args || {}).join(", ")})`);
  return html`<div class="sugg">
    <div class="sugg-head"><code>${s.answer_id}</code><span class="when">for dates from ${fmtDate(s.stale_from)}, written from ${s.clause_id} ${s.based_on_version}</span>
      ${pill(s.check_decision)}${pill(s.status)}${s.check_ledger_id ? html`<a class="small" href="#/ledger/${s.check_ledger_id}">check #${s.check_ledger_id} →</a>` : ""}</div>
    <p class="sugg-text">${s.text}</p>
    ${looked.length ? html`<div class="small muted">Agent looked up: ${looked.join(" · ")}</div>` : html`<div class="small muted">Agent looked up nothing beyond the changed clause.</div>`}
    ${s.status === "PENDING" ? html`<div class="row"><button class="btn" type="button" data-approve="${s.suggestion_id}" ${released ? "" : raw("disabled")}>Approve and publish</button>
      <button class="btn ghost" type="button" data-reject="${s.suggestion_id}">Reject</button>${released ? "" : html`<span class="small muted">The check did not release this draft, so it cannot be published.</span>`}</div>`
      : html`<div class="small muted">${lower(s.status)} by ${s.decided_by} at ${fmtTs(s.decided_at)}</div>`}
  </div>`;
}
async function refreshImpact(message) {
  imp.result = (await api(`/api/impact/${imp.clause}`)).body;
  mount($("#imp-result"), html`${message ? html`<div class="banner ok"><span>${message}</span></div>` : ""}${impactView(imp.result, null)}`);
  await loadSuggestions();
}
document.addEventListener("click", async (e) => {
  const run = e.target.closest("#sugg-run");
  const approve = e.target.closest("[data-approve]");
  const reject = e.target.closest("[data-reject]");
  if (!run && !approve && !reject) return;
  const btn = run || approve || reject;
  btn.disabled = true;
  try {
    if (run) {
      btn.textContent = "Drafting and checking...";
      const { body } = await post(`/api/impact/${imp.clause}/suggestions`, {});
      const n = body.drafted.length;
      await refreshImpact(`The agent drafted ${n} correction${n === 1 ? "" : "s"}; each one went through the full check on the date it must hold from.`);
    } else {
      const id = (approve || reject).dataset.approve || (approve || reject).dataset.reject;
      const { body } = await post(`/api/suggestions/${id}/decision`, { approve: Boolean(approve) });
      await refreshImpact(approve ? `Published as ${body.published_answer_id}; the old answer keeps the dates before the change.` : "Suggestion rejected.");
    }
  } catch (err) {
    const el = $("#imp-sugg");
    if (el) mount(el, html`<div class="error-box">${err.message}</div>${suggestionsView()}`);
  }
});

// ---------- Policy intake ----------
// A policy PDF becomes a draft: the model proposes clause versions, code checks each one against the document,
// and the editor accepts what goes into force (DECIDE_POLICY_DRAFT, then APPLY_DRAFT_ITEM -> APPLY_POLICY_CHANGE).
const itk = { doc: AIRLINE, drafts: [], draft: null, accept: new Set(), result: null, busy: false };
async function sendPdf(path, blob) {
  const headers = { "content-type": "application/pdf" };
  const token = savedToken();
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(path, { method: "POST", body: blob, headers });
  if (res.status === 401) { askToken(); throw new Error("This AsOf server needs an API token: enter it at the top of the page."); }
  let body = null;
  try { body = await res.json(); } catch { /* empty body */ }
  if (!res.ok) throw new Error(errorText(body, res.status));
  return body;
}
async function download(path, filename) {
  const headers = {};
  const token = savedToken();
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(path, { headers });
  if (!res.ok) throw new Error(`Download failed (${res.status})`);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
// Word-level diff (longest common subsequence) between the version in force and the proposal.
function wordDiff(before, after) {
  const a = String(before || "").split(/(\s+)/), b = String(after || "").split(/(\s+)/);
  const n = a.length, m = b.length, dp = Array.from({ length: n + 1 }, () => new Uint16Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const outp = [];
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) { outp.push(html`${a[i]}`); i++; j++; }
    else if (dp[i + 1][j] >= dp[i][j + 1]) { if (a[i].trim()) outp.push(html`<del>${a[i]}</del>`); else outp.push(html`${a[i]}`); i++; }
    else { if (b[j].trim()) outp.push(html`<ins>${b[j]}</ins>`); else outp.push(html`${b[j]}`); j++; }
  }
  while (i < n) { if (a[i].trim()) outp.push(html`<del>${a[i]}</del>`); i++; }
  while (j < m) { outp.push(b[j].trim() ? html`<ins>${b[j]}</ins>` : html`${b[j]}`); j++; }
  return outp;
}
const CHECK_ICON = { pass: "✓", fail: "✕", warn: "!" };
const KIND_LABEL = { CHANGE: "New version", NEW: "New clause", UNCHANGED: "Unchanged" };
function ruleTable(item) {
  const now = (item.current && item.current.rule) || {};
  const keys = [...new Set([...Object.keys(now), ...Object.keys(item.rule || {})])];
  if (!keys.length) return html`<p class="small muted">No checkable parameters.</p>`;
  const show = (v) => (v === undefined ? "–" : Array.isArray(v) ? v.join(", ") : String(v));
  return html`<table class="rule-diff"><thead><tr><th>Parameter</th>${item.kind === "NEW" ? "" : html`<th>Now</th>`}<th>Proposed</th></tr></thead><tbody>
    ${keys.map((k) => { const changed = JSON.stringify(now[k]) !== JSON.stringify((item.rule || {})[k]);
      return html`<tr class="${changed && item.kind !== "NEW" ? "changed" : ""}"><td><code>${k}</code></td>${item.kind === "NEW" ? "" : html`<td>${show(now[k])}</td>`}<td>${show((item.rule || {})[k])}</td></tr>`; })}
  </tbody></table>`;
}
function itemCard(item, decided) {
  const can = !decided && !item.blocked && item.kind !== "UNCHANGED";
  const fails = item.checks.filter((c) => c.status === "fail").length;
  return html`<div class="itk-item ${item.blocked ? "blocked" : ""} ${item.kind === "UNCHANGED" ? "same" : ""}">
    <div class="itk-head">
      <label class="itk-pick"><input type="checkbox" data-item="${item.item_no}" ${can ? "" : raw("disabled")} ${itk.accept.has(item.item_no) ? raw("checked") : ""}
        aria-label="Accept item ${item.item_no}"></label>
      <span class="pill ${item.kind === "NEW" ? "pass" : item.kind === "CHANGE" ? "corrected" : "neutral"}">${KIND_LABEL[item.kind]}</span>
      <b class="mono">${item.clause_id}</b><span class="itk-title">${item.title}</span>
      <span class="when">from ${fmtDate(item.effective_from)}${item.effective_to ? ` until ${fmtDate(item.effective_to)}` : ", open-ended"}${item.source_page ? ` · page ${item.source_page}` : ""}</span>
      ${item.applied_version ? html`<span class="pill pass">In force as ${item.applied_version}</span>`
        : decided ? html`<span class="pill rejected">Not applied</span>`
        : item.blocked ? html`<span class="pill escalated">Blocked: ${fails} check${fails === 1 ? "" : "s"} failed</span>` : ""}
    </div>
    ${item.kind === "CHANGE" && item.current ? html`<div class="itk-diff"><div class="eyebrow">Text: ${item.current.version} in force on that date → proposed</div><p class="diff">${wordDiff(item.current.text, item.clause_text)}</p></div>`
      : html`<div class="itk-diff"><div class="eyebrow">${item.kind === "NEW" ? "Proposed text" : `Same text as ${item.current ? item.current.version : "the version in force"}`}</div><p class="diff">${item.clause_text}</p></div>`}
    <div class="itk-grid">
      <div>${ruleTable(item)}</div>
      <ul class="checks">${item.checks.map((c) => html`<li class="${c.status}"><span class="ci">${CHECK_ICON[c.status]}</span><span><b>${c.check}</b> ${c.detail}</span></li>`)}</ul>
    </div>
  </div>`;
}
function draftView(d) {
  const decided = d.status !== "PENDING";
  const appliable = d.items_detail.filter((i) => !i.blocked && i.kind !== "UNCHANGED").length;
  return html`
    <div class="card">
      <div class="card-head"><h2>Draft ${d.draft_id}: ${d.source_name}</h2>${pill(d.status === "APPLIED" ? "approved" : d.status)}</div>
      <dl class="kv">
        <dt>Document</dt><dd>${DOC_NAME[d.doc_id] || d.doc_id} · ${d.pages} page${d.pages === 1 ? "" : "s"} · <a href="#" id="itk-src">download the file from Db2</a></dd>
        <dt>SHA-256</dt><dd class="hash" title="computed by Db2 over the stored file (ADD_POLICY_DRAFT)">${d.sha256}</dd>
        <dt>Proposed by</dt><dd>${d.extracted_by}</dd>
        <dt>Uploaded</dt><dd>${fmtTs(d.created_at)}${d.uploaded_by ? ` by ${d.uploaded_by}` : ""}</dd>
        ${decided ? html`<dt>Decided</dt><dd>${fmtTs(d.decided_at)} by ${d.decided_by_user || d.decided_by}</dd>` : ""}
      </dl>
    </div>
    ${itk.result ? resultBanner(itk.result) : ""}
    <div class="card"><div class="card-head"><h2>Proposed clause versions</h2><span class="sub">checked against the document by code; nothing is in force until approved</span></div>
      ${d.items_detail.map((i) => itemCard(i, decided))}
      ${decided ? "" : html`<div class="itk-actions">
        <button class="btn" id="itk-approve" type="button" ${appliable ? "" : raw("disabled")}>Approve ${itk.accept.size} selected and apply as asofedit</button>
        <button class="btn ghost" id="itk-preview" type="button" title="Db2 applies the draft and runs CHANGE_IMPACT in one transaction, then rolls it back">Preview impact</button>
        <button class="btn ghost" id="itk-reject" type="button">Reject draft</button>
        <span class="small muted">Approval runs DECIDE_POLICY_DRAFT, then APPLY_DRAFT_ITEM for each accepted item (a changed clause goes through APPLY_POLICY_CHANGE), in one transaction.</span>
      </div>`}
    </div>`;
}
function resultBanner(r) {
  const flagged = r.applied.reduce((n, a) => n + a.published_flagged, 0);
  const versions = r.applied.map((a) => `${a.clause_id} ${a.version}`).join(", ");
  if (r.preview) {
    const stale = Object.values(r.impact || {}).flat().filter((x) => x.kind === "ANSWER" && x.status === "STALE").length;
    return html`<div class="banner fix"><strong>Preview only: nothing was saved.</strong><span>Db2 applied ${versions}, ran CHANGE_IMPACT and rolled back.
      ${stale} released answer${stale === 1 ? "" : "s"} would become stale; ${flagged} help-centre answer${flagged === 1 ? "" : "s"} would need review.</span></div>`;
  }
  if (!r.approved) return html`<div class="banner"><strong>Draft rejected.</strong><span>Nothing changed in the policy.</span></div>`;
  return html`<div class="banner ok"><strong>Approved and in force: ${versions}.</strong><span>${flagged} help-centre answer${flagged === 1 ? " was" : "s were"} flagged for review.
    Each new version's change note names this draft and the file's SHA-256. <a href="#/timeline">See the timeline →</a> · <a href="#/impact">Change impact →</a></span></div>`;
}
async function Intake(arg) {
  itk.drafts = (await api("/api/policy/drafts")).body || [];
  const id = Number(arg) || null;
  if (id && (!itk.draft || itk.draft.draft_id !== id)) {
    itk.draft = (await api(`/api/policy/drafts/${id}`)).body; itk.result = null;
    itk.accept = new Set(itk.draft.status === "PENDING" ? itk.draft.items_detail.filter((i) => !i.blocked && i.kind !== "UNCHANGED").map((i) => i.item_no) : []);
  }
  if (!id) itk.draft = null;
  renderIntake();
}
function renderIntake() {
  mount(view, html`
    <div class="page-head"><div><h1>Policy intake</h1>
      <p>Upload a policy document as the editor. The model proposes clause versions; code checks every one against the document: the clause text must appear word for word, the effective date must be quoted, and every rule value must be stated in the text. You choose what goes into force. The file is stored in Db2 with the SHA-256 Db2 computed, and every version approved from it names the draft it came from.</p></div></div>
    <div class="tl-layout itk-layout">
      <div class="stack">
        <form class="card" id="itk-form" autocomplete="off">
          <div class="field"><label for="itk-doc">Policy document</label>
            <select id="itk-doc">${Object.entries(DOC_NAME).map(([k, v]) => html`<option value="${k}" ${k === itk.doc ? raw("selected") : ""}>${v} (${k})</option>`)}</select></div>
          <div class="field"><label for="itk-file">PDF file</label><input id="itk-file" type="file" accept="application/pdf,.pdf">
            <div class="hint">PDF with a text layer, at most 2 MB and 20 pages.${health.replay ? " Replay mode has a recorded extraction only for the sample." : ""}</div></div>
          <div class="field row"><button class="btn grow" id="itk-upload" type="submit">Extract draft</button>
            <button class="btn ghost grow" id="itk-sample" type="button" title="A fictional revision of the Aurelia Air policy, effective 1 February 2027">Use the sample</button></div>
          <div id="itk-status" aria-live="polite"></div>
        </form>
        <div class="card"><div class="card-head"><h2>Drafts</h2><span class="sub">POLICY_DRAFT</span></div>
          ${itk.drafts.length ? html`<table><tbody>${itk.drafts.map((d) => html`<tr class="click ${itk.draft && itk.draft.draft_id === d.draft_id ? "on" : ""}" data-draft="${d.draft_id}">
            <td>#${d.draft_id}</td><td><div class="itk-name">${d.source_name}</div><div class="small muted">${pill(d.status === "APPLIED" ? "approved" : d.status)} ${fmtTs(d.created_at)} · ${d.items} item${d.items === 1 ? "" : "s"}${d.blocked_items ? `, ${d.blocked_items} blocked` : ""}</div></td></tr>`)}</tbody></table>` : html`<p class="muted">No drafts yet. Try the sample revision.</p>`}
        </div>
      </div>
      <section id="itk-draft">${itk.draft ? draftView(itk.draft) : html`<div class="empty"><h3>No draft open</h3>
        <p>Upload a policy PDF, or use the sample: a fictional Aurelia Air revision that raises the first bag fee, adds a sports equipment clause, extends travel credits from 1 March 2027 and restates one clause unchanged.</p></div>`}</section>
    </div>`);
  wireIntake();
}
function wireIntake() {
  $("#itk-doc").addEventListener("change", (e) => { itk.doc = e.target.value; });
  const run = async (blob, name) => {
    if (itk.busy) return;
    itk.busy = true;
    $("#itk-upload").disabled = true; $("#itk-sample").disabled = true;
    mount($("#itk-status"), html`<div class="loading small"><div class="spinner"></div>Reading the PDF, proposing clause versions, checking each one against the document...</div>`);
    try {
      const body = await sendPdf(`/api/policy/drafts?doc_id=${encodeURIComponent(itk.doc)}&name=${encodeURIComponent(name)}`, blob);
      itk.draft = body.draft; itk.result = null;
      itk.accept = new Set(body.draft.items_detail.filter((i) => !i.blocked && i.kind !== "UNCHANGED").map((i) => i.item_no));
      location.hash = `#/intake/${body.draft.draft_id}`;
      if (body.discarded && body.discarded.length) {
        setTimeout(() => mount($("#itk-status"), html`<div class="banner fix"><strong>${body.discarded.length} section${body.discarded.length === 1 ? " was" : "s were"} left out.</strong><span>${body.discarded.map((x) => `${x.title}: ${x.reason}`).join("; ")}</span></div>`), 50);
      }
    } catch (err) {
      mount($("#itk-status"), html`<div class="error-box">${err.message}</div>`);
    } finally {
      itk.busy = false;
      const u = $("#itk-upload"), sm = $("#itk-sample");
      if (u) u.disabled = false; if (sm) sm.disabled = false;
    }
  };
  $("#itk-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = $("#itk-file").files[0];
    if (!f) { mount($("#itk-status"), html`<div class="error-box">Choose a PDF first, or use the sample revision.</div>`); return; }
    run(f, f.name);
  });
  $("#itk-sample").addEventListener("click", async () => {
    try {
      const headers = {}; const token = savedToken(); if (token) headers.authorization = `Bearer ${token}`;
      const res = await fetch("/api/policy/intake/sample", { headers });
      if (!res.ok) throw new Error(`Could not load the sample (${res.status})`);
      itk.doc = AIRLINE;
      run(await res.blob(), "aurelia-csp-revision-2027-1.pdf");
    } catch (err) { mount($("#itk-status"), html`<div class="error-box">${err.message}</div>`); }
  });
  $$("[data-draft]").forEach((tr) => tr.addEventListener("click", () => { location.hash = `#/intake/${tr.dataset.draft}`; }));
  const d = itk.draft;
  if (!d) return;
  $("#itk-src").addEventListener("click", (e) => { e.preventDefault(); download(`/api/policy/drafts/${d.draft_id}/source`, d.source_name).catch((err) => alert(err.message)); });
  $$("[data-item]").forEach((cb) => cb.addEventListener("change", () => {
    const n = Number(cb.dataset.item);
    if (cb.checked) itk.accept.add(n); else itk.accept.delete(n);
    const btn = $("#itk-approve"); if (btn) { btn.textContent = `Approve ${itk.accept.size} selected and apply as asofedit`; btn.disabled = !itk.accept.size; }
  }));
  const decide = async (body, btn) => {
    btn.disabled = true;
    try {
      const { body: r } = await post(`/api/policy/drafts/${d.draft_id}/decision`, body);
      itk.result = r; itk.draft = r.draft;
      if (!r.preview) { tl.data = null; tl.sel = null; }
      itk.drafts = (await api("/api/policy/drafts")).body || [];
      renderIntake();
    } catch (err) {
      mount($("#itk-status"), html`<div class="error-box">${err.message}</div>`);
      btn.disabled = false;
    }
  };
  const approve = $("#itk-approve"), preview = $("#itk-preview"), reject = $("#itk-reject");
  if (approve) approve.addEventListener("click", () => decide({ approve: true, accept: [...itk.accept] }, approve));
  if (preview) preview.addEventListener("click", () => decide({ approve: true, accept: [...itk.accept], preview: true }, preview));
  if (reject) reject.addEventListener("click", () => decide({ approve: false }, reject));
}

// ---------- Backtest ----------
// A CSV of past answers, each checked through the normal check (ledger channel "backtest"); Db2 records each row's
// outcome and the money its contradicted claims put at stake, and the report below is SQL over those tables.
const bt = { runs: [], sampleId: null, report: null, busy: false, timer: null, error: null };
const BT_OUTCOME = { WRONG: "contradicted", UNCONFIRMED: "needs_review", OK: "pass", FAILED: "error", SKIPPED: "neutral" };
const BT_STATE = { RUNNING: "pending", DONE: "approved", DEADLINE: "needs_review", STOPPED: "needs_review", FAILED: "error", INTERRUPTED: "error" };
const usd = (v) => (v === null || v === undefined ? "–" : `$${Number(v).toFixed(2)}`);
async function sendCsv(path, blob) {
  const headers = { "content-type": "text/csv" };
  const token = savedToken();
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(path, { method: "POST", body: blob, headers });
  if (res.status === 401) { askToken(); throw new Error("This AsOf server needs an API token: enter it at the top of the page."); }
  let body = null;
  try { body = await res.json(); } catch { /* empty body */ }
  if (!res.ok) { const err = new Error(errorText(body, res.status)); err.rows = (body && body.errors) || []; throw err; }
  return body;
}
async function Backtest(arg) {
  clearTimeout(bt.timer);
  const list = (await api("/api/backtests")).body;
  bt.runs = list.runs; bt.sampleId = list.sample_run_id;
  const id = Number(arg) || bt.sampleId || (bt.runs[0] && bt.runs[0].run_id) || null;
  bt.report = id ? (await api(`/api/backtests/${id}`)).body : null;
  renderBacktest();
  if (bt.report && bt.report.run.state === "RUNNING") {
    bt.timer = setTimeout(() => { if (location.hash.startsWith("#/backtest")) Backtest(String(id)).catch(() => {}); }, 2500);
  }
}
function btRunRow(r) {
  const on = bt.report && bt.report.run.run_id === r.run_id;
  return html`<tr class="click ${on ? "on" : ""}" data-run="${r.run_id}"><td>#${r.run_id}</td>
    <td><div class="itk-name">${r.source_name}</div><div class="small muted">${pill(r.state, BT_STATE[r.state])} ${fmtTs(r.created_at)} · ${r.rows} rows${r.state === "RUNNING" ? `, ${r.items} checked` : `, ${r.wrong} wrong`}</div></td></tr>`;
}
function btClaim(c) {
  return html`<li><span class="mono">${c.clause_id} ${c.version}</span> <span class="muted small">${period(c.from, c.to)}</span>
    <div>${c.claim}</div>${c.money === "COMPUTED" ? html`<div class="small">said ${usd(c.stated_usd)}, the version in force set ${usd(c.policy_usd)} (<code>${c.rule_key}</code>): ${c.favours === "CUSTOMER" ? "in the customer's favour" : "against the customer"}</div>` : html`<div class="small muted">no money difference: ${c.note}</div>`}</li>`;
}
function btReport(rep) {
  const r = rep.run, m = rep.money;
  const running = r.state === "RUNNING";
  return html`
    <div class="card">
      <div class="card-head"><h2>Run ${r.run_id}: ${r.source_name}</h2>${pill(r.state, BT_STATE[r.state])}</div>
      <dl class="kv">
        <dt>Rows</dt><dd>${r.rows}${r.sample ? " · the built-in fictional sample" : ""}${r.doc_id === "auto" ? " · rows without a doc_id routed by Db2's vote" : ` · rows without a doc_id checked against ${DOC_NAME[r.doc_id] || r.doc_id}`}</dd>
        <dt>Checked by</dt><dd>${r.model}</dd>
        <dt>Started</dt><dd>${fmtTs(r.created_at)}${r.requested_by ? ` by ${r.requested_by}` : ""}${r.finished_at ? ` · finished ${fmtTs(r.finished_at)}` : ""}</dd>
        <dt>File SHA-256</dt><dd class="hash">${r.sha256}</dd>
        ${r.note ? html`<dt>Note</dt><dd>${r.note}</dd>` : ""}
      </dl>
    </div>
    ${running ? html`<div class="banner fix"><strong>Running: ${r.items} of ${r.rows} rows checked.</strong><span>Each row goes through the full check and into the ledger; this page refreshes until the run ends. No row starts after ${fmtTs(r.deadline_at)}.</span></div>` : ""}
    ${r.state === "INTERRUPTED" ? html`<div class="banner"><strong>Interrupted.</strong><span>The process running it stopped after ${r.items} of ${r.rows} rows; the rest were never checked.</span></div>` : ""}
    ${r.unaccounted > 0 && !running ? html`<div class="banner"><strong>${r.unaccounted} row${r.unaccounted === 1 ? " has" : "s have"} no outcome.</strong><span>The run stopped before it could record them.</span></div>` : ""}
    <div class="bt-stats">
      <div class="stat bad"><div class="n">${r.wrong}</div><div class="l">wrong for their date</div></div>
      <div class="stat warn"><div class="n">${r.unconfirmed}</div><div class="l">not confirmed by the policy</div></div>
      <div class="stat good"><div class="n">${r.ok}</div><div class="l">right for their date</div></div>
      <div class="stat"><div class="n">${r.failed}</div><div class="l">check failed closed</div></div>
      <div class="stat"><div class="n">${r.skipped}</div><div class="l">not checked</div></div>
    </div>
    <div class="card"><div class="card-head"><h2>Wrong answers by clause version</h2><span class="sub">V_BACKTEST_CONTRADICTIONS</span></div>
        ${rep.by_clause.length ? html`<div class="scroll-x"><table><thead><tr><th>Clause version in force</th><th class="num">Answers</th><th class="num">Claims</th><th class="num">Priced</th></tr></thead><tbody>
          ${rep.by_clause.map((c) => html`<tr><td>${clauseRef(c.clause_id, c.version, c.from, c.to)}</td><td class="num">${c.wrong_answers}</td><td class="num">${c.contradicted_claims}</td><td class="num">${usd(c.abs_usd)}</td></tr>`)}</tbody></table></div>`
          : html`<p class="muted">${running ? "Nothing wrong yet." : "No answer contradicted the policy in force on its date."}</p>`}</div>
    <div class="card"><div class="card-head"><h2>Money at stake</h2><span class="sub">BACKTEST_COST</span></div>
        <dl class="kv">
          <dt>Priced</dt><dd><b>${usd(m.total_abs_usd)}</b> over ${m.computed_claims} of ${rep.contradicted_claims} contradicted claim${rep.contradicted_claims === 1 ? "" : "s"}</dd>
          <dt>Customer's favour</dt><dd>${usd(m.customer_favour_usd)} (${m.customer_favour_claims}): a lower fee or a larger payment than the policy, what the company could be held to</dd>
          <dt>Against them</dt><dd>${usd(m.company_favour_usd)} (${m.company_favour_claims}): told to pay more or expect less than the policy</dd>
        </dl>
        ${rep.not_computable.length ? html`<div class="sep"></div><h3>Not priced</h3><ul class="small">${rep.not_computable.map((x) => html`<li>${x.claims} claim${x.claims === 1 ? "" : "s"}: ${x.reason}</li>`)}</ul>` : ""}
        <p class="small muted">${rep.cost_method}</p></div>
    <div class="card"><div class="card-head"><h2>Costliest examples</h2><span class="sub">largest priced difference first; question and draft as the ledger keeps them, redacted</span></div>
      ${rep.costliest.length ? rep.costliest.map((x) => html`<div class="bt-example">
        <div class="bt-example-head"><b>Row ${x.row}</b> · ${fmtDate(x.customer_date)} · ${x.channel} · <a href="#/ledger/${x.ledger_id}">ledger #${x.ledger_id}</a><span class="grow"></span><b>${usd(x.abs_usd)}</b></div>
        <div class="small muted">${x.question}</div>
        <p class="bt-draft"><s>${x.draft}</s></p>
        <ul class="bt-claims">${x.contradicted.map(btClaim)}</ul>
        ${x.decision === "CORRECTED" ? html`<div class="small"><span class="eyebrow">What the policy in force supports (rewritten from the clauses, re-checked)</span><div>${x.final_answer}</div></div>` : ""}
      </div>`) : html`<p class="muted">No contradicted claim had a dollar amount to compare.</p>`}</div>
    <div class="card"><div class="card-head"><h2>Every row</h2><span class="sub">BACKTEST_ITEM: the outcome Db2 derived from each row's ledger decision</span></div>
      <div class="scroll-x"><table><thead><tr><th>Row</th><th>Customer date</th><th>Channel</th><th>Outcome</th><th>Reason</th><th>Question</th><th>Ledger</th></tr></thead><tbody>
      ${rep.items.map((i) => html`<tr><td class="num">${i.row}</td><td>${fmtDate(i.customer_date)}</td><td>${i.channel}</td><td>${pill(i.outcome, BT_OUTCOME[i.outcome])}</td>
        <td class="small muted">${sentence(i.reason)}${i.contradicted.length ? html`<div>${i.contradicted.map((c) => `${c.clause_id} ${c.version}`).filter((v, k, a) => a.indexOf(v) === k).join(", ")}</div>` : ""}${i.detail && !i.ledger_id ? html`<div class="trunc" title="${i.detail}">${i.detail}</div>` : ""}</td>
        <td class="trunc" title="${i.question || ""}">${i.question || ""}</td><td>${i.ledger_id ? html`<a href="#/ledger/${i.ledger_id}">#${i.ledger_id}</a>` : "–"}</td></tr>`)}
      </tbody></table></div></div>`;
}
function renderBacktest() {
  const demo = health.demo;
  mount(view, html`
    <div class="page-head"><div><h1>Backtest</h1>
      <p>Upload past conversations as a CSV. Every row goes through the full check for its customer's date and is recorded in the ledger on channel <code>backtest</code>, kept out of the live numbers. Db2 derives each row's outcome from its ledger decision and reads the money at stake out of the cited clause version's <code>RULE_JSON</code>.</p></div></div>
    <div class="grid-2 bt-layout">
      <div class="stack">
        <form class="card" id="bt-form" autocomplete="off">
          <div class="field"><label for="bt-file">CSV file</label><input id="bt-file" type="file" accept=".csv,text/csv" ${demo ? raw("disabled") : ""}>
            <div class="hint">UTF-8 with a header row: <code>question,draft,customer_date,channel</code>, optionally <code>doc_id</code>. Dates as YYYY-MM-DD; channel chat, email, faq or api; at most 500 rows and 2 MB.${health.replay ? " Replay mode has recorded model outputs for the sample's rows only; other rows fail closed." : ""}</div></div>
          <div class="field"><label for="bt-doc">Policy for rows without a doc_id</label>
            <select id="bt-doc" ${demo ? raw("disabled") : ""}><option value="auto">Route each row (Db2's vote)</option>${Object.entries(DOC_NAME).map(([k, v]) => html`<option value="${k}">${v} (${k})</option>`)}</select></div>
          <div class="field row"><button class="btn grow" id="bt-upload" type="submit" ${demo || bt.busy ? raw("disabled") : ""}>Check file</button>
            <button class="btn ghost grow" id="bt-sample" type="button" ${demo || bt.busy ? raw("disabled") : ""} title="20 fictional past answers over both policies">Run the sample</button></div>
          <div class="small"><a href="#" id="bt-sample-dl">Download the sample CSV</a></div>
          ${demo ? html`<p class="small muted">Disabled in the public demo: uploads and runs. The report shown is a run of the built-in sample made when the demo was seeded; run AsOf locally with ./quickstart.sh to check your own file.</p>` : ""}
          <div id="bt-status" aria-live="polite">${bt.error ? html`<div class="error-box">${bt.error.message}${bt.error.rows && bt.error.rows.length ? html`<ul class="small">${bt.error.rows.slice(0, 10).map((e) => html`<li>${e.row ? `Row ${e.row}${e.line ? ` (line ${e.line})` : ""}: ` : ""}${e.message}</li>`)}</ul>` : ""}</div>` : ""}</div>
        </form>
        <div class="card"><div class="card-head"><h2>Runs</h2><span class="sub">BACKTEST_RUN</span></div>
          ${bt.runs.length ? html`<table><tbody>${bt.runs.map(btRunRow)}</tbody></table>` : html`<p class="muted">No backtests yet. Try the sample.</p>`}</div>
      </div>
      <section id="bt-report">${bt.report ? btReport(bt.report) : html`<div class="empty"><h3>No run open</h3>
        <p>Run the sample: 20 fictional past answers from Aurelia Air and Fernhollow Bank, with customer dates on both sides of policy changes.</p></div>`}</section>
    </div>`);
  wireBacktest();
}
function wireBacktest() {
  const start = async (blob, name) => {
    if (bt.busy) return;
    bt.busy = true; bt.error = null;
    $("#bt-upload").disabled = true; $("#bt-sample").disabled = true;
    mount($("#bt-status"), html`<div class="loading small"><div class="spinner"></div>Validating the file and starting the run...</div>`);
    try {
      const doc = $("#bt-doc").value;
      const body = await sendCsv(`/api/backtests?doc_id=${encodeURIComponent(doc)}&name=${encodeURIComponent(name)}`, blob);
      bt.busy = false;
      location.hash = `#/backtest/${body.run_id}`;
    } catch (err) {
      bt.busy = false; bt.error = err;
      renderBacktest();
    }
  };
  $("#bt-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = $("#bt-file").files[0];
    if (!f) { mount($("#bt-status"), html`<div class="error-box">Choose a CSV first, or run the sample.</div>`); return; }
    start(f, f.name);
  });
  $("#bt-sample").addEventListener("click", async () => {
    try {
      const headers = {}; const token = savedToken(); if (token) headers.authorization = `Bearer ${token}`;
      const res = await fetch("/api/backtests/sample", { headers });
      if (!res.ok) throw new Error(`Could not load the sample (${res.status})`);
      start(await res.blob(), "fictional-backtest-sample.csv");
    } catch (err) { mount($("#bt-status"), html`<div class="error-box">${err.message}</div>`); }
  });
  $("#bt-sample-dl").addEventListener("click", (e) => { e.preventDefault(); download("/api/backtests/sample", "fictional-backtest-sample.csv").catch((err) => alert(err.message)); });
  $$("[data-run]").forEach((tr) => tr.addEventListener("click", () => { location.hash = `#/backtest/${tr.dataset.run}`; }));
}

// ---------- Analytics ----------
async function Analytics() {
  mount(view, html`<div class="loading"><div class="spinner"></div>Querying Db2 views...</div>`);
  const a = (await api("/api/analytics")).body;
  const total = a.decisions.reduce((s, d) => s + d.count, 0);
  const maxArea = Math.max(1, ...a.areas.map((x) => x.claims));
  const pct = (v, t) => (t ? (100 * v) / t : 0).toFixed(2);
  mount(view, html`
    <div class="page-head"><div><h1>Analytics</h1><p>Straight from Db2: the views <code>V_DECISION_STATS</code>, <code>V_CLAIM_OUTCOMES_BY_AREA</code> and <code>V_RULE_OVERRIDES</code>, and a count over <code>CLAIM_CITATION</code> for the rule check.</p></div></div>
    ${total ? "" : html`<div class="empty"><h3>No decisions yet</h3><p>Check a few answers in the <a href="#/playground">Playground</a>.</p></div>`}
    <div class="cols-2">
      <div class="card"><div class="card-head"><h2>Decisions</h2><span class="sub">${total} recorded</span></div><div class="bars">
        ${["PASS", "CORRECTED", "ESCALATED", "REVIEWED"].map((k) => { const d = a.decisions.find((x) => x.decision === k) || { count: 0, avg_latency_ms: 0 };
          return html`<div class="bar-row"><span>${pill(k)}</span><div class="bar"><i class="${lower(k)}" data-width="${pct(d.count, total)}"></i></div><span class="num">${d.count}</span></div>`; })}
      </div>${a.backtest_decisions ? html`<p class="small muted">${a.backtest_decisions} backtest decision${a.backtest_decisions === 1 ? " is" : "s are"} left out of every number on this page: they are checks of past answers, not answers AsOf released. See <a href="#/backtest">Backtest</a>.</p>` : ""}${a.replayed_decisions ? html`<p class="small muted">${a.replayed_decisions} of these ${total} decisions were made in replay mode, from recorded model outputs, so their latency leaves out model time.</p>` : ""}<div class="sep"></div><table><thead><tr><th>Reason</th><th class="num">Decisions</th></tr></thead><tbody>
        ${a.reasons.map((r) => html`<tr><td>${sentence(r.reason)}</td><td class="num">${r.count}</td></tr>`)}</tbody></table></div>
      <div class="card"><div class="card-head"><h2>Claims in drafts, by area</h2></div>
        <div class="legend"><span><i class="supported"></i>Supported</span><span><i class="contradicted"></i>Contradicted</span><span><i class="not_covered"></i>Not covered</span></div>
        <div class="bars">${a.areas.map((x) => html`<div class="bar-row"><span>${AREA_LABEL[x.area] || x.area}</span>
          <div class="bar"><i class="supported" data-width="${pct(x.supported, maxArea)}"></i><i class="contradicted" data-width="${pct(x.contradicted, maxArea)}"></i><i class="not_covered" data-width="${pct(x.not_covered, maxArea)}"></i></div>
          <span class="num">${x.claims}</span></div>`)}</div></div>
    </div>
    <div class="card"><div class="card-head"><h2>Deterministic rule check</h2><span class="sub">numbers, limits, delay tiers and permissions in each claim, against the clause's RULE_JSON, whatever the judge said</span></div>
      ${(() => { const rc = a.rule_checks || { match: 0, mismatch: 0, mismatch_judge_agreed: 0, not_applicable: 0 };
        return html`<div class="bars"><div class="bar-row"><span>Mismatch</span><div class="bar"><i class="contradicted" data-width="${pct(rc.mismatch, rc.match + rc.mismatch + rc.not_applicable)}"></i></div><span class="num">${rc.mismatch}</span></div>
        <div class="bar-row"><span>Match</span><div class="bar"><i class="supported" data-width="${pct(rc.match, rc.match + rc.mismatch + rc.not_applicable)}"></i></div><span class="num">${rc.match}</span></div>
        <div class="bar-row"><span>Nothing to compare</span><div class="bar"><i class="not_covered" data-width="${pct(rc.not_applicable, rc.match + rc.mismatch + rc.not_applicable)}"></i></div><span class="num">${rc.not_applicable}</span></div></div>
        <p class="small muted bars-note">Claims in drafts. The judge also said contradicted in ${rc.mismatch_judge_agreed} of the ${rc.mismatch} mismatches; where it said supported, the rule check overruled it (below).</p>`; })()}
      <div class="sep"></div><h3>Where the rule check overruled the judge</h3>
      ${a.rule_overrides.length ? html`<table><thead><tr><th>Entry</th><th>Customer date</th><th>Claim</th><th>Clause</th></tr></thead><tbody>
        ${a.rule_overrides.map((r) => html`<tr><td><a href="#/ledger/${r.ledger_id}">#${r.ledger_id}</a></td><td>${fmtDate(r.as_of_date)}</td><td>${r.claim}</td><td><code>${r.clause_id}</code> ${r.version}</td></tr>`)}
      </tbody></table>` : html`<p class="muted">None yet: in every mismatch so far, the judge had also found the claim contradicted.</p>`}</div>`);
}

async function loadScenarios() {
  try {
    const res = await fetch("/ui/scenarios.json", { cache: "no-store" });
    if (res.ok) ({ playground: SCENARIOS, presets: PRESETS, ask_examples: ASK_EXAMPLES, reviews: REVIEW_REPLIES = [] } = await res.json());
  } catch { /* every screen still works; only the scenario chips are missing */ }
  ask.question = ASK_EXAMPLES[0] || "";
}

Promise.all([status(), loadScenarios()]).then(route);  // the first page already knows Db2's clock zone
