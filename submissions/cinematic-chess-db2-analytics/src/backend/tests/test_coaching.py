from __future__ import annotations

import pytest

from backend.app.coaching import LangChainCoach
from backend.app.errors import CoachingDisabledError
from backend.app.models import AnalyticsSummary


def test_disabled_coaching_needs_no_optional_langchain_packages(settings) -> None:
    summary = AnalyticsSummary(
        total_games=0,
        wins=0,
        losses=0,
        draws=0,
        unknown=0,
        most_played_openings=[],
    )

    with pytest.raises(CoachingDisabledError, match="disabled"):
        LangChainCoach(settings).generate(summary, None)
