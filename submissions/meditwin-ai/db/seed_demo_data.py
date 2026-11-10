"""
MediTwin AI — Seed Demo Data
Creates synthetic patients and sample data for demonstration.
All data is explicitly synthetic.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SYNTHETIC_PATIENTS = [
    {
        "demo_code": "DEMO-001",
        "display_name": "Synthetic Patient Alpha",
        "birth_year": 1985,
    },
    {
        "demo_code": "DEMO-002",
        "display_name": "Synthetic Patient Beta",
        "birth_year": 1972,
    },
    {
        "demo_code": "DEMO-003",
        "display_name": "Synthetic Patient Gamma",
        "birth_year": 1990,
    },
]


def seed_patients(repo) -> list:
    """Create synthetic demo patients if they don't exist. Returns list of patient IDs."""
    patient_ids = []
    for p in SYNTHETIC_PATIENTS:
        existing = repo.get_patient_by_code(p["demo_code"])
        if existing:
            patient_ids.append(existing["PATIENT_ID"])
            logger.info(f"Patient {p['demo_code']} already exists.")
        else:
            pid = repo.create_patient(
                demo_code=p["demo_code"],
                display_name=p["display_name"],
                birth_year=p["birth_year"],
            )
            patient_ids.append(pid)
            repo.log_audit(
                action="CREATE",
                entity_type="PATIENT",
                entity_id=pid,
                actor_id="SEED_SCRIPT",
                details={"demo_code": p["demo_code"]},
            )
            logger.info(f"Created patient {p['demo_code']} with ID {pid}.")
    return patient_ids

