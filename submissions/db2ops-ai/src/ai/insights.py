"""Evidence-grounded analytics summaries."""
from src.ai.sql_generator import explain_results


def summarize(question: str, dataframe) -> str:
    return explain_results(question, dataframe)
