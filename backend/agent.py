"""
# AI Agent aims to be a neccessary participant in WebRTC meeting room, providing real-time transcription, meeting summary, action items, etc.
>>> run `python agent.py start` to start the agent server
>>> Background Thread run FastAPI
>>> Main Thread run LiveKit Agent
"""
import time
import asyncio
import json
import sys
import os
import threading
import uvicorn
import requests
from loguru import logger

# ===== FastAPI & Token imports =====
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from livekit import api

# LiveKit transport
from livekit.agents import AgentServer, JobContext, cli

from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import (
    Frame,
    TextFrame,
    InterruptionFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)

# Aggregators
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
    LLMAssistantAggregatorParams,
)
# VAD (Voice Activity Detection)
from pipecat.audio.vad.silero import SileroVADAnalyzer

# Pipeline and Task
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask

# Services from pipecat for OpenAI's STT, LLM, and TTS
from utils.pipecat_service.openai_stt import OpenAISTTServiceConfig
from utils.pipecat_service.openai_llm import OpenAILLMServiceConfig
from utils.pipecat_service.openai_tts import OpenAITTSServiceConfig
from utils.user_tagging import UserTaggingProcessor
from utils.transcript_sender import TranscriptSender
from prompts import get_system_prompt

from dotenv import load_dotenv
load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")


# ==========================================
# 1. FastAPI Web Server for Token Generation
# ==========================================
app = FastAPI()

# 設定 CORS (建議透過環境變數控制，開發時可先用 ["*"] 允許所有來源)
frontend_url = os.getenv("FRONTEND_URL", "*") 

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url] if frontend_url != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": time.time()}

@app.get("/api/token")
async def get_token(room: str, username: str):
    if not room or not username:
        raise HTTPException(status_code=400, detail="Missing room or username")

    token = api.AccessToken(
        os.getenv("LIVEKIT_API_KEY"),
        os.getenv("LIVEKIT_API_SECRET")
    )
    token.with_identity(username).with_name(username).with_grants(
        api.VideoGrants(
            room_join=True,
            room=room,
            can_publish=True,
            can_subscribe=True,
        )
    )
    return {"token": token.to_jwt()}

def run_fastapi():
    # Render 會自動提供 PORT 環境變數，如果沒有則預設使用 8000
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"啟動 FastAPI Token 伺服器於 port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)


server = AgentServer()

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    # 1. LiveKit Agent 框架作為「任務接收者」連線
    await ctx.connect()
    logger.info(f"Dispatcher successfully joined room: {ctx.room.name}")

    # ============= Generate Token for Pipecat =============
    livekit_url = os.getenv("LIVEKIT_URL")
    if not livekit_url:
        raise ValueError("請確認已設定 LIVEKIT_URL 環境變數")

    pipecat_token = api.AccessToken(
        os.getenv("LIVEKIT_API_KEY"),
        os.getenv("LIVEKIT_API_SECRET")
    ).with_identity("ai-agent-pipecat").with_name("AI Assistant").with_grants(
        api.VideoGrants(
            room_join=True,
            room=ctx.room.name, 
            can_publish=True,
            can_subscribe=True,
        )
    ).to_jwt()

    # ============= Initialize Services =============
    user_tagger = UserTaggingProcessor()
    
    tts = OpenAITTSServiceConfig(voice="alloy")._tts()
    # stt = OpenAISTTServiceConfig(model="whisper-1")._stt()
    stt = OpenAISTTServiceConfig(model="gpt-4o-realtime-preview")._stt()
    llm = OpenAILLMServiceConfig(
        model="gpt-4o-mini",
        system_instruction=get_system_prompt()
    )._llm()

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
        assistant_params=LLMAssistantAggregatorParams(),
    )

    # ============= Transport =============
    """
    Must use these configs:
    >>> url=livekit_url,
    >>> room_name=ctx.room,
    >>> token=pipecat_token
    """
    transport = LiveKitTransport(
        url=livekit_url,
        room_name=ctx.room,
        token=pipecat_token,
        params=LiveKitParams(
            audio_in_enabled=True,
            audio_out_enabled=False, 
            transcription_out_enabled=True,
        ),
    )

    # self-defined processor
    user_transcript_sender = TranscriptSender(transport, "User")
    agent_transcript_sender = TranscriptSender(transport, "Agent")

    # === Pipeline and Task===
    pipeline = Pipeline([
        transport.input(),          # Receive Input (Speech, Text messages from chat)
        stt,                        
        user_tagger,                # Tag User's transcription with speaker ID
        user_transcript_sender,   # Intercept user's transcription and send to frontend UI, Testing
        user_aggregator,            # Check if user has stopped speaking, aggregate transcription into user message, and send to LLM
        llm,                       
        agent_transcript_sender,  # Intercept agent's transcription and send to frontend UI, Testing
        tts,                        
        transport.output(),         # Output with speech
        assistant_aggregator        # Record Agent's conversation
    ])

    task = PipelineTask(
        pipeline, 
        params=PipelineParams()
    )

    runner = PipelineRunner()

    # ==== Transport Event Handlers ====

    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport: LiveKitTransport, participant_id):
        await asyncio.sleep(1)
        await task.queue_frame(
            TTSSpeakFrame(
                "Testing, testing"
            )
        )

    @transport.event_handler("on_participant_connected")
    async def on_participant_connected(transport: LiveKitTransport, participant_id):
        logger.info(f"Participant {participant_id} joined! Agent is starting service.")
        await task.queue_frames([TextFrame("Hello, I'm AI Agent for this meeting room.")])

    @transport.event_handler("on_participant_disconnected")
    async def on_participant_disconnected(transport: LiveKitTransport, participant_id):
        logger.info(f"❌ Participant disconnected: {participant_id}")

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport: LiveKitTransport, participant_id, reason):
        logger.info(f"❌ Participant left: {participant_id}, reason: {reason}")

    @transport.event_handler("on_data_received")
    async def on_data_received(transport: LiveKitTransport, data, participant_id):
        logger.info(f"Received data from participant {participant_id}: {data}")
        # convert data from bytes to string
        json_data = json.loads(data)

        await task.queue_frames(
            [
                InterruptionFrame(),
                UserStartedSpeakingFrame(),
                TranscriptionFrame(
                    user_id=participant_id,
                    timestamp=json_data["timestamp"],
                    text=json_data["message"],
                ),
                UserStoppedSpeakingFrame(),
            ],
        )

    logger.debug("Agent 連線中...")
    await runner.run(task)


# ====================================================
# Keep-Alive: prevent Render free-tier from sleeping
# ====================================================
def _keep_alive():
    """
    Ping the /health endpoint every 13 minutes to prevent the Render
    free-tier server from sleeping due to inactivity.
    """
    # Render provides BACKEND_API_URL automatically in production
    base_url = os.environ.get("BACKEND_API_URL", "")
    if not base_url:
        logger.warning("Keep-alive skipped: No BACKEND_API_URL found.")
        return

    # Ensure URL ends with a slash for safety, then add health
    ping_url = f"{base_url.rstrip('/')}/health"
    interval = 13 * 60  # 13 minutes
    
    # Wait a bit for the server to actually start up before first ping
    time.sleep(30)
    
    while True:
        try:
            resp = requests.get(ping_url, timeout=10)
            logger.info(f"Keep-alive ping successful: {ping_url} [{resp.status_code}]")
        except Exception as exc:
            logger.warning(f"Keep-alive ping failed: {exc}")
        
        time.sleep(interval)


if __name__ == "__main__":

    # 1. Start FastAPI in background
    api_thread = threading.Thread(target=run_fastapi, daemon=True)
    api_thread.start()

    # 2. Start Keep-Alive in background
    keep_alive_thread = threading.Thread(target=_keep_alive, daemon=True, name="keep-alive")
    keep_alive_thread.start()

    # 3. Start LiveKit Agent (Main Thread)
    cli.run_app(server)