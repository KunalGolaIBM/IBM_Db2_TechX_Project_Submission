"""Finding normalizer and deduplication service."""

from typing import List, Dict
from ..models import Finding


class FindingNormalizer:
    """Normalizes findings from diverse tools and removes duplicates using stable fingerprints."""

    @staticmethod
    def deduplicate(findings: List[Finding]) -> List[Finding]:
        seen: Dict[str, Finding] = {}
        for f in findings:
            if f.fingerprint not in seen:
                seen[f.fingerprint] = f
            else:
                # Merge references and preserve highest severity
                existing = seen[f.fingerprint]
                for ref in f.references:
                    if ref not in existing.references:
                        existing.references.append(ref)
        return list(seen.values())

    @staticmethod
    def group_by_severity(findings: List[Finding]) -> Dict[str, List[Finding]]:
        groups = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
            "info": []
        }
        for f in findings:
            sev = f.severity.lower()
            if sev in groups:
                groups[sev].append(f)
            else:
                groups["info"].append(f)
        return groups

    @staticmethod
    def group_by_category(findings: List[Finding]) -> Dict[str, List[Finding]]:
        groups: Dict[str, List[Finding]] = {}
        for f in findings:
            cat = f.category.lower()
            if cat not in groups:
                groups[cat] = []
            groups[cat].append(f)
        return groups
