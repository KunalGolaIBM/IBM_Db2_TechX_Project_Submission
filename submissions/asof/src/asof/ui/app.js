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
  form.innerHTML = '<label for="api-token">This AsOf server needs its API token</label>'
    + '<input id="api-token" type="password" autocomplete="off" required><button class="btn sm" type="submit">Use token</button>';
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    try { sessionStorage.setItem(TOKEN_KEY, $("#api-token").value.trim()); } catch { /* private mode: ask again next time */ }
    form.remove();
    status();
    route();
  });
  document.body.prepend(form);
}
async function api(path, options = {}) {
  const headers = { "content-type": "application/json" };
  const token = savedToken();
  if (token) headers.authorization = `Bearer ${token}`;
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) { askToken(); throw new Error("This AsOf server needs an API token: enter it at the top of the page."); }
  let body = null;
  try { body = await res.json(); } catch { /* empty body */ }
  if (!res.ok && res.status !== 503) throw new Error(errorText(body, res.status));
  return { status: res.status, body };
}
function errorText(body, status) {
  if (!body) return `Request failed (${status})`;
  if (body.error) return body.error;
  if (typeof body.detail === "string") return body.detail;
  if (Array.isArray(body.detail)) return body.detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ");
  return `Request failed (${status})`;
}
const post = (path, data) => api(path, { method: "POST", body: JSON.stringify(data) });

// ---------- formatting ----------
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const OPEN = "9999-12-31";
function fmtDate(d) {
  if (!d) return "";
  if (String(d).startsWith("9999")) return "open-ended";
  const [y, m, day] = String(d).slice(0, 10).split("-").map(Number);
  return `${day} ${MONTHS[m - 1]} ${y}`;
}
function fmtTs(t) {
  if (!t) return "";
  return String(t).replace("T", " ").slice(0, 19);
}
const period = (from, to) => `${fmtDate(from)} → ${String(to).startsWith("9999") ? "open-ended" : fmtDate(to)}`;
const lower = (s) => String(s || "").toLowerCase();
const today = () => new Date().toISOString().slice(0, 10);
const shortHash = (h) => (h || "").slice(0, 12);
const pill = (value, cls) => html`<span class="pill ${cls || lower(value)}">${String(value).replaceAll("_", " ")}</span>`;
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
};

// ---------- shell ----------
const view = $("#view");
const routes = { playground: Playground, timeline: Timeline, ledger: Ledger, ask: Ask, impact: Impact, analytics: Analytics };
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

async function status() {
  try {
    const { body } = await api("/healthz");
    mount($("#status"), html`
      <span class="tag ${body.db2 === "ok" ? "" : "warn"}" title="IBM Db2 connection as the least-privilege user">Db2 ${body.db2 === "ok" ? "connected" : "unavailable"}</span>
      <span class="tag ${body.llm_ready ? "brand" : "warn"}" title="LLM provider and model">${body.llm_ready ? body.llm : "no model configured"}</span>`);
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
const SCENARIOS = [
  { label: "Moffatt: March booking", mode: "ask", question: QUESTION_MOFFATT, as_of: "2026-03-10" },
  { label: "Same question: June booking", mode: "ask", question: QUESTION_MOFFATT, as_of: "2026-06-02" },
  { label: "Stale bag fee (July)", mode: "ask", question: "How much is the first checked bag?", as_of: "2026-07-15" },
  { label: "Ticket transfer", mode: "ask", question: "Can I transfer my ticket to a friend?", as_of: "2026-04-01" },
  { label: "Pet fee, December trip", mode: "ask", question: "Can my cat fly in the cabin with me, and what does it cost?", as_of: "2026-12-15" },
  { label: "Paste a draft", mode: "draft", question: "Can my dog fly in the cabin with me?",
    draft: "Yes, dogs up to 12 kg including the carrier can fly in the cabin for $100 each way.", as_of: "2026-05-05" },
  { label: "Bank: \"refunded automatically\"", mode: "draft", doc: BANK, question: "I was charged an overdraft fee yesterday. Will you refund it?",
    draft: "Yes, don't worry: overdraft fees are refunded automatically within a few days.", as_of: "2026-03-15" },
  { label: "Bank: overdraft fee in August", mode: "draft", doc: BANK, question: "How much is the overdraft fee?",
    draft: "The overdraft fee is $35 for each item we pay.", as_of: "2026-08-03" },
];
const play = { mode: "ask", doc: AIRLINE, question: QUESTION_MOFFATT, draft: "", as_of: "2026-03-10", scenario: 0, result: null };

const HEADLINE = {
  PASS: "Released as written",
  CORRECTED: "Corrected before release",
  ESCALATED: "Held for a specialist",
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
    case "ERROR_FAIL_CLOSED": return "A check could not complete, so the answer was held (fail closed).";
    case "LEDGER_UNAVAILABLE": return "The decision could not be recorded in the ledger, so nothing was released.";
    default: return r.reason_code;
  }
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
          <select id="doc">${[AIRLINE, BANK].map((d) => html`<option value="${d}" ${d === s.doc ? raw("selected") : ""}>${DOC_NAME[d]} (${d})</option>`)}</select>
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
      ? await post("/api/assistant/ask", { question: play.question, as_of_date: play.as_of })
      : await post("/api/gate", { question: play.question, draft_answer: play.draft, as_of_date: play.as_of, doc_id: play.doc });
    body._as_of = play.as_of;
    body._draft = play.mode === "ask" ? body.assistant?.draft : play.draft;
    play.result = body;
    mount(box, resultView(body, play.as_of));
  } catch (err) {
    mount(box, html`<div class="error-box">${err.message}</div>`);
  } finally {
    btn.disabled = false;
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
function resultView(r, asOf) {
  const first = r.claims.filter((c) => c.pass_no === 1);
  const second = r.claims.filter((c) => c.pass_no === 2);
  const draft = r._draft ?? r.assistant?.draft;
  return html`
    <div class="decision ${lower(r.decision)}">
      <div class="icon">${ICONS[r.decision]}</div>
      <div><div class="row">${pill(r.decision)}<h2>${HEADLINE[r.decision]}</h2></div><p>${explain(r, asOf)}</p></div>
      <div class="meta">${(r.latency_ms / 1000).toFixed(1)} s · ${r.model}<br>
        ${r.ledger_id ? html`<a href="#/ledger/${r.ledger_id}">Ledger entry #${r.ledger_id} →</a>` : html`<span>Not recorded</span>`}</div>
    </div>
    <div class="cols-2">
      <div class="card"><div class="eyebrow">${r.assistant ? "Demo assistant's draft" : "Draft"}</div><div class="sep"></div>
        <div class="answer ${r.decision === "PASS" ? "" : "struck"}">${draft}</div></div>
      <div class="card"><div class="eyebrow">What the customer receives</div><div class="sep"></div>
        <div class="answer final">${r.final_answer}</div></div>
    </div>
    <div class="card">
      <div class="card-head"><h2>Claims in the draft</h2><span class="sub">checked against the clauses in force on ${fmtDate(asOf)}</span></div>
      ${first.length ? html`<div class="claims">${first.map(claimCard)}</div>` : html`<p class="muted">No policy claims found.</p>`}
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
  const end = Math.max(toMs("2027-03-01"), latest + 120 * DAY);
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
          <div class="tl-axis"><div class="eyebrow">Clause</div><div class="tl-scale">${ticks.map((t) => html`<span class="tl-tick" data-left="${t.left}">${t.label}</span>`)}<i class="tl-marker" data-left="${markerLeft}" data-label="as of ${fmtDate(tl.asOf)}"></i></div></div>
          ${groups.map((g) => html`
            <div class="tl-area">${AREA_LABEL[g.area] || g.area}</div>
            ${g.items.map((c) => html`
              <div class="tl-row">
                <div class="tl-name"><code>${c.clause_id}</code><span title="${c.title}">${c.title}</span></div>
                <div class="tl-track">
                  ${ticks.map((t) => html`<i class="tl-grid" data-left="${t.left}"></i>`)}
                  <i class="tl-marker" data-left="${markerLeft}"></i>
                  ${c.versions.map((v) => {
                    const l = pos(toMs(v.from)); const w = Math.max(0.6, pos(toMs(v.to)) - l);
                    const sel = tl.sel.id === c.clause_id && tl.sel.version === v.version;
                    return html`<button type="button" class="tl-seg ${v.version} ${sel ? "selected" : ""}" data-left="${l.toFixed(3)}" data-width="${w.toFixed(3)}"
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
    <div><div class="eyebrow">System-time history in Db2</div><div class="hist" id="tl-hist"><div class="muted small">Loading...</div></div></div>`);
  box.classList.add("stack");
  // Remember which panel this request is for: a slower response for a clause selected
  // earlier must not overwrite the panel of the clause selected now.
  const target = $("#tl-hist");
  try {
    const hist = (await api(`/api/policy/clauses/${encodeURIComponent(c.clause_id)}/history`)).body;
    if (!target.isConnected) return;
    mount(target, hist.map((h) => html`
      <div class="hist-item ${h.current ? "current" : ""}">
        <div class="row"><strong>${h.version}</strong><span class="muted">${period(h.from, h.to)}</span>${h.current ? pill("current", "ok") : pill("superseded", "neutral")}</div>
        <div class="muted">held ${fmtTs(h.recorded_at)} → ${h.current ? "now" : fmtTs(h.superseded_at)} · by <code>${h.changed_by}</code></div>
      </div>`));
  } catch (err) { if (target.isConnected) mount(target, html`<div class="error-box">${err.message}</div>`); }
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
    <div class="card"><div class="card-head"><div class="chips" id="dec-filter">
      ${[null, "PASS", "CORRECTED", "ESCALATED"].map((d) => html`<button type="button" class="chip ${led.decision === d ? "on" : ""}" data-dec="${d || ""}">${d ? d.toLowerCase() : "all decisions"}</button>`)}
    </div></div><div id="ledger-table"><div class="loading"><div class="spinner"></div>Loading ledger...</div></div></div>`);
  $("#verify").addEventListener("click", verifyChain);
  $("#dec-filter").addEventListener("click", (e) => { const b = e.target.closest("[data-dec]"); if (b) { led.decision = b.dataset.dec || null; Ledger(); } });
  verifyChain();
  const q = led.decision ? `?limit=100&decision=${led.decision}` : "?limit=100";
  const rows = (await api(`/api/ledger${q}`)).body;
  mount($("#ledger-table"), rows.length ? html`
    <table><thead><tr><th>#</th><th>Recorded</th><th>Customer date</th><th>Decision</th><th>Reason</th><th>Question</th><th>Row hash</th></tr></thead>
    <tbody>${rows.map((r) => html`<tr class="click" data-id="${r.ledger_id}">
      <td class="num"><a href="#/ledger/${r.ledger_id}">${r.ledger_id}</a></td><td>${fmtTs(r.created_at)}</td><td>${fmtDate(r.as_of_date)}</td>
      <td>${pill(r.decision)}</td><td class="small muted">${r.reason_code.replaceAll("_", " ").toLowerCase()}</td>
      <td class="trunc" title="${r.question_redacted}">${r.question_redacted}</td><td class="hash">${shortHash(r.row_hash)}</td></tr>`)}</tbody></table>`
    : html`<div class="empty"><h3>No decisions recorded yet</h3><p>Check an answer in the <a href="#/playground">Playground</a>.</p></div>`);
  $("#ledger-table").addEventListener("click", (e) => { const tr = e.target.closest("tr[data-id]"); if (tr) location.hash = `#/ledger/${tr.dataset.id}`; });
}
async function verifyChain() {
  const box = $("#chain");
  if (!box) return;
  mount(box, html`<div class="banner ok"><div class="spinner"></div>Running VERIFY_CHAIN in Db2...</div>`);
  try {
    const s = (await api("/api/chain/verify")).body;
    mount(box, s.status === "OK"
      ? html`<div class="banner ok"><strong>Chain intact.</strong><span>VERIFY_CHAIN recomputed ${s.rows_checked} row hash${s.rows_checked === 1 ? "" : "es"}: ${s.detail}.</span></div>`
      : html`<div class="banner bad"><strong>Chain broken at entry #${s.first_bad_ledger_id}.</strong><span>${s.detail}</span></div>`);
  } catch (err) { mount(box, html`<div class="banner bad">${err.message}</div>`); }
}
function sqlBlock(createdAt, asOf, clauseId) {
  return raw(`<pre class="sql"><span class="kw">SELECT</span> VERSION_LABEL, CLAUSE_TEXT
<span class="kw">FROM</span> ASOF.POLICY_CLAUSE
  <span class="kw">FOR SYSTEM_TIME AS OF</span> '${esc(fmtTs(createdAt))}'   <span class="cm">-- what Db2 held when the answer was given</span>
  <span class="kw">FOR BUSINESS_TIME AS OF</span> '${esc(String(asOf))}'           <span class="cm">-- the customer's date</span>
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
      <div class="row">${pill(e.decision)}<button class="btn ghost sm" id="verify">Verify hash chain</button></div>
    </div>
    <div id="chain"></div>
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
        <div class="sep"></div><dl class="kv"><dt>Previous hash</dt><dd class="hash">${e.prev_hash}</dd><dt>Row hash</dt><dd class="hash">${e.row_hash}</dd><dt>Reason</dt><dd>${e.reason_code}</dd></dl></div>
    </div>
    <div class="card"><div class="card-head"><h2>Claim citations</h2><span class="sub">CLAIM_CITATION rows, shredded from the hashed verdict JSON by JSON_TABLE</span></div>
      <table><thead><tr><th>Check</th><th>#</th><th>Claim</th><th>Verdict</th><th>Judge</th><th>Rule</th><th>Clause</th></tr></thead>
      <tbody>${e.citations.map((c) => html`<tr><td>${c.pass_no === 1 ? "draft" : "rewrite"}</td><td>${c.claim_no}</td><td>${c.claim_text}</td>
        <td>${pill(c.verdict)}</td><td class="small">${(c.llm_verdict || "").replaceAll("_", " ").toLowerCase()}</td><td class="small">${c.rule_check.replaceAll("_", " ").toLowerCase()}</td>
        <td>${c.clause_id ? html`<code>${c.clause_id}</code> ${c.clause_version}` : html`<span class="muted">none</span>`}</td></tr>`)}</tbody></table></div>`);
  $("#verify").addEventListener("click", verifyChain);
}

// ---------- Ask the ledger ----------
const ASK_EXAMPLES = [
  "How many decisions of each kind were made, per channel?",
  "Which clause versions had the most contradicted claims?",
  "Where did the rule check overrule the model judge?",
  "What share of checks for March 2026 travel dates were escalated?",
  "Show the escalated decisions with the customer's question and our reply.",
];
const ask = { question: ASK_EXAMPLES[0], result: null, busy: false };
async function Ask() {
  mount(view, html`
    <div class="page-head"><div><h1>Ask the ledger</h1>
      <p>Plain-English questions for auditors, answered by a LangChain SQL chain over SQLAlchemy (<code>ibm_db_sa</code>). It runs as the read-only Db2 user <code>asofread</code>, which can only SELECT six audit views. SQLGlot checks every generated query before it runs, and Db2's column masks hide the customer's question and our reply from this user.</p></div></div>
    <div class="grid-2">
      <form class="card" id="ask-form" autocomplete="off">
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
  });
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    ask.question = $("#aq").value.trim();
    ask.busy = true;
    mount($("#ask-result"), html`<div class="loading"><div class="spinner"></div>Writing SQL, checking it, running it in Db2 as asofread...</div>`);
    $("#ask-run").disabled = true;
    try {
      ask.result = (await post("/api/ledger/ask", { question: ask.question })).body;
    } catch (err) {
      ask.result = { status: "ERROR", reason: err.message, attempts: [], rows: [], columns: [] };
    }
    ask.busy = false;
    Ask();
  });
}
function askView(r) {
  const head = {
    ANSWERED: html`<div class="banner ok"><strong>Answered.</strong><span>${r.rows.length} row${r.rows.length === 1 ? "" : "s"}${r.truncated ? " (capped)" : ""} in ${(r.latency_ms / 1000).toFixed(1)} s, as ${r.runs_as}.</span></div>`,
    REFUSED: html`<div class="banner bad"><strong>Refused.</strong><span>No query ran. ${r.reason}</span></div>`,
    FAILED: html`<div class="banner bad"><strong>Db2 rejected the query.</strong><span>${r.reason}</span></div>`,
    ERROR: html`<div class="banner bad"><strong>Not available.</strong><span>${r.reason}</span></div>`,
  }[r.status];
  const attempts = (r.attempts || []).filter((a) => a.refused || a.db2_error);
  return html`${head}
    ${r.answer ? html`<div class="card"><div class="eyebrow">Answer</div><div class="sep"></div><div class="answer final">${r.answer}</div>
      ${r.explanation ? html`<div class="sep"></div><p class="small muted">${r.explanation}</p>` : ""}</div>` : ""}
    ${r.sql ? html`<div class="card"><div class="card-head"><h2>SQL that ran</h2><span class="sub">regenerated by SQLGlot from the checked parse tree</span></div><pre class="sql">${r.sql}</pre></div>` : ""}
    ${r.columns && r.columns.length ? html`<div class="card"><div class="card-head"><h2>Rows</h2><span class="sub">straight from Db2; [masked] is Db2's column mask</span></div>
      <div class="scroll-x"><table><thead><tr>${r.columns.map((c) => html`<th>${c}</th>`)}</tr></thead>
      <tbody>${r.rows.map((row) => html`<tr>${row.map((v) => html`<td class="${v === "[masked]" ? "muted" : ""}">${v === null ? "null" : v}</td>`)}</tr>`)}</tbody></table></div></div>` : ""}
    ${attempts.length ? html`<div class="card"><div class="card-head"><h2>Attempts that did not run</h2><span class="sub">the model gets one retry with the reason</span></div>
      ${attempts.map((a) => html`<pre class="sql">${a.proposed_sql}</pre><p class="small">${a.refused ? html`<strong>Refused by the SQLGlot check:</strong> ${a.refused}` : html`<strong>Db2:</strong> ${a.db2_error}`}</p>`)}</div>` : ""}`;
}

// ---------- Change impact ----------
const PRESETS = [
  { label: "Pet fee to $125 from 1 Dec 2026", clause: "PET-001", from: "2026-12-01",
    text: "Small cats and dogs may travel in the cabin if the pet and its carrier together weigh no more than 8 kg. The pet fee is $125 each way.",
    rule: { max_pet_weight_kg: 8, pet_fee_usd: 125 }, note: "Pet fee rises to $125 from 1 December 2026." },
  { label: "Bereavement window to 60 days from 1 Jan 2027", clause: "BRV-002", from: "2027-01-01",
    text: "Bereavement fares may be requested before travel or retroactively. A retroactive request must be submitted within 60 days of the date the original ticket was issued, together with the documentation listed in clause BRV-003. Approved retroactive requests are refunded the fare difference to the original form of payment.",
    rule: { retroactive_allowed: true, request_window_days: 60, request_before_travel_required: false }, note: "Retroactive window shortened to 60 days." },
  { label: "First bag to $45 from 1 Jan 2027", clause: "BAG-001", from: "2027-01-01",
    text: "The first checked bag costs $45 each way on Economy fares.", rule: { first_bag_fee_usd: 45 }, note: "First bag fee rises to $45." },
  { label: "Bank: overdraft fee to $20 from 1 Jan 2027", clause: "OVD-001", from: "2027-01-01",
    text: "An overdraft fee of $20 is charged for each item we pay when the account does not have enough available funds.",
    rule: { overdraft_fee_usd: 20 }, note: "Overdraft fee falls to $20 from 1 January 2027." },
];
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
      <p>Apply a policy change as the editor user <code>asofedit</code>. <code>APPLY_POLICY_CHANGE</code> runs <code>UPDATE ... FOR PORTION OF BUSINESS_TIME</code>, so Db2 splits the version and keeps the replaced row in history. <code>CHANGE_IMPACT</code> then finds every released answer and help-centre answer that relied on the clause, and tells stale from historically valid.</p></div></div>
    <div class="grid-2">
      <form class="card" id="imp-form" autocomplete="off">
        <div class="field"><label>Presets</label><div class="chips">${PRESETS.map((p, i) => html`<button type="button" class="chip" data-preset="${i}">${p.label}</button>`)}</div></div>
        <div class="sep"></div>
        <div class="field"><label for="imp-clause">Clause</label>
          <select id="imp-clause">${tl.data.map((x) => html`<option value="${x.clause_id}" ${x.clause_id === imp.clause ? raw("selected") : ""}>${x.clause_id} · ${x.title}</option>`)}</select>
          <div class="hint">${c.versions.map((v) => `${v.version}: ${period(v.from, v.to)}`).join(" · ")}</div></div>
        <div class="field row"><div class="grow"><label for="imp-from">Effective from</label><input id="imp-from" type="date" value="${f.from}" required></div>
          <div class="grow"><label for="imp-to">Until (optional)</label><input id="imp-to" type="date" value="${f.to}"></div>
          <div><label for="imp-ver">Version</label><input id="imp-ver" type="text" value="${f.version}" size="4" required></div></div>
        <div class="field"><label for="imp-text">New clause text</label><textarea id="imp-text" rows="4" required>${f.text}</textarea></div>
        <div class="field"><label for="imp-rule">Rule parameters (RULE_JSON)</label><textarea id="imp-rule" class="code" rows="3" required>${f.rule}</textarea></div>
        <div class="field"><label for="imp-note">Change note</label><input id="imp-note" type="text" value="${f.note}" maxlength="400" required></div>
        <div class="field row"><button class="btn grow" id="imp-apply" type="submit">Apply change as asofedit</button><button class="btn ghost" id="imp-show" type="button">Impact only</button></div>
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
    ${applied ? html`<div class="banner ok"><strong>Change applied.</strong><span>Db2 split ${applied.rows_changed} row${applied.rows_changed === 1 ? "" : "s"} with FOR PORTION OF BUSINESS_TIME; the replaced row moved to POLICY_CLAUSE_HIST. ${applied.published_flagged} help-centre answer${applied.published_flagged === 1 ? " was" : "s were"} flagged for review. <a href="#/timeline">See it on the timeline →</a></span></div>` : ""}
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
    <section id="imp-sugg"></section>`;
}

// Drafted corrections: the change-impact agent drafts, the check runs on each, the editor decides.
const sug = { list: [] };
async function loadSuggestions() {
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

// ---------- Analytics ----------
async function Analytics() {
  mount(view, html`<div class="loading"><div class="spinner"></div>Querying Db2 views...</div>`);
  const a = (await api("/api/analytics")).body;
  const total = a.decisions.reduce((s, d) => s + d.count, 0);
  const maxArea = Math.max(1, ...a.areas.map((x) => x.claims));
  const pct = (v, t) => (t ? (100 * v) / t : 0).toFixed(2);
  mount(view, html`
    <div class="page-head"><div><h1>Analytics</h1><p>Straight from the Db2 views <code>V_DECISION_STATS</code>, <code>V_CLAIM_OUTCOMES_BY_AREA</code> and <code>V_RULE_OVERRIDES</code>.</p></div></div>
    ${total ? "" : html`<div class="empty"><h3>No decisions yet</h3><p>Check a few answers in the <a href="#/playground">Playground</a>.</p></div>`}
    <div class="cols-2">
      <div class="card"><div class="card-head"><h2>Decisions</h2><span class="sub">${total} recorded</span></div><div class="bars">
        ${["PASS", "CORRECTED", "ESCALATED"].map((k) => { const d = a.decisions.find((x) => x.decision === k) || { count: 0, avg_latency_ms: 0 };
          return html`<div class="bar-row"><span>${pill(k)}</span><div class="bar"><i class="${lower(k)}" data-width="${pct(d.count, total)}"></i></div><span class="num">${d.count}</span></div>`; })}
      </div><div class="sep"></div><table><thead><tr><th>Reason</th><th class="num">Decisions</th></tr></thead><tbody>
        ${a.reasons.map((r) => html`<tr><td>${r.reason.replaceAll("_", " ").toLowerCase()}</td><td class="num">${r.count}</td></tr>`)}</tbody></table></div>
      <div class="card"><div class="card-head"><h2>Claims in drafts, by area</h2></div>
        <div class="legend"><span><i class="supported"></i>supported</span><span><i class="contradicted"></i>contradicted</span><span><i class="not_covered"></i>not covered</span></div>
        <div class="bars">${a.areas.map((x) => html`<div class="bar-row"><span>${AREA_LABEL[x.area] || x.area}</span>
          <div class="bar"><i class="supported" data-width="${pct(x.supported, maxArea)}"></i><i class="contradicted" data-width="${pct(x.contradicted, maxArea)}"></i><i class="not_covered" data-width="${pct(x.not_covered, maxArea)}"></i></div>
          <span class="num">${x.claims}</span></div>`)}</div></div>
    </div>
    <div class="card"><div class="card-head"><h2>Rule check overruled the judge</h2><span class="sub">the LLM said SUPPORTED; numbers or permissions in RULE_JSON said otherwise</span></div>
      ${a.rule_overrides.length ? html`<table><thead><tr><th>Entry</th><th>Customer date</th><th>Claim</th><th>Clause</th></tr></thead><tbody>
        ${a.rule_overrides.map((r) => html`<tr><td><a href="#/ledger/${r.ledger_id}">#${r.ledger_id}</a></td><td>${fmtDate(r.as_of_date)}</td><td>${r.claim}</td><td><code>${r.clause_id}</code> ${r.version}</td></tr>`)}
      </tbody></table>` : html`<p class="muted">No overrides recorded yet.</p>`}</div>`);
}

status();
route();
