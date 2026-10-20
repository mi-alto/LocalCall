# Install LocalCall on macOS

## 1. Download the project and models

Requirements: Apple Silicon Mac, Python 3.10 or newer, Homebrew, and Chrome 116+ or a compatible Brave version. The tested machine has 16 GiB RAM. See [README.md](README.md) for tested dependency versions and limitations.

```sh
git clone https://github.com/mi-alto/LocalCall.git
cd LocalCall
brew install whisper-cpp ffmpeg
python3 scripts/setup.py
```

The setup script downloads and verifies the public model weights. Audio stays local during recording and transcription. The weights are not included in this repository.

## 2. Load the extension

1. Open `chrome://extensions` or `brave://extensions`.
2. Enable **Developer mode** → **Load unpacked**.
3. Select the repository's **extension** folder, containing `manifest.json`. Select a folder, not a ZIP.
4. Pin LocalCall in the browser toolbar and copy its 32-letter extension ID.

Alternatively, generate a ZIP with `python3 scripts/package_extension.py`, extract it, and load the extracted `LocalCall` folder. The extension is not published on the Chrome Web Store.

## 3. Enable browser-driven startup

From the repository folder, replace `YOUR_EXTENSION_ID` with the ID copied above:

```sh
python3 scripts/install_native_host.py --extension-id YOUR_EXTENSION_ID
```

This registers the local launcher for Chrome and Brave under your macOS account. If the browsers show different IDs, supply `--extension-id` twice in the same command. Installing again replaces the authorized ID list. Only those extension IDs can use the launcher.

Open the LocalCall popup and click **Attiva servizio sul Mac**. The backend starts without a Terminal window and pairs automatically. On supported Meet/Teams pages, the invitation's **Attiva servizio** button does the same. Neither action starts recording.

Whisper loads only during transcription and exits afterwards. The lightweight server remains running after activation. Close a previously running older server before using the updated launcher.

**After moving or renaming the project, rerun the installer:** native registration requires an absolute launcher path. If you reinstall the extension from another folder, check whether its ID changed.

### Manual startup alternative

If you do not install the native launcher, open `Avvia LocalCall.command` and keep its Terminal window open. In the local app, choose **Nuova registrazione / Impostazioni** → **Copia codice per l’estensione**. Paste the code in the extension settings under **Collegamento manuale · avanzate**, then click **Verifica e salva codice**.

The pairing code authorizes the local connection; it is not an online account. Keep it private.

## 4. Configure your voice

The interface currently uses Italian:

1. In the popup choose **Configura la mia voce** or open **Impostazioni**.
2. Select the microphone and press **Abilita e verifica il microfono**.
3. Allow access when prompted. A successful check automatically enables and saves microphone capture for the next recording; the check stream then stops.
4. Enter your display name, select the language, and click **Salva e chiudi**.

Microphone capture is off by default and independent of the meeting's mute button: if enabled, it records even when you are muted in Meet/Teams. Use headphones to reduce echo. Changes apply to the next recording, not one already running. Without microphone capture, your own voice may be absent.

## 5. Record and transcribe

Supported sites: `meet.google.com`, `teams.microsoft.com`, `teams.live.com`, `teams.cloud.microsoft`. Teams desktop is not supported.

Notify participants, open the extension **from the meeting tab**, and choose **Avvia registrazione**. The optional macOS shortcut is Command+Shift+Y; resolve conflicts in the browser's extension shortcut settings.

**REC** indicates recording, including when there are warnings. Open the popup to see whether it captures tab audio only or tab audio plus microphone. Choose **Termina e trascrivi**, then **Apri trascrizioni**. Processing runs on your Mac after recording stops. Export TXT, SRT or JSON from the transcript page.

History can be filtered by title, detected participant name/email and inclusive **Dal / Al** start-date boundaries. Setup and local microphone recording are on a separate page.

Speaker attribution depends on visible page signals. One live Teams layout was checked for speech/silence transitions; live Meet attribution and broad accuracy remain unverified. Test a short call before relying on the names. Missing evidence remains **Non identificato**. Emails appear only when explicitly exposed in the participant tile; old recordings do not gain missing names or emails retroactively.

## Updates and removal

Stop and save any active recording before updating. Pull the project updates, reload the extension on the browser extensions page and refresh the local app. Restart an idle backend after server changes. Do not reload an extension during recording.

To remove the native launcher, remove `org.localcall.launcher.json` from the Chrome and Brave `NativeMessagingHosts` folders under `~/Library/Application Support/`, plus `data/native-launcher` and `data/native-origins.json`. This does not remove recordings or stop an already-running backend.
