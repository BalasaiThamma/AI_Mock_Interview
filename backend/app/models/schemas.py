from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
import uuid

# --- Context Models ---

class CandidateProject(BaseModel):
    name: str
    description: str
    technologies: List[str] = Field(default_factory=list)
    role: Optional[str] = None
    outcomes: Optional[str] = None

class CandidateContext(BaseModel):
    candidate_id: str = Field(default_factory=lambda: f"CAND-{uuid.uuid4().hex[:6].upper()}")
    name: str = "Candidate"
    target_role: str = "Software Engineer"
    years_of_experience: float = 3.0
    skills: List[str] = Field(default_factory=list)
    experience_summary: str = ""
    projects: List[CandidateProject] = Field(default_factory=list)
    education: Optional[str] = None

class CompetencyDefinition(BaseModel):
    name: str
    category: Literal["technical", "behavioral", "situational", "project", "communication"] = "technical"
    weight: float = 1.0
    description: str = ""
    target_difficulty: int = 3  # 1 to 5

class JobContext(BaseModel):
    job_id: str = Field(default_factory=lambda: f"JOB-{uuid.uuid4().hex[:6].upper()}")
    title: str = "Software Engineer"
    seniority: str = "Mid-Level"
    department: str = "Engineering"
    description: str = ""
    required_skills: List[str] = Field(default_factory=list)
    competencies: List[CompetencyDefinition] = Field(default_factory=list)

# --- Question & Answer Models ---

class Question(BaseModel):
    question_id: str = Field(default_factory=lambda: f"Q-{uuid.uuid4().hex[:6].upper()}")
    competency: str
    question_type: Literal["technical", "behavioral", "situational", "project", "clarification", "deep_dive"] = "technical"
    difficulty: int = Field(default=3, ge=1, le=5)
    sequence: int = 1
    text: str
    reason: str = ""
    expected_evidence: List[str] = Field(default_factory=list)
    is_followup: bool = False
    parent_question_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AnswerQuality(BaseModel):
    relevance: float = Field(default=0.0, ge=0.0, le=100.0, description="Weight 15%")
    correctness: float = Field(default=0.0, ge=0.0, le=100.0, description="Weight 25%")
    depth: float = Field(default=0.0, ge=0.0, le=100.0, description="Weight 20%")
    evidence: float = Field(default=0.0, ge=0.0, le=100.0, description="Weight 15%")
    problem_solving: float = Field(default=0.0, ge=0.0, le=100.0, description="Weight 15%")
    communication: float = Field(default=0.0, ge=0.0, le=100.0, description="Weight 10%")

class AnswerEvaluation(BaseModel):
    evaluation_id: str = Field(default_factory=lambda: f"EVAL-{uuid.uuid4().hex[:6].upper()}")
    question_id: str
    answer_quality: AnswerQuality
    overall_score: float = Field(default=0.0, ge=0.0, le=100.0)
    evidence: List[str] = Field(default_factory=list, description="Verbatim extracted quotes from candidate answer")
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    needs_followup: bool = False
    followup_action: Optional[Literal["probe_depth", "clarify_vague", "request_evidence", "probe_fundamentals", "advance_difficulty", "verify_contradiction", "none"]] = "none"
    followup_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Answer(BaseModel):
    answer_id: str = Field(default_factory=lambda: f"ANS-{uuid.uuid4().hex[:6].upper()}")
    question_id: str
    text: str
    modality: Literal["text", "voice"] = "text"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    evaluation: Optional[AnswerEvaluation] = None

# --- Session & State Models ---

InterviewStatus = Literal["CREATED", "CONTEXT_READY", "QUESTIONING", "COMPLETED", "ANALYZING", "REPORT_READY", "ARCHIVED"]

class InterviewConfig(BaseModel):
    mode: Literal["text", "voice"] = "text"
    interview_type: Literal["technical", "behavioral", "mixed", "system_design"] = "technical"
    target_question_count: int = 5
    difficulty: Literal["adaptive", "entry", "mid", "senior"] = "adaptive"
    allow_followups: bool = True
    max_followups_per_question: int = 2
    time_limit_minutes: int = 30

class InterviewState(BaseModel):
    status: InterviewStatus = "CREATED"
    current_question_index: int = 0
    covered_competencies: List[str] = Field(default_factory=list)
    competency_scores: Dict[str, List[float]] = Field(default_factory=dict)
    weak_areas: List[str] = Field(default_factory=list)
    last_question_id: Optional[str] = None
    current_consecutive_followups: int = 0
    total_questions_asked: int = 0
    is_terminal: bool = False

class InterviewSession(BaseModel):
    interview_id: str = Field(default_factory=lambda: f"INTV-{uuid.uuid4().hex[:8].upper()}")
    candidate_id: str
    job_id: str
    status: InterviewStatus = "CREATED"
    config: InterviewConfig = Field(default_factory=InterviewConfig)
    candidate_context: CandidateContext
    job_context: JobContext
    state: InterviewState = Field(default_factory=InterviewState)
    questions: List[Question] = Field(default_factory=list)
    answers: List[Answer] = Field(default_factory=list)
    evaluations: List[AnswerEvaluation] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

# --- Report & Recommendation Models ---

class SkillGap(BaseModel):
    skill: str
    severity: Literal["low", "moderate", "high", "critical"] = "moderate"
    score: float = 0.0
    evidence: List[str] = Field(default_factory=list)
    recommendation_priority: int = 1

class LearningRecommendation(BaseModel):
    rec_id: str = Field(default_factory=lambda: f"REC-{uuid.uuid4().hex[:6].upper()}")
    gap: str
    resource_title: str
    resource_type: Literal["course", "book", "documentation", "project", "practice_problem", "article"] = "documentation"
    action: str
    priority: Literal["high", "medium", "low"] = "medium"
    source: str = "Vellei Curated Knowledge"
    link: Optional[str] = None
    estimated_hours: Optional[int] = 4

class RadarMetric(BaseModel):
    dimension: str
    score: float
    benchmark: float = 75.0

class CompetencyScore(BaseModel):
    competency: str
    category: str = "technical"
    score: float
    questions_count: int
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)

class InterviewReport(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    report_id: str = Field(default_factory=lambda: f"REP-{uuid.uuid4().hex[:8].upper()}")
    interview_id: str
    candidate_id: str
    job_id: str
    target_role: str
    overall_readiness_score: float = Field(default=0.0, ge=0.0, le=100.0)
    readiness_tier: Literal["Strong Hire / Ready", "Moderate / Minor Gaps", "Needs Focused Preparation", "Not Ready"] = "Needs Focused Preparation"
    version: str = "1.0.0"
    model_metadata: Dict[str, Any] = Field(default_factory=dict)
    radar_metrics: List[RadarMetric] = Field(default_factory=list)
    competency_breakdown: List[CompetencyScore] = Field(default_factory=list)
    overall_strengths: List[str] = Field(default_factory=list)
    critical_gaps: List[SkillGap] = Field(default_factory=list)
    learning_recommendations: List[LearningRecommendation] = Field(default_factory=list)
    transcript_summary: str = ""
    total_questions: int = 0
    duration_minutes: float = 0.0
    generated_at: datetime = Field(default_factory=datetime.utcnow)

# --- Contract & Request/Response DTOs ---

class SessionUpdateDTO(BaseModel):
    covered_competencies: List[str] = Field(default_factory=list)
    possible_gaps: List[str] = Field(default_factory=list)

class InterviewerOutputContract(BaseModel):
    action: Literal["ask_question", "follow_up", "complete"] = "ask_question"
    question: str
    competency: str
    question_type: Literal["technical", "behavioral", "situational", "project", "clarification", "deep_dive"] = "technical"
    difficulty: int = 3
    reason: str
    expected_evidence: List[str] = Field(default_factory=list)
    session_update: SessionUpdateDTO = Field(default_factory=SessionUpdateDTO)

class EvaluationOutputContract(BaseModel):
    question_id: str
    answer_quality: AnswerQuality
    overall_score: float
    evidence: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    confidence: float = 0.9
    needs_followup: bool = False
    followup_action: Optional[str] = "none"
    followup_reason: Optional[str] = None

# --- API Request Payloads ---

class CreateSessionRequest(BaseModel):
    candidate_id: Optional[str] = None
    job_id: Optional[str] = None
    candidate_data: Optional[CandidateContext] = None
    job_data: Optional[JobContext] = None
    mode: Literal["text", "voice"] = "text"
    interview_type: Literal["technical", "behavioral", "mixed", "system_design"] = "technical"
    question_count: int = 5
    difficulty: Literal["adaptive", "entry", "mid", "senior"] = "adaptive"

class AnswerSubmitRequest(BaseModel):
    question_id: str
    answer: str
    modality: Literal["text", "voice"] = "text"
    client_timestamp: Optional[datetime] = None

class DirectEvaluateRequest(BaseModel):
    question_text: str
    competency: str
    candidate_answer: str
    expected_evidence: Optional[List[str]] = None
    difficulty: int = 3
