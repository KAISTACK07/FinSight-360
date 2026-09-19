"""
FinSight 360 AI Analytics Assistant
FastAPI Application — Main Entry Point

Endpoints:
  POST /api/ai/query       — Main AI query endpoint
  GET  /api/ai/health      — Health check
  GET  /api/ai/capabilities — Supported question categories

Usage:
  uvicorn ai_assistant.main:app --reload --port 8000
"""

import os
import sys
import logging
import time

# Add project root to path so existing config can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Any

from ai_assistant.intent_detector import detect_intent, Intent, get_supported_categories
from ai_assistant.sql_generator import generate_and_validate_sql
from ai_assistant.database_service import execute_query, test_connection, DatabaseError
from ai_assistant.llm_service import generate_explanation, classify_intent
from ai_assistant.response_builder import build_response, build_unsupported_response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-24s │ %(levelname)-8s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("finsight360.api")

# ============================================================
# FastAPI App
# ============================================================
app = FastAPI(
    title="FinSight 360 AI Analytics Assistant",
    description=(
        "AI-powered natural language analytics interface for the "
        "FinSight 360 retail banking intelligence platform. "
        "Ask questions about customers, revenue, CLV, churn, "
        "segmentation, risk drivers, and get data-backed recommendations."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS — allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Request / Response Models
# ============================================================
class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural-language question about customers, revenue, CLV, churn, segments, or risk.",
        examples=["Which customer segment has the highest average CLV?"],
    )
    conversation_context: Optional[str] = Field(
        None,
        description="Optional previous question for conversational context.",
    )


class QueryResponse(BaseModel):
    success: bool
    question: str
    intent: str
    sql: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    summary: str
    insights: list[str] = []
    recommendations: list[str] = []
    data_recommendations: list[dict[str, Any]] = []
    shap_drivers: list[dict[str, Any]] = []
    sources: dict[str, bool] = {}
    warnings: Optional[list[str]] = None
    error: Optional[str] = None
    processing_time_ms: Optional[int] = None


class HealthResponse(BaseModel):
    status: str
    database: bool
    llm_provider: str
    version: str


# ============================================================
# Endpoints
# ============================================================

@app.post("/api/ai/query", response_model=QueryResponse)
async def query_ai(request: QueryRequest):
    """
    Main AI query endpoint. Accepts a natural-language question and returns
    a structured analytical response backed by actual PostgreSQL data.

    Pipeline:
    1. Intent Detection
    2. SQL Generation
    3. SQL Validation (security)
    4. Database Execution (read-only)
    5. LLM Explanation
    6. Data-grounded Recommendations
    """
    start_time = time.time()
    question = request.question.strip()

    logger.info(f"━━━ New Query: {question[:80]}... ━━━")

    try:
        # Step 1: Detect Intent
        intent = detect_intent(question, llm_classify_fn=classify_intent)
        logger.info(f"Intent: {intent.value}")

        # Handle unknown intent
        if intent == Intent.UNKNOWN:
            response = build_unsupported_response(question)
            response["processing_time_ms"] = int((time.time() - start_time) * 1000)
            return QueryResponse(**response)

        # Step 2: Generate and Validate SQL
        sql_result = generate_and_validate_sql(question, intent.value)

        if sql_result["error"]:
            response = build_response(
                question=question,
                intent=intent.value,
                sql=None,
                query_result=None,
                explanation=None,
                error=sql_result["error"],
            )
            response["processing_time_ms"] = int((time.time() - start_time) * 1000)
            return QueryResponse(**response)

        sql = sql_result["sql"]
        logger.info(f"SQL: {sql[:120]}...")

        # Step 3: Execute Query
        try:
            query_result = execute_query(sql)
        except DatabaseError as e:
            response = build_response(
                question=question,
                intent=intent.value,
                sql=sql,
                query_result=None,
                explanation=None,
                error=str(e),
            )
            response["processing_time_ms"] = int((time.time() - start_time) * 1000)
            return QueryResponse(**response)

        # Step 4: Generate Explanation
        from ai_assistant.schema_metadata import get_schema_context_for_llm
        explanation = generate_explanation(
            question=question,
            intent=intent.value,
            sql=sql,
            data=query_result["rows"],
            schema_context=get_schema_context_for_llm(),
        )

        # Step 5: Build Response
        response = build_response(
            question=question,
            intent=intent.value,
            sql=sql,
            query_result=query_result,
            explanation=explanation,
            validation_warnings=sql_result.get("validation", {})
                and sql_result["validation"].warnings if sql_result.get("validation") else None,
        )

        processing_time = int((time.time() - start_time) * 1000)
        response["processing_time_ms"] = processing_time
        logger.info(f"━━━ Response: {response.get('summary', '')[:80]}... ({processing_time}ms) ━━━")

        return QueryResponse(**response)

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        processing_time = int((time.time() - start_time) * 1000)
        return QueryResponse(
            success=False,
            question=question,
            intent="UNKNOWN",
            summary="An unexpected error occurred. Please try again.",
            error="Internal server error. Please try rephrasing your question.",
            processing_time_ms=processing_time,
        )


@app.get("/api/ai/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint — verifies database connectivity and LLM availability."""
    db_ok = test_connection()
    llm_provider = os.getenv("AI_LLM_PROVIDER", "none")

    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        database=db_ok,
        llm_provider=llm_provider,
        version="1.0.0",
    )


@app.get("/api/ai/capabilities")
async def get_capabilities():
    """Returns the list of supported question categories with examples."""
    return {
        "categories": get_supported_categories(),
        "total_categories": len(get_supported_categories()),
    }


# ============================================================
# Error Handlers
# ============================================================

@app.exception_handler(422)
async def validation_error_handler(request, exc):
    """Handle validation errors without exposing internals."""
    return {
        "success": False,
        "error": "Invalid request. Please provide a valid question (3-500 characters).",
        "detail": str(exc.errors()) if hasattr(exc, "errors") else str(exc),
    }


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """Handle internal errors without exposing stack traces."""
    logger.error(f"Internal error: {exc}", exc_info=True)
    return {
        "success": False,
        "error": "An internal error occurred. Please try again.",
    }


# ============================================================
# Startup
# ============================================================

@app.on_event("startup")
async def startup_event():
    """Verify database connection on startup."""
    logger.info("=" * 60)
    logger.info("FinSight 360 AI Analytics Assistant Starting...")
    logger.info("=" * 60)

    if test_connection():
        logger.info("✅ Database connection verified")
    else:
        logger.error("❌ Database connection failed — queries will fail")

    llm_provider = os.getenv("AI_LLM_PROVIDER", "none")
    logger.info(f"LLM Provider: {llm_provider}")
    logger.info("=" * 60)
