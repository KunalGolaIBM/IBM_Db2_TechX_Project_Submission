
from db import get_connection
import ibm_db


def get_quiz_questions():
    """Retrieve quiz questions from IBM Db2."""

    connection = get_connection()

    try:
        sql = """
            SELECT QUESTION_ID, QUESTION_TEXT,
                   OPTION_A, OPTION_B, OPTION_C
            FROM QUIZ_QUESTIONS
            ORDER BY QUESTION_ID
        """

        statement = ibm_db.exec_immediate(connection, sql)

        questions = []

        while True:
            row = ibm_db.fetch_assoc(statement)

            if not row:
                break

            questions.append({
                "id": row["QUESTION_ID"],
                "question": row["QUESTION_TEXT"],
                "options": {
                    "A": row["OPTION_A"],
                    "B": row["OPTION_B"],
                    "C": row["OPTION_C"]
                }
            })

        return questions

    finally:
        ibm_db.close(connection)


def check_quiz_answer(question_id, selected_option):
    """Check an answer without exposing the correct answer."""

    if selected_option not in ("A", "B", "C"):
        return {"correct": False, "message": "Invalid option."}

    connection = get_connection()

    try:
        sql = """
            SELECT CORRECT_OPTION, EXPLANATION
            FROM QUIZ_QUESTIONS
            WHERE QUESTION_ID = ?
        """

        statement = ibm_db.prepare(connection, sql)
        ibm_db.bind_param(statement, 1, question_id)
        ibm_db.execute(statement)

        row = ibm_db.fetch_assoc(statement)

        if not row:
            return {"correct": False, "message": "Question not found."}

        correct = selected_option == row["CORRECT_OPTION"]

        return {
            "correct": correct,
            "message": row["EXPLANATION"] or (
                "Correct!" if correct else "Try again."
            )
        }

    finally:
        ibm_db.close(connection)
