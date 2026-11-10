"""Rule based translation result types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationResult:
    """Output of the rule translator.

    db2_sql is the rewritten SQL. applied_rules lists the
    rule names that changed something. untranslatable
    lists patterns with no known Db2 form. An empty
    untranslatable list does not mean the SQL is correct.
    Only execution on Db2 can prove that.
    """

    db2_sql: str
    applied_rules: tuple[str, ...] = ()
    untranslatable: tuple[str, ...] = ()

    @property
    def needs_agent(self) -> bool:
        """True when a human or agent should look at this."""
        return bool(self.untranslatable)
