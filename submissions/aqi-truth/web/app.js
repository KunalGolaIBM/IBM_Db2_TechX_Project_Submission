// AQI Truth front end. Live mode talks to the FastAPI server (Db2 + Granite); offline mode reads a read-only
// export of the same Db2 run from data/. Every number on the page comes from one of those two places.
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const PARAMS = ["pm25","pm10","no2","so2","o3","co"];
const LABEL = {pm25:"PM2.5",pm10:"PM10",no2:"NO₂",so2:"SO₂",o3:"O₃",co:"CO",ALL:"all"};
let API = (window.AQT_API || "").replace(/\/$/, "");
const fmt = new Intl.NumberFormat("en-IN");
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const cat = a => a == null ? "" : a <= 50 ? "Good" : a <= 100 ? "Satisfactory" : a <= 200 ? "Moderate" : a <= 300 ? "Poor" : a <= 400 ? "Very Poor" : "Severe";
const icon = (id, cls = "ic") => `<svg class="${cls}" aria-hidden="true"><use href="#i-${id}"/></svg>`;
// Two audited periods: the Sep-Dec 2025 study period (the headline) and Oct-Nov 2026 (as far as the archive reaches).
const PERIODS = [{id: "2025", label: "Sep–Dec 2025", from: "2025-09-01", to: "2025-12-31"},
                 {id: "2026", label: "Oct–Nov 2026", from: "2026-10-01", to: "2026-10-01"}];
const span = (a, b) => { const out = []; for (let t = Date.parse(a + "T00:00:00Z"); t <= Date.parse(b + "T00:00:00Z"); t += 864e5) out.push(new Date(t).toISOString().slice(0, 10)); return out; };
let PERIOD = PERIODS[0], DAYS = span(PERIOD.from, PERIOD.to);
const periodOf = d => PERIODS.find(p => d >= p.from && d <= p.to) || PERIODS[0];
const niceDay = d => new Date(d + "T00:00:00Z").toLocaleDateString("en-GB", {day:"numeric", month:"short", year:"numeric", timeZone:"UTC"});
const shortName = n => n.split(",")[0];

let LIVE = false, STATIONS = [], BY = {}, MAP = null, RECORDED = null, CUR = {s: 11603, d: "2025-10-23"};

async function get(path, snap) {
  if (LIVE) { const r = await fetch(API + path); if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.status); return r.json(); }
  const r = await fetch(snap); if (!r.ok) throw new Error("offline"); return r.json();
}

async function init() {
  const probe = async base => { const r = await fetch(base + "/api/health", {signal: AbortSignal.timeout(9000)});
    if (!r.ok || !(await r.json()).db2) throw 0; return base; };
  // Try both routes to the live server at once; keep the first that answers with a healthy Db2.
  const alt = window.AQT_ALT ? fetch(window.AQT_ALT, {cache: "no-store", signal: AbortSignal.timeout(5000)}).then(r => r.json())
    .then(j => j.api ? probe(j.api.replace(/\/$/, "")) : Promise.reject(0)) : Promise.reject(0);
  try { API = await Promise.any([probe(API), alt]); LIVE = true; } catch { LIVE = false; }
  const st = $("#status"); st.dataset.state = LIVE ? "live" : "offline";
  st.querySelector("span").textContent = LIVE ? "Live · Db2 + Granite" : "Offline export";
  st.title = LIVE ? "Every verdict, explanation and answer is computed now by IBM Db2 and IBM Granite" + (API ? " on " + new URL(API).host : "")
                  : "The live server is not reachable from this network, so the page shows a read-only export of the same Db2 run.";
  const [stats, stations, calendar, map, rec] = await Promise.all([
    get("/api/stats", "data/stats.json"), get("/api/stations", "data/stations.json"), get("/api/calendar", "data/calendar.json"),
    fetch("data/map.json").then(r => r.json()).catch(() => null), fetch("data/asks.json").then(r => r.json()).catch(() => null)]);
  STATIONS = stations; MAP = map; RECORDED = rec;
  const dup = {}; for (const s of stations) dup[shortName(s.name)] = (dup[shortName(s.name)] || 0) + 1;
  for (const s of stations) { s.label = dup[shortName(s.name)] > 1 ? `${shortName(s.name)} (${s.operator || "?"})` : shortName(s.name); s.n = {V:0,S:0,N:0}; }
  for (const c of calendar) { (BY[c.s] ||= {})[c.d] = c; const s = stations.find(x => x.id === c.s); if (s && c.d <= PERIODS[0].to) s.n[c.st]++; }
  const last = calendar.reduce((m, c) => c.d > m ? c.d : m, "");
  if (last >= PERIODS[1].from) PERIODS[1].to = last; else PERIODS.pop();
  periodSwitch();
  hero(stats, calendar);
  drawMap(); drawCalendar();
  $("#station").innerHTML = [...stations].sort((a,b) => a.label.localeCompare(b.label)).map(s => `<option value="${s.id}">${esc(s.label)}</option>`).join("");
  $("#station").onchange = () => select(+$("#station").value, CUR.d);
  $("#day").onchange = () => select(CUR.s, $("#day").value);
  $$(".tabs button").forEach(b => b.onclick = () => tab(b.dataset.tab));
  select(CUR.s, CUR.d, false);
  askSetup();
  fetch("data/results.html").then(r => r.text()).then(h => $("#resultsbody").innerHTML = h).catch(() => {});
}

/* ---------- hero ---------- */
function countUp(el, to) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) { el.textContent = fmt.format(to); return; }
  const t0 = performance.now(), dur = 900;
  const step = t => { const p = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - p, 3); el.textContent = fmt.format(Math.round(to * e)); if (p < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}
async function hero(stats, calendar) {
  $("#k-stations").textContent = STATIONS.length;
  countUp($("#h-shown"), stats.shown_anyway);
  $("#figures").innerHTML = [
    [stats.shown_anyway_very_poor, "of those would have read Very Poor or Severe"],
    [stats.suspect, "days computed only after excluding bad readings"],
    [stats.station_days, "station-days audited against CPCB rules"],
    [(stats.readings / 1e6).toFixed(2) + "M", "15-minute pollutant readings in Db2"]]
    .map(([n, t]) => `<div><dt>${typeof n === "number" ? fmt.format(n) : n}</dt><dd>${t}</dd></div>`).join("");
  // Specimen: the refused station-day with the highest plain-average AQI, straight from the audit.
  const pick = calendar.filter(c => c.st === "N" && c.n != null && c.d <= PERIODS[0].to).sort((a, b) => b.n - a.n)[0];
  if (!pick) return;
  let v; try { v = await get(`/api/day?station=${pick.s}&day=${pick.d}&llm=false`, `data/day/${pick.s}_${pick.d}.json`); } catch { return; }
  $("#specimen").innerHTML = `
    <div class="spec-top"><span>${icon("pin")} ${esc(shortName(v.station))}</span><span>${niceDay(v.day)}</span></div>
    <div class="spec-cols">
      <div><div class="spec-lab">Plain-average dashboard</div><div class="spec-big struck num">${v.naive_aqi}</div><div class="spec-cat">${cat(v.naive_aqi)}</div></div>
      <div><div class="spec-lab">${icon("db")} Db2 audit</div><span class="stamp">No AQI<br>computable</span></div>
    </div>
    <p class="spec-why">${esc(v.reason)}.</p>
    <a class="spec-cta" href="#audit" data-s="${pick.s}" data-d="${pick.d}">See the hours behind it ${icon("arrow")}</a>`;
  $("#specimen .spec-cta").onclick = e => { select(pick.s, pick.d); };
}

/* ---------- map ---------- */
function drawMap() {
  if (!MAP) { $(".mapbox").hidden = true; return; }
  const svg = $("#map"); svg.setAttribute("viewBox", `-12 -12 ${MAP.w + 24} ${MAP.h + 24}`);
  const dots = STATIONS.filter(s => MAP.stations[s.id]).map(s => {
    const [x, y] = MAP.stations[s.id], tot = s.n.V + s.n.S + s.n.N, share = tot ? s.n.N / tot : 0;
    const fill = share >= .1 ? "var(--red)" : share > 0 ? "var(--amber)" : "var(--green)";
    return `<circle class="stn" data-s="${s.id}" cx="${x}" cy="${y}" r="7" fill="${fill}"><title>${esc(s.label)}</title></circle>`;
  }).join("");
  svg.innerHTML = `<path class="outline" d="${MAP.outline}"/>${dots}<circle class="sel-ring" r="12" cx="-99" cy="-99"/>`;
  $("#mapcredit").textContent = "Dot colour: share of days with no computable AQI (red ≥ 10%, amber > 0). " + MAP.credit + ".";
  const tip = $("#maptip"), box = $(".mapbox");
  svg.onmousemove = e => {
    const c = e.target.closest(".stn"); if (!c) { tip.hidden = true; return; }
    const s = STATIONS.find(x => x.id === +c.dataset.s), r = box.getBoundingClientRect(), cr = c.getBoundingClientRect();
    tip.innerHTML = `<b>${esc(s.label)}</b> · ${esc(s.operator || "")}<br>${s.n.N} no-AQI · ${s.n.S} suspect · ${s.n.V} valid`;
    tip.style.left = (cr.left + cr.width / 2 - r.left) + "px"; tip.style.top = (cr.top - r.top) + "px"; tip.hidden = false;
  };
  svg.onmouseleave = () => tip.hidden = true;
  svg.onclick = e => { const c = e.target.closest(".stn"); if (c) select(+c.dataset.s, CUR.d); };
}

/* ---------- station, strip, day ---------- */
function inSnapshot(s, d) { const c = (BY[s] || {})[d]; return c && (c.st !== "V" || d === "2025-10-21" || d === PERIODS[PERIODS.length - 1].to); }

function select(s, d, scroll = false) {
  const changed = s !== CUR.s; CUR = {s, d};
  const st = STATIONS.find(x => x.id === s); if (!st) return;
  const p = periodOf(d);
  if (p !== PERIOD) { PERIOD = p; DAYS = span(p.from, p.to); $("#strip").innerHTML = ""; periodSwitch(); }
  $("#station").value = s; $("#day").value = d;
  $("#st-name").textContent = st.label;
  const n = {V: 0, S: 0, N: 0}; for (const day of DAYS) { const c = (BY[s] || {})[day]; if (c) n[c.st]++; }
  $("#st-sub").textContent = `${st.name.split(" - ")[0]} · operator ${st.operator || "unknown"} · ${PERIOD.label}: ${n.N} days with no AQI, ${n.S} suspect`;
  if (MAP && MAP.stations[s]) { const r = $("#map .sel-ring"); r.setAttribute("cx", MAP.stations[s][0]); r.setAttribute("cy", MAP.stations[s][1]); }
  if (changed || !$("#strip").childElementCount) strip(s);
  $$("#strip .t.sel").forEach(x => x.classList.remove("sel"));
  const t = $(`#strip .t[data-d="${d}"]`); if (t) t.classList.add("sel");
  load();
}

function periodSwitch() {
  const box = $("#periods"); if (!box) return;
  box.hidden = PERIODS.length < 2;
  box.innerHTML = PERIODS.map(p => `<button type="button" aria-pressed="${p === PERIOD}" data-p="${p.id}">${p.label}</button>`).join("");
  box.onclick = e => { const b = e.target.closest("button"); if (!b) return; const p = PERIODS.find(x => x.id === b.dataset.p);
    if (p !== PERIOD) select(CUR.s, p.id === "2026" ? p.to : "2025-10-23"); };
  $("#day").min = PERIOD.from; $("#day").max = PERIOD.to;
  $("#strip").setAttribute("aria-label", "Days, " + PERIOD.label);
}

function strip(s) {
  const by = BY[s] || {};
  $("#strip").style.gridTemplateColumns = `repeat(${DAYS.length},1fr)`;
  $("#strip").innerHTML = DAYS.map(d => { const c = by[d];
    const k = c ? c.st : "x", off = !LIVE && c && !inSnapshot(s, d) ? " off" : "";
    return `<div class="t ${k === "V" ? "" : k}${off}" role="option" data-d="${d}" title="${niceDay(d)}${c ? ` · ${{V:"valid",S:"suspect",N:"no AQI"}[c.st]} · audited ${c.a ?? "—"} / plain average ${c.n ?? "—"}` : " · not audited"}"></div>`; }).join("");
  $("#strip + .months")?.remove();
  const cnt = {}; for (const d of DAYS) cnt[d.slice(0, 7)] = (cnt[d.slice(0, 7)] || 0) + 1;
  const ms = Object.keys(cnt), name = m => new Date(m + "-01T00:00:00Z").toLocaleDateString("en-GB", {month: "short", timeZone: "UTC"});
  $("#strip").insertAdjacentHTML("afterend", `<div class="months" style="grid-template-columns:${ms.map(m => cnt[m] + "fr").join(" ")}">${ms.map(m => `<span>${cnt[m] > 3 ? name(m) : ""}</span>`).join("")}</div>`);
  $("#strip").onclick = e => { const t = e.target.closest(".t"); if (t && !t.classList.contains("x")) select(CUR.s, t.dataset.d); };
}

document.addEventListener("keydown", e => {
  if (!["ArrowLeft","ArrowRight"].includes(e.key) || !document.activeElement || !document.activeElement.closest("#audit") || /INPUT|SELECT/.test(document.activeElement.tagName)) return;
  const i = DAYS.indexOf(CUR.d) + (e.key === "ArrowRight" ? 1 : -1);
  if (DAYS[i]) { e.preventDefault(); select(CUR.s, DAYS[i]); }
});

function tab(name) {
  $$(".tabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === name));
  $$(".panel").forEach(p => p.hidden = p.dataset.panel !== name);
  if (name === "receipt") receipt();
}

/* ---------- verifiable receipt ---------- */
const short = h => h ? `${h.slice(0, 12)}…${h.slice(-6)}` : "—";
const utc = t => String(t).replace("T", " ").slice(0, 19) + " UTC";
function receiptChecks(r) {
  const row = (ok, title, text) => `<li class="${ok ? "ok" : "no"}">${icon(ok ? "check" : "x")}<div><b>${title}</b><span>${text}</span></div></li>`;
  return `<ul class="rchecks">
    ${row(r.chain_ok, "Hash chain", `this receipt's SHA-256 recomputes from its fields and links to the receipt before it`)}
    ${row(r.history_ok, "History", `the readings Db2 returns <code>FOR SYSTEM_TIME AS OF</code> ${utc(r.issued_at)} hash to the receipt`)}
    ${row(r.data_same, "Current data", r.data_same ? `the ${fmt.format(r.n_now)} readings stored now are the ones judged` : `${r.changed} reading(s) differ from what was judged: ${esc(r.example || "")}`)}
    ${row(r.rules_same, "Rules", "CPCB breakpoints, plausibility limits and settings are unchanged")}</ul>`;
}
async function receipt() {
  const p = $("#p-receipt"), {s, d} = CUR;
  if (!LIVE) { p.innerHTML = `<p class="fine">${icon("lock")} Every verdict gets a SHA-256 receipt in Db2, and Db2 re-checks it on request. That needs the live server, which this network can't reach right now.</p>`; return; }
  p.innerHTML = `<div class="lines"><div class="sk"></div><div class="sk" style="width:70%"></div></div>`;
  let r; try { r = await get(`/api/receipt?station=${s}&day=${d}`); } catch (e) { p.innerHTML = `<p class="fine">No receipt: ${esc(e.message)}</p>`; return; }
  if (CUR.s !== s || CUR.d !== d) return;
  p.innerHTML = `<p class="fine">${icon("lock")} A Db2 trigger issued this receipt when the verdict was written. <code>AQ.VERIFY_RECEIPT</code> just re-checked it, live.</p>
    <div class="rhead"><span class="stamp sm ${r.result === "MATCH" ? "VALID" : ""}">${r.result.replace("_", " ")}</span>
      <span class="fine">receipt #${r.receipt_id} · issued ${utc(r.issued_at)} · ${fmt.format(r.n_readings)} readings judged</span></div>
    ${receiptChecks(r)}
    <dl class="rhash"><dt>receipt</dt><dd>${short(r.receipt_hash)}</dd><dt>previous</dt><dd>${short(r.prev_hash)}</dd><dt>inputs</dt><dd>${short(r.input_hash)}</dd></dl>
    <div class="tamper"><button class="btn" id="tamperbtn">${icon("shield")}Try to tamper with this day</button>
      <span class="fine">Db2 overwrites one reading inside a savepoint, re-checks the receipt, then rolls the change back. Nothing is kept.</span></div>
    <div id="tamperout"></div>`;
  $("#tamperbtn").onclick = async () => {
    const b = $("#tamperbtn"), out = $("#tamperout"); b.disabled = true;
    out.innerHTML = `<div class="thinking">${icon("db")} Db2 is changing a reading and re-checking the receipt…</div>`;
    try {
      const r2 = await fetch(`${API}/api/receipt/tamper?station=${s}&day=${d}`, {method: "POST"});
      if (!r2.ok) throw new Error((await r2.json().catch(() => ({}))).detail || r2.status);
      const t = await r2.json();
      out.innerHTML = `<ol class="tsteps">
        <li><b>1 · Overwrite</b><span>${esc(t.touched)}</span></li>
        <li><b>2 · Verify</b><span><span class="stamp sm">${esc(t.during.replace("_", " "))}</span> ${esc(t.during_detail || "")}</span></li>
        <li><b>3 · Roll back, verify</b><span><span class="stamp sm ${t.after === "MATCH" ? "VALID" : ""}">${esc(t.after)}</span> the change is gone and the receipt holds again.</span></li></ol>
        <p class="fine">All three steps ran inside one Db2 call (<code>AQ.TAMPER_TEST</code>, ${t.ms} ms).</p>`;
    } catch (e) { out.innerHTML = `<p class="fine">Could not run the tamper test: ${esc(e.message)}</p>`; }
    b.disabled = false;
  };
}


let loadSeq = 0;
async function load() {
  const {s, d} = CUR, seq = ++loadSeq;
  let v;
  try { v = await get(`/api/day?station=${s}&day=${d}&llm=false`, `data/day/${s}_${d}.json`); }
  catch (e) {
    if (seq !== loadSeq) return;
    $("#verdict").innerHTML = `<div style="grid-column:1/-1"><div class="v-lab">${icon("file")} Not in the offline export</div>
      <p class="v-reason">${LIVE ? esc(e.message) : "The offline copy holds every red and amber day (and 21 Oct for all stations). This valid day is in the live audit only."}</p></div>`;
    $("#p-why").innerHTML = ""; $("#grid").innerHTML = ""; $("#evidence").innerHTML = ""; return;
  }
  if (seq !== loadSeq) return;
  const nc = v.status === "NOT_COMPUTABLE", vd = $("#verdict");
  vd.classList.remove("swap"); void vd.offsetWidth; vd.classList.add("swap");
  vd.innerHTML = `
    <div class="naive ${nc && v.naive_aqi != null ? "struck" : ""}"><div class="v-lab">Plain-average dashboard</div>
      <div class="v-big num">${v.naive_aqi ?? "—"}</div><div class="v-cat">${cat(v.naive_aqi) || "no data"}</div></div>
    <div><div class="v-lab">${icon("db")} Db2 audit · ${niceDay(v.day)}</div>
      ${nc ? `<span class="stamp">No AQI computable</span>`
           : `<div class="v-big num">${v.aqi}</div><div class="v-cat">${cat(v.aqi)} · driven by ${LABEL[v.prominent] || v.prominent} · <span class="stamp sm ${v.status}">${v.status}</span></div>`}
      <p class="v-reason">${esc(v.reason)}.</p></div>`;
  hours(v); evidence(v);
  if (!$("#p-receipt").hidden) receipt();
  if (v.explanation) why(v.explanation);
  else if (LIVE) {
    $("#p-why").innerHTML = `<div class="thinking">${icon("cpu")} Granite is writing two sentences from the evidence. Code checks every number before it is shown.</div><div class="lines"><div class="sk"></div><div class="sk" style="width:80%"></div></div>`;
    try { const e = await get(`/api/explain?station=${s}&day=${d}`); if (seq === loadSeq) why(e); }
    catch { if (seq === loadSeq) $("#p-why").innerHTML = `<p class="fine">No explanation could be generated right now.</p>`; }
  } else $("#p-why").innerHTML = `<p class="fine">No stored explanation for this day in the offline export.</p>`;
}

function why(ex) {
  if (!ex) { $("#p-why").innerHTML = `<p class="fine">No explanation stored.</p>`; return; }
  const tmpl = ex.model.startsWith("template");
  $("#p-why").innerHTML = `<p class="why">${esc(ex.text)}</p><div class="badges">
    <span class="badge${tmpl ? " warn" : ""}">${icon(tmpl ? "file" : "cpu")}${tmpl ? "Template: model text failed the checks" : "IBM " + esc(ex.model)}</span>
    <span class="badge">${icon("check")}numbers match the evidence</span>
    <span class="badge${ex.vector_agrees ? "" : " warn"}">${icon(ex.vector_agrees ? "check" : "x")}${ex.vector_agrees ? "Db2 vector search found the same rule" : "vector search disagreed; cited rule kept"}</span>
    <span class="badge">${icon("file")}${esc(ex.rules)}</span></div>`;
}

function hours(v) {
  let g = `<div></div>` + Array.from({length: 24}, (_, h) => `<div class="hdr">${h % 3 ? "" : h}</div>`).join("");
  for (const p of PARAMS) g += `<div class="lab">${LABEL[p]}</div>` + v.grid[p].map((c, h) => c
    ? `<div class="cell ${c.k} ${c.j ? "j" : ""}" title="${LABEL[p]} ${h}:00–${h + 1}:00 · ${c.k}${c.v != null ? " · " + c.v : ""}${c.raw != null && c.raw !== c.v ? " (raw " + c.raw + ")" : ""}"></div>`
    : `<div class="cell" title="${LABEL[p]} ${h}:00–${h + 1}:00 · nothing arrived"></div>`).join("");
  $("#grid").innerHTML = g;
}

function evidence(v) {
  $("#evidence").innerHTML = `<tr><th>Pollutant</th><th>Check</th><th>Observed</th><th>Rule</th></tr>` + v.evidence.map(e =>
    `<tr class="${e.passed ? "" : "fail"}"><td>${LABEL[e.param] || e.param}</td><td><span class="${e.passed ? "ok" : "no"}">${e.passed ? "✓" : "✗"}</span> ${e.check}</td>
     <td>${esc(String(e.observed ?? "").replace(/(^|[^\d])\.(\d)/g, "$10.$2"))}</td>
     <td>${e.url ? `<a href="${e.url}" target="_blank" rel="noopener" title="${esc(e.source)}">${e.rule}</a>` : e.rule}</td></tr>`).join("");
}

function drawCalendar() {
  $("#cal").innerHTML = STATIONS.map(s => `<div class="calrow"><div class="nm" title="${esc(s.name)}">${esc(s.label)}</div>` +
    DAYS.map(d => { const c = (BY[s.id] || {})[d]; return `<div class="d ${c ? (c.st === "V" ? "" : c.st) : "x"}" data-s="${s.id}" data-d="${d}" title="${d}${c ? " · " + c.st : ""}"></div>`; }).join("") + `</div>`).join("");
  $("#cal").onclick = e => { const d = e.target.closest(".d"); if (d) { select(+d.dataset.s, d.dataset.d); $("#audit").scrollIntoView(); } };
}

/* ---------- ask ---------- */
const ATTACK = q => /delete|ignore|drop|tomorrow|every row/i.test(q);
function askSetup() {
  const seg = $("#seg"); seg.classList.toggle("live", LIVE);
  $$("#seg button").forEach(b => b.onclick = () => mode(b.dataset.mode));
  const qs = RECORDED ? RECORDED.answers.map(a => a.question) : [];
  $("#chips").innerHTML = qs.map((q, i) => `<button type="button" class="chip${ATTACK(q) ? " attack" : ""}" data-i="${i}">${esc(q)}</button>`).join("");
  $("#chips").onclick = e => { const b = e.target.closest(".chip"); if (b) { $("#q").value = qs[+b.dataset.i]; askLive(false); } };
  $("#askform").onsubmit = e => { e.preventDefault(); askLive(false); };
  recorded();
  if (!LIVE) {
    mode("rec");
    $("#pane-live").insertAdjacentHTML("afterbegin", `<div class="refuse" style="margin-bottom:14px">${icon("x")}<div><b>The live server isn't reachable from this network.</b> Typed questions need it. Some networks block <code>*.github.dev</code>; mobile data usually works. The Recorded tab shows real answers the live system gave.</div></div>`);
    $("#q").disabled = $("#askbtn").disabled = true;
  } else asklog();
}

function mode(m) {
  $("#seg").dataset.mode = m;
  $$("#seg button").forEach(b => b.setAttribute("aria-selected", b.dataset.mode === m));
  $$(".askpane").forEach(p => p.hidden = p.dataset.pane !== m);
}

function recorded() {
  if (!RECORDED) { $("#rec-note").textContent = "No recorded answers available."; return; }
  $("#rec-note").innerHTML = `${icon("history")} Real answers the live system gave on ${esc(RECORDED.recorded)}: Granite wrote the SQL and Db2 ran it as the read-only user. Kept so the page still shows the question box when the server is offline. They are not live.`;
  $("#rec-list").innerHTML = RECORDED.answers.map(a => `<details class="rec-item"><summary><span>${esc(a.question)}</span>${icon("arrow")}</summary><div class="rec-body">${render(a)}</div></details>`).join("");
}

const KW = /\b(SELECT|FROM|WHERE|AND|OR|GROUP BY|ORDER BY|DESC|ASC|NULLS LAST|COUNT|MAX|MIN|AVG|SUM|DISTINCT|AS|LIKE|BETWEEN|IS NOT NULL|IS NULL|NOT|IN|FETCH FIRST|ROWS?|ONLY|HAVING|JOIN|ON|CASE|WHEN|THEN|ELSE|END)\b/g;
const hl = s => esc(s).replace(KW, '<span class="k">$1</span>');

function render(r, meta = "") {
  if (r.refused) return `${meta}<div class="refuse">${icon("shield")}<div><b>Refused.</b> ${esc(r.why)}</div></div>${r.sql ? `<pre class="sqlbox" style="margin-top:12px"><span class="cap">blocked SQL</span>${hl(r.sql)}</pre>` : ""}`;
  const rows = r.rows || [];
  return `${meta}<pre class="sqlbox"><span class="cap">checked SQL</span>${hl(r.sql)}</pre>
    <div class="tablewrap"><table><tr>${r.columns.map(c => `<th>${esc(c)}</th>`).join("")}</tr>${rows.length ? rows.map(row => `<tr>${row.map(c => `<td>${esc(typeof c === "number" && !Number.isInteger(c) ? c.toFixed(1) : c)}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${r.columns.length}">No rows match.</td></tr>`}</table></div>`;
}

let busy = false, tick = null;
function pipe(step, state) {
  const li = $(`#pipe li[data-step="${step}"]`); if (!li) return;
  const order = ["guard","model","check","db2","done"], i = order.indexOf(step);
  $$("#pipe li").forEach((x, j) => { if (j < i && !x.classList.contains("fail")) { x.classList.remove("on"); x.classList.add("done"); } });
  li.classList.remove("on","done","fail"); li.classList.add(state);
}

async function askLive(fresh) {
  const q = $("#q").value.trim() || $("#q").placeholder;
  if (busy || !LIVE) return; busy = true; $("#q").value = q;
  $("#askbtn").disabled = true; $("#pipe").hidden = false; $$("#pipe li").forEach(x => x.className = "");
  const ans = $("#answer"); ans.innerHTML = ""; const t0 = performance.now(); let phase = "Checking the question", sql = "", gotTok = false, firstTok = null;
  $("#timer").hidden = false;
  const show = () => { const s = (performance.now() - t0) / 1000;
    $("#timer").innerHTML = `${icon("clock")}<b>${s.toFixed(1)} s</b> <span>${phase}</span>`; };
  clearInterval(tick); tick = setInterval(show, 100); show();
  pipe("guard", "on");
  const finish = r => {
    clearInterval(tick); busy = false; $("#askbtn").disabled = false;
    const s = ((performance.now() - t0) / 1000).toFixed(1);
    if (r.refused) { const at = r.sql ? (r.why.startsWith("Db2") ? "db2" : "check") : "guard"; pipe(at, "fail"); }
    else { pipe("done", "done"); }
    $("#timer").innerHTML = `${icon("clock")}<b>${s} s</b> <span>${r.source === "reused" ? `SQL reused from an identical earlier question · Db2 ran it just now in ${r.ms_db2} ms`
      : r.ms_model ? `Granite ${(r.ms_model / 1000).toFixed(1)} s (first word after ${(r.ms_first_token / 1000).toFixed(1)} s) · Db2 ${r.ms_db2} ms` : "answered"}</span>`;
    const meta = r.source === "reused" ? `<div class="meta"><span class="badge">${icon("history")}SQL Granite wrote for this exact question at ${esc(String(r.reused_from).replace("T", " ").slice(0, 16))} UTC, checked again and run live by Db2</span><button class="btn" id="fresh">${icon("refresh")}Ask Granite fresh</button></div>` : "";
    ans.innerHTML = `<div class="result-in">${render(r, meta)}</div>`;
    const f = $("#fresh"); if (f) f.onclick = () => askLive(true);
    asklog();
  };
  let res;
  try { res = await fetch(API + "/api/ask/stream", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({question: q, fresh})}); }
  catch { finish({refused: true, why: "The live server stopped answering. Try again in a minute, or use the Recorded tab."}); return; }
  if (!res.ok) { const j = await res.json().catch(() => ({})); finish({refused: true, why: j.detail || `server error ${res.status}`}); return; }
  const rd = res.body.getReader(), dec = new TextDecoder(); let buf = "", done = false;
  const box = () => { let b = $("#answer .sqlbox.live"); if (!b) { ans.innerHTML = `<pre class="sqlbox live"><span class="cap">Granite is writing</span><span class="txt"></span><span class="caret"></span></pre>`; b = $("#answer .sqlbox.live"); } return b; };
  try {
    while (!done) {
      const {value, done: end} = await rd.read(); if (end) break;
      buf += dec.decode(value, {stream: true}); let nl;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl); buf = buf.slice(nl + 1); if (!line.trim()) continue;
        const ev = JSON.parse(line);
        if (ev.e === "guard") { phase = "Checking the question is in scope"; }
        else if (ev.e === "reuse") { pipe("model", "done"); pipe("check", "on"); phase = "Same question asked before: reusing its checked SQL"; box().querySelector(".txt").textContent = ev.sql; }
        else if (ev.e === "queue") { phase = "Granite is answering another visitor; you're next"; }
        else if (ev.e === "model") { pipe("model", "on"); phase = "Granite is reading the schema and your question (CPU only, about 10 s)"; box(); }
        else if (ev.e === "tok") { if (!gotTok) { gotTok = true; phase = "Granite is writing SQL"; } sql += ev.t; box().querySelector(".txt").innerHTML = hl(sql); }
        else if (ev.e === "check") { pipe("check", "on"); phase = "Checking the SQL: one SELECT, audited views only"; }
        else if (ev.e === "db2") { pipe("db2", "on"); phase = "Db2 is running it as AQREADER"; }
        else if (ev.e === "result") { done = true; finish(ev); }
      }
    }
    if (!done) finish({refused: true, why: "The answer was cut off. Try again."});
  } catch { if (busy) finish({refused: true, why: "The connection dropped while Granite was working. Try again."}); }
}

async function asklog() {
  if (!LIVE) return;
  try {
    const rows = await get("/api/asklog");
    if (!rows.length) return;
    $("#asklog-box").hidden = false;
    $("#asklog").innerHTML = `<p class="fine">From <code>AQ.ASK_LOG</code>, an append-only Db2 table. Every question is logged with how it was answered.</p><div class="tablewrap"><table><tr><th>When (UTC)</th><th>Question</th><th>Outcome</th><th>SQL by</th><th>Granite</th><th>Db2</th></tr>` +
      rows.map(r => `<tr><td>${esc(String(r.at).replace("T", " ").slice(5, 16))}</td><td>${esc(r.question)}</td><td>${esc(r.outcome)}</td><td>${{GRANITE:"Granite",REUSED:"reused",GUARD:"—"}[r.source] || esc(r.source)}</td><td>${r.ms_model != null ? (r.ms_model / 1000).toFixed(1) + " s" : "—"}</td><td>${r.ms_db2 != null ? r.ms_db2 + " ms" : "—"}</td></tr>`).join("") + `</table></div>`;
  } catch {}
}

init();
