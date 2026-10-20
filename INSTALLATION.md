# Install LocalCall

## Start the Mac app

Install the requirements and models as described in [README.md](README.md). Open `Avvia LocalCall.command`, or run `python3 -m localcall.server`. Keep the server running during recording and transcription. If an older version is running, stop it with Control+C first.

## Install the browser extension

1. Open `chrome://extensions` in Chrome or `brave://extensions` in Brave.
2. Enable **Developer mode**, choose **Load unpacked**, and select this repository's `extension` folder.
3. Alternatively, run `python3 scripts/package_extension.py`, extract the ZIP in `dist/`, and select its extracted `LocalCall` folder.
4. Pin LocalCall in the browser toolbar. Use one installation per browser, not separate copies for Meet and Teams.

The extension is not published on the Chrome Web Store. Unpacked installations must remain in their selected folder. After updating source files, reload the extension from the extensions page.

## Pair the extension

The interface currently uses Italian:

1. In the local app, click **Copia codice per l’estensione** (copy pairing code).
2. Open the extension's **Impostazioni** (settings) and paste the code.
3. Enter your display name and select the language. Click **Salva e verifica** (save and verify).
4. To include your own voice, choose **Abilita microfono**, grant access, select a device and enable **Registra anche il mio microfono**. This is off by default.

The pairing code authorizes access to the local app; it is not an online account. Keep it private. Microphone recording is independent of the meeting's mute button. Use headphones to reduce echo.

## Record a meeting

Open a meeting at `meet.google.com`, `teams.microsoft.com`, `teams.live.com` or `teams.cloud.microsoft`. Notify participants, then open LocalCall in that tab and choose **Avvia registrazione**. The optional macOS shortcut is Command+Shift+Y; conflicts can be resolved in the browser's extension shortcut settings.

**REC** means recording; **!** indicates a warning. Choose **Termina e trascrivi**, then **Apri trascrizioni** to see the final transcript after local processing. TXT, SRT and JSON exports are available.

This targets Meet and Teams **web**, not Teams desktop. Names depend on visible page indicators and have not yet been validated in a real call. Test with two participants before relying on attribution. Uncertain intervals remain unidentified.
