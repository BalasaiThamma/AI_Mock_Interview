import random
from typing import List, Optional, Dict, Any
from app.models.schemas import (
    Question, JobContext, CandidateContext, InterviewSession, InterviewerOutputContract
)
from app.services.rag_knowledge import knowledge_base
from app.services.llm_client import llm_client

class QuestionGenerator:
    """
    Job-aware Question Planning & Dynamic Next Question Generation.
    Avoids duplicate questions, maps to target competencies, and calibrates difficulty.
    """

    def generate_initial_question(self, job: JobContext, candidate: CandidateContext) -> Question:
        first_comp = job.competencies[0] if job.competencies else None
        comp_name = first_comp.name if first_comp else "System Architecture"
        target_diff = first_comp.target_difficulty if first_comp else 3

        # Check knowledge base first
        bank_questions = knowledge_base.get_questions_for_competency(comp_name)
        if bank_questions:
            chosen = bank_questions[0]
            return Question(
                competency=comp_name,
                question_type=chosen.get("question_type", "technical"),
                difficulty=chosen.get("difficulty", target_diff),
                sequence=1,
                text=chosen["text"],
                reason=f"Opening calibration question for competency: {comp_name}",
                expected_evidence=chosen.get("expected_evidence", []),
                is_followup=False
            )

        # Fallback dynamic question
        return Question(
            competency=comp_name,
            question_type="technical",
            difficulty=target_diff,
            sequence=1,
            text=f"Welcome to the interview for the {job.title} role. To start, could you walk me through your technical approach and best practices when working with {comp_name}?",
            reason="Warm-up opening question to gauge foundational understanding",
            expected_evidence=[f"Key principles of {comp_name}", "Practical implementation experience"],
            is_followup=False
        )

    def generate_next_question(self, session: InterviewSession) -> Optional[Question]:
        """
        Selects next uncovered or priority competency and generates a fresh, non-repeated question.
        """
        covered = set(session.state.covered_competencies)
        all_comps = session.job_context.competencies or []
        
        # Find next uncovered competency
        remaining_comps = [c for c in all_comps if c.name not in covered]
        if not remaining_comps:
            # All covered; pick the one with lowest score if under budget
            remaining_comps = all_comps

        if not remaining_comps:
            return None

        target_comp = remaining_comps[0]
        asked_texts = [q.text.lower() for q in session.questions]

        # Check Knowledge base for unused questions
        bank_questions = knowledge_base.get_questions_for_competency(target_comp.name)
        for bq in bank_questions:
            if bq["text"].lower() not in asked_texts:
                return Question(
                    competency=target_comp.name,
                    question_type=bq.get("question_type", "technical"),
                    difficulty=bq.get("difficulty", target_comp.target_difficulty),
                    sequence=len(session.questions) + 1,
                    text=bq["text"],
                    reason=f"Assessing core competency: {target_comp.name}",
                    expected_evidence=bq.get("expected_evidence", []),
                    is_followup=False
                )

        # LLM Generation for unique context-aware question
        system_instruction = (
            "You are an expert technical interviewer for Vellei. "
            "Generate the next interview question tailored to the target job description and candidate context. "
            "Ensure the question is novel, technically deep, and does not repeat previously asked questions. "
            "Return JSON matching InterviewerOutputContract."
        )

        user_prompt = (
            f"TARGET ROLE: {session.job_context.title}\n"
            f"DEPARTMENT: {session.job_context.department}\n"
            f"JOB DESCRIPTION: {session.job_context.description}\n"
            f"TARGET COMPETENCY: {target_comp.name} ({target_comp.description})\n"
            f"TARGET DIFFICULTY: {target_comp.target_difficulty}/5\n"
            f"CANDIDATE SKILLS: {session.candidate_context.skills}\n"
            f"ALREADY ASKED QUESTIONS: {asked_texts}\n\n"
            "Generate a new question targeting this competency."
        )

        llm_q = llm_client.generate_structured(
            prompt=user_prompt,
            system_instruction=system_instruction,
            schema_class=InterviewerOutputContract
        )

        if llm_q and llm_q.question:
            return Question(
                competency=target_comp.name,
                question_type=llm_q.question_type or "technical",
                difficulty=llm_q.difficulty or target_comp.target_difficulty,
                sequence=len(session.questions) + 1,
                text=llm_q.question,
                reason=llm_q.reason or f"Evaluating {target_comp.name}",
                expected_evidence=llm_q.expected_evidence or [f"Understanding of {target_comp.name}"],
                is_followup=False
            )

        # Fallback question
        return Question(
            competency=target_comp.name,
            question_type="technical",
            difficulty=target_comp.target_difficulty,
            sequence=len(session.questions) + 1,
            text=f"Regarding {target_comp.name}, can you discuss a challenging technical problem you solved and how you evaluated design trade-offs?",
            reason=f"Exploring competency {target_comp.name}",
            expected_evidence=["Problem definition", "Design trade-offs", "Concrete implementation"],
            is_followup=False
        )

question_generator = QuestionGenerator()
