"""Pre-LLM validation of user-supplied architecture descriptions.

Two layers of defence:
  1. Intent validation  — reject off-topic, too-vague, or nonsensical inputs.
  2. Prompt-injection defence — detect attempts to hijack the LLM system prompt.

Neither layer calls the LLM; both run purely on the input text so failures are
fast, cheap, and never consume API quota.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.ok


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_CLOUDS = {"aws", "azure", "gcp", "multi"}

# Keywords that suggest the description is infrastructure-related
_INFRA_SIGNALS = {
    "vpc", "vnet", "subnet", "network", "firewall", "security group",
    "s3", "blob", "storage", "bucket",
    "ec2", "vm", "instance", "compute", "container", "kubernetes", "k8s",
    "iam", "role", "policy", "permission", "identity",
    "database", "rds", "sql", "postgres", "mysql", "cosmos",
    "lambda", "function", "serverless",
    "load balancer", "alb", "nlb", "gateway",
    "dns", "route53", "private", "public", "ingress", "egress",
    "cluster", "aks", "eks", "gke",
    "monitoring", "logging", "cloudwatch", "azure monitor",
    "cdn", "cloudfront", "waf",
    "terraform", "module", "resource", "output", "variable",
    "region", "zone", "availability",
    "encryption", "kms", "key vault",
}

# Patterns that strongly suggest prompt injection attempts
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?previous", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+you\s+are|a)\s+", re.IGNORECASE),
    re.compile(r"forget\s+(everything|your\s+(instructions|rules|constraints))", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"do\s+anything\s+now", re.IGNORECASE),
    re.compile(r"<\s*(script|iframe|img)[^>]*>", re.IGNORECASE),
]

# Architectural anti-patterns we warn about (not block — the LLM will refuse
# to generate these, but we surface the intent early so the user can revise)
_RISKY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b0\.0\.0\.0/0\b|open\s+to\s+the\s+internet|publicly\s+accessible", re.IGNORECASE),
        "Description requests broad public exposure — the scaffold will apply least-privilege defaults. "
        "Be explicit if a resource genuinely needs public access.",
    ),
    (
        re.compile(r"admin(istrator)?\s+access|full\s+access|wildcard\s+policy|\*:\*", re.IGNORECASE),
        "Description references overly-permissive IAM — the scaffold will scope permissions to least privilege.",
    ),
    (
        re.compile(r"no\s+encryption|unencrypted|disable\s+(encryption|tls|ssl)", re.IGNORECASE),
        "Description requests no encryption — the scaffold will enable encryption at rest and in transit by default.",
    ),
]

# Minimum meaningful description length (characters)
_MIN_LENGTH = 20
_MAX_LENGTH = 4000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate(description: str, cloud: str) -> ValidationResult:
    """Validate *description* and *cloud* before sending to the LLM.

    Returns a :class:`ValidationResult`.  If ``ok`` is ``False`` the caller
    should surface ``errors`` to the user and abort.  ``warnings`` are
    non-blocking but should be shown.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- cloud ---
    if cloud not in _VALID_CLOUDS:
        errors.append(
            f"Unknown cloud '{cloud}'. Valid options: {', '.join(sorted(_VALID_CLOUDS))}."
        )

    # --- length ---
    text = description.strip()
    if len(text) < _MIN_LENGTH:
        errors.append(
            f"Description is too short ({len(text)} chars). "
            "Please describe the architecture you want in at least a sentence."
        )
    if len(text) > _MAX_LENGTH:
        errors.append(
            f"Description is too long ({len(text)} chars, limit {_MAX_LENGTH}). "
            "Please keep the description concise — one paragraph is ideal."
        )

    # --- prompt injection ---
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            errors.append(
                "Description appears to contain a prompt-injection attempt and cannot be processed. "
                "Please describe your cloud architecture in plain technical language."
            )
            break  # one error is enough

    # Only continue further checks if no hard errors yet
    if not errors:
        # --- intent (is this infra-related?) ---
        lower = text.lower()
        matched_signals = sum(1 for sig in _INFRA_SIGNALS if sig in lower)
        if matched_signals == 0:
            errors.append(
                "Description doesn't appear to describe a cloud architecture. "
                "Please include infrastructure terms (e.g. VPC, subnet, EC2, IAM, storage)."
            )

        # --- architectural risk warnings ---
        for pattern, message in _RISKY_PATTERNS:
            if pattern.search(text):
                warnings.append(message)

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)
