"""
Sample curated tech internships for instant offline demo and reliable testing.
"""

from typing import List, Dict, Any
from datetime import date, timedelta
from internscrap.scrapers.base import BaseScraper


class SampleScraper(BaseScraper):
    """Loads a curated set of software engineering, AI, and data internships."""

    @property
    def name(self) -> str:
        return "CuratedTechX"

    def scrape(self) -> List[Dict[str, Any]]:
        today = date.today()
        return [
            {
                "title": "Db2 Database Kernel & Optimization Intern",
                "company": "IBM",
                "company_location": "Armonk, NY",
                "location": "San Jose, CA / Hybrid",
                "is_remote": False,
                "stipend_min": 45.0,
                "stipend_max": 60.0,
                "currency": "USD",
                "apply_url": "https://www.ibm.com/employment/internships",
                "source": self.name,
                "external_id": "IBM-TECHX-01",
                "deadline": str(today + timedelta(days=28)),
                "skills": ["IBM Db2", "C++", "SQL", "Database Internals", "Linux"],
                "industry": "Enterprise AI & Cloud",
                "tier": "Enterprise"
            },
            {
                "title": "Open Source Systems & Kubernetes Intern",
                "company": "Red Hat",
                "company_location": "Raleigh, NC",
                "location": "Remote",
                "is_remote": True,
                "stipend_min": 40.0,
                "stipend_max": 52.0,
                "currency": "USD",
                "apply_url": "https://www.redhat.com/en/jobs",
                "source": self.name,
                "external_id": "RH-TECHX-02",
                "deadline": str(today + timedelta(days=15)),
                "skills": ["Go", "Kubernetes", "Linux", "Docker", "Python"],
                "industry": "Open Source Software",
                "tier": "Enterprise"
            },
            {
                "title": "Full Stack Engineering Intern",
                "company": "Stripe",
                "company_location": "San Francisco, CA",
                "location": "Remote / New York",
                "is_remote": True,
                "stipend_min": 60.0,
                "stipend_max": 75.0,
                "currency": "USD",
                "apply_url": "https://stripe.com/jobs/search?q=intern",
                "source": self.name,
                "external_id": "STRIPE-SWE-03",
                "deadline": str(today + timedelta(days=21)),
                "skills": ["Ruby", "TypeScript", "React", "SQL", "APIs"],
                "industry": "Fintech & Payments",
                "tier": "Enterprise"
            },
            {
                "title": "Machine Learning Research Intern - Foundation Models",
                "company": "Anthropic",
                "company_location": "San Francisco, CA",
                "location": "San Francisco, CA",
                "is_remote": False,
                "stipend_min": 65.0,
                "stipend_max": 85.0,
                "currency": "USD",
                "apply_url": "https://www.anthropic.com/careers",
                "source": self.name,
                "external_id": "ANTH-ML-04",
                "deadline": str(today + timedelta(days=35)),
                "skills": ["Python", "PyTorch", "LLMs", "Deep Learning", "Distributed Systems"],
                "industry": "Artificial Intelligence",
                "tier": "Startup"
            },
            {
                "title": "Distributed Data Infrastructure Intern",
                "company": "Databricks",
                "company_location": "San Francisco, CA",
                "location": "Remote",
                "is_remote": True,
                "stipend_min": 55.0,
                "stipend_max": 70.0,
                "currency": "USD",
                "apply_url": "https://www.databricks.com/company/careers",
                "source": self.name,
                "external_id": "DBX-DATA-05",
                "deadline": str(today + timedelta(days=19)),
                "skills": ["Java", "Scala", "Apache Spark", "SQL", "Distributed Systems"],
                "industry": "Data Platform",
                "tier": "Enterprise"
            },
            {
                "title": "AI Platform & Agent Systems Intern",
                "company": "Scale AI",
                "company_location": "San Francisco, CA",
                "location": "San Francisco, CA",
                "is_remote": False,
                "stipend_min": 52.0,
                "stipend_max": 68.0,
                "currency": "USD",
                "apply_url": "https://scale.com/careers",
                "source": self.name,
                "external_id": "SCALE-AI-06",
                "deadline": str(today + timedelta(days=10)),
                "skills": ["Python", "Machine Learning", "TypeScript", "Docker"],
                "industry": "AI Infrastructure",
                "tier": "Startup"
            }
        ]
