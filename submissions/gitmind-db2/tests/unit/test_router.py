"""
Unit tests for LangGraph Agent Types and Router Enums
"""

import unittest
from workflows.router import AgentType, RoutingDecision


class TestRouter(unittest.TestCase):

    def test_all_seven_agent_types_defined(self):
        expected = {"history", "recovery", "code", "github", "suggest", "docs", "project"}
        actual = {a.value for a in AgentType}
        self.assertEqual(expected, actual)

    def test_routing_decision_structure(self):
        decision = RoutingDecision(
            primary_agent=AgentType.HISTORY,
            secondary_agents=[AgentType.CODE, AgentType.GITHUB],
            reasoning="Query asks for commit history and function changes.",
            rewritten_query="Show commit evolution for auth function",
        )
        self.assertEqual(decision.primary_agent, AgentType.HISTORY)
        self.assertEqual(len(decision.secondary_agents), 2)
        self.assertIn(AgentType.CODE, decision.secondary_agents)


if __name__ == "__main__":
    unittest.main()

