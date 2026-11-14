"""Compatibility import; implementation lives in services.presenter."""
import sys
from services.presenter import present as present
from services import presenter as _implementation
sys.modules[__name__] = _implementation
