import json
import unittest
from shipsafe.mcp_server import ShipSafeMcpServer, MCP_TOOLS


class TestMcpServer(unittest.TestCase):
    def setUp(self):
        self.server = ShipSafeMcpServer()

    def test_tools_list_spec(self):
        tool_names = [t["name"] for t in MCP_TOOLS]
        self.assertIn("shipsafe_discover_project", tool_names)
        self.assertIn("shipsafe_run_assessment", tool_names)
        self.assertIn("shipsafe_get_assessment", tool_names)
        self.assertIn("shipsafe_retrieve_guidance", tool_names)
        self.assertIn("shipsafe_compare_assessments", tool_names)
        self.assertIn("shipsafe_export_report", tool_names)

    def test_call_discover_tool(self):
        res = self.server.handle_call_tool("shipsafe_discover_project", {"workspace_path": "."})
        self.assertIn("content", res)
        data = json.loads(res["content"][0]["text"])
        self.assertIn("languages", data)


if __name__ == "__main__":
    unittest.main()
