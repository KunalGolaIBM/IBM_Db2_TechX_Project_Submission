from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseScraper(ABC):
    """Abstract base class for internship scrapers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the scraper source."""
        pass

    @abstractmethod
    def scrape(self) -> List[Dict[str, Any]]:
        """
        Executes the scraper and returns a list of standardized internship dicts.
        Format of each item:
        {
            'title': str,
            'company': str,
            'company_location': str,
            'location': str,
            'is_remote': bool,
            'stipend_min': float | None,
            'stipend_max': float | None,
            'currency': str,
            'apply_url': str,
            'source': str,
            'external_id': str,
            'deadline': str | None (YYYY-MM-DD),
            'skills': list[str],
            'industry': str,
            'tier': str
        }
        """
        pass
