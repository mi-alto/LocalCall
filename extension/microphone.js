globalThis.microphoneError = error => ({
  NotAllowedError: 'Permesso microfono negato. Consenti il microfono al browser nelle Impostazioni di Sistema del Mac → Privacy e sicurezza → Microfono, e nelle autorizzazioni del browser.',
  NotFoundError: 'Nessun microfono trovato. Collega un microfono e riprova.',
  OverconstrainedError: 'Il microfono selezionato non è disponibile. Scegli Predefinito di sistema e riprova.',
  NotReadableError: 'Il browser non riesce ad aprire il microfono. Controlla il dispositivo o scegline un altro.',
  SecurityError: 'Il browser ha bloccato l’accesso al microfono. Controlla le autorizzazioni.'
}[error.name] || 'Impossibile usare il microfono ('+(error.name||'errore')+'). '+(error.message||''));
