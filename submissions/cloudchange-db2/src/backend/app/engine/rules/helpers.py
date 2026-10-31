"""Helper utilities for deterministic rule evaluation."""

from typing import Any, NamedTuple, Optional

# Standard EC2 instance size hierarchy for within-family comparison
EC2_SIZE_ORDER = [
    "nano",
    "micro",
    "small",
    "medium",
    "large",
    "xlarge",
    "2xlarge",
    "3xlarge",
    "4xlarge",
    "6xlarge",
    "8xlarge",
    "9xlarge",
    "10xlarge",
    "12xlarge",
    "16xlarge",
    "18xlarge",
    "24xlarge",
    "32xlarge",
    "48xlarge",
    "56xlarge",
    "112xlarge",
]

PUBLIC_CIDRS = {"0.0.0.0/0", "::/0"}
SENSITIVE_PORTS = {22, 3389}


class SemanticIngressRule(NamedTuple):
    """Semantic representation of a single security group ingress permission."""
    protocol: str
    from_port: int
    to_port: int
    cidr: str

    def encompasses_port(self, port: int) -> bool:
        """Check if this rule permits traffic on the target port."""
        if self.protocol == "-1":
            return True
        return self.from_port <= port <= self.to_port


def compare_ec2_instance_types(before_type: str, after_type: str) -> str:
    """Compare two EC2 instance types conservatively.
    
    Returns:
        "SCALE_UP" or "SCALE_DOWN" if and only if both instance types belong
        to the exact same family and generation and their sizes are recognized.
        Returns "MODIFIED" for cross-family, cross-generation, or ambiguous comparisons.
    """
    if not before_type or not after_type or before_type == after_type:
        return "MODIFIED"

    parts_before = before_type.split(".")
    parts_after = after_type.split(".")

    if len(parts_before) != 2 or len(parts_after) != 2:
        return "MODIFIED"

    family_before, size_before = parts_before[0].lower(), parts_before[1].lower()
    family_after, size_after = parts_after[0].lower(), parts_after[1].lower()

    # Only compare sizing direction within the exact same family and generation
    if family_before == family_after:
        if size_before in EC2_SIZE_ORDER and size_after in EC2_SIZE_ORDER:
            idx_before = EC2_SIZE_ORDER.index(size_before)
            idx_after = EC2_SIZE_ORDER.index(size_after)
            if idx_after > idx_before:
                return "SCALE_UP"
            elif idx_after < idx_before:
                return "SCALE_DOWN"

    return "MODIFIED"


def extract_public_ingress_rules(attributes: Optional[dict[str, Any]]) -> set[SemanticIngressRule]:
    """Extract all public ingress rules (0.0.0.0/0 and ::/0) semantically from SG attributes."""
    if not attributes or not isinstance(attributes, dict):
        return set()

    ingress_blocks = attributes.get("ingress", [])
    if not isinstance(ingress_blocks, list):
        return set()

    public_rules: set[SemanticIngressRule] = set()

    for block in ingress_blocks:
        if not isinstance(block, dict):
            continue

        raw_protocol = block.get("protocol", "tcp")
        protocol = str(raw_protocol).lower() if raw_protocol is not None else "-1"
        if protocol in ("all", "-1"):
            protocol = "-1"

        raw_from = block.get("from_port")
        raw_to = block.get("to_port")
        from_port = int(raw_from) if raw_from is not None else 0
        to_port = int(raw_to) if raw_to is not None else 0

        # Protocol -1 normalizes ports to 0
        if protocol == "-1":
            from_port = 0
            to_port = 0

        # Check IPv4 CIDRs
        ipv4_cidrs = block.get("cidr_blocks") or []
        if isinstance(ipv4_cidrs, list):
            for cidr in ipv4_cidrs:
                if cidr in PUBLIC_CIDRS:
                    public_rules.add(SemanticIngressRule(protocol, from_port, to_port, cidr))

        # Check IPv6 CIDRs
        ipv6_cidrs = block.get("ipv6_cidr_blocks") or []
        if isinstance(ipv6_cidrs, list):
            for cidr in ipv6_cidrs:
                if cidr in PUBLIC_CIDRS:
                    public_rules.add(SemanticIngressRule(protocol, from_port, to_port, cidr))

    return public_rules


def extract_new_public_ingress_rules(
    before_attrs: Optional[dict[str, Any]],
    after_attrs: Optional[dict[str, Any]]
) -> list[SemanticIngressRule]:
    """Compute the semantic difference of public ingress rules newly introduced in after.
    
    Pre-existing public rules in before will NOT appear in the returned list.
    """
    public_before = extract_public_ingress_rules(before_attrs)
    public_after = extract_public_ingress_rules(after_attrs)

    new_rules = public_after - public_before
    # Deterministic sorting
    return sorted(list(new_rules), key=lambda r: (r.protocol, r.from_port, r.to_port, r.cidr))
