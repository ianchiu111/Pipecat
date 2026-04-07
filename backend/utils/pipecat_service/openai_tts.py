
import os
from pipecat.services.openai.tts import OpenAITTSService

class OpenAITTSServiceConfig:
    def __init__(self, voice):
        self.voice = voice

    def _tts(self):
        return OpenAITTSService(
            api_key=os.getenv("OPENAI_API_KEY"),
            settings=OpenAITTSService.Settings(
                voice=self.voice
            )
        )