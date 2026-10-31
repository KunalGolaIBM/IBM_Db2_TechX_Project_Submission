"""Terraform State Resource Identity Resolver.

Maps declarative Terraform resource addresses to physical AWS resource IDs
using Terraform State artifacts.
"""

from typing import Any, Optional
from backend.app.models.evidence import ResourceIdentity


class StateIdentityResolver:
    """Extracts physical AWS resource IDs from Terraform state JSON."""

    def resolve_identities(self, state_json: dict[str, Any]) -> dict[str, ResourceIdentity]:
        """Parse Terraform state JSON and return a mapping of address -> ResourceIdentity."""
        identities: dict[str, ResourceIdentity] = {}
        
        # State v4 format: resources array
        resources = state_json.get("resources", [])
        for res in resources:
            res_type = res.get("type", "")
            res_name = res.get("name", "")
            mode = res.get("mode", "managed")
            if mode != "managed":
                continue

            module = res.get("module")
            if module:
                address = f"{module}.{res_type}.{res_name}"
            else:
                address = f"{res_type}.{res_name}"
            instances = res.get("instances", [])
            for inst in instances:
                attributes = inst.get("attributes", {})
                physical_id = attributes.get("id") or attributes.get("identifier")
                if physical_id:
                    identities[address] = ResourceIdentity(
                        terraform_address=address,
                        resource_type=res_type,
                        provider="aws",
                        resource_id=physical_id
                    )
        return identities
