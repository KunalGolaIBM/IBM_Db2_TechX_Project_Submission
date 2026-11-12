"""ShipSafe: production-readiness add-on for IBM Bob and other AI IDEs, built on IBM Db2."""

import os as _os

# Everything stays on this machine: switch off the anonymous usage telemetry that
# CrewAI, LiteLLM and Haystack (PostHog) send by default. Users can still opt in.
for _key, _value in (("CREWAI_DISABLE_TELEMETRY", "true"), ("OTEL_SDK_DISABLED", "true"),
                     ("LITELLM_TELEMETRY", "False"), ("HAYSTACK_TELEMETRY_ENABLED", "False"),
                     ("ANONYMIZED_TELEMETRY", "False")):
    _os.environ.setdefault(_key, _value)

__version__ = "3.0.0"
