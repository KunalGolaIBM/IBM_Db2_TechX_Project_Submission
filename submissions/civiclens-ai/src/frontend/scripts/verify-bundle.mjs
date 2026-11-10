#!/usr/bin/env node
/**
 * Verifies the production bundle in dist/ contains nothing that should stay on the server:
 *  - the literal value of any secret in the environment (auth tokens, database password, LLM keys),
 *  - database / driver / credential identifiers,
 *  - and that the HTML carries the Content-Security-Policy.
 * Secret VALUES are never printed; findings name only the file and the kind of match.
 *
 *   npm run build && npm run verify:bundle        (export your .env first for the literal-value check)
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const dist = new URL('../dist/', import.meta.url).pathname
const walk = (dir) =>
  readdirSync(dir).flatMap((n) => {
    const p = join(dir, n)
    return statSync(p).isDirectory() ? walk(p) : [p]
  })

let files
try {
  files = walk(dist)
} catch {
  console.error('dist/ not found: run `npm run build` first.')
  process.exit(2)
}

// literal secret values from the environment
const secrets = []
for (const name of ['DB2_PASSWORD', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'WATSONX_APIKEY', 'CIVICLENS_AUTH_TOKENS']) {
  for (const part of (process.env[name] ?? '').split(',')) {
    const value = part.split(':').pop().trim() // "id:role:token" -> token
    if (value.length >= 12) secrets.push({ name, value })
  }
}

const FORBIDDEN = [
  [/DB2_PASSWORD|DB2_USER|DB2_HOST|DB2INST1/i, 'database credential variable name'],
  [/\bibm_db\b|clidriver/i, 'database driver reference'],
  [/\bPWD=|UID=db2/i, 'connection-string fragment'],
  [/db2inst1/i, 'database user name'],
  [/CIVICLENS_AUTH_TOKENS/, 'auth token configuration variable'],
  [/Bearer\s+[A-Za-z0-9._-]{16,}/, 'hardcoded bearer token'],
  [/\bsk-[A-Za-z0-9_-]{20,}/, 'API-key shaped string'],
]

const findings = []
let scanned = 0
for (const file of files) {
  if (!/\.(js|css|html|map|json|svg|txt)$/.test(file)) continue
  scanned += 1
  const text = readFileSync(file, 'utf8')
  const rel = file.slice(dist.length)
  for (const s of secrets) if (text.includes(s.value)) findings.push(`${rel}: contains the literal value of ${s.name}`)
  for (const [pattern, what] of FORBIDDEN) if (pattern.test(text)) findings.push(`${rel}: ${what}`)
}

const html = readFileSync(join(dist, 'index.html'), 'utf8')
const csp = /http-equiv="Content-Security-Policy"\s+content="([^"]*)"/.exec(html)
if (!csp) findings.push('index.html: Content-Security-Policy meta tag is missing')
else {
  const policy = csp[1].replaceAll('&#39;', "'")
  if (!/script-src 'self'(;|$)/.test(policy)) findings.push("index.html: script-src is not exactly 'self'")
  if (/unsafe-eval/.test(policy)) findings.push('index.html: CSP allows unsafe-eval')
  if (!/object-src 'none'/.test(policy)) findings.push("index.html: CSP does not set object-src 'none'")
}
if (/<script(?![^>]*\bsrc=)[^>]*>[^<]+<\/script>/.test(html)) findings.push('index.html: contains an inline script')

for (const f of findings) console.error(`FINDING ${f}`)
console.log(`Scanned ${scanned} bundle files, checked ${secrets.length} literal secret value(s) from the environment: ${findings.length} finding(s)`)
process.exit(findings.length ? 1 : 0)
