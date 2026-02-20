# Luna RPG v4 - Agent Guidelines

**Ultimo aggiornamento:** 2026-02-20 (Sessione completata)  
**Stato progetto:** MVP COMPLETO + Sistemi Avanzati  
**Versione:** 4.0.0-dev

### ✅ Sessione 2026-02-20 Completata:
- Time Manager (☀️🌅🌆🌙)
- Memory System V2 (keyword + semantic search)
- Outfit System V2 (componenti strutturati)
- Location System V2 (navigazione immersiva)
- Audio TTS (Google Cloud + gTTS)
- Content Guidelines (18+)
- World Creation Guide aggiornata
- Workflow JSON dalla v3 integrati

---

## 🎯 Panoramica Progetto

Luna RPG v4 è un **Visual Novel/RPG AI-driven** modulare dove ogni **mondo YAML** definisce completamente l'esperienza:
- Genere e stile narrativo
- Personaggi e relazioni
- Meccaniche di gameplay attive (combat, economia, affinità, etc.)
- Struttura narrativa (Story Beats)

**Filosofia chiave:** Python è il Game Master, l'AI è lo scrittore esecutivo.

---

## 📁 Struttura Progetto (Attuale)

```
luna-rpg-v4/
├── pyproject.toml              # Poetry config, dipendenze, tool settings
├── README.md                   # Setup e documentazione
├── PROJECT_ROADMAP.md          # Roadmap completa
├── AGENTS.md                   # Questo file - stato progetto
├── .env                        # Configurazione runtime (API keys, etc.)
├── .env.example                # Template .env
├── comfy_workflow_image.json   # ComfyUI workflow (copiato da v3)
├── comfy_workflow_video.json   # Wan2.1 I2V workflow (copiato da v3)
├── google_credentials.json     # Google Cloud TTS (opzionale)
│
├── src/luna/                   # Codice sorgente
│   ├── __init__.py
│   ├── __main__.py             # Entry point
│   │
│   ├── core/                   # Engine principale
│   │   ├── __init__.py
│   │   ├── models.py           # Pydantic models (30+ modelli)
│   │   ├── database.py         # SQLAlchemy 2.0 async
│   │   ├── state.py            # StateManager
│   │   ├── config.py           # Settings + UserPreferences
│   │   ├── story_director.py   # Story Beats controller
│   │   ├── prompt_builder.py   # System prompt builder
│   │   ├── engine.py           # GameEngine orchestrator
│   │   └── content_guidelines.py  # Content guidelines (18+)
│   │
│   ├── systems/                # Sistemi di gioco
│   │   ├── __init__.py
│   │   ├── world.py            # WorldLoader (YAML parsing)
│   │   ├── quests.py           # QuestEngine (state machine)
│   │   ├── personality.py      # PersonalityEngine
│   │   ├── location.py         # Location System V2
│   │   ├── memory.py           # Memory System V2
│   │   ├── time_manager.py     # Time Manager
│   │   └── gameplay/           # 9 Gameplay Systems modulari
│   │       ├── base.py
│   │       ├── __init__.py
│   │       ├── affinity.py
│   │       ├── combat.py
│   │       ├── inventory.py
│   │       ├── economy.py
│   │       ├── skills.py
│   │       ├── reputation.py
│   │       ├── clues.py
│   │       ├── survival.py
│   │       └── morality.py
│   │
│   ├── ai/                     # LLM Clients
│   │   ├── __init__.py
│   │   ├── base.py             # BaseLLMClient
│   │   ├── gemini.py           # Gemini provider (primario)
│   │   ├── moonshot.py         # Moonshot provider (fallback)
│   │   ├── mock.py             # Mock client per testing
│   │   ├── manager.py          # LLMManager con retry/fallback
│   │   ├── prompts.py          # Prompt builders
│   │   └── personality_analyzer.py  # LLM-based deep analysis
│   │
│   ├── media/                  # Media generation
│   │   ├── __init__.py
│   │   ├── pipeline.py         # MediaPipeline (async)
│   │   ├── builders.py         # ComfyUI prompt builders
│   │   ├── comfy_client.py     # ComfyUI API client
│   │   ├── video_client.py     # Wan2.1 I2V client
│   │   ├── audio_client.py     # TTS (Google Cloud + gTTS)
│   │   └── outfit.py           # Outfit System V2
│   │
│   └── ui/                     # PySide6 interface
│       ├── __init__.py
│       ├── app.py              # LunaApplication controller
│       ├── startup_dialog.py   # StartupDialog (3 tabs)
│       ├── main_window.py      # MainWindow (3 pannelli)
│       ├── widgets.py          # Widgets custom
│       └── image_viewer.py     # ImageViewer con zoom/pan
│
├── tests/                      # Test suite (placeholder)
│   ├── __init__.py
│   ├── unit/
│   └── integration/
│
├── worlds/                     # Content YAML
│   ├── templates/
│   ├── school_life/            # Esempio world v1
│   ├── school_life_v2/         # Esempio world v2 (modular)
│   └── legacy/
│
├── storage/                    # Runtime data
│   ├── saves/                  # Database SQLite
│   ├── images/                 # Immagini generate
│   ├── videos/                 # Video generati
│   ├── logs/                   # Log sessioni
│   └── config/                 # User preferences
│
└── docs/
    └── WORLD_CREATION_GUIDE.md # Guida completa YAML
```

---

## ✅ Fasi Completate

### Fase 0: Project Setup ✅
- `pyproject.toml` con Poetry, Ruff, MyPy, Pytest
- Struttura cartelle completa
- `README.md`, `.env.example`
- Entry point `__main__.py`

### Fase 1: Core Data Layer ✅
- **25+ Pydantic Models** in `core/models.py`
- **SQLAlchemy 2.0 Database** (`core/database.py`): 4 tabelle, async
- **StateManager** (`core/state.py`): Load/save, manipolazione stato

### Fase 2: Configuration System ✅
- **Pydantic Settings** (`core/config.py`): Env vars, multi-provider LLM
- **UserPreferences**: Persistenza JSON

### Fase 3: World System ✅
- **WorldLoader** (`systems/world.py`): Legacy + modulare
- **9 Gameplay Systems** (`systems/gameplay/`)

### Fase 3b: Story Beats System ✅
- **StoryDirector** (`core/story_director.py`): Controllo narrativa Python

### Fase 4: AI Layer ✅
- **GeminiClient** (primario), **MoonshotClient** (fallback)
- **LLMManager**: Retry, fallback automatico
- **PersonalityAnalyzer**: Deep analysis LLM-based

### Fase 5: Quest Engine ✅
- **QuestEngine** (`systems/quests.py`): State machine completa
- **ConditionEvaluator**: Rule engine esplicito
- **ActionExecutor**: Azioni quest

### Fase 6: Personality Engine ✅
- **PersonalityEngine** (`systems/personality.py`): 8 behavior types
- **Impression tracking**: 5 dimensioni (-100/+100)
- **Dual-mode**: Regex + LLM analysis

### Fase 7: Game Engine ✅
- **GameEngine** (`core/engine.py`): 10-step orchestration
- **PromptBuilder**: Classe separata
- Integrazione completa tutti i sistemi

### Fase 8: Media Generation ✅
- **ComfyUIClient**: API reali, LoRA stacking
- **VideoClient**: Wan2.1 I2V con temporal prompt
- **BASE_PROMPTS**: Identici alla v3
- **Anti-fusion**: Enhanced per multi-character

### Fase 9: UI ✅
- **StartupDialog**: 3 tab (New Game, Load Game, Settings)
- **MainWindow**: 3 pannelli (status, image, story)
- **ImageViewer**: Zoom/pan interattivo
- **Dark theme**: Global stylesheet

---

## 🎬 Story Beats System (Pattern Chiave)

**Concetto:** Python controlla la narrazione, AI esegue.

```yaml
story_beats:
  premise: "Storia di primo amore in un liceo"
  themes: ["amore", "scoperta_di_sé"]
  hard_limits:
    - "NESSUN personaggio può morire"
    - "NO magia"
  
  beats:
    - id: "incontro"
      description: "Elena lascia cadere i libri"
      trigger: "turn <= 5 AND location == 'Biblioteca'"
      required_elements: ["elena", "libri", "aiuto"]
      tone: "awkward_cute"
      consequence: "elena_affinity += 5"
```

---

## 🎮 Gameplay Systems (Pattern)

```python
class GameplaySystem(ABC):
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.is_active = True
    
    @property
    @abstractmethod
    def name(self) -> str: ...
```

**9 Sistemi:** affinity, combat, inventory, economy, skills, reputation, clues, survival, morality

---

## 🖼️ Image Viewer (Zoom/Pan)

**Controlli:**
- **Rotellina**: Zoom in/out
- **Click + drag**: Pan
- **Doppio click**: Fit to window
- **Tasti**: +/- (zoom), 0 (reset), F (fit)

---

## 🗄️ Database Pattern

```python
async with db_manager.session() as db:
    session = await db_manager.create_session(db, world_id, companion, affinity)
    await db_manager.add_message(db, session_id, "user", text, turn)
```

---

## 📝 Convenzioni Codice

- **Type hints**: Obbligatori su funzioni pubbliche
- **Async**: SEMPRE per I/O (DB, HTTP, file)
- **Error handling**: Custom exceptions, mai silenziare critici
- **Stile**: Google docstrings, snake_case, PascalCase classi

---

## 📋 Todo List - Stato Attuale

### ✅ Completato
- [x] Fasi 0-9: Tutte le fasi core completate
- [x] 25+ modelli Pydantic
- [x] 9 Gameplay Systems
- [x] AI Layer con fallback
- [x] Quest + Personality Engine
- [x] Game Engine orchestrator
- [x] Media generation (ComfyUI + Wan2.1)
- [x] UI completa (PySide6)

### ✅ Completati (Aggiunte Post-MVP)
- [x] **Time Manager**: Ciclo giorno/notte manuale (☀️🌅🌆🌙)
- [x] **Memory System V2**: Keyword + semantic search (opzionale)
- [x] **Outfit System V2**: Outfit strutturato con coerenza visiva
  - OutfitState con componenti (top, bottom, shoes, etc)
  - OutfitPromptMapper per SD positive/negative
  - UI widget per visualizzazione
  - LLM può modificare componenti specifici
- [x] **Location System V2**: Navigazione immersiva
  - Gerarchia location (parent/child)
  - Stati dinamici (crowded, empty, locked, damaged)
  - Discovery location nascoste
  - Companion può rifiutare di seguire
  - Transizioni narrative
  - Visibilità limitata (solo location raggiungibili)
  - Comandi naturali ("vado nei bagni")
- [x] **Audio TTS**: Sintesi vocale integrata
  - Google Cloud TTS (primario) o gTTS (fallback)
  - Supporto italiano (it-IT)
  - Riproduzione con pygame
  - Toggle on/off nella UI
- [x] **Content Guidelines (18+)**: Linee guida contenuti
  - File `content_guidelines.py` per tono adult
  - Tutti i personaggi sono adulti consenzienti (18+)
  - Scene romantiche/intime gestite con tatto
  - Integrato automaticamente nel system prompt
- [x] **Workflow Files**: Copiati dalla v3
  - `comfy_workflow_image.json` → Image generation (cyberrealisticPony)
  - `comfy_workflow_video.json` → Wan2.1 I2V video generation
  - Configurati per RunPod ComfyUI

### 🔄 Da Fare (Fase 10 - Testing & Polish)
- [ ] **Unit tests** (>80% coverage)
- [ ] **Integration tests** (ComfyUI, TTS, Database)
- [ ] **E2E tests** (flusso completo gioco)
- [ ] **Performance profiling** (memory, CPU)
- [ ] **Documentation** completa

### 🎯 Priorità Sessione Successiva
- [ ] **Verifica Audio TTS** integrazione completa con MediaPipeline
- [ ] **Verifica ComfyUI RunPod** workflow esecuzione
- [ ] **Verifica Video Generation** workflow Wan2.1
- [ ] **Test end-to-end** del flusso gioco completo

---

## 🔧 Comandi Utili

```bash
# Setup
poetry install

# Run
poetry run luna
# oppure
python -m luna

# Linting
ruff check .
ruff format .

# Type checking
mypy src/luna

# Testing
pytest
pytest --cov=luna
```

---

## 🌩️ RunPod ComfyUI Requirements

I seguenti file/modello devono essere presenti sul tuo Pod ComfyUI:

### Image Generation (`comfy_workflow_image.json`)
- **Checkpoint**: `cyberrealisticPony_v7.safetensors`
- **LoRAs**:
  - `stsDebbie-10e.safetensors` (character consistency)
  - `Expressive_H-000010.safetensors` (expressions)
  - `FantasyWorldPonyV2.safetensors` (style)

### Video Generation (`comfy_workflow_video.json`)
- **Model**: `Wan2.1_I2V_fp8_Civitai.gguf`
- **VAE**: `wan_2.1_vae.safetensors`
- **Text Encoder**: `umt5_xxl_fp8_e4m3fn.safetensors`

### Configurazione Environment
```bash
# .env
COMFYUI_URL=https://your-pod-id-8080.proxy.runpod.net
GOOGLE_CREDENTIALS=google_credentials.json  # Per TTS
```

---

## 💡 Pattern Importanti

1. **Python è Source of Truth**: L'LLM suggerisce, Python valida e applica
2. **Modularità**: Ogni sistema può essere abilitato/disabilitato da YAML
3. **Story Beats**: Struttura narrativa controllata da Python
4. **Type Safety**: Pydantic models + mypy strict
5. **Async Everywhere**: Per I/O operations

---

**🎯 Prossimo step:** Verifica integrazione Audio/ComfyUI + Testing completo

**✅ Stato:** Sistemi avanzati implementati, pronto per verifica e2e
