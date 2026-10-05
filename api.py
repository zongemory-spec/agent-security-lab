from __future__ import annotations
import logging
import json
import os
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel, ConfigDict, Field
from agent import RealAgent
from approvals import ApprovalStore
from auth import AuthRegistry
from llm_client import ModelError
from mock_llm import DemoLLM
from security import PolicyError, redact
from storage import Database

class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class ChatBody(StrictBody):
    session_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    message: str = Field(min_length=1, max_length=8000)

class ActionBody(StrictBody):
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")

def create_app(db=None, auth=None, llm=None):
    db = db or Database(os.getenv("LAB_DB", "data/lab.sqlite3"))
    auth = auth or AuthRegistry.from_file(os.getenv("LAB_AUTH_FILE", "data/demo_auth.json"))
    if llm is None:
        backend = os.getenv("LAB_MODEL", "mock")
        if backend == "mock":
            llm = DemoLLM()
        elif backend == "real":
            from config import get_provider_config
            from llm_client import RealLLMClient
            llm = RealLLMClient(get_provider_config())
        else:
            raise RuntimeError("LAB_MODEL must be mock or real")
    app = FastAPI(title="Agent Security Lab (local synthetic demo)")
    audit_logger = logging.getLogger("lab.audit")
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False
    if not audit_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        audit_logger.addHandler(handler)
    app.state.db, app.state.auth = db, auth
    approvals = ApprovalStore(db)
    app.state.approvals = approvals
    agent = RealAgent(llm, db=db, mode="secure")
    app.state.agent = agent
    known_secrets = tuple(auth.credentials) + (getattr(llm.cfg, "api_key", ""),)

    @app.middleware("http")
    async def audit_request(request, call_next):
        request.state.request_id = uuid4().hex
        request.state.ctx = None
        request.state.reason = "request_completed"
        # No request headers, messages, arguments, URL query strings or upstream errors in audit logs.
        try:
            response = await call_next(request)
        except Exception:
            request.state.reason = "internal_error"
            response = JSONResponse({"detail": "internal_error"}, status_code=500)
        db.audit(request.state.ctx, request.state.request_id, "http", request.state.reason)
        audit_logger.info(json.dumps({"request_id": request.state.request_id,
            "status": response.status_code, "reason": request.state.reason}))
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(PolicyError)
    async def policy_error(request, exc):
        request.state.reason = exc.reason
        return JSONResponse({"detail": exc.reason}, status_code=exc.status,
                            headers={"WWW-Authenticate": "Bearer"} if exc.status == 401 else None)

    @app.exception_handler(ModelError)
    async def model_error(request, exc):
        request.state.reason = exc.reason
        return JSONResponse({"detail": exc.reason}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        request.state.reason = "invalid_request"
        return JSONResponse({"detail": "invalid_request"}, status_code=422)

    def authenticated(request: Request):
        ctx = auth.authenticate(request.headers.get("Authorization"))
        request.state.ctx = ctx
        return ctx

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def ui():
        return Path(__file__).with_name("ui.html").read_text(encoding="utf-8-sig")

    @app.post("/chat")
    async def chat(body: ChatBody, request: Request, ctx=Depends(authenticated)):
        result = await agent.run(body.message, ctx, body.session_id, request.state.request_id)
        result["run_id"] = request.state.request_id
        result = redact(result, known_secrets)
        db.save_run(result["run_id"], ctx, result, known_secrets)
        return result

    @app.get("/actions/{action_id}")
    def get_action(action_id: str, ctx=Depends(authenticated)):
        return approvals.get(action_id, ctx)

    @app.post("/actions/{action_id}/approve")
    def approve(action_id: str, body: ActionBody, request: Request, ctx=Depends(authenticated)):
        return approvals.decide(action_id, body.digest, ctx, True, request.state.request_id)

    @app.post("/actions/{action_id}/reject")
    def reject(action_id: str, body: ActionBody, request: Request, ctx=Depends(authenticated)):
        return approvals.decide(action_id, body.digest, ctx, False, request.state.request_id)

    @app.post("/actions/{action_id}/execute")
    def execute(action_id: str, body: ActionBody, request: Request, ctx=Depends(authenticated)):
        return approvals.execute(action_id, body.digest, ctx, auth.is_approver, request.state.request_id)

    @app.get("/runs/{run_id}")
    def get_run(run_id: str, ctx=Depends(authenticated)):
        return db.get_run(run_id, ctx)

    return app

