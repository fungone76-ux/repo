# Luna RPG v4 - Project Roadmap

**Data inizio:** 2026-02-20  
**Stato:** Fasi 0-9 COMPLETATE + Global Events System v1.0 ✅  
**Versione:** 4.0.0-dev  
**Ultimo aggiornamento:** 2026-02-21 - Event System LLM Transmission

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
├── google_credentials.json     # Google Cloud TTS credentials
│
├── src/luna/                   # Package principale
│   ├── core/                   # Core engine
│   ├── systems/                # Game systems
│   ├── ai/                     # AI/LLM clients
│   ├── media/                  # Media generation
│   └── ui/                     # PySide6 interface
│
├── worlds/                     # Content YAML
│   ├── school_life_complete/   # ⭐ World v4 completo
│   └── legacy/
│
├── tests/                      # Test suite
├── storage/                    # Runtime data
└── docs/                       # Documentazione
```

---

## ✅ Fasi Completate

### Fase 0: Project Setup ✅ COMPLETATA
- [x] `pyproject.toml` con Poetry, Ruff, MyPy, Pytest
- [x] Struttura cartelle completa
- [x] `README.md`, `.env.example`
- [x] Entry point `__main__.py`

### Fase 1: Core Data Layer ✅ COMPLETATA
- [x] 25+ Pydantic Models in `core/models.py`
- [x] SQLAlchemy 2.0 Database (`core/database.py`)
- [x] StateManager completo (`core/state.py`)

### Fase 2: Configuration System ✅ COMPLETATA
- [x] Pydantic Settings (`core/config.py`)
- [x] UserPreferences persistenza JSON
- [x] Multi-provider LLM config

### Fase 3: World System + Gameplay Systems ✅ COMPLETATA
- [x] WorldLoader con modular + legacy support
- [x] 9 Gameplay Systems modulari
- [x] Documentazione YAML

### Fase 3b: Story Beats System ✅ COMPLETATA
- [x] StoryBeat, NarrativeArc, BeatExecution models
- [x] StoryDirector con trigger evaluation
- [x] Integrazione World Loader

### Fase 4: AI Layer ✅ COMPLETATA
- [x] BaseLLMClient astratto
- [x] GeminiClient (primario) - safety settings, JSON mode
- [x] MoonshotClient (fallback) - OpenAI-compatible
- [x] MockLLMClient per testing
- [x] LLMManager con retry/fallback automatico
- [x] Prompt builders + JSON schema

### Fase 5: Quest Engine ✅ COMPLETATA
- [x] QuestEngine state machine completa
- [x] ConditionEvaluator (rule engine esplicito)
- [x] ActionExecutor (azioni minime)
- [x] Integrazione StoryDirector

### Fase 6: Personality Engine ✅ COMPLETATA
- [x] PersonalityEngine con 8 behavior types
- [x] Impression tracking (5 dimensioni)
- [x] Archetype calculation
- [x] NPC relations/jealousy matrix
- [x] LLM-based Deep Analysis

### Fase 7: Game Engine ✅ COMPLETATA
- [x] GameEngine 10-step orchestration
- [x] PromptBuilder classe separata
- [x] MediaPipeline async
- [x] State validation
- [x] Integrazione completa tutti i sistemi

### Fase 8: Media Generation ✅ COMPLETATA
- [x] MediaPipeline async generation
- [x] Prompt builders (Single/Multi/NPC)
- [x] BASE_PROMPTS identici v3
- [x] ComfyUIClient API reali
- [x] VideoClient Wan2.1 I2V
- [x] AudioClient TTS (Google Cloud + gTTS)
- [x] Anti-fusion enhanced

### Fase 9: UI ✅ COMPLETATA
- [x] StartupDialog 3 tabs
- [x] MainWindow 3 pannelli
- [x] Widgets custom (Quest, Companion, Event, Story, Image)
- [x] ImageViewer con zoom/pan
- [x] Dark theme global
- [x] Async event loop (qasync)

---

## ✅ Aggiornamenti Post-MVP (Completati)

### World Creation System ✅
- [x] **World `school_life_complete`** creato e funzionante
  - 3 personaggi: Maria (42), Stella (18), Luna (38)
  - 12 quest complete con stati e transizioni
  - Story beats affinity-based (non turni)
  - Location System V2 implementato
  - Global events (rainstorm, blackout, etc.)

### Execution Mode System ✅
- [x] LOCAL mode: SD WebUI (Automatic1111) per immagini
- [x] RUNPOD mode: ComfyUI per immagini + Wan2.1 per video
- [x] Switch automatico con salvataggio preferenze
- [x] SDWebUIClient per generazione locale

### Chat UI ✅
- [x] Visualizzazione stile chat (utente verde, personaggio rosa)
- [x] Story panel con larghezza fissa
- [x] Distinzione chiara tra messaggi
- [x] Font aumentato a 15px

### Video Generation ✅
- [x] VideoGenerationDialog per input movimento
- [x] LLM conversione azione → temporal prompt
- [x] Integrazione Wan2.1 I2V
- [x] Progress dialog durante generazione

### Audio TTS ✅
- [x] Google Cloud TTS installato e configurato
- [x] Credenziali `google_credentials.json` supportate
- [x] Fallback gTTS funzionante
- [x] Supporto italiano (it-IT)

### Prompt Optimization ✅
- [x] Modificato prompt builder per risposte corte
- [x] Limite: max 3 frasi per risposta
- [x] Istruzioni strict per LLM

### BASE_PROMPTS Integration ✅
- [x] Uso corretto base prompt personaggi per consistenza visiva
- [x] ImagePromptBuilder con supporto character-specific prompts

### Global Events System v1.0 ✅
- [x] **Schema completo** con validazione campi obbligatori
- [x] **Trasmissione LLM**: Eventi inclusi nel system prompt
- [x] **EventSchemaValidator**: Validazione automatica all'avvio
  - Controlla campi obbligatori: `title`, `description`, `duration`, `atmosphere_change`, `narrative_prompt`
  - Rileva testo italiano in campi LLM (warning)
- [x] **EventContextBuilder**: Costruzione contesto LLM-friendly
  - Sostituzione placeholder: `{current_companion}`, `{location}`, `{time}`, `{player_name}`
  - Calcolo fase evento: "beginning", "ongoing", "ending"
  - Formattazione prompt: Header, Atmosphere, Narrative Context, World State, Visual Notes
- [x] **Convenzione Bilingue** definita e implementata:
  - Campi LLM (`description`, `atmosphere_change`, `narrative_prompt`, `visual_tags`) in **inglese**
  - Campi UI (`title`, `message`) in italiano
- [x] **Documentazione**: `docs/EVENT_SYSTEM_SPEC.md` con schema completo

### Enhanced Context Transmission v2.0 ✅
- [x] **Time Slot Context**: Trasmissione `ambient_description` e `lighting`
- [x] **Location Time Context**: Trasmissione `time_descriptions` per orario specifico
- [x] **Location Visual Context**: Trasmissione `visual_style` e `lighting` location
- [x] **Emotional State Context**: Trasmissione `description` e `dialogue_tone`
- [x] **Companion Background**: Nuovi campi `background` e `relationship_to_player`
- [x] **Affinity Tier Context**: Trasmissione `examples` e `voice_markers`
- [x] **Bugfix WorldLoader**: Caricamento corretto `ambient_description` time slots

### Bug Fixes ✅
- [x] GameState.flags per StoryDirector e Quests
- [x] Sampler names compatibili ComfyUI/SD WebUI
- [x] Physical description per personaggi
- [x] Quest syntax: target_stage vs target, value vs state

---

## 🔄 Fase 10: Testing & Polish (IN CORSO)

### Obiettivi
- [ ] Unit tests (>80% coverage)
- [ ] Integration tests per game loop
- [ ] E2E tests per UI
- [ ] Performance profiling
- [ ] Bug fixing su RunPod
- [ ] Documentation finale

### Features Opzionali Future
- [ ] Advanced Audio TTS con voice cloning
- [x] **MemoryManager** ✅ COMPLETATO
  - History management, facts storage, summarization
- [x] **TimeManager** ✅ COMPLETATO
  - Ciclo giorno/notte con transizioni
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
1. Test end-to-end del world `school_life_complete`
2. Verifica che l'LLM rispetti il limite 3 frasi
3. Bug fixing eventuali
4. Performance optimization

---

**Ultimo aggiornamento:** 2026-02-20 (World Creation + Bug Fixes + TTS Setup)
**Stato:** MVP completo con world funzionante, pronto per testing approfondito
