import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.models.schemas import (
    InterviewSession, InterviewReport, RadarMetric, CompetencyScore,
    SkillGap, LearningRecommendation
)
from app.services.rag_knowledge import knowledge_base
from app.core.config import settings

class ReportEngine:
    """
    Diagnostic Report Engine:
    - Aggregates per-question 6-dimension rubric scores
    - Derives competency mastery levels
    - Extracts concrete evidence-backed strengths and gaps
    - Maps skill gaps to curated learning recommendations
    - Stores reproducibility and model metadata
    """

    def generate_report(self, session: InterviewSession) -> InterviewReport:
        evaluations = session.evaluations or []
        questions_by_id = {q.question_id: q for q in session.questions}

        # If no evaluations exist, create baseline report
        if not evaluations:
            return InterviewReport(
                interview_id=session.interview_id,
                candidate_id=session.candidate_id,
                job_id=session.job_id,
                target_role=session.job_context.title,
                overall_readiness_score=0.0,
                readiness_tier="Not Ready",
                model_metadata={"model": settings.GEMINI_MODEL, "engine": "Vellei Diagnostic Engine v1.0"},
                radar_metrics=[
                    RadarMetric(dimension="Relevance", score=0.0),
                    RadarMetric(dimension="Correctness", score=0.0),
                    RadarMetric(dimension="Depth", score=0.0),
                    RadarMetric(dimension="Evidence", score=0.0),
                    RadarMetric(dimension="Problem Solving", score=0.0),
                    RadarMetric(dimension="Communication", score=0.0)
                ],
                competency_breakdown=[],
                overall_strengths=[],
                critical_gaps=[],
                learning_recommendations=[],
                transcript_summary="Interview was concluded without answered questions.",
                total_questions=len(session.questions),
                duration_minutes=0.0
            )

        # 1. Calculate Average Radar Metrics
        rel_scores = [e.answer_quality.relevance for e in evaluations]
        corr_scores = [e.answer_quality.correctness for e in evaluations]
        depth_scores = [e.answer_quality.depth for e in evaluations]
        evid_scores = [e.answer_quality.evidence for e in evaluations]
        prob_scores = [e.answer_quality.problem_solving for e in evaluations]
        comm_scores = [e.answer_quality.communication for e in evaluations]

        avg_rel = sum(rel_scores) / len(rel_scores)
        avg_corr = sum(corr_scores) / len(corr_scores)
        avg_depth = sum(depth_scores) / len(depth_scores)
        avg_evid = sum(evid_scores) / len(evid_scores)
        avg_prob = sum(prob_scores) / len(prob_scores)
        avg_comm = sum(comm_scores) / len(comm_scores)

        radar_metrics = [
            RadarMetric(dimension="Relevance", score=round(avg_rel, 1), benchmark=80.0),
            RadarMetric(dimension="Correctness", score=round(avg_corr, 1), benchmark=80.0),
            RadarMetric(dimension="Depth", score=round(avg_depth, 1), benchmark=75.0),
            RadarMetric(dimension="Evidence", score=round(avg_evid, 1), benchmark=70.0),
            RadarMetric(dimension="Problem Solving", score=round(avg_prob, 1), benchmark=75.0),
            RadarMetric(dimension="Communication", score=round(avg_comm, 1), benchmark=80.0)
        ]

        # 2. Overall Score Calculation
        overall_scores = [e.overall_score for e in evaluations]
        overall_readiness = round(sum(overall_scores) / len(overall_scores), 1)

        # 3. Readiness Tier
        if overall_readiness >= 85.0:
            tier = "Strong Hire / Ready"
        elif overall_readiness >= 70.0:
            tier = "Moderate / Minor Gaps"
        elif overall_readiness >= 50.0:
            tier = "Needs Focused Preparation"
        else:
            tier = "Not Ready"

        # 4. Group by Competency
        comp_scores_map: Dict[str, List[float]] = {}
        comp_strengths_map: Dict[str, List[str]] = {}
        comp_gaps_map: Dict[str, List[str]] = {}
        comp_evidence_map: Dict[str, List[str]] = {}

        for ev in evaluations:
            q = questions_by_id.get(ev.question_id)
            comp = q.competency if q else "General Technical"
            if comp not in comp_scores_map:
                comp_scores_map[comp] = []
                comp_strengths_map[comp] = []
                comp_gaps_map[comp] = []
                comp_evidence_map[comp] = []

            comp_scores_map[comp].append(ev.overall_score)
            comp_strengths_map[comp].extend(ev.strengths)
            comp_gaps_map[comp].extend(ev.gaps)
            comp_evidence_map[comp].extend(ev.evidence)

        competency_breakdown: List[CompetencyScore] = []
        critical_gaps: List[SkillGap] = []
        all_strengths: List[str] = []

        for comp, scores in comp_scores_map.items():
            avg_comp_score = round(sum(scores) / len(scores), 1)
            competency_breakdown.append(
                CompetencyScore(
                    competency=comp,
                    score=avg_comp_score,
                    questions_count=len(scores),
                    strengths=list(dict.fromkeys(comp_strengths_map.get(comp, [])))[:3],
                    gaps=list(dict.fromkeys(comp_gaps_map.get(comp, [])))[:3]
                )
            )

            # Identify gaps (< 75)
            if avg_comp_score < 75.0:
                severity = "critical" if avg_comp_score < 45.0 else ("high" if avg_comp_score < 60.0 else "moderate")
                critical_gaps.append(
                    SkillGap(
                        skill=comp,
                        severity=severity,
                        score=avg_comp_score,
                        evidence=comp_evidence_map.get(comp, [])[:2],
                        recommendation_priority=1 if severity in ["critical", "high"] else 2
                    )
                )

            # Collect global strengths
            if avg_comp_score >= 70.0:
                all_strengths.extend(comp_strengths_map.get(comp, []))

        # 5. Generate Curated Learning Recommendations
        learning_recs: List[LearningRecommendation] = []
        for gap in critical_gaps:
            recs = knowledge_base.get_recommendations_for_gap(gap.skill, gap.severity)
            learning_recs.extend(recs)

        # Fallback recommendation if none generated
        if not learning_recs and critical_gaps:
            for gap in critical_gaps:
                learning_recs.append(
                    LearningRecommendation(
                        gap=gap.skill,
                        resource_title=f"Advanced Guide to {gap.skill}",
                        resource_type="documentation",
                        action=f"Deepen conceptual and practical mastery in {gap.skill}.",
                        priority="high",
                        source="Vellei Recommended Curriculum",
                        link="https://roadmap.sh",
                        estimated_hours=8
                    )
                )

        # 6. Calculate Duration
        duration_mins = 5.0
        if session.completed_at and session.created_at:
            duration_mins = round((session.completed_at - session.created_at).total_seconds() / 60.0, 1)

        # Build clean transcript summary
        summary = (
            f"Candidate completed {len(evaluations)} question-answer turns for the {session.job_context.title} role. "
            f"Overall demonstrated proficiency scored at {overall_readiness}% ({tier}). "
            f"Strongest performance in {[c.competency for c in competency_breakdown if c.score >= 75] or ['Initial Foundations']}. "
            f"Key growth areas identified across {[g.skill for g in critical_gaps] or ['None - Ready for Onsite']}."
        )

        return InterviewReport(
            interview_id=session.interview_id,
            candidate_id=session.candidate_id,
            job_id=session.job_id,
            target_role=session.job_context.title,
            overall_readiness_score=overall_readiness,
            readiness_tier=tier,
            model_metadata={
                "model": settings.GEMINI_MODEL,
                "framework": "Vellei AI Orchestrator v1.0",
                "evaluation_rubric_version": "2026.1",
                "structured_schema": "EvaluationOutputContract_v2"
            },
            radar_metrics=radar_metrics,
            competency_breakdown=competency_breakdown,
            overall_strengths=list(dict.fromkeys(all_strengths))[:5] or ["Demonstrated willingness to engage with challenging technical questions"],
            critical_gaps=critical_gaps,
            learning_recommendations=learning_recs,
            transcript_summary=summary,
            total_questions=len(session.questions),
            duration_minutes=duration_mins,
            generated_at=datetime.utcnow()
        )

report_engine = ReportEngine()
