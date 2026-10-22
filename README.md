# LocalCall

Local meeting recording and transcription for Apple Silicon Macs, with a Chrome/Brave extension for Google Meet and Microsoft Teams on the web. Audio is processed on your Mac using open-weight models; LocalCall does not send recordings or transcripts to an AI service.

[Documentazione italiana](README.it.md) · [Installation](INSTALLATION.md) · [Test report](TEST_REPORT.md)

## Status

Experimental, extension version 0.3.8. Transcription runs **after recording stops**, not live. The interface currently uses Italian; transcription supports Italian, English and automatic language detection.

The same extension targets Meet and Teams web in Chrome and Brave. Teams desktop, Safari and Firefox are not supported. Speaker names come from visible page elements and speaking indicators, not acoustic voice clustering. One Teams web layout has been inspected live, including speech/silence transitions (see TEST_REPORT.md); full attribution accuracy and other layouts remain unverified. Missing or ambiguous evidence is labeled “Non identificato” (unidentified).

## Requirements and setup

- macOS with Apple Silicon; tested on an Apple M3 with 16 GiB RAM.
- Python 3.10+, FFmpeg and whisper.cpp. Tested versions: Python 3.14.4, FFmpeg 7.1.1 and whisper.cpp 1.8.3.
- Chrome 116+ or a compatible current Brave release.

```sh
git clone https://github.com/mi-alto/LocalCall.git
cd LocalCall
brew install whisper-cpp ffmpeg
python3 scripts/setup.py
python3 -m localcall.server
```

Setup downloads Whisper large-v3-turbo Q5_0 (approximately 574 MB) and Silero VAD, using pinned revisions and SHA256 verification. Model weights are not included in Git. This is a tested practical configuration, not a claim of best accuracy across all benchmarks. The VAD timestamp parser is verified against whisper.cpp 1.8.3; other versions require testing.

Alternatively, open `Avvia LocalCall.command` and keep its Terminal window open. Use the local app at `http://127.0.0.1:8765`; the launcher opens it with its local pairing token. CPU fallback: `LOCALCALL_CPU=1 python3 -m localcall.server`.

After one-time native bridge setup, the extension can start the backend without a Terminal window and pair automatically. Whisper is loaded only while transcribing; the idle Python server does not keep model weights in RAM. The lightweight server stays running after activation.

Load the `extension` directory as an unpacked extension, then follow [INSTALLATION.md](INSTALLATION.md) to pair it. Create an installable ZIP with `python3 scripts/package_extension.py` (output in `dist/`).

## Recording and speaker attribution

The extension records tab audio and, optionally, the microphone on a shared audio clock. Microphone capture is **off by default**. When enabled, it saves your voice only while the meeting page confirms that you are unmuted; muted, unknown and stale states produce silence. Use headphones and notify participants before recording.

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

Latest pre-publication validation: 40 Python tests passed with real local inference; 10 Node/browser tests passed on Chrome, with the native-toolbar test intentionally skipped. Earlier validation also covered three browser tests on Brave and one full Chrome extension capture flow on a simulated Meet page. A live two-participant Teams test verified DOM speaker signals; complete diarization accuracy, live Meet, hours-long recordings and WER/DER benchmarks remain unverified. See [TEST_REPORT.md](TEST_REPORT.md) for scope and limitations.

## Project layout

- `localcall/`: Python server, speaker attribution and local web interface.
- `extension/`: Manifest V3 extension, recorder and Meet/Teams page adapters.
- `scripts/`: model setup, synthetic audio and ZIP packaging.
- `tests/`: server, inference and browser tests.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines and [THIRD_PARTY.md](THIRD_PARTY.md) for upstream components. LocalCall source is licensed under the [GNU General Public License v3.0 only](LICENSE) (`GPL-3.0-only`). Third-party tools and model weights retain their own licenses.

## History

The sidebar searches meeting titles and detected participant names. Optional **Dal / Al** date filters use the recording start date in your local timezone and include both boundary days. The transcript page shows the detected participant list. Names not captured in old sessions cannot be recovered by this search. **Nuova registrazione / Impostazioni** opens the separate setup and microphone recording view.

Participant emails are captured only when explicitly exposed on the same meeting tile (email attributes or visible mailto links; Teams stream data-tid was observed to contain an address). No profile APIs, inferred addresses or chat-wide email scraping are used. Emails remain local, appear under participant names and are searchable in History. Availability depends on the provider and participant privacy settings; live Meet email extraction is not yet verified. Existing recordings without captured emails remain unchanged.

### Automatic stop and retained audio

Version 0.3.7 stops capture when the meeting tab closes or navigates outside Meet/Teams. After detecting the in-call leave button, it also stops when that control has been absent for at least 60 seconds. A background alarm checks every 30 seconds, including when tab timers are throttled. Silence alone never stops recording. This DOM-based heuristic needs a recognized leave control; changed provider layouts may still require manual stop. Reload the extension after upgrading, outside an active recording.

Original `remote.webm` (tab) and `mic.webm` (optional microphone) remain in `data/<session-id>/`. Enabled microphone capture follows the meeting mute state (version 0.3.8). Files are not uploaded to a transcription provider. Stop recordings before leaving the computer if automatic detection is unavailable.

Speech detection now retains 200 ms around speech and waits 500 ms before splitting a pause, reducing clipped words and fragmented context. Speech-boundary changes no longer automatically erase an otherwise observed speaker; real speaker changes and missing coverage remain conservative. This does not guarantee correct transcription, especially for distant microphones, echo, jargon or background voices.

### Meeting microphone privacy (0.3.8)

The microphone stream passes through a closed-by-default audio gain before the recorder. Only a fresh, explicit unmuted observation from an active meeting opens it. Muted/ambiguous states close it; permission expires after at most 1.25 seconds on the audio clock even if page timers stop. DOM changes and microphone toolbar pointer presses trigger immediate observations, with a 500 ms polling fallback. A small detection/message delay remains: this is not sample-accurate synchronization with the provider. English and Italian microphone action labels are supported; unrecognized layouts/languages leave the local voice silent. The device may remain open to preserve the continuous recording timeline, but blocked samples are replaced with silence before encoding/upload to localhost. This applies to browser meetings, not standalone microphone notes. Existing recordings are not retroactively redacted.

### Local speaker recovery

Run `python3 scripts/setup_speaker.py` once (requires `uv` and Apple Silicon on macOS). The separate Python 3.12 environment uses a hashed dependency lock and pinned SpeechBrain ECAPA-TDNN weights. A completion marker prevents use of partial installations. Whisper exits before ECAPA starts; ECAPA uses two CPU threads and bounded short audio reads. On macOS, `sandbox-exec` denies OS network operations. Hugging Face offline mode and Python socket guards are additional protections. The worker exits when its backend parent disappears.

Speaker attribution now runs audio-first across all VAD speech intervals in the remote track. Three-second ECAPA windows (1.5-second hop) are grouped with average-linkage cosine clustering; at most 1,600 embeddings train the clustering to bound quadratic memory. A cluster receives a browser name only after at least three separated, unambiguous observations with consistent support. Browser events must be sampled periodically (the extension samples every 500 ms); they expire after 1.25 seconds.

A temporal Viterbi decoder compares named voices and unnamed acoustic competitors. It can correct stale DOM names, or abstain. Transcript wording never affects speaker decisions. Microphone tracks and explicit manual corrections are protected. Real simultaneous speech, very short replies and uncertain transitions can remain unidentified: this is not source separation, and similarity scores are not calibrated probabilities.

Contiguous turns are grouped for display; unknown fragments with different diagnostic reasons can share a paragraph. Original attribution, word timing and acoustic provenance remain in JSON exports. SRT retains short underlying cues. Failures fall back to DOM rows with a warning. Existing saved sessions are not automatically rewritten.

The earlier targeted recovery and audit routines remain for regression comparisons; the server uses `ecapa-session-v1`. Experimental embedding caches are opt-in, local-only, ignored by Git, and not created by normal recording. Production diagnostics contain counts, not names or transcript text. No audio, embeddings or transcripts are sent to an LLM or external inference service.

Short unresolved transitions between different acoustic speakers receive a bounded multiscale change-point check (3/4.5/6-second context, at most 768 extra embedding requests per session). Words outside the plausible boundary collar may receive a name; the collar remains unknown. This step never uses transcript wording or human corrections and never relabels already resolved voice rows.

For a verified two-person browser call with separate microphone capture, unresolved short utterances receive a bounded three-scale ECAPA check (up to 192 extra windows). A second, explicitly marked **remote-channel** fallback requires exactly two stable roster identities, one remotely active identity, matching acoustic identity, and fresh agreeing roster/speaker observations around the word. A third participant, stale/missing observations or conflicting identities disables this fallback. Channel attribution is not claimed as a voice match and remains marked in the UI and TXT/SRT/JSON exports. The fallback also requires explicit browser identification of the local participant (extension 0.3.9), or a per-session two-person confirmation. It only processes the separate remote track and excludes words overlapping microphone VAD speech, with a 250 ms margin. Short acoustic recovery requires at least 1.5 seconds of target audio, including a gap-only embedding; neighboring speech alone cannot establish identity. Reload the unpacked extension after updating to collect the local identity.

Lost or rejected browser observations disable channel inference. Visible tiles are not a guaranteed full roster in pinned/limited gallery layouts; channel attribution remains explicitly distinguished from acoustic recognition.

Verified two-person sessions also receive a paired-profile acoustic pass after both tracks are transcribed. Remote reference windows require strong browser-named cluster support and no microphone VAD overlap; microphone references must lie outside remote VAD speech. Each profile uses at most 256 examples. Unknown remote words are compared against both profiles using the median of the five closest examples (remote similarity ≥0.40, margin over the local profile ≥0.15), with the existing word-coverage checks. This pass never changes resolved names or assigns the local name to remote audio. Missing/ambiguous participant evidence, lost browser events, inadequate references or a worker failure leave the previous result intact. Scores are not probabilities; short turns, echo and bad word alignment can still be wrong. `profile_recovery` provenance is retained in JSON. Processing is offline on two CPU threads, in a separate worker that exits afterward; temporary WAV files are removed after the paired pass, including failure paths. No new extension update is needed beyond 0.3.9.

Query windows exclude temporally overlapping remote references, so the same audio cannot support its own identification. Candidate windows overlapping microphone speech also receive a simultaneous-microphone echo veto (cosine ≥0.8); at most 256 additional queries are allowed, and remaining overlapping candidates abstain when that budget is exhausted.
