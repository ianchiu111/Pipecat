
import os
from pipecat.services.openai.stt import OpenAISTTService

class OpenAISTTServiceConfig:
    def __init__(self, model):
        self.model = model

    def _stt(self):
        return OpenAISTTService(
            api_key=os.getenv("OPENAI_API_KEY"),
            settings=OpenAISTTService.Settings(
                model=self.model
            )
        )
    