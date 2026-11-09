"""No-cost, no-network readiness check for the real-LLM path.

It reads the same settings the API uses and answers one question: COULD a real provider run right now?
That needs a provider selected (LLM_PROVIDER), a model (LLM_MODEL), the provider's credentials and the
provider's package. Only variable NAMES are reported, never values. It never contacts a provider and
never makes a billable call.

  READY    the settings are complete and the package is installed. This does NOT prove the credentials work:
           one bounded real run (billable, needs explicit authorization) is the only proof.
  BLOCKED  something is missing; the reasons are listed.

Exit code: 0 = READY, 2 = BLOCKED.

Usage:  python scripts/llm_preflight.py
"""

import sys

import _bootstrap  # noqa: F401
from civiclens.agent.llm import llm_status
from civiclens.config import get_settings

ONE_BOUNDED_RUN = (
    "CIVICLENS_DB2_TESTS=1 CIVICLENS_LLM_TESTS=1 pytest tests/integration/test_llm_provider_live.py -v"
)


def main() -> int:
    status = llm_status(get_settings())
    print("LLM readiness (no provider is contacted, no value is printed)")
    print(f"  provider : {status['provider']}")
    print(f"  model    : {status['model'] or '(not set)'}")
    if status["provider"] == "none":
        print("  status   : BLOCKED")
        print("  problem  : LLM_PROVIDER is 'none', so no real provider is selected.")
        print("             Every recommendation will be 'Rule-based · no LLM' (or manual).")
        print("             Nothing is claimed to be AI.")
        print("  to enable: set LLM_PROVIDER (openai | anthropic | watsonx), LLM_MODEL and that")
        print("             provider's credentials, pip install -r requirements-llm.txt,")
        print("             then re-run this check.")
        return 2
    if not status["configured"]:
        print("  status   : BLOCKED")
        print(f"  problem  : {status['problem']}")
        return 2
    print("  status   : READY (settings complete, package installed; the credentials are NOT verified)")
    print("  next     : a real run is billable and needs explicit authorization.")
    print("             The one bounded verification is:")
    print(f"             {ONE_BOUNDED_RUN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
