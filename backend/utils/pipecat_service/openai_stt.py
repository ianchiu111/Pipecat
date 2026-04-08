
import os
from pipecat.services.openai.stt import OpenAISTTService, OpenAIRealtimeSTTService

class OpenAISTTServiceConfig:
    def __init__(self, model):
        self.model = model

    def _stt(self):
        # return OpenAISTTService(
        #     api_key=os.getenv("OPENAI_API_KEY"),
        #     settings=OpenAISTTService.Settings(
        #         model=self.model,
        #         language="en" # for english speaker
        #     )
        # )
    
        return OpenAIRealtimeSTTService(
            api_key=os.getenv("OPENAI_API_KEY"),
            settings=OpenAIRealtimeSTTService.Settings(
                model=self.model,
                noise_reduction="near_field",
            ),
        )