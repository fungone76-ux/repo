# Luna RPG v4 - Project Roadmap

**Data inizio:** 2026-02-20  
**Stato:** Fasi 0-9 COMPLETATE - MVP Funzionante  
**Versione target:** 4.0.0

---

## 📋 Panoramica

Luna RPG v4 è un Visual Novel/RPG AI-driven che eredita e migliora l'architettura di Luna RPG v3. Obiettivo: codice più pulito, testabile, estensibile e gameplay più profondo.

---

## 🗂️ Struttura Progetto (Aggiornata)

```
luna-rpg-v4/
├── pyproject.toml              # Poetry config, dipendenze, tool settings
├── README.md                   # Setup e documentazione utente
├── PROJECT_ROADMAP.md          # Questo file - memoria progetto
├── AGENTS.md                   # Stato progetto per agenti
├── .env.example                # Template variabili ambiente
├── .gitignore                  # Esclusioni git
│
├── src/luna/                   # Package principale
│   ├── __init__.py
│   ├── __main__.py             # Entry point: python -m luna
│   │
│   ├── core/                   # Core engine
│   │   ├── __init__.py
│   │   ├── models.py           # Pydantic models (25+)
│   │   ├── database.py         # SQLAlchemy 2.0 async
│   │   ├── state.py            # StateManager
│   │   ├── config.py           # Settings + UserPreferences
│   │   ├── story_director.py   # Story Beats controller
│   │   ├── prompt_builder.py   # System prompt builder
│   │   └── engine.py           # GameEngine orchestrator
│   │
│   ├── systems/                # Game systems
│   │   ├── __init__.py
│   │   ├── world.py            # WorldLoader
│   │   ├── quests.py           # QuestEngine
│   │   ├── personality.py      # PersonalityEngine
│   │   └── gameplay/           # 9 Gameplay Systems
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
│   ├── ai/                     # AI/LLM clients
│   │   ├── __init__.py
│   │   ├── base.py             # Abstract LLM client
│   │   ├── gemini.py           # Gemini provider (primario)
│   │   ├── moonshot.py         # Moonshot provider (fallback)
│   │   ├── mock.py             # Mock client
│   │   ├── manager.py          # LLMManager
│   │   ├── prompts.py          # Prompt builders
│   │   └── personality_analyzer.py
│   │
│   ├── media/                  # Media generation
│   │   ├── __init__.py
│   │   ├── pipeline.py         # MediaPipeline
│   │   ├── builders.py         # ComfyUI prompt builders
│   │   ├── comfy_client.py     # ComfyUI client
│   │   └── video_client.py     # Wan2.1 video client
│   │
│   └── ui/                     # PySide6 interface
│       ├── __init__.py
│       ├── app.py              # LunaApplication
│       ├── startup_dialog.py   # StartupDialog
│       ├── main_window.py      # MainWindow
│       ├── widgets.py          # Widgets custom
│       └── image_viewer.py     # ImageViewer zoom/pan
│
├── tests/                      # Test suite
│   ├── __init__.py
│   ├── unit/
│   └── integration/
│
├── worlds/                     # Content YAML
│   ├── templates/
│   ├── school_life/
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
    └── WORLD_CREATION_GUIDE.md # Guida creazione mondi
```

---

## ✅ Fasi Completate

### Fase 0: Project Setup ✅ COMPLETATA
- [x] `pyproject.toml` con Poetry, Ruff, MyPy, Pytest
- [x] Struttura cartelle completa
- [x] `README.md`, `.env.example`
- [x] Entry point `__main__.py`

**Data:** 2026-02-20

---

### Fase 1: Core Data Layer ✅ COMPLETATA
- [x] 25+ Pydantic Models in `core/models.py`
- [x] SQLAlchemy 2.0 Database (`core/database.py`)
- [x] StateManager completo (`core/state.py`)

**Data:** 2026-02-20

---

### Fase 2: Configuration System ✅ COMPLETATA
- [x] Pydantic Settings (`core/config.py`)
- [x] UserPreferences persistenza JSON
- [x] Multi-provider LLM config

**Data:** 2026-02-20

---

### Fase 3: World System + Gameplay Systems ✅ COMPLETATA
- [x] WorldLoader con modular + legacy support
- [x] 9 Gameplay Systems modulari
- [x] Documentazione YAML

**Data:** 2026-02-20

---

### Fase 3b: Story Beats System ✅ COMPLETATA
- [x] StoryBeat, NarrativeArc, BeatExecution models
- [x] StoryDirector con trigger evaluation
- [x] Integrazione World Loader

**Data:** 2026-02-20

---

### Fase 4: AI Layer ✅ COMPLETATA
- [x] BaseLLMClient astratto
- [x] GeminiClient (primario) - safety settings, JSON mode
- [x] MoonshotClient (fallback) - OpenAI-compatible
- [x] MockLLMClient per testing
- [x] LLMManager con retry/fallback automatico
- [x] Prompt builders + JSON schema

**Data:** 2026-02-20

---

### Fase 5: Quest Engine ✅ COMPLETATA
- [x] QuestEngine state machine completa
- [x] ConditionEvaluator (rule engine esplicito)
- [x] ActionExecutor (azioni minime)
- [x] Integrazione StoryDirector

**Data:** 2026-02-20

---

### Fase 6: Personality Engine ✅ COMPLETATA
- [x] PersonalityEngine con 8 behavior types
- [x] Impression tracking (5 dimensioni)
- [x] Archetype calculation
- [x] NPC relations/jealousy matrix
- [x] LLM-based Deep Analysis

**Data:** 2026-02-20

---

### Fase 7: Game Engine ✅ COMPLETATA
- [x] GameEngine 10-step orchestration
- [x] PromptBuilder classe separata
- [x] MediaPipeline async
- [x] State validation
- [x] Integrazione completa tutti i sistemi

**Data:** 2026-02-20

---

### Fase 8: Media Generation ✅ COMPLETATA
- [x] MediaPipeline async generation
- [x] Prompt builders (Single/Multi/NPC)
- [x] BASE_PROMPTS identici v3
- [x] ComfyUIClient API reali
- [x] VideoClient Wan2.1 I2V
- [x] Anti-fusion enhanced

**Data:** 2026-02-20

---

### Fase 9: UI ✅ COMPLETATA
- [x] StartupDialog 3 tabs
- [x] MainWindow 3 pannelli
- [x] Widgets custom (Quest, Companion, Event, Story, Image)
- [x] ImageViewer con zoom/pan
- [x] Dark theme global
- [x] Async event loop (qasync)

**Data:** 2026-02-20

---

## 🔄 Fase 10: Testing & Polish

### Obiettivi
- [ ] Unit tests (>80% coverage)
- [ ] Integration tests per game loop
- [ ] E2E tests per UI
- [ ] Performance profiling
- [ ] Bug fixing
- [ ] Documentation finale

### Features Opzionali
- [ ] Audio TTS implementation
- [x] **MemoryManager** ✅ COMPLETATO
  - History management, facts storage, summarization
- [ ] TimeManager (posticipato)
- [ ] Additional gameplay features

---

## 📝 Convenzioni Codice

- **Async/await:** SEMPRE per I/O (DB, API, file)
- **Type hints:** Obbligatori su funzioni pubbliche
- **Docstring:** Google style
- **Nomi:** snake_case funzioni/variabili, PascalCase classi

---

## 🎯 Prossimo Step

**Fase 10: Testing & Polish**

Priorità:
1. Unit tests per core systems
2. Integration tests game loop
3. Bug fixing
4. Performance optimization

---

**Ultimo aggiornamento:** 2026-02-20  
**Stato:** MVP completo - Pronto per testing
