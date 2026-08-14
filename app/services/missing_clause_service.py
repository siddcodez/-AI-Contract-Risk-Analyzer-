"""Missing-clause detection service.

Implements deterministic missing-clause detection by comparing the set of
detected/classified clause types against an organization-configurable list of
expected clause types for the relevant contract type.

The missing/present decision is authoritative and deterministic:
Missing = Expected - Detected.
No LLM hallucination of missing clause content is permitted.
"""

import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.missing_clause import MissingClause
from app.repositories import (
    contract_chunk_repo,
    missing_clause_repo,
    risk_finding_repo,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Canonical Clause Types and Synonyms Mapping
# ---------------------------------------------------------------------------

CANONICAL_CLAUSE_TYPES: dict[str, str] = {
    "indemnity": "indemnification",
    "indemnification": "indemnification",
    "limitation_of_liability": "limitation_of_liability",
    "liability": "limitation_of_liability",
    "termination": "termination",
    "payment_terms": "payment_terms",
    "payment": "payment_terms",
    "intellectual_property": "intellectual_property",
    "ip": "intellectual_property",
    "confidentiality": "confidentiality",
    "non_disclosure": "confidentiality",
    "nda": "confidentiality",
    "non_compete": "non_compete",
    "non_solicitation": "non_solicitation",
    "governing_law": "governing_law",
    "jurisdiction": "governing_law",
    "dispute_resolution": "dispute_resolution",
    "arbitration": "dispute_resolution",
    "warranty": "warranty",
    "warranties": "warranty",
    "insurance": "insurance",
    "data_protection": "data_protection",
    "data_privacy": "data_protection",
    "privacy": "data_protection",
    "security": "data_protection",
    "force_majeure": "force_majeure",
    "assignment": "assignment",
    "renewal": "renewal",
    "auto_renewal": "renewal",
    "sla": "sla",
    "service_level": "sla",
    "compliance": "compliance",
}

CLAUSE_DISPLAY_NAMES: dict[str, str] = {
    "indemnification": "indemnification",
    "limitation_of_liability": "limitation of liability",
    "termination": "termination",
    "payment_terms": "payment terms",
    "intellectual_property": "intellectual property",
    "confidentiality": "confidentiality",
    "non_compete": "non-compete",
    "non_solicitation": "non-solicitation",
    "governing_law": "governing law",
    "dispute_resolution": "dispute resolution",
    "warranty": "warranty",
    "insurance": "insurance",
    "data_protection": "data protection",
    "force_majeure": "force majeure",
    "assignment": "assignment",
    "renewal": "renewal",
    "sla": "service level agreement (SLA)",
    "compliance": "regulatory compliance",
}

# Regex patterns for direct text-level clause detection across chunks
CLAUSE_DETECTION_PATTERNS: dict[str, list[str]] = {
    "indemnification": [
        r"\bindemni(fy|fication|fies)\b",
        r"\bhold harmless\b",
        r"\bdefend.*claims\b",
    ],
    "limitation_of_liability": [
        r"\blimitation of liability\b",
        r"\blimit(ed|ing)?.*liability\b",
        r"\bliability.*cap\b",
        r"\baggregate liability\b",
    ],
    "confidentiality": [
        r"\bconfidential(ity)?\b",
        r"\bnon-disclosure\b",
        r"\bproprietary information\b",
    ],
    "termination": [
        r"\bterminat(e|ion|ed|ing)\b",
        r"\bcancellation.*notice\b",
        r"\bright to terminate\b",
    ],
    "payment_terms": [
        r"\bpayment terms\b",
        r"\binvoices?\b",
        r"\bfees?\b",
        r"\bnet\s*(?:30|60|90|15|45)\b",
    ],
    "intellectual_property": [
        r"\bintellectual property\b",
        r"\bwork for hire\b",
        r"\bcopyrights?\b",
        r"\bpatents?\b",
        r"\bip ownership\b",
    ],
    "non_compete": [
        r"\bnon-compete\b",
        r"\bnot.*compet(e|ition)\b",
        r"\bcompetitive activity\b",
    ],
    "non_solicitation": [
        r"\bnon-solicit(ation)?\b",
        r"\bnot.*solicit.*employ\b",
        r"\bhire.*employee\b",
    ],
    "governing_law": [
        r"\bgoverning law\b",
        r"\bgoverned by.*laws\b",
        r"\bjurisdiction\b",
    ],
    "dispute_resolution": [
        r"\bdispute resolution\b",
        r"\barbitrat(e|ion)\b",
        r"\bmediation\b",
    ],
    "warranty": [
        r"\bwarrant(y|ies|ed)\b",
        r"\brepresentations? and warranties\b",
        r"\bas is\b",
    ],
    "insurance": [
        r"\binsurance\b",
        r"\bcommercial general liability\b",
        r"\bcyber liability\b",
    ],
    "data_protection": [
        r"\bdata protection\b",
        r"\bdata privacy\b",
        r"\bpersonal data\b",
        r"\bgdpr\b",
        r"\bccpa\b",
        r"\bdata processing\b",
        r"\bsoc\s*2\b",
    ],
    "force_majeure": [
        r"\bforce majeure\b",
        r"\bacts? of god\b",
        r"\bunforeseeable circumstances\b",
    ],
    "assignment": [
        r"\bassignment\b",
        r"\bassign.*rights\b",
        r"\btransfer.*agreement\b",
    ],
    "renewal": [
        r"\bauto-?renew(al)?\b",
        r"\bautomatic(ally)? renew\b",
        r"\bsuccessive terms\b",
    ],
    "sla": [
        r"\bservice level\b",
        r"\buptime\b",
        r"\bsla\b",
        r"\bavailability\b",
    ],
}

# ---------------------------------------------------------------------------
# Default Expected Clause Sets per Contract Type
# ---------------------------------------------------------------------------

DEFAULT_EXPECTED_CLAUSES: dict[str, list[str]] = {
    "vendor_msa": [
        "confidentiality",
        "limitation_of_liability",
        "indemnification",
        "termination",
        "payment_terms",
        "data_protection",
        "governing_law",
        "dispute_resolution",
        "insurance",
        "warranty",
    ],
    "saas_msa": [
        "confidentiality",
        "limitation_of_liability",
        "indemnification",
        "termination",
        "payment_terms",
        "data_protection",
        "sla",
        "intellectual_property",
        "governing_law",
        "dispute_resolution",
    ],
    "nda": [
        "confidentiality",
        "termination",
        "governing_law",
        "dispute_resolution",
    ],
    "employment": [
        "confidentiality",
        "termination",
        "intellectual_property",
        "non_compete",
        "non_solicitation",
        "governing_law",
    ],
    "general_commercial": [
        "confidentiality",
        "limitation_of_liability",
        "indemnification",
        "termination",
        "payment_terms",
        "governing_law",
        "dispute_resolution",
    ],
}


def normalize_clause_type(raw_type: str) -> str:
    """Normalize a clause type string to its canonical representation."""
    cleaned = raw_type.strip().lower().replace("-", "_").replace(" ", "_")
    return CANONICAL_CLAUSE_TYPES.get(cleaned, cleaned)


def normalize_contract_type(raw_contract_type: str | None) -> str:
    """Normalize contract type into canonical key."""
    if not raw_contract_type:
        return "general_commercial"
    low = raw_contract_type.strip().lower()
    if "nda" in low or "non-disclosure" in low or "nondisclosure" in low:
        return "nda"
    if "saas" in low:
        return "saas_msa"
    if "vendor" in low or "supplier" in low or "master service" in low or "msa" in low:
        return "vendor_msa"
    if "employ" in low:
        return "employment"
    return "general_commercial"


def get_expected_clauses(
    contract_type: str,
    org_overrides: dict[str, list[str]] | None = None,
) -> list[str]:
    """Retrieve expected clause types for a contract type, applying any tenant overrides."""
    norm_type = normalize_contract_type(contract_type)
    if org_overrides and norm_type in org_overrides:
        raw_list = org_overrides[norm_type]
    else:
        raw_list = DEFAULT_EXPECTED_CLAUSES.get(
            norm_type, DEFAULT_EXPECTED_CLAUSES["general_commercial"]
        )

    # Normalize all clause types and return deduplicated ordered list
    seen: set[str] = set()
    result: list[str] = []
    for c in raw_list:
        normalized = normalize_clause_type(c)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def detect_present_clauses_from_text(chunks_text: list[str]) -> set[str]:
    """Scan raw chunk text against clause detection patterns."""
    detected: set[str] = set()
    combined_text = "\n\n".join(chunks_text)

    for clause_type, patterns in CLAUSE_DETECTION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                detected.add(clause_type)
                break
    return detected


async def detect_missing_clauses(
    session: AsyncSession,
    *,
    contract_id: uuid.UUID,
    version_id: uuid.UUID,
    org_id: uuid.UUID,
    contract_type: str = "general_commercial",
    org_overrides: dict[str, list[str]] | None = None,
) -> list[MissingClause]:
    """Detect and persist missing clauses for a specific contract version.

    Flow:
        1. Resolve expected clause types for this contract type.
        2. Identify detected clauses from classified RiskFindings and chunk text patterns.
        3. Compute Missing = Expected - Detected.
        4. Generate deterministic confidence and factual explanation.
        5. Clear previous missing clauses for (contract_id, version_id) for idempotency.
        6. Bulk insert new MissingClause records and return them.

    Args:
        session: Active database session with tenant context set.
        contract_id: UUID of the parent contract.
        version_id: UUID of the contract version.
        org_id: UUID of the owning organization.
        contract_type: Type of contract (e.g. 'vendor_msa', 'nda').
        org_overrides: Optional organization-specific playbook clause mapping.

    Returns:
        List of created MissingClause records.
    """
    logger.info(
        "missing_clause_detection_started",
        contract_id=str(contract_id),
        version_id=str(version_id),
        org_id=str(org_id),
        contract_type=contract_type,
    )

    # 1. Expected clauses
    expected_clauses = get_expected_clauses(contract_type, org_overrides)

    # 2. Detected clauses from classified RiskFindings
    findings = await risk_finding_repo.list_by_contract(session, contract_id, limit=200)
    detected_from_findings: set[str] = set()
    for f in findings:
        if f.version_id == version_id:
            cat_name = f.category.value if hasattr(f.category, "value") else str(f.category)
            detected_from_findings.add(normalize_clause_type(cat_name))

    # Detected clauses from chunk text
    chunks = await contract_chunk_repo.list_by_contract(session, contract_id)
    version_chunks_text = [c.content for c in chunks if c.version_id == version_id]
    detected_from_text = detect_present_clauses_from_text(version_chunks_text)

    # Union of all structured classifications
    detected_clauses = detected_from_findings | detected_from_text

    # 3. Calculate missing set
    missing_clause_types = [c for c in expected_clauses if c not in detected_clauses]

    # 4. Generate deterministic records
    # Base confidence: 0.95 if chunks exist and text was processed, 0.50 if no text was found
    has_text = len(version_chunks_text) > 0
    confidence = 0.95 if has_text else 0.50

    missing_items: list[dict[str, Any]] = []
    for c_type in missing_clause_types:
        display_name = CLAUSE_DISPLAY_NAMES.get(c_type, c_type.replace("_", " "))
        reason = (
            f"No {display_name} clause was identified among the classified clauses "
            f"for this contract version."
        )
        missing_items.append(
            {
                "id": uuid.uuid4(),
                "contract_id": contract_id,
                "version_id": version_id,
                "org_id": org_id,
                "clause_type": c_type,
                "confidence": confidence,
                "reason": reason,
                "status": "missing",
                "metadata_json": {
                    "contract_type": contract_type,
                    "expected_count": len(expected_clauses),
                    "detected_count": len(detected_clauses),
                },
            }
        )

    # 5. Idempotent persistence: clear old and bulk insert new
    await missing_clause_repo.delete_by_contract_and_version(session, contract_id, version_id)

    persisted_records: list[MissingClause] = []
    if missing_items:
        persisted_records = await missing_clause_repo.bulk_create(session, items=missing_items)

    await session.flush()

    logger.info(
        "missing_clause_detection_completed",
        contract_id=str(contract_id),
        version_id=str(version_id),
        org_id=str(org_id),
        expected_count=len(expected_clauses),
        detected_count=len(detected_clauses),
        missing_count=len(persisted_records),
    )

    return persisted_records
