
import os
from pipecat.services.openai.llm import OpenAILLMService

class OpenAILLMServiceConfig:
    def __init__(self, model, system_instruction=None):
        self.model = model
        self.system_instruction = system_instruction

    def _llm(self):
        return OpenAILLMService(
            api_key=os.getenv("OPENAI_API_KEY"),
            settings=OpenAILLMService.Settings(
                model=self.model,
                system_instruction=self.system_instruction
            )
        )