import pytest
from app.models.schemas import Question, AnswerQuality, AnswerEvaluation, CandidateContext, JobContext, InterviewSession, Answer
from app.services.evaluator import evaluator
from app.services.followup_engine import followup_engine

def test_vague_answer_triggers_clarification():
    q = Question(
        competency="Database & Query Optimization",
        difficulty=3,
        text="How do you diagnose slow queries in PostgreSQL?",
        expected_evidence=["EXPLAIN ANALYZE", "Indexes", "Sequential scans"]
    )
    vague_ans = "I just looked at the database and fixed the query so it was fast."
    
    eval_res = evaluator.evaluate_answer(q, vague_ans)
    assert eval_res.needs_followup is True
    assert eval_res.followup_action in ["clarify_vague", "request_evidence"]
    assert eval_res.overall_score < 70.0

def test_strong_answer_triggers_depth_advance():
    q = Question(
        competency="Python Internals & Concurrency",
        difficulty=3,
        text="Explain the Python GIL and how to achieve concurrency.",
        expected_evidence=["GIL mutex", "multiprocessing for CPU bound", "asyncio for I/O bound"]
    )
    strong_ans = (
        "The Python GIL is a mutual exclusion lock that prevents multiple native threads from executing bytecodes concurrently. "
        "For CPU-bound tasks, we bypass GIL contention by using multiprocessing or ProcessPoolExecutor to run isolated memory processes. "
        "For I/O-bound operations like HTTP requests, asyncio cooperative event loops context switch without thread context overhead."
    )
    
    eval_res = evaluator.evaluate_answer(q, strong_ans)
    assert eval_res.overall_score >= 80.0
    assert eval_res.needs_followup is True
    assert eval_res.followup_action == "advance_difficulty"

def test_followup_generation_produces_valid_question():
    session = InterviewSession(
        candidate_id="CAND-001",
        job_id="JOB-PY-001",
        candidate_context=CandidateContext(skills=["Python"]),
        job_context=JobContext(title="Python Developer")
    )
    q = Question(
        question_id="Q-TEST-01",
        competency="Python Internals & Concurrency",
        difficulty=3,
        text="How do you handle concurrency in Python?",
        expected_evidence=["asyncio", "multiprocessing"]
    )
    ans = Answer(question_id=q.question_id, text="I used multithreading.")
    eval_res = AnswerEvaluation(
        question_id=q.question_id,
        answer_quality=AnswerQuality(relevance=60, correctness=50, depth=40, evidence=30, problem_solving=40, communication=60),
        overall_score=47.5,
        needs_followup=True,
        followup_action="clarify_vague",
        followup_reason="Answer lacks technical depth on thread safety"
    )

    fu_question = followup_engine.generate_followup(session, q, ans, eval_res)
    assert fu_question.is_followup is True
    assert fu_question.parent_question_id == q.question_id
    assert len(fu_question.text) > 10
