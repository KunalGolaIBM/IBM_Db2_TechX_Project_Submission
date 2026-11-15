/**
 * Tests interpret and plan through the exact supabase.functions.invoke path
 * (same headers the browser SDK sends).
 */
import https from 'https';

const API_KEY = 'sb_publishable_6XO0BUlauW57RyYPCqVygg_pwxCUZ1B';

function post(body) {
  return new Promise((resolve) => {
    const json = JSON.stringify(body);
    const opts = {
      hostname: 'iiywpvjtvzkkwxfgrqnd.supabase.co',
      path: '/functions/v1/suggest-mission',
      method: 'POST',
      headers: {
        'apikey':         API_KEY,
        'Authorization':  `Bearer ${API_KEY}`,
        'Content-Type':   'application/json',
        'x-client-info':  'supabase-js-web/2.112.4',
        'Content-Length': Buffer.byteLength(json),
      },
      timeout: 35000,
    };
    const req = https.request(opts, (res) => {
      let d = '';
      res.on('data', c => d += c);
      res.on('end', () => resolve({ status: res.statusCode, raw: d }));
    });
    req.on('error',   e  => resolve({ status: 0, raw: `ERROR: ${e.message}` }));
    req.on('timeout', () => { req.destroy(); resolve({ status: 0, raw: 'TIMEOUT' }); });
    req.write(json);
    req.end();
  });
}

const now        = new Date();
const dateIso    = now.toISOString();
const dateLabel  = now.toLocaleDateString('en-GB', { weekday:'long', day:'numeric', month:'long', year:'numeric' });

// ── 1. interpret ──────────────────────────────────────────────────────────────
console.log('=== INTERPRET ===');
const r1 = await post({
  operation:          'interpret',
  raw_input:          'maths assign due tomorrow, dorahack submit tonight',
  available_hours:    3,
  energy:             'medium',
  consistency_goals:  [],
  horizon:            'today',
  current_date_iso:   dateIso,
  current_date_label: dateLabel,
});
console.log('HTTP:', r1.status);
console.log('Body:', r1.raw.substring(0, 600));

// ── 2. plan (uses the interpreted items from above if interpret succeeded) ────
let items;
try {
  items = JSON.parse(r1.raw).items;
} catch {
  items = [
    { text: 'Dorahack submission', category: 'deadline', deadlineLabel: 'Tonight', isoDeadline: dateIso.slice(0,10), priority: 'urgent', isConsistency: false },
    { text: 'Maths assignment',    category: 'deadline', deadlineLabel: 'Tomorrow', isoDeadline: null, priority: 'high', isConsistency: false },
  ];
}

console.log('\n=== PLAN ===');
const r2 = await post({
  operation:          'plan',
  raw_input:          'maths assign due tomorrow, dorahack submit tonight',
  available_hours:    3,
  energy:             'medium',
  consistency_goals:  [],
  horizon:            'today',
  current_date_label: dateLabel,
  items,
});
console.log('HTTP:', r2.status);
console.log('Body:', r2.raw.substring(0, 600));
