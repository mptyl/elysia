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
