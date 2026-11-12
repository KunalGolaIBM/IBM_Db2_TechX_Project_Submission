import os
import unittest
from pathlib import Path
from shipsafe.discovery import ProjectDiscovery


class TestProjectDiscovery(unittest.TestCase):
    def setUp(self):
        self.fixtures_dir = Path(__file__).parent.parent / "fixtures"

    def test_clean_project_discovery(self):
        clean_path = str(self.fixtures_dir / "clean_project")
        discovery = ProjectDiscovery(clean_path).discover()

        self.assertIn("python", discovery.languages)
        self.assertIn("pyproject.toml", [Path(m).name for m in discovery.manifests])
        self.assertIn("sast_bandit", discovery.applicable_checks)
        self.assertIn("secrets", discovery.applicable_checks)
        self.assertTrue(len(discovery.project_id) > 5)

    def test_nonexistent_workspace_raises(self):
        with self.assertRaises(ValueError):
            ProjectDiscovery("/path/that/does/not/exist/at/all").discover()


if __name__ == "__main__":
    unittest.main()
