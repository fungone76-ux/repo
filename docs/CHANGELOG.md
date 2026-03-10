# Changelog - Luna RPG v4

## [2026-03-09] - V4.5 Remote Communication, Invitations & Outfit System

### 📱 Comunicazione Remota (Phone/Message)

**Nuovo File:** `src/luna/systems/remote_communication.py`

Sistema completo per comunicare con NPC via telefono/messaggi:

- **Pattern detection:** Riconosce "scrivo a X", "mando messaggio a X", "chiamo X", "mandami..."
- **Auto-switch companion:** Il target diventa companion attivo automaticamente
- **Location corretta:** L'immagine mostra il target nella sua location (da schedule)
- **Context prompt:** Aggiunge "Stai ricevendo un messaggio..." al system prompt
- **Affinity & Personality:** Funzionano correttamente sul target remoto
- **Visual EN override:** Sovrascrive la descrizione scena generata dall'LLM per matchare la location reale del NPC

**Esempio:**
```
Player (a casa): "Scrivo a Luna, mi manchi"
→ Companion diventa Luna
→ Luna risponde dal suo ufficio
→ Affinity calcolata con Luna
→ Immagine generata nell'ufficio di Luna (non in classe!)
```

### 🏠 Sistema di Inviti a Casa

**Nuovo File:** `src/luna/systems/invitation_manager.py`

Invita NPC a casa tua via messaggio:

1. **Invio:** "Vieni a casa mia stasera" → registrato con tempo di arrivo
2. **Accettazione:** NPC risponde positivamente ("Va bene", "Ok", "Ci sto")
3. **Attesa:** Invito in sospeso fino al cambio fase
4. **Arrivo:** Messaggio narrativo:
   > *Mentre ti rilassi in salotto, senti suonare il campanello. Aprendo la porta, trovi [NPC] che è venuta come promesso.*

**Tempi supportati:** mattina, pomeriggio, sera, notte

### 👕 Outfit Adattivo per Location

**File:** `turn_orchestrator.py` - Metodo `_update_outfit_for_context()`

L'outfit del companion cambia automaticamente in base alla location:

| Location | Luna | Stella | Maria |
|----------|------|--------|-------|
| Palestra | `gym_teacher` | `cheerleader` | - |
| Scuola/Ufficio | `teacher_suit` | `uniform_mod` | `cleaning_uniform` |
| Casa (notte) | `nightwear` | `pajamas` | `home` |
| Casa (giorno) | `casual` | `pajamas` | `home` |
| Piscina/Spiaggia | - | `swimsuit` | - |

**Mapping Schedule:**
- `teacher_formal` → `teacher_suit`
- `teacher_strict` → `strict_teacher`

### ⏰ Messaggio Narrativo Cambio Fase

Quando un companion se ne va al cambio fase:

```
⏰ La campanella suona. È pomeriggio.

*Luna raccoglie le sue cose.* "Devo andare in ufficio a correggere i compiti."

[La Luna è andata in: Ufficio Professoresse]
```

### 👥 Regole di Follow Migliorate

Quando ti sposti:

**Un companion ti segue SOLO se:**
- Affinity ≥ 65
- È stato ESPLICITAMENTE INVITATO ("vieni con me", "seguimi")
- Non è un NPC temporaneo

**Altrimenti:** rimane indietro, switch automatico a SOLO

### 🧹 Pulizia Memoria Nuova Partita

Quando inizi una nuova partita:
- **SQLite:** Tutti i messaggi e fatti cancellati
- **ChromaDB:** Memoria semantica cancellata
- **Isolamento:** Nuovo session_id garantisce partita pulita

### 🔧 Affinity Calcolata da Python

**Modifica:** L'affinity è ora calcolata deterministicamente da Python invece che dall'LLM:

```python
calculator = get_calculator()
affinity_result = calculator.calculate(
    user_input=user_input,
    companion_name=game_state.active_companion,
    turn_count=game_state.turn_count,
)
```

**Vantaggi:** Prevedibile, bilanciata, funziona in comunicazione remota

### 🐛 Bug Fix V4.5

- **Movement "blocked":** Non blocca più quando sei già alla location target
- **Phase Manager State:** `_turns_in_phase` ora salvato/caricato correttamente
- **Personality Impression:** `analyze_with_llm` non sovrascrive più i cambiamenti quando fallisce
- **MultiNPC Location:** Filtra NPC per location usando `companion.schedule`
- **Schedule Access:** Fix errore "dict object has no attribute schedule"

### 📁 Files Modificati V4.5

| File | Modifica |
|------|----------|
| `remote_communication.py` | **NUOVO** - Sistema comunicazione remota |
| `invitation_manager.py` | **NUOVO** - Sistema inviti NPC |
| `turn_orchestrator.py` | Integrazione V4.5, outfit adattivo, affinity Python |
| `movement.py` | Fix "blocked" quando già alla location |
| `memory.py` | Metodo `clear()` completo |
| `engine.py` | Pulizia memoria su nuova partita, Phase Manager state |
| `phase_manager.py` | `to_dict()`/`from_dict()` per salvare stato |
| `personality.py` | Fix impression change overwrite |
| `multi_npc/manager.py` | Fix accesso a `companion.schedule` |
| `affinity_calculator.py` | Log debug per pattern matching |
| `prompt_builder.py` | Fix accesso a schedule come dict |

### 📝 TODO per V4.6

- **Memory Isolation:** I messaggi devono essere isolati per companion (Stella non deve vedere i messaggi a Luna)

### 📱 Comunicazione Remota (Phone/Message)

**Nuovo File:** `src/luna/systems/remote_communication.py`

Sistema completo per comunicare con NPC via telefono/messaggi:

- **Pattern detection:** Riconosce "scrivo a X", "mando messaggio a X", "chiamo X", "mandami..."
- **Auto-switch companion:** Il target diventa companion attivo automaticamente
- **Location corretta:** L'immagine mostra il target nella sua location (da schedule)
- **Context prompt:** Aggiunge "Stai ricevendo un messaggio..." al system prompt
- **Affinity & Personality:** Funzionano correttamente sul target remoto

**Esempio:**
```
Player (a casa): "Scrivo a Luna, mi manchi"
→ Companion diventa Luna
→ Luna risponde dal suo ufficio
→ Affinity calcolata con Luna
```

### 🏠 Sistema di Inviti a Casa

**Nuovo File:** `src/luna/systems/invitation_manager.py`

Invita NPC a casa tua via messaggio:

1. **Invio:** "Vieni a casa mia stasera" → registrato con tempo di arrivo
2. **Accettazione:** NPC risponde positivamente ("Va bene", "Ok", "Ci sto")
3. **Attesa:** Invito in sospeso fino al cambio fase
4. **Arrivo:** Messaggio narrativo:
   > *Mentre ti rilassi in salotto, senti suonare il campanello. Aprendo la porta, trovi [NPC] che è venuta come promesso.*

**Tempi supportati:** mattina, pomeriggio, sera, notte

### ⏰ Messaggio Narrativo Cambio Fase

Quando un companion se ne va al cambio fase:

```
⏰ La campanella suona. È pomeriggio.

*Luna raccoglie le sue cose.* "Devo andare in ufficio a correggere i compiti."

[La Luna è andata in: Ufficio Professoresse]
```

### 👥 Regole di Follow Migliorate

Quando ti sposti:

**Un companion ti segue SOLO se:**
- Affinity ≥ 65
- È stato ESPLICITAMENTE INVITATO ("vieni con me", "seguimi")
- Non è un NPC temporaneo

**Altrimenti:** rimane indietro, switch automatico a SOLO

### 🧹 Pulizia Memoria Nuova Partita

Quando inizi una nuova partita:
- **SQLite:** Tutti i messaggi e fatti cancellati
- **ChromaDB:** Memoria semantica cancellata
- **Isolamento:** Nuovo session_id garantisce partita pulita

### 🔧 Affinity Calcolata da Python

**Modifica:** L'affinity è ora calcolata deterministicamente da Python invece che dall'LLM:

```python
calculator = get_calculator()
affinity_result = calculator.calculate(
    user_input=user_input,
    companion_name=game_state.active_companion,
    turn_count=game_state.turn_count,
)
```

**Vantaggi:** Prevedibile, bilanciata, funziona in comunicazione remota

### 📁 Files Modificati V4.5

| File | Modifica |
|------|----------|
| `remote_communication.py` | **NUOVO** - Sistema comunicazione remota |
| `invitation_manager.py` | **NUOVO** - Sistema inviti NPC |
| `turn_orchestrator.py` | Integrazione V4.5, affinity Python |
| `memory.py` | Metodo `clear()` completo |
| `engine.py` | Pulizia memoria su nuova partita |

---

## [2026-03-08] - Director of Photography & Bug Fixes

### 🎬 Director of Photography (DoP) System - NEW!

#### Aspect Ratio Dinamico per Immagini e Video
- **File:** `src/luna/media/aspect_ratio_director.py` (NUOVO!)
- **Descrizione:** Sistema che simula un Direttore della Fotografia esperto per decidere l'orientamento ottimale delle immagini
- **Tre modalità supportate:**
  - `landscape` (736x512): Panorami, ambienti ampi, scene d'azione orizzontale, gruppi
  - `portrait` (512x736): Ritratti, figure intere, architetture verticali, primi piani
  - `square` (1024x1024): Medium shot bilanciati, default versatile
- **Vincolo tecnico:** Tutte le dimensioni divisibili per 16 (compatibilità WanVideo)
- **Integrazione:**
  - Prompt LLM aggiornato con sezione DoP che richiede aspect_ratio e ragionamento
  - `ImagePrompt` e `LLMResponse` estesi con campi `aspect_ratio` e `dop_reasoning`
  - `ComfyClient` mappa aspect_ratio a dimensioni concrete nel workflow
  - `VideoClient` eredita proporzioni dall'immagine sorgente per coerenza

#### Files Modificati per DoP:
- `src/luna/media/aspect_ratio_director.py` (NUOVO - 250 righe)
- `src/luna/core/models.py` - Aggiunti campi aspect_ratio a ImagePrompt e LLMResponse
- `src/luna/media/builders.py` - ImagePromptBuilder supporta aspect_ratio
- `src/luna/media/pipeline.py` - MediaPipeline passa aspect_ratio ai generatori
- `src/luna/media/comfy_client.py` - Applica dimensioni dinamiche al workflow
- `src/luna/media/video_client.py` - Preserva aspect ratio nel video
- `src/luna/core/prompt_builder.py` - Sezione DoP nel system prompt
- `src/luna/systems/turn_orchestrator.py` - Passa aspect_ratio dalla risposta LLM

### 🔧 Bug Fixes - V4.3.1

#### 1. Fix Caricamento Partita - Affinity & Personality
- **Problema:** Caricando una partita, affinity e personality partivano da zero
- **Causa:** I valori venivano caricati nel game state ma non sincronizzati con UI e personality engine
- **Fix in `main_window.py`:**
  - `_update_companion_list()` ora aggiorna le barre affinity dai valori del game state
  - `_load_game()` carica esplicitamente i personality states dal database
  - `_load_game()` carica esplicitamente i quest states dal database
  - Aggiunto `_update_event_widget()` a `_update_all_widgets()`

#### 2. Fix Eventi Globali in UI
- **Problema:** Gli eventi globali attivi non venivano mostrati nella finestra di sinistra dopo il caricamento
- **Causa:** Il callback `on_event_changed` viene chiamato solo quando un evento CAMBIA, non quando viene caricato
- **Fix in `main_window.py`:**
  - Dopo il caricamento, sincronizza il widget con `event_manager.get_primary_event()`
  - Aggiunto metodo `_update_event_widget()` per aggiornamento manuale
  - Chiamata sincronizzazione iniziale in `start_game()` e `_load_game()`

#### 3. Fix Quest Status Enum vs String
- **Problema:** `AttributeError: 'str' object has no attribute 'value'` in `state_memory.py`
- **Causa:** In alcuni casi `quest_state.status` era già una stringa invece di un enum
- **Fix in `state_memory.py`:**
  - Aggiunto controllo `hasattr(quest_state.status, 'value')` prima di accedere a `.value`
  - Fallback a `str(quest_state.status)` se già stringa
  - Pattern coerente con altri enum nel codebase

### 📁 Files Modificati - Bug Fixes:
- `src/luna/ui/main_window.py` - Fix caricamento affinity, personality, eventi
- `src/luna/systems/state_memory.py` - Fix quest status enum/string handling

---

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
