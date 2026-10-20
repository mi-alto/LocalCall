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
3. Save the manual code under **Collegamento manuale · avanzate** → **Verifica e salva codice**. Save your display name and language with **Salva nome e lingua**.
4. To include your own voice, select a device and choose **Abilita e verifica il microfono**. Grant access; successful verification saves and enables capture automatically for the next recording. This is off by default.

The pairing code authorizes access to the local app; it is not an online account. Keep it private. Microphone recording is independent of the meeting's mute button. Use headphones to reduce echo.

## Record a meeting

Open a meeting at `meet.google.com`, `teams.microsoft.com`, `teams.live.com` or `teams.cloud.microsoft`. Notify participants, then open LocalCall in that tab and choose **Avvia registrazione**. The optional macOS shortcut is Command+Shift+Y; conflicts can be resolved in the browser's extension shortcut settings.

**REC** means recording; **!** indicates a warning. Choose **Termina e trascrivi**, then **Apri trascrizioni** to see the final transcript after local processing. TXT, SRT and JSON exports are available.

This targets Meet and Teams **web**, not Teams desktop. Names depend on visible page indicators and have not yet been validated in a real call. Test with two participants before relying on attribution. Uncertain intervals remain unidentified.

## Optional browser-driven startup (0.3.0)

Install the extension first and copy its 32-letter ID from the browser extensions page. In this repository run:

```sh
python3 scripts/install_native_host.py --extension-id YOUR_EXTENSION_ID
```

This registers `org.localcall.launcher` for Chrome and Brave under your macOS user account. Only the explicitly supplied extension ID is authorized. If the two browsers show different IDs, supply `--extension-id` twice in the same command. Installing again replaces the authorized ID list.

Reload the extension and reopen the meeting tab after upgrading to 0.3.0 (the new permission is `nativeMessaging`). On a Meet/Teams page, the LocalCall invitation offers **Attiva servizio**. It starts the local server and pairs the extension automatically. You can also click **Attiva servizio sul Mac** in the extension popup. Then use the toolbar's **Avvia registrazione** button: accepting the invitation alone never records audio. The invitation appears on supported pages, including landing pages, not only after joining a call.

No Terminal window is needed in this mode. Whisper loads only during transcription and exits afterwards. The lightweight server stays running after activation; this version does not stop it automatically. A previously running 0.2 server must be closed before using the bridge.

Native messaging registration contains an absolute launcher path, as required by the browser. **After moving or renaming the project, rerun the installer.** If the extension ID changes, use its new ID. The legacy Finder/Terminal startup and manual pairing remain available when the bridge is not installed. An unpacked ZIP installation needs the same registration with its own extension ID.

To remove the bridge, remove `org.localcall.launcher.json` from the Chrome and Brave `NativeMessagingHosts` folders under `~/Library/Application Support/`, and remove `data/native-launcher` and `data/native-origins.json`. This does not remove recordings or stop an already-running server.

### Microphone setup (0.3.2)

From the popup choose **Configura la mia voce** (or the next-recording microphone button while recording). Select a device and press **Abilita e verifica il microfono**. Grant permission: a successful check automatically enables and saves microphone capture for the next recording. No extra checkbox or save step is needed. The test stream is closed immediately; the current recording is not changed. Errors now distinguish permission denial, missing devices, unavailable saved devices and device read failures.

Name/language have their own save button. Manual pairing is under the advanced disclosure. These controls replace the earlier microphone/pairing steps above.
