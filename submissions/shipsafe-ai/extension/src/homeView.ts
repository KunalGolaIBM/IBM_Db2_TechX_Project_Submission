import * as vscode from "vscode";
import { mascotSvg, Mood } from "./mascot";

export interface HealthItem {
  id: "engine" | "granite" | "db2" | "agent";
  label: string;
  state: "ok" | "missing" | "working" | "unknown";
  detail: string;
  optional: boolean;
  action?: { label: string; command: string };
}

export interface FileCard {
  name: string;
  verdict: "clean" | "warn" | "block";
  summary: string;
  issues: { line: number; severity: string; title: string; rule: string }[];
}

export interface HomeState {
  mascot: boolean;
  mood: Mood;
  say: string;
  health: HealthItem[];
  file?: FileCard;
  stats: { checks: number; blocked: number; fixed: number };
  agents: { name: string; checks: number; blocked: number; fixed: number }[] | null;
  canAskBob: boolean;
  toggles: { key: string; label: string; value: boolean }[];
  agentName: string;
}

/** The ShipSafe home panel in the activity bar: Shippy, setup checklist, current file, actions, settings. */
export class HomeViewProvider implements vscode.WebviewViewProvider {
  static readonly id = "shipsafe.home";
  private view?: vscode.WebviewView;

  constructor(private readonly getState: () => HomeState,
              private readonly onToggle: (key: string, value: boolean) => Thenable<void>) {}

  resolveWebviewView(view: vscode.WebviewView): void {
    this.view = view;
    view.webview.options = { enableScripts: true, enableCommandUris: false };
    view.webview.html = this.html(view.webview);
    view.webview.onDidReceiveMessage((msg: { type: string; command?: string; args?: unknown[]; key?: string; value?: boolean }) => {
      if (msg.type === "ready") {
        this.refresh();
      } else if (msg.type === "run" && msg.command?.startsWith("shipsafe.")) {
        void vscode.commands.executeCommand(msg.command!, ...(msg.args || []));
      } else if (msg.type === "toggle" && msg.key) {
        void this.onToggle(msg.key, !!msg.value);
      }
    });
    view.onDidChangeVisibility(() => view.visible && this.refresh());
  }

  refresh(): void {
    void this.view?.webview.postMessage({ type: "state", state: this.getState() });
  }

  private html(webview: vscode.Webview): string {
    const nonce = [...Array(24)].map(() => Math.random().toString(36)[2]).join("");
    const moods: Mood[] = ["happy", "alert", "thinking", "celebrate", "sleepy"];
    const svgs = Object.fromEntries(moods.map((m) => [m, mascotSvg(m, 76)]));
    return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; img-src ${webview.cspSource} data:; script-src 'nonce-${nonce}';">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
:root{--gold:#F2C94C;--blue:#3B6CFF;--red:#E5484D;--green:#2FB67C;--amber:#E8A33D}
body{padding:0 12px 16px;color:var(--vscode-foreground);font-family:var(--vscode-font-family);font-size:var(--vscode-font-size)}
.hero{display:flex;gap:10px;align-items:flex-end;margin:12px 0 6px}
.hero svg{flex:0 0 auto}
.bubble{position:relative;background:var(--vscode-editorWidget-background);border:1px solid var(--vscode-widget-border,rgba(128,128,128,.35));
 border-radius:10px;padding:8px 10px;line-height:1.4;margin-bottom:26px}
.bubble:after{content:"";position:absolute;left:-7px;bottom:12px;width:12px;height:12px;background:inherit;border-left:inherit;border-bottom:inherit;transform:rotate(45deg)}
.bubble b{color:var(--gold)}
h3{font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.75;margin:16px 0 6px;font-weight:600}
.card{border:1px solid var(--vscode-widget-border,rgba(128,128,128,.3));border-radius:8px;padding:8px 10px;margin-bottom:8px;background:var(--vscode-sideBar-background)}
.row{display:flex;align-items:center;gap:8px;padding:5px 0}
.row+.row{border-top:1px solid var(--vscode-widget-border,rgba(128,128,128,.15))}
.dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto;background:var(--vscode-descriptionForeground)}
.ok .dot{background:var(--green)} .missing .dot{background:var(--amber)} .working .dot{background:var(--blue);animation:pulse 1s infinite}
@keyframes pulse{50%{opacity:.3}}
.grow{flex:1;min-width:0}
.label{font-weight:600}
.detail{opacity:.75;font-size:.92em;overflow-wrap:anywhere}
.opt{font-size:.8em;opacity:.6;margin-left:4px;font-weight:400}
button{font:inherit;border:none;border-radius:4px;padding:4px 10px;cursor:pointer;color:var(--vscode-button-foreground);background:var(--vscode-button-background);white-space:nowrap}
button:hover{background:var(--vscode-button-hoverBackground)}
button.ghost{background:var(--vscode-button-secondaryBackground);color:var(--vscode-button-secondaryForeground)}
button.ghost:hover{background:var(--vscode-button-secondaryHoverBackground)}
.pill{display:inline-block;font-size:.78em;font-weight:700;letter-spacing:.06em;padding:2px 8px;border-radius:99px;color:#111}
.pill.block{background:var(--red);color:#fff}.pill.warn{background:var(--amber)}.pill.clean{background:var(--green);color:#fff}
.file-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:4px}
.fname{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.issue{display:flex;gap:6px;font-size:.92em;padding:3px 0;cursor:pointer}
.issue:hover{color:var(--vscode-textLink-foreground)}
.sev{font-size:.75em;font-weight:700;text-transform:uppercase;min-width:52px;opacity:.85}
.sev.critical,.sev.high{color:var(--red)} .sev.medium{color:var(--amber)}
.actions{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.actions button{width:100%;text-align:left;padding:7px 8px;white-space:normal}
.stats{display:flex;gap:6px}
.stat{flex:1;text-align:center;border-radius:8px;padding:6px 2px;background:var(--vscode-editorWidget-background)}
.stat b{display:block;font-size:1.5em;color:var(--gold)}
.toggle{display:flex;align-items:center;justify-content:space-between;padding:4px 0;gap:8px}
.switch{position:relative;width:30px;height:16px;flex:0 0 auto}
.switch input{opacity:0;width:0;height:0}
.slider{position:absolute;inset:0;border-radius:99px;background:var(--vscode-input-background);border:1px solid var(--vscode-widget-border,rgba(128,128,128,.4));cursor:pointer}
.slider:before{content:"";position:absolute;width:10px;height:10px;left:2px;top:2px;border-radius:50%;background:var(--vscode-foreground);transition:.15s}
.switch input:checked+.slider{background:var(--blue);border-color:var(--blue)}
.switch input:checked+.slider:before{transform:translateX(14px);background:#fff}
.btns{display:flex;gap:6px;margin-top:6px;flex-wrap:wrap}
a{color:var(--vscode-textLink-foreground)}
.muted{opacity:.7}
</style></head><body>
<div class="hero"><div id="mascot"></div><div class="bubble" id="say">Hi, I'm <b>Shippy</b>.</div></div>
<h3>Setup</h3><div class="card" id="health"></div>
<h3>This file</h3><div class="card" id="file"></div>
<h3>Do something</h3>
<div class="actions">
 <button class="ghost" data-run="shipsafe.askBob" id="ask-bob">Ask Bob (guarded)</button>
 <button class="ghost" data-run="shipsafe.checkWorkspace">Check workspace</button>
 <button class="ghost" data-run="shipsafe.checkSql">Check SQL on Db2</button>
 <button class="ghost" data-run="shipsafe.askStandards">Ask team standards</button>
 <button class="ghost" data-run="shipsafe.readiness">Readiness check</button>
 <button class="ghost" data-run="shipsafe.remember">Remember decision</button>
 <button class="ghost" data-run="shipsafe.recall">Recall decisions</button>
 <button class="ghost" data-run="shipsafe.tryDemo">Try it on a demo file</button>
 <button class="ghost" data-run="shipsafe.sessionReport">What was caught</button>
</div>
<h3>AI agents, guarded <span class="muted" style="text-transform:none;letter-spacing:0">(last 24 h, from IBM Db2)</span></h3>
<div class="card" id="agents"></div>
<h3>Today</h3>
<div class="stats"><div class="stat"><b id="s-checks">0</b>checks</div><div class="stat"><b id="s-blocked">0</b>blocked</div><div class="stat"><b id="s-fixed">0</b>fixed</div></div>
<h3>Make it yours</h3><div class="card" id="toggles"></div>
<div class="btns"><button class="ghost" data-run="shipsafe.openSettings">All settings</button><button class="ghost" data-run="shipsafe.walkthrough">Guided tour</button></div>
<script nonce="${nonce}">
const vscode = acquireVsCodeApi();
const SVG = ${JSON.stringify(svgs)};
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-run]");
  if (b) { vscode.postMessage({ type: "run", command: b.dataset.run, args: b.dataset.args ? JSON.parse(b.dataset.args) : [] }); }
});
document.addEventListener("change", (e) => {
  if (e.target.dataset.key) { vscode.postMessage({ type: "toggle", key: e.target.dataset.key, value: e.target.checked }); }
});
window.addEventListener("message", ({ data }) => {
  if (data.type !== "state") return;
  const s = data.state;
  document.getElementById("mascot").innerHTML = s.mascot ? SVG[s.mood] : "";
  document.getElementById("say").innerHTML = s.say;
  document.getElementById("health").innerHTML = s.health.map((h) =>
    '<div class="row ' + h.state + '"><span class="dot"></span><div class="grow"><div class="label">' + esc(h.label) +
    (h.optional ? '<span class="opt">optional</span>' : '') + '</div><div class="detail">' + esc(h.detail) + '</div></div>' +
    (h.action ? '<button data-run="' + esc(h.action.command) + '">' + esc(h.action.label) + '</button>' : '') + '</div>').join("");
  const f = s.file;
  document.getElementById("file").innerHTML = !f ? '<div class="muted">Open a Python, JavaScript or TypeScript file and save it; ShipSafe checks it in under a second.</div>' :
    '<div class="file-head"><span class="fname">' + esc(f.name) + '</span><span class="pill ' + f.verdict + '">' + f.verdict.toUpperCase() + '</span></div>' +
    '<div class="detail">' + esc(f.summary) + '</div>' +
    f.issues.slice(0, 6).map((i) => '<div class="issue" data-run="shipsafe.revealLine" data-args="[' + i.line + ']"><span class="sev ' + i.severity + '">' + i.severity +
      '</span><span>L' + i.line + ' ' + esc(i.title) + '</span></div>').join("") +
    '<div class="btns"><button data-run="shipsafe.checkFile">Check again</button>' + (f.issues.length ? '<button data-run="shipsafe.fixFile">Fix with Granite</button>' : '') + '</div>';
  document.getElementById("s-checks").textContent = s.stats.checks;
  document.getElementById("s-blocked").textContent = s.stats.blocked;
  document.getElementById("s-fixed").textContent = s.stats.fixed;
  document.getElementById("ask-bob").style.display = s.canAskBob ? "" : "none";
  document.getElementById("agents").innerHTML = s.agents === null
    ? '<div class="muted">Connect IBM Db2 to see what every AI agent was stopped from writing.</div>'
    : (s.agents.length ? '<table style="width:100%;border-collapse:collapse;font-size:.92em"><tr class="muted"><td>Who asked</td><td style="text-align:right">checks</td><td style="text-align:right">blocked</td><td style="text-align:right">fixed</td></tr>' +
        s.agents.map((a) => '<tr><td>' + esc(a.name) + '</td><td style="text-align:right">' + a.checks + '</td><td style="text-align:right;color:var(--red)">' + a.blocked +
          '</td><td style="text-align:right;color:var(--green)">' + a.fixed + '</td></tr>').join("") + '</table>'
      : '<div class="muted">No checks yet today.</div>') +
    '<div class="detail" style="margin-top:6px">Bob, Copilot or Claude Code call ShipSafe before writing. Anything an agent saves without asking is still checked by Shippy.</div>';
  document.getElementById("toggles").innerHTML = s.toggles.map((t) => '<label class="toggle"><span>' + esc(t.label) +
    '</span><span class="switch"><input type="checkbox" data-key="' + esc(t.key) + '"' + (t.value ? ' checked' : '') + '><span class="slider"></span></span></label>').join("");
});
vscode.postMessage({ type: "ready" });
</script></body></html>`;
  }
}
