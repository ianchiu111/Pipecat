### =======================
# Add AI agent into RTC room as a participant with LiveKit Transport
# run `python agent.py --room <RoomName>` to add the agent into a specific room
### =======================

import asyncio
import json
import sys
from loguru import logger

# LiveKit transport and configuration
from pipecat.runner.livekit import configure
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


# ============= Initialize =============

user_tagger = UserTaggingProcessor()

## pipecat service
tts = OpenAITTSServiceConfig(voice="alloy")._tts()
stt = OpenAISTTServiceConfig(model="whisper-1")._stt()
llm = OpenAILLMServiceConfig(
    model="gpt-4o-mini",
    system_instruction=get_system_prompt()
)._llm()

## Aggregators
context = LLMContext()
user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
    context,
    user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    assistant_params=LLMAssistantAggregatorParams(),
)

# ============= Main =============

async def main():

    url, token, room_name,  = await configure()

    transport = LiveKitTransport(
        url=url,
        token=token,
        room_name=room_name,
        params=LiveKitParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
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
        # user_transcript_sender,   # Intercept user's transcription and send to frontend UI, Testing
        user_aggregator,            # Check if user has stopped speaking, aggregate transcription into user message, and send to LLM
        llm,                       
        # agent_transcript_sender,  # Intercept agent's transcription and send to frontend UI, Testing
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

if __name__ == "__main__":
    asyncio.run(main())