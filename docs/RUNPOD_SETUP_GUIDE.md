# Guida Setup RunPod - ComfyUI per Luna RPG v4

## Prerequisiti
- RunPod con GPU A5000 (o superiore)
- Template PyTorch o ComfyUI pre-installato
- ~25GB VRAM per Wan2.1

---

## Installazione Nodi Custom

### 1. Frame Interpolation (RIFE)
```bash
cd /workspace/ComfyUI/custom_nodes
git clone https://github.com/Fannovel16/ComfyUI-Frame-Interpolation.git
cd ComfyUI-Frame-Interpolation
python install.py
```

### 2. KJNodes
```bash
cd /workspace/ComfyUI/custom_nodes
git clone https://github.com/kijai/ComfyUI-KJNodes.git
cd ComfyUI-KJNodes
pip install -r requirements.txt
```

### 3. WanVideoWrapper
```bash
cd /workspace/ComfyUI/custom_nodes
git clone https://github.com/kijai/ComfyUI-WanVideoWrapper.git
cd ComfyUI-WanVideoWrapper
pip install -r requirements.txt
```

### 4. VideoHelperSuite
```bash
cd /workspace/ComfyUI/custom_nodes
git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git
cd ComfyUI-VideoHelperSuite
pip install -r requirements.txt
```

### 5. GGUF Loader
```bash
cd /workspace/ComfyUI/custom_nodes
git clone https://github.com/city96/ComfyUI-GGUF.git
cd ComfyUI-GGUF
pip install -r requirements.txt
```

---

## Download Modelli

### Modelli Obbligatori

```bash
# Crea directories
mkdir -p /workspace/ComfyUI/models/unet
mkdir -p /workspace/ComfyUI/models/vae
mkdir -p /workspace/ComfyUI/models/clip
mkdir -p /workspace/ComfyUI/models/clip_vision
mkdir -p /workspace/ComfyUI/models/loras
mkdir -p /workspace/ComfyUI/custom_nodes/ComfyUI-Frame-Interpolation/ckpts/rife
```

#### 1. Wan2.1 I2V (Unet)
```bash
wget -O /workspace/ComfyUI/models/unet/Wan2.1_I2V_fp8_Civitai.gguf \
  "https://huggingface.co/city96/Wan2.1-I2V-14B-480P-gguf/resolve/main/Wan2.1_I2V_fp8_Civitai.gguf"
```

#### 2. VAE
```bash
wget -O /workspace/ComfyUI/models/vae/wan_2.1_vae.safetensors \
  "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors"
```

#### 3. CLIP
```bash
wget -O /workspace/ComfyUI/models/clip/umt5_xxl_fp8_e4m3fn_scaled.safetensors \
  "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"
```

#### 4. CLIP Vision
```bash
wget -O /workspace/ComfyUI/models/clip_vision/clip_vision_h.safetensors \
  "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors" \
  -O clip_vision_h.safetensors
```

#### 5. LoRAs (opzionali ma consigliati)
```bash
# HIGH LoRA
wget -O /workspace/ComfyUI/models/loras/Wan_2_2_I2V_A14B_HIGH_lightx2v_MoE_distill_lora_rank_64_bf16.safetensors \
  "URL_DA_TROVARE"

# LOW LoRA
wget -O /workspace/ComfyUI/models/loras/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors \
  "URL_DA_TROVARE"
```

#### 6. RIFE Model
```bash
wget -O /workspace/ComfyUI/custom_nodes/ComfyUI-Frame-Interpolation/ckpts/rife/rife47.pth \
  "https://github.com/hzwer/Practical-RIFE/releases/download/v4.7/rife47.pth"
```

---

## Avvio ComfyUI

```bash
cd /workspace/ComfyUI
python main.py --listen 0.0.0.0 --port 8188
```

---

## Troubleshooting

### Errore: "Node 'RIFE VFI' not found"
**Soluzione**: Verifica installazione ComfyUI-Frame-Interpolation
```bash
cd /workspace/ComfyUI/custom_nodes/ComfyUI-Frame-Interpolation
python install.py
```

### Errore: "rife47.pth not found"
**Soluzione**: Verifica path modello
```bash
ls -la /workspace/ComfyUI/custom_nodes/ComfyUI-Frame-Interpolation/ckpts/rife/
```

### Errore: "missing_node_type Color Fix"
**Soluzione**: Aggiorna KJNodes o rimuovi nodo ColorCorrection dal workflow
```bash
cd /workspace/ComfyUI/custom_nodes/ComfyUI-KJNodes
git pull
pip install -r requirements.txt
```

### Errore: "required_input_missing" su RIFE
**Soluzione**: Aggiungi parametro `clear_cache_after_n_frames` al workflow JSON

### Porta occupata
**Soluzione**:
```bash
pkill -f "python main.py"
sleep 2
cd /workspace/ComfyUI && python main.py --listen 0.0.0.0 --port 8188
```

---

## Verifica Installazione

Apri ComfyUI nel browser (porta 8188) e cerca i nodi:
- ✅ `RIFE VFI` in ComfyUI-Frame-Interpolation/VFI
- ✅ `ImageResizeKJv2` in KJNodes
- ✅ `WanImageToVideo` in WanVideoWrapper
- ✅ `VHS_VideoCombine` in VideoHelperSuite
- ✅ `UnetLoaderGGUF` in GGUF

---

## Configurazione Luna (PC Windows)

File `.env`:
```env
COMFY_URL=https://TUO-POD.runpod.net
GEMINI_API_KEY=la_tua_chiave
MOONSHOT_API_KEY=la_tua_chiave
```

Avvio:
```powershell
python -m luna
```

---

*Guida aggiornata: 2026-02-23*
