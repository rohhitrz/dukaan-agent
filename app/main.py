"""FastAPI app: serves the chat UI and one /chat endpoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import agent, db, policy_search
from app.config import settings

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)-7s %(name)-18s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dukaan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    policy_search.load_policies()
    log.info("model=%s max_tool_iterations=%d", settings.openai_model, settings.max_tool_iterations)
    yield


app = FastAPI(title="Dukaan Agent", lifespan=lifespan)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str
    trace: list[dict]
    latency_ms: int
    steps: int


@app.exception_handler(Exception)
def unhandled(request: Request, exc: Exception) -> JSONResponse:
    # Without this an OpenAI auth/rate-limit error reaches the UI as a bare 500 with
    # no message. Surfacing the exception text is the whole debugging story in Phase 0.
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": f"{type(exc).__name__}: {exc}"})


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> dict:
    # The loop is blocking (sync OpenAI client + sqlite3), so FastAPI runs this
    # endpoint in a threadpool - that is what defining it as `def` and not
    # `async def` buys us here.
    return agent.chat(req.session_id, req.message)


@app.post("/reset")
def reset(session_id: str) -> dict:
    agent.reset(session_id)
    return {"ok": True}


@app.get("/health")
def health() -> dict:
    return {"ok": True, "model": settings.openai_model}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(settings.static_dir / "index.html")


app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")
