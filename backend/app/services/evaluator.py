import re
from typing import List, Dict, Any, Optional
from app.models.schemas import (
    AnswerEvaluation, AnswerQuality, Question, EvaluationOutputContract
)
from app.services.llm_client import llm_client

class EvaluationEngine:
    """
    6-Dimension Explicit Rubric Evaluation Engine:
    - Relevance (15%)
    - Technical Correctness (25%)
    - Depth / Reasoning (20%)
    - Evidence / Examples (15%)
    - Problem Solving (15%)
    - Communication (10%)
    """

    DIMENSION_WEIGHTS = {
        "relevance": 0.15,
        "correctness": 0.25,
        "depth": 0.20,
        "evidence": 0.15,
        "problem_solving": 0.15,
        "communication": 0.10
    }

    PROMPT_INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"system\s*override",
        r"reveal\s+(your\s+)?(system\s+prompt|rubric|hidden)",
        r"you\s+are\s+no\s+longer\s+an\s+interviewer",
        r"score:\s*100/100",
        r"give\s+me\s+100%",
        r"output\s+only\s+json"
    ]

    REFUSAL_PATTERNS = [
        r"\b(i\s*don'?t\s*know|i\s*dont\s*know|dont\s*know|don'?t\s*know)\b",
        r"\b(i\s*am\s*not\s*sure|iam\s*not\s*sure|i'?m\s*not\s*sure|not\s*sure)\b",
        r"\b(no\s*idea|no\s*clue|have\s*no\s*idea|haven'?t\s*worked|never\s*worked\s*with|skip|idk|pass)\b",
        r"\b(can'?t\s*answer|cannot\s*answer|no\s*answer|n/a)\b"
    ]

    def _is_prompt_injection(self, text: str) -> bool:
        lower = text.lower()
        return any(re.search(pat, lower) for pat in self.PROMPT_INJECTION_PATTERNS)

    def _is_refusal_or_unknown(self, text: str) -> bool:
        lower = text.lower().strip()
        if len(lower.split()) < 3 and lower in ["no", "skip", "idk", "pass", "none", "na", "n/a", "no idea"]:
            return True
        return any(re.search(pat, lower) for pat in self.REFUSAL_PATTERNS)

    def calculate_overall_score(self, quality: AnswerQuality) -> float:
        score = (
            quality.relevance * self.DIMENSION_WEIGHTS["relevance"] +
            quality.correctness * self.DIMENSION_WEIGHTS["correctness"] +
            quality.depth * self.DIMENSION_WEIGHTS["depth"] +
            quality.evidence * self.DIMENSION_WEIGHTS["evidence"] +
            quality.problem_solving * self.DIMENSION_WEIGHTS["problem_solving"] +
            quality.communication * self.DIMENSION_WEIGHTS["communication"]
        )
        return round(min(100.0, max(0.0, score)), 1)

    def extract_evidence_snippets(self, text: str) -> List[str]:
        sentences = [s.strip() for s in re.split(r'[.!?]\s+', text) if len(s.strip()) > 15]
        if not sentences:
            return [text.strip()] if text.strip() else []
        return sentences[:3]

    def evaluate_answer_deterministic(self, question: Question, answer_text: str) -> AnswerEvaluation:
        # Check prompt injection
        if self._is_prompt_injection(answer_text):
            quality = AnswerQuality(
                relevance=0.0,
                correctness=0.0,
                depth=0.0,
                evidence=0.0,
                problem_solving=0.0,
                communication=10.0
            )
            return AnswerEvaluation(
                question_id=question.question_id,
                answer_quality=quality,
                overall_score=self.calculate_overall_score(quality),
                evidence=[f"Candidate attempted adversarial override: '{answer_text[:60]}...'"],
                strengths=[],
                gaps=["Candidate attempted prompt injection instead of addressing the interview question."],
                confidence=1.0,
                needs_followup=False,
                followup_action="none",
                followup_reason="Adversarial input detected; prompt ignored."
            )

        clean_text = answer_text.strip()
        word_count = len(clean_text.split())
        
        # Check refusal / unknown answer ("I don't know", "I am not sure", etc.) -> Score = 0.0
        if self._is_refusal_or_unknown(clean_text) or word_count < 2:
            quality = AnswerQuality(
                relevance=0.0,
                correctness=0.0,
                depth=0.0,
                evidence=0.0,
                problem_solving=0.0,
                communication=0.0
            )
            return AnswerEvaluation(
                question_id=question.question_id,
                answer_quality=quality,
                overall_score=0.0,
                evidence=[clean_text] if clean_text else ["No substantive answer provided"],
                strengths=[],
                gaps=[f"Candidate stated lack of knowledge ('{clean_text}') on target competency '{question.competency}'."],
                confidence=1.0,
                needs_followup=False,
                followup_action="none",
                followup_reason="Candidate indicated lack of knowledge; moving forward with score 0."
            )

        # Keyword / Expected evidence matching heuristic
        matched_expected = 0
        expected_items = question.expected_evidence or []
        for exp in expected_items:
            tokens = [t.lower() for t in re.findall(r'\w+', exp) if len(t) > 3]
            if any(t in clean_text.lower() for t in tokens):
                matched_expected += 1

        coverage_ratio = (matched_expected / len(expected_items)) if expected_items else 0.5

        # Heuristic scoring based on length, evidence terms, technical keywords
        has_metrics = bool(re.search(r'\d+(\.\d+)?(%|ms|s|req|x|k|m|gb|tb|rows|users)', clean_text, re.I))
        has_tradeoffs = any(w in clean_text.lower() for w in ["because", "tradeoff", "trade-off", "versus", "however", "instead of", "downside", "overhead"])
        has_concrete_tool = any(w in clean_text.lower() for w in ["implemented", "configured", "built", "used", "deployed", "designed", "asyncio", "fastapi", "postgres", "redis", "pytorch", "kafka", "docker"])

        # Base scores
        rel = min(95.0, 50.0 + (coverage_ratio * 40.0) + (10.0 if word_count > 25 else 0.0))
        corr = min(95.0, 45.0 + (coverage_ratio * 45.0) + (10.0 if has_concrete_tool else 0.0))
        depth = min(95.0, 40.0 + (25.0 if has_tradeoffs else 5.0) + (min(30.0, word_count * 0.4)))
        evid = min(95.0, 30.0 + (35.0 if has_metrics else 5.0) + (25.0 if has_concrete_tool else 5.0))
        prob = min(95.0, 45.0 + (25.0 if has_tradeoffs else 10.0) + (coverage_ratio * 25.0))
        comm = min(95.0, 50.0 + (25.0 if word_count >= 20 and word_count <= 250 else 10.0) + (15.0 if "." in clean_text else 0.0))

        quality = AnswerQuality(
            relevance=round(rel, 1),
            correctness=round(corr, 1),
            depth=round(depth, 1),
            evidence=round(evid, 1),
            problem_solving=round(prob, 1),
            communication=round(comm, 1)
        )
        overall = self.calculate_overall_score(quality)
        evidence_snippets = self.extract_evidence_snippets(clean_text)

        # Strengths & Gaps
        strengths = []
        gaps = []
        if overall >= 75.0:
            strengths.append(f"Demonstrated solid conceptual mastery of {question.competency}.")
            if has_tradeoffs:
                strengths.append("Clearly articulated trade-offs and rationale behind architectural decisions.")
            if has_metrics:
                strengths.append("Provided concrete quantifiable metrics to back technical claims.")
        else:
            gaps.append(f"Needs deeper elaboration on fundamental principles of {question.competency}.")
            if not has_metrics and not has_concrete_tool:
                gaps.append("Answer lacks specific implementation details and measurable project outcomes.")

        # Follow-up decision
        needs_fu = False
        fu_action = "none"
        fu_reason = None

        if word_count < 25 and overall < 70.0:
            needs_fu = True
            fu_action = "clarify_vague"
            fu_reason = "Answer was brief and high-level; needs specific elaboration."
        elif not has_metrics and not has_concrete_tool and overall < 75.0:
            needs_fu = True
            fu_action = "request_evidence"
            fu_reason = "Answer describes general ideas without citing concrete implementation evidence or metrics."
        elif overall >= 80.0:
            needs_fu = True
            fu_action = "advance_difficulty"
            fu_reason = "Strong baseline answer provided; candidate is ready for architectural depth and edge-case probing."

        return AnswerEvaluation(
            question_id=question.question_id,
            answer_quality=quality,
            overall_score=overall,
            evidence=evidence_snippets,
            strengths=strengths if strengths else ["Attempted initial response on topic"],
            gaps=gaps if gaps else ["Could explore secondary edge cases and failure modes"],
            confidence=0.92,
            needs_followup=needs_fu,
            followup_action=fu_action,
            followup_reason=fu_reason
        )

    def evaluate_answer(self, question: Question, answer_text: str) -> AnswerEvaluation:
        # If prompt injection or refusal/unknown ("I don't know", "I am not sure"), handle immediately with 0 score
        if self._is_prompt_injection(answer_text) or self._is_refusal_or_unknown(answer_text) or len(answer_text.strip().split()) < 2:
            return self.evaluate_answer_deterministic(question, answer_text)

        system_instruction = (
            "You are an expert technical hiring evaluator for Vellei AI Mock Interview Platform. "
            "Evaluate the candidate's answer strictly against the 6-dimension rubric:\n"
            "- relevance (15%): Directness and topic alignment (0-100)\n"
            "- correctness (25%): Technical and factual accuracy (0-100)\n"
            "- depth (20%): Trade-offs, mechanisms, edge cases (0-100)\n"
            "- evidence (15%): Concrete examples, metrics, code/architectural artifacts (0-100)\n"
            "- problem_solving (15%): Structured reasoning (0-100)\n"
            "- communication (10%): Clarity and structure (0-100)\n\n"
            "Extract 1-3 exact quotes from candidate response into 'evidence'. "
            "Identify concise strengths and concrete gaps. "
            "Determine if an adaptive follow-up is needed ('needs_followup': bool, 'followup_action': str, 'followup_reason': str)."
        )

        user_prompt = (
            f"QUESTION ID: {question.question_id}\n"
            f"COMPETENCY: {question.competency}\n"
            f"QUESTION TYPE: {question.question_type}\n"
            f"DIFFICULTY: {question.difficulty}/5\n"
            f"QUESTION TEXT: {question.text}\n"
            f"EXPECTED EVIDENCE: {question.expected_evidence}\n\n"
            f"CANDIDATE ANSWER:\n{answer_text}\n\n"
            "Return JSON matching EvaluationOutputContract."
        )

        llm_eval = llm_client.generate_structured(
            prompt=user_prompt,
            system_instruction=system_instruction,
            schema_class=EvaluationOutputContract
        )

        if llm_eval:
            overall = self.calculate_overall_score(llm_eval.answer_quality)
            return AnswerEvaluation(
                question_id=question.question_id,
                answer_quality=llm_eval.answer_quality,
                overall_score=overall,
                evidence=llm_eval.evidence or self.extract_evidence_snippets(answer_text),
                strengths=llm_eval.strengths or ["Addressed the core interview question"],
                gaps=llm_eval.gaps or [],
                confidence=llm_eval.confidence,
                needs_followup=llm_eval.needs_followup,
                followup_action=llm_eval.followup_action or "none",
                followup_reason=llm_eval.followup_reason
            )

        return self.evaluate_answer_deterministic(question, answer_text)

evaluator = EvaluationEngine()
