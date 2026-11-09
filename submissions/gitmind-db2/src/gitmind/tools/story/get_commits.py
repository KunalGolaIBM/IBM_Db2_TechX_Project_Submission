from git import Repo, InvalidGitRepositoryError, BadName
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta

def hyperlink(text, url):
    return f"\033]{url}\033\\{text}\033]\033\\"

def get_recent_commits(repo_path=".", days=7):
    repo = Repo(repo_path)

    since = datetime.now() - timedelta(days=days)

    commits = []

    for commit in repo.iter_commits():
        commit_time = datetime.fromtimestamp(commit.committed_date)

        if commit_time < since:
            break

        commits.append(
            {
                "hash": commit.hexsha[:7],
                "message": commit.message.strip(),
                "author": str(commit.author),
                "date": commit_time.date(),
            }
        )

    return commits



def file_changes_by_commit(
    repo_path=".",
    commit_hash=None,
):
    """
    Return file changes for a commit.

    Returns:
        [
            {
                "path": "src/main.py",
                "action": "modified",
                "old_path": None
            }
        ]
    """

    try:
        repo = Repo(Path(repo_path).resolve())
    except InvalidGitRepositoryError:
        raise ValueError(f"{repo_path} is not a valid git repository")

    try:
        commit = repo.commit(commit_hash) if commit_hash else repo.head.commit
    except BadName:
        raise ValueError(f"Invalid commit hash: {commit_hash}")

    changes = []

    try:
        output = repo.git.diff_tree(
            "--root",
            "--find-renames",
            "--name-status",
            "-r",
            commit.hexsha,
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to get diff for commit {commit.hexsha}"
        ) from e

    for line in output.splitlines():

        if not line.strip():
            continue

        parts = line.split("\t")

        status = parts[0]

        # Added
        if status == "A":
            changes.append(
                {
                    "path": parts[1],
                    "action": "added",
                    "old_path": None,
                }
            )

        # Modified
        elif status == "M":
            changes.append(
                {
                    "path": parts[1],
                    "action": "modified",
                    "old_path": None,
                }
            )

        # Deleted
        elif status == "D":
            changes.append(
                {
                    "path": parts[1],
                    "action": "deleted",
                    "old_path": None,
                }
            )

        # Copied
        elif status.startswith("C"):
            changes.append(
                {
                    "path": parts[2],
                    "action": "copied",
                    "old_path": parts[1],
                }
            )

        # Renamed
        elif status.startswith("R"):
            changes.append(
                {
                    "path": parts[2],
                    "action": "renamed",
                    "old_path": parts[1],
                }
            )

    return sorted(
        changes,
        key=lambda x: (x["path"], x["action"]),
    )