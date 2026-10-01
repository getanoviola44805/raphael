# Roadmap di Raphael

## Principio guida: un solo cervello, più facce

Tutto ciò che Raphael sa fare vive nel **core** (`RaphaelApp` in `src/core/app.py`):
modello, memoria, strumenti e cronologia. Le interfacce sono solo "facce" diverse
dello stesso core:

- la **finestra principale** (chat completa);
- il **pannello compatto** che compare quando lo chiami (scorciatoia o "Ehi Raphael");
- la **voce** (ascolto e risposta parlata);
- la modalità **terminale**.

Ogni nuova capacità si aggiunge al core, quindi è disponibile **subito in tutte le
facce**, senza doppioni. Il pannello compatto deve avere sempre tutti gli strumenti:
controllo del PC, lettura dei file, memoria e ricerca web.

## Fatto

- [x] Chat con Ollama (qwen3.5:35b-a3b) in streaming, con cronologia salvata
- [x] Ricerca web (`/cerca` e strumento automatico) con fonti
- [x] Finestra con Markdown, allegati immagine, Ctrl+V, pulsante 🧠 Ragiona
- [x] Eseguibile Windows con icona
- [x] Controllo del PC: aprire programmi, siti e file, cercare file, data e ora
- [x] Memoria a lungo termine (`/memoria`, `/ricorda`, `/dimentica` e strumenti automatici)
- [x] Lettura dei file senza allegarli: testo, codice, PDF, Word, PowerPoint ed elenco cartelle
- [x] Azioni, pacchetto 1 (fondamenta): conferma con pulsanti, registro delle azioni
      (`/registro`), annulla (`/annulla`), sola lettura (`/solalettura`),
      creare cartelle e salvare testo in un file
- [x] Interfaccia pulita, rotonda e tutta scura: colonna centrata, fumetti arrotondati,
      cerchio sfumato che gira, casella arrotondata con 📎 e 🧠, tasto Copia,
      barra del titolo scura
- [x] Protezione dalle azioni finte: il simbolo ⚙️ compare solo quando uno strumento
      è stato usato davvero

## In preparazione

- [ ] Azioni, pacchetto 2: volume (generale e per app), musica, timer e promemoria
      con notifica, screenshot, "guarda lo schermo", calcolatrice esatta

## Da fare

1. **Raphael sempre presente**
   - icona nell'area di notifica, vicino all'orologio
   - avvio insieme a Windows
   - scorciatoia Ctrl+Spazio per chiamarlo
2. **Pannello compatto animato** (design originale)
   - finestrella scura semitrasparente con bordo blu→viola, come l'icona
   - sfera animata con quattro stati: in attesa, in ascolto, sta pensando, sta parlando
   - casella di testo e risposta breve
   - **tutti gli strumenti del core**: controllo del PC, lettura dei file, memoria e ricerca web
   - pulsanti Conferma/Annulla per le azioni a rischio
3. **Voce**
   - 🎤 ascolto con faster-whisper
   - risposta parlata con **Kokoro** (voce principale Sara, alternativa Nicola);
     XTTS-v2 solo come prova se serve più naturalezza
   - motore vocale intercambiabile
   - modalità voce con risposte brevi e parlate, interrompibile
   - da verificare: compatibilità di Kokoro con Python 3.14 (kokoro-onnx o ambiente separato)
4. **Parola d'attivazione "Ehi Raphael"** (openWakeWord o Porcupine), che apre il pannello compatto
5. **Altre azioni sul PC**: l'elenco completo, con i livelli di rischio e l'ordine
   in cui farle, è in [azioni.md](azioni.md). Le fondamenta (conferma, registro
   e annulla) sono pronte: si continua con il pacchetto 2.
6. **Rifiniture dell'interfaccia**: nuova conversazione, impostazioni, avvio automatico di Ollama
7. **AI Router con un modello cloud** per i compiti più pesanti