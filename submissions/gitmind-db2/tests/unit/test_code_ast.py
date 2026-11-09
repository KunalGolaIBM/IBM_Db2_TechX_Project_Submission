"""
Unit tests for Tree-sitter Code AST Extraction
"""

import unittest
from tools.code_tools import _detect_language, _extract_definitions


class TestCodeAST(unittest.TestCase):

    def test_detect_language(self):
        self.assertEqual(_detect_language("test.py"), "python")
        self.assertEqual(_detect_language("index.js"), "javascript")
        self.assertEqual(_detect_language("app.tsx"), "typescript")
        self.assertIsNone(_detect_language("data.csv"))

    def test_extract_python_functions(self):
        code = b"""
class AuthService:
    def authenticate(self, user, token):
        return True

def standalone_handler():
    pass
"""
        defs = _extract_definitions(code, "python")
        names = [d["name"] for d in defs]
        types = [d["type"] for d in defs]

        self.assertIn("AuthService", names)
        self.assertTrue(any("authenticate" in n for n in names))
        self.assertIn("standalone_handler", names)
        self.assertIn("class", types)
        self.assertIn("function", types)

    def test_extract_javascript_functions(self):
        code = b"""
class TokenManager {
    verify() { return true; }
}
function calculateHash(x) { return x; }
"""
        defs = _extract_definitions(code, "javascript")
        names = [d["name"] for d in defs]
        self.assertIn("TokenManager", names)
        self.assertIn("calculateHash", names)


if __name__ == "__main__":
    unittest.main()
