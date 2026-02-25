# Luna RPG v4 - Stato Progetto

## Data: 2026-02-24

---

## Sistema Video Completato ✅

### Workflow Video Attivo
File: `comfy_workflow_video.json`

**Caratteristiche:**
- **Modello**: Wan2.1 I2V (Image-to-Video)
- **Durata**: ~10 secondi (162 frame @ 16fps)
- **Risoluzione**: 480x896
- **Frame interpolation**: RIFE 2x (da 81 a 162 frame)
- **Colori**: Prompt ottimizzato per saturazione e contrasto

### Nodi Custom Installati su RunPod

1. **ComfyUI-Frame-Interpolation** (RIFE VFI)
   - Repository: `Fannovel16/ComfyUI-Frame-Interpolation`
   - Modello: `rife47.pth` in `ckpts/rife/`
   - Parametri: `clear_cache_after_n_frames: 10`

2. **ComfyUI-KJNodes**
   - Repository: `kijai/ComfyUI-KJNodes`
   - Nodi usati: `ImageResizeKJv2`

3. **ComfyUI-WanVideoWrapper**
   - Repository: `kijai/ComfyUI-WanVideoWrapper`
   - Nodo: `WanImageToVideo`

4. **ComfyUI-VideoHelperSuite**
   - Repository: `Kosinkadink/ComfyUI-VideoHelperSuite`
   - Nodo: `VHS_VideoCombine`

5. **ComfyUI-GGUF**
   - Repository: `city96/ComfyUI-GGUF`
   - Nodo: `UnetLoaderGGUF`

### Configurazione Modello RIFE

```bash
# Crea directory per il modello
mkdir -p /workspace/ComfyUI/custom_nodes/ComfyUI-Frame-Interpolation/ckpts/rife

# Scarica rife47.pth
wget -O /workspace/ComfyUI/custom_nodes/ComfyUI-Frame-Interpolation/ckpts/rife/rife47.pth \
  "https://github.com/hzwer/Practical-RIFE/releases/download/v4.7/rife47.pth"

# Oppure se già presente in models/:
ln -sf /workspace/ComfyUI/models/frame_interpolation/rife/rife47.pth \
  /workspace/ComfyUI/custom_nodes/ComfyUI-Frame-Interpolation/ckpts/rife/rife47.pth
```

### Flusso Workflow

```
1. UnetLoaderGGUF (Wan2.1_I2V_fp8)
2. VAELoader (wan_2.1_vae)
3. CLIPLoader (umt5_xxl_fp8)
4. LoadImage (input.png)
5. CLIPTextEncode (prompt positivo con colori saturati)
6. CLIPTextEncode (prompt negativo)
7. CLIPVisionLoader
8. CLIPVisionEncode
9. ImageResizeKJv2 (480x896)
10. WanImageToVideo (81 frame)
11. LoraLoader HIGH
12. LoraLoader LOW
13. KSamplerAdvanced 1/2
14. KSamplerAdvanced 2/2
15. VAEDecode
16. RIFE VFI (2x interpolation → 162 frame) ⭐
17. VHS_VideoCombine (output MP4)
```

### Prompt Ottimizzati

**Positivo:**
```
Cinematic photorealistic video, beautiful woman, graceful natural movement, 
detailed skin texture, soft lighting, continuous fluid motion, 8k masterpiece, 
vibrant saturated colors, rich colors, high contrast, colorful, vivid
```

**Negativo:**
```
(deformed, distorted, disfigured:1.3), poor quality, bad anatomy, ugly, 
text, watermark, blurry, low resolution, extra limbs, bad motion, morphing, 
cartoon, anime, (faded colors:1.2), washed out, grayscale, monochrome
```

---

## Sistema Auto-Switch Companion ✅

### Funzionamento
Quando il giocatore interagisce con un NPC non-companion, il sistema:

1. **Rileva** il target dal testo (es. "vedo una donna...")
2. **Crea** un companion temporaneo con `is_temporary=True`
3. **Switcha** il companion attivo
4. **Usa** NPC_BASE per l'immagine (senza LoRA dei companion)
5. **Salta** il personality engine (non modifica affinità)

### File Modificati
- `src/luna/core/engine.py`: `_detect_generic_npc_interaction()`, `_create_temporary_companion()`
- `src/luna/core/models.py`: `is_temporary` flag in `CompanionDefinition`
- `src/luna/systems/personality.py`: skip per NPC temporanei
- `src/luna/media/builders.py`: supporto `base_prompt` parametro

---

## Debug Mode ✅

Flag `--no-media` per testare senza ComfyUI:

```bash
python -m luna --no-media
```

Salta generazione immagini/video, mantiene solo LLM e audio.

---

## Problemi Risolti

| Problema | Soluzione |
|----------|-----------|
| Video troppo corto (5 sec) | Aggiunto RIFE 2x → 10 sec |
| Colori slavati | Prompt con "vibrant saturated colors, high contrast" |
| Nodo RIFE mancante | Installato ComfyUI-Frame-Interpolation + rife47.pth |
| Error 400 su RIFE | Aggiunto `clear_cache_after_n_frames: 10` |
| Companion parla per NPC | Implementato auto-switch con NPC temporanei |
| Error 404 su Gemini fallback | Fix nomi modelli: `gemini-1.5-pro-latest`, `gemini-1.5-flash-latest` |
| Config modelli hardcoded | Creato `src/luna/config/models.yaml` per configurazione esterna |
| JSON parse errors frequenti | Aggiunto `src/luna/ai/json_repair.py` per repair automatico |
| StateUpdate validation failed | Fix: gestione errori validazione Pydantic (updates = StateUpdate() vuoto) |
| NPC temporaneo non switcha | Fix: aggiunto NPC ad affinity system in `_create_temporary_companion` |
| Prompt SD con doppioni | Fix: rimossa istruzione dal system prompt che diceva al LLM di includere base prompt + migliorato detection duplicati |
| Outfit descrizione mancante | Fix: `ImagePromptBuilder` ora aggiunge outfit al prompt + system prompt istruisce LLM a descrivere vestiti |
| "studentessa" non switcha a Stella | Fix: aggiunto "studentessa" ai role patterns + aggiunti aliases per tutti i companion |
| LLM include vecchio companion dopo switch | Fix: aggiunta sezione "COMPANION SWITCH" nel system prompt che impone focus solo sul nuovo NPC |

---

## Configurazione Modelli LLM

File: `src/luna/config/models.yaml`

Modifica i modelli senza toccare il codice:

```yaml
gemini:
  primary: "gemini-3-pro-preview"
  fallbacks:
    - "gemini-2.0-flash"
    - "gemini-1.5-pro-latest"
    - "gemini-1.5-flash-latest"
  
  temperature: 0.95
  max_tokens: 2048

moonshot:
  primary: "kimi-k2.5"
  temperature: 0.9
```

### Modelli disponibili (Google AI)
- `gemini-3-pro-preview` - **Modello primario** - Ultimo modello Pro (preview)
- `gemini-2.0-flash` - Veloce, buono per la maggior parte dei casi
- `gemini-1.5-pro-latest` - Modello Pro stabile
- `gemini-1.5-flash-latest` - Flash veloce ed economico

### JSON Repair Automatico

File: `src/luna/ai/json_repair.py`

Ripara automaticamente JSON malformato:
- Trailing commas
- Missing commas
- Single quotes → double quotes
- Unquoted keys
- Newlines in strings
- Markdown code blocks
- Comments

---

## Avvio RunPod Giornaliero

**Problema:** Ogni riavvio devi reinstallare? **No!** I file sono già lì.

**Guida completa:** `docs/RUNPOD_DAILY_STARTUP.md`

### Avvio Rapido (se hai già installato)
```bash
# 1. Libera porta se occupata
pkill -f "python main.py" 2>/dev/null || true
sleep 3

# Se ancora occupata, uccidi tutti i processi Python
ps aux | grep python | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true
sleep 3

# 2. Avvia ComfyUI
cd /workspace/ComfyUI && python main.py --listen 0.0.0.0 --port 8188
```

### Script Automatico (salva una volta)
```bash
# Crea script di avvio
cat > /workspace/start_comfyui.sh << 'EOF'
#!/bin/bash
echo "Pulizia processi..."
pkill -f "python main.py" 2>/dev/null || true
sleep 2
ps aux | grep python | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true
sleep 2
echo "Avvio ComfyUI..."
cd /workspace/ComfyUI && python main.py --listen 0.0.0.0 --port 8188
EOF
chmod +x /workspace/start_comfyui.sh

# Usa sempre questo per avviare
/workspace/start_comfyui.sh
```

**Importante:** 
- Usa sempre **"Resume"** sul Pod esistente, non crearne uno nuovo
- I file in `/workspace/` persistono (nodi, modelli, pacchetti pip)
- **NON devi reinstallare requirements.txt ad ogni avvio!** (solo se crei Pod nuovo)

---

## Stato API LLM

⚠️ Richiede configurazione API keys in `.env`:
- `GEMINI_API_KEY=` (per generazione testo)
- `MOONSHOT_API_KEY=` (fallback)

---

## ✅ Random & Daily Events System - IMPLEMENTATO

**Data:** 2026-02-25

### File Creati/Modificati
- ✅ `src/luna/systems/dynamic_events.py` - Nuovo sistema (517 righe)
- ✅ `src/luna/systems/gameplay_manager.py` - Integrazione
- ✅ `src/luna/core/engine.py` - Flusso di gioco aggiornato
- ✅ `docs/WORLD_CREATION_GUIDE.md` - Documentazione completa

### Funzionalità
- **Random Events**: Eventi casuali basati su location/weight con scelte multiple
- **Daily Events**: Eventi orari (Morning/Afternoon/Evening/Night) con effetti automatici
- **Cooldown system**: Previene ripetizioni troppo frequenti
- **Stat checks**: D20 roll contro statistiche del player
- **Effetti**: Affinità, items, stats, flags

### Esempi nel World Preistorico
- 20 Random Events (bambini_giocano, trappola_cacciatori, mercante_conchiglie...)
- 15 Daily Events (sveglia_villaggio, preparazione_caccia, riposo_caldo...)

---

## Prossimi Step Consigliuti

1. ✅ Configurare API keys per LLM
2. ✅ Testare generazione video completa
3. ✅ Random & Daily Events System
4. ⬜ Aggiungere più hint NPC per fantasy/sci-fi worlds
5. ⬜ Ottimizzare traduzione IT→EN per SD prompts
6. ⬜ Testare con modelli video più lunghi (160 frame nativi)

---

*Ultimo aggiornamento: 2026-02-25*
