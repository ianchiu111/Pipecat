### =======================
# Combined FastAPI server + pipecat agent runner
#
# Provides:
#   GET  /health       - Health check (used by Render keep-alive)
#   POST /start-agent  - Start the AI agent for a given LiveKit room
#
# Run: python server.py
# The server listens on PORT env var (default 10000).
#
# This approach runs everything in ONE asyncio event loop, avoiding the
# livekit-agents multiprocessing worker pool that times out on free-tier
# instances (0.1 CPU / 512 MB).
### =======================

import asyncio
import os
import sys
from contextlib import asynccontextmanager

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="INFO")

# agent.py is imported at module level; its heavy model initialisation only
# runs inside run_agent() when the first /start-agent request arrives.
from agent import run_agent  # noqa: E402

# ---- Agent lifecycle tracking (room_name -> asyncio.Task) ----
_agent_tasks: dict[str, asyncio.Task] = {}

BACKEND_URL = os.getenv("BACKEND_URL", "")
KEEP_ALIVE_INTERVAL = int(os.getenv("KEEP_ALIVE_INTERVAL", "240"))  # seconds

# Restrict CORS to the configured frontend origin, or allow all if not set.
# Set FRONTEND_URL env var in production (e.g. https://your-app.vercel.app).
_frontend_url = os.getenv("FRONTEND_URL", "")
CORS_ORIGINS: list[str] = [_frontend_url] if _frontend_url else ["*"]


async def _keep_alive():
    """Periodically ping the /health endpoint to prevent Render free-tier spin-down."""
    if not BACKEND_URL:
        logger.info("BACKEND_URL not set – keep-alive disabled")
        return
    url = f"{BACKEND_URL}/health"
    async with httpx.AsyncClient() as client:
        while True:
            await asyncio.sleep(KEEP_ALIVE_INTERVAL)
            try:
                resp = await client.get(url, timeout=10)
                logger.info(f"Keep-alive ping successful: {url} [{resp.status_code}]")
            except Exception as exc:
                logger.warning(f"Keep-alive ping failed: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start keep-alive background task
    task = asyncio.create_task(_keep_alive())
    yield
    task.cancel()


# ---- FastAPI app ----

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,  # /start-agent uses no cookies or auth headers
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/start-agent")
async def start_agent(room: str):
    """Trigger the AI agent to join a LiveKit room.

    If an agent is already running for the given room it is left untouched.
    The agent runs as a background asyncio task (no subprocess spawning).
    """
    existing = _agent_tasks.get(room)
    if existing and not existing.done():
        logger.info(f"Agent already running for room: {room}")
        return {"status": "already_running", "room": room}

    async def _run():
        try:
            await run_agent(room)
        except Exception as exc:
            logger.error(f"Agent error in room {room}: {exc}")
        finally:
            _agent_tasks.pop(room, None)
            logger.info(f"Agent task completed for room: {room}")

    task = asyncio.create_task(_run())
    _agent_tasks[room] = task
    logger.info(f"Started agent for room: {room}")
    return {"status": "started", "room": room}


# ---- Entry point ----

def run_fastapi():
    port = int(os.getenv("PORT", 10000))
    logger.info(f"Starting FastAPI server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    run_fastapi()
