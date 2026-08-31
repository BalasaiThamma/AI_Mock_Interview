import pytest
from app.models.schemas import AnswerQuality, Question
from app.services.evaluator import evaluator

def test_rubric_weights_and_mathematics():
    # Verify exact weights:
    # Relevance: 15%, Correctness: 25%, Depth: 20%, Evidence: 15%, Problem Solving: 15%, Communication: 10%
    quality = AnswerQuality(
        relevance=100.0,
        correctness=100.0,
        depth=100.0,
        evidence=100.0,
        problem_solving=100.0,
        communication=100.0
    )
    score = evaluator.calculate_overall_score(quality)
    assert score == 100.0

    # Custom mix test
    quality_mix = AnswerQuality(
        relevance=80.0,      # 80 * 0.15 = 12.0
        correctness=90.0,    # 90 * 0.25 = 22.5
        depth=70.0,          # 70 * 0.20 = 14.0
        evidence=60.0,       # 60 * 0.15 = 9.0
        problem_solving=80.0,# 80 * 0.15 = 12.0
        communication=90.0   # 90 * 0.10 = 9.0
                             # Sum = 78.5
    )
    score_mix = evaluator.calculate_overall_score(quality_mix)
    assert score_mix == 78.5

def test_verbatim_evidence_extraction():
    q = Question(
        competency="RAG Architecture & Retrieval",
        difficulty=4,
        text="Explain your RAG retrieval architecture."
    )
    text = (
        "We implemented hybrid search combining BM25 keyword matching with dense Qdrant vector retrieval. "
        "The retrieved candidates were re-ranked using Cohere Rerank v3. "
        "This reduced hallucinated clauses from 18% down to under 1.2%."
    )
    eval_res = evaluator.evaluate_answer(q, text)
    assert len(eval_res.evidence) >= 1
    # Evidence must contain actual text snippets from candidate answer
    for ev_snippet in eval_res.evidence:
        assert any(word in text for word in ev_snippet.split()[:3])

def test_unknown_and_not_sure_answers_score_zero():
    q = Question(
        competency="Python Internals & Concurrency",
        difficulty=3,
        text="Explain how the GIL impacts multiprocessing vs multithreading."
    )
    unknown_answers = [
        "I Don't know",
        "Iam not sure",
        "I'm not sure",
        "i dont know",
        "no idea",
        "skip",
        "have no clue",
        "not sure about this"
    ]

    for ans in unknown_answers:
        eval_res = evaluator.evaluate_answer(q, ans)
        assert eval_res.overall_score == 0.0, f"Expected 0.0 for '{ans}', got {eval_res.overall_score}"
        assert eval_res.answer_quality.correctness == 0.0
        assert eval_res.answer_quality.relevance == 0.0
        assert eval_res.answer_quality.depth == 0.0
        assert eval_res.answer_quality.evidence == 0.0
        assert eval_res.needs_followup is False
