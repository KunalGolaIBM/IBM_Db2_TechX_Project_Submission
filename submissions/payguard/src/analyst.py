"""Compatibility import; implementation lives in services.analyst."""
import sys
from services.analyst import UnsafeSQL as UnsafeSQL, guard_sql as guard_sql, Analyst as Analyst
from services.analyst import QUICK_QUESTIONS as QUICK_QUESTIONS
from services import analyst as _implementation
sys.modules[__name__] = _implementation
