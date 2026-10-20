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
