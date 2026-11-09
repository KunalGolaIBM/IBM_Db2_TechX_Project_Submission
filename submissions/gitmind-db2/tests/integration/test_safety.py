"""
Integration tests for Git Safety and Destructive Operation Guardrails
"""

import unittest
from tools.git_tools import run_safe_git_command


class TestGitSafety(unittest.TestCase):

    def test_destructive_commands_blocked_by_default(self):
        """
        Verify that destructive git operations (hard reset, force push, branch deletion)
        are blocked by the safe runner without approval.
        """
        destructive_commands = [
            "git push --force",
            "git push -f origin main",
            "git reset --hard HEAD~1",
            "git branch -D feature",
            "git clean -fd",
        ]

        for cmd in destructive_commands:
            result = run_safe_git_command.invoke({"command": cmd, "repo_path": "."})
            self.assertTrue(
                "destructive" in result.lower() or "blocked" in result.lower() or "not allowed" in result.lower(),
                f"Expected command '{cmd}' to be blocked, but got: {result}",
            )


if __name__ == "__main__":
    unittest.main()

