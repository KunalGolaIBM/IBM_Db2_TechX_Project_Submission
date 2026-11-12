"""Verify the seed script only calls providers available in its Faker locale."""

import re
from pathlib import Path

from faker import Faker

SEED_FILE = Path(__file__).resolve().parents[1] / "eval" / "seed.py"


def test_seed_faker_providers_exist_for_indian_english():
    fake = Faker("en_IN")
    source = SEED_FILE.read_text(encoding="utf-8")
    providers = sorted(set(re.findall(r"fake\.(\w+)\(", source)))

    missing = [provider for provider in providers if not hasattr(fake, provider)]

    assert not missing, f"Missing en_IN Faker providers: {missing}"
