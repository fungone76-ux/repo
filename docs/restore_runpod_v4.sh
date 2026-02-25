#!/bin/bash
# =============================================================================
# SCRIPT RIPRISTINO RUNPOD - LUNA RPG v4
# =============================================================================
# Setup completo: Stable Diffusion (Immagini) + ComfyUI Wan 2.1 (Video)
# 
# ISTruzioni:
# 1. Su RunPod, crea una nuova istanza PyTorch (CUDA 12.1+)
# 2. Upload questo file in /workspace/
# 3. chmod +x restore_runpod_v4.sh && ./restore_runpod_v4.sh
# =============================================================================

set -e  # Exit on error

echo "🚀 INIZIO RIPRISTINO LUNA RPG v4"
echo "=================================="

# =============================================================================
# PARTE 1: RIPRISTINO STABLE DIFFUSION WEBUI (Immagini)
# =============================================================================
echo ""
echo "📦 [1/6] Ripristino Stable Diffusion WebUI..."

if [ ! -d "/workspace/stable-diffusion-webui" ]; then
    echo "⬇️ Clonando SD WebUI..."
    cd /workspace
    git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui.git
fi

cd /workspace/stable-diffusion-webui

# Creazione venv principale (se non esiste)
if [ ! -d "venv" ]; then
    echo "🐍 Creazione venv SD WebUI..."
    python -m venv venv
    ./venv/bin/pip install --upgrade pip
fi

# Download modelli principali
echo "⬇️ Download modelli checkpoint..."
mkdir -p models/Stable-diffusion
mkdir -p models/Lora

# === MODELLO PRINCIPALE (Luna RPG v4) ===
echo "⬇️ Download modello principale..."
if [ ! -f "models/Stable-diffusion/luna_main_model.safetensors" ]; then
    wget -O models/Stable-diffusion/luna_main_model.safetensors \
        "https://civitai.com/api/download/models/1177183?type=Model&format=SafeTensor&size=pruned&fp=fp16"
fi

# Download LoRA (sostituisci con i tuoi link reali)
echo "⬇️ Download LoRA..."

# LoRA stsDebbie (se hai il link)
# wget -O models/Lora/stsDebbie-10e.safetensors "LINK_CIVITAI_DEBBIE"

# LoRA stsSmith (se hai il link)
# wget -O models/Lora/stsSmith-10e.safetensors "LINK_CIVITAI_SMITH"

# LoRA Fantasy World Pony
# wget -O models/Lora/FantasyWorldPonyV2.safetensors "LINK_CIVITAI_FANTASY"

# LoRA Expressive
# wget -O models/Lora/Expressive_H-000001.safetensors "LINK_CIVITAI_EXPRESSIVE"

echo "✅ SD WebUI pronto"

# =============================================================================
# PARTE 2: INSTALLAZIONE COMFYUI + WAN 2.1 (Video)
# =============================================================================
echo ""
echo "🎬 [2/6] Installazione ComfyUI..."

cd /workspace

if [ ! -d "ComfyUI" ]; then
    echo "⬇️ Clonando ComfyUI..."
    git clone https://github.com/comfyanonymous/ComfyUI.git
fi

cd ComfyUI

# Creazione VENV isolato per ComfyUI
echo "🛡️ Creazione venv isolato per ComfyUI..."
if [ ! -d "venv_comfy" ]; then
    python -m venv venv_comfy
    ./venv_comfy/bin/pip install --upgrade pip
    ./venv_comfy/bin/pip install torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0 --index-url https://download.pytorch.org/whl/cu121
    ./venv_comfy/bin/pip install -r requirements.txt
fi

# Installazione pacchetti aggiuntivi per Wan 2.1
echo "⬇️ Installazione dipendenze Wan 2.1..."
./venv_comfy/bin/pip install requests websocket-client accelerate imageio-ffmpeg opencv-python-headless gguf GitPython rich diffusers huggingface_hub toml ftfy

# SageAttention (opzionale, per performance)
echo "⚡ Installazione SageAttention (opzionale)..."
./venv_comfy/bin/pip install sageattention || echo "SageAttention non installato (non critico)"

# =============================================================================
# PARTE 3: DOWNLOAD MODELLI WAN 2.1
# =============================================================================
echo ""
echo "🎬 [3/6] Download modelli Wan 2.1 (GGUF)..."

mkdir -p models/unet models/vae models/clip_vision models/text_encoders

# Modello principale Wan 2.1 I2V (GGUF Q4 - bilanciato qualità/velocità)
echo "⬇️ Download Wan 2.1 I2V GGUF..."
if [ ! -f "models/unet/wan2.1_i2v_480p_q4.gguf" ]; then
    wget -O models/unet/wan2.1_i2v_480p_q4.gguf \
        "https://huggingface.co/City96/Wan2.1-I2V-GGUF/resolve/main/Wan2.1-I2V-14B-480P-Q4_K_M.gguf"
fi

# VAE
echo "⬇️ Download VAE..."
if [ ! -f "models/vae/wan_2.1_vae.safetensors" ]; then
    wget -O models/vae/wan_2.1_vafes.safetensors \
        "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors"
fi

# CLIP Vision
echo "⬇️ Download CLIP Vision..."
if [ ! -f "models/clip_vision/clip_vision_h.safetensors" ]; then
    wget -O models/clip_vision/clip_vision_h.safetensors \
        "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors"
fi

# Text Encoder (UMT5 XXL)
echo "⬇️ Download Text Encoder..."
if [ ! -f "models/text_encoders/umt5_xxl_fp8.safetensors" ]; then
    wget -O models/text_encoders/umt5_xxl_fp8.safetensors \
        "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"
fi

# =============================================================================
# PARTE 4: INSTALLAZIONE NODI CUSTOM
# =============================================================================
echo ""
echo "🧩 [4/6] Installazione nodi custom ComfyUI..."

cd custom_nodes

# GGUF support
if [ ! -d "ComfyUI-GGUF" ]; then
    echo "⬇️ Nodo GGUF..."
    git clone https://github.com/city96/ComfyUI-GGUF
    cd ComfyUI-GGUF
    /workspace/ComfyUI/venv_comfy/bin/pip install -r requirements.txt
    cd ..
fi

# Video Helper Suite
if [ ! -d "ComfyUI-VideoHelperSuite" ]; then
    echo "⬇️ Video Helper Suite..."
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite
    cd ComfyUI-VideoHelperSuite
    /workspace/ComfyUI/venv_comfy/bin/pip install -r requirements.txt
    cd ..
fi

# ComfyUI Manager (opzionale ma consigliato)
if [ ! -d "ComfyUI-Manager" ]; then
    echo "⬇️ ComfyUI Manager..."
    git clone https://github.com/ltdrdata/ComfyUI-Manager
fi

# Wan Video Wrapper (se serve)
if [ ! -d "ComfyUI-WanVideoWrapper" ]; then
    echo "⬇️ Wan Video Wrapper..."
    git clone https://github.com/Kijai/ComfyUI-WanVideoWrapper
fi

cd ..

# =============================================================================
# PARTE 5: SETUP PROGETTO LUNA RPG v4
# =============================================================================
echo ""
echo "🎮 [5/6] Setup progetto Luna RPG v4..."

cd /workspace

if [ ! -d "luna-rpg-v4" ]; then
    echo "📁 Creazione directory progetto..."
    mkdir -p luna-rpg-v4
fi

cd luna-rpg-v4

# Directory per output
mkdir -p storage/generated/images
mkdir -p storage/generated/videos
mkdir -p storage/generated/audio
mkdir -p storage/temp
mkdir -p storage/cache
mkdir -p logs

echo "✅ Directory progetto create"

# =============================================================================
# PARTE 6: CONFIGURAZIONE FINALE
# =============================================================================
echo ""
echo "⚙️  [6/6] Configurazione finale..."

# Script di avvio SD WebUI
cat > /workspace/start_sd.sh << 'EOF'
#!/bin/bash
cd /workspace/stable-diffusion-webui
source venv/bin/activate
python launch.py --listen --port 7860 --xformers --enable-insecure-extension-access --api --medvram
EOF
chmod +x /workspace/start_sd.sh

# Script di avvio ComfyUI
cat > /workspace/start_comfy.sh << 'EOF'
#!/bin/bash
cd /workspace/ComfyUI
source venv_comfy/bin/activate
python main.py --listen --port 8188
EOF
chmod +x /workspace/start_comfy.sh

# Script di avvio entrambi
cat > /workspace/start_all.sh << 'EOF'
#!/bin/bash
echo "🚀 Avvio SD WebUI (Porta 7860) e ComfyUI (Porta 8188)..."
echo "Attendi 30-60 secondi per il caricamento..."
nohup /workspace/start_sd.sh > /workspace/sd.log 2>&1 &
nohup /workspace/start_comfy.sh > /workspace/comfy.log 2>&1 &
echo "✅ Servizi avviati!"
echo "📷 SD WebUI: https://$(hostname -I | awk '{print $1}'):7860"
echo "🎬 ComfyUI: https://$(hostname -I | awk '{print $1}'):8188"
EOF
chmod +x /workspace/start_all.sh

# =============================================================================
# RIEPILOGO
# =============================================================================
echo ""
echo "=================================="
echo "✅ RIPRISTINO COMPLETATO!"
echo "=================================="
echo ""
echo "📁 Percorsi importanti:"
echo "   SD WebUI:     /workspace/stable-diffusion-webui"
echo "   ComfyUI:      /workspace/ComfyUI"
echo "   Progetto:     /workspace/luna-rpg-v4"
echo ""
echo "🚀 Comandi di avvio:"
echo "   Avvio SD:     /workspace/start_sd.sh"
echo "   Avvio Comfy:  /workspace/start_comfy.sh"
echo "   Avvio entrambi: /workspace/start_all.sh"
echo ""
echo "🌐 Porte:"
echo "   SD WebUI:     7860"
echo "   ComfyUI:      8188"
echo ""
echo "⚠️  IMPORTANTE:"
echo "   1. Modifica lo script per aggiungere i link Civitai dei tuoi modelli"
echo "   2. Su RunPod, configura i Proxy per le porte 7860 e 8188"
echo "   3. La prima installazione richiede ~20-30 minuti"
echo ""
