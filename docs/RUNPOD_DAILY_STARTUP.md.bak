# Avvio Giornaliero RunPod - Procedura Corretta

**Problema:** Ogni volta che riavvii il Pod, ComfyUI sembra "scomparire" e devi reinstallare tutto.
**Soluzione:** I file sono già lì, devi solo avviarli correttamente!

---

## 🔍 Capire lo Stato del Pod

Quando riavvii un Pod su RunPod, ci sono due possibilità:

### Caso 1: Pod Sospeso (Sleep) → Riattivazione
- I file sono **già presenti** (nodi, modelli, tutto)
- Devi solo **riavviare ComfyUI**

### Caso 2: Pod Nuovo/Cancellato → Setup da zero
- Devi reinstallare tutto (usa `RUNPOD_SETUP_GUIDE.md`)

---

## 💾 Cosa è Persistentemente Salvato?

Quando riattivi un Pod esistente, **questi dati sono già lì** (non devi reinstallare):

| Location | Contenuto | Persiste? |
|----------|-----------|-----------|
| `/workspace/ComfyUI/` | ComfyUI + nodi installati | ✅ Sì |
| `/workspace/ComfyUI/models/` | Modelli scaricati (GGUF, VAE, etc) | ✅ Sì |
| Pacchetti pip installati | `torch`, `numpy`, etc | ✅ Sì |
| `/workspace/start_comfyui.sh` | Script di avvio | ✅ Sì |

**NON devi reinstallare:**
- ❌ Nodi custom (già in `custom_nodes/`)
- ❌ Modelli (già in `models/`)
- ❌ Requirements (pacchetti pip persistono)

**Devi solo:**
- ✅ Riavviare ComfyUI
- ✅ Liberare la porta se occupata

---

## ✅ Procedura di Avvio Rapido (Caso 1 - il più comune)

### Step 1: Connettiti al Pod via SSH/Web Terminal

### Step 2: Verifica se ComfyUI è già in esecuzione
```bash
# Controlla se c'è già un processo ComfyUI in running
ps aux | grep "python main.py"
```

**Se vedi un output** → ComfyUI è già attivo, vai a Step 4
**Se NON vedi nulla** → Procedi con Step 3

### Step 3: Libera la Porta (se occupata)
```bash
# Metodo 1: Uccidi processi Python di ComfyUI (funziona sempre)
pkill -f "python main.py" 2>/dev/null || true
sleep 3

# Metodo 2: Se ancora occupata, uccidi tutti i processi Python
# (Attenzione: questo uccide TUTTI i processi Python nel Pod)
ps aux | grep python | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true
sleep 3
```

### Step 4: Avvia ComfyUI
```bash
cd /workspace/ComfyUI
python main.py --listen 0.0.0.0 --port 8188
```

**Output atteso:**
```
Starting server
To see the GUI go to: http://0.0.0.0:8188
```

### Step 5: Verifica nel Browser
Apri l'URL del tuo Pod (es. `https://xxx-8188.proxy.runpod.net`) 

---

## ⚠️ Problemi Comuni e Soluzioni

### Problema: "Port 8188 is already in use"
```bash
# Soluzione: Uccidi tutti i processi Python e riprova
pkill -f "python main.py" 2>/dev/null || true
sleep 3
ps aux | grep python | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true
sleep 3
cd /workspace/ComfyUI && python main.py --listen 0.0.0.0 --port 8188
```

### Problema: "ModuleNotFoundError" (moduli mancanti)

**Nota importante:** I pacchetti pip installati in `/workspace/` sono **persistenti**.
Se hai già installato i requirements una volta, **non devi rifarlo** ad ogni avvio.

**Quando reinstallare:**
- Solo se vedi errori "ModuleNotFoundError"
- Solo se hai creato un Pod NUOVO (non riattivato)
- Solo se aggiorni i nodi (`git pull`)

```bash
# Reinstalla SOLO se necessario (NON ogni volta!)
cd /workspace/ComfyUI/custom_nodes/ComfyUI-Frame-Interpolation
python install.py

cd /workspace/ComfyUI/custom_nodes/ComfyUI-KJNodes
pip install -r requirements.txt

cd /workspace/ComfyUI/custom_nodes/ComfyUI-WanVideoWrapper
pip install -r requirements.txt

cd /workspace/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite
pip install -r requirements.txt

cd /workspace/ComfyUI/custom_nodes/ComfyUI-GGUF
pip install -r requirements.txt
```

### Problema: "GGUF chiede di scaricare ogni volta"

Se il nodo GGUF richiede di scaricare file ad ogni avvio, probabilmente cerca di scaricare la libreria `gguf` o file temporanei.

**Soluzione:**
```bash
# Verifica che la libreria gguf sia installata
pip list | grep gguf

# Se manca, reinstallala (una sola volta)
pip install gguf

# Se il problema persiste, il nodo potrebbe cercare di scaricare tokenizer
# Verifica che esista la cartella tokenizer
cd /workspace/ComfyUI/custom_nodes/ComfyUI-GGUF
ls -la

# Se mancano file, reinstalla il nodo completo
cd /workspace/ComfyUI/custom_nodes
git clone https://github.com/city96/ComfyUI-GGUF.git ComfyUI-GGUF-new
rm -rf ComfyUI-GGUF
mv ComfyUI-GGUF-new ComfyUI-GGUF
cd ComfyUI-GGUF
pip install -r requirements.txt
```

### Problema: "File not found" (modelli mancanti)
```bash
# Verifica che i modelli esistano
ls -la /workspace/ComfyUI/models/unet/*.gguf 2>/dev/null || echo "❌ Manca modello UNET"
ls -la /workspace/ComfyUI/models/vae/*.safetensors 2>/dev/null || echo "❌ Manca VAE"
ls -la /workspace/ComfyUI/custom_nodes/ComfyUI-Frame-Interpolation/ckpts/rife/*.pth 2>/dev/null || echo "❌ Manca RIFE"
```

---

## 🚀 Script di Avvio Automatico

Salva questo come `/workspace/start_comfyui.sh`:

```bash
#!/bin/bash

echo "🔍 Controllo processi esistenti..."
pkill -f "python main.py" 2>/dev/null || true
sleep 2

echo "🔓 Liberazione porta 8188..."
# Se ancora occupata, uccidi tutti i processi Python
ps aux | grep python | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true
sleep 2

echo "🚀 Avvio ComfyUI..."
cd /workspace/ComfyUI
python main.py --listen 0.0.0.0 --port 8188
```

Rendilo eseguibile:
```bash
chmod +x /workspace/start_comfyui.sh
```

**Uso futuro:**
```bash
/workspace/start_comfyui.sh
```

---

## 📝 Checklist Pre-Avio Luna

Prima di avviare Luna in modalità RUNPOD, verifica:

- [ ] Pod RunPod è **Running** (non sleeping)
- [ ] ComfyUI è **attivo** su porta 8188
- [ ] URL del Pod è **accessibile** dal browser
- [ ] File `.env` di Luna ha `COMFY_URL` corretto

### Configurazione `.env` (Windows)
```env
# Esempio
COMFY_URL=https://xy1a2b3c-8188.proxy.runpod.net
GEMINI_API_KEY=your_key_here
```

---

## 🔧 Perché Succede Questo?

**RunPod Persistence:**
- `/workspace/` → **Persistente** (i tuoi file restano)
- `/tmp/`, `/root/` → **Temporanei** (si cancellano)

**ComfyUI è in `/workspace/` → Dovrebbe persistere!**

Se perdi i dati ogni riavvio, probabilmente:
1. Stai usando un template che resetta `/workspace`
2. O stai creando un Pod nuovo invece di riattivare quello vecchio

**Soluzione:** Sempre clicca **"Resume"** sul Pod esistente, non crearne uno nuovo!

---

## 🆘 Se Tutto Fallisce

Se ComfyUI continua a non funzionare, verifica lo stato:

```bash
# 1. Sei in /workspace?
pwd

# 2. ComfyUI esiste?
ls -la /workspace/ComfyUI/main.py

# 3. I nodi esistono?
ls /workspace/ComfyUI/custom_nodes/

# 4. I modelli esistono?
ls /workspace/ComfyUI/models/unet/
```

**Se mancano i file** → Segui `RUNPOD_SETUP_GUIDE.md` per reinstallare
**Se i file ci sono** → Usa lo script sopra per avviare

---

**Ultimo aggiornamento:** 2026-02-24
