"""Compatibility import; implementation lives in adapters.gemini."""
import sys
from adapters.gemini import LLMUnavailable as LLMUnavailable, generate as generate, generate_json as generate_json, run_tool_agent as run_tool_agent
from adapters import gemini as _implementation
sys.modules[__name__] = _implementation
