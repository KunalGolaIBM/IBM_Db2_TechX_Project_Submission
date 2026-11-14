"""Compatibility import; implementation lives in adapters.paypal."""
import sys
from adapters.paypal import PayPalError as PayPalError, PayPalClient as PayPalClient
from adapters import paypal as _implementation
sys.modules[__name__] = _implementation
