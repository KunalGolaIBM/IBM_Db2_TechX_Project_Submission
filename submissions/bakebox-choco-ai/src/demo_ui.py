"""
Self-Contained Interactive Judge Playground HTML UI served at `GET /demo`.
Zero external CDN or npm build required — communicates directly with FastAPI endpoints.
"""

DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>BAKEBOX CHOCO AI — IBM Db2 Live Engineering Console</title>
<style>
  :root { --bg: #0f172a; --card: #1e293b; --accent: #f59e0b; --text: #f8fafc; --muted: #94a3b8; --ok: #10b981; --err: #ef4444; }
  * { box-sizing: border-box; font-family: system-ui, -apple-system, sans-serif; }
  body { margin: 0; background: var(--bg); color: var(--text); padding: 24px; line-height: 1.5; }
  h1 { margin: 0 0 4px; color: var(--accent); font-size: 1.6rem; }
  .sub { color: var(--muted); margin-bottom: 20px; font-size: 0.92rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }
  .card { background: var(--card); border: 1px solid #334155; border-radius: 12px; padding: 16px; }
  .card h2 { margin: 0 0 10px; font-size: 1.05rem; color: #e2e8f0; }
  input, select, button { width: 100%; padding: 9px 12px; margin: 6px 0; border-radius: 8px; border: 1px solid #475569; background: #0f172a; color: var(--text); }
  button { background: var(--accent); color: #0f172a; font-weight: 700; border: none; cursor: pointer; }
  button:hover { opacity: 0.92; }
  pre { background: #020617; padding: 10px; border-radius: 8px; overflow-x: auto; font-size: 0.8rem; max-height: 240px; color: #cbd5e1; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.75rem; background: #1e3a8a; color: #93c5fd; margin-right: 6px; }
</style>
</head>
<body>
  <h1>BAKEBOX — CHOCO AI on IBM Db2</h1>
  <div class="sub">Shri Ram Baker (Mathura) · 3-Way Hybrid RRF (Db2 Cosine + BM25 + TF-IDF) · Recursive BOM CTE · WITH RS Locking · SHA-256 Audit Chain</div>
  <div id="healthBanner" class="sub"><span class="badge">Loading health...</span></div>

  <div class="grid">
    <div class="card">
      <h2>1. CHOCO AI Bilingual Chat &amp; Guardrails</h2>
      <input id="chatSession" value="judge_demo_1" placeholder="Session ID" />
      <input id="chatMsg" value="bina ande wala red velvet cake dikhao" placeholder="Ask about cakes, order #1002, or patty tawa rule..." />
      <button onclick="sendChat()">Send to CHOCO AI</button>
      <pre id="chatOut">Click "Send to CHOCO AI" to test 3-Way RRF + Hinglish CRAG + Self-RAG.</pre>
    </div>

    <div class="card">
      <h2>2. Recursive Db2 BOM CTE Checker</h2>
      <select id="bomCakeId">
        <option value="1">Cake #1: Red Velvet Crimson Crumb Crown (All In Stock)</option>
        <option value="2">Cake #2: Black Forest Gateau (Cherries Shortage Test)</option>
        <option value="4">Cake #4: Red Velvet Heart Love Affair</option>
      </select>
      <button onclick="checkBom()">Run WITH RECIPE_BOM CTE</button>
      <pre id="bomOut">Select a cake to inspect multi-level ingredient stock in Db2.</pre>
    </div>

    <div class="card">
      <h2>3. Atomic ACID Order (WITH RS + BOM + Audit)</h2>
      <input id="ordName" value="Aditi Agrawal" placeholder="Customer Name" />
      <input id="ordPhone" value="+91 9876501234" placeholder="10-digit Mobile" />
      <input id="ordCakeId" type="number" value="1" min="1" placeholder="Cake ID" />
      <input id="ordQty" type="number" value="1" min="1" max="20" placeholder="Quantity" />
      <button onclick="placeOrder()">Place Atomic Order</button>
      <pre id="ordOut">Executes BOM check (scaled by qty) -> SP_RESERVE_CAKE_STOCK -> SEQ_BB_ORDER_ID -> BB_ORDERS -> BB_AUDIT_LOG.</pre>
    </div>

    <div class="card">
      <h2>4. 2FA Order Tracking &amp; Audit Chain Verify</h2>
      <input id="trkId" type="number" value="1002" placeholder="Order ID" />
      <input id="trkPhone" value="+91 9876543210" placeholder="Registered Phone" />
      <input id="opKey" type="password" value="" placeholder="X-Operator-Key (if configured in .env)" />
      <button onclick="trackOrder()">Track Order (Masked PII)</button>
      <button onclick="verifyAudit()" style="background:#10b981;margin-top:6px;">Verify HMAC-SHA256 BB_AUDIT_LOG Chain</button>
      <pre id="trkOut">Test #1002 with +91 9876543210 (try wrong phone to trigger auth failure log).</pre>
    </div>
  </div>

<script>
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
async function refreshHealth() {
  const r = await fetch('/api/health');
  const d = await r.json();
  document.getElementById('healthBanner').innerHTML =
    `<span class="badge">${escapeHtml(d.db2_mode)}</span>` +
    `<span class="badge">Catalog: ${escapeHtml(d.catalog_items_indexed)} nodes</span>` +
    `<span class="badge">Audit Valid: ${escapeHtml(d.audit_chain_intact)}</span>`;
}
async function sendChat() {
  const r = await fetch('/api/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ session_id: chatSession.value, message: chatMsg.value })
  });
  chatOut.textContent = JSON.stringify(await r.json(), null, 2);
}
async function checkBom() {
  const r = await fetch(`/api/cakes/${bomCakeId.value}/availability`);
  bomOut.textContent = JSON.stringify(await r.json(), null, 2);
}
async function placeOrder() {
  const r = await fetch('/api/orders', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      cake_id: parseInt(ordCakeId.value, 10),
      customer_name: ordName.value,
      customer_phone: ordPhone.value,
      quantity: parseInt(ordQty.value || '1', 10)
    })
  });
  ordOut.textContent = JSON.stringify(await r.json(), null, 2);
  refreshHealth();
}
async function trackOrder() {
  const r = await fetch(`/api/orders/${trkId.value}?phone=${encodeURIComponent(trkPhone.value)}`);
  trkOut.textContent = JSON.stringify(await r.json(), null, 2);
}
async function verifyAudit() {
  const headers = opKey.value ? {'X-Operator-Key': opKey.value} : {};
  const r = await fetch('/api/audit/verify', { headers });
  trkOut.textContent = JSON.stringify(await r.json(), null, 2);
}
refreshHealth();
</script>
</body>
</html>
"""
