import os
import json
from typing import List, Dict, Any, Optional
from app.models.schemas import LearningRecommendation, SkillGap

class KnowledgeBase:
    """
    RAG & Curated Knowledge Repository for Technical & Behavioral Competencies,
    Question Banks, Rubrics, and Actionable Learning Resources.
    """
    
    CURATED_RESOURCES: Dict[str, List[Dict[str, Any]]] = {
        "Python Internals & Concurrency": [
            {
                "resource_title": "Fluent Python (2nd Edition) - Chapters on GIL & Asyncio",
                "resource_type": "book",
                "action": "Master GIL mutex mechanisms, asyncio event loop scheduling, and multiprocessing queues.",
                "source": "O'Reilly Media",
                "link": "https://www.oreilly.com/library/view/fluent-python-2nd/9781492056348/",
                "estimated_hours": 12
            },
            {
                "resource_title": "Python AsyncIO Deep Dive: Concurrency Beyond Threads",
                "resource_type": "course",
                "action": "Implement cooperative multitasking event loops and debug async race conditions.",
                "source": "RealPython",
                "link": "https://realpython.com/async-io-python/",
                "estimated_hours": 6
            }
        ],
        "API & Backend Architecture": [
            {
                "resource_title": "FastAPI Production Architecture Guide",
                "resource_type": "documentation",
                "action": "Design dependency injection patterns, middleware security, and connection pooling.",
                "source": "FastAPI Official Docs",
                "link": "https://fastapi.tiangolo.com/tutorial/bigger-applications/",
                "estimated_hours": 5
            },
            {
                "resource_title": "Microservice Architecture Patterns (Chris Richardson)",
                "resource_type": "book",
                "action": "Study API Gateway, SAGA orchestration, and rate limiting algorithms.",
                "source": "Manning",
                "link": "https://microservices.io/patterns/",
                "estimated_hours": 15
            }
        ],
        "Database & Query Optimization": [
            {
                "resource_title": "Use The Index, Luke! - Relational Database Indexing",
                "resource_type": "article",
                "action": "Analyze EXPLAIN execution plans, B-Tree lookups, and compound index ordering.",
                "source": "Markus Winand",
                "link": "https://use-the-index-luke.com/",
                "estimated_hours": 8
            },
            {
                "resource_title": "PostgreSQL High Performance Query Tuning",
                "resource_type": "course",
                "action": "Optimize vacuuming, connection saturation, and N+1 query problems in ORMs.",
                "source": "PostgresGuide",
                "link": "https://www.postgresguide.com/performance/queries/",
                "estimated_hours": 10
            }
        ],
        "RAG Architecture & Retrieval": [
            {
                "resource_title": "Advanced RAG Techniques: Hybrid Search & Re-ranking",
                "resource_type": "documentation",
                "action": "Implement dense + sparse hybrid vector search (BM25 + Cohere Rerank) and parent document chunking.",
                "source": "Pinecone Learning Center",
                "link": "https://www.pinecone.io/learn/advanced-rag-techniques/",
                "estimated_hours": 8
            },
            {
                "resource_title": "RAG Triad & RAGAS Evaluation Framework",
                "resource_type": "practice_problem",
                "action": "Build automated evaluation pipelines for Context Relevance, Faithfulness, and Answer Relevance.",
                "source": "Exploding Gradients",
                "link": "https://docs.ragas.io/en/stable/",
                "estimated_hours": 6
            }
        ],
        "LLM Orchestration & Agents": [
            {
                "resource_title": "Building Reliable Agentic Workflows & Multi-Agent State Machines",
                "resource_type": "article",
                "action": "Architect deterministic state transitions, error recovery loops, and prompt guardrails.",
                "source": "Anthropic Research",
                "link": "https://www.anthropic.com/research/building-effective-agents",
                "estimated_hours": 6
            }
        ],
        "Low-Latency Model Serving": [
            {
                "resource_title": "NVIDIA Triton Inference Server Mastery",
                "resource_type": "documentation",
                "action": "Configure dynamic batching, model concurrency, and TensorRT engine optimization.",
                "source": "NVIDIA Developer",
                "link": "https://developer.nvidia.com/triton-inference-server",
                "estimated_hours": 12
            }
        ],
        "Statistical Analysis & Inference": [
            {
                "resource_title": "Trustworthy Online Controlled Experiments (A/B Testing Bible)",
                "resource_type": "book",
                "action": "Master variance reduction (CUPED), sample ratio mismatches (SRM), and false discovery rate control.",
                "source": "Cambridge University Press",
                "link": "https://exp-platform.com/",
                "estimated_hours": 16
            }
        ],
        "Distributed System Patterns": [
            {
                "resource_title": "Designing Data-Intensive Applications (Martin Kleppmann)",
                "resource_type": "book",
                "action": "Study replication, partitioning, consensus protocols (Raft/Paxos), and transactional isolation.",
                "source": "O'Reilly Media",
                "link": "https://dataintensive.net/",
                "estimated_hours": 25
            }
        ]
    }

    QUESTION_BANK: Dict[str, List[Dict[str, Any]]] = {
        "Python Internals & Concurrency": [
            {
                "text": "How does the Python Global Interpreter Lock (GIL) impact multithreaded CPU-bound vs I/O-bound programs, and how do you choose between asyncio, threading, and multiprocessing?",
                "difficulty": 4,
                "question_type": "technical",
                "expected_evidence": [
                    "GIL prevents concurrent execution of Python bytecode across native threads",
                    "CPU-bound tasks require multiprocessing to utilize multiple CPU cores",
                    "I/O-bound tasks release the GIL during syscalls and benefit from asyncio cooperative concurrency"
                ]
            },
            {
                "text": "Explain the lifecycle of a Python generator and how 'yield' differs from 'return'. How does the asyncio event loop build upon generator/coroutine mechanics?",
                "difficulty": 4,
                "question_type": "technical",
                "expected_evidence": [
                    "Generators suspend execution state via stack frame preservation",
                    "send() and throw() mechanisms",
                    "Coroutines (__await__) yielding future control back to event loop"
                ]
            }
        ],
        "API & Backend Architecture": [
            {
                "text": "When building a high-throughput API with FastAPI, how do you manage database connection pooling and asynchronous request lifecycles without leaking connections?",
                "difficulty": 3,
                "question_type": "technical",
                "expected_evidence": [
                    "Async session lifecycle management with context managers or Depends()",
                    "Pool sizing, max overflow, and connection checkout timeouts",
                    "Ensuring connections close on client disconnect or exception"
                ]
            }
        ],
        "Database & Query Optimization": [
            {
                "text": "Suppose a critical PostgreSQL query on a table with 50M rows suddenly experiences high latency. Walk me through how you diagnose and resolve this using EXPLAIN ANALYZE.",
                "difficulty": 4,
                "question_type": "technical",
                "expected_evidence": [
                    "Sequential scan vs Index scan vs Bitmap heap scan",
                    "Analyzing actual time, cost estimates, and rows filtered",
                    "Adding composite/partial indexes, analyzing table statistics with VACUUM ANALYZE"
                ]
            }
        ],
        "RAG Architecture & Retrieval": [
            {
                "text": "In a production RAG system, semantic dense vector search often retrieves irrelevant chunks or misses exact keyword matches. How do you design a hybrid retrieval and re-ranking pipeline to solve this?",
                "difficulty": 4,
                "question_type": "technical",
                "expected_evidence": [
                    "Hybrid search combining BM25 keyword search with dense embedding cosine similarity",
                    "Reciprocal Rank Fusion (RRF) or weighted score normalization",
                    "Cross-encoder re-ranking (e.g. Cohere Rerank / BGE-Reranker) for top-k precision"
                ]
            }
        ],
        "LLM Orchestration & Agents": [
            {
                "text": "How do you build guardrails against hallucination and prompt injection in a user-facing autonomous agent workflow?",
                "difficulty": 4,
                "question_type": "situational",
                "expected_evidence": [
                    "Strict output schema validation (e.g. Pydantic / JSON schema)",
                    "Input sanitization, delimiter isolation, and role instruction anchoring",
                    "Grounding checks against retrieved context before response dispatch"
                ]
            }
        ]
    }

    @classmethod
    def get_questions_for_competency(cls, competency: str) -> List[Dict[str, Any]]:
        for key, q_list in cls.QUESTION_BANK.items():
            if key.lower() in competency.lower() or competency.lower() in key.lower():
                return q_list
        return []

    @classmethod
    def get_recommendations_for_gap(cls, gap_name: str, severity: str = "moderate") -> List[LearningRecommendation]:
        recs: List[LearningRecommendation] = []
        matched_category = None
        for key, resource_list in cls.CURATED_RESOURCES.items():
            if key.lower() in gap_name.lower() or gap_name.lower() in key.lower():
                matched_category = resource_list
                break
        
        if not matched_category:
            # Fallback general engineering resource
            recs.append(
                LearningRecommendation(
                    gap=gap_name,
                    resource_title=f"Core Competency Deep Dive: {gap_name}",
                    resource_type="documentation",
                    action=f"Study core architectural principles, standard practices, and edge cases in {gap_name}.",
                    priority="high" if severity in ["high", "critical"] else "medium",
                    source="Vellei Curated Catalog",
                    link="https://roadmap.sh/backend",
                    estimated_hours=6
                )
            )
            return recs

        for res in matched_category:
            recs.append(
                LearningRecommendation(
                    gap=gap_name,
                    resource_title=res["resource_title"],
                    resource_type=res["resource_type"],
                    action=res["action"],
                    priority="high" if severity in ["high", "critical"] else "medium",
                    source=res.get("source", "Vellei Knowledge Base"),
                    link=res.get("link"),
                    estimated_hours=res.get("estimated_hours", 6)
                )
            )
        return recs

knowledge_base = KnowledgeBase()
