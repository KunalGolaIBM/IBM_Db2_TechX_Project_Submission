import unittest
from pathlib import Path
from shipsafe.orchestration import AssessmentOrchestrator
from shipsafe.reports import ReportGenerator


class TestReportGenerator(unittest.TestCase):
    def test_markdown_and_json_reports(self):
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "clean_project"
        orch = AssessmentOrchestrator()
        result = orch.run_assessment(str(fixtures_dir), profile="quick", persist_to_db2=False)

        md = ReportGenerator.to_markdown(result)
        self.assertIn("# ShipSafe AI Production-Readiness Assessment Report", md)
        self.assertIn("Release Gate Status", md)
        self.assertIn("Limitations & Disclaimer", md)

        js = ReportGenerator.to_json(result)
        self.assertIn("assessment", js)
        self.assertIn("gate", js)


if __name__ == "__main__":
    unittest.main()
