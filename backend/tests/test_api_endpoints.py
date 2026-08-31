import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_and_root():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

    res_root = client.get("/")
    assert res_root.status_code == 200

def test_presets_endpoints():
    res_jobs = client.get("/api/v1/presets/jobs")
    assert res_jobs.status_code == 200
    assert len(res_jobs.json()) >= 5

    res_cands = client.get("/api/v1/presets/candidates")
    assert res_cands.status_code == 200
    assert len(res_cands.json()) >= 10

def test_full_mock_interview_api_flow():
    # 1. Create Session
    create_payload = {
        "job_id": "JOB-PY-001",
        "candidate_id": "CAND-001",
        "mode": "text",
        "interview_type": "technical",
        "question_count": 2,
        "difficulty": "adaptive"
    }
    create_res = client.post("/api/v1/mock-interviews", json=create_payload)
    assert create_res.status_code == 201
    intv_id = create_res.json()["interview_id"]

    # 2. Get State
    state_res = client.get(f"/api/v1/mock-interviews/{intv_id}")
    assert state_res.status_code == 200
    assert state_res.json()["status"] == "CONTEXT_READY"

    # 3. Start Interview
    start_res = client.post(f"/api/v1/mock-interviews/{intv_id}/start")
    assert start_res.status_code == 200
    first_q = start_res.json()["first_question"]
    assert first_q["question_id"] is not None

    # 4. Submit Answer 1
    ans1_payload = {
        "question_id": first_q["question_id"],
        "answer": "I use asyncio event loops for asynchronous networking and multiprocessing for CPU-bound tasks.",
        "modality": "text"
    }
    ans1_res = client.post(f"/api/v1/mock-interviews/{intv_id}/answers", json=ans1_payload)
    assert ans1_res.status_code == 200

    # 5. Complete Session
    comp_res = client.post(f"/api/v1/mock-interviews/{intv_id}/complete")
    assert comp_res.status_code == 200

    # 6. Retrieve Transcript
    trans_res = client.get(f"/api/v1/mock-interviews/{intv_id}/transcript")
    assert trans_res.status_code == 200
    assert len(trans_res.json()["turns"]) >= 1

    # 7. Retrieve Diagnostic Report
    rep_res = client.get(f"/api/v1/mock-interviews/{intv_id}/report")
    assert rep_res.status_code == 200
    report_data = rep_res.json()
    assert report_data["overall_readiness_score"] >= 0
    assert len(report_data["radar_metrics"]) == 6

    # 8. Retrieve Recommendations
    rec_res = client.get(f"/api/v1/mock-interviews/{intv_id}/recommendations")
    assert rec_res.status_code == 200

def test_direct_evaluate_endpoint():
    payload = {
        "question_text": "What is the GIL?",
        "competency": "Python Internals",
        "candidate_answer": "The GIL is a mutex preventing simultaneous Python bytecode execution across threads.",
        "expected_evidence": ["mutex", "bytecode", "threads"],
        "difficulty": 3
    }
    res = client.post("/api/v1/mock-interviews/evaluate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["overall_score"] > 50
    assert "answer_quality" in data
