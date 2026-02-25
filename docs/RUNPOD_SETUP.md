# Setup RunPod - Luna RPG v4

Guida completa per configurare Luna RPG v4 su RunPod con doppio environment (SD WebUI + ComfyUI).

## Requisiti

- Account RunPod con crediti
- API Key OpenRouter (o altro provider LLM)
- API Key ElevenLabs (opzionale, per audio)
- Link diretti ai modelli Civitai (se vuoi usare modelli specifici)

## Fase 1: Preparazione Locale (PC)

### 1.1 Configura i file necessari

Crea un file `.env` basato su `.env.runpod.example`:

```bash
cp docs/.env.runpod.example .env
```

Modifica `.env` con le tue chiavi API:
- `OPENROUTER_API_KEY`
- `ELEVENLABS_API_KEY`

### 1.2 Prepara il workflow video (se serve)

Il file `comfy_workflow_video_base.json` è già configurato per RunPod.

## Fase 2: Setup RunPod

### 2.1 Crea l'istanza

1. Vai su [runpod.io](https://runpod.io)
2. Clicca "Deploy" → "GPU Cloud"
3. Seleziona template: **PyTorch 2.4.0 - CUDA 12.1**
4. Scegli GPU: **RTX 4090** (consigliata) o **RTX A6000**
5. Storage: **100 GB** (minimo consigliato)
6. Avvia

### 2.2 Upload script di installazione

Nel terminale RunPod:

```bash
cd /workspace
# Upload via scp o usa l'editor di RunPod per creare il file
nano restore_runpod_v4.sh
# [Incolla il contenuto dello script]
chmod +x restore_runpod_v4.sh
```

### 2.3 Esegui installazione

```bash
./restore_runpod_v4.sh
```

**Tempo stimato**: 20-30 minuti (scarica ~20GB di modelli)

## Fase 3: Avvio Servizi

### 3.1 Avvia SD WebUI (Terminale 1)

```bash
/workspace/start_sd.sh
```

Attendi il messaggio: `Running on local URL: http://0.0.0.0:7860`

### 3.2 Avvia ComfyUI (Terminale 2)

```bash
/workspace/start_comfy.sh
```

Attendi il messaggio: `Starting server`

### 3.3 Configura Proxy RunPod

Nel pannello RunPod:
1. Vai su "Connect"
2. Aggiungi Proxy:
   - Porta 7860 (SD WebUI) → HTTP
   - Porta 8188 (ComfyUI) → HTTP

## Fase 4: Upload Progetto

### 4.1 Crea cartella progetto

```bash
mkdir -p /workspace/luna-rpg-v4
```

### 4.2 Upload file progetto

Dal tuo PC:

```bash
# Usa scp o rsync
scp -r src/ storage/ pyproject.toml .env user@runpod-ip:/workspace/luna-rpg-v4/
```

Oppure usa l'editor RunPod per creare i file manualmente.

### 4.3 Installa dipendenze Python

```bash
cd /workspace/luna-rpg-v4
pip install -e .
```

## Fase 5: Avvio Luna RPG

### 5.1 Test connessione

```bash
cd /workspace/luna-rpg-v4
python -c "from src.luna.core.config import get_settings; print(get_settings().execution_mode)"
# Deve stampare: RUNPOD
```

### 5.2 Avvia l'applicazione

```bash
python -m luna
```

## Troubleshooting

### Errore: "Model not found"

Verifica che i nomi dei modelli nel workflow JSON corrispondano a quelli scaricati:

```bash
ls -la /workspace/ComfyUI/models/unet/
ls -la /workspace/ComfyUI/models/vae/
```

### Errore: "CUDA out of memory"

Per GPU con memoria limitata, modifica i parametri in SD WebUI:
- Aggiungi `--medvram` o `--lowvram` in `/workspace/start_sd.sh`

### Errore: "Connection refused" da Luna

Verifica che i servizi siano in ascolto:

```bash
# Verifica SD WebUI
curl http://localhost:7860/sdapi/v1/samplers

# Verifica ComfyUI
curl http://localhost:8188/system_stats
```

### Workflow non funziona

1. Apri ComfyUI nel browser (URL dal proxy RunPod)
2. Carica il workflow: `comfy_workflow_video_base.json`
3. Verifica che tutti i nodi siano corretti (nessun rosso)
4. Se mancano nodi, installali tramite ComfyUI Manager

## Ottimizzazioni

### Per velocizzare la generazione

1. **Usa SageAttention** (già incluso nello script)
2. **Riduci risoluzione video**: Modifica `VIDEO_WIDTH` e `VIDEO_HEIGHT` in `.env`
3. **Riduci frame**: `VIDEO_FRAMES=41` (invece di 81)

### Per salvare spazio

I modelli occupano molto spazio. Se hai limiti:

```bash
# Elimina modelli non usati
rm /workspace/ComfyUI/models/unet/wan2.1_i2v_720p_q4.gguf  # Se usi solo 480p
```

## Sicurezza

⚠️ **Importante**: RunPod espone le porte su internet pubblica!

1. Usa password forti per tutti i servizi
2. Disabilita l'accesso quando non usi il pod
3. Non committare mai le chiavi API nel repository

## Backup

Per salvare il lavoro prima di chiudere il pod:

```bash
# Crea archivio
tar -czf luna_backup_$(date +%Y%m%d).tar.gz /workspace/luna-rpg-v4/storage/

# Scarica via scp
scp user@runpod-ip:/workspace/luna-rpg-v4/luna_backup_*.tar.gz ./backups/
```

## Supporto

Per problemi specifici:
- **SD WebUI**: [AUTOMATIC1111 Wiki](https://github.com/AUTOMATIC1111/stable-diffusion-webui/wiki)
- **ComfyUI**: [ComfyUI Examples](https://comfyanonymous.github.io/ComfyUI_examples/)
- **Wan 2.1**: [ComfyUI-GGUF Issues](https://github.com/city96/ComfyUI-GGUF/issues)
