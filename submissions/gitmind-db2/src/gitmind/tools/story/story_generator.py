from collections import defaultdict
from tools.story.get_commits import file_changes_by_commit, hyperlink
from utils.banner import print_banner

# to group commits by author
# def group_commits_by_author(commits):
#     """
#     Group commits by author.

#     Args:
#         commits (list): A list of dictionaries containing commit information.

#     Returns:
#         dict: A dictionary where keys are author names and values are lists of their commits.
#     """
#     grouped_commits = defaultdict(list)
#     for commit in commits:
#         grouped_commits[commit["author"]].append(commit)
#     return grouped_commits

# # to group commits by date
# def group_commits_by_date(commits):
#     """
#     Group commits by date.

#     Args:
#         commits (list): A list of dictionaries containing commit information.

#     Returns:
#         dict: A dictionary where keys are dates and values are lists of commits made on that date.
#     """
#     grouped_commits = defaultdict(list)
#     for commit in commits:
#         grouped_commits[commit["date"]].append(commit)
#     return grouped_commits          

# to generate a narrative story from commits - gitmind story
# def generate_story(commits):
#     """
#     Generate a narrative story from a list of commits.

#     Args:
#         commits (list): A list of dictionaries containing commit information.
#     Returns:
#         str: A narrative story summarizing the commits.
#     """
#     if not commits:
#         return "No commits found."

#     # grouped_by_author = group_commits_by_author(commits)
#     grouped_by_date = group_commits_by_date(commits)

#     story_lines = []
#     story_lines.append("Repository Story - \n")

#     for date, daily_commits in grouped_by_date.items():
#         story_lines.append(f"On {date}, the following commits were made:")
#         for commit in daily_commits:
#             story_lines.append(
#                 f"- [{commit['hash']}] {commit['message']} by https://github.com/{commit['author']}"
#             )
#         story_lines.append("")

#     return "\n".join(story_lines)


# def generate_detailed_story(commits):
#     """
#     Generate a detailed narrative story from a list of commits, including file changes.

#     Args:
#         commits (list): A list of dictionaries containing commit information.

#     Returns:
#         str: A detailed narrative story summarizing the commits and their file changes.
#     """
#     if not commits:
#         return "No commits found."

#     grouped_by_date = group_commits_by_date(commits)

#     story_lines = []
#     story_lines.append("Repository Story - \n")

#     for date, daily_commits in grouped_by_date.items():
#         story_lines.append(f"On {date}, the following commits were made:")
#         for commit in daily_commits:
#             story_lines.append(
#                 f"- [{commit['hash']}] {commit['message']} by https://github.com/{commit['author']}"
#             )
#             file_changes = file_changes_by_commit(commit_hash=commit['hash'])
#             if file_changes:
#                 story_lines.append(f"  Files changed: {file_changes}")
#         story_lines.append("")

#     return "\n".join(story_lines)

class GroupCommits:
    def __init__(self, commits):
        self.commits = commits

    def group(self, by="date | author"):
        if not self.commits:
            return "No commits found."
        grouped_commits= defaultdict(list)
        for commits in self.commits:
            if by == "date":
                grouped_commits[commits["date"]].append(commits)
            elif by == "author":
                grouped_commits[commits["author"]].append(commits)

        return grouped_commits  

class StoryGenerator:
    def __init__(self, commits):
        self.commits = commits

    def generate(self, detailed=False, by: str = "date"):
        if not self.commits:
            return "No commits found."
        
        grouper = GroupCommits(self.commits)
        
        grouped_by = grouper.group(by=by)

        story_lines = []

        print_banner("Repository Story")

        for first_key, daily_commits in grouped_by.items():
            if by == "date":
                story_lines.append(f"On {first_key}, the following commits were made:")
            elif by == "author":
                story_lines.append(f"By {first_key}, the following commits were made:")

            
            for commit in daily_commits:
                story_lines.append(
                    f"- [{commit['hash']}] {commit['message']} by https://github.com/{commit['author']}"
                )

                if detailed:
                    file_changes = file_changes_by_commit(commit_hash=commit['hash'])
                    if file_changes:
                        story_lines.append(f"  Files changed: {file_changes}")
                        story_lines.append("")

        return "\n".join(story_lines)
    

