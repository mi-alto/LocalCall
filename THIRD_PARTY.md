# Third-party components

LocalCall uses separately installed tools and downloaded weights. A license for LocalCall's own source does not replace upstream terms. Review each upstream license before redistributing tools or weights.

- [whisper.cpp](https://github.com/ggml-org/whisper.cpp): local inference runtime, installed separately.
- [OpenAI Whisper large-v3-turbo](https://huggingface.co/openai/whisper-large-v3-turbo): transcription model; [quantized distribution](https://huggingface.co/ggerganov/whisper.cpp).
- [Silero VAD distribution for whisper.cpp](https://huggingface.co/ggml-org/whisper-vad): voice activity detection weights.
- [FFmpeg](https://ffmpeg.org/): audio conversion, installed separately; redistribution terms depend on its build.
- [Playwright](https://github.com/microsoft/playwright): development-only browser testing dependency, pinned in package-lock.json.

The browser adapter documentation previously referenced selector examples in [MeetCheat](https://github.com/afreediz/MeetCheat/blob/main/src/content.js) and [Meeting Speaker Logger](https://github.com/bidheyakthapa/meet-speaker-detector). These are not official provider APIs. Review provenance and applicable upstream terms before public release; this document is not a completed third-party licensing audit.

## Optional speaker verification

SpeechBrain ECAPA-TDNN weights: https://huggingface.co/speechbrain/spkrec-ecapa-voxceleb, revision `0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`, Apache-2.0 as declared by the model card. SpeechBrain: https://github.com/speechbrain/speechbrain (Apache-2.0). Weights are downloaded separately, not bundled in this repository. Credits: Desplanques, Thienpondt and Demuynck (ECAPA-TDNN), and the SpeechBrain authors. Model card retained alongside local weights.

Speaker runtime also uses PyTorch/TorchAudio (BSD-style licenses), NumPy (BSD), SciPy (BSD), Python SoundFile (BSD) and libsndfile (LGPL-2.1-or-later). Dependency license notices are retained in the separately installed environment. See https://github.com/pytorch/pytorch/blob/main/LICENSE and https://github.com/libsndfile/libsndfile/blob/master/COPYING .
