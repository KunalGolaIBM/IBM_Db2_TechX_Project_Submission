"""
Scraper for remote internship and junior positions from RemoteOK API.
"""

from typing import List, Dict, Any
from datetime import date, timedelta
import requests
from internscrap.config import SCRAPER_TIMEOUT, SCRAPER_USER_AGENT
from internscrap.scrapers.base import BaseScraper


class RemoteOkScraper(BaseScraper):
    """Scrapes remote tech listings matching 'intern' or 'junior' from RemoteOK."""

    API_URL = "https://remoteok.com/api"

    @property
    def name(self) -> str:
        return "RemoteOK"

    def scrape(self) -> List[Dict[str, Any]]:
        headers = {
            "User-Agent": SCRAPER_USER_AGENT,
            "Accept": "application/json"
        }
        internships = []
        try:
            response = requests.get(
                self.API_URL, 
                headers=headers, 
                timeout=SCRAPER_TIMEOUT,
                params={"tag": "intern"}
            )
            if response.status_code != 200:
                return internships

            data = response.json()
            # The first element in remoteok api is legal disclaimer object
            items = data[1:] if len(data) > 1 and isinstance(data[0], dict) and "legal" in data[0] else data

            today = date.today()
            for item in items:
                if not isinstance(item, dict) or not item.get("position"):
                    continue

                title = item.get("position", "")
                company = item.get("company", "Unknown")
                tags = item.get("tags", [])
                apply_url = item.get("url") or f"https://remoteok.com/l/{item.get('id', '')}"
                external_id = str(item.get("id", hash(f"{company}_{title}")))

                # Determine if salary is provided
                stipend_min = float(item.get("salary_min")) if item.get("salary_min") else None
                stipend_max = float(item.get("salary_max")) if item.get("salary_max") else None

                internships.append({
                    "title": title,
                    "company": company,
                    "company_location": item.get("location", "Remote"),
                    "location": "Remote",
                    "is_remote": True,
                    "stipend_min": stipend_min,
                    "stipend_max": stipend_max,
                    "currency": "USD",
                    "apply_url": apply_url,
                    "source": self.name,
                    "external_id": external_id,
                    "deadline": str(today + timedelta(days=30)),
                    "skills": [t.title() for t in tags[:5]],
                    "industry": "Software & Internet",
                    "tier": "Startup"
                })

        except Exception as e:
            # Gracefully handle network timeouts or rate limits
            pass

        return internships
