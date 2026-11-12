"""Project and Git discovery service for ShipSafe AI."""

import os
import subprocess
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Any


EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    "dist", "build", ".pytest_cache", ".ruff_cache", ".mypy_cache"
}


@dataclass
class DiscoveryResult:
    """Structured result of project discovery."""
    workspace_root: str
    project_id: str
    repo_name: str
    git_detected: bool
    current_branch: Optional[str]
    head_commit: Optional[str]
    base_commit: Optional[str]
    changed_files: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    manifests: List[str] = field(default_factory=list)
    test_frameworks: List[str] = field(default_factory=list)
    has_docker: bool = False
    has_iac: bool = False
    applicable_checks: List[str] = field(default_factory=list)
    skipped_checks: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workspace_root": self.workspace_root,
            "project_id": self.project_id,
            "repo_name": self.repo_name,
            "git_detected": self.git_detected,
            "current_branch": self.current_branch,
            "head_commit": self.head_commit,
            "base_commit": self.base_commit,
            "changed_files": self.changed_files,
            "languages": self.languages,
            "manifests": self.manifests,
            "test_frameworks": self.test_frameworks,
            "has_docker": self.has_docker,
            "has_iac": self.has_iac,
            "applicable_checks": self.applicable_checks,
            "skipped_checks": self.skipped_checks,
            "warnings": self.warnings,
        }


class ProjectDiscovery:
    """Inspects a target workspace without modifying any files."""

    def __init__(self, workspace_root: str):
        self.workspace_root = str(Path(workspace_root).resolve())

    def discover(self) -> DiscoveryResult:
        root_path = Path(self.workspace_root)
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError(f"Workspace path does not exist or is not a directory: {self.workspace_root}")

        repo_name = root_path.name
        # Safe project identifier: hash of root path to avoid exposing absolute machine paths
        root_hash = hashlib.sha256(self.workspace_root.encode("utf-8")).hexdigest()[:12]
        project_id = f"prj_{repo_name.lower().replace(' ', '_')}_{root_hash}"

        git_detected = False
        current_branch = None
        head_commit = None
        base_commit = None
        changed_files: List[str] = []
        warnings: List[str] = []

        # 1. Git Discovery via safe subprocess
        git_dir = root_path / ".git"
        if git_dir.exists():
            git_detected = True
            try:
                # Get current branch
                res = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=self.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    stdin=subprocess.DEVNULL,
                )
                if res.returncode == 0:
                    current_branch = res.stdout.strip()

                # Get HEAD commit
                res = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    stdin=subprocess.DEVNULL,
                )
                if res.returncode == 0:
                    head_commit = res.stdout.strip()[:12]

                # Get uncommitted and staged changes
                res = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=self.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    stdin=subprocess.DEVNULL,
                )
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        parts = line.strip().split(maxsplit=1)
                        if len(parts) == 2:
                            changed_files.append(parts[1])
            except Exception as e:  # pragma: no cover - git binary missing or hung past its timeout
                warnings.append(f"Git inspection warning: {str(e)}")
        else:
            warnings.append("Workspace is not a Git repository. Scan will target all discoverable project files.")

        # 2. Languages & Manifests
        languages: Set[str] = set()
        manifests: List[str] = []
        test_frameworks: Set[str] = set()
        has_docker = False
        has_iac = False

        # Bounded scan
        for dirpath, dirnames, filenames in os.walk(self.workspace_root):
            # Prune excluded dirs in-place
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

            rel_dir = os.path.relpath(dirpath, self.workspace_root)

            for f in filenames:
                file_rel = os.path.normpath(os.path.join(rel_dir, f)) if rel_dir != "." else f
                f_lower = f.lower()

                # Manifests
                if f in ("pyproject.toml", "requirements.txt", "Pipfile", "setup.py"):
                    languages.add("python")
                    manifests.append(file_rel)
                elif f in ("package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
                    languages.add("typescript" if any(f.endswith(".ts") or f.endswith(".tsx") for f in filenames) else "javascript")
                    manifests.append(file_rel)
                elif f in ("go.mod", "go.sum"):
                    languages.add("go")
                    manifests.append(file_rel)
                elif f in ("pom.xml", "build.gradle"):
                    languages.add("java")
                    manifests.append(file_rel)

                # Tests
                if f.startswith("test_") or f.endswith("_test.py"):
                    languages.add("python")
                    test_frameworks.add("pytest/unittest")
                elif f.endswith(".spec.ts") or f.endswith(".test.tsx") or f.endswith(".test.js"):
                    test_frameworks.add("vitest/jest")

                # Containers & IaC
                if "dockerfile" in f_lower or f in ("docker-compose.yml", "docker-compose.yaml", "compose.yaml"):
                    has_docker = True
                if f.endswith(".tf") or f in ("k8s.yaml", "deployment.yaml") or "helm" in rel_dir.lower():
                    has_iac = True

                # File extension heuristic
                if f.endswith(".py"):
                    languages.add("python")
                elif f.endswith(".ts") or f.endswith(".tsx"):
                    languages.add("typescript")
                elif f.endswith(".js") or f.endswith(".jsx"):
                    languages.add("javascript")

        # 3. Applicable & Skipped Checks
        applicable_checks: List[str] = ["secrets"]  # Secrets always applicable
        skipped_checks: Dict[str, str] = {}

        if "python" in languages:
            applicable_checks.extend(["sast_bandit", "dependencies_pip_audit", "quality_ruff"])
            if "pytest/unittest" in test_frameworks:
                applicable_checks.append("tests_pytest")
            else:
                skipped_checks["tests_pytest"] = "No python test files matching 'test_*.py' detected"
        else:
            skipped_checks["sast_bandit"] = "Python language not detected in repository"
            skipped_checks["dependencies_pip_audit"] = "No Python requirements or pyproject.toml found"

        if has_docker or has_iac:
            applicable_checks.append("infrastructure_trivy")
        else:
            skipped_checks["infrastructure_trivy"] = "No Dockerfile, Compose, or IaC configuration detected"

        return DiscoveryResult(
            workspace_root=self.workspace_root,
            project_id=project_id,
            repo_name=repo_name,
            git_detected=git_detected,
            current_branch=current_branch,
            head_commit=head_commit,
            base_commit=base_commit,
            changed_files=changed_files,
            languages=sorted(list(languages)),
            manifests=manifests,
            test_frameworks=sorted(list(test_frameworks)),
            has_docker=has_docker,
            has_iac=has_iac,
            applicable_checks=applicable_checks,
            skipped_checks=skipped_checks,
            warnings=warnings,
        )
