"""Compatibility import; implementation lives in services.investigation."""
import sys
from services.investigation import Investigator as Investigator, fallback_explanation as fallback_explanation, parse_purchase_fallback as parse_purchase_fallback
from services import investigation as _implementation
sys.modules[__name__] = _implementation
