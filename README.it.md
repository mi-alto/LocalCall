# LocalCall

App locale per macOS Apple Silicon e un’estensione Chrome/Brave per registrare riunioni, raccogliere gli indicatori visibili dei partecipanti e produrre trascrizioni con nomi e tempi. Italiano, inglese e rilevamento automatico della lingua. Nessuna API AI remota, nessun account necessario per trascrivere.

## Avvio su questo Mac

1. Doppio clic su **Avvia LocalCall.command**. Lascia aperta la finestra del Terminale durante registrazione ed elaborazione.
2. Si apre l’interfaccia locale su `http://127.0.0.1:8765`. Il modello è già scaricato e verificato.
3. Per registrare una nota personale: inserisci titolo, nome e lingua, poi **Registra microfono** → **Termina e trascrivi**.
4. Per una riunione: configura una volta l’estensione seguendo i passaggi qui sotto.

La trascrizione avviene **dopo lo stop**. Durante la call il plugin mostra i parlanti identificati, non una trascrizione live. L’interfaccia locale mostra le registrazioni, lo stato e il testo finale. Esportazioni TXT, SRT e JSON.

## Estensione Chrome / Brave

Pacchetto pronto: [LocalCall-browser-0.2.0.zip](dist/LocalCall-browser-0.2.0.zip). Estrai lo ZIP e carica la cartella LocalCall; in alternativa usa la cartella extension del progetto. [Guida completa](INSTALLAZIONE.md). Una sola estensione per **Meet e Teams web**, non Teams desktop.

1. Apri `chrome://extensions` in Chrome, oppure `brave://extensions` in Brave.
2. Attiva **Modalità sviluppatore**, scegli **Carica estensione non pacchettizzata**, seleziona la cartella `extension` di questo progetto.
3. Nell’app LocalCall premi **Copia codice per l’estensione**.
4. Apri le **Impostazioni** dell’estensione, incolla il codice, inserisci il tuo nome e scegli la lingua. Premi **Salva e verifica**.
5. Se vuoi includere la tua voce, premi **Abilita microfono** e concedi il permesso. Scegli il dispositivo e attiva la relativa casella: il microfono è disattivato inizialmente e viene catturato separatamente dalla scheda.
6. Nella scheda della call Meet/Teams premi l’icona dell’estensione e **Avvia registrazione**. Per finire, **Termina e trascrivi**.
7. Premi **Apri trascrizioni**. La sessione diventa “Pronta” al termine dell’elaborazione.

Richiede Chrome 116+ o una versione Brave compatibile con `tabCapture` e documenti offscreen. Chrome è stato collaudato automaticamente con un profilo isolato; Anche Brave è stato collaudato con audio sintetico. La cattura completa dalla barra di Chrome è stata verificata su una pagina Meet simulata; una call reale non è ancora stata collaudata. Su macOS può essere necessario concedere al browser l’accesso al microfono nelle Impostazioni di Sistema.

Usa cuffie per ridurre l’eco. Il microfono dell’estensione è **indipendente dal tasto muto della call**: registra la voce locale anche quando Meet/Teams è in muto. Disattiva la relativa opzione se non lo desideri. Avvisa i partecipanti prima della registrazione.

## Modelli e hardware

Hardware rilevato in questa sessione: **Apple M3, 16 GiB RAM**.

- Whisper **large-v3-turbo Q5_0**, pesi aperti, 574.041.195 byte. In esecuzione con whisper.cpp/Metal: un modello bilingue/multilingue evita due copie in memoria.
- Silero **v6.2.0**, 885.098 byte: rilevamento locale del parlato per ridurre output spuri nei silenzi.
- Una sola elaborazione alla volta, quattro thread CPU e accelerazione Metal. Il motore si chiude dopo ciascuna traccia, liberando la memoria.
- Non è una dichiarazione di superiorità assoluta su tutti i benchmark: Turbo quantizzato è la scelta pratica implementata e provata su questo M3; la precisione dipende da accenti, rumore, sovrapposizioni e lingua.

Dipendenze già disponibili sul Mac del collaudo: Python 3.14.4, whisper.cpp 1.8.3, FFmpeg 7.1.1. Runtime Python senza pacchetti aggiuntivi. Su un altro Mac: Python 3.10+, `brew install whisper-cpp ffmpeg`, poi `python3 scripts/setup.py`. Setup scarica solo pesi pubblici da Hugging Face con revisione fissata e verifica SHA256. I download avvengono prima della registrazione; runtime e trascrizione non contengono chiamate di rete esterne. `LOCALCALL_CPU=1 python3 -m localcall.server` forza la CPU se Metal non è disponibile.

Fonti: [Whisper Turbo, modello e limiti](https://huggingface.co/openai/whisper-large-v3-turbo), [whisper.cpp](https://github.com/ggml-org/whisper.cpp), [pesi quantizzati](https://huggingface.co/ggerganov/whisper.cpp), [Silero per whisper.cpp](https://huggingface.co/ggml-org/whisper-vad), [cattura audio in Chrome](https://developer.chrome.com/docs/extensions/how-to/web-platform/screen-capture).

## Attribuzione dei parlanti e limiti

Il browser registra **due flussi** WebM/Opus (scheda e microfono); il server li converte localmente, trascrive con tempi a livello di parola e unisce le parole alle osservazioni DOM campionate ogni 500 ms. Il microfono è assegnato al nome configurato. Le osservazioni della scheda scadono dopo 1,25 secondi, evitando di prolungare un nome quando la pagina smette di aggiornarsi.

Gli adattatori in `extension/adapters.js` cercano nomi nelle tessere visibili e attributi/indicatori di parlato. Non leggono chat, cookie o credenziali e non utilizzano i sottotitoli remoti. Sono inclusi selettori grafici documentati da altri progetti, tra cui [MeetCheat](https://github.com/afreediz/MeetCheat/blob/main/src/content.js) e [Meeting Speaker Logger](https://github.com/bidheyakthapa/meet-speaker-detector). Sono indizi tecnici, **non API garantite** dai fornitori.

**Non è stata eseguita una call reale con partecipanti su Meet/Teams.** I test degli adattatori usano DOM controllati: non provano che i selettori corrispondano a ogni versione attuale dei servizi. L’estensione può registrare l’audio ma non trovare i nomi. Il popup lo segnala quando non vede un parlante: controlla che il nome segua davvero chi parla nella prima call di prova. Una pagina modificata, tessere fuori schermo, omonimi, cambi rapidi, più persone su uno stesso microfono e schede in background possono ridurre la precisione.

Non viene eseguito clustering acustico delle voci: l’attribuzione remota si basa sui segnali della pagina. In mancanza di evidenza, con segnali scaduti o sovrapposizioni, compare **Non identificato**. La frazione di copertura temporale esportata come `confidence` non è una probabilità calibrata di correttezza. I timestamp di Whisper sono stimati, non misure perfette dei confini fonetici. Italiano/inglese misti nello stesso discorso richiedono una verifica dedicata; il rilevamento automatico seleziona la lingua dell’audio.

## Privacy, persistenza e recupero

- Server vincolato esclusivamente a `127.0.0.1`, con verifica Host/Origin e codice Bearer casuale. Nessun ascolto sulla rete locale.
- Nessun analytics, CDN o font esterno; estensione autorizzata a comunicare solo con il server loopback.
- `data/` contiene audio, osservazioni, trascrizioni e codice di abbinamento, con permessi limitati all’utente. I file non sono cifrati dall’app: usa FileVault se desideri cifratura del disco. La privacy delle chiamate effettuate da Meet/Teams resta quella dei rispettivi servizi; LocalCall non introduce un servizio di trascrizione terzo.
- Blocchi audio inviati al Mac ogni due secondi, numerati e con retry idempotente. Nessun accumulo dell’intera call nella memoria del browser. Il contenitore continuo viene completato allo stop.
- Se il server resta irraggiungibile, la registrazione si arresta dopo i tentativi di invio: **i blocchi non consegnati possono andare persi**; quelli ricevuti restano sul disco. Non è un backup garantito in caso di crash o disconnessione.
- Dopo un riavvio, le sessioni incomplete risultano “Interrotte”: **Recupera / riprova** tenta di trascrivere quanto disponibile. Una sessione abbandonata mentre il server resta aperto è recuperabile dopo almeno 30 secondi senza nuovi dati. Un contenitore molto incompleto può non essere decodificabile.
- La cancellazione dall’interfaccia rimuove audio e trascrizione della sessione selezionata. Non è cancellazione sicura del supporto.

## Test

```sh
python3 -m unittest discover -s tests -v
npm ci
npx playwright install chromium
npm test
```

Per i test di inferenza generare i campioni sintetici con `python3 scripts/make_test_audio.py`, poi eseguire `LOCALCALL_INFERENCE_TEST=1 python3 -m unittest discover -s tests -v`. Anche i test browser richiedono questi campioni; usano un microfono finto, non quello reale. `CHROMIUM_PATH` permette di scegliere un eseguibile Chromium già presente. I test browser avviano un server su una porta libera con dati e profilo temporanei. Il test completo della barra del browser è separato e richiede un gesto nativo: `LOCALCALL_NATIVE_ACTION=1 node --test tests/extension_flow.test.js`. Dettagli e limiti del collaudo in `TEST_REPORT.md`.

## Licenza

Il codice di LocalCall è distribuito sotto [GNU GPL versione 3](LICENSE), esclusivamente questa versione (`GPL-3.0-only`). Strumenti e modelli di terze parti mantengono le proprie licenze; vedi [THIRD_PARTY.md](THIRD_PARTY.md).

## Avvio dal browser (0.3)

È disponibile il collegamento nativo descritto in [INSTALLAZIONE.md](INSTALLAZIONE.md): dopo la configurazione iniziale, **Attiva servizio** avvia il backend in background e abbina automaticamente l’estensione. Non serve il Terminale. Il modello si carica soltanto durante la trascrizione; il server leggero resta acceso. Dopo uno spostamento della cartella occorre registrare nuovamente il collegamento nativo.
