"""
Tests for scrapers and data ingestion normalization.
"""

from internscrap.scrapers.sample_loader import SampleScraper


def test_sample_scraper():
    scraper = SampleScraper()
    items = scraper.scrape()
    assert len(items) > 0
    first = items[0]
    assert "title" in first
    assert "company" in first
    assert "apply_url" in first
    assert "skills" in first
    assert isinstance(first["skills"], list)
    assert len(first["skills"]) > 0
