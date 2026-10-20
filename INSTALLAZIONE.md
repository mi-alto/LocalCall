# LocalCall 0.3 — estensione per Chrome e Brave

È una sola estensione: funziona con **Google Meet e Microsoft Teams in versione web**, sia su Chrome sia su Brave. Non acquisisce la versione desktop di Teams e non è un’estensione Safari/Firefox.

## 1. Prepara l’app sul Mac

Apri **Avvia LocalCall.command** nella cartella del progetto `LocalCall`. Si apre l’interfaccia locale. Lascia aperta la finestra del Terminale durante registrazione e trascrizione. Per installare i modelli su un nuovo Mac, segui il README.

Se avevi la versione precedente in esecuzione, chiudila dal suo Terminale (Control+C), poi avvia nuovamente. Il pacchetto del browser non include l’app o i modelli: comunica con l’app presente sul Mac.

## 2. Installa il plugin

1. Estrai `LocalCall-browser-0.3.2.zip`. Otterrai la cartella **LocalCall**, contenente `manifest.json`.
2. Apri `chrome://extensions` in Chrome oppure `brave://extensions` in Brave.
3. Attiva **Modalità sviluppatore**.
4. Premi **Carica estensione non pacchettizzata** e seleziona la cartella **LocalCall** estratta, non lo ZIP.
5. Fissa LocalCall nella barra del browser dal menu delle estensioni (icona puzzle).

Se avevi già installato LocalCall da una cartella diversa, rimuovi la vecchia copia prima di aggiungere questa, per evitare due pulsanti uguali. Se carichi direttamente la cartella `extension` del progetto, puoi aggiornare premendo **Ricarica** nella scheda dell’estensione.

L’estensione non è pubblicata sul Chrome Web Store. È normale che il browser la mostri come estensione in modalità sviluppatore. Non serve installare plugin diversi per Meet e Teams.

## 3. Abbina il Mac e scegli il microfono

1. Nell’app LocalCall premi **Copia codice per l’estensione**.
2. Dal popup dell’estensione apri **Impostazioni** e incolla il codice.
3. Inserisci il tuo nome e scegli **Italiano**, **English** o rilevamento automatico.
4. Per includere la tua voce, apri **Configura la mia voce**, scegli il dispositivo e premi **Abilita e verifica il microfono**. Concedi il permesso: l’attivazione si salva automaticamente. Vale dalla prossima registrazione. Il microfono è disattivato inizialmente.
5. Nome e lingua si salvano con **Salva nome e lingua**. Il codice manuale, se necessario, si trova in **Collegamento manuale · avanzate** → **Verifica e salva codice**.

Il microfono del plugin è indipendente dal muto di Meet/Teams: se lo abiliti registra anche quando nella call sei in muto. Usa cuffie per evitare di registrare due volte la voce degli altri. Se non abiliti il microfono, viene registrato solo l’audio degli altri partecipanti riprodotto dalla scheda.

## 4. Registra

1. Entra nella call su `meet.google.com`, `teams.microsoft.com`, `teams.live.com` o `teams.cloud.microsoft`.
2. Avvisa i partecipanti della registrazione.
3. Dalla scheda della call premi l’icona LocalCall → **Avvia registrazione**. In alternativa usa **⌘⇧Y** se il comando non è già assegnato ad altro (gestibile in `chrome://extensions/shortcuts`).
4. Il badge **REC** indica la registrazione. **!** indica un avviso: apri il popup per leggerlo.
5. Premi **Termina e trascrivi**, poi **Apri trascrizioni**. Il testo finale arriva dopo l’elaborazione locale ed è esportabile in TXT, SRT e JSON.

Se il microfono viene scollegato, la registrazione degli altri continua e compare un avviso. Il plugin tenta di riprendere il dispositivo scelto quando cambia l’elenco dei dispositivi. Se non è disponibile, la tua voce manca; l’audio della scheda resta registrato.

## Compatibilità e limiti

Chrome/Brave devono supportare Manifest V3, tabCapture e offscreen (Chrome 116 o successivo; consigliata una versione aggiornata). I test automatici distinguono l’audio dalla lettura dei nomi. I nomi sono ricavati dalle tessere visibili e dagli indicatori del sito: aggiornamenti di Meet/Teams, layout, iframe e schede inattive possono impedire di identificarli. In quei punti il testo resta **Non identificato**. Una call reale con due persone è ancora necessaria per confermare la precisione nel tuo layout.

Le trascrizioni restano sul Mac. Internet serve a Meet/Teams per la call, ma LocalCall non invia audio o trascrizioni a servizi AI esterni.

## Avvio dal browser senza Terminale (0.3)

Dopo aver caricato l’estensione, copia il suo ID dalla pagina delle estensioni. Una sola volta, dalla cartella del progetto, esegui:

```sh
python3 scripts/install_native_host.py --extension-id ID_DELL_ESTENSIONE
```

Ricarica l’estensione e riapri la scheda Meet/Teams. Nel riquadro LocalCall premi **Attiva servizio**, oppure usa **Attiva servizio sul Mac** nel popup dell’estensione. Il backend parte in background e l’abbinamento è automatico. Per registrare, apri comunque l’estensione dalla barra e premi **Avvia registrazione**: la sola attivazione non registra audio.

Il modello viene caricato solo durante la trascrizione, poi liberato. Rimane acceso soltanto il server leggero, senza Terminale. Il riquadro compare anche sulle pagine iniziali dei servizi, non solo nelle call. Chiudi un eventuale server 0.2 prima di usare questa funzione.

Il collegamento nativo richiede un percorso assoluto: se sposti o rinomini di nuovo la cartella, riesegui l’installazione. Se Chrome e Brave mostrano ID diversi, passa due opzioni `--extension-id` nello stesso comando. Il nuovo elenco sostituisce il precedente. L’avvio manuale resta disponibile.
