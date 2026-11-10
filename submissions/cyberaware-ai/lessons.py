
from db import get_connection
import ibm_db


def get_all_lessons():
    """Retrieve all cybersecurity lessons from IBM Db2."""

    connection = get_connection()

    try:
        sql = """
            SELECT LESSON_ID, TITLE, CATEGORY, LESSON_CONTENT
            FROM LESSONS
            ORDER BY LESSON_ID
        """

        statement = ibm_db.exec_immediate(connection, sql)

        lessons = []

        while True:
            row = ibm_db.fetch_assoc(statement)

            if not row:
                break

            lessons.append({
                "id": row["LESSON_ID"],
                "title": row["TITLE"],
                "category": row["CATEGORY"],
                "content": row["LESSON_CONTENT"]
            })

        return lessons

    finally:
        ibm_db.close(connection)


def get_lesson_context():
    """Prepare lesson information for the AI assistant."""

    lessons = get_all_lessons()

    return "\n\n".join(
        f"Lesson: {lesson['title']}\n"
        f"Category: {lesson['category']}\n"
        f"Information: {lesson['content']}"
        for lesson in lessons
    )
