import unittest

from src.odyssey_db2 import Task, build_plan_prompt, order_tasks, parse_capture


class OdysseyPlannerTests(unittest.TestCase):
    def test_parse_capture_ignores_empty_items(self):
        self.assertEqual(parse_capture("Write report, , email mentor"), [
            Task("Write report"),
            Task("email mentor"),
        ])

    def test_order_tasks_prioritizes_urgent_work(self):
        tasks = [Task("low task", priority="low"), Task("incident", priority="urgent")]
        self.assertEqual([task.title for task in order_tasks(tasks)], ["incident", "low task"])

    def test_prompt_contains_structured_task_metadata(self):
        prompt = build_plan_prompt([Task("Ship feature", "deadline", "high")])
        self.assertIn("Ship feature [deadline, high]", prompt)


if __name__ == "__main__":
    unittest.main()
