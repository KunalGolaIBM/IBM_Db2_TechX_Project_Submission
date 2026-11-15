"""Persist Odyssey captures in IBM Db2 and turn them into actionable plans."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv() -> bool:
        return False


load_dotenv()


@dataclass(frozen=True)
class Task:
    title: str
    category: str = "task"
    priority: str = "medium"


def parse_capture(raw_input: str) -> list[Task]:
    """Convert a simple capture into tasks without requiring an LLM."""
    parts = [part.strip() for part in raw_input.replace("\n", ",").split(",")]
    return [Task(title=part) for part in parts if part]


def order_tasks(tasks: Iterable[Task]) -> list[Task]:
    """Apply Odyssey's deterministic urgency ordering."""
    rank = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(tasks, key=lambda task: (rank.get(task.priority, 2), task.title.lower()))


def build_plan_prompt(tasks: list[Task]) -> str:
    """Build the structured input used by the LangChain planning chain."""
    task_lines = "\n".join(
        f"- {task.title} [{task.category}, {task.priority}]" for task in tasks
    )
    return (
        "Create a concise, actionable Odyssey plan from these tasks. "
        "Return a numbered list with one next action per task.\n\n"
        f"{task_lines}"
    )


def generate_plan(tasks: list[Task]) -> str:
    """Generate a plan with LangChain when configured, otherwise use local ordering."""
    if not tasks:
        return "No tasks captured."

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return "\n".join(
            f"{index}. {task.title}" for index, task in enumerate(order_tasks(tasks), start=1)
        )

    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are Odyssey, a focused productivity planner. "
                "Prefer small concrete next actions.",
            ),
            ("human", "{capture}"),
        ]
    )
    model_kwargs = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "api_key": api_key,
    }
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    if base_url:
        model_kwargs["base_url"] = base_url
    chain = prompt | ChatOpenAI(**model_kwargs) | StrOutputParser()
    return chain.invoke({"capture": build_plan_prompt(tasks)})


class Db2TaskStore:
    """Small parameterized IBM Db2 repository for captured Odyssey tasks."""

    def __init__(self) -> None:
        self._connection = None

    def connect(self) -> None:
        import ibm_db

        required = ("DB2_DATABASE", "DB2_HOSTNAME", "DB2_PORT", "DB2_USERNAME", "DB2_PASSWORD")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise ValueError(f"Missing Db2 configuration: {', '.join(missing)}")
        connection_string = (
            f"DATABASE={os.environ['DB2_DATABASE']};"
            f"HOSTNAME={os.environ['DB2_HOSTNAME']};"
            f"PORT={os.environ['DB2_PORT']};"
            f"PROTOCOL={os.getenv('DB2_PROTOCOL', 'TCPIP')};"
            f"UID={os.environ['DB2_USERNAME']};PWD={os.environ['DB2_PASSWORD']};"
        )
        self._connection = ibm_db.connect(connection_string, "", "")

    def save_capture(self, raw_input: str, tasks: Iterable[Task]) -> int:
        import ibm_db

        if self._connection is None:
            self.connect()
        statement = ibm_db.prepare(
            self._connection,
            "INSERT INTO ODYSSEY_TASKS "
            "(RAW_INPUT, TITLE, CATEGORY, PRIORITY, CAPTURED_AT) VALUES (?, ?, ?, ?, ?)",
        )
        captured_at = datetime.now(timezone.utc).replace(tzinfo=None)
        count = 0
        for task in tasks:
            ibm_db.bind_param(statement, 1, raw_input)
            ibm_db.bind_param(statement, 2, task.title)
            ibm_db.bind_param(statement, 3, task.category)
            ibm_db.bind_param(statement, 4, task.priority)
            ibm_db.bind_param(statement, 5, captured_at)
            ibm_db.execute(statement)
            count += 1
        return count

    def close(self) -> None:
        if self._connection is not None:
            import ibm_db

            ibm_db.close(self._connection)
            self._connection = None


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Store an Odyssey capture in IBM Db2")
    parser.add_argument("capture", help="Comma- or newline-separated tasks")
    parser.add_argument("--save", action="store_true", help="Persist parsed tasks in Db2")
    args = parser.parse_args()

    tasks = parse_capture(args.capture)
    if args.save:
        store = Db2TaskStore()
        try:
            saved = store.save_capture(args.capture, tasks)
        finally:
            store.close()
        print(f"Saved {saved} task(s) to IBM Db2.")
    print(json.dumps({"tasks": [asdict(task) for task in tasks], "plan": generate_plan(tasks)}))


if __name__ == "__main__":
    main()
