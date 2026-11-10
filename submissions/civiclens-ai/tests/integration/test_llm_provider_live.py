"""Exercises a REAL hosted LLM provider. Skipped unless you opt in:

    CIVICLENS_DB2_TESTS=1 CIVICLENS_LLM_TESTS=1 LLM_PROVIDER=anthropic LLM_MODEL=<model> \
    ANTHROPIC_API_KEY=... pytest tests/integration/test_llm_provider_live.py

(or LLM_PROVIDER=openai / watsonx with their credentials). It makes billable API calls.
"""

import os

import pytest

from civiclens.agent import investigate
from civiclens.config import get_settings
from civiclens.db import investigation_repo as inv_repo
from civiclens.domain.investigation_models import GeneratorType, RunRequest
from tests.conftest import db2_enabled
from tests.integration.test_investigations_live import CREATOR, cluster, db, new_inv  # noqa: F401

pytestmark = [
    pytest.mark.db2,
    pytest.mark.llm,
    pytest.mark.skipif(
        not (
            db2_enabled()
            and os.getenv("CIVICLENS_LLM_TESTS") == "1"
            and os.getenv("LLM_PROVIDER", "none") != "none"
        ),
        reason="real-LLM test: set CIVICLENS_LLM_TESTS=1, LLM_PROVIDER, LLM_MODEL and the provider key",
    ),
]


def test_real_llm_produces_grounded_proposals(db):  # noqa: F811
    ids = set(cluster(db, 6))
    inv = new_inv(db)
    res = investigate.run_investigation(
        db, inv.investigation_id, requested_by=CREATOR, settings=get_settings(),
        request=RunRequest(mode="llm"),
    )  # fmt: skip
    assert res.generator is GeneratorType.LLM and res.model_name.startswith(os.environ["LLM_PROVIDER"])
    recs = inv_repo.list_recommendations(db, inv.investigation_id)
    for rec in recs:
        assert rec.status.value == "PROPOSED" and rec.evidence_ids
        assert set(rec.evidence_ids) <= {
            e.complaint_id for e in inv_repo.list_evidence(db, inv.investigation_id)
        }
    assert ids  # cluster existed for the model to find
