# LocalCall

Local meeting recording and transcription for Apple Silicon Macs, with a Chrome/Brave extension for Google Meet and Microsoft Teams on the web. Audio is processed on your Mac using open-weight models; LocalCall does not send recordings or transcripts to an AI service.

[Documentazione italiana](README.it.md) · [Installation](INSTALLATION.md) · [Test report (Italian)](TEST_REPORT.md)

## Status

Experimental, version 0.2.0. Transcription runs **after recording stops**, not live. The interface currently uses Italian; transcription supports Italian, English and automatic language detection.

The same extension targets Meet and Teams web in Chrome and Brave. Teams desktop, Safari and Firefox are not supported. Speaker names come from visible page elements and speaking indicators, not acoustic voice clustering. Real meeting layouts have **not yet been validated**; missing or ambiguous evidence is labeled “Non identificato” (unidentified).

## Requirements and setup

- macOS with Apple Silicon; tested on an Apple M3 with 16 GiB RAM.
- Python 3.10+, FFmpeg and whisper.cpp. Tested versions: Python 3.14.4, FFmpeg 7.1.1 and whisper.cpp 1.8.3.
- Chrome 116+ or a compatible current Brave release.

```sh
brew install whisper-cpp ffmpeg
python3 scripts/setup.py
python3 -m localcall.server
```

Setup downloads Whisper large-v3-turbo Q5_0 (approximately 574 MB) and Silero VAD, using pinned revisions and SHA256 verification. Model weights are not included in Git. This is a tested practical configuration, not a claim of best accuracy across all benchmarks. The VAD timestamp parser is verified against whisper.cpp 1.8.3; other versions require testing.

Alternatively, open `Avvia LocalCall.command` and keep its Terminal window open. Use the local app at `http://127.0.0.1:8765`; the launcher opens it with its local pairing token. CPU fallback: `LOCALCALL_CPU=1 python3 -m localcall.server`.

Load the `extension` directory as an unpacked extension, then follow [INSTALLATION.md](INSTALLATION.md) to pair it. Create an installable ZIP with `python3 scripts/package_extension.py` (output in `dist/`).

## Recording and speaker attribution

The extension records tab audio and, optionally, the microphone on a shared audio clock. Microphone capture is **off by default** and independent of Meet/Teams mute: if enabled, it records even while the meeting microphone is muted. Use headphones and notify participants before recording.

Page observations are sampled every 500 ms and expire after 1.25 seconds. Whisper word timestamps are combined with these observations. Rapid speaker changes, overlap, hidden tiles, iframes, background tabs and provider layout updates can reduce attribution accuracy. The microphone track uses the configured local name; echo detection is only a heuristic. Confidence values are not calibrated probabilities.

Stop recording to process locally and export TXT, SRT or JSON. If the microphone disconnects, tab recording continues with a warning. Incomplete sessions may be recoverable, but audio not delivered to the server can be lost and truncated containers may not decode.

## Privacy and storage

The server listens only on `127.0.0.1` and checks Host, Origin and a random bearer token. Recordings, participant observations, transcripts and pairing credentials live in `data/`, which Git ignores. LocalCall does not encrypt these files; disk encryption is an operating-system responsibility. Meet/Teams still use their own network services for the call.

Never publish `data/`, recordings, browser profiles, tokens, raw review prompts or diagnostic output containing participant information. The default Git exclusions also cover model weights, dependencies, test output, local reviews and generated packages.

## Development and tests

```sh
python3 -m unittest discover -s tests -v
python3 scripts/make_test_audio.py
LOCALCALL_INFERENCE_TEST=1 python3 -m unittest discover -s tests -v
npm ci
npx playwright install chromium
npm test
```

Synthetic audio generation uses macOS voices. Browser tests start isolated temporary servers and profiles. `CHROMIUM_PATH` selects an installed Chromium-family executable. The optional full toolbar test requires a native user gesture:

```sh
LOCALCALL_NATIVE_ACTION=1 node --test tests/extension_flow.test.js
```

Recorded validation: 32 Python tests with real local inference; three browser tests on Chrome and Brave; one full Chrome extension capture flow on a simulated Meet page. No real multi-person Meet/Teams call, hours-long recording or WER/DER benchmark has been validated. See [TEST_REPORT.md](TEST_REPORT.md) for scope and limitations.

## Project layout

- `localcall/`: Python server, speaker attribution and local web interface.
- `extension/`: Manifest V3 extension, recorder and Meet/Teams page adapters.
- `scripts/`: model setup, synthetic audio and ZIP packaging.
- `tests/`: server, inference and browser tests.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines and [THIRD_PARTY.md](THIRD_PARTY.md) for upstream components. LocalCall source is licensed under the [GNU General Public License v3.0 only](LICENSE) (`GPL-3.0-only`). Third-party tools and model weights retain their own licenses.
