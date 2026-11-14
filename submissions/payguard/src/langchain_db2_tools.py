"""Compatibility import; implementation lives in adapters.langchain_db2."""
import sys
from adapters.langchain_db2 import PayGuardEmbeddings as PayGuardEmbeddings, ParameterizedDB2VS as ParameterizedDB2VS, example_vector_store as example_vector_store, run_investigation as run_investigation
from adapters import langchain_db2 as _implementation
sys.modules[__name__] = _implementation
