# Welcome
This project implements a real-time, multi-user conversational AI voice agent. The system is divided into a modern web frontend and a Python-based AI backend, communicating seamlessly via WebRTC.

## System: Frontend (Client & Token API)
- Tech Stack: `Next.js`, `React`, `TypeScript`.
- RTC Interface: Utilizes `@livekit/components-react` to build a responsive, real-time meeting room UI.
- Authentication: A `Next.js API route` uses the `livekit-server-sdk` to securely generate dynamic room access tokens based on user inputs.
- Real-time UI: Listens to `WebRTC Data Channels` to instantly render AI-generated transcripts.

## System: Backend (AI Voice Agent)
- Tech Stack: `Python`, `Pipecat AI Framework`.
- AI Pipeline: Orchestrates `Voice Activity Detection (VAD)`, `Speech-to-Text (STT)`, `LLM processing`, and `Text-to-Speech (TTS)` into a continuous, low-latency stream.

## Reference
1. [LiveKit](https://livekit.com)
2. Pipecat
    - [Github Repo](https://github.com/pipecat-ai/pipecat/tree/main)
    - [Docs](https://docs.pipecat.ai/server/services/stt/openai)

## Code Examples
1. [transports-livekit](https://github.com/pipecat-ai/pipecat/blob/main/examples/transports/transports-livekit.py)

