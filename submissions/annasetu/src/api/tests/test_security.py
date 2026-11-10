import unittest

from api.app.security import password_hash, password_matches


class SecurityTests(unittest.TestCase):
    def test_password_hash_is_salted_and_verifies(self):
        first = password_hash("correct horse battery staple")
        second = password_hash("correct horse battery staple")
        self.assertNotEqual(first, second)
        self.assertTrue(password_matches("correct horse battery staple", first))
        self.assertFalse(password_matches("wrong password", first))

    def test_malformed_password_hash_fails_closed(self):
        self.assertFalse(password_matches("anything", "not-a-valid-hash"))
