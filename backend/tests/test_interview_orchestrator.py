import pytest
from app.db.database import init_db, SessionLocal
from app.services.orchestrator import orchestrator
from app.models.schemas import CreateSessionRequest, AnswerSubmitRequest

@pytest.fixture(scope="module")
def db_session():
    init_db()
    db = SessionLocal()
    yield db
    db.close()

def test_session_lifecycle_and_state_transitions(db_session):
    # 1. Create session
    req = CreateSessionRequest(
        job_id="JOB-PY-001",
        candidate_id="CAND-001",
        question_count=2,
        difficulty="adaptive"
    )
    session = orchestrator.create_interview_session(db_session, req)
    assert session.interview_id.startswith("INTV-")
    assert session.status == "CONTEXT_READY"
    assert session.job_context.title == "Senior Python Developer"
    assert len(session.job_context.competencies) >= 3

    # 2. Start session
    session, q1 = orchestrator.start_interview(db_session, session.interview_id)
    assert session.status == "QUESTIONING"
    assert q1 is not None
    assert "Python" in q1.competency or "GIL" in q1.text or len(q1.text) > 10
    assert q1.sequence == 1

    # 3. Answer Q1
    ans_req = AnswerSubmitRequest(
        question_id=q1.question_id,
        answer="I use asyncio for I/O bound tasks to achieve high concurrency without thread overhead, while multiprocessing is used for CPU-bound computation to bypass the GIL."
    )
    turn_res = orchestrator.submit_answer_and_progress(db_session, session.interview_id, ans_req)
    assert turn_res["action"] in ["ask_question", "follow_up", "complete"]
    assert "evaluation_preview" in turn_res
    assert turn_res["evaluation_preview"]["score"] > 50

    # 4. If follow-up or next question, answer to complete
    if turn_res["action"] != "complete" and turn_res.get("next_question"):
        q2 = turn_res["next_question"]
        ans_req2 = AnswerSubmitRequest(
            question_id=q2["question_id"],
            answer="In our FastAPI architecture, we used connection pooling with SQLAlchemy async engine and Redis caching to handle 10k req/sec with sub-20ms latency."
        )
        final_turn = orchestrator.submit_answer_and_progress(db_session, session.interview_id, ans_req2)
        assert final_turn["session_status"] in ["REPORT_READY", "COMPLETED", "QUESTIONING"]

    # 5. Check Report Generation
    report = orchestrator.get_report(db_session, session.interview_id)
    assert report is not None
    assert report.overall_readiness_score > 0
    assert len(report.radar_metrics) == 6
    assert len(report.competency_breakdown) > 0

def test_no_duplicate_questions(db_session):
    req = CreateSessionRequest(
        job_id="JOB-GENAI-004",
        candidate_id="CAND-004",
        question_count=3
    )
    session = orchestrator.create_interview_session(db_session, req)
    session, q1 = orchestrator.start_interview(db_session, session.interview_id)
    
    # Progress through questions
    ans1 = AnswerSubmitRequest(
        question_id=q1.question_id,
        answer="We used BM25 with Qdrant vector search and Reciprocal Rank Fusion, followed by Cohere re-ranking."
    )
    res = orchestrator.submit_answer_and_progress(db_session, session.interview_id, ans1)
    
    question_texts = [q.text for q in session.questions]
    # Check that all questions asked so far are distinct
    assert len(question_texts) == len(set(question_texts))
