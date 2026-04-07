
import json
from loguru import logger

from pipecat.transports.livekit.transport import LiveKitTransport
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import Frame, TextFrame

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