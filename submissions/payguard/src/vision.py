"""Compatibility import; implementation lives in adapters.vision."""
import sys
from adapters.vision import ImageError as ImageError, read_screenshot as read_screenshot, to_message as to_message
from adapters import vision as _implementation
sys.modules[__name__] = _implementation
