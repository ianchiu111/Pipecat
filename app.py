#
# https://github.com/pipecat-ai/pipecat/blob/main/examples/transports/transports-livekit.py
# run with `python3 app.py -r <testing room name>`
#

import asyncio
import json
import os
import sys
from loguru import logger
from datetime import datetime

# LiveKit transport and configuration
from pipecat.runner.livekit import configure
from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport

# Aggregators
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
    LLMAssistantAggregatorParams,
)
# VAD (Voice Activity Detection)
from pipecat.audio.vad.silero import SileroVADAnalyzer
# Pipeline components
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
# Event Handlers
from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)

# Services from pipecat for OpenAI's STT, LLM, and TTS
from utils.pipecat_service.openai_stt import OpenAISTTServiceConfig
from utils.pipecat_service.openai_llm import OpenAILLMServiceConfig
from utils.pipecat_service.openai_tts import OpenAITTSServiceConfig
from utils.user_tagging import UserTaggingProcessor

from dotenv import load_dotenv
load_dotenv(override=True)

# logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

# ============= Initialize =============

system_prompt = """
You are a helpful sales assistant listening to a multi-person voice conversation. 
Your responses will be spoken aloud, so avoid emojis, bullet points, or other formatting that can't be spoken. 

You will receive transcripts formatted like "[Speaker_ID says]: message". 
Pay close attention to who is speaking. A conversation will typically have a Sales rep and a Client.

Your job is to listen to the flow of the conversation, understand the interaction between the different speakers, and provide a brief, helpful suggestion or summary based on the client's needs.
"""

## pipecat service
tts = OpenAITTSServiceConfig(voice="alloy")._tts()
stt = OpenAISTTServiceConfig(model="whisper-1")._stt()
llm = OpenAILLMServiceConfig(
    model="gpt-4o-mini",
    system_instruction=system_prompt
)._llm()

## self-defined processor
user_tagger = UserTaggingProcessor()

## Aggregators
context = LLMContext()
user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
    context,
    user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    assistant_params=LLMAssistantAggregatorParams(),
)

# ============= Main =============
async def main():
    (url, token, room_name) = await configure()

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

    pipeline = Pipeline(
        [
            transport.input(),     # input from LiveKit
            stt,
            user_tagger,
            user_aggregator,       # aggregate user input into context
            llm,  
            tts,
            transport.output(),    # output to LiveKit
            assistant_aggregator,  # aggregate assistant output into context
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )
    
    # When first participant connect to LiveKit, this event will be triggered
    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport, participant_id):
        await asyncio.sleep(1)
        await task.queue_frame(
            TranscriptionFrame(
                text="Testing, testing, 1, 2, 3. This is a test of the emergency broadcast system.",
                user_id="user",
                timestamp=str(datetime.now().timestamp()),
            )
        )

    # When receiving text or JSON messages, this event will be triggered
    @transport.event_handler("on_data_received")
    async def on_data_received(transport, data, frame: Frame):
        # convert data from bytes to string
        json_data = json.loads(data)
        logger.debug(f"Receive original data: {json_data}")

        await task.queue_frames(
            [
                InterruptionFrame(),
                UserStartedSpeakingFrame(),
                TranscriptionFrame(
                    user_id=frame.user_id,
                    timestamp=json_data["timestamp"],
                    text=json_data["message"],
                ),
                UserStoppedSpeakingFrame(),
            ],
        )

    runner = PipelineRunner()

    await runner.run(task)


if __name__ == "__main__":
    asyncio.run(main())