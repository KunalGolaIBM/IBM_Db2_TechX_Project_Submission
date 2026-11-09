import re
from utils.banner import print_banner
from rich.console import Console

console = Console(markup=True)

STOPWORDS = {
    "feat",
    "fix",
    "chore",
    "refactor",
    "introduce",
    "docs",
    "test",
    "add",
    "update",
    "remove",
    "merge",
    "initial",
    "setup",
    "config",
    "workflows",
    "ci",
    "build",
    "release",
    "version",
    "style",
    "cleanup",
    "typo",
    "improve",
    "optimize",
    "performance",
    "security",
    "deprecated",
    "hotfix",
    "minor",
    "major",
    "patch",
    "wip",
    "temp",
    "misc",
}

# def extract_topic(commit_message):
#     """
#     Extracts a topic from a commit message by removing stopwords and non-alphanumeric characters.
#     """
#     # Remove non-alphanumeric characters and convert to lowercase
#     cleaned_message = re.sub(r"[^a-zA-Z0-9\s]", "", commit_message).lower()
#     # Split the message into words
#     words = cleaned_message.split()
#     # Filter out stopwords
#     filtered_words = [word for word in words if word not in STOPWORDS]

#     removed_stopwords = [word for word in words if word in STOPWORDS]
#     # If no words remain after filtering, return a default topic
#     if not filtered_words:
#         return removed_stopwords if removed_stopwords else "general"
#     # Join the remaining words to form the topic
#     topic = " ".join(filtered_words)

#     # clear_message = f"{removed_stopwords}: {topic}"
#     return topic

def extract_topic(commit_msg):
    words = re.findall(r"\w+", commit_msg.lower())
    # print(f'Words extracted from commit message: {words}')

    for word in words:
        if word not in STOPWORDS:
            # return the first non-stopword as the topic
            return word

    return "misc"

# extracted_topic = extract_topic("add: gitmind explain feature and introduce agent structure in README")
# print(extracted_topic)


def map_commit_to_topic(commit_msg: list):
    commits_by_topic: dict[str, list[object]] = {}
    for commit in commit_msg:
        topic = extract_topic(commit)
        if topic not in commits_by_topic:
            commits_by_topic[topic] = []
        commits_by_topic[topic].append(commit)

    return commits_by_topic


# mapped_commits = map_commit_to_topic([
#     "Add 'gitmind explain' feature and introduce agent structure in README",
#     "Add initial architecture diagram and enhance 'gitmind suggest' description in README",
#     "Structured Features and Details"
# ])
# print(f"Mapped Commits: {mapped_commits}")

class OverviewGenerator:
    def __init__(self, commits):
        self.commits = commits

    def extract_topic(self, commit):
        """
        Extracts a topic from a commit message by removing stopwords and non-alphanumeric characters.
        """
        words = re.findall(r"\w+", str(commit['message']).lower())
        # print(f'Words extracted from commit message: {words}')

        for word in words:
            if word not in STOPWORDS:
                # return the first non-stopword as the topic
                return word

        return "misc"

    def overview(self):
        """
        Generate a quick overview of the commits, grouped by topic.

        Args:
            commits (list): A list of dictionaries containing commit information.
        Returns:
            str: A quick overview summarizing the commits by topic.
        """
        if not self.commits:
            return 'No commits found.'

        print_banner("Quick Overview")

        if console:
            console.print("[yellow]This might not be accurate, please use 'gitmind story --detailed' for a more detailed story.[/yellow]\n")

        topic_groups = {}
        for commit in self.commits:
            topic = self.extract_topic(commit)
            if topic not in topic_groups:
                topic_groups[topic] = []
            topic_groups[topic].append(commit['message'])

        overview_lines = []
        for topic, commits in topic_groups.items():
            overview_lines.append(f"- {topic}: {(commits)}")

        return "\n".join(overview_lines)
