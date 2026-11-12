"""Scan-target allowlisting.

The API never scans an arbitrary path supplied by a client. Targets must
resolve (after symlinks and `..`) to a directory inside one of the configured
allowed roots (SHIPSAFE_ALLOWED_ROOTS).
"""

from pathlib import Path
from typing import Dict, List


class TargetNotAllowed(PermissionError):
    pass


PROJECT_MARKERS = ("pyproject.toml", "requirements.txt", "setup.py", "package.json", "go.mod", "pom.xml", ".git")


def resolve_target(target: str, allowed_roots: List[str]) -> Path:
    if not target or "\x00" in target:
        raise TargetNotAllowed("Empty or invalid target path")
    roots = [Path(r).resolve() for r in allowed_roots if r]
    candidate = Path(target)
    tries = [candidate] if candidate.is_absolute() else [root / candidate for root in roots]
    for path in tries:
        resolved = path.resolve()
        for root in roots:
            try:
                resolved.relative_to(root)
            except ValueError:
                continue
            if resolved.is_dir():
                return resolved
    raise TargetNotAllowed(f"Target '{target}' is not a directory inside an allowed workspace root")


def list_workspaces(allowed_roots: List[str], max_depth: int = 2) -> List[Dict[str, str]]:
    """Discover scannable project folders under the allowed roots (for the UI picker)."""
    found: Dict[str, Dict[str, str]] = {}
    for root_str in allowed_roots:
        root = Path(root_str).resolve()
        if not root.is_dir():
            continue
        stack = [(root, 0)]
        while stack:
            path, depth = stack.pop()
            if any((path / m).exists() for m in PROJECT_MARKERS):
                found[str(path)] = {"name": path.name, "path": str(path), "root": str(root)}
                continue
            if depth < max_depth:
                for child in sorted(path.iterdir(), reverse=True):
                    if child.is_dir() and not child.name.startswith((".", "__")) and child.name not in ("node_modules", "venv"):
                        stack.append((child, depth + 1))
    return sorted(found.values(), key=lambda w: w["name"].lower())
