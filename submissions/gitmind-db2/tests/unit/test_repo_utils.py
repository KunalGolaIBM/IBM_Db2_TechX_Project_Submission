"""
Unit tests for GitMind 2.0 Repository Identification and Utilities
"""

import unittest
from utils.repo_utils import (
    get_repo_id,
    get_repo_key,
    normalize_remote_url,
)


class TestRepoUtils(unittest.TestCase):

    def test_normalize_remote_url_https(self):
        url = "https://github.com/vastavikadi/gitmind.git"
        norm = normalize_remote_url(url)
        self.assertEqual(norm, "github.com/vastavikadi/gitmind")

    def test_normalize_remote_url_ssh(self):
        url = "git@github.com:vastavikadi/gitmind.git"
        norm = normalize_remote_url(url)
        self.assertEqual(norm, "github.com/vastavikadi/gitmind")

    def test_get_repo_id_deterministic(self):
        id1 = get_repo_id(".")
        id2 = get_repo_id(".")
        self.assertEqual(id1, id2)
        self.assertEqual(len(id1), 16)
        self.assertTrue(id1.isalnum())

    def test_get_repo_key(self):
        key = get_repo_key(".")
        self.assertIn("gitmind", key.lower())


if __name__ == "__main__":
    unittest.main()

