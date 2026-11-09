"""
GitMind — Core Git Tools

LangChain-compatible tools for inspecting git repository state,
history, branches, reflog, diffs, and more. These tools are shared
across all GitMind agents.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from git import Repo, InvalidGitRepositoryError, BadName
from langchain.tools import tool


def _get_repo(repo_path: str = ".") -> Repo:
    """Helper: open a git repo, raise clear error if invalid."""
    try:
        return Repo(Path(repo_path).resolve(), search_parent_directories=True)
    except InvalidGitRepositoryError:
        raise ValueError(f"'{repo_path}' is not inside a Git repository.")


#  STATUS & STATE

@tool
def get_repo_status(repo_path: str = ".") -> str:
    """
    Get the current status of the repository: current branch,
    staged/modified/untracked files, merge/rebase state, and conflicts.
    """
    repo = _get_repo(repo_path)

    git_dir = Path(repo.git_dir)
    is_merging = (git_dir / "MERGE_HEAD").exists()
    is_rebasing = (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()
    is_cherry_picking = (git_dir / "CHERRY_PICK_HEAD").exists()

    staged = [item.a_path for item in repo.index.diff("HEAD")] if not repo.head.is_detached and repo.head.is_valid() else []
    modified = [item.a_path for item in repo.index.diff(None)]
    untracked = repo.untracked_files
    conflicts = [item.a_path for item in repo.index.diff(None) if item.change_type == "U"] if is_merging else []

    branch = "HEAD (detached)" if repo.head.is_detached else repo.active_branch.name

    status = {
        "branch": branch,
        "is_detached": repo.head.is_detached,
        "staged_files": staged,
        "modified_files": modified,
        "untracked_files": untracked[:20],
        "conflicts": conflicts,
        "is_merging": is_merging,
        "is_rebasing": is_rebasing,
        "is_cherry_picking": is_cherry_picking,
    }
    return str(status)


@tool
def get_repo_stats(repo_path: str = ".") -> str:
    """
    Get aggregate statistics about the repository:
    total commits, branches, contributors, tags, and latest commit info.
    """
    repo = _get_repo(repo_path)
    commits = list(repo.iter_commits(max_count=1))

    stats = {
        "total_commits": int(repo.git.rev_list("--all", "--count")),
        "total_branches": len(list(repo.branches)),
        "total_tags": len(list(repo.tags)),
        "total_contributors": len(
            set(c.author.name for c in repo.iter_commits(max_count=500))
        ),
        "latest_commit": (
            {
                "hash": commits[0].hexsha[:8],
                "author": commits[0].author.name,
                "date": commits[0].committed_datetime.isoformat(),
                "message": commits[0].message.strip()[:120],
            }
            if commits
            else None
        ),
    }
    return str(stats)

#  COMMIT HISTORY

@tool
def get_commit_history(repo_path: str = ".", limit: int = 50, since_days: int = 0) -> str:
    """
    Get recent commit history. Optionally filter to commits within
    the last `since_days` days. Returns a list of commit objects with
    hash, author, date, and message.
    """
    repo = _get_repo(repo_path)
    since = datetime.now() - timedelta(days=since_days) if since_days > 0 else None

    commits = []
    for commit in repo.iter_commits(max_count=limit):
        commit_time = datetime.fromtimestamp(commit.committed_date)
        if since and commit_time < since:
            break
        commits.append({
            "hash": commit.hexsha[:8],
            "author": commit.author.name,
            "date": commit_time.isoformat(),
            "message": commit.message.strip()[:200],
        })
    return str(commits)


@tool
def get_commit_details(repo_path: str = ".", commit_hash: str = "HEAD") -> str:
    """
    Get full details of a specific commit: author, date, message,
    parent hashes, and list of changed files with change types.
    """
    repo = _get_repo(repo_path)
    try:
        commit = repo.commit(commit_hash)
    except BadName:
        return f"Error: Invalid commit reference '{commit_hash}'"

    # diff against parent
    if commit.parents:
        diffs = commit.diff(commit.parents[0])
    else:
        diffs = commit.diff(None)

    files = []
    for diff in diffs:
        files.append({
            "path": diff.b_path or diff.a_path,
            "change_type": diff.change_type,
            "old_path": diff.a_path if diff.renamed else None,
        })

    return str({
        "hash": commit.hexsha,
        "short_hash": commit.hexsha[:8],
        "author": commit.author.name,
        "author_email": commit.author.email,
        "date": commit.committed_datetime.isoformat(),
        "message": commit.message.strip(),
        "parents": [p.hexsha[:8] for p in commit.parents],
        "files_changed": files,
        "stats": {
            "total_files": len(files),
            "insertions": commit.stats.total.get("insertions", 0),
            "deletions": commit.stats.total.get("deletions", 0),
        },
    })


@tool
def get_commit_range(
    repo_path: str = ".",
    start_commit: str = "",
    end_commit: str = "HEAD",
) -> str:
    """
    Get all commits between two references (e.g., 'main..feature-branch').
    """
    repo = _get_repo(repo_path)
    commits = []
    for commit in repo.iter_commits(f"{start_commit}..{end_commit}"):
        commits.append({
            "hash": commit.hexsha[:8],
            "author": commit.author.name,
            "date": commit.committed_datetime.isoformat(),
            "message": commit.message.strip()[:200],
        })
    return str(commits)


@tool
def search_commits(repo_path: str = ".", query: str = "", limit: int = 50) -> str:
    """
    Search commit messages for a query string (case-insensitive).
    Returns matching commits.
    """
    repo = _get_repo(repo_path)
    results = []
    for commit in repo.iter_commits(max_count=limit * 3):
        if query.lower() in commit.message.lower():
            results.append({
                "hash": commit.hexsha[:8],
                "author": commit.author.name,
                "date": commit.committed_datetime.isoformat(),
                "message": commit.message.strip()[:200],
            })
            if len(results) >= limit:
                break
    return str(results)


#  FILE HISTORY & BLAME


@tool
def get_file_history(repo_path: str = ".", file_path: str = "", limit: int = 30) -> str:
    """
    Get the commit history for a specific file. Shows who changed it,
    when, and what the commit message was.
    """
    repo = _get_repo(repo_path)
    commits = []
    for commit in repo.iter_commits(paths=file_path, max_count=limit):
        commits.append({
            "hash": commit.hexsha[:8],
            "author": commit.author.name,
            "date": commit.committed_datetime.isoformat(),
            "message": commit.message.strip()[:200],
        })
    return str(commits)


@tool
def get_file_blame(repo_path: str = ".", file_path: str = "") -> str:
    """
    Run git blame on a file and return structured blame data:
    which commit and author last modified each line.
    """
    repo = _get_repo(repo_path)
    try:
        blame = repo.blame("HEAD", file_path)
    except Exception as e:
        return f"Error running blame on '{file_path}': {e}"

    result = []
    for commit, lines in blame:
        result.append({
            "commit": commit.hexsha[:8],
            "author": commit.author.name,
            "date": commit.committed_datetime.isoformat()[:10],
            "lines": len(lines),
            "message": commit.message.strip()[:80],
        })
    return str(result)


#  BRANCHES & TAGS

@tool
def get_branches_info(repo_path: str = ".") -> str:
    """
    Get all branches with tracking info, ahead/behind counts,
    and last commit date.
    """
    repo = _get_repo(repo_path)
    branches = []
    current = repo.active_branch.name if not repo.head.is_detached else None

    for branch in repo.branches:
        info = {
            "name": branch.name,
            "is_current": branch.name == current,
            "last_commit": branch.commit.hexsha[:8],
            "last_commit_date": branch.commit.committed_datetime.isoformat(),
            "last_commit_msg": branch.commit.message.strip()[:80],
        }

        # Tracking info
        if branch.tracking_branch():
            tracking = branch.tracking_branch()
            info["tracking"] = tracking.name
            try:
                ahead = len(list(repo.iter_commits(f"{tracking.name}..{branch.name}")))
                behind = len(list(repo.iter_commits(f"{branch.name}..{tracking.name}")))
                info["ahead"] = ahead
                info["behind"] = behind
            except Exception:
                info["ahead"] = 0
                info["behind"] = 0

        branches.append(info)

    return str(branches)


@tool
def get_tags(repo_path: str = ".") -> str:
    """
    Get all tags with their associated commit info.
    """
    repo = _get_repo(repo_path)
    tags = []
    for tag in repo.tags:
        tags.append({
            "name": tag.name,
            "commit": tag.commit.hexsha[:8],
            "date": tag.commit.committed_datetime.isoformat(),
            "message": tag.tag.message.strip()[:120] if tag.tag else "",
        })
    return str(tags)


@tool
def get_contributors(repo_path: str = ".", limit: int = 200) -> str:
    """
    Get a ranked list of contributors by commit count.
    """
    repo = _get_repo(repo_path)
    counts: dict[str, int] = {}
    for commit in repo.iter_commits(max_count=limit):
        name = commit.author.name
        counts[name] = counts.get(name, 0) + 1

    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return str([{"name": name, "commits": count} for name, count in ranked])


#  REFLOG & RECOVERY


@tool
def get_reflog(repo_path: str = ".", limit: int = 30) -> str:
    """
    Get the reflog — a record of all HEAD changes. Useful for
    recovering lost commits, finding deleted branches, and
    understanding recent actions.
    """
    repo = _get_repo(repo_path)
    try:
        output = repo.git.reflog(
            "--format=%H|%gd|%gs|%ci",
            f"-n{limit}",
        )
    except Exception as e:
        return f"Error reading reflog: {e}"

    entries = []
    for line in output.strip().splitlines():
        parts = line.split("|", 3)
        if len(parts) >= 3:
            entries.append({
                "hash": parts[0][:8],
                "ref": parts[1],
                "action": parts[2],
                "timestamp": parts[3] if len(parts) > 3 else "",
            })
    return str(entries)


@tool
def get_dangling_objects(repo_path: str = ".") -> str:
    """
    Run git fsck to find dangling commits, blobs, and trees.
    These are objects not reachable from any reference — potentially
    recoverable lost work.
    """
    repo = _get_repo(repo_path)
    try:
        output = repo.git.fsck("--lost-found", "--no-reflogs")
    except Exception:
        try:
            output = repo.git.fsck("--lost-found")
        except Exception as e:
            return f"Error running git fsck: {e}"

    objects = []
    for line in output.strip().splitlines():
        parts = line.strip().split()
        if len(parts) >= 3 and parts[0] == "dangling":
            objects.append({
                "type": parts[1],
                "hash": parts[2][:8],
                "full_hash": parts[2],
            })

    return str(objects)


@tool
def get_stash_list(repo_path: str = ".") -> str:
    """
    List all stash entries with their messages and branch context.
    """
    repo = _get_repo(repo_path)
    try:
        output = repo.git.stash("list", "--format=%gd|%gs|%H")
    except Exception:
        return "[]"

    entries = []
    for line in output.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("|", 2)
        if len(parts) >= 2:
            entries.append({
                "ref": parts[0],
                "message": parts[1],
                "hash": parts[2][:8] if len(parts) > 2 else "",
            })
    return str(entries)

#  DIFF & COMPARISON


@tool
def get_diff(repo_path: str = ".", ref1: str = "HEAD~1", ref2: str = "HEAD") -> str:
    """
    Get the diff between two references. Returns a summary of changes
    (not the full patch, to keep LLM context manageable).
    """
    repo = _get_repo(repo_path)
    try:
        diff_output = repo.git.diff("--stat", ref1, ref2)
        return diff_output
    except Exception as e:
        return f"Error computing diff: {e}"


@tool
def get_merge_base(repo_path: str = ".", branch1: str = "", branch2: str = "") -> str:
    """
    Find the merge base (common ancestor) of two branches.
    Useful for understanding when branches diverged.
    """
    repo = _get_repo(repo_path)
    try:
        output = repo.git.merge_base(branch1, branch2)
        commit = repo.commit(output.strip())
        return str({
            "merge_base_hash": commit.hexsha[:8],
            "author": commit.author.name,
            "date": commit.committed_datetime.isoformat(),
            "message": commit.message.strip()[:200],
        })
    except Exception as e:
        return f"Error finding merge base: {e}"


#  SAFETY & RISK DETECTION

@tool
def get_unpushed_commits(repo_path: str = ".") -> str:
    """
    Find commits on the current branch that haven't been pushed
    to the remote tracking branch.
    """
    repo = _get_repo(repo_path)
    if repo.head.is_detached:
        return "HEAD is detached — no tracking branch."

    branch = repo.active_branch
    tracking = branch.tracking_branch()
    if not tracking:
        return f"Branch '{branch.name}' has no remote tracking branch."

    unpushed = []
    for commit in repo.iter_commits(f"{tracking.name}..{branch.name}"):
        unpushed.append({
            "hash": commit.hexsha[:8],
            "message": commit.message.strip()[:120],
            "date": commit.committed_datetime.isoformat(),
        })

    return str({
        "branch": branch.name,
        "tracking": tracking.name,
        "unpushed_count": len(unpushed),
        "commits": unpushed,
    })


@tool
def detect_force_push_risk(repo_path: str = ".") -> str:
    """
    Detect if a force push would be dangerous: checks if the remote
    has commits that the local branch doesn't have (i.e., someone
    else pushed after our last fetch).
    """
    repo = _get_repo(repo_path)
    if repo.head.is_detached:
        return "HEAD is detached — cannot assess push risk."

    branch = repo.active_branch
    tracking = branch.tracking_branch()
    if not tracking:
        return f"No tracking branch for '{branch.name}'."

    try:
        remote_ahead = list(repo.iter_commits(f"{branch.name}..{tracking.name}"))
        local_ahead = list(repo.iter_commits(f"{tracking.name}..{branch.name}"))
    except Exception:
        return "Could not compare with remote. Try `git fetch` first."

    risk = {
        "branch": branch.name,
        "remote_has_new_commits": len(remote_ahead),
        "local_unpushed_commits": len(local_ahead),
        "force_push_dangerous": len(remote_ahead) > 0,
        "recommendation": (
            "SAFE: Remote has no new commits."
            if len(remote_ahead) == 0
            else f"DANGEROUS: Remote has {len(remote_ahead)} commit(s) you don't have. "
            "Use 'git push --force-with-lease' or fetch and rebase first."
        ),
    }
    return str(risk)

@tool
def run_safe_git_command(command: str) -> str:
    """
    Run a read-only git command. Only allows safe, non-destructive
    git subcommands: log, show, branch, tag, status, diff, blame,
    reflog, stash list, remote, config --list.
    """
    ALLOWED = {
        "log", "show", "branch", "tag", "status", "diff",
        "blame", "reflog", "stash", "remote", "config",
        "shortlog", "describe", "rev-list", "name-rev",
    }

    parts = command.strip().split()
    if not parts:
        return "Error: Empty command."

    # Strip leading 'git' if got included
    if parts[0] == "git":
        parts = parts[1:]

    if not parts or parts[0] not in ALLOWED:
        return f"Error: Command '{parts[0] if parts else ''}' is not allowed. Allowed: {', '.join(sorted(ALLOWED))}"

    # Guardrails against destructive subcommands & flags
    cmd_lower = [p.lower() for p in parts]
    if parts[0] == "branch" and (any(flag in parts for flag in ("-d", "-D", "--delete")) or any(flag in cmd_lower for flag in ("-d", "--delete"))):
        return "Error: Destructive git branch deletion is not allowed without explicit developer confirmation."
    if parts[0] == "stash" and any(action in cmd_lower for action in ("drop", "clear", "pop")):
        return "Error: Destructive git stash modification is not allowed without explicit developer confirmation."
    if parts[0] == "tag" and any(flag in cmd_lower for flag in ("-d", "--delete")):
        return "Error: Destructive git tag deletion is not allowed without explicit developer confirmation."

    try:
        result = subprocess.run(
            ["git"] + parts,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()
        if not output and result.stderr:
            return f"(stderr) {result.stderr.strip()}"

        if len(output) > 8000:
            return output[:8000] + "\n... (output truncated)"
        return output
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds."
    except Exception as e:
        return f"Error running command: {e}"


#  LEARN ABOUT THE PROJECT

@tool
def get_project_description(repo_path: str = ".") -> str:
    """
    Develops a high-level understanding of the repository by analyzing its
    documentation, metadata, structure, and supporting files.

    Scans for READMEs and documentation in `docs/` and project root.
    Examines package metadata (`package.json`, `pyproject.toml`, `go.mod`, etc.).
    Checks for build artifacts, configuration, and environment files.
    Extracts project scope, dependencies, and intended use cases.
    Returns a structured overview of the project's identity and purpose.
    """
    repo = _get_repo(repo_path)
    project_context = []
    
    #Root Files
    root_files = [
        "README.md", "README.rst", "README.txt",
        "SUMMARY.md", "PROJECT.md", "PROJECT.rst",
        "ABOUT.md", "ABOUT.rst", "ABOUT.txt"
    ]
    
    for file in root_files:
        path = Path(repo_path) / file
        if path.exists():
            content = path.read_text(errors='ignore')
            
            if len(content.strip()) > 10:
                project_context.append(f"--- {file} ---\n{content}")
    
    #Docs
    docs_path = Path(repo_path) / "docs"
    
    docs = []
    if docs_path.exists():
        for file in docs_path.iterdir():
            if file.is_file() and file.name.lower().endswith(('.md', '.txt', '.rst')):
                docs.append(f"--- {file.name} ---\n{file.read_text(errors='ignore')}")
    
    if docs:
        project_context.append("\n".join(docs))
    
    #Package Managers
    package_info = []
    
    # Python
    if (Path(repo_path) / "pyproject.toml").exists():
        with open(Path(repo_path) / "pyproject.toml", "r", encoding="utf-8") as f:
            package_info.append("--- pyproject.toml ---\n" + f.read())
    if (Path(repo_path) / "setup.py").exists():
        with open(Path(repo_path) / "setup.py", "r", encoding="utf-8") as f:
            package_info.append("--- setup.py ---\n" + f.read())
    
    # JavaScript/TypeScript
    if (Path(repo_path) / "package.json").exists():
        with open(Path(repo_path) / "package.json", "r", encoding="utf-8") as f:
            package_info.append("--- package.json ---\n" + f.read())
    
    # Go
    if (Path(repo_path) / "go.mod").exists():
        with open(Path(repo_path) / "go.mod", "r", encoding="utf-8") as f:
            package_info.append("--- go.mod ---\n" + f.read())
    
    # Rust
    if (Path(repo_path) / "Cargo.toml").exists():
        with open(Path(repo_path) / "Cargo.toml", "r", encoding="utf-8") as f:
            package_info.append("--- Cargo.toml ---\n" + f.read())
    
    if package_info:
        project_context.append("\n\n" + "\n\n".join(package_info))
    
    # 4. branch info
    branch_info = ""
    try:
        branch = repo.active_branch.name
        branch_info = f"\nCurrent Branch: {branch}"
    except Exception:
        pass
    
    #Combining Information
    full_context = "".join(project_context) + branch_info
    
    #basic metadata
    try:
        total_files = int(repo.git.execute(["git", "ls-files"]).count("\n")) + 1
    except Exception:
        total_files = "unknown"

    metadata = {
        "repo_path": str(Path(repo_path).resolve()),
        "branch": branch if branch_info else "N/A",
        "total_files": total_files,
    }

    return f"**Project Description:**\n{full_context}\n\n**Metadata:**\n{str(metadata)}"

#  TOOL REGISTRY

ALL_GIT_TOOLS = [
    #Status & state
    get_repo_status,
    get_repo_stats,
    #Commit history
    get_commit_history,
    get_commit_details,
    get_commit_range,
    search_commits,
    #File history & blame
    get_file_history,
    get_file_blame,
    #Branches & tags
    get_branches_info,
    get_tags,
    get_contributors,
    #Reflog & recovery
    get_reflog,
    get_dangling_objects,
    get_stash_list,
    #Diff & comparison
    get_diff,
    get_merge_base,
    #Safety & risk
    get_unpushed_commits,
    detect_force_push_risk,
    
    #general
    run_safe_git_command,
]

HISTORY_TOOLS = [
    get_commit_history,
    get_commit_details,
    get_commit_range,
    search_commits,
    get_file_history,
    get_file_blame,
    get_branches_info,
    get_tags,
    get_contributors,
    get_repo_stats,
    run_safe_git_command,
]

RECOVERY_TOOLS = [
    get_reflog,
    get_dangling_objects,
    get_stash_list,
    get_branches_info,
    get_repo_status,
    get_commit_details,
    run_safe_git_command,
]

SUGGEST_TOOLS = [
    get_repo_status,
    get_reflog,
    get_unpushed_commits,
    detect_force_push_risk,
    get_branches_info,
    get_stash_list,
    get_commit_history,
    run_safe_git_command,
]

PROJECT_TOOLS = [
    get_project_description,
]