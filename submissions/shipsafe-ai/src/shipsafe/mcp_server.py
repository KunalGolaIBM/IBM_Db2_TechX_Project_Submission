"""IBM Bob Model Context Protocol (MCP) Server for ShipSafe AI."""

import json
import sys
import os
from typing import Dict, Any, List

from .discovery import ProjectDiscovery
from .reports import ReportGenerator
from .runtime import build_runtime


# Typed MCP tool definitions exposed to IBM Bob IDE
MCP_TOOLS = [
    {
        "name": "shipsafe_discover_project",
        "description": "Discover project languages, manifests, test suites, Git diff, and applicable release checks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_path": {
                    "type": "string",
                    "description": "Path to workspace repository root",
                    "default": "."
                }
            }
        }
    },
    {
        "name": "shipsafe_run_assessment",
        "description": "Run deterministic pre-PR production-readiness assessment, persist to IBM Db2, and evaluate release gate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace_root": {"type": "string", "default": "."},
                "profile": {"type": "string", "enum": ["quick", "pre-pr", "deep"], "default": "pre-pr"},
                "base_commit": {"type": "string", "description": "Optional Git base commit for diff scoping"}
            }
        }
    },
    {
        "name": "shipsafe_get_assessment",
        "description": "Retrieve full assessment details and gate status by Assessment ID from IBM Db2.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "assessment_id": {"type": "string", "description": "Unique assessment identifier"}
            },
            "required": ["assessment_id"]
        }
    },
    {
        "name": "shipsafe_get_finding",
        "description": "Retrieve normalized evidence, location, and remediation for a specific finding.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "finding_id": {"type": "string", "description": "Finding identifier"}
            },
            "required": ["finding_id"]
        }
    },
    {
        "name": "shipsafe_retrieve_guidance",
        "description": "Semantic search over engineering policies stored as vectors in IBM Db2 (langchain-db2).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Question or finding topic to search"},
                "category": {"type": "string", "description": "Optional policy category filter"}
            },
            "required": ["question"]
        }
    },
    {
        "name": "shipsafe_compare_assessments",
        "description": "Compare previous and current assessments to detect new, resolved, and regressed issues.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "previous_id": {"type": "string"},
                "current_id": {"type": "string"}
            },
            "required": ["previous_id", "current_id"]
        }
    },
    {
        "name": "shipsafe_export_report",
        "description": "Export Markdown or JSON production-readiness report for an assessment.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "assessment_id": {"type": "string"},
                "format": {"type": "string", "enum": ["markdown", "json"], "default": "markdown"}
            },
            "required": ["assessment_id"]
        }
    }
]


class ShipSafeMcpServer:
    """STDIO JSON-RPC 2.0 MCP server for IBM Bob and other MCP clients."""

    def __init__(self, runtime=None):
        self._runtime = runtime
        self._last_result = None

    @property
    def runtime(self):
        # Connect to Db2 lazily so `initialize` / `tools/list` answer instantly.
        if self._runtime is None:
            self._runtime = build_runtime()
        return self._runtime

    @property
    def repository(self):
        return self.runtime.repository

    def handle_call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch typed MCP tool calls."""
        if name == "shipsafe_discover_project":
            ws = arguments.get("workspace_path", ".")
            discovery = ProjectDiscovery(ws).discover()
            return {"content": [{"type": "text", "text": json.dumps(discovery.to_dict(), indent=2)}]}

        elif name == "shipsafe_run_assessment":
            ws = arguments.get("workspace_root", ".")
            profile = arguments.get("profile", "pre-pr")
            base = arguments.get("base_commit")
            result = self.runtime.orchestrator.run_assessment(ws, profile=profile, base_commit=base)
            self._last_result = result
            summary = {
                "assessment_id": result.assessment.assessment_id,
                "project_id": result.assessment.project_id,
                "status": result.gate.status.value,
                "gate_reason": result.gate.reason,
                "critical_count": result.assessment.critical_count,
                "high_count": result.assessment.high_count,
                "medium_count": result.assessment.medium_count,
                "findings_count": len(result.findings),
                "persisted_in_db2": result.persisted,
                "policies": [f"{p['doc_id']}: {p['title']}" for p in result.retrieved_policies],
            }
            return {"content": [{"type": "text", "text": json.dumps(summary, indent=2)}]}

        elif name == "shipsafe_get_assessment":
            asm_id = arguments["assessment_id"]
            asm = self.repository.get_assessment(asm_id)
            if not asm:
                return {"isError": True, "content": [{"type": "text", "text": f"Assessment '{asm_id}' not found in Db2."}]}
            findings = self.repository.get_findings(asm_id)
            tool_runs = self.repository.get_tool_runs(asm_id)
            return {"content": [{"type": "text", "text": json.dumps({"assessment": asm, "findings": findings, "tool_runs": tool_runs}, indent=2, default=str)}]}

        elif name == "shipsafe_get_finding":
            fnd = self.repository.get_finding(arguments["finding_id"])
            if not fnd:
                return {"isError": True, "content": [{"type": "text", "text": f"Finding '{arguments['finding_id']}' not found in Db2."}]}
            return {"content": [{"type": "text", "text": json.dumps(fnd, indent=2, default=str)}]}

        elif name == "shipsafe_retrieve_guidance":
            kb = self.runtime.knowledge_base
            if kb is None:
                return {"isError": True, "content": [{"type": "text", "text": "Policy search requires the IBM Db2 backend."}]}
            results = kb.retrieve(arguments["question"], top_k=3, category=arguments.get("category"))
            return {"content": [{"type": "text", "text": json.dumps(results, indent=2)}]}

        elif name == "shipsafe_compare_assessments":
            prev_id = arguments["previous_id"]
            curr_id = arguments["current_id"]
            diff = self.repository.compare_assessments(prev_id, curr_id)
            return {"content": [{"type": "text", "text": json.dumps(diff, indent=2, default=str)}]}

        elif name == "shipsafe_export_report":
            asm_id = arguments["assessment_id"]
            fmt = arguments.get("format", "markdown")
            asm = self.repository.get_assessment(asm_id)
            if not asm:
                return {"isError": True, "content": [{"type": "text", "text": f"Assessment '{asm_id}' not found in Db2."}]}
            if self._last_result and self._last_result.assessment.assessment_id == asm_id:
                if fmt == "markdown":
                    text = ReportGenerator.to_markdown(self._last_result)
                else:
                    text = ReportGenerator.to_json(self._last_result)
            else:
                findings = self.repository.get_findings(asm_id)
                text = json.dumps({"assessment": asm, "findings": findings}, indent=2, default=str)
            return {"content": [{"type": "text", "text": text}]}

        else:
            return {"isError": True, "content": [{"type": "text", "text": f"Unknown tool: {name}"}]}

    def run_stdio(self) -> None:
        """Standard JSON-RPC 2.0 loop reading from stdin and writing to stdout."""
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                req = json.loads(line)
                method = req.get("method")
                req_id = req.get("id")
                if "id" not in req:
                    continue  # JSON-RPC notification (e.g. notifications/initialized): no response

                if method == "initialize":
                    res = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "serverInfo": {"name": "shipsafe", "version": "1.1.0"},
                            "capabilities": {"tools": {}}
                        }
                    }
                elif method == "tools/list":
                    res = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"tools": MCP_TOOLS}
                    }
                elif method == "tools/call":
                    params = req.get("params", {})
                    tool_name = params.get("name")
                    arguments = params.get("arguments", {})
                    tool_res = self.handle_call_tool(tool_name, arguments)
                    res = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": tool_res
                    }
                else:
                    res = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"}
                    }

                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()
            except Exception as e:
                err_res = {
                    "jsonrpc": "2.0",
                    "id": req.get("id") if "req" in locals() and isinstance(req, dict) else None,
                    "error": {"code": -32603, "message": str(e)}
                }
                sys.stdout.write(json.dumps(err_res) + "\n")
                sys.stdout.flush()


def main():
    server = ShipSafeMcpServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
