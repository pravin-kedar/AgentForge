import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, chat, conversations
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, request_context_middleware
from app.tools.registry import TOOL_REGISTRY  # noqa: F401  (import triggers startup duplicate-name validation)

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("agentforge")

app = FastAPI(
    title="AgentForge",
    description="LLM-powered travel planning agent with function calling and tool orchestration.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(request_context_middleware)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(conversations.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
