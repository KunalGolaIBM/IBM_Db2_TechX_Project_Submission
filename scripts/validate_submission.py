#!/usr/bin/env python3
"""
Submission Validator for IBM Db2 TechX Summit 2026.
Checks submission folder structure, required files, metadata JSON, and secret prevention.
Zero external dependencies (uses standard library only).
"""

import sys
import os
import re
import json
from pathlib import Path

SLUG_REGEX = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FORBIDDEN_FILES = [".env", ".env.local", ".env.development", ".env.production", "id_rsa", "id_ed25519"]
FORBIDDEN_EXTENSIONS = [".pem", ".pfx", ".p12", ".key"]

REQUIRED_FILES = [
    "README.md",
    "architecture.md",
    "submission.json",
    ".env.example"
]

def check_directory(dir_path: Path) -> list:
    errors = []
    slug = dir_path.name

    if slug == "_template":
        # Skip template folder from strict participant validation
        return []

    # 1. Slug format check
    if not SLUG_REGEX.match(slug):
        errors.append(f"Invalid folder name '{slug}'. Must be lowercase kebab-case (e.g., 'my-db2-project').")

    # 2. Required files check
    for req_file in REQUIRED_FILES:
        target = dir_path / req_file
        if not target.is_file():
            errors.append(f"Missing required file: '{req_file}' in {dir_path.as_posix()}")
        elif target.stat().st_size < 20:
            errors.append(f"File '{req_file}' is empty or too short.")

    # 3. Secret and unwanted files check
    for root, _, files in os.walk(dir_path):
        for file in files:
            file_lower = file.lower()
            if file_lower in FORBIDDEN_FILES or any(file_lower.endswith(ext) for ext in FORBIDDEN_EXTENSIONS):
                rel_file = Path(root, file).relative_to(dir_path)
                errors.append(f"POTENTIAL SECRET / UNWANTED FILE COMMITTED: '{rel_file.as_posix()}'. Remove this file immediately.")

    # 4. submission.json validation
    sub_json = dir_path / "submission.json"
    if sub_json.is_file():
        try:
            with open(sub_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                errors.append("submission.json root must be a JSON object.")
            else:
                project = data.get("project", {})
                team = data.get("team", {})
                db2 = data.get("ibm_db2", {})

                if not project.get("title") or project.get("title") == "Project Title Here":
                    errors.append("submission.json: 'project.title' is missing or unchanged from template.")
                if not project.get("slug"):
                    errors.append("submission.json: 'project.slug' is missing.")
                elif project.get("slug") != slug:
                    errors.append(f"submission.json: 'project.slug' ('{project.get('slug')}') does not match directory name ('{slug}').")

                if not team.get("name") or team.get("name") == "Team Name Here":
                    errors.append("submission.json: 'team.name' is missing or unchanged from template.")
                if not isinstance(team.get("members"), list) or len(team.get("members")) == 0:
                    errors.append("submission.json: 'team.members' must contain at least one member.")

                if not db2.get("edition"):
                    errors.append("submission.json: 'ibm_db2.edition' is required.")
                if not db2.get("connector"):
                    errors.append("submission.json: 'ibm_db2.connector' is required.")

        except json.JSONDecodeError as e:
            errors.append(f"submission.json contains invalid JSON: {e}")
        except Exception as e:
            errors.append(f"Error reading submission.json: {e}")

    return errors

def main():
    root_dir = Path(__file__).resolve().parent.parent
    submissions_dir = root_dir / "submissions"

    if not submissions_dir.is_dir():
        print(f"Error: submissions directory not found at {submissions_dir}")
        sys.exit(1)

    target_paths = []

    if len(sys.argv) > 1:
        # User specified explicit path(s)
        for arg in sys.argv[1:]:
            p = Path(arg).resolve()
            if p.is_dir():
                target_paths.append(p)
    else:
        # Check all submission subdirectories
        for item in submissions_dir.iterdir():
            if item.is_dir() and item.name != "_template":
                target_paths.append(item)

    if not target_paths:
        print("No submission directories found to validate. If testing, run against a target folder:")
        print("  python scripts/validate_submission.py submissions/<project-slug>")
        sys.exit(0)

    total_errors = 0
    print(f"Validating {len(target_paths)} submission folder(s)...")

    for target in target_paths:
        print(f"\nChecking: {target.relative_to(root_dir).as_posix()}")
        errors = check_directory(target)
        if errors:
            total_errors += len(errors)
            print(f"  [FAIL] with {len(errors)} error(s):")
            for err in errors:
                print(f"    - {err}")
        else:
            print("  [PASS] all validation checks.")

    print("\n" + "=" * 50)
    if total_errors > 0:
        print(f"VALIDATION FAILED: {total_errors} total error(s) found.")
        sys.exit(1)
    else:
        print("ALL VALIDATION CHECKS PASSED.")
        sys.exit(0)

if __name__ == "__main__":
    main()
