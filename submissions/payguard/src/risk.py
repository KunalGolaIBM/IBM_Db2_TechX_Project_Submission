"""Compatibility import; implementation lives in domain.scoring."""
import sys
from domain.models import ScreenRequest as ScreenRequest, ScreenResult as ScreenResult
from domain import scoring as _implementation
sys.modules[__name__] = _implementation
