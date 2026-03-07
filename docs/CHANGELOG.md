# Changelog - Luna RPG v4

## [2026-03-07] - Modular Architecture V4.3

### 🏗️ Refactoring - V4.3

#### 1. TurnOrchestrator (Estrazione da engine.py)
- **File:** `src/luna/systems/turn_orchestrator.py` (NUOVO!)
- **Descrizione:** Estrazione completa della logica `process_turn` da engine.py
- **Steps implementati:** Tutti i 10 step originali preservati
  1. Dynamic event checking
  2. Movement detection & handling (con solo mode)
  3. Companion switching (mentioned/schedule/temporary)
  4. Multi-NPC detection
  5. Personality analysis
  6. StoryDirector check
  7. Quest engine update
  8. LLM generation con retry logic
  9. State updates (affinity, outfit, flags)
  10. Media generation (solo mode + multi-NPC)
- **Vantaggi:**
  - Engine.py ridotto da ~3100 a ~1600 righe
  - Logica del turno isolata e testabile
  - Preservato 100% della funzionalità originale

#### 2. NPC Detection System (Refactor)
- **File:** `src/luna/systems/npc_detector.py` (NUOVO!)
- **Features:**
  - Word boundary matching (`\b`) per evitare false positive
  - Extended skip_words (posture: 'seduta', 'seduto', 'in piedi')
  - Template-based NPC creation
- **Bug Fix:** "Seduta" non viene più rilevato come NPC

#### 3. Input Preprocessor (Refactor)
- **File:** `src/luna/systems/input_preprocessor.py` (NUOVO!)
- **Responsabilità:** Parsing input, command handling, movement routing

#### 4. Response Processor (Refactor)
- **File:** `src/luna/systems/response_processor.py` (NUOVO!)
- **Responsabilità:** LLM validation, retry logic, safety filters

#### 5. State Updater (Refactor)
- **File:** `src/luna/systems/state_updater.py` (NUOVO!)
- **Responsabilità:** Game state updates, affinity, outfit, flags

#### 6. Media Coordinator (Refactor)
- **File:** `src/luna/systems/media_coordinator.py` (NUOVO!)
- **Responsabilità:** Image/video generation coordination, solo mode handling

#### 7. Utility Modules
- **File:** `src/luna/utils/logging_config.py` - Structured logging
- **File:** `src/luna/utils/retry_decorator.py` - Exponential backoff per LLM

### 📁 Files Nuovi/Modificati - V4.3
- `src/luna/systems/turn_orchestrator.py` (NUOVO - 950+ righe)
- `src/luna/systems/npc_detector.py` (NUOVO - 220 righe)
- `src/luna/systems/input_preprocessor.py` (NUOVO - 260 righe)
- `src/luna/systems/response_processor.py` (NUOVO - 200 righe)
- `src/luna/systems/state_updater.py` (NUOVO - 250 righe)
- `src/luna/systems/media_coordinator.py` (NUOVO - 260 righe)
- `src/luna/utils/logging_config.py` (NUOVO)
- `src/luna/utils/retry_decorator.py` (NUOVO)
- `src/luna/core/engine.py` (REFACTORED - delega a TurnOrchestrator)
- `src/luna/systems/activity_system.py` (FIX - typo EXERCIZING)

### 🔧 Bug Fix - V4.3
- **ActivityType Typo:** `EXERCIZING` → `EXERCISING` in activity_system.py

---

## [2026-03-04] - Phase System V4.2 & Generic Schedules

### ✨ New Features - V4.2

#### 1. Phase System (8 Turns per Phase)
- **Sistema:** 8 turni per fase (Morning → Afternoon → Evening → Night)
- **Ciclo:** 32 turni = 1 giorno completo
- **Auto-advance:** Tempo avanza automaticamente ogni 8 turni
- **File:** `src/luna/systems/phase_manager.py` (nuovo)

#### 2. NPC Daily Schedules (Generic)
- **Feature:** Companion seguono routine giornaliere basate sul tempo
- **Al cambio fase:** NPC si spostano, player rimane in location
- **Auto-switch:** Se companion lascia → passa a "solo mode"
- **File:** `src/luna/systems/schedule_manager.py` (modificato)

#### 3. Freeze System (Pause Turns)
- **Comandi:** `pausa`, `freeze`, `blocca turni` per bloccare
- **Auto-freeze:** Scene romantiche/critiche bloccano automaticamente
- **Comandi resume:** `riprendi`, `unfreeze` per riprendere
- **Uso:** Previene che il tempo scada durante scene importanti

#### 4. File Rename: npc_schedules.yaml → companion_schedules.yaml
- **Motivo:** Nome precedente confondeva NPC secondari con Companion principali
- **Aggiornato:** 
  - `worlds/school_life_complete/companion_schedules.yaml` (rinominato)
  - `worlds/prehistoric_tribe/companion_schedules.yaml` (rinominato)
  - `src/luna/systems/world.py` (loader aggiornato)
  - Documentazione aggiornata
- **Nota:** Header aggiunto per chiarezza su COMPANION vs NPC

### 📁 Files Nuovi/Modificati - V4.2
- `src/luna/systems/phase_manager.py` (NUOVO)
- `src/luna/core/models.py` (PhaseChangeResult, TurnResult flags)
- `src/luna/core/engine.py` (integration PhaseManager)
- `worlds/*/companion_schedules.yaml` (schedule specifiche)
- `docs/PHASE_SYSTEM_V42.md` (documentazione tecnica)
- `docs/WORLD_CREATION_GUIDE.md` (sezione schedules)
- `docs/COMPLETE_TECHNICAL_SPECIFICATION.md` (sezione 4.4)

---

## [2026-03-03] - Movement Fixes, Solo Mode & StateMemory

### 🔧 Fix

#### 1. Movement Fixed - V4.1
- **Problema:** Movimento falliva per `requires_parent` (es. bagno, segreteria)
- **Causa:** `can_move_to()` bloccava se non si era nella location parent
- **Fix:** Rimosso check `requires_parent` - movimento libero ovunque
- **File:** `src/luna/systems/location.py`

#### 2. NPC Template Loading Fixed - V4.1
- **Problema:** Template NPC (es. segretaria rossa) non venivano caricati
- **Causa:** `WorldDefinition` non includeva il campo `npc_templates`
- **Effetto:** NPC generici senza caratteristiche visive definite
- **Fix:** Aggiunto `npc_templates`, `npc_fallback_female`, `npc_fallback_male` a `WorldDefinition`
- **File:** `src/luna/systems/world.py`

#### 3. NPC Template Override - V4.1
- **Problema:** NPC generici creati prima del template non venivano sostituiti
- **Causa:** `_create_npc_from_template()` creava nuovo nome (`npc_X`) senza rimuovere generico
- **Fix:** Ora rimuove l'NPC generico esistente prima di creare quello template
- **File:** `src/luna/core/engine.py`

#### 4. Movement False Positive Fixed - V4.1
- **Problema:** Frasi come "riesco a farlo" venivano interpretate come movimento
- **Causa:** Pattern `esco ` matchava dentro `riesco ` (substring match)
- **Fix:** Aggiunto word boundary matching (regex con \b)
- **File:** `src/luna/systems/movement.py`

#### 5. Movement Companion Name Filter - V4.1
- **Problema:** "entra Luna" veniva interpretato come movimento verso `school_office_luna`
- **Causa:** Il nome del companion veniva risolto come location
- **Fix:** Aggiunto check in `resolve_location()` per skippare nomi companion
- **File:** `src/luna/systems/movement.py`

#### 5. Memory Summary Error Filter - V4.1
- **Problema:** Messaggi di errore LLM venivano salvati come facts ("Mi scusi, c'è stato un errore...")
- **Causa:** `_generate_llm_summary` non filtrava risposte di errore
- **Effetto:** Fatti falsi/memorie inutili nella long-term memory
- **Fix:** Aggiunto filtro per error phrases ("errore", "mi scusi", "unable to", etc.)
- **File:** `src/luna/systems/memory.py`

#### 6. Load Game - Active Companion Restore - V4.1
- **Problema:** Dopo il load, Luna rispondeva come segretaria (personaggio sbagliato)
- **Causa:** `active_companion` non veniva ripristinato dal save
- **Effetto:** L'LLM usava il contesto del personaggio sbagliato
- **Fix:** Aggiunto restore esplicito di `active_companion` nel codice di load
- **File:** `src/luna/ui/main_window.py`

#### 7. Guardrails Error Method Fixed - V4.1
- **Problema:** `'GuardrailsValidationError' object has no attribute 'get_retry_prompt'`
- **Causa:** Chiamato metodo su eccezione invece che sulla classe corretta
- **Fix:** Cambiato da `guard_err.get_retry_prompt()` a `ResponseGuardrails.get_retry_prompt()`
- **File:** `src/luna/core/engine.py`

#### 8. Companion Left Behind Logic Fixed
- **Problema:** `companion_left_behind` era `False` anche quando doveva essere `True`
- **Causa:** Logic error in `MovementHandler.handle_movement()`
- **Fix:** Semplificata logica - sempre lascia indietro companion quando player si muove
- **File:** `src/luna/systems/movement.py`

### ⭐ Aggiunto

#### 1. Time Manager System - V4.1 Hybrid Adaptive
- **File:** `src/luna/systems/time_manager.py` (nuovo!)
- **Fase 1 (Auto-advance):** Tempo avanza ogni N turni (default: 5)
- **Fase 2 (Rest commands):** Rileva comandi tipo "vado a dormire", "riposo"
- **Fase 3 (Deadlines):** Sistema scadenze per quest con warning
- **Messaggi immersivi:** Transizioni tipo "🌅 Il sole sale più alto..."
- **UI:** Rimosso pulsante manuale, tempo ora è display-only

#### 2. Movement System Refactor
- **File:** `src/luna/systems/movement.py` (nuovo!)
- **Descrizione:** Estratto completo da engine.py
- **Features:**
  - Rilevamento intento movimento ("vado in bagno")
  - Risoluzione nome → ID location
  - Gestione companion sempre indietro (V4.1)
  - Parametri per immagini solo mode

#### 2. Solo Mode (Immagini Location Vuote)
- **Quando:** Player si muove senza companion
- **Meccanica:**
  - Companion switcha a `"_solo_"`
  - Nessun LoRA applicato
  - Usa `location_visual_style` per scene vuote
  - Esempio: bagno vuoto, corridoio vuoto, etc.

#### 3. StateMemoryManager (Unificazione)
- **File:** `src/luna/systems/state_memory.py` (nuovo!)
- **Descrizione:** Unifica salvataggio stato + memoria
- **Salva:**
  - Game state (location, outfit, affinità)
  - Quest states
  - Event states
  - StoryDirector state
  - Personality states
  - Short-term memory (messaggi)
  - Long-term memory (fatti)
- **Prima:** 40+ righe sparse in engine.py
- **Ora:** `await self.state_memory.save_all()`

#### 4. IntroGenerator (Refactor)
- **File:** `src/luna/systems/intro.py` (nuovo!)
- **Descrizione:** Estratto da engine.py
- **Metodi:** `generate()`, `_build_prompt()`

#### 5. Nuovi NPC
- **File:** `worlds/school_life_complete/npc_templates.yaml`
- **Aggiunti:** psicologa, farmacista, parroco, commesso, barista, bibliotecaria, allenatore, infermiera, segretaria

#### 6. Nuova Location
- **File:** `worlds/school_life_complete/locations.yaml`
- **Aggiunta:** `school_secretary` (Segreteria Scolastica)
- **Aliases:** segreteria, ufficio amministrativo

### ✅ Modificato

#### Core Models
- **File:** `src/luna/core/models.py`
- **Aggiunto:** `TurnResult` (spostato da engine.py)
- **Import corretto:** `from luna.core.models import TurnResult`

#### GameEngine
- **File:** `src/luna/core/engine.py`
- **Ridotto:** Da ~2700 a ~2470 righe (-230 righe)
- **Rimossi:** `generate_intro()`, `_build_intro_prompt()`
- **Rimosso:** Codice salvataggio sparso
- **Aggiunto:** `self.state_memory`, `self.intro_generator`

#### Media Pipeline
- **File:** `src/luna/media/pipeline.py`
- **Aggiunto:** Supporto `location_visual_style` per solo mode
- **Aggiunto:** Parametro in `_generate_image_async()`

#### ImagePromptBuilder
- **File:** `src/luna/media/builders.py`
- **Aggiunto:** Rilevamento solo mode (`character_name == "_solo_"`)
- **Aggiunto:** Uso `location_visual_style` quando in solo

### 🐛 Bug Fix

#### Movimento - Memoria Persa
- **Problema:** Messaggi durante movimento non salvati
- **Fix:** Aggiunto `await self.state_memory.add_message()` prima del return

#### Farewell - Stato Non Salvato
- **Problema:** Stato non persisteva dopo "ci vediamo dopo"
- **Fix:** Aggiunto `await self.state_memory.save_all()`

#### MovementHandler - Parametri Invertiti
- **Problema:** `(location_manager, world, game_state)` invece di `(world, location_manager, game_state)`
- **Fix:** Ordine parametri corretto

### 🗑️ Rimosso
- **File:** `src/repo/` (backup vecchio codice)
- **Note:** 196 file duplicati non utilizzati

---

## [2026-02-28] - Sistemi Deterministici & UI

### ⭐ Aggiunto

#### 1. Affinity Calculator (Sistema Deterministico)
- **File:** `src/luna/systems/affinity_calculator.py`
- **Descrizione:** Calcolo affinità basato su regex pattern invece di LLM
- **Vantaggi:** Prevedibile, debuggabile, bilanciato
- **Sistema:** 5 tier positivi (+1 a +5), 5 tier negativi (-1 a -5)
- **Bonus:** Consecutive bonus (+1 ogni 3), Time bonus (+1 ogni 5 turni)

#### 2. Quest Choice System
- **File:** `src/luna/ui/quest_choice_widget.py`
- **Descrizione:** UI con bottoni per scelte quest invece di testo libero
- **Tipi supportati:** Accetta/Rifiuta/Info, Yes/No, Custom choices
- **Blocca input** durante scelta per evitare confusione
- **Colore bottoni:** Verde (accetta), Rosso (rifiuta), Blu (info)

#### 3. Companion Locator Widget
- **File:** `src/luna/ui/companion_locator_widget.py`
- **Descrizione:** Mostra posizione companion basata su affinità tier
- **Unlock:** 0-25 (vago), 26-50 (area), 51+ (esatto)

### ✅ Modificato

#### Engine
- `src/luna/core/engine.py`: Integrazione affinity calculator
- `src/luna/core/models.py`: Aggiunto tipo `activation_type: "choice"`
- `src/luna/systems/quests.py`: Supporto quest pending choice

#### UI
- `src/luna/ui/main_window.py`: Aggiunto choice widget e gestione input bloccato

---

## [2026-02-27] - Save/Load & Movement

### ⭐ Aggiunto

#### Save/Load System
- **Database:** SQLite con async SQLAlchemy
- **Persiste:** Game state completo (location, affinità, outfit, quest, flags)
- **UI:** Pulsanti Save/Load nella toolbar

#### Movement System Italiano
- Pattern regex per verbi italiani: vado, esco, entro, torno, raggiungo
- Alias matching per location
