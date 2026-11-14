"""Compatibility import; implementation lives in adapters.db2."""
import sys
from adapters.db2 import Db2Repository as Db2Repository
from adapters import db2 as _implementation
sys.modules[__name__] = _implementation
