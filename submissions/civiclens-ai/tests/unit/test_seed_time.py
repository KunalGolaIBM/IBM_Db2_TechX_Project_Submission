import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend" / "scripts"))

from seed_synthetic import reported_time  # noqa: E402


def test_seeded_times_are_never_in_the_future():
    now = datetime(2026, 11, 9, 8, 30)
    for days_ago in range(0, 3):
        for hour in range(0, 24):
            t = reported_time(now, days_ago, hour)
            assert t <= now and t.hour == hour
    assert reported_time(now, 0, 21) == datetime(2026, 11, 8, 21, 0)
    assert reported_time(now, 0, 6) == datetime(2026, 11, 9, 6, 0)
