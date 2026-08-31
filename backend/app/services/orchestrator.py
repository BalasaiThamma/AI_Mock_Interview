import json
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from app.models.schemas import (
    InterviewSession, InterviewState, InterviewConfig, Question, Answer,
    AnswerEvaluation, InterviewReport, CreateSessionRequest, AnswerSubmitRequest
)
from app.db.database import InterviewSessionModel
from app.services.context_loader import context_loader
from app.services.question_generator import question_generator
from app.services.followup_engine import followup_engine
from app.services.evaluator import evaluator
from app.services.report_engine import report_engine

class InterviewOrchestrator:
    """
    Stateful Interview Orchestrator & State Machine:
    CREATED -> CONTEXT_READY -> QUESTIONING -> COMPLETED -> ANALYZING -> REPORT_READY -> ARCHIVED
    """

    def _save_session(self, db: DBSession, session: InterviewSession, report: Optional[InterviewReport] = None):
        db_session = db.query(InterviewSessionModel).filter(InterviewSessionModel.interview_id == session.interview_id).first()
        session_dict = session.model_dump(mode="json")
        report_dict = report.model_dump(mode="json") if report else (session_dict.get("report") if "report" in session_dict else None)

        if not db_session:
            db_session = InterviewSessionModel(
                interview_id=session.interview_id,
                candidate_id=session.candidate_id,
                job_id=session.job_id,
                status=session.status,
                mode=session.config.mode,
                interview_type=session.config.interview_type,
                config=session.config.model_dump(mode="json"),
                candidate_context=session.candidate_context.model_dump(mode="json"),
                job_context=session.job_context.model_dump(mode="json"),
                state=session.state.model_dump(mode="json"),
                questions=[q.model_dump(mode="json") for q in session.questions],
                answers=[a.model_dump(mode="json") for a in session.answers],
                evaluations=[e.model_dump(mode="json") for e in session.evaluations],
                report=report_dict,
                created_at=session.created_at,
                updated_at=datetime.utcnow(),
                completed_at=session.completed_at
            )
            db.add(db_session)
        else:
            db_session.status = session.status
            db_session.mode = session.config.mode
            db_session.interview_type = session.config.interview_type
            db_session.state = session.state.model_dump(mode="json")
            db_session.questions = [q.model_dump(mode="json") for q in session.questions]
            db_session.answers = [a.model_dump(mode="json") for a in session.answers]
            db_session.evaluations = [e.model_dump(mode="json") for e in session.evaluations]
            if report_dict:
                db_session.report = report_dict
            db_session.updated_at = datetime.utcnow()
            db_session.completed_at = session.completed_at

        db.commit()
        db.refresh(db_session)

    def _load_session(self, db: DBSession, interview_id: str) -> Optional[InterviewSession]:
        db_session = db.query(InterviewSessionModel).filter(InterviewSessionModel.interview_id == interview_id).first()
        if not db_session:
            return None

        # Reconstruct Pydantic model
        questions = [Question(**q) for q in (db_session.questions or [])]
        answers = [Answer(**a) for a in (db_session.answers or [])]
        evaluations = [AnswerEvaluation(**e) for e in (db_session.evaluations or [])]

        session = InterviewSession(
            interview_id=db_session.interview_id,
            candidate_id=db_session.candidate_id,
            job_id=db_session.job_id,
            status=db_session.status,
            config=InterviewConfig(**(db_session.config or {})),
            candidate_context=context_loader.normalize_candidate_context(raw=None, candidate_id=db_session.candidate_id),
            job_context=context_loader.normalize_job_context(raw=None, job_id=db_session.job_id),
            state=InterviewState(**(db_session.state or {})),
            questions=questions,
            answers=answers,
            evaluations=evaluations,
            created_at=db_session.created_at,
            updated_at=db_session.updated_at,
            completed_at=db_session.completed_at
        )
        return session

    def create_interview_session(self, db: DBSession, req: CreateSessionRequest) -> InterviewSession:
        cand_ctx = context_loader.normalize_candidate_context(raw=req.candidate_data, candidate_id=req.candidate_id)
        job_ctx = context_loader.normalize_job_context(raw=req.job_data, job_id=req.job_id)

        config = InterviewConfig(
            mode=req.mode,
            interview_type=req.interview_type,
            target_question_count=req.question_count,
            difficulty=req.difficulty,
            allow_followups=True,
            max_followups_per_question=2
        )

        session = InterviewSession(
            candidate_id=cand_ctx.candidate_id,
            job_id=job_ctx.job_id,
            status="CONTEXT_READY",
            config=config,
            candidate_context=cand_ctx,
            job_context=job_ctx,
            state=InterviewState(status="CONTEXT_READY")
        )

        self._save_session(db, session)
        return session

    def start_interview(self, db: DBSession, interview_id: str) -> Tuple[InterviewSession, Question]:
        session = self._load_session(db, interview_id)
        if not session:
            raise ValueError(f"Session '{interview_id}' not found.")

        if session.status in ["QUESTIONING", "REPORT_READY", "COMPLETED"] and session.questions:
            return session, session.questions[-1]

        # Generate first question
        q1 = question_generator.generate_initial_question(session.job_context, session.candidate_context)
        session.questions.append(q1)
        session.status = "QUESTIONING"
        session.state.status = "QUESTIONING"
        session.state.last_question_id = q1.question_id
        session.state.total_questions_asked = 1
        session.state.current_question_index = 1

        self._save_session(db, session)
        return session, q1

    def submit_answer_and_progress(
        self,
        db: DBSession,
        interview_id: str,
        answer_req: AnswerSubmitRequest
    ) -> Dict[str, Any]:
        session = self._load_session(db, interview_id)
        if not session:
            raise ValueError(f"Session '{interview_id}' not found.")

        if session.status not in ["QUESTIONING", "CONTEXT_READY"]:
            # If already completed, return existing status
            return {
                "action": "completed",
                "session_status": session.status,
                "message": "Interview is already finished."
            }

        # Find the question being answered
        current_question = None
        for q in reversed(session.questions):
            if q.question_id == answer_req.question_id:
                current_question = q
                break
        if not current_question and session.questions:
            current_question = session.questions[-1]

        if not current_question:
            raise ValueError("No active question to answer.")

        # 1. Capture Answer
        answer_obj = Answer(
            question_id=current_question.question_id,
            text=answer_req.answer,
            modality=answer_req.modality,
            timestamp=datetime.utcnow()
        )

        # 2. Evaluate Answer with 6-dimension rubric
        eval_obj = evaluator.evaluate_answer(current_question, answer_req.answer)
        answer_obj.evaluation = eval_obj
        session.answers.append(answer_obj)
        session.evaluations.append(eval_obj)

        # 3. Update Competency Score Tracker
        comp = current_question.competency
        if comp not in session.state.competency_scores:
            session.state.competency_scores[comp] = []
        session.state.competency_scores[comp].append(eval_obj.overall_score)

        # 4. Check Follow-Up Rules
        allow_fu = (
            session.config.allow_followups and
            eval_obj.needs_followup and
            session.state.current_consecutive_followups < session.config.max_followups_per_question
        )

        next_action = "ask_question"
        next_question: Optional[Question] = None

        if allow_fu:
            # Generate adaptive follow-up
            next_question = followup_engine.generate_followup(
                session=session,
                last_question=current_question,
                last_answer=answer_obj,
                evaluation=eval_obj
            )
            session.questions.append(next_question)
            session.state.current_consecutive_followups += 1
            session.state.total_questions_asked += 1
            session.state.last_question_id = next_question.question_id
            next_action = "follow_up"
        else:
            # Mark competency covered
            if comp not in session.state.covered_competencies:
                session.state.covered_competencies.append(comp)
            session.state.current_consecutive_followups = 0

            # 5. Check Termination Conditions (Question count or all covered)
            total_answered = len(session.answers)
            if total_answered >= session.config.target_question_count:
                # Complete the interview!
                return self.finalize_interview(db, session)

            # Generate next question from plan
            next_question = question_generator.generate_next_question(session)
            if not next_question:
                return self.finalize_interview(db, session)

            session.questions.append(next_question)
            session.state.total_questions_asked += 1
            session.state.current_question_index += 1
            session.state.last_question_id = next_question.question_id
            next_action = "ask_question"

        self._save_session(db, session)

        return {
            "action": next_action,
            "session_status": session.status,
            "evaluation_preview": {
                "score": eval_obj.overall_score,
                "strengths": eval_obj.strengths,
                "gaps": eval_obj.gaps,
                "is_followup": eval_obj.needs_followup,
                "followup_reason": eval_obj.followup_reason
            },
            "next_question": next_question.model_dump() if next_question else None,
            "progress": {
                "answered_count": len(session.answers),
                "target_count": session.config.target_question_count,
                "covered_competencies": session.state.covered_competencies
            }
        }

    def finalize_interview(self, db: DBSession, session: InterviewSession) -> Dict[str, Any]:
        session.status = "COMPLETED"
        session.state.status = "COMPLETED"
        session.completed_at = datetime.utcnow()

        # Generate diagnostic report
        session.status = "ANALYZING"
        report = report_engine.generate_report(session)
        session.status = "REPORT_READY"
        session.state.status = "REPORT_READY"

        self._save_session(db, session, report=report)

        return {
            "action": "complete",
            "session_status": "REPORT_READY",
            "message": "Interview completed successfully. Diagnostic report is ready.",
            "report_id": report.report_id,
            "overall_score": report.overall_readiness_score,
            "readiness_tier": report.readiness_tier
        }

    def get_report(self, db: DBSession, interview_id: str) -> Optional[InterviewReport]:
        db_session = db.query(InterviewSessionModel).filter(InterviewSessionModel.interview_id == interview_id).first()
        if not db_session:
            return None
        if db_session.report:
            return InterviewReport(**db_session.report)

        # Generate on demand if completed
        session = self._load_session(db, interview_id)
        if session:
            report = report_engine.generate_report(session)
            db_session.report = report.model_dump()
            db_session.status = "REPORT_READY"
            db.commit()
            return report
        return None

    def get_transcript(self, db: DBSession, interview_id: str) -> Dict[str, Any]:
        session = self._load_session(db, interview_id)
        if not session:
            raise ValueError(f"Session '{interview_id}' not found.")

        turns = []
        evals_by_qid = {e.question_id: e for e in session.evaluations}
        answers_by_qid = {a.question_id: a for a in session.answers}

        for q in session.questions:
            ans = answers_by_qid.get(q.question_id)
            ev = evals_by_qid.get(q.question_id)
            turns.append({
                "question": q.model_dump(),
                "answer": ans.model_dump() if ans else None,
                "evaluation": ev.model_dump() if ev else None
            })

        return {
            "interview_id": session.interview_id,
            "candidate_id": session.candidate_id,
            "candidate_name": session.candidate_context.name,
            "job_title": session.job_context.title,
            "status": session.status,
            "turns": turns,
            "created_at": session.created_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None
        }

orchestrator = InterviewOrchestrator()
