from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession
from typing import List, Dict, Any, Optional

from app.db.database import get_db
from app.models.schemas import (
    CreateSessionRequest, AnswerSubmitRequest, DirectEvaluateRequest,
    InterviewSession, InterviewReport, LearningRecommendation,
    Question, AnswerEvaluation
)
from app.services.orchestrator import orchestrator
from app.services.context_loader import context_loader
from app.services.evaluator import evaluator

router = APIRouter()

# --- Preset & Metadata Endpoints ---

@router.get("/presets/jobs", summary="List predefined job descriptions")
def list_jobs():
    return context_loader.list_jobs()

@router.get("/presets/candidates", summary="List sample candidate profiles")
def list_candidates():
    return context_loader.list_candidates()

@router.get("/benchmark/dataset", summary="Get evaluation benchmark dataset")
def get_benchmark_dataset():
    return context_loader._load_raw_dataset()

# --- Mock Interview Lifecycle Endpoints ---

@router.post("/mock-interviews", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED, summary="Create interview session")
def create_session(req: CreateSessionRequest, db: DBSession = Depends(get_db)):
    try:
        session = orchestrator.create_interview_session(db, req)
        return {
            "interview_id": session.interview_id,
            "status": session.status,
            "candidate_id": session.candidate_id,
            "job_id": session.job_id,
            "job_title": session.job_context.title,
            "candidate_name": session.candidate_context.name,
            "config": session.config.model_dump(),
            "created_at": session.created_at
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mock-interviews/{interview_id}", summary="Get interview session state")
def get_session(interview_id: str, db: DBSession = Depends(get_db)):
    session = orchestrator._load_session(db, interview_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Interview session '{interview_id}' not found.")
    return session.model_dump()

@router.post("/mock-interviews/{interview_id}/start", summary="Start interview and get first question")
def start_interview(interview_id: str, db: DBSession = Depends(get_db)):
    try:
        session, q1 = orchestrator.start_interview(db, interview_id)
        return {
            "interview_id": session.interview_id,
            "status": session.status,
            "first_question": q1.model_dump(),
            "target_question_count": session.config.target_question_count,
            "time_limit_minutes": session.config.time_limit_minutes
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mock-interviews/{interview_id}/answers", summary="Submit candidate answer and receive next action")
def submit_answer(interview_id: str, req: AnswerSubmitRequest, db: DBSession = Depends(get_db)):
    try:
        result = orchestrator.submit_answer_and_progress(db, interview_id, req)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mock-interviews/{interview_id}/complete", summary="Manually finalize session and trigger report generation")
def complete_interview(interview_id: str, db: DBSession = Depends(get_db)):
    try:
        session = orchestrator._load_session(db, interview_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Interview session '{interview_id}' not found.")
        return orchestrator.finalize_interview(db, session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mock-interviews/{interview_id}/transcript", summary="Retrieve full question-answer audit transcript")
def get_transcript(interview_id: str, db: DBSession = Depends(get_db)):
    try:
        return orchestrator.get_transcript(db, interview_id)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/mock-interviews/{interview_id}/report", summary="Retrieve final diagnostic candidate report")
def get_report(interview_id: str, db: DBSession = Depends(get_db)):
    report = orchestrator.get_report(db, interview_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Diagnostic report for '{interview_id}' not found. Ensure interview is completed.")
    return report.model_dump()

@router.get("/mock-interviews/{interview_id}/recommendations", summary="Retrieve actionable learning recommendations")
def get_recommendations(interview_id: str, db: DBSession = Depends(get_db)):
    report = orchestrator.get_report(db, interview_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Recommendations for '{interview_id}' not found.")
    return {
        "interview_id": interview_id,
        "critical_gaps": [g.model_dump() for g in report.critical_gaps],
        "learning_recommendations": [r.model_dump() for r in report.learning_recommendations]
    }

# --- Developer / Test Harness Endpoint ---

@router.post("/mock-interviews/evaluate", summary="Direct evaluate testing endpoint for QA and evaluation benchmarks")
def direct_evaluate(req: DirectEvaluateRequest):
    mock_q = Question(
        competency=req.competency,
        difficulty=req.difficulty,
        text=req.question_text,
        expected_evidence=req.expected_evidence or []
    )
    eval_res = evaluator.evaluate_answer(mock_q, req.candidate_answer)
    return eval_res.model_dump()
