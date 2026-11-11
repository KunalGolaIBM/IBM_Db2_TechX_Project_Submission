import re
import uuid
import logging
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse
from app.repositories.opportunity_repository import opportunity_repo
from app.repositories.ingestion_repository import ingestion_repo

logger = logging.getLogger("cloud_loop.service.ingestion")

def is_valid_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        return bool(parsed.scheme in ["http", "https"] and parsed.netloc)
    except Exception:
        return False

def slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", text.lower())
    return re.sub(r"[\s-]+", "-", cleaned).strip("-")

class IngestionService:
    def ingest_records(self, source: str, raw_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        ingestion_repo.create_run(run_id, source)

        processed = 0
        inserted = 0
        updated = 0
        rejected = 0
        errors = []

        for item in raw_items:
            processed += 1
            try:
                # 1. Map fields according to opportunity schema
                title = item.get("title") or item.get("role") or item.get("name")
                org = item.get("organization") or item.get("company") or item.get("provider") or item.get("organizer")
                app_url = item.get("application_url") or item.get("applyUrl") or item.get("website")

                if not title or not org or not app_url:
                    rejected += 1
                    errors.append(f"Item #{processed}: Missing essential title, organization, or application URL.")
                    continue

                if not is_valid_url(app_url):
                    rejected += 1
                    errors.append(f"Item #{processed} ('{title}'): Invalid application URL '{app_url}'.")
                    continue

                # Deduce opportunity type
                opp_type = item.get("opportunity_type") or item.get("type") or "opportunity"
                if "job" in opp_type.lower():
                    opp_type = "job"
                elif "intern" in opp_type.lower():
                    opp_type = "internship"
                elif "event" in opp_type.lower() or "hackathon" in opp_type.lower() or "competition" in opp_type.lower():
                    opp_type = "event"
                elif "prog" in opp_type.lower():
                    opp_type = "program"
                elif "cert" in opp_type.lower():
                    opp_type = "certification"

                # Standardize slug and ID
                slug = item.get("slug") or f"{slugify(org)}-{slugify(title)}"
                opp_id = str(item.get("id") or slug)

                # Parse skills list
                skills = item.get("skills") or []
                if isinstance(skills, str):
                    skills = [s.strip() for s in skills.split(",") if s.strip()]

                record = {
                    "id": opp_id,
                    "slug": slug,
                    "title": str(title).strip(),
                    "organization": str(org).strip(),
                    "opportunity_type": opp_type,
                    "category": item.get("category") or "Technology",
                    "description": item.get("description"),
                    "location": item.get("location") or "Remote / Pan-India",
                    "location_type": item.get("locationType") or item.get("location_type") or "remote",
                    "skills": list(skills),
                    "eligibility": item.get("eligibility") or item.get("eligibleBatch"),
                    "deadline": item.get("deadline") or item.get("registrationDeadline") or "Ongoing",
                    "application_url": app_url.strip(),
                    "source_name": source,
                    "source_url": item.get("source_url") or app_url.strip(),
                    "verification_status": "verified",
                }

                existing = opportunity_repo.get_by_id(opp_id)
                if not existing and slug:
                    existing = opportunity_repo.get_by_slug(slug)
                    if existing:
                        opp_id = existing.get("id") or opp_id
                        record["id"] = opp_id

                opportunity_repo.upsert(record)
                if existing:
                    updated += 1
                else:
                    inserted += 1

            except Exception as e:
                rejected += 1
                errors.append(f"Item #{processed} failed: {e}")

        status = "completed" if rejected == 0 else "completed_with_errors" if inserted + updated > 0 else "failed"
        summary = f"Processed {processed}: Inserted {inserted}, Updated {updated}, Rejected {rejected}."
        if errors:
            summary += f" First errors: {'; '.join(errors[:3])}"

        ingestion_repo.complete_run(run_id, processed, inserted, updated, rejected, status, summary)
        return {
            "run_id": run_id,
            "source": source,
            "processed": processed,
            "inserted": inserted,
            "updated": updated,
            "rejected": rejected,
            "status": status,
            "summary": summary,
        }

ingestion_service = IngestionService()

