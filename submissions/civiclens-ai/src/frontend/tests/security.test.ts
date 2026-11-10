import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const root = join(__dirname, '..')
const walk = (dir: string): string[] =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name)
    return statSync(path).isDirectory() ? walk(path) : [path]
  })
const sourceFiles = walk(join(root, 'src')).filter((f) => /\.(ts|tsx)$/.test(f))
const stripComments = (code: string) => code.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1')
const read = (file: string) => readFileSync(file, 'utf8')

describe('static security checks on the frontend source', () => {
  it('finds source files to check', () => {
    expect(sourceFiles.length).toBeGreaterThan(40)
  })

  it('has no HTML-injection or code-evaluation sinks', () => {
    const sinks = /dangerouslySetInnerHTML|\.innerHTML\s*=|\.outerHTML\s*=|insertAdjacentHTML|document\.write\(|\beval\(|new Function\(/
    const hits = sourceFiles.filter((f) => sinks.test(stripComments(read(f))))
    expect(hits.map((f) => f.replace(root, ''))).toEqual([])
  })

  it('never uses localStorage (the token lives in sessionStorage only) or cookies', () => {
    const hits = sourceFiles.filter((f) => /localStorage|document\.cookie/.test(stripComments(read(f))))
    expect(hits.map((f) => f.replace(root, ''))).toEqual([])
  })

  it('only the token store touches sessionStorage', () => {
    const hits = sourceFiles.filter((f) => /sessionStorage/.test(stripComments(read(f)))).map((f) => f.replace(root + '/', ''))
    expect(hits).toEqual(['src/auth/tokenStore.ts'])
  })

  it('sends requests without ambient credentials', () => {
    expect(read(join(root, 'src/api/client.ts'))).toContain("credentials: 'omit'")
  })

  it('has no secret-looking VITE_ variable anywhere (VITE_ values are baked into the public bundle)', () => {
    const files = [...sourceFiles, join(root, 'vite.config.ts'), join(root, '.env.example'), join(root, 'index.html')]
    const names = files.flatMap((f) => [...stripComments(read(f)).matchAll(/VITE_[A-Z0-9_]+/g)].map((m) => m[0]))
    expect(new Set(names)).toEqual(new Set(['VITE_API_BASE_URL']))
    for (const name of names) expect(name).not.toMatch(/TOKEN|SECRET|PASSWORD|PASSWD|KEY|CREDENTIAL|DB2/)
  })

  it('the committed env example holds only the public API address setting', () => {
    const lines = read(join(root, '.env.example')).split('\n').filter((l) => l.trim() && !l.trim().startsWith('#'))
    expect(lines).toEqual(['VITE_API_BASE_URL='])
  })

  it('hardcodes no bearer token or credential in the source', () => {
    const hits = sourceFiles.filter((f) => /Bearer\s+[A-Za-z0-9_-]{16,}|sk-[A-Za-z0-9]{16,}|(password|passwd|apikey|api_key)\s*[:=]\s*['"][^'"]{8,}/i.test(stripComments(read(f))))
    expect(hits.map((f) => f.replace(root, ''))).toEqual([])
  })

  it('the production CSP blocks inline and remote scripts and only allows the tile host for images', () => {
    const config = read(join(root, 'vite.config.ts'))
    expect(config).toContain(`"script-src 'self'"`)
    expect(config).not.toMatch(/unsafe-eval/)
    expect(config).toContain("object-src 'none'")
    expect(config).toContain("base-uri 'self'")
    expect(config).toContain('https://tile.openstreetmap.org')
    expect(config).toMatch(/connect-src 'self'/)
    const scriptDirective = /"script-src ([^"]*)"/.exec(config)![1]
    expect(scriptDirective).toBe("'self'") // no 'unsafe-inline', no remote hosts
  })

  it('the HTML shell has no inline scripts', () => {
    const html = read(join(root, 'index.html'))
    const inline = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)].filter((m) => !/\bsrc=/.test(m[1]) || m[2].trim())
    expect(inline).toEqual([])
  })

  it('tokens are never written into URLs or logged', () => {
    const risky = sourceFiles.filter((f) => /console\.(log|info|debug)\([^)]*token/i.test(stripComments(read(f))) || /\?token=|&token=/.test(read(f)))
    expect(risky.map((f) => f.replace(root, ''))).toEqual([])
  })
})
