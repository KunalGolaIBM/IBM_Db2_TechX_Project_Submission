"""
Parser for GitHub Community Tech Internship Lists (Markdown tables).
Fetches publicly curated summer/fall SWE internship listings.
"""

import re
from typing import List, Dict, Any
from datetime import date, timedelta
import requests
from internscrap.config import SCRAPER_TIMEOUT, SCRAPER_USER_AGENT
from internscrap.scrapers.base import BaseScraper


class GitHubInternshipScraper(BaseScraper):
    """Parses markdown tables from popular GitHub internship repositories."""

    RAW_URL = (
        "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships"
        "/dev/README.md"
    )

    @property
    def name(self) -> str:
        return "GitHubTechInternships"

    def scrape(self) -> List[Dict[str, Any]]:
        headers = {"User-Agent": SCRAPER_USER_AGENT}
        internships = []
        try:
            res = requests.get(self.RAW_URL, headers=headers, timeout=SCRAPER_TIMEOUT)
            if res.status_code != 200:
                return internships

            lines = res.text.splitlines()
            today = date.today()

            # Markdown table line regex: | Company | Role | Location | Application/Link | Date Posted |
            row_pattern = re.compile(r"^\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|")
            link_pattern = re.compile(r'href="([^"]+)"|\[Apply\]\(([^)]+)\)')

            for line in lines:
                if not line.startswith("|") or "---" in line or "Company" in line:
                    continue

                match = row_pattern.match(line)
                if not match:
                    continue

                company_raw, role_raw, location_raw, link_col = [g.strip() for g in match.groups()]
                # Strip markdown bold/links from company
                company = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", company_raw)
                company = re.sub(r"[*_`]", "", company).strip()

                role = re.sub(r"[*_`]", "", role_raw).strip()
                location = re.sub(r"[*_`]", "", location_raw).strip()

                if not company or not role or "🔒" in link_col:
                    continue

                # Extract URL from link column
                urls = link_pattern.findall(link_col)
                apply_url = ""
                if urls:
                    apply_url = urls[0][0] or urls[0][1]

                if not apply_url or not apply_url.startswith("http"):
                    continue

                is_remote = "remote" in location.lower()
                external_id = str(hash(f"{company}_{role}_{location}"))

                # Extract inferred skills from role
                skills = ["Software Engineering"]
                role_lower = role.lower()
                if "backend" in role_lower:
                    skills.extend(["Python", "SQL", "APIs"])
                if "frontend" in role_lower or "web" in role_lower:
                    skills.extend(["React", "TypeScript", "CSS"])
                if "ai" in role_lower or "machine learning" in role_lower:
                    skills.extend(["Python", "Machine Learning", "PyTorch"])
                if "data" in role_lower:
                    skills.extend(["SQL", "IBM Db2", "Python", "Data Engineering"])

                internships.append({
                    "title": role,
                    "company": company,
                    "company_location": location,
                    "location": location,
                    "is_remote": is_remote,
                    "stipend_min": None,
                    "stipend_max": None,
                    "currency": "USD",
                    "apply_url": apply_url,
                    "source": self.name,
                    "external_id": external_id,
                    "deadline": str(today + timedelta(days=25)),
                    "skills": list(set(skills)),
                    "industry": "Technology",
                    "tier": "Enterprise" if any(k in company.lower() for k in ["ibm", "google", "microsoft", "amazon", "apple", "meta"]) else "Mid"
                })

                if len(internships) >= 30:
                    break

        except Exception:
            pass

        return internships
