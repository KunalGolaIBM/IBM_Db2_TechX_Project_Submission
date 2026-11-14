"""Compatibility import; implementation lives in domain.signals."""
import sys
from domain import signals as _implementation
sys.modules[__name__] = _implementation
