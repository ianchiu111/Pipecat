
from loguru import logger

from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.frames.frames import Frame, TranscriptionFrame

class UserTaggingProcessor(FrameProcessor):
    async def process_frame(self, frame: Frame, direction: FrameDirection):

        # Let the base class handle system control frames (e.g., StartFrame, InterruptionFrame, etc) and internal state.
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):          
            # Add user ID to his/her transcription frames so the LLM can differentiate between speakers.   
            speaker_id = frame.user_id
            frame.text = f"[{speaker_id} says]: {frame.text}"
            
            logger.debug(f"Tagged transcription: {frame.text}")

        await self.push_frame(frame, direction)