const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n, c = "USD") => { try { return new Intl.NumberFormat("en", { style: "currency", currency: c, maximumFractionDigits: 0 }).format(n || 0); } catch { return `${c} ${n}`; } };
let CONFIG = {}, LANG = "en", IMAGE = null, paypalReady = null;

async function api(path, body, isForm) {
  const opts = body ? { method: "POST", body: isForm ? body : JSON.stringify(body), headers: isForm ? {} : { "Content-Type": "application/json" } } : {};
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : (data.detail ? "Please check the details you entered." : r.statusText));
  return data;
}
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("on"); setTimeout(() => t.classList.remove("on"), 2600); }

/* ---------------- routing ---------------- */
function route() {
  const v = (location.hash || "#check").slice(1);
  const name = ["check", "agent", "report", "dashboard"].includes(v) ? v : "check";
  $$(".view").forEach((x) => x.classList.toggle("active", x.id === `view-${name}`));
  $$("nav.main a[data-view]").forEach((a) => a.classList.toggle("active", a.dataset.view === name));
  if (name === "dashboard") loadDashboard();
}
window.addEventListener("hashchange", route);

/* ---------------- language ---------------- */
$$(".seg button").forEach((b) => b.addEventListener("click", () => {
  LANG = b.dataset.lang;
  $$(".seg button").forEach((x) => x.classList.toggle("on", x === b));
}));

/* ---------------- screenshot input ---------------- */
const drop = $("#drop"), fileIn = $("#file");
function setImage(file) {
  if (!file || !file.type.startsWith("image/")) return toast("That isn't an image.");
  if (file.size > 8 * 1024 * 1024) return toast("Image is larger than 8 MB.");
  IMAGE = file;
  $("#thumb-img").src = URL.createObjectURL(file);
  $("#thumb-name").textContent = ` ${file.name || "pasted image"} · ${(file.size / 1024).toFixed(0)} KB`;
  drop.classList.add("has-image");
}
function clearImage() { IMAGE = null; fileIn.value = ""; drop.classList.remove("has-image"); }
fileIn.addEventListener("change", () => fileIn.files[0] && setImage(fileIn.files[0]));
$("#remove-img").addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); clearImage(); });
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("drag"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("drag"); }));
drop.addEventListener("drop", (e) => e.dataTransfer.files[0] && setImage(e.dataTransfer.files[0]));
document.addEventListener("paste", (e) => {
  if (!$("#view-check").classList.contains("active")) return;
  const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
  if (item) { e.preventDefault(); setImage(item.getAsFile()); toast("Screenshot added"); }
});

const EXAMPLES = {
  ig: "Seller (FastDeals NG): Bro the PS5 is brand new, only 2 left and many people are interested. It's $210. Send it as friends and family to avoid fees, or transfer to my OPay 0000012345. Account name is different but don't mind. Let's continue on WhatsApp.",
  phish: "From: PayPal Security Team <paypal-support@secure-verify.example>\nYour PayPal account has been limited due to unusual activity. Verify your account at https://paypa1-verify.example/login within 24 hours or it will be closed.",
  job: "HR (Global Remote Jobs): Congratulations! You have been selected for the data entry job, earn $50 daily. Pay the $25 registration fee immediately to start your training. Chat with HR on WhatsApp 0700 000 0202.",
  safe: "Uyo Gadgets Ltd (sales@uyo-gadgets.example): Hi, your order #1043 for the Samsung A55 is confirmed. Total $320. Pay through PayPal checkout, invoice attached, delivery to Uyo in 2 days.",
};
$$("[data-ex]").forEach((b) => b.addEventListener("click", () => { clearImage(); $("#text").value = EXAMPLES[b.dataset.ex]; $("#text").focus(); }));

/* ---------------- check ---------------- */
const STEPS = ["Reading the chat…", "Checking the blocklist…", "Comparing with known scams…", "Asking the AI investigator…"];
$("#checker").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = $("#text").value.trim();
  if (!IMAGE && !text) return toast("Add a screenshot or paste the message first.");
  const btn = $("#check-btn"), load = $("#loading");
  btn.disabled = true; load.classList.add("on"); $("#result").innerHTML = "";
  let i = 0; $("#loading-text").textContent = IMAGE ? STEPS[0] : STEPS[1];
  const timer = setInterval(() => { i = Math.min(i + 1, STEPS.length - 1); $("#loading-text").textContent = STEPS[i]; }, 1100);
  try {
    let res;
    if (IMAGE) {
      const fd = new FormData(); fd.append("file", IMAGE); fd.append("language", LANG);
      res = await api("/api/screen-image", fd, true);
    } else {
      res = await api("/api/screen", { message: text, language: LANG, payment_method: guessMethod(text) });
    }
    showResult(res, $("#result"));
  } catch (err) {
    $("#result").innerHTML = `<div class="card"><p class="err"><b>Couldn't check that.</b> ${esc(err.message)}</p></div>`;
  } finally { clearInterval(timer); btn.disabled = false; load.classList.remove("on"); }
});
function guessMethod(t) {
  const s = t.toLowerCase();
  if (/friends?\s*(and|&|n)\s*family|f&f/.test(s)) return "friends_family";
  if (/gift ?card/.test(s)) return "gift_card";
  if (/\b(usdt|btc|bitcoin|crypto)\b/.test(s)) return "crypto";
  if (/\b(opay|moniepoint|palmpay|transfer|account number|acct)\b/.test(s)) return "wire";
  return "goods_services";
}

/* ---------------- verdict ---------------- */
const SEAL = {
  BLOCK: '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
  REVIEW: '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><path d="M12 7v6M12 17h.01"/></svg>',
  ALLOW: '<svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>',
};

function showResult(res, box) {
  const p = res.plain || { headline: res.verdict, reasons: [], reportable: [] };
  const ai = res.ai || {};
  const summary = p.subline || "";
  const why = p.reasons.map((r) => `<li class="${r.tone}"><i>${r.tone === "good" ? "✓" : "!"}</i><span>${esc(r.text)}</span></li>`).join("");
  const sc = res.screenshot;
  const read = sc ? `<div class="read"><b>From your screenshot:</b> ${esc(sc.seller_name || "Unknown seller")}${sc.platform ? " on " + esc(sc.platform) : ""}${res.amount ? " · " + money(res.amount, res.currency) : ""}
      <div class="tags">${[...sc.phones, ...sc.bank_accounts, ...sc.emails, ...sc.links].map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div></div>` : "";
  const report = p.reportable.length && res.verdict !== "ALLOW"
    ? `<button class="btn ghost" data-act="report">Report this seller</button>` : "";
  const warnText = `⚠️ PayGuard warning: ${p.reportable.map((r) => r.value).join(", ") || "this seller"} - ${p.reasons.map((r) => r.text).join(" ")} Check before you pay.`;
  const acts = res.verdict === "ALLOW"
    ? `<button class="btn ghost" data-act="again">Check another</button>`
    : `${report}<a class="btn wa" target="_blank" rel="noopener" href="https://wa.me/?text=${encodeURIComponent(warnText)}">Warn friends on WhatsApp</a><button class="btn ghost" data-act="again">Check another</button>`;
  box.innerHTML = `
    <article class="verdict">
      <div class="band ${res.verdict}">
        <div class="seal">${SEAL[res.verdict]}</div>
        <div><h2>${esc(p.headline)}</h2><p>${esc(summary)}</p></div>
      </div>
      <div class="body">
        ${read}
        ${why ? `<ul class="why">${why}</ul>` : ""}
        <div class="acts">${acts}</div>
        <div class="pay" id="pay-${res.screening_id}"></div>
        <div class="feedback">Was this right? <button class="chip" data-fb="yes">Yes</button><button class="chip" data-fb="no">No</button></div>
        ${techDetails(res)}
      </div>
    </article>`;
  box.querySelector('[data-act="again"]')?.addEventListener("click", () => { clearImage(); $("#text").value = ""; box.innerHTML = ""; window.scrollTo({ top: 0, behavior: "smooth" }); });
  box.querySelector('[data-act="report"]')?.addEventListener("click", (e) => reportFromResult(res, e.target));
  $$("[data-fb]", box).forEach((b) => b.addEventListener("click", () => { b.parentElement.textContent = "Thanks for the feedback."; }));
  renderPay(res, $(`#pay-${res.screening_id}`, box));
  box.scrollIntoView({ behavior: "smooth", block: "start" });
}

function techDetails(res) {
  const color = { ALLOW: "var(--safe)", REVIEW: "var(--warn)", BLOCK: "var(--bad)" }[res.verdict];
  const ev = (res.reasons || []).map((r) => `<li><div><span class="src ${esc(r.source)}">${esc(r.source.replace("_", " "))}</span>${esc(r.label)}${r.evidence ? `<em>${esc(r.evidence)}</em>` : ""}</div><span class="w ${r.weight < 0 ? "neg" : ""}">${r.weight > 0 ? "+" : ""}${r.weight}</span></li>`).join("");
  const m = (res.matched_patterns || []).map((x) => `<tr><td>${esc(x.title)}</td><td>${Number(x.similarity).toFixed(2)}</td></tr>`).join("");
  const trace = (res.ai?.trace || []).map((t) => `${t.tool}(${JSON.stringify(t.args)})\n → ${t.result_preview}`).join("\n\n");
  return `<details class="tech"><summary>Technical details</summary>
    <div class="techgrid">
      <div class="ring" style="--p:${res.risk_score};--c:${color}"><div>${res.risk_score}<small>RISK</small></div></div>
      <div><ul class="ev">${ev || "<li>No signals.</li>"}</ul></div>
    </div>
    ${m ? `<p class="note"><b>Closest scam patterns</b> (Db2 VECTOR_DISTANCE, cosine)</p><table><tr><th>Pattern</th><th>Similarity</th></tr>${m}</table>` : ""}
    ${trace ? `<p class="note"><b>AI investigator tool calls</b> (each one is a Db2 query)</p><pre>${esc(trace)}</pre>` : ""}
    <p class="note">Check #${res.screening_id} · stored in IBM Db2 · AI: ${esc(res.ai?.mode || "rules")} · source: ${esc(res.source || "paste")}</p>
  </details>`;
}

async function reportFromResult(res, btn) {
  const target = res.plain.reportable[0];
  btn.disabled = true;
  try {
    const r = await api("/api/report", { entity_type: target.type, value: target.value, category: res.top_category || "off_platform",
      narrative: (res.screenshot?.transcript || $("#text").value || "Reported from a PayGuard check").slice(0, 1900).padEnd(12, "."), reporter: "payguard-user" });
    btn.textContent = `Reported ✓ (${r.entity.report_count} report${r.entity.report_count === 1 ? "" : "s"})`;
    toast(r.entity.status === "BLOCKED" ? "Thanks - this contact is now blocked for everyone." : "Thanks - your report protects the next buyer.");
  } catch (e) { btn.disabled = false; toast(e.message); }
}

/* ---------------- PayPal ---------------- */
function loadPayPal() {
  if (!CONFIG.paypal_client_id) return Promise.reject(new Error("PayPal is not configured"));
  return paypalReady ||= new Promise((ok, fail) => {
    const s = document.createElement("script");
    s.src = `https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(CONFIG.paypal_client_id)}&currency=${CONFIG.currency}&intent=capture&components=buttons`;
    s.onload = () => ok(window.paypal); s.onerror = () => fail(new Error("PayPal could not load"));
    document.head.appendChild(s);
  });
}
function renderPay(res, box) {
  if (!box || res.verdict === "BLOCK") { if (box) box.remove(); return; }
  if (!res.paypal_allowed) {
    box.innerHTML = res.amount && !["USD", "GBP", "EUR"].includes(res.currency)
      ? `<p class="note">If you go ahead, pay in a way you can dispute. PayPal checkout here supports USD, GBP and EUR.</p>`
      : `<p class="note">If you go ahead, use PayPal Goods &amp; Services or another method with buyer protection.</p>`;
    return;
  }
  if (!CONFIG.paypal_client_id) { box.innerHTML = `<p class="note">PayPal checkout appears here when sandbox keys are configured.</p>`; return; }
  const id = res.screening_id;
  box.innerHTML = `<h3>Pay ${money(res.amount, res.currency)} with buyer protection</h3>
    ${res.verdict === "REVIEW" ? `<label class="ack"><input type="checkbox" id="ack-${id}"> I've read the warnings and still want to pay.</label>` : ""}
    <div id="ppb-${id}" style="max-width:420px;margin-top:10px"></div><p class="note" id="ppm-${id}"></p>`;
  const msg = $(`#ppm-${id}`);
  loadPayPal().then((paypal) => paypal.Buttons({
    style: { shape: "pill", label: "pay", height: 46 },
    onClick: (_d, actions) => { const a = $(`#ack-${id}`); if (a && !a.checked) { msg.innerHTML = '<span class="err">Tick the box first.</span>'; return actions.reject(); } return actions.resolve(); },
    createOrder: async () => (await api("/api/paypal/orders", { screening_id: id, acknowledge_risk: !!$(`#ack-${id}`)?.checked })).id,
    onApprove: async (d) => { const c = await api(`/api/paypal/orders/${d.orderID}/capture`, { screening_id: id }); box.innerHTML = `<p class="ok"><b>Paid with PayPal (sandbox) ✓</b> ${esc(c.status)} · ${esc(c.capture_id || "")}</p>`; },
    onError: (err) => { msg.innerHTML = `<span class="err">${esc(err.message || err)}</span>`; },
  }).render(`#ppb-${id}`)).catch((e) => { box.innerHTML = `<p class="note">${esc(e.message)}</p>`; });
}

/* ---------------- agent ---------------- */
$$("[data-agent]").forEach((b) => b.addEventListener("click", () => { $("#agent-input").value = b.dataset.agent; }));
$("#agent-btn").addEventListener("click", async () => {
  const btn = $("#agent-btn"), steps = $("#agent-steps");
  btn.disabled = true; btn.textContent = "Agent working…"; $("#agent-result").innerHTML = "";
  steps.innerHTML = `<div class="loading on"><div class="scan"></div><span>Understanding your request…</span></div>`;
  try {
    const r = await api("/api/agent/purchase", { instruction: $("#agent-input").value, language: LANG });
    const i = r.intent, v = r.screening.verdict;
    steps.innerHTML = `
      <div class="step"><b>1 · Understood</b> ${esc(i.item)} from ${esc(i.merchant || "unknown seller")} · ${money(i.amount, i.currency)} · ${esc(i.payment_method.replace("_", " "))}</div>
      <div class="step"><b>2 · Checked the seller</b> blocklist, reported scams, AI investigator</div>
      <div class="step"><b>3 · Decided</b> ${v === "BLOCK" ? "Refused to pay. This looks like a scam." : v === "REVIEW" ? "Needs your OK before paying." : "Safe. PayPal checkout is ready for your approval."}</div>`;
    showResult(r.screening, $("#agent-result"));
  } catch (e) { steps.innerHTML = `<p class="err">${esc(e.message)}</p>`; }
  finally { btn.disabled = false; btn.textContent = "Run agent"; }
});

/* ---------------- report ---------------- */
$("#report-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  try {
    const r = await api("/api/report", { entity_type: f.entity_type.value, value: f.value.value, category: f.category.value,
      amount: parseFloat(f.amount.value || 0), narrative: f.narrative.value, reporter: "payguard-user" });
    $("#report-out").innerHTML = `<span class="ok"><b>Thank you.</b> ${esc(r.entity.entity_value)} now has ${r.entity.report_count} report(s) · status <b>${esc(r.entity.status)}</b>.</span>`;
    f.reset();
  } catch (err) { $("#report-out").innerHTML = `<span class="err">${esc(err.message)}</span>`; }
});

/* ---------------- dashboard ---------------- */
function table(cols, rows) {
  if (!rows?.length) return `<p class="note">No rows.</p>`;
  return `<table><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr>${rows.map((r) => `<tr>${r.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</table>`;
}
let quickLoaded = false;
async function loadDashboard() {
  try {
    const h = await api("/api/health");
    $("#status").innerHTML = [[h.db2, "IBM Db2 connected"], [h.llm, h.llm ? `AI: ${h.model}` : "AI: rules only"], [h.paypal, h.paypal ? "PayPal sandbox" : "PayPal: no keys"], [true, `Embeddings: ${h.embedder}`]]
      .map(([on, t]) => `<span class="pill ${on ? "on" : "off"}">${esc(t)}</span>`).join("");
    const s = await api("/api/stats");
    $("#k-screen").textContent = s.totals.screenings; $("#k-block").textContent = s.totals.blocked;
    $("#k-review").textContent = s.totals.reviewed; $("#k-money").textContent = money(s.totals.money_protected);
    $("#kb").textContent = `Knowledge base in Db2: ${s.knowledge_base.patterns} scam patterns · ${s.knowledge_base.entities} contacts · ${s.knowledge_base.reports} community reports`;
    const max = Math.max(1, ...s.categories.map((c) => c.n));
    $("#cat-bars").innerHTML = s.categories.map((c) => `<div class="bar"><span>${esc(c.category)}</span><i style="width:${(c.n / max) * 100}%"></i><b>${c.n}</b></div>`).join("") || `<p class="note">No data yet.</p>`;
    $("#top-entities").innerHTML = table(["Contact", "Status", "Reports"], s.top_entities.map((e) => [e.entity_value, e.status, e.report_count]));
    const rec = await api("/api/screenings/recent");
    $("#recent").innerHTML = table(["#", "When", "Seller", "Amount", "Risk", "Verdict"], rec.map((r) => [r.id, (r.created_at || "").replace("T", " ").slice(0, 16), r.merchant || "-", money(r.amount, r.currency), r.risk_score, r.verdict]));
  } catch (e) { $("#status").innerHTML = `<span class="pill off">${esc(e.message)}</span>`; }
  if (!quickLoaded) {
    const qs = await api("/api/analyst/quick").catch(() => []);
    $("#quick").innerHTML = qs.map((q) => `<button class="chip" data-q="${esc(q)}">${esc(q)}</button>`).join("");
    $$("[data-q]").forEach((b) => b.addEventListener("click", () => ask(b.dataset.q)));
    quickLoaded = true;
  }
}
async function ask(q) {
  const out = $("#analyst-out"); out.innerHTML = `<div class="loading on"><div class="scan"></div><span>Running on Db2…</span></div>`;
  try {
    const r = await api("/api/analyst", { question: q });
    out.innerHTML = `${r.summary ? `<p><b>${esc(r.summary)}</b></p>` : ""}${r.error ? `<p class="err">${esc(r.error)}</p>` : ""}
      ${r.sql ? `<details><summary class="note">Db2 SQL (${esc(r.mode)})</summary><pre>${esc(r.sql.trim())}</pre></details>` : ""}${table(r.columns, r.rows)}`;
  } catch (e) { out.innerHTML = `<p class="err">${esc(e.message)}</p>`; }
}
$("#analyst-btn").addEventListener("click", () => { const q = $("#analyst-input").value.trim(); if (q) ask(q); });
$("#analyst-input").addEventListener("keydown", (e) => e.key === "Enter" && $("#analyst-btn").click());

/* ---------------- PWA: install + share target ---------------- */
let deferredInstall = null;
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferredInstall = e; $("#install").classList.add("on"); });
$("#install-btn").addEventListener("click", async () => { if (!deferredInstall) return; deferredInstall.prompt(); await deferredInstall.userChoice; deferredInstall = null; $("#install").classList.remove("on"); });
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});

async function boot() {
  CONFIG = await api("/api/config").catch(() => ({}));
  route();
  const q = new URLSearchParams(location.search);
  if (q.get("r")) {  // arrived from the Android share sheet
    try { showResult(await api(`/api/results/${encodeURIComponent(q.get("r"))}`), $("#result")); }
    catch (e) { toast(e.message); }
    history.replaceState(null, "", "/#check");
  } else if (q.get("error")) {
    toast(q.get("error") === "empty" ? "Nothing was shared - try again." : q.get("error"));
    history.replaceState(null, "", "/#check");
  }
}
boot();
