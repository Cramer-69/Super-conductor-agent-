"""Semantic Wall API — Phase 1 MVP.

Deployed as its own service, independent of this repo's other app (see
semantic_wall/README.md). Exposes the reusable contract other clients
(a Claude-only app, a multi-provider app, the iOS scaffold in
ios/ConductorApp/) can connect to instead of re-implementing memory/agent
orchestration themselves.
"""

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from semantic_wall.agent.core import SemanticWallAgent
from semantic_wall.checkin import engine as checkin_engine
from semantic_wall.config import settings
from semantic_wall.db.supabase_client import is_configured as memory_is_configured

logger = logging.getLogger("semantic_wall")

app = FastAPI(title="Semantic Wall", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    # No cookies/credentialed requests are used (user_id travels in the
    # JSON body, not a session cookie) — allow_credentials=True combined
    # with a wildcard origin is rejected by browsers anyway, so leave it
    # False rather than restricting allow_origins for no reason.
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    query: str
    agent_id: str = "strategist"


class ChatResponse(BaseModel):
    response: str
    agent_id: str
    memories_used: int
    model: str
    checkin_due: bool


class CheckinRequest(BaseModel):
    user_id: str
    session_id: str
    agent_id: str = "strategist"
    completion_confirmation: bool
    quality_rating: int = Field(ge=1, le=5)
    improvement_note: str
    used_in_real_work: bool
    willingness_to_pay: str
    price_point_cents: Optional[int] = None


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "semantic-wall",
        "version": "0.1.0",
        "memory_configured": memory_is_configured(),
        "providers": settings.configured_providers(),
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        agent = SemanticWallAgent(agent_id=request.agent_id)
        result = agent.chat(request.user_id, request.session_id, request.query)
        checkin_engine.record_activity(request.session_id)
        return ChatResponse(
            response=result["response"],
            agent_id=result["agent_id"],
            memories_used=result["memories_used"],
            model=result["model"],
            checkin_due=checkin_engine.is_checkin_due(request.session_id),
        )
    except Exception as e:
        logger.exception(f"Unhandled error in /api/chat: {e}")
        raise HTTPException(status_code=500, detail="Internal error processing chat request.")


@app.get("/api/checkin/status")
async def checkin_status(session_id: str):
    due = checkin_engine.is_checkin_due(session_id)
    return {
        "due": due,
        "questions": checkin_engine.CHECKIN_QUESTIONS if due else [],
    }


@app.post("/api/checkin")
async def submit_checkin(request: CheckinRequest):
    try:
        result = checkin_engine.submit_checkin(
            user_id=request.user_id,
            session_id=request.session_id,
            agent_id=request.agent_id,
            completion_confirmation=request.completion_confirmation,
            quality_rating=request.quality_rating,
            improvement_note=request.improvement_note,
            used_in_real_work=request.used_in_real_work,
            willingness_to_pay=request.willingness_to_pay,
            price_point_cents=request.price_point_cents,
        )
        return result
    except checkin_engine.CheckinValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("semantic_wall.api.main:app", host=settings.api_host, port=settings.api_port)
