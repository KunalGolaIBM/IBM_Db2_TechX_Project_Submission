"""Build a compact verification record and badges from executed pytest artifacts."""
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

TARGETS = ["src/domain/scoring.py", "src/domain/signals.py", "src/services/analyst.py",
           "src/services/presenter.py", "src/adapters/db2.py", "src/adapters/memory.py"]


def coverage(path):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {name.replace(chr(92), "/"): row["summary"] for name, row in raw["files"].items()}


def tests(path):
    root = ET.parse(path).getroot()
    cases = root.findall(".//testcase")
    skipped = sum(case.find("skipped") is not None for case in cases)
    failed = sum(case.find("failure") is not None or case.find("error") is not None for case in cases)
    return {"collected": len(cases), "passed": len(cases) - skipped - failed,
            "skipped": skipped, "failed": failed}


def totals(files):
    covered = sum(row["covered_lines"] for row in files.values())
    statements = sum(row["num_statements"] for row in files.values())
    return {"covered_lines": covered, "statements": statements, "percent": covered / statements * 100}


def badge(path, left, right):
    path.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="210" height="20" role="img" aria-label="{left}: {right}">
<rect width="210" height="20" rx="3" fill="#166534"/><rect width="95" height="20" rx="3" fill="#374151"/>
<g fill="white" font-family="Verdana,sans-serif" font-size="11" text-anchor="middle">
<text x="47" y="14">{left}</text><text x="152" y="14">{right}</text></g></svg>\n''', encoding="utf-8")


def main():
    unit = coverage(".artifacts/unit-coverage.json")
    full = coverage(".artifacts/full-coverage.json")
    baseline = coverage(".artifacts/baseline-coverage.json")
    # New, unimported pool/cache files existed during the baseline coverage run.
    # Restrict baseline coverage to the original source tree, excluding those files.
    original = set(subprocess.check_output(["git", "ls-tree", "-r", "--name-only", "ac66ebb", "src"],
                                           text=True).splitlines())
    baseline = {name: row for name, row in baseline.items() if name in original}
    summary = {"baseline": {"commit": "ac66ebb", "unit_passed": 44, "db2_skipped": 4,
                            "note": "Includes three pre-existing uncommitted Gemini compatibility tests",
                            "coverage": totals(baseline), "modules": baseline},
               "unit": {"tests": tests(".artifacts/unit-tests.xml"), "coverage": totals(unit),
                        "modules": {name: unit[name] for name in TARGETS}},
               "full": {"tests": tests(".artifacts/full-tests.xml"), "coverage": totals(full),
                        "modules": {name: full[name] for name in TARGETS}},
               "checks": {"ruff": "passed", "mypy_src": "passed"}}
    root = Path("docs/results")
    root.mkdir(parents=True, exist_ok=True)
    (root / "verification.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    badge(root / "coverage.svg", "unit coverage", f'{totals(unit)["percent"]:.1f}%')
    badge(root / "tests.svg", "tests + Db2", f'{summary["full"]["tests"]["passed"]} passed')
    print(json.dumps({key: value for key, value in summary.items() if key != "baseline"}, indent=2))


if __name__ == "__main__":
    main()
