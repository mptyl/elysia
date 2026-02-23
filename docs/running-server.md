# Avviare il Server Backend (`elysia start 0.0.0.0`)

Il comando `elysia start --host 0.0.0.0 --port 8090` (o simili) avvia il backend sulla porta **8090**, in ascolto su `0.0.0.0` (rendendolo accessibile da tutta la rete locale e non solo da localhost).

Questo documento spiega tre modi per tenerlo in esecuzione: a mano, con `nohup`, e con `tmux`.

---

## 1. Lancio manuale (foreground)

```bash
cd /opt/athena/elysia
elysia start --host 0.0.0.0 --port 8090
```

Il processo resta agganciato al terminale corrente. Se chiudi il terminale o premi `Ctrl+C`, il server si ferma terminando in automatico.

**Quando usarlo:** durante lo sviluppo locale, o quando vuoi vedere i log in tempo reale e non ti serve che resti in ascolto.

**Come fermarlo:** premi `Ctrl+C` nel terminale.

---

## 2. Lancio con `nohup` (background)

### Cos'è `nohup`

Quando chiudi un terminale (o una connessione SSH), il sistema operativo invia il segnale **SIGHUP** (Signal Hang Up) a tutti i processi figli di quel terminale. Per default, i processi che ricevono SIGHUP terminano.

`nohup` (= **no hang up**) fa due cose:

1. **Ignora il segnale SIGHUP**, quindi il processo sopravvive alla chiusura del terminale.
2. **Redirige stdout e stderr** su un file (`nohup.out` per default), dato che il terminale non sarà più disponibile per presentare l'output.

### Avviare

```bash
cd /opt/athena/elysia
nohup elysia start --host 0.0.0.0 --port 8090 > backend-server.log 2>&1 &
```

Spiegazione dei parametri:

| Parte | Significato |
|---|---|
| `nohup` | Protegge il processo dalla chiusura del terminale |
| `elysia start ...` | Il comando da eseguire per lanciare il server |
| `> backend-server.log` | Redirige stdout nel log file indicato |
| `2>&1` | Redirige anche stderr loggandolo nello stesso file |
| `&` | Manda il processo in background |

La shell stamperà un output tipo:

```
[1] 54321
```

Dove `54321` è il **PID** (Process ID). Annotalo, ti servirà per terminare il server in seguito.

### Consultare i log

```bash
# Ultime 50 righe del log
tail -50 /opt/athena/elysia/backend-server.log

# Seguire i log in tempo reale (premi Ctrl+C per uscire dal tail, il server NON si ferma)
tail -f /opt/athena/elysia/backend-server.log
```

### Fermare il processo

**Metodo 1 — se conosci il PID:**

```bash
kill 54321
```

**Metodo 2 — trovare il PID controllando la porta:**

```bash
ss -tlnp | grep 8090
# Output d'esempio: users:(("python",pid=54321,fd=5))

kill 54321
```

**Metodo 3 — trovare il PID dal nome del processo:**

```bash
pgrep -f "elysia start"
# Stampa il PID del processo in esecuzione

kill $(pgrep -f "elysia start")
```

**Metodo 4 — kill forzato (se per qualche motivo non dovesse rispondere al `kill`):**

```bash
kill -9 54321
```

> `kill` senza flag invia SIGTERM (terminazione pulita). `kill -9` invia SIGKILL (terminazione immediata e dal SO). Usa `-9` solo se il processo non risponde per un po' di tempo al comando standard.

### Verifica che il processo sia fermo

```bash
ss -tlnp | grep 8090
```

Se non mostra alcun output, la porta è libera con successo.

---

## 3. Lancio con `tmux` (sessione persistente e condivisa)

### Cos'è `tmux`

`tmux` (Terminal MUltiplexer) crea sessioni di terminale virtuali che continuano a vivere in modo indipendente anche se ti disconnetti. Puoi **rientrare nella sessione** in un momento successivo per vedere e interagire con l'output.

### Avviare

```bash
# Crea una sessione chiamata "backend" e lancia il server in quel terminale dedicato
tmux new-session -d -s backend "cd /opt/athena/elysia && elysia start --host 0.0.0.0 --port 8090"
```

*Nota: per creare sessioni persistenti condivise dal team (ad esempio con permessi sul gruppo `athena`), si può condividere una socket specifica in fase di avvio:*
```bash
tmux -S /tmp/elysia_tmux new-session -d -s backend "cd /opt/athena/elysia && elysia start --host 0.0.0.0 --port 8090"
chgrp athena /tmp/elysia_tmux
chmod 770 /tmp/elysia_tmux
```

### Vedere i log (entrare / riagganciarsi alla sessione)

```bash
tmux attach -t backend
# o, qualora sia stata configurata la socket condivisa: tmux -S /tmp/elysia_tmux attach -t backend
```

Sei tornato dentro la sessione. Mostrerà l'output di log generato nativamente.

**Per uscire dalla sessione tmux senza fermare il server (il cosiddetto detach):** premi la combinazione di tasti `Ctrl+B`, lascia andare e poi premi il tasto `D`.

### Fermare il processo

**Dall'interno della sessione di tmux:**

1. Agganciati alla sessione: `tmux attach -t backend`
2. Premi `Ctrl+C` (ferma il server bloccandone l'esecuzione)
3. La sessione potrebbe chiudersi da sola se era stata avviata con la sola stringa di comando iniziale; in caso di terminale interattivo rimasto orfano, digita `exit`.

**Dall'esterno:**

```bash
tmux kill-session -t backend
```

### Comandi tmux utili

| Comando | Significato |
|---|---|
| `tmux ls` | Elenca tutte le sessioni del tuo utente correntemente aperte |
| `tmux attach -t backend` | Rientra e ispeziona live lo stato e i log |
| `Ctrl+B, D` | (Tasti) Stacco della sessione corrente, mandandola in background a proseguire il processo  |
| `tmux kill-session -t backend` | Distruggi forzatamente la sessione e termina il server che girava dentro |

---

## 4. Gestire un tmux condiviso (setup Athena)

Su Athena il team condivide una singola sessione tmux a cui tutti i membri del gruppo `athena` possono agganciarsi. Questo permette a chiunque di controllare i log dei servizi, riavviarli, o lavorare in finestre separate senza dover chiedere a chi ha lanciato il processo.

### Come funziona

Normalmente ogni utente ha la propria directory di socket tmux (`/tmp/tmux-<UID>/default`), inaccessibile agli altri. Per condividere una sessione si crea una **socket condivisa** in un percorso noto, con i permessi impostati sul gruppo.

Sul server Athena:

| Elemento | Valore |
|---|---|
| Socket condivisa | `/tmp/shared-tmux` |
| Gruppo Unix | `athena` |
| Membri del gruppo | `leonardo.porcacchia`, `simone.mezzabotta`, `marco.pancotti` |
| Permessi socket | `srw-rwx---` (770 — owner e gruppo possono leggere, scrivere ed eseguire) |

### Creare la sessione condivisa

Chi crea la sessione per primo (un qualsiasi membro del gruppo) esegue:

```bash
# 1. Crea la sessione sulla socket condivisa
tmux -S /tmp/shared-tmux new-session -d -s athena

# 2. Imposta il gruppo e i permessi sulla socket
chgrp athena /tmp/shared-tmux
chmod 770 /tmp/shared-tmux
```

Dopo questi comandi, la socket `/tmp/shared-tmux` è accessibile a tutti i membri del gruppo `athena`.

> **Nota:** i passi 2 e 3 (`chgrp` e `chmod`) servono solo alla prima creazione. Se la socket esiste già con i permessi corretti (perché qualcun altro l'ha già creata), basta il primo comando.

### Agganciarsi alla sessione

Qualsiasi membro del gruppo `athena` può entrare nella sessione con:

```bash
tmux -S /tmp/shared-tmux attach -t athena
```

**Più utenti possono essere agganciati contemporaneamente.** Tutti vedono lo stesso output in tempo reale. Se un utente digita un comando, gli altri lo vedono apparire.

Per uscire senza chiudere la sessione: `Ctrl+B`, poi `D`.

### Gestire le finestre (windows)

Una sessione tmux può avere più **finestre** (tabs), ciascuna con il proprio terminale. Questo è il modo consigliato per gestire più servizi (backend, frontend, ecc.) all'interno della stessa sessione condivisa.

```bash
# Creare una nuova finestra con un nome
tmux -S /tmp/shared-tmux new-window -t athena -n backend

# Lanciare un comando in quella finestra
tmux -S /tmp/shared-tmux send-keys -t athena:backend \
  "cd /opt/athena/elysia && elysia start --host 0.0.0.0 --port 8090" Enter

# Creare un'altra finestra per il frontend
tmux -S /tmp/shared-tmux new-window -t athena -n frontend
tmux -S /tmp/shared-tmux send-keys -t athena:frontend \
  "cd /opt/athena/elysia-frontend && npm run dev:server" Enter
```

Una volta agganciati alla sessione, si naviga tra le finestre con:

| Scorciatoia | Azione |
|---|---|
| `Ctrl+B, c` | Crea una nuova finestra |
| `Ctrl+B, ,` | Rinomina la finestra corrente |
| `Ctrl+B, n` | Va alla finestra successiva |
| `Ctrl+B, p` | Va alla finestra precedente |
| `Ctrl+B, 0-9` | Va alla finestra con quel numero |
| `Ctrl+B, w` | Mostra l'elenco delle finestre e permette di scegliere |

### Setup tipico per Athena

Un esempio di avvio completo della sessione condivisa con le finestre per i servizi principali:

```bash
#!/bin/bash
# Crea la sessione condivisa con la prima finestra (shell generica)
tmux -S /tmp/shared-tmux new-session -d -s athena -n shell
chgrp athena /tmp/shared-tmux
chmod 770 /tmp/shared-tmux

# Finestra per il backend
tmux -S /tmp/shared-tmux new-window -t athena -n backend
tmux -S /tmp/shared-tmux send-keys -t athena:backend \
  "cd /opt/athena/elysia && source .venv/bin/activate && elysia start --host 0.0.0.0 --port 8090" Enter

# Finestra per il frontend
tmux -S /tmp/shared-tmux new-window -t athena -n frontend
tmux -S /tmp/shared-tmux send-keys -t athena:frontend \
  "cd /opt/athena/elysia-frontend && npm run dev:server" Enter

# Torna alla finestra shell
tmux -S /tmp/shared-tmux select-window -t athena:shell

echo "Sessione 'athena' creata. Agganciati con: tmux -S /tmp/shared-tmux attach -t athena"
```

### Comandi rapidi per la sessione condivisa

Tutti i comandi tmux per la sessione condivisa richiedono `-S /tmp/shared-tmux`. Per comodità si può definire un alias:

```bash
# Aggiungere al proprio ~/.bashrc o ~/.zshrc
alias ta='tmux -S /tmp/shared-tmux attach -t athena'
alias tls='tmux -S /tmp/shared-tmux ls'
alias tks='tmux -S /tmp/shared-tmux kill-session -t athena'
```

Riepilogo dei comandi più frequenti:

| Comando | Significato |
|---|---|
| `tmux -S /tmp/shared-tmux ls` | Elenca le sessioni sulla socket condivisa |
| `tmux -S /tmp/shared-tmux attach -t athena` | Si aggancia alla sessione condivisa |
| `tmux -S /tmp/shared-tmux new-window -t athena -n <nome>` | Crea una nuova finestra nella sessione |
| `tmux -S /tmp/shared-tmux send-keys -t athena:<finestra> "<cmd>" Enter` | Invia un comando a una finestra specifica |
| `tmux -S /tmp/shared-tmux kill-window -t athena:<finestra>` | Chiude una singola finestra |
| `tmux -S /tmp/shared-tmux kill-session -t athena` | Chiude tutta la sessione e termina tutti i processi |

### Attenzione

- **La socket vive in `/tmp`:** al riavvio della macchina il file viene cancellato. La sessione va ricreata dopo ogni reboot.
- **Un solo creatore alla volta:** se la sessione `athena` esiste già sulla socket, `new-session` fallirà. Usare `attach` per agganciarsi a quella esistente.
- **Chi chiude, chiude per tutti:** `kill-session` termina la sessione per tutti gli utenti agganciati. Usare con cautela: preferire `Ctrl+B, D` per sganciarsi senza fermare nulla.
- **Permessi:** se un nuovo membro viene aggiunto al gruppo `athena` (tramite `usermod -aG athena <utente>`), deve fare logout/login (o `newgrp athena`) perché la membership diventi effettiva.
