# Update 0.3.5 — History and meeting titles

A targeted browser test passed for uniform History card height, visible start date/time, and cleaned Teams/Meet titles. The rendered History screenshot was inspected. New extension recordings read document.title from the meeting tab after injecting the adapter, stripping known provider suffixes, notification counters and join-page prefixes. Existing session titles are cleaned for display only; saved metadata is preserved. Displayed clock time is the recording start time in the viewer's local timezone, not the scheduled meeting time.

---

# Update 0.3.4 — Teams live DOM adapter

On 2026-10-20 the user's live Teams web test exposed remote tiles as `[data-cid="calling-participant-stream"]`, names under `[data-tid="participant-info-nametag"] [data-person-mri]`, and a `[data-tid="voice-level-stream-outline"]` with `data-is-speaking="true"` during speech and `"false"` during a user-confirmed silent interval. The self tile is `[data-tid="myself-video"]`.

The adapter now reads this structure and excludes the self tile by its marker, not by comparing display names. A generic `.vdi-frame-occlusion` class alone is no longer accepted as evidence of speech. The targeted browser adapter test passed with an anonymized fixture covering equal self/remote names, active, inactive and missing speech attributes. No private DOM or participant identifiers are included in the fixture.

This validates selectors and speech/silence signals on one live Teams layout, not every Teams layout or a complete updated recording-to-transcript run. Previously captured sessions without participant/speaker observations cannot gain reliable attribution merely by retranscribing the same audio. Google Meet live validation remains outstanding.

---

# Update 0.3.2 — simpler microphone setup

Nine Node/browser tests passed; the optional native-toolbar test was skipped. The Chrome component test now checks a denied microphone permission leaves capture disabled, then verifies successful synthetic microphone access automatically saves the enabled setting. Recorder/transcription regression tests passed. The microphone setup screenshot was inspected. No physical microphone or live recording was accessed during this change; the user’s actual permission/device failure still requires verification in their browser.

---

# Update 0.3.1 — recording status clarity

Six targeted Node tests passed: popup recording/idle/offline states, active-service button disabling, separate microphone warnings, preserved REC badge, and native worker authorization. No recording was restarted or interrupted for this UI change. Reload the extension only after stopping and saving an active recording.

---

# Update 0.3.0 — browser-driven backend startup

Validation after adding native messaging: **38 Python tests passed**, including real local inference, bounded native protocol messages, installer origin validation, detached backend startup and reuse of a real isolated server. **Five Node tests passed** (three Chrome browser regression tests and two worker authorization/token-isolation tests); the optional native toolbar capture test remained skipped in this run.

The installed macOS launcher was also invoked using the actual framed native protocol: it started the updated backend and returned a pairing token successfully. This checks the installed launcher, not the browser’s native-host discovery or the new on-page invitation in a live meeting. The extension must be reloaded to grant its new nativeMessaging permission. Automatic invitation visibility and end-to-end native-host discovery from the user’s Brave profile remain to be confirmed after reload.

The bridge does not preload Whisper. The lightweight server remains running after activation; model processes exit after transcription. The previously running inactive legacy server was stopped before validating the updated launcher. No private meeting audio was used.

---

# Collaudo LocalCall 0.2.0 — 20 ottobre 2026

Mac Apple M3, 16 GiB RAM; Python 3.14.4, whisper.cpp 1.8.3, FFmpeg 7.1.1. Campioni sintetici italiani e inglesi, profili browser e dati temporanei. Nessuna call privata utilizzata.

## Risultati verificati

**32 test Python superati**, con inferenza locale reale abilitata. Coprono autenticazione e isolamento loopback, attribuzione temporale, eventi assenti/scaduti/sovrapposti, esportazione, recupero, cancellazione e quattro prove del modello (italiano, inglese, silenzio e parlato separato da pause lunghe).

Le regressioni aggiunte verificano: seconda istanza senza alterazione delle registrazioni, metadati corrotti, JSONL troncato, recupero della coda audio non confermata, retry dopo fallimento del salvataggio senza duplicazioni, eventi malformati scartati singolarmente, eventi grandi, creazione idempotente e metadati di dimensione limitata.

**3 test browser superati su Chrome for Testing e su Brave**:

1. Adattatori Meet/Teams su pagine controllate: nomi e indicatori di parlato, elementi nascosti e widget inattivi. L'ultima esecuzione Chrome include anche esclusione della tessera locale e opacità zero.
2. Interfaccia: registrazione WebM sintetica, elaborazione locale reale ed esportazione; nessuna richiesta esterna o errore JavaScript osservato.
3. Componente registratore dell'estensione: due tracce, eventi dei parlanti, trascrizioni italiana e inglese, conferma di upload persa, errore degli eventi e microfono scollegato simulato. L'audio remoto continua. Questa prova avvia direttamente il componente; non dimostra da sola il percorso del pulsante sulla barra.

**Una prova completa aggiuntiva superata su Chrome, con pagina Meet simulata**: apertura dell'estensione con scorciatoia nativa, popup → worker → offscreen → vera cattura audio della scheda, osservazione della pagina, ripristino dopo ricaricamento, stop e trascrizione locale attribuita. Nessun mock di tabCapture. La pagina e l'audio sono sintetici: non è una riunione reale.

Il test completo è escluso dalla suite ordinaria perché richiede un gesto nativo nella finestra di prova. I tentativi aggiuntivi su Teams simulato/Brave non hanno completato questo passaggio di interazione e non costituiscono collaudi superati di tali combinazioni.

## Correzioni rilevanti

- Protezione da avvii multipli prima del recupero delle sessioni; scritture atomiche e retry audio senza duplicazioni.
- Microfono facoltativo e inizialmente spento, scelta dispositivo, avvisi e prosecuzione dell'audio remoto dopo perdita del microfono.
- Code audio ed eventi separate e limitate; un errore dei nomi non arresta l'audio.
- Orologio comune per le tracce, esclusione dei segnali scaduti e maggiore prudenza vicino ai cambi di parlante.
- Correzione osservata dei tempi di Whisper sulle pause lunghe tramite gli intervalli VAD. Il parser degli intervalli è verificato con whisper.cpp 1.8.3; versioni con log diversi richiedono nuova verifica.
- Recupero dell'osservatore dopo ricaricamento, risposta esplicita ai messaggi e avvisi visibili nel popup.
- Se una traccia non è elaborabile, l'altra può essere conservata con avviso. Il rilevamento di eco testuale è solo un'euristica.

## Limiti ancora da verificare

Nessuna call reale Meet/Teams con partecipanti è stata effettuata. I selettori DOM restano euristiche: layout diversi, iframe, schede inattive e modifiche dei servizi possono produrre “Non identificato”. Non è implementato clustering acustico delle voci.

Non collaudati: riunioni di ore, consumi massimi, sospensione del Mac, disconnessione fisica di periferiche, tutti i profili e permessi macOS, accuratezza WER/DER su voci reali e cambio lingua continuo. La disconnessione del microfono nei test è un evento simulato.

Prima dell'uso regolare serve una breve call reale con due persone, alternando frasi note e verificando nomi nel popup e tempi nell'esportazione. Il modello trascrive dopo lo stop; non offre testo live durante la call.

La review Claude e le riproduzioni in reviews documentano la versione precedente: non sono il rapporto della versione corretta. Gli script verify_findings.py e verify_options.mjs riproducono difetti storici e non fanno parte della suite corrente.
