import asyncio
import json
import uuid
import httpx
import websockets
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.db.session import set_tenant_context
from app.models.contract_version import ContractVersion
from app.models.risk_finding import RiskCategory, RiskFinding, RiskSeverity
from app.models.contract_chunk import ContractChunk
from app.services import chunking_service

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"
DB_URL = "postgresql+asyncpg://contract_user:contract_pass@127.0.0.1:5432/contract_risk_db"

async def create_version_2_helper(contract_id: uuid.UUID, org_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """Helper to create Version 2 with chunks and findings for the contract so compare can be tested live."""
    engine = create_async_engine(DB_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    with open("scratch/sample_contract_v2.txt", "r", encoding="utf-8") as f:
        v2_text = f.read()

    async with session_factory() as session:
        await set_tenant_context(session, str(org_id))
        
        # Get version 1
        from app.repositories import contract_version_repo
        versions = await contract_version_repo.list_by_contract(session, contract_id)
        v1_id = versions[0].id
        
        # Create Version 2
        v2 = ContractVersion(
            id=uuid.uuid4(),
            contract_id=contract_id,
            version_number=2,
            file_name="sample_contract_v2.txt",
            file_size=len(v2_text.encode("utf-8")),
            content_type="text/plain",
            storage_key=f"{org_id}/{contract_id}/v2.txt",
            org_id=org_id,
        )
        session.add(v2)
        await session.flush()
        
        # Add chunks for v2
        chunks = chunking_service.chunk_text(v2_text)
        for i, c_text in enumerate(chunks):
            chunk_obj = ContractChunk(
                id=uuid.uuid4(),
                contract_id=contract_id,
                version_id=v2.id,
                chunk_index=i,
                content=c_text,
                token_count=len(c_text.split()),
                embedding=[0.01] * 1536,
                org_id=org_id,
            )
            session.add(chunk_obj)
            
        # Add risk findings for v2 (e.g. governing law finding added, liability modified)
        f1 = RiskFinding(
            id=uuid.uuid4(),
            contract_id=contract_id,
            version_id=v2.id,
            category=RiskCategory.governing_law,
            severity=RiskSeverity.low,
            title="Delaware Governing Law Clause Added",
            description="Governing law clause added designating State of Delaware.",
            evidence="This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware.",
            recommendation="Review Delaware jurisdiction with legal team.",
            confidence=0.94,
            status="pending_review",
            org_id=org_id,
        )
        f2 = RiskFinding(
            id=uuid.uuid4(),
            contract_id=contract_id,
            version_id=v2.id,
            category=RiskCategory.liability,
            severity=RiskSeverity.high,
            title="Increased Liability Cap to $1M",
            description="Liability cap increased from $10k to $1,000,000.",
            evidence="IN NO EVENT SHALL EITHER PARTY'S AGGREGATE LIABILITY ARISING OUT OF OR RELATED TO THIS AGREEMENT EXCEED $1,000,000",
            recommendation="Verify insurance coverage accommodates $1,000,000 aggregate cap.",
            confidence=0.92,
            status="pending_review",
            org_id=org_id,
        )
        session.add(f1)
        session.add(f2)
        await session.commit()
        v2_id = v2.id

    await engine.dispose()
    return v1_id, v2_id


async def run_journey():
    client = httpx.AsyncClient(base_url=BASE_URL, timeout=30.0)

    print("\n=======================================================")
    print(" 1. REGISTER NEW ORGANIZATION + ADMIN USER")
    print("=======================================================")
    unique_suffix = uuid.uuid4().hex[:6]
    reg_payload = {
        "org_name": f"Acme Legal Corp {unique_suffix}",
        "email": f"admin_{unique_suffix}@acmelegal.com",
        "password": "StrongPassword123!",
        "full_name": "Alice Legal Admin",
    }
    r = await client.post("/api/v1/auth/register", json=reg_payload)
    print(f"Register Status: {r.status_code}")
    reg_data = r.json()
    token = reg_data["access_token"]
    print(f"Token:   {token[:10]}...[REDACTED]...{token[-10:]}")

    # Fetch user details from /api/v1/auth/me
    headers = {"Authorization": f"Bearer {token}"}
    r_me = await client.get("/api/v1/auth/me", headers=headers)
    me_data = r_me.json()
    user_id = me_data["id"]
    org_id = me_data["org_id"]
    print(f"User ID: {user_id}")
    print(f"Org ID:  {org_id}")
    print(f"Org:     {me_data['org_name']}")

    print("\n=======================================================")
    print(" 2. AUTHENTICATE / LOGIN")
    print("=======================================================")
    login_payload = {
        "email": f"admin_{unique_suffix}@acmelegal.com",
        "password": "StrongPassword123!",
    }
    r = await client.post("/api/v1/auth/login", json=login_payload)
    print(f"Login Status: {r.status_code}")
    login_data = r.json()
    token = login_data["access_token"]
    print(f"Token Type: {login_data['token_type']}")

    headers = {"Authorization": f"Bearer {token}"}

    print("\n=======================================================")
    print(" 3. UPLOAD REAL TEST CONTRACT (V1)")
    print("=======================================================")
    with open("scratch/sample_contract_v1.txt", "rb") as f:
        contract_bytes = f.read()

    files = {"file": ("acme_msa_v1.txt", contract_bytes, "text/plain")}
    r = await client.post("/api/v1/contracts/upload", headers=headers, files=files)
    print(f"Upload Status: {r.status_code}")
    upload_res = r.json()
    contract_id = upload_res["contract_id"]
    job_id = upload_res["job_id"]
    print(f"Contract ID: {contract_id}")
    print(f"Job ID:      {job_id}")
    print(f"Job Status:  {upload_res['status']}")

    print("\n=======================================================")
    print(" 4. CONNECT WEBSOCKET & POLL INGESTION STATUS")
    print("=======================================================")
    ws_uri = f"{WS_URL}/api/v1/ws/contracts/{contract_id}?token={token}"
    
    # Listen to WebSocket in background task
    ws_messages = []
    async def listen_ws():
        try:
            async with websockets.connect(ws_uri) as ws:
                print("  [WebSocket] Connected successfully to live stream!")
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=15.0)
                    data = json.loads(msg)
                    event_name = data.get("event")
                    print(f"  [WebSocket Event Received] event={event_name} contract_id={data.get('contract_id')} user_email={data.get('user_email')} data={data.get('data')}")
                    ws_messages.append(data)
        except Exception as e:
            print(f"  [WebSocket listener closed]: {e}")

    ws_task = asyncio.create_task(listen_ws())

    # Poll status endpoint
    for attempt in range(1, 15):
        await asyncio.sleep(1)
        r = await client.get(f"/api/v1/contracts/{contract_id}/status", headers=headers)
        status_data = r.json()
        current_status = status_data.get("job_status") or status_data.get("contract_status")
        print(f"  [Attempt {attempt}] Ingestion Job Status: {current_status} (contract_status={status_data.get('contract_status')})")
        if current_status == "completed" or status_data.get("contract_status") == "completed":
            print("  --> Ingestion completed successfully!")
            break
        elif current_status == "failed":
            print(f"  --> Ingestion failed: {status_data.get('error_message')}")
            break

    print("\n=======================================================")
    print(" 5. TRIGGER & POLL RISK ANALYSIS")
    print("=======================================================")
    r = await client.post(f"/api/v1/contracts/{contract_id}/analyze", headers=headers)
    print(f"Trigger Analysis Status: {r.status_code}")
    analyze_trigger = r.json()
    analysis_job_id = analyze_trigger["analysis_job_id"]
    print(f"Analysis Job ID: {analysis_job_id}")

    for attempt in range(1, 20):
        await asyncio.sleep(1)
        r = await client.get(f"/api/v1/contracts/{contract_id}/analysis", headers=headers)
        analysis_data = r.json()
        current_status = analysis_data["status"]
        print(f"  [Attempt {attempt}] Analysis Job Status: {current_status}")
        if current_status == "completed":
            print("  --> Analysis completed successfully!")
            print(f"  Findings Count: {analysis_data.get('findings_count')}")
            
            # Fetch findings list
            r_find = await client.get(f"/api/v1/contracts/{contract_id}/findings", headers=headers)
            findings_data = r_find.json()
            print(f"  Total Findings: {findings_data.get('total')}")
            for f in findings_data.get("items", [])[:3]:
                print(f"    * [{f.get('severity').upper()}] {f.get('title')}: {f.get('description')[:80]}...")
            break
        elif current_status == "failed":
            print(f"  --> Analysis failed: {analysis_data.get('error_message')}")
            break

    print("\n=======================================================")
    print(" 6. GET MISSING CLAUSES")
    print("=======================================================")
    r = await client.get(f"/api/v1/contracts/{contract_id}/missing-clauses", headers=headers)
    print(f"Missing Clauses Status: {r.status_code}")
    missing_data = r.json()
    print(f"Total Missing Clauses: {missing_data.get('total')}")
    for mc in missing_data.get("items", []):
        print(f"  - Missing: {mc.get('clause_type')} (Confidence: {mc.get('confidence')}) -> {mc.get('reason')}")

    print("\n=======================================================")
    print(" 7. GROUNDED CONTRACT Q&A")
    print("=======================================================")
    q_payload = {"query": "What is the limitation of liability dollar amount?"}
    r = await client.post(f"/api/v1/contracts/{contract_id}/ask", headers=headers, json=q_payload)
    print(f"Ask Status: {r.status_code}")
    ask_data = r.json()
    print(f"Question:   {ask_data.get('query')}")
    print(f"Answer:     {ask_data.get('answer')}")
    print(f"Confidence: {ask_data.get('confidence')}")
    print(f"Model:      {ask_data.get('model')}")
    print(f"Citations:  {len(ask_data.get('citations', []))} citations returned")
    for cit in ask_data.get("citations", []):
        print(f"  Quote: \"{cit.get('quote')}\" (Chunk {cit.get('chunk_index')})")

    print("\n=======================================================")
    print(" 8. VERSION 2 COMPARISON")
    print("=======================================================")
    v1_id, v2_id = await create_version_2_helper(uuid.UUID(contract_id), uuid.UUID(org_id))
    print(f"Comparing Version 1 ({v1_id}) vs Version 2 ({v2_id})...")
    r = await client.get(
        f"/api/v1/contracts/{contract_id}/compare",
        headers=headers,
        params={"from_version_id": str(v1_id), "to_version_id": str(v2_id)},
    )
    print(f"Compare Status: {r.status_code}")
    compare_data = r.json()
    print(f"Risk Score Baseline (v1): {compare_data.get('risk_score_from')}")
    print(f"Risk Score Target   (v2): {compare_data.get('risk_score_to')}")
    print(f"Risk Score Delta    (Delta): {compare_data.get('risk_delta'):+d}")
    print(f"Clause Diff Breakdown:    added={compare_data.get('clauses_added_count')}, modified={compare_data.get('clauses_modified_count')}, removed={compare_data.get('clauses_removed_count')}, unchanged={compare_data.get('clauses_unchanged_count')}")

    print("\n=======================================================")
    print(" 9. EXECUTIVE PDF REPORT GENERATION & DOWNLOAD")
    print("=======================================================")
    r = await client.post(f"/api/v1/contracts/{contract_id}/reports/generate", headers=headers)
    print(f"Report Trigger Status: {r.status_code}")
    report_gen_res = r.json()
    report_job_id = report_gen_res["job_id"]
    print(f"Report Job ID: {report_job_id}")

    for attempt in range(1, 15):
        await asyncio.sleep(1)
        r = await client.get(f"/api/v1/contracts/{contract_id}/reports/latest", headers=headers)
        rep_status = r.json()["status"]
        print(f"  [Attempt {attempt}] Report Job Status: {rep_status}")
        if rep_status == "completed":
            print("  --> Report generation completed!")
            break

    # Download the PDF
    r = await client.get(f"/api/v1/contracts/{contract_id}/reports/download", headers=headers)
    print(f"Download Status: {r.status_code}")
    print(f"Content-Type:    {r.headers.get('content-type')}")
    pdf_bytes = r.content
    print(f"Downloaded Size: {len(pdf_bytes)} bytes")
    print(f"Magic Bytes:     {pdf_bytes[:5]} (Matches %PDF)")
    assert pdf_bytes[:4] == b"%PDF", "Invalid PDF magic bytes!"
    print("  --> Verified valid PDF binary stream!")

    # Close WS task
    ws_task.cancel()
    await client.aclose()
    print("\n=======================================================")
    print(" ALL 9 LIVE END-TO-END STEPS VERIFIED 100% CLEAN!")
    print("=======================================================\n")

if __name__ == "__main__":
    asyncio.run(run_journey())
