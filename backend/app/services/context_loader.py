import json
import os
from typing import Dict, Any, List, Optional
from app.models.schemas import CandidateContext, JobContext, CompetencyDefinition, CandidateProject

class ContextLoader:
    def __init__(self, dataset_path: Optional[str] = None):
        if not dataset_path:
            dataset_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "evaluation_dataset.json")
        self.dataset_path = dataset_path
        self._dataset_cache: Optional[Dict[str, Any]] = None

    def _load_raw_dataset(self) -> Dict[str, Any]:
        if self._dataset_cache is not None:
            return self._dataset_cache
        if os.path.exists(self.dataset_path):
            try:
                with open(self.dataset_path, "r", encoding="utf-8") as f:
                    self._dataset_cache = json.load(f)
                    return self._dataset_cache
            except Exception as e:
                print(f"Error loading dataset from {self.dataset_path}: {e}")
        return {"jobs": [], "candidates": []}

    def list_jobs(self) -> List[Dict[str, Any]]:
        data = self._load_raw_dataset()
        return data.get("jobs", [])

    def list_candidates(self) -> List[Dict[str, Any]]:
        data = self._load_raw_dataset()
        return data.get("candidates", [])

    def get_job_by_id(self, job_id: str) -> Optional[JobContext]:
        jobs = self.list_jobs()
        for j in jobs:
            if j.get("job_id") == job_id:
                competencies = [
                    CompetencyDefinition(**c) if isinstance(c, dict) else c
                    for c in j.get("competencies", [])
                ]
                return JobContext(
                    job_id=j["job_id"],
                    title=j.get("title", "Software Engineer"),
                    seniority=j.get("seniority", "Mid-Level"),
                    department=j.get("department", "Engineering"),
                    description=j.get("description", ""),
                    required_skills=j.get("required_skills", []),
                    competencies=competencies
                )
        return None

    def get_candidate_by_id(self, candidate_id: str) -> Optional[CandidateContext]:
        candidates = self.list_candidates()
        for c in candidates:
            if c.get("candidate_id") == candidate_id:
                projects = [
                    CandidateProject(**p) if isinstance(p, dict) else p
                    for p in c.get("projects", [])
                ]
                return CandidateContext(
                    candidate_id=c["candidate_id"],
                    name=c.get("name", "Candidate"),
                    target_role=c.get("target_role", "Software Engineer"),
                    years_of_experience=c.get("years_of_experience", 3.0),
                    skills=c.get("skills", []),
                    experience_summary=c.get("experience_summary", ""),
                    projects=projects
                )
        return None

    def normalize_job_context(self, raw: Optional[JobContext] = None, job_id: Optional[str] = None) -> JobContext:
        if raw and raw.competencies and len(raw.competencies) > 0:
            return raw
        if job_id:
            found = self.get_job_by_id(job_id)
            if found:
                return found
        # Default fallback job
        return JobContext(
            job_id="JOB-DEFAULT",
            title="Full Stack Software Engineer",
            seniority="Mid-Level",
            department="Product Engineering",
            description="Build scalable web applications, REST APIs, and database persistence layers.",
            required_skills=["Python", "FastAPI", "React", "PostgreSQL", "System Architecture"],
            competencies=[
                CompetencyDefinition(name="API & Backend Architecture", category="technical", weight=1.2, target_difficulty=3, description="REST principles, authentication, async I/O"),
                CompetencyDefinition(name="Database & Data Modeling", category="technical", weight=1.0, target_difficulty=3, description="Schema design, indexes, transactions"),
                CompetencyDefinition(name="Problem Solving & Code Quality", category="technical", weight=1.0, target_difficulty=3, description="Clean code, edge case handling, debugging")
            ]
        )

    def normalize_candidate_context(self, raw: Optional[CandidateContext] = None, candidate_id: Optional[str] = None) -> CandidateContext:
        if raw and raw.skills:
            return raw
        if candidate_id:
            found = self.get_candidate_by_id(candidate_id)
            if found:
                return found
        return CandidateContext(
            candidate_id="CAND-DEFAULT",
            name="Alex Morgan",
            target_role="Software Engineer",
            years_of_experience=3.5,
            skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
            experience_summary="Mid-level backend developer with experience in microservices and REST APIs."
        )

context_loader = ContextLoader()
