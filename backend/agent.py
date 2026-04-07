# # agent.py
# run `python agent.py --room insurance-room` to start the agent

import asyncio
import json
import os
import sys
from loguru import logger

# LiveKit transport and configuration
from pipecat.runner.livekit import configure
from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

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

from pipecat.frames.frames import TextFrame

# Services from pipecat for OpenAI's STT, LLM, and TTS
from utils.pipecat_service.openai_stt import OpenAISTTServiceConfig
from utils.pipecat_service.openai_llm import OpenAILLMServiceConfig
from utils.pipecat_service.openai_tts import OpenAITTSServiceConfig
from utils.user_tagging import UserTaggingProcessor

# Event Handlers
from pipecat.frames.frames import (
    Frame,
    InterruptionFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
    # LLMTextFrame,
    # LLMFullResponseEndFrame,
)

from dotenv import load_dotenv
load_dotenv(override=True)

logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

# ============= 自訂攔截器 (FrameProcessor) =============
class TranscriptSender(FrameProcessor):
    def __init__(self, transport: LiveKitTransport, speaker_role):
        super().__init__()
        self.transport = transport
        self.speaker_role = speaker_role

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # 如果這個幀是文字幀，就打包成 JSON 送給前端
        if isinstance(frame, TextFrame) and frame.text.strip():
            msg = json.dumps({
                "type": "transcript",  # 我們靠這個來讓前端辨識
                "speaker": self.speaker_role,
                "text": frame.text
            })

            # 修正：移除 topic 參數，並且直接傳遞 string (msg) 而非 bytes
            await self.transport.send_message(msg)
        
        await self.push_frame(frame, direction)

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

user_tagger = UserTaggingProcessor()


## Aggregators
context = LLMContext()
user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
    context,
    user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    assistant_params=LLMAssistantAggregatorParams(),
)

async def main():

    url, token, room_name,  = await configure()

    # transport = LiveKitTransport(url, token, room_name)
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

    user_transcript_sender = TranscriptSender(transport, "User")
    agent_transcript_sender = TranscriptSender(transport, "Agent")

    # === Pipeline and Task===
    pipeline = Pipeline([
        transport.input(),          # 1. 接收語音
        stt,                        # 2. 語音轉文字
        user_tagger,                # 3. 打上說話者標籤
        user_transcript_sender,     # 4. 攔截 User 文字，傳給前端 UI
        user_aggregator,            # 5. 等 User 講完話
        llm,                        # 6. LLM 思考生成文字
        agent_transcript_sender,    # 7. 攔截 Agent 文字，傳給前端 UI
        tts,                        # 8. 文字轉語音
        transport.output(),         # 9. 語音回傳 LiveKit
        assistant_aggregator        # 10. 紀錄 Agent 對話
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
                "Testing, testing, 1, 2, 3. This is a test of the emergency broadcast system."
            )
        )

    @transport.event_handler("on_participant_connected")
    async def on_participant_connected(transport: LiveKitTransport, participant_id):
        logger.info(f"客戶 {participant_id} 加入了！Agent 開始服務。")
        # 主動打招呼
        await task.queue_frames([TextFrame("您好，我是您的專屬保險顧問 Agent Lee，請問今天想了解哪方面的保障呢？")])

    @transport.event_handler("on_participant_disconnected")
    async def on_participant_disconnected(transport: LiveKitTransport, participant_id):
        logger.info(f"❌ Participant disconnected: {participant_id}")

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport: LiveKitTransport, participant_id, reason):
        logger.info(f"❌ Participant left: {participant_id}, reason: {reason}")

    ## https://github.com/pipecat-ai/pipecat/blob/main/examples/transports/transports-livekit.py
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