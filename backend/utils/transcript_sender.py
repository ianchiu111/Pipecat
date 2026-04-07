
import json
from loguru import logger

from pipecat.transports.livekit.transport import LiveKitTransport
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import Frame, TextFrame, LLMTextFrame, LLMFullResponseEndFrame, TranscriptionFrame

class TranscriptSender(FrameProcessor):
    def __init__(self, transport: LiveKitTransport, speaker_role):
        super().__init__()
        self.transport = transport
        self.speaker_role = speaker_role
        self.llm_response = "" 
        self.is_summary_mode = False  

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        # For User's speaking
        if isinstance(frame, TranscriptionFrame):
            msg = json.dumps({
                "type": "transcript", 
                "speaker": self.speaker_role,
                "text": frame.text,
                "isFinal": False 
            })
            await self.transport.send_message(msg)

        # For AI summary
        if isinstance(frame, LLMTextFrame):
            self.llm_response += frame.text

        elif isinstance(frame, LLMFullResponseEndFrame):
            if "#" in self.llm_response or "*" in self.llm_response:
                self.is_summary_mode = True

            msg_type = "summary" if self.is_summary_mode else "transcript"

            if self.llm_response.strip():
                msg = json.dumps({
                    "type": msg_type,
                    "speaker": self.speaker_role,
                    "text": self.llm_response,
                    "isChunk": False,
                    "isFinal": True 
                })
                await self.transport.send_message(msg)
            
            self.llm_response = ""
            self.is_summary_mode = False

        await self.push_frame(frame, direction)