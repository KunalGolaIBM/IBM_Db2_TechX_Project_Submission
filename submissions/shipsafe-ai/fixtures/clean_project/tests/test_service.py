import unittest
from src.service import calculate_tax


class TestCleanService(unittest.TestCase):
    def test_calculate_tax_standard(self):
        self.assertEqual(calculate_tax(100.0, 0.08), 8.0)

    def test_calculate_tax_negative_raises(self):
        with self.assertRaises(ValueError):
            calculate_tax(-10.0)


if __name__ == "__main__":
    unittest.main()
