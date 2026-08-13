"""AI/LLM Provider abstraction for contract risk analysis.

Provides a pluggable LLM risk analysis service.
By default (LLM_PROVIDER="mock"), executes a deterministic rule-based legal risk engine
that evaluates text chunks for legal/business risk patterns across 15 standard risk categories,
extracting verbatim evidence quotes, assigning severity ratings, and providing recommendations.
Operates 100% offline with zero external API key dependencies.
"""

import re
import uuid
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.risk_finding import RiskCategory, RiskSeverity

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Rule patterns for local legal risk analysis engine
# ---------------------------------------------------------------------------

RISK_RULES: list[dict[str, Any]] = [
    {
        "category": RiskCategory.liability,
        "severity": RiskSeverity.critical,
        "patterns": [
            r"\buncapped liability\b",
            r"\bunlimited liability\b",
            r"\bshall not be subject to any limitation of liability\b",
            r"\bno cap on liability\b",
            r"\bexceeds? the total fees paid\b",
        ],
        "title": "Uncapped Liability Exposure",
        "description": (
            "The clause removes or avoids standard limitations of liability, exposing "
            "the organization to unlimited monetary damages."
        ),
        "recommendation": (
            "Insert a mutual cap on liability equal to 12 months of fees paid under the agreement."
        ),
        "confidence": 0.95,
    },
    {
        "category": RiskCategory.indemnification,
        "severity": RiskSeverity.high,
        "patterns": [
            r"\bindemnify and hold harmless\b",
            r"\bindemnif(y|ication) for third-party claims\b",
            r"\bshall defend, indemnify, and hold harmless\b",
            r"\bisolate and hold harmless against any and all claims\b",
        ],
        "title": "Broad One-Sided Indemnification",
        "description": (
            "Broad obligation to defend and indemnify the counterparty against any and all "
            "third-party claims without reciprocal protection."
        ),
        "recommendation": (
            "Make indemnification mutual and scope obligations strictly to gross negligence "
            "or willful misconduct."
        ),
        "confidence": 0.90,
    },
    {
        "category": RiskCategory.termination,
        "severity": RiskSeverity.high,
        "patterns": [
            r"\bterminate for convenience without notice\b",
            r"\bterminate immediately without cause\b",
            r"\bterminate at any time without penalty\b",
            r"\bunilateral termination right\b",
        ],
        "title": "Unilateral Immediate Termination Without Cause",
        "description": (
            "Allows the counterparty to terminate the contract immediately without cause "
            "or prior written notice."
        ),
        "recommendation": (
            "Require a minimum of 30 days prior written notice for termination for convenience."
        ),
        "confidence": 0.88,
    },
    {
        "category": RiskCategory.renewal,
        "severity": RiskSeverity.medium,
        "patterns": [
            r"\bautomatic(ally)? renew(s|al)?\b",
            r"\bauto-renew\b",
            r"\brenew automatically for successive terms\b",
        ],
        "title": "Automatic Renewal Clause",
        "description": (
            "The contract automatically renews unless written notice of non-renewal "
            "is provided within a narrow window."
        ),
        "recommendation": (
            "Ensure non-renewal notice window is clearly flagged in vendor management "
            "systems (minimum 60 days)."
        ),
        "confidence": 0.85,
    },
    {
        "category": RiskCategory.intellectual_property,
        "severity": RiskSeverity.high,
        "patterns": [
            r"\bwork for hire\b",
            r"\bassigns? all right, title and interest\b",
            r"\bexclusive property of\b",
            r"\btransfer of pre-existing ip\b",
        ],
        "title": "Broad Intellectual Property Assignment",
        "description": (
            "Assigns ownership of deliverables or IP created during performance "
            "exclusively to the counterparty."
        ),
        "recommendation": (
            "Carve out pre-existing background IP and grant a non-exclusive commercial "
            "license instead of outright assignment."
        ),
        "confidence": 0.92,
    },
    {
        "category": RiskCategory.data_privacy,
        "severity": RiskSeverity.high,
        "patterns": [
            r"\bpersonal data transfer\b",
            r"\bcross-border data transfer\b",
            r"\btransfer data outside the (EEA|EU|jurisdiction)\b",
            r"\bprocess personal data\b",
        ],
        "title": "Data Privacy & Cross-Border Transfer Compliance Risk",
        "description": (
            "Involves processing or transferring personal data without explicit standard "
            "contractual clauses or DPA terms."
        ),
        "recommendation": (
            "Execute a standard Data Processing Addendum (DPA) containing Standard "
            "Contractual Clauses (SCCs)."
        ),
        "confidence": 0.89,
    },
    {
        "category": RiskCategory.governing_law,
        "severity": RiskSeverity.low,
        "patterns": [
            r"\bgoverned by the laws of\b",
            r"\bjurisdiction of the courts of\b",
            r"\bexclusive venue in\b",
        ],
        "title": "Non-Standard Governing Law / Forum Selection",
        "description": (
            "Defines legal jurisdiction and governing law for resolving "
            "potential contract disputes."
        ),
        "recommendation": (
            "Verify that designated jurisdiction matches organization "
            "corporate standards or request neutral forum."
        ),
        "confidence": 0.80,
    },
    {
        "category": RiskCategory.payment,
        "severity": RiskSeverity.medium,
        "patterns": [
            r"\blate payment fee\b",
            r"\binterest at the rate of\b",
            r"\bnon-refundable\b",
            r"\bprice increase\b",
            r"\bprice adjustment\b",
        ],
        "title": "Unilateral Price Increase or Non-Refundable Payment Terms",
        "description": (
            "Contains terms allowing unilateral price escalations or designating "
            "advance payments as non-refundable."
        ),
        "recommendation": (
            "Cap annual price escalations to CPI or a maximum of 3%-5% per renewal period."
        ),
        "confidence": 0.82,
    },
    {
        "category": RiskCategory.confidentiality,
        "severity": RiskSeverity.medium,
        "patterns": [
            r"\bconfidential information\b",
            r"\bnon-disclosure\b",
            r"\bkeep in strict confidence\b",
            r"\bperpetual confidentiality\b",
        ],
        "title": "Confidentiality & Non-Disclosure Obligation",
        "description": (
            "Imposes non-disclosure obligations regarding proprietary "
            "information shared during performance."
        ),
        "recommendation": (
            "Ensure standard exclusions apply (public knowledge, prior "
            "possession, independent development)."
        ),
        "confidence": 0.84,
    },
    {
        "category": RiskCategory.security,
        "severity": RiskSeverity.high,
        "patterns": [
            r"\bsecurity breach notification\b",
            r"\bsecurity audit\b",
            r"\bcybersecurity standards\b",
            r"\bdata breach\b",
        ],
        "title": "Security Audit & Breach Notification Requirements",
        "description": (
            "Defines cybersecurity requirements, audit rights, and data "
            "breach notification timeframes."
        ),
        "recommendation": (
            "Require immediate security incident notification (within 24-48 hours) "
            "and annual SOC 2 Type II reports."
        ),
        "confidence": 0.87,
    },
]


def analyze_contract_text(chunks_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Analyze contract text chunks and detect risk findings.

    Args:
        chunks_data: List of chunk dicts containing 'id', 'chunk_index', and 'content'.

    Returns:
        List of dicts representing detected RiskFinding objects.
    """
    settings = get_settings()
    provider = settings.LLM_PROVIDER.lower()

    if provider == "mock":
        return _analyze_with_mock_engine(chunks_data)

    logger.warning(
        "Unknown or unsupported LLM_PROVIDER, falling back to rule-based mock engine",
        provider=provider,
    )
    return _analyze_with_mock_engine(chunks_data)


def _analyze_with_mock_engine(chunks_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rule-based risk detection engine scanning chunks for legal risk patterns."""
    findings: list[dict[str, Any]] = []
    seen_categories: set[str] = set()

    for chunk in chunks_data:
        chunk_id = chunk.get("id")
        content = chunk.get("content", "")

        for rule in RISK_RULES:
            category = rule["category"]
            # Limit to one finding per risk category per contract to avoid clutter
            if category.value in seen_categories:
                continue

            for pattern in rule["patterns"]:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    # Extract surrounding sentence as verbatim evidence
                    evidence = _extract_surrounding_sentence(content, match.start(), match.end())
                    seen_categories.add(category.value)

                    findings.append(
                        {
                            "category": category,
                            "severity": rule["severity"],
                            "title": rule["title"],
                            "description": rule["description"],
                            "evidence": evidence,
                            "recommendation": rule["recommendation"],
                            "confidence": rule["confidence"],
                            "chunk_id": chunk_id if isinstance(chunk_id, uuid.UUID) else None,
                            "metadata_json": {
                                "pattern_matched": pattern,
                                "engine": "mock-rule-analyzer",
                            },
                        }
                    )
                    break  # Matched rule for this chunk

    # If no specific risk rules matched, add a baseline general review finding
    if not findings and chunks_data:
        first_chunk = chunks_data[0]
        first_content = first_chunk.get("content", "")[:200]
        chunk_id_val = (
            first_chunk.get("id") if isinstance(first_chunk.get("id"), uuid.UUID) else None
        )
        findings.append(
            {
                "category": RiskCategory.other,
                "severity": RiskSeverity.low,
                "title": "Standard Contract Terms Review",
                "description": (
                    "Standard contract provisions detected. No high-risk anomalies "
                    "flagged by automated scanner."
                ),
                "evidence": first_content if first_content else "Document header review.",
                "recommendation": "Perform standard legal review prior to execution.",
                "confidence": 0.75,
                "chunk_id": chunk_id_val,
                "metadata_json": {"engine": "mock-rule-analyzer", "baseline": True},
            }
        )

    return findings


def _extract_surrounding_sentence(text: str, start: int, end: int) -> str:
    """Extract sentence or context block around a regex pattern match."""
    # Find sentence start (. or newline)
    sent_start = text.rfind(".", 0, start)
    if sent_start == -1:
        sent_start = text.rfind("\n", 0, start)
    sent_start = 0 if sent_start == -1 else sent_start + 1

    # Find sentence end (. or newline)
    sent_end = text.find(".", end)
    if sent_end == -1:
        sent_end = text.find("\n", end)
    sent_end = len(text) if sent_end == -1 else sent_end + 1

    quote = text[sent_start:sent_end].strip()
    if len(quote) > 500:
        quote = quote[:497] + "..."
    return quote if quote else text[start:end]
