# Luna RPG v4

Visual Novel/RPG AI-driven con Quest System, Personality Engine e generazione immagini in tempo reale.

## 🎮 Caratteristiche

- **AI Multi-Provider**: Moonshot, Gemini, OpenAI, Ollama (locale)
- **Quest System**: State machine modulare definita in YAML
- **Personality Engine**: Tracciamento dinamico comportamento e relazioni
  - 5 dimensioni: Trust, Attraction, Fear, Curiosity, Power Balance
  - Archetipi player: The Romantic, The Dominant, etc.
  - UI con barre di progresso in tempo reale
- **Living World**: NPC con schedule, tempo che scorre, eventi globali
- **Save/Load Completo**: Persistenza di game state, personality, quest, eventi
- **Solo Mode**: Quando ti muovi, il companion rimane indietro e vedi la location vuota
- **Movement System**: Navigazione con verbi italiani ("vado in bagno", "esco")
- **Generazione Media**: 
  - Immagini: SD WebUI (local) o ComfyUI (RunPod)
  - Video: Wan2.1 I2V con temporal prompt (LLM-powered)
  - Audio: TTS (Google Cloud + gTTS fallback)
- **UI Moderna**: PySide6 con tema dark, widgets dinamici, notifiche toast
- **Chat Stile Visual Novel**: Conversazione colorata (utente=verde, NPC=rosa)
- **Auto-switch Companion**: Cambia personaggio menzionandolo nel testo

## 🚀 Setup

### Prerequisiti

- Python 3.12+
- Poetry (gestione dipendenze)
- (Opzionale) GPU per generazione immagini locali
- (Opzionale) Account RunPod per generazione cloud

### Installazione

1. **Clona il repository:**
```bash
cd D:\
git clone <repo-url> luna-rpg-v4
cd luna-rpg-v4
```

2. **Installa Poetry** (se non presente):
```powershell
# Windows (PowerShell)
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -

# Aggiungi Poetry al PATH se necessario
$env:Path += ";$env:APPDATA\Python\Scripts"
```

3. **Configura l'ambiente:**
```bash
# Crea file .env dalla copia di esempio
copy .env.example .env

# Edita .env con le tue API keys
notepad .env
```

4. **Installa le dipendenze:**
```bash
poetry install
```

5. **Attiva l'ambiente virtuale:**
```bash
poetry shell
```

## 🏃 Avvio

```bash
# Modalità sviluppo
python -m luna

# O tramite script Poetry
poetry run luna
```

## ⚙️ Configurazione

### File `.env`

Copia `.env.example` in `.env` e configura:

```bash
# LLM Provider (gemini, moonshot, openai)
LLM_PROVIDER=gemini

# API Keys (almeno una richiesta)
GEMINI_API_KEY=your_key_here
MOONSHOT_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Modalità esecuzione (LOCAL, RUNPOD)
EXECUTION_MODE=LOCAL

# RunPod (solo se EXECUTION_MODE=RUNPOD)
RUNPOD_ID=your_pod_id
RUNPOD_API_KEY=your_runpod_key
```

### Modalità Esecuzione

Nel dialogo di avvio (o in `.env`):

- **LOCAL**: Usa Stable Diffusion WebUI locale (richiede GPU)
- **RUNPOD**: Usa ComfyUI su RunPod (cloud, più veloce)

## 🗂️ Struttura Progetto

```
luna-rpg-v4/
├── src/luna/
│   ├── core/           # GameEngine, StateManager, Database
│   ├── systems/        # Quests, Personality, Memory, Movement
│   ├── media/          # Image/video/audio generation
│   └── ui/             # PySide6 interface
├── worlds/             # World definitions (YAML)
├── docs/               # Documentation
└── storage/            # Generated images, audio
```

## 📚 Documentazione

Vedi cartella `docs/`:
- `AGENTS.md` - Stato progetto e novità
- `CHANGELOG.md` - Cronologia modifiche
- `COMPLETE_TECHNICAL_SPECIFICATION.md` - Architettura completa

## 🆕 Novità V4 (Marzo 2026)

- **Movement System**: Navigazione con verbi italiani
- **Solo Mode**: Location vuote quando sei da solo
- **StateMemoryManager**: Unificazione stato + memoria
- **IntroGenerator**: Refactor scena iniziale
- **NPC Expansion**: 23 personaggi secondari
- **NPC Templates**: Personaggi secondari con aspetto consistente (capelli rossi, occhiali, etc.)

## 📝 License

Progetto privato - Tutti i diritti riservati.
