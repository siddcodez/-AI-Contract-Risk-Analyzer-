"""Contract analysis and playbook API endpoints.

POST /api/v1/contracts/analyze
    Accepts raw contract text (JSON body) or uploaded file (multipart).
    Returns clause-level risk classifications, risk score, and suggested redlines.

GET /api/v1/playbooks
    Returns available playbook metadata and default rules.

POST /api/v1/contracts/export
    Accepts analysis result object and export format, returns formatted report.
"""

import re
import uuid
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.logging import get_logger

router = APIRouter(prefix="/contracts", tags=["contracts"])
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class AnalyzeTextRequest(BaseModel):
    text: str = Field(..., min_length=50, description="Raw contract text to analyze")
    playbook: str = Field("standard", description="Playbook key to apply")
    sensitivity: str = Field("standard", description="Risk sensitivity: strict|standard|permissive")
    contract_name: str = Field("Uploaded Contract", description="Display name for the contract")


class ClauseResult(BaseModel):
    id: str
    type: str
    severity: str
    snippet: str
    original: str
    risk: str
    redline: str | None
    page_hint: int


class AnalyzeResponse(BaseModel):
    contract_id: str
    name: str
    type: str
    pages: int
    size: str
    score: int
    clauses: list[ClauseResult]
    playbook: str
    sensitivity: str


class ExportRequest(BaseModel):
    analysis: dict[str, Any]
    format: str = Field("json", description="Export format: json|markdown|html")


# ---------------------------------------------------------------------------
# Clause classification engine (server-side mirror of client NLP engine)
# ---------------------------------------------------------------------------

CLAUSE_PATTERNS: list[dict[str, Any]] = [
    {
        "type": "Indemnification",
        "patterns": [r"indemni(?:fy|fication)", r"hold harmless", r"defend.*claims"],
        "risk_standard": "high",
        "risk_strict": "critical",
        "risk_permissive": "medium",
        "base_score": 30,
        "risk_text": (
            "Indemnification clauses transfer liability risk. Broad or one-sided indemnification "
            "obligations can expose your organisation to significant uncapped financial liability."
        ),
        "redline_template": (
            "Indemnification obligations shall be limited to direct damages arising from the "
            "indemnifying party's own gross negligence or wilful misconduct, capped at fees paid "
            "in the preceding 12 months."
        ),
    },
    {
        "type": "Limitation of Liability",
        "patterns": [r"limitation of liability", r"limit(?:ed|ing).*liability", r"liability.*cap"],
        "risk_standard": "medium",
        "risk_strict": "high",
        "risk_permissive": "safe",
        "base_score": 15,
        "risk_text": (
            "Liability caps protect both parties but an unusually low cap (e.g., $500 flat) "
            "fails to cover real-world damages from data breaches, service outages, or breaches."
        ),
        "redline_template": (
            "Total liability shall not exceed the greater of (a) fees paid in the preceding "
            "12 months or (b) [INSERT MINIMUM FLOOR]. Exclusions apply for gross negligence, "
            "wilful misconduct, and data breaches."
        ),
    },
    {
        "type": "Confidentiality",
        "patterns": [r"confidential(?:ity)?", r"non-disclosure", r"proprietary information"],
        "risk_standard": "safe",
        "risk_strict": "medium",
        "risk_permissive": "safe",
        "base_score": 5,
        "risk_text": (
            "Confidentiality obligations are standard in commercial agreements. Review the "
            "definition of Confidential Information, term length, and any residuals carve-outs."
        ),
        "redline_template": None,
    },
    {
        "type": "Non-Compete",
        "patterns": [r"non-compete", r"not.*compet", r"competitive activit"],
        "risk_standard": "critical",
        "risk_strict": "critical",
        "risk_permissive": "high",
        "base_score": 35,
        "risk_text": (
            "Broad non-compete clauses (e.g., worldwide, multi-year) are unenforceable in many "
            "jurisdictions (CA, MN, ND ban them outright) and may create costly litigation."
        ),
        "redline_template": (
            "Non-compete restrictions shall be limited to [YOUR STATE/REGION], restricted to "
            "directly competing roles, for a maximum period of [ONE (1)] year, with compensation "
            "paid during the restriction period."
        ),
    },
    {
        "type": "Non-Solicitation",
        "patterns": [r"non-solicit", r"not.*solicit.*employ", r"hire.*employee"],
        "risk_standard": "high",
        "risk_strict": "high",
        "risk_permissive": "medium",
        "base_score": 20,
        "risk_text": (
            "Non-solicitation clauses restrict talent acquisition. Overly broad language "
            "('anyone involved in any capacity') may unintentionally restrict general hiring."
        ),
        "redline_template": (
            "Restrictions shall apply only to direct solicitation of key personnel with whom "
            "there was direct contact under this Agreement, for a period of [ONE (1)] year. "
            "General job postings shall not be restricted."
        ),
    },
    {
        "type": "Governing Law",
        "patterns": [r"governing law", r"governed by.*laws", r"jurisdiction"],
        "risk_standard": "medium",
        "risk_strict": "medium",
        "risk_permissive": "safe",
        "base_score": 10,
        "risk_text": (
            "Governing law and jurisdiction determine where disputes are litigated. "
            "Foreign or inconvenient jurisdictions can materially increase litigation costs."
        ),
        "redline_template": (
            "Consider negotiating for [YOUR JURISDICTION]. Alternatively, propose binding "
            "arbitration under [AAA/JAMS] rules as a neutral, cost-effective alternative."
        ),
    },
    {
        "type": "Auto-Renewal",
        "patterns": [r"auto.?renew", r"automatic(?:ally)? renew", r"renew.*unless.*notice"],
        "risk_standard": "medium",
        "risk_strict": "high",
        "risk_permissive": "safe",
        "base_score": 15,
        "risk_text": (
            "Auto-renewal with long notice periods (90+ days) limits operational flexibility "
            "and creates risk of unintended multi-year commitments."
        ),
        "redline_template": (
            "Reduce non-renewal notice period to [30/60] days. Include automated reminder "
            "at [90] days before renewal. Allow pro-rata refund on accidental renewal."
        ),
    },
    {
        "type": "Data Processing",
        "patterns": [
            r"data.*processing",
            r"personal data",
            r"gdpr",
            r"data.*license",
            r"data.*ownership",
        ],
        "risk_standard": "critical",
        "risk_strict": "critical",
        "risk_permissive": "high",
        "base_score": 40,
        "risk_text": (
            "Data processing clauses granting vendors perpetual or irrevocable licenses to "
            "customer data for their own commercial purposes are a GDPR/CCPA risk and create "
            "serious IP and competitive intelligence exposure."
        ),
        "redline_template": (
            "Vendor shall not use Customer Data for any purpose other than providing the "
            "contracted services. Vendor acquires no ownership or license to Customer Data. "
            "All Customer Data remains the exclusive property of Customer."
        ),
    },
    {
        "type": "Service Level Agreement",
        "patterns": [r"service level", r"uptime", r"availability", r"sla"],
        "risk_standard": "high",
        "risk_strict": "critical",
        "risk_permissive": "medium",
        "base_score": 20,
        "risk_text": (
            "'Commercially reasonable efforts' without defined SLAs or meaningful remedies "
            "provides no enforceable guarantee. 99% uptime allows ~87 hours of annual downtime."
        ),
        "redline_template": (
            "Vendor guarantees 99.9% monthly uptime. Excess downtime entitles Customer to "
            "service credits of [5%] of monthly fees per hour, up to [30%] monthly cap. "
            "Planned maintenance excluded only with 72-hour prior notice."
        ),
    },
    {
        "type": "Intellectual Property",
        "patterns": [
            r"intellectual property",
            r"ip.*ownership",
            r"work.*for.*hire",
            r"assignment.*ip",
        ],
        "risk_standard": "safe",
        "risk_strict": "medium",
        "risk_permissive": "safe",
        "base_score": 8,
        "risk_text": (
            "IP ownership clauses should clearly attribute pre-existing and newly created IP. "
            "Verify that custom development commissioned under a SOW is customer-owned."
        ),
        "redline_template": None,
    },
    {
        "type": "Termination",
        "patterns": [r"terminat(?:ion|e)", r"cancellation.*notice", r"right to terminate"],
        "risk_standard": "medium",
        "risk_strict": "high",
        "risk_permissive": "safe",
        "base_score": 12,
        "risk_text": (
            "Termination clauses define exit rights. One-sided termination rights or lack of "
            "cure periods for immaterial breaches create operational risk."
        ),
        "redline_template": (
            "Either party may terminate for material breach with [30-day] written notice "
            "and opportunity to cure. Convenience termination requires [90-day] notice with "
            "pro-rata refund of prepaid fees."
        ),
    },
    {
        "type": "Arbitration",
        "patterns": [r"arbitrat(?:ion|e)", r"waive.*jury", r"class action.*waiv"],
        "risk_standard": "high",
        "risk_strict": "high",
        "risk_permissive": "medium",
        "base_score": 20,
        "risk_text": (
            "Mandatory arbitration with class action waiver may be unenforceable for certain "
            "employment or consumer claims. Pre-dispute arbitration clauses face "
            "regulatory scrutiny."
        ),
        "redline_template": (
            "Specify a neutral arbitration provider (JAMS/AAA), employer-paid fees, "
            "carve-outs for injunctive relief, and opt-out rights for individual statutory claims."
        ),
    },
]

SENSITIVITY_MAP = {
    "strict": "risk_strict",
    "standard": "risk_standard",
    "permissive": "risk_permissive",
}
SEVERITY_SCORE = {"critical": 40, "high": 25, "medium": 12, "safe": 3}


def classify_clauses(text: str, sensitivity: str = "standard") -> list[dict[str, Any]]:
    """Simple regex-based clause classifier that mirrors the client-side NLP engine."""
    severity_key = SENSITIVITY_MAP.get(sensitivity, "risk_standard")
    paragraphs = re.split(r"\n{2,}", text)

    found_clauses: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    for i, para in enumerate(paragraphs):
        for rule in CLAUSE_PATTERNS:
            for pattern in rule["patterns"]:
                if re.search(pattern, para, re.IGNORECASE):
                    clause_id = f"clause_{uuid.uuid4().hex[:6]}"
                    while clause_id in used_ids:
                        clause_id = f"clause_{uuid.uuid4().hex[:6]}"
                    used_ids.add(clause_id)
                    severity = rule[severity_key]
                    snippet = (
                        para[:120].replace("\n", " ").strip() + "…" if len(para) > 120 else para
                    )
                    found_clauses.append(
                        {
                            "id": clause_id,
                            "type": rule["type"],
                            "severity": severity,
                            "snippet": snippet,
                            "original": para[:600].strip(),
                            "risk": rule["risk_text"],
                            "redline": rule["redline_template"],
                            "page_hint": max(1, (i // 3) + 1),
                        }
                    )
                    break  # only match each rule once per paragraph

    return found_clauses


def compute_risk_score(clauses: list[dict[str, Any]], sensitivity: str = "standard") -> int:
    """Compute aggregate risk score 0-100 from clause severities."""
    if not clauses:
        return 0
    total = sum(SEVERITY_SCORE.get(c["severity"], 0) for c in clauses)
    max_possible = len(clauses) * 40
    raw = int((total / max_possible) * 100) if max_possible else 0
    # Sensitivity modifier
    mod = {"strict": 1.15, "standard": 1.0, "permissive": 0.85}.get(sensitivity, 1.0)
    return min(100, int(raw * mod))


def infer_contract_type(text: str, playbook: str) -> str:
    if playbook != "standard":
        return playbook.upper()
    low = text.lower()
    if "non-disclosure" in low or "nda" in low:
        return "NDA"
    if "employment" in low or "employee" in low:
        return "Employment"
    if "saas" in low or "subscription" in low:
        return "SaaS / MSA"
    if "vendor" in low or "supplier" in low:
        return "Vendor"
    return "General Commercial"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/analyze", response_model=AnalyzeResponse, summary="Analyze contract text")
async def analyze_contract(request: AnalyzeTextRequest) -> JSONResponse:
    """Classify clauses, compute risk score, and return redline suggestions."""
    logger.info(
        "Analyzing contract text",
        name=request.contract_name,
        playbook=request.playbook,
        sensitivity=request.sensitivity,
        text_len=len(request.text),
    )

    clauses = classify_clauses(request.text, request.sensitivity)
    score = compute_risk_score(clauses, request.sensitivity)
    contract_type = infer_contract_type(request.text, request.playbook)

    # Estimate page count (~500 words/page)
    word_count = len(request.text.split())
    pages = max(1, round(word_count / 500))

    # Estimate text size
    byte_size = len(request.text.encode("utf-8"))
    if byte_size < 1024:
        size_str = f"{byte_size} B"
    elif byte_size < 1_048_576:
        size_str = f"{byte_size // 1024} KB"
    else:
        size_str = f"{byte_size / 1_048_576:.1f} MB"

    return JSONResponse(
        content={
            "contract_id": str(uuid.uuid4()),
            "name": request.contract_name,
            "type": contract_type,
            "pages": pages,
            "size": size_str,
            "score": score,
            "clauses": clauses,
            "playbook": request.playbook,
            "sensitivity": request.sensitivity,
        }
    )


@router.post("/analyze-file", summary="Analyze uploaded contract file")
async def analyze_contract_file(
    file: UploadFile = File(...),
    playbook: str = Form("standard"),
    sensitivity: str = Form("standard"),
) -> JSONResponse:
    """Accept a file upload (TXT only server-side; PDF/DOCX handled client-side)."""
    not_txt = file.content_type not in ("text/plain",) and not (
        file.filename or ""
    ).lower().endswith(".txt")
    if not_txt:
        raise HTTPException(
            status_code=415,
            detail="Server-side parsing supports TXT only. Use client-side analysis for PDF/DOCX.",
        )

    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    req = AnalyzeTextRequest(
        text=text,
        playbook=playbook,
        sensitivity=sensitivity,
        contract_name=file.filename or "Uploaded Contract",
    )
    return await analyze_contract(req)


@router.get("/playbooks", summary="List available playbooks")
async def list_playbooks() -> JSONResponse:
    """Return all available playbooks with their metadata."""
    return JSONResponse(
        content={
            "playbooks": [
                {
                    "key": "standard",
                    "name": "Standard Risk Playbook",
                    "description": "Balanced risk assessment for general commercial contracts.",
                    "icon": "⚖️",
                    "clause_types": [r["type"] for r in CLAUSE_PATTERNS],
                },
                {
                    "key": "nda",
                    "name": "NDA Playbook",
                    "description": "Optimized for non-disclosure and confidentiality agreements.",
                    "icon": "🤫",
                    "clause_types": [
                        "Confidentiality",
                        "Non-Solicitation",
                        "Governing Law",
                        "Termination",
                    ],
                },
                {
                    "key": "vendor",
                    "name": "Vendor Agreement Playbook",
                    "description": "Focused on vendor/supplier and software procurement risks.",
                    "icon": "📦",
                    "clause_types": [
                        "Limitation of Liability",
                        "Data Processing",
                        "Service Level Agreement",
                        "Indemnification",
                        "Intellectual Property",
                        "Auto-Renewal",
                    ],
                },
                {
                    "key": "employment",
                    "name": "Employment Playbook",
                    "description": "Executive and general employment contract risk review.",
                    "icon": "👤",
                    "clause_types": [
                        "Non-Compete",
                        "Non-Solicitation",
                        "Arbitration",
                        "Termination",
                    ],
                },
                {
                    "key": "saas",
                    "name": "SaaS / MSA Playbook",
                    "description": "Software-as-a-Service and master service agreement analysis.",
                    "icon": "☁️",
                    "clause_types": [
                        "Service Level Agreement",
                        "Data Processing",
                        "Limitation of Liability",
                        "Auto-Renewal",
                        "Intellectual Property",
                    ],
                },
            ]
        }
    )


@router.post("/export", summary="Export analysis report")
async def export_report(request: ExportRequest) -> JSONResponse:
    """Generate formatted export of contract analysis results."""
    analysis = request.analysis
    fmt = request.format.lower()

    if fmt == "json":
        return JSONResponse(content={"format": "json", "data": analysis})

    if fmt == "markdown":
        clauses = analysis.get("clauses", [])
        lines = [
            "# Contract Risk Analysis Report",
            "",
            f"**Contract:** {analysis.get('name', 'Unknown')}",
            f"**Type:** {analysis.get('type', '—')}",
            f"**Risk Score:** {analysis.get('score', 0)}/100",
            f"**Playbook:** {analysis.get('playbook', 'standard')}",
            f"**Clauses Analyzed:** {len(clauses)}",
            "",
            "---",
            "",
            "## Identified Clauses",
            "",
        ]
        for c in clauses:
            lines += [
                f"### {c.get('type', 'Unknown')} — `{c.get('severity', '').upper()}`",
                "",
                f"**Snippet:** {c.get('snippet', '')}",
                "",
                f"**Risk Analysis:** {c.get('risk', '')}",
                "",
            ]
            if c.get("redline"):
                lines += ["**Suggested Redline:**", f"> {c['redline']}", ""]
            lines.append("---")
            lines.append("")

        return JSONResponse(content={"format": "markdown", "data": "\n".join(lines)})

    raise HTTPException(status_code=400, detail=f"Unsupported export format: {fmt}")
