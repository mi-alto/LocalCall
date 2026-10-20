# Third-party components

LocalCall uses separately installed tools and downloaded weights. A license for LocalCall's own source does not replace upstream terms. Review each upstream license before redistributing tools or weights.

- [whisper.cpp](https://github.com/ggml-org/whisper.cpp): local inference runtime, installed separately.
- [OpenAI Whisper large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo): transcription model; [quantized distribution](https://huggingface.co/ggerganov/whisper.cpp).
- [Silero VAD distribution for whisper.cpp](https://huggingface.co/ggml-org/whisper-vad): voice activity detection weights.
- [FFmpeg](https://ffmpeg.org/): audio conversion, installed separately; redistribution terms depend on its build.
- [Playwright](https://github.com/microsoft/playwright): development-only browser testing dependency, pinned in package-lock.json.

The browser adapter documentation previously referenced selector examples in [MeetCheat](https://github.com/afreediz/MeetCheat/blob/main/src/content.js) and [Meeting Speaker Logger](https://github.com/bidheyakthapa/meet-speaker-detector). These are not official provider APIs. Review provenance and applicable upstream terms before public release; this document is not a completed third-party licensing audit.
