import re
from typing import List


def generate_sql_from_question(question: str) -> str:
    q = question.lower().strip()

    if "top" in q and "student" in q:
        return "SELECT name, cgpa FROM students ORDER BY cgpa DESC FETCH FIRST 5 ROWS ONLY"

    if "attendance" in q:
        return "SELECT course_id, present_days, total_days FROM attendance ORDER BY present_days DESC"

    if "course" in q or "courses" in q:
        return "SELECT * FROM courses ORDER BY course_id"

    if "result" in q or "marks" in q:
        return "SELECT student_id, course_id, marks, grade FROM results ORDER BY marks DESC"

    if "event" in q:
        return "SELECT * FROM events ORDER BY event_date DESC"

    return "SELECT * FROM students FETCH FIRST 10 ROWS ONLY"


def extract_keywords(question: str) -> List[str]:
    return re.findall(r"[a-zA-Z]+", question)
