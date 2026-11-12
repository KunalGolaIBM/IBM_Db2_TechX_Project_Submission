import * as path from "path";
import * as vscode from "vscode";
import { CheckResult, Issue } from "./format";

type Node = { kind: "file"; uri: vscode.Uri; result: CheckResult } | { kind: "issue"; uri: vscode.Uri; issue: Issue };

const ICON: Record<string, vscode.ThemeIcon> = {
  critical: new vscode.ThemeIcon("error", new vscode.ThemeColor("errorForeground")),
  high: new vscode.ThemeIcon("error", new vscode.ThemeColor("errorForeground")),
  medium: new vscode.ThemeIcon("warning", new vscode.ThemeColor("editorWarning.foreground")),
  low: new vscode.ThemeIcon("info", new vscode.ThemeColor("editorInfo.foreground")),
};

/** Findings per file, worst files first; clicking an issue jumps to its line. */
export class FindingsProvider implements vscode.TreeDataProvider<Node> {
  static readonly id = "shipsafe.findings";
  private readonly changed = new vscode.EventEmitter<void>();
  readonly onDidChangeTreeData = this.changed.event;

  constructor(private readonly results: Map<string, CheckResult>) {}

  refresh(): void {
    this.changed.fire();
  }

  getChildren(node?: Node): Node[] {
    if (!node) {
      const rank = { block: 0, warn: 1, clean: 2 } as const;
      return [...this.results.entries()]
        .filter(([, r]) => r.issues.length)
        .sort(([, a], [, b]) => rank[a.verdict] - rank[b.verdict] || b.issues.length - a.issues.length)
        .map(([key, result]) => ({ kind: "file" as const, uri: vscode.Uri.parse(key), result }));
    }
    return node.kind === "file" ? node.result.issues.map((issue) => ({ kind: "issue" as const, uri: node.uri, issue })) : [];
  }

  getTreeItem(node: Node): vscode.TreeItem {
    if (node.kind === "file") {
      const item = new vscode.TreeItem(path.basename(node.uri.fsPath), vscode.TreeItemCollapsibleState.Expanded);
      item.resourceUri = node.uri;
      item.description = `${node.result.verdict} · ${node.result.issues.length}`;
      item.iconPath = node.result.verdict === "block" ? ICON.high : ICON.medium;
      item.contextValue = "shipsafeFile";
      item.tooltip = node.result.summary;
      return item;
    }
    const i = node.issue;
    const item = new vscode.TreeItem(`L${i.line}  ${i.title}`, vscode.TreeItemCollapsibleState.None);
    item.description = i.rule_id;
    item.iconPath = ICON[i.severity] || ICON.low;
    const md = new vscode.MarkdownString(`**${i.title}** (${i.severity}, ${i.rule_id})\n\n${i.why}\n\n**Fix:** ${i.fix}`);
    if (i.policy) {
      md.appendMarkdown(`\n\n**Team policy ${i.policy.doc_id}:** ${i.policy.title}`);
    }
    item.tooltip = md;
    item.contextValue = "shipsafeIssue";
    item.command = { command: "vscode.open", title: "Open", arguments: [node.uri,
      { selection: new vscode.Range(Math.max(0, i.line - 1), 0, Math.max(0, i.line - 1), 0) }] };
    return item;
  }
}
