# Luna RPG v4

Visual Novel/RPG AI-driven con Quest System, Personality Engine e generazione immagini in tempo reale.

## 🎮 Caratteristiche

- **AI Multi-Provider**: Moonshot, Gemini, OpenAI, Ollama (locale)
- **Quest System**: State machine modulare definita in YAML
- **Personality Engine**: Tracciamento dinamico comportamento e relazioni
- **Living World**: NPC con schedule, tempo che scorre, eventi globali
- **Generazione Media**: Immagini (ComfyUI/SD), Video (Wan2.1), Audio (TTS)
- **UI Moderna**: PySide6 con tema dark, widgets dinamici

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

# Percorsi locali
LOCAL_SD_URL=http://127.0.0.1:7860
LOCAL_COMFY_URL=http://127.0.0.1:8188

# Database
DATABASE_URL=sqlite+aiosqlite:///storage/saves/luna_v4.db

# Google TTS (opzionale)
GOOGLE_CREDENTIALS_PATH=google_credentials.json
```

### Provider LLM Supportati

| Provider | Locale/Cloud | Note |
|----------|-------------|------|
| **Gemini** | Cloud | Google AI, buon fallback |
| **Moonshot** | Cloud | Primario raccomandato |
| **OpenAI** | Cloud | GPT-4, GPT-3.5 |
| **Ollama** | Locale | Richiede Ollama installato |

Per usare **Ollama**:
1. Installa [Ollama](https://ollama.ai/)
2. Scarica un modello: `ollama pull llama3`
3. Imposta `LLM_PROVIDER=ollama`

## 🖥️ Modalità di Esecuzione

### Locale (SD WebUI)
- Generazione immagini via Stable Diffusion WebUI
- Video non disponibile
- Ideale per testing e sviluppo

### RunPod (ComfyUI)
- Generazione immagini via ComfyUI
- Video Wan2.1 I2V disponibile
- Richiede account RunPod con GPU

## 🧪 Testing

```bash
# Tutti i test
pytest

# Solo unit tests
pytest tests/unit

# Solo test veloci (esclude slow)
pytest -m "not slow"

# Con coverage
pytest --cov=luna --cov-report=html
```

## 📁 Struttura Progetto

```
luna-rpg-v4/
├── src/luna/              # Codice sorgente
│   ├── core/              # Engine, database, modelli
│   ├── systems/           # Quest, personality, time
│   ├── ai/                # LLM clients
│   ├── media/             # Image/video/audio generation
│   └── ui/                # PySide6 interface
├── tests/                 # Test suite
├── worlds/                # Content YAML
├── storage/               # Dati runtime (DB, immagini, logs)
└── docs/                  # Documentazione
```

## 🎨 Creazione Contenuti

Vedi `docs/CONTENT_CREATION.md` per guida alla creazione di:
- Mondi di gioco
- Personaggi (companion)
- Quest e storyline
- Dialoghi dinamici

## 🤝 Contributing

1. Fork il repository
2. Crea un branch: `git checkout -b feature/nome-feature`
3. Committa i cambi: `git commit -am 'Aggiunge feature'`
4. Pusha: `git push origin feature/nome-feature`
5. Apri una Pull Request

## 📝 Note

- **Python 3.12+** richiesto per feature async moderne
- **Type hints** obbligatori su codice nuovo
- **Ruff** per linting/formatting: `ruff check . && ruff format .`
- **Mypy** per type checking: `mypy src/luna`

## 📜 License

MIT License - vedi LICENSE file

## 🙏 Crediti

Basato su Luna RPG v3, con migliorie architetturali e nuove features.
