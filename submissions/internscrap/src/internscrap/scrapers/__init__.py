"""
Scrapers package initialization.
"""

from typing import List, Dict, Any
from internscrap.scrapers.base import BaseScraper
from internscrap.scrapers.sample_loader import SampleScraper
from internscrap.scrapers.remoteok import RemoteOkScraper
from internscrap.scrapers.github_internships import GitHubInternshipScraper

SCRAPERS = {
    "sample": SampleScraper(),
    "remoteok": RemoteOkScraper(),
    "github": GitHubInternshipScraper()
}

def get_scrapers(source: str = "all") -> List[BaseScraper]:
    """Returns the requested scraper instances."""
    if source in SCRAPERS:
        return [SCRAPERS[source]]
    # 'all' runs sample + online scrapers
    return list(SCRAPERS.values())
