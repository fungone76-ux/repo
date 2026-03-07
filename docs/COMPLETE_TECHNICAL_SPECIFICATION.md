# LUNA RPG v4 - SPECIFICAZIONE TECNICA E DISCURSIVA COMPLETA

**Versione:** 1.0  
**Data:** 2026-02-28  
**Tipo:** Documentazione Tecnico-Discursiva per Ricostruzione Completa

---

## PREMESSA DISCURSIVA

Luna RPG v4 è un visual novel/RPG interattivo guidato da AI, dove il giocatore interagisce con companion virtuali attraverso dialoghi in linguaggio naturale. L'esperienza è arricchita da immagini generate in tempo reale che rappresentano le scene descritte dall'AI.

### Cos'è Luna RPG v4 (Visione Utente)

Per il giocatore, Luna RPG è:
- Una storia interattiva dove scrive in italiano e l'AI risponde
- Un'esperienza visiva con immagini generate per ogni scena
- Un sistema di relazioni dove le azioni influenzano l'affinità con i personaggi
- Un mondo persistente che evolve nel tempo

### Cos'è Luna RPG v4 (Visione Tecnica)

Per lo sviluppatore, Luna RPG è:
- Un orchestratore che coordina LLM (Gemini/Moonshot), database SQLite, e ComfyUI
- Un game loop turn-based con 10 step sequenziali
- Un sistema di stati gestito via Pydantic e SQLAlchemy
- Un'architettura event-driven con PySide6 per la UI

---

## PARTE I: ARCHITETTURA E FILOSOFIA

### 1.1 Perché Questa Architettura?

**Il Problema:** Creare un gioco narrativo dove:
1. L'AI genera testo coerente con lo stato di gioco
2. Le immagini devono corrispondere alla scena descritta
3. Lo stato deve persistere tra sessioni
4. L'interfaccia deve essere reattiva durante le chiamate AI

**La Soluzione:**
```
Separazione di Concetti:
- GameEngine: Orchestrazione pura, nessuna logica di business
- Systems: Ogni sistema gestisce un aspetto specifico
- Models: Dati immutabili (Pydantic) garantiscono consistenza
- UI: PySide6 con async per non bloccare durante LLM/media
```

### 1.2 Il Game Loop come Cuore del Sistema

Ogni turno rappresenta un ciclo completo di "input → elaborazione → output → persistenza". Pensalo come un respiro: il giocatore "ispira" con il suo input, il sistema "elabora" attraverso i 10 step, e "espira" con la risposta.

**I 10 Step Spiegati Discorsivamente:**

1. **Personality Analysis** - Il sistema "ascolta" il tono del giocatore. Se scrive "ti amo", rileva romanticismo. Se scrive "obbedisci", rileva dominanza. Questo crea un profilo comportamentale.

2. **StoryDirector Check** - Il sistema verifica se è il momento giusto per eventi narrativi importanti. Come un regista che dice "azione" quando le condizioni sono perfette.

3. **Quest Engine Update** - Controlla se il giocatore ha sbloccato nuove missioni. Le quest possono attivarsi automaticamente, tramite trigger, o richiedere scelte esplicite.

4. **System Prompt Building** - Costruisce il "copione" per l'AI. Include: chi siamo, dove siamo, chi è il companion, cosa è successo prima, cosa deve succedere ora.

5. **LLM Generation** - L'AI "legge" il copione e "recita" la sua parte, generando testo e descrizioni visive.

6. **Response Validation** - Verifica che la risposta dell'AI sia valida e applica correzioni se necessario.

7. **State Updates** - Applica i cambiamenti proposti dall'AI (affinità, location, outfit).

8. **Media Generation** - Genera l'immagine della scena in background.

9. **Save State** - Salva tutto sul database.

10. **Return Result** - Mostra il risultato al giocatore.

---

## PARTE II: STRUTTURA DEL PROGETTO

### 2.1 Organizzazione Logica

Il progetto è organizzato per layer di astrazione, dal più basso (dati) al più alto (UI):

```
Layer 5: UI (PySide6)
    └─> Cosa vede e tocca l'utente
    
Layer 4: Game Logic
    └─> Regole del gioco, quest, personalità
    
Layer 3: AI Integration
    └─> Comunicazione con LLM
    
Layer 2: Media Generation
    └─> Comunicazione con ComfyUI
    
Layer 1: Data Persistence
    └─> Database e file system
```

### 2.2 Directory Tree Completo

```
luna-rpg-v4/
│
├── src/luna/                    # CODICE SORGENTE
│   ├── __main__.py              # Entry point: inizializza Qt e avvia app
│   │
│   ├── core/                    # NUCLEO DEL SISTEMA
│   │   ├── models.py            # 📐 TUTTI i modelli dati Pydantic
│   │   │                         # Questo file definisce la "forma" di ogni
│   │   │                         # dato nel gioco: GameState, Companion, Quest...
│   │   ├── engine.py            # 🎮 GameEngine: il direttore d'orchestra
│   │   │                         # Coordina TUTTI i sistemi in sequenza
│   │   ├── state.py             # 💾 StateManager: gestisce il GameState
│   │   │                         # Carica, salva, modifica lo stato corrente
│   │   ├── database.py          # 🗄️  DatabaseManager: SQLite async
│   │   │                         # Tutta la persistenza passa da qui
│   │   ├── prompt_builder.py    # 📝 Costruisce i prompt per l'AI
│   │   │                         # Assembla contesto + istruzioni + schema JSON
│   │   ├── story_director.py    # 🎬 Gestisce i "beat" narrativi
│   │   │                         # Momenti obbligatori nella storia
│   │   └── config.py            # ⚙️  Configurazione da .env
│   │
│   ├── ai/                      # INTEGRAZIONE LLM
│   │   ├── base.py              # Interfaccia comune ai provider
│   │   ├── gemini.py            # Google Gemini API
│   │   ├── moonshot.py          # Moonshot API (OpenAI-compatibile)
│   │   ├── manager.py           # Factory e gestione fallback
│   │   ├── prompts.py           # Template system prompt
│   │   ├── json_repair.py       # Ripara JSON malformato
│   │   └── personality_analyzer.py
│   │
│   ├── media/                   # GENERAZIONE MEDIA
│   │   ├── pipeline.py          # Orchestrazione media
│   │   ├── comfy_client.py      # Client API ComfyUI (RunPod)
│   │   ├── sd_webui_client.py   # Client SD WebUI (locale)
│   │   ├── builders.py          # Costruzione prompt immagini
│   │   ├── audio_client.py      # Text-to-speech Google
│   │   └── video_client.py      # Video generation Wan2.1
│   │
│   ├── systems/                 # GAMEPLAY SYSTEMS
│   │   ├── world.py             # Caricamento mondi YAML
│   │   ├── quests.py            # Sistema quest completo
│   │   ├── personality.py       # Analisi comportamento
│   │   ├── memory.py            # Memoria conversazioni
│   │   ├── location.py          # Gestione location
│   │   ├── global_events.py     # Eventi globali
│   │   ├── dynamic_events.py    # Eventi random/giornalieri
│   │   ├── outfit_modifier.py   # Modifiche outfit deterministiche
│   │   ├── affinity_calculator.py # NUOVO: calcolo affinità regex
│   │   ├── companion_locator.py # Tracciamento posizione NPC
│   │   ├── gameplay_manager.py  # Manager gameplay actions
│   │   ├── movement.py          # 🆕 V4.3: Gestione movimento player
│   │   ├── state_memory.py      # 🆕 V4.3: Unificazione stato + memoria
│   │   ├── intro.py             # 🆕 V4.3: Generazione scena iniziale
│   │   ├── activity_system.py   # 🆕 V4.2: Sistema attività NPC
│   │   ├── phase_manager.py     # 🆕 V4.2: Gestione fasi giornata
│   │   ├── schedule_manager.py  # 🆕 V4.2: Schedule giornaliere NPC
│   │   ├── time_manager.py      # 🆕 V4.1: Gestione tempo e scadenze
│   │   ├── pose_extractor.py    # Estrazione pose da input
│   │   ├── initiative_system.py # Gestione iniziativa conversazioni
│   │   # 🆕 V4.3: Refactored components (from engine.py)
│   │   ├── turn_orchestrator.py   # 🆕 V4.3: Coordinamento turno 10-step
│   │   ├── npc_detector.py        # 🆕 V4.3: Detection NPC/companion
│   │   ├── input_preprocessor.py  # 🆕 V4.3: Parsing input & comandi
│   │   ├── response_processor.py  # 🆕 V4.3: Validazione LLM & retry
│   │   ├── state_updater.py       # 🆕 V4.3: Aggiornamento stato
│   │   └── media_coordinator.py   # 🆕 V4.3: Coordinamento media
│   │   ├── gameplay/            # Sottosistemi gameplay
│   │   │   ├── affinity.py
│   │   │   ├── inventory.py
│   │   │   ├── combat.py
│   │   │   ├── economy.py
│   │   │   └── ...
│   │   └── multi_npc/           # Sistema multi-personaggio
│   │       ├── manager.py
│   │       ├── dialogue_sequence.py
│   │       └── interaction_rules.py
│   │
│   ├── utils/                   # 🆕 V4.3: UTILITY MODULES
│   │   ├── logging_config.py    # Structured logging
│   │   └── retry_decorator.py   # Exponential backoff per LLM
│   │
│   ├── ui/                      # INTERFACCIA UTENTE
│   │   ├── app.py               # Setup QApplication
│   │   ├── main_window.py       # Finestra principale (layout 4 pannelli)
│   │   ├── widgets.py           # Quest tracker, companion status
│   │   ├── action_bar.py        # Barra azioni contestuali
│   │   ├── feedback_visualizer.py # Notifiche toast
│   │   ├── quest_choice_widget.py # UI scelte multiple
│   │   ├── companion_locator_widget.py
│   │   ├── image_viewer.py
│   │   ├── startup_dialog.py    # Dialog iniziale
│   │   └── video_dialog.py
│   │
│   └── config/
│       └── models.yaml          # Configurazione modelli LLM
│
├── worlds/                      # DEFINIZIONI MONDI
│   ├── school/                  # World "School"
│   │   ├── _meta.yaml          # Metadata, narrative arc, endgame
│   │   ├── locations.yaml      # Location e connessioni
│   │   ├── global_events.yaml  # Eventi globali
│   │   ├── luna.yaml           # Companion Luna completo
│   │   └── stella.yaml         # Companion Stella
│   │
│   └── prehistoric_tribe/       # World "Terra degli Antenati"
│       ├── _meta.yaml
│       ├── locations.yaml
│       ├── kara.yaml
│       ├── naya.yaml
│       └── zara.yaml
│
├── storage/                     # DATI RUNTIME
│   ├── images/                  # Immagini generate
│   ├── videos/                  # Video generati
│   ├── audio/                   # Audio TTS
│   └── luna.db                 # Database SQLite
│
├── docs/                        # DOCUMENTAZIONE
│   ├── COMPLETE_TECHNICAL_SPECIFICATION.md
│   ├── QUEST_CHOICE_SYSTEM.md
│   ├── WORLD_CREATION_GUIDE.md
│   └── ...
│
├── tests/                       # TEST SUITE
├── .env                         # Variabili ambiente
└── pyproject.toml              # Dipendenze Poetry
```

---

## PARTE III: DATA MODELS - IL "DNA" DEL SISTEMA

### 3.1 Filosofia dei Modelli

Tutti i dati in Luna RPG sono **immutabili e validati**. Questo significa:
- Non puoi creare un GameState invalido
- I campi hanno tipi precisi (int, str, enum)
- Le relazioni sono esplicite (dict, list)

### 3.2 GameState - Lo Stato dell'Universo

Il `GameState` è il contenitore supremo. Rappresenta l'intero universo di gioco in un singolo oggetto.

**Concettualmente:**
- Se salvi un GameState su file, hai salvato TUTTO
- Se carichi un GameState, ripristini l'esatto momento di gioco
- Ogni campo rappresenta un aspetto del mondo

**Tecnicamente:**
```python
class GameState(LunaBaseModel):
    # Identità
    session_id: Optional[int] = None  # ID database
    world_id: str                      # Quale mondo (school, fantasy...)
    
    # Tempo e Spazio
    turn_count: int = 0               # Quanti "respiri" di gioco
    time_of_day: TimeOfDay            # Morning/Afternoon/Evening/Night
    current_location: str             # Dove siamo fisicamente
    
    # Chi siamo
    active_companion: str             # Con chi stiamo parlando ORA
    companion_outfits: Dict[str, OutfitState]  # Cosa indossa ognuno
    
    # Relazioni
    affinity: Dict[str, int]          # Quanto ci piace ogni companion (0-100)
    
    # Progresso
    active_quests: List[str]          # Quest in corso
    completed_quests: List[str]       # Quest finite
    flags: Dict[str, Any]             # Flags generici (chiave-valore)
    
    # Player
    player: PlayerState               # Stats, inventario, oro
    npc_states: Dict[str, NPCState]   # Stato di ogni NPC
```

**Esempio pratico:**
```python
# Turn 0: Inizio gioco
state = GameState(
    world_id="school",
    active_companion="luna",
    current_location="school_entrance",
    time_of_day=TimeOfDay.MORNING,
    turn_count=0,
    affinity={"luna": 0, "stella": 0},
    companion_outfits={
        "luna": OutfitState(style="teacher_suit", ...),
        "stella": OutfitState(style="casual", ...)
    }
)

# Turn 10: Dopo alcune interazioni
state.turn_count = 10
state.affinity["luna"] = 35  # Siamo più amici
state.current_location = "school_library"
state.companion_outfits["luna"].components["shoes"] = "barefoot"  # Si è tolta le scarpe
```

### 3.3 OutfitState - La Rivoluzione dei Vestiti

**Problema che risolve:** In un gioco con immagini, l'outfit deve essere:
- Descritto all'AI per il testo
- Tradotto in prompt per Stable Diffusion
- Modificabile pezzo per pezzo (togliere solo le scarpe)
- Persistente tra i turni

**Soluzione - Componenti:**
```python
class OutfitState:
    style: str = "default"           # Chiave nel wardrobe (es. "casual")
    description: str = ""            # Descrizione testuale completa
    components: Dict[str, str] = {}  # Componenti individuali
    
# Esempio: Luna inizia con completo
outfit = OutfitState(
    style="teacher_suit",
    components={
        "top": "white button-up blouse",
        "bottom": "charcoal grey pencil skirt",
        "shoes": "black high heels",
        "outerwear": "navy blazer"
    }
)

# Player scrive: "Luna si toglie le scarpe"
# Sistema modifica SOLO il componente shoes:
outfit.components["shoes"] = "barefoot"

# Il prompt SD diventa:
# "wearing white button-up blouse, charcoal grey pencil skirt, barefoot, navy blazer"
```

**Modifiche Speciali:**
```python
# Stati speciali (asciugamano, grembiule...) sovrascrivono tutto
outfit.is_special = True
outfit.components = {"special": "towel", "shoes": "barefoot"}
outfit.description = "fresh out of shower, wearing only a towel"
```

### 3.4 CompanionDefinition - L'Anima dei Personaggi

Ogni companion è definito in YAML e caricato in questo modello.

**Concettualmente:**
- È la "fiche" del personaggio
- Contiene tutto ciò che lo rende unico
- Include istruzioni per l'AI su come interpretarlo

**Struttura:**
```python
class CompanionDefinition:
    # Identità
    name: str = "Luna"
    role: str = "Teacher"
    age: int = 32
    base_personality: str = "strict but caring..."
    
    # Visual Identity (per Stable Diffusion)
    base_prompt: str = "stsdebbie, 1girl, mature woman..."
    physical_description: str = "brown hair, green eyes..."
    
    # Wardrobe - Il Guardaroba
    wardrobe: Dict[str, WardrobeDefinition] = {
        "teacher_suit": WardrobeDefinition(
            description="professional outfit...",
            sd_prompt="charcoal grey pencil skirt..."
        ),
        "casual": WardrobeDefinition(...),
        "evening_gown": WardrobeDefinition(...)
    }
    
    # Schedule - Dove si trova durante il giorno
    schedule: Dict[TimeOfDay, ScheduleEntry] = {
        TimeOfDay.MORNING: ScheduleEntry(
            location="school_office",
            activity="preparing lessons",
            outfit="teacher_suit"
        ),
        TimeOfDay.AFTERNOON: ScheduleEntry(
            location="school_classroom",
            activity="teaching",
            outfit="teacher_suit"
        )
    }
    
    # Emotional States
    emotional_states: Dict[str, EmotionalStateDefinition] = {
        "default": EmotionalStateDefinition(...),
        "flustered": EmotionalStateDefinition(...),
        "angry": EmotionalStateDefinition(...)
    }
    
    # Affinity Tiers - Come si comporta in base all'affinità
    affinity_tiers: Dict[str, Dict] = {
        "stranger": {"range": [0, 25], "behavior": "formal"},
        "friend": {"range": [51, 75], "behavior": "warm"},
        "lover": {"range": [76, 100], "behavior": "romantic"}
    }
    
    # Quests - Missioni associate
    quests: Dict[str, QuestDefinition] = {
        "luna_private_lesson": QuestDefinition(...)
    }
    
    # Aliases - Nomi alternativi per riconoscimento
    aliases: List[str] = ["professoressa", "prof", "miss luna"]
```

### 3.5 QuestDefinition - Le Storie Dentro la Storia

Le quest sono sotto-storie con stato e progresso.

**Anatomia di una Quest:**
```python
class QuestDefinition:
    # Metadati
    id: str = "luna_private_lesson"
    title: str = "Private Lesson"
    description: str = "Luna offers to help you after class..."
    
    # Attivazione - Come inizia?
    activation_type: "auto" | "manual" | "trigger" | "choice"
    
    # Se "auto": si attiva quando condizioni soddisfatte
    activation_conditions: [
        QuestCondition(type="affinity", target="luna", operator="gte", value=60),
        QuestCondition(type="location", value="school_library")
    ]
    
    # Se "choice": richiede conferma player
    requires_player_choice: True
    choice_title: "A Special Offer"
    choice_description: "Luna looks at you... 'Want help after class?'"
    
    # Stages - Fasi della quest
    stages: {
        "start": QuestStage(
            title="The Lesson",
            narrative_prompt="Luna is waiting at her desk...",
            on_enter=[QuestAction(action="set_location", target="school_library")],
            exit_conditions=[
                QuestCondition(type="action", pattern="study|learn")
            ]
        ),
        "romantic_moment": QuestStage(...),
        "completion": QuestStage(...)
    }
```

### 3.6 LLMResponse - La Voce dell'AI

Quando l'AI risponde, lo fa con questa struttura:

```python
class LLMResponse:
    # Testo narrativo (italiano)
    text: str = "Luna ti sorride dolcemente..."
    
    # Descrizione visiva (inglese, per SD)
    visual_en: str = "Luna smiling gently, sitting behind wooden desk..."
    
    # Tag per migliorare qualità immagine
    tags_en: ["masterpiece", "detailed", "soft lighting"]
    
    # Cambiamenti di stato proposti
    updates: StateUpdate(
        affinity_change={"luna": 2},
        outfit_update=OutfitUpdate(modify_components={"shoes": "barefoot"}),
        set_flags={"luna_flustered": True}
    )
```

---

## PARTE IV: CORE SYSTEMS - I MOTORI DEL GIOCO

### 4.1 GameEngine - Il Direttore d'Orchestra

**Metafora:** Il GameEngine è come un direttore d'orchestra. Non suona alcuno strumento, ma coordina tutti i musicisti (sistemi) per creare l'armonia (esperienza di gioco).

**V4.3 REFACTORING:** La logica del game loop è stata estratta in `TurnOrchestrator` per migliorare modularità e testabilità. Il GameEngine mantiene il ruolo di coordinatore ma delega l'esecuzione del turno.

**Responsabilità:**
1. Tenere riferimenti a TUTTI i sistemi
2. Inizializzare e coordinare i sottosistemi
3. Fornire API pulite alla UI
4. Delegare l'esecuzione del turno a `TurnOrchestrator`

**Architettura V4.3 (Modulare):**
```python
class GameEngine:
    # Dati
    world: WorldDefinition          # Il mondo "statico" (definizioni)
    state_manager: StateManager     # Il mondo "dinamico" (stato runtime)
    
    # Sistemi di Gameplay
    quest_engine: QuestEngine
    personality_engine: PersonalityEngine
    location_manager: LocationManager
    outfit_modifier: OutfitModifier
    affinity_calculator: AffinityCalculator
    
    # Sistemi AI/Media
    llm_manager: LLMManager
    media_pipeline: MediaPipeline
    prompt_builder: PromptBuilder
    
    # Sistemi Narrativi
    story_director: StoryDirector
    memory_manager: MemoryManager
    multi_npc_manager: MultiNPCManager
    
    # V4.3: Modular Components (refactored from engine.py)
    turn_orchestrator: TurnOrchestrator      # Main turn flow coordinator
    npc_detector: NPCDetector                # NPC/companion detection
    input_preprocessor: InputPreprocessor    # Input parsing & commands
    response_processor: ResponseProcessor    # LLM validation & retry
    state_updater: StateUpdater              # Game state updates
    media_coordinator: MediaCoordinator      # Media generation coordination
```

**Flusso V4.3 (Delegato):**
```python
# UI chiama:
result = await engine.process_turn("Ciao Luna!")

# GameEngine delega a TurnOrchestrator:
async def process_turn(self, user_input):
    # 1. Skip check preliminare
    if not user_input or not user_input.strip():
        return TurnResult(text="[Nessun input ricevuto]", ...)
    
    # 2. Delega completa a TurnOrchestrator
    return await self.turn_orchestrator.execute_turn(user_input)

# TurnOrchestrator esegue i 10 step:
async def execute_turn(self, user_input):
    # Step 0: Event checking, Movement, Commands
    preprocess_result = await self._step_preprocess(user_input, game_state)
    
    # Step 1-2: Companion switching
    switched, is_temp = await self._step_companion_switch(user_input, game_state)
    
    # Step 3: Build prompt
    system_prompt = self._step_build_prompt(game_state, ...)
    
    # Step 4-5: LLM Generation with retry
    llm_response, provider = await self._step_generate_llm(system_prompt, ...)
    
    # Step 6-7: Update state
    updates = self._step_update_state(game_state, llm_response)
    
    # Step 8: Media generation (async)
    media_result = await self._step_generate_media(game_state, llm_response)
    
    # Step 9: Save state
    await self._step_save_memory(game_state, user_input, llm_response)
    
    # Step 10: Build result
    return self._step_build_result(game_state, llm_response, media_result, ...)
```

**Vantaggi del Refactoring V4.3:**
- **Separazione dei Concerni:** Ogni componente ha una responsabilità unica
- **Testabilità:** I componenti possono essere testati isolatamente
- **Manutenibilità:** Modifiche localizzate senza impatto sull'engine principale
- **Code Reduction:** Engine.py ridotto da ~3100 a ~1600 righe

**Componenti Refactored (V4.3):**

| Componente | File | Righe | Responsabilità |
|------------|------|-------|----------------|
| TurnOrchestrator | `systems/turn_orchestrator.py` | ~950 | Coordinamento 10-step turn |
| NPCDetector | `systems/npc_detector.py` | ~220 | Detection companion/NPC con word boundaries |
| InputPreprocessor | `systems/input_preprocessor.py` | ~260 | Parsing input, command handling |
| ResponseProcessor | `systems/response_processor.py` | ~200 | LLM validation, retry logic |
| StateUpdater | `systems/state_updater.py` | ~250 | Game state updates |
| MediaCoordinator | `systems/media_coordinator.py` | ~260 | Media generation coordination |

### 4.2 StateManager - Il Guardiano del Tempo

**Metafora:** Lo StateManager è come un TARDIS (Doctor Who). Contiene l'intero universo in un oggetto compatto e può "viaggiare nel tempo" salvando e caricando stati.

**Caratteristiche:**
- **Single Source of Truth:** Solo lui può modificare il GameState
- **Validazione:** Ogni modifica è validata prima di essere applicata
- **Persistenza:** Salva automaticamente su database
- **History:** Tiene traccia dei cambiamenti

**API:**
```python
class StateManager:
    @property
    def current(self) -> GameState:
        """Accesso allo stato corrente."""
        
    @property  
    def is_loaded(self) -> bool:  # NOTA: è proprietà, non metodo!
        """C'è un gioco caricato?"""
        
    def advance_turn(self) -> None:
        """Incrementa turn_count di 1."""
        
    def change_affinity(self, character: str, delta: int) -> None:
        """Modifica affinità (con clamp 0-100)."""
        
    def set_location(self, location_id: str) -> None:
        """Cambia location corrente."""
        
    def set_outfit(self, outfit: OutfitState, companion: str) -> None:
        """Aggiorna outfit di un companion."""
        
    async def save(self, db) -> bool:
        """Serializza e salva su database."""
        
    async def load(self, db, session_id: int) -> GameState:
        """Carica stato da database."""
```

### 4.3 AffinityCalculator - Il Giudice Imparziale (NUOVO)

**Problema risolto:** Prima l'LLM decideva i cambi di affinità, ma era inconsistente. Ora un sistema deterministico basato su regex calcola i valori.

**Filosofia:** L'affinità cambia in base a COSA dici, non a COME lo interpreta l'AI.

**Sistema a Tier:**
```python
class AffinityCalculator:
    # Pattern positivi (dal più debole al più forte)
    POSITIVE_PATTERNS = {
        # +1: Educazione di base
        "greeting": (r"\b(ciao|salve|buongiorno)\b", 1),
        "thanks": (r"\b(grazie|ti ringrazio)\b", 1),
        "polite": (r"\b(per favore|scusa)\b", 1),
        
        # +2: Amichevolezza
        "compliment_appearance": (r"\b(bella|carina|elegante)\b", 2),
        "compliment_personality": (r"\b(brava|dolce|gentile)\b", 2),
        "interest": (r"\b(mi piaci|sei speciale)\b", 2),
        
        # +3: Romantico
        "romantic": (r"\b(sei bellissima|ti bacio|mi attrai)\b", 3),
        "flirty": (r"\b(sexy|desidero|sensuale)\b", 3),
        
        # +4: Emotivo profondo
        "love": (r"\b(ti amo|mi fido|insieme per sempre)\b", 4),
        "vulnerable": (r"\b(solo con te|mi confido|mi capisci)\b", 4),
        
        # +5: Eccezionale
        "marriage": (r"\b(sposami|moglie|futuro insieme)\b", 5),
    }
    
    # Pattern negativi (speculari)
    NEGATIVE_PATTERNS = {
        # -1: Fastidio
        "impatient": (r"\b(sbrigati|muoviti|non ho tempo)\b", -1),
        
        # -2: Scortesia
        "rude": (r"\b(stupida|idiota|zitta|obbedisci)\b", -2),
        
        # -3: Cattiveria
        "mean": (r"\b(brutta|inutile|patetica)\b", -3),
        
        # -4: Ostilità
        "hostile": (r"\b(ammazzo|uccido|odio|puttana)\b", -4),
        
        # -5: Violenza
        "violent": (r"\b(violento|stupro|tortura)\b", -5),
    }
```

**Bonus Sistema:**
- **Streak Bonus:** +1 ogni 3 interazioni positive consecutive (ricompensa consistenza)
- **Time Bonus:** +1 ogni 5 turni con lo stesso companion (ricompensa dedizione)

**Esempio:**
```python
# Input: "Ciao Luna, sei bellissima oggi!"
calculator.calculate("Ciao Luna, sei bellissima oggi!", "luna", turn=5)
# Risultato:
# - "ciao" → +1 (greeting)
# - "sei bellissima" → +3 (romantic)
# - Totale: +4 (clamped a max +5)
# - Bonus: +0 (prima interazione)
# - Finale: +4 affinità
```

---

### 4.4 Phase System V4.2 - Il Tempo che Scorre (NUOVO)

**Problema:** Il tempo deve avanzare in modo significativo, con NPC che seguono routine giornaliere e il mondo che cambia.

**Soluzione:** Sistema a fasi con 8 turni per periodo.

#### Concetti Chiave

**Le 4 Fasi:**
- **Mattina** (8 turni) → Pomeriggio → Sera → Notte → (ciclo)
- 32 turni totali = 1 giorno completo

**Cosa succede al cambio fase:**
1. Il tempo avanza (Morning → Afternoon)
2. Gli NPC si spostano secondo la loro schedule
3. Se il companion del player se ne va → auto-switch a "solo"
4. Viene generata una nuova immagine della location (vuota)

**Freeze System:**
Il player può bloccare il conteggio turni con comandi come "pausa" o "freeze". Utile per scene romantiche o importanti dove non si vuole che il tempo scada.

#### NPC Schedules

Ogni NPC ha una routine giornaliera che definisce:
- **Location**: Dove si trova in ogni fascia oraria
- **Activity**: Cosa sta facendo (contesto per LLM)
- **Outfit**: Abbigliamento consigliato per quella fase

**Esempio - Kara (Sciamana):**
```yaml
npc_schedules:
  Kara:
    morning:
      location: "caverna"
      activity: "Prepara pozioni mistiche"
      outfit: "ritual_paint"
    afternoon:
      location: "villaggio"
      activity: "Dice il futuro ai tribù"
      outfit: "ritual_paint"
```

#### Componenti

**PhaseManager:**
- Gestisce il conteggio turni per fase
- Esegue il cambio fase quando necessario
- Gestisce il freeze/unfreeze

**ScheduleManager:**
- Carica schedule da YAML o genera default
- Risolve location NPC per time of day
- Trova NPC presenti in una location

#### Flusso Cambio Fase

```
Turno 8/8 Mattina
    ↓
PhaseManager.on_turn_end() → PhaseChangeResult
    ↓
1. Avanza tempo: Morning → Afternoon
2. Sposta NPC: Kara(caverna→villaggio), Naya(giungla→giungla)
3. Verifica: Kara era con player? Sì → companion_left=True
4. Switch companion: "Kara" → "_solo_"
5. Genera messaggio: "🌅 Il sole sale più alto... è pomeriggio."
6. UI riceve: needs_location_refresh=True
7. UI genera: immagine location vuota (senza Kara)
```

#### Integrazione con Altri Sistemi

| Sistema | Interazione |
|---------|-------------|
| Quest | Deadline funzionano indipendentemente |
| Events | Eventi globali attivati ogni turno |
| Movement | Quando player entra, auto-switch a NPC presente |
| Media | Genera immagine location vuota quando companion lascia |

---

## PARTE V: AI INTEGRATION - IL CERVELLO

### 5.1 Architettura LLM - Multi-Provider con Fallback

**Problema:** Gli LLM possono fallire (rate limit, downtime). Serve un sistema robusto.

**Soluzione:** Chain of Responsibility con fallback automatico.

**Flusso:**
```
Player Input
    ↓
LLMManager.generate()
    ↓
┌─────────────────────────────────────┐
│ 1. Prova Gemini (primario)          │
│    ├─ Successo → Ritorna risposta   │
│    └─ Fallimento → Passa a fallback │
↓                                     │
│ 2. Prova Moonshot (fallback)        │
│    ├─ Successo → Ritorna risposta   │
│    └─ Fallimento → Ritorna errore   │
└─────────────────────────────────────┘
```

### 5.2 Il System Prompt - Il Copione dell'AI

L'AI non "conosce" il gioco. Gli viene fornito un copione completo ad ogni turno.

**Struttura del Prompt:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYSTEM PROMPT                                 │
├─────────────────────────────────────────────────────────────────┤
│ 1. WORLD CONTEXT                                                │
│    Premessa del mondo, temi, situazione attuale                 │
│    Es: "Sei in una scuola superiore. È l'ora di pranzo..."      │
├─────────────────────────────────────────────────────────────────┤
│ 2. LOCATION                                                     │
│    Descrizione dettagliata della location corrente              │
│    Es: "Sei in biblioteca. Scaffali pieni di libri..."          │
├─────────────────────────────────────────────────────────────────┤
│ 3. TIME                                                         │
│    Ora del giorno e atmosfera                                   │
│    Es: "Afternoon - Luce dorata che entra dalle finestre"       │
├─────────────────────────────────────────────────────────────────┤
│ 4. ACTIVE COMPANION                                             │
│    Chi è il personaggio con cui si interagisce                │
│    - Nome, ruolo, età                                          │
│    - Personalità base                                          │
│    - Base prompt (LoRA triggers per immagine)                  │
│    - Outfit attuale (dal wardrobe)                             │
│    - Stato emotivo corrente                                    │
├─────────────────────────────────────────────────────────────────┤
│ 5. PLAYER CONTEXT                                               │
│    Stats del giocatore, inventario, oro                        │
├─────────────────────────────────────────────────────────────────┤
│ 6. PERSONALITY PROFILE                                          │
│    Archetipo rilevato (Gentle, Dominant, Romantic...)          │
│    Impressione corrente del companion sul player               │
│    Es: "Luna ti trova gentile e romantico (trust: +30)"        │
├─────────────────────────────────────────────────────────────────┤
│ 7. MEMORY                                                       │
│    Ultime 20 messaggi della conversazione                      │
│    Fatti importanti ricordati (semantic search)                │
│    Es: "Ricorda: Player ha confessato di amare il caffè"       │
├─────────────────────────────────────────────────────────────────┤
│ 8. ACTIVE QUESTS                                                │
│    Quest in corso e loro narrative_prompt                      │
│    Es: "Quest 'Private Lesson': Luna ti sta insegnando..."     │
├─────────────────────────────────────────────────────────────────┤
│ 9. STORY CONTEXT                                                │
│    Story beat attivo (se presente)                             │
│    Evento globale attivo                                       │
├─────────────────────────────────────────────────────────────────┤
│ 10. NARRATIVE GUIDELINES                                        │
│    - Rispondi in italiano                                      │
│    - Non ripetere l'input del player                           │
│    - Descrivi outfit e location dettagliatamente               │
│    - Genera descrizione visiva in inglese                      │
├─────────────────────────────────────────────────────────────────┤
│ 11. RESPONSE FORMAT (JSON Schema)                               │
│    Schema preciso che l'AI deve seguire                        │
│    Include: text, visual_en, tags_en, updates...               │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 JSON Repair - L'Assicurazione Qualità

**Problema:** L'AI a volte genera JSON malformato:
- Virgole extra alla fine
- Chiavi non quotate
- Single quotes invece di double
- Markdown code blocks attorno

**Soluzione:** Pipeline di repair automatico:
```python
class JSONRepair:
    def repair(self, text: str) -> str:
        # Step 1: Estrai da markdown ```json ... ```
        text = extract_from_markdown(text)
        
        # Step 2: Rimuovi trailing commas
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        
        # Step 3: Aggiungi virgole mancanti tra proprietà
        text = re.sub(r'}\s*{', '},{', text)
        
        # Step 4: Converte single quotes → double
        text = text.replace("'", '"')
        
        # Step 5: Quota chiavi non quotate
        text = re.sub(r'(\w+):', r'"\1":', text)
        
        # Step 6: Escape newlines in stringhe
        text = text.replace('\n', '\\n')
        
        return text
```

---

## PARTE VI: MEDIA GENERATION - GLI OCCHI

### 6.1 Filosofia delle Immagini

**Principio:** Ogni scena descritta dall'AI deve avere un'immagine corrispondente.

**Sfide:**
1. **Consistenza del Personaggio:** Luna deve sempre somigliare a Luna
2. **Consistenza dell'Outfit:** Se si è tolta le scarpe, l'immagine deve mostrarla scalza
3. **Qualità:** Immagini dettagliate e atmosferiche
4. **Velocità:** Generazione in background senza bloccare l'UI

**Soluzione:**
```
Consistenza Personaggio → LoRA + Trigger words fissi
Consistenza Outfit → Wardrobe description sovrascritta
Qualità → Prompt engineering con quality tags
Velocità → Async generation + placeholder
```

### 6.2 ImagePromptBuilder - L'Architetto delle Immagini

Prende la descrizione dell'AI e la trasforma in un prompt ottimizzato per Stable Diffusion.

**Input:**
```python
{
    "companion_def": Luna,
    "visual_en": "Luna smiling, sitting behind desk",
    "tags_en": ["soft lighting", "classroom"],
    "outfit": OutfitState(components={...})
}
```

**Output:**
```
Positive:
score_9, score_8_up, masterpiece, photorealistic, detailed, 
stsdebbie, 1girl, mature woman, brown hair, green eyes, 
wearing professional teacher outfit, charcoal grey pencil skirt, 
crisp white button-up blouse, sheer black pantyhose, 
Luna smiling, sitting behind desk, soft lighting, classroom

Negative:
(deformed, distorted, disfigured:1.3), poor quality, 
bad anatomy, ugly, text, watermark, blurry...

Parameters:
width: 896, height: 1152, steps: 24, seed: random
```

**Note tecniche:**
- `score_9, score_8_up` sono tag Pony Diffusion per qualità
- `stsdebbie` è il trigger word della LoRA di Luna
- I componenti outfit sono sempre inclusi per consistenza

### 6.3 ComfyUI Client - Il Generatore

**Architettura:**
```
Workflow JSON (comfy_workflow.json)
    ↓
Modifica nodi con parametri
    ↓
Invio via WebSocket a ComfyUI
    ↓
ComfyUI esegue pipeline
    ↓
Ricezione immagine
    ↓
Salvataggio in storage/images/
```

**Nodi principali nel workflow:**
1. `CheckpointLoaderSimple` - Carica modello SDXL
2. `LoraLoader` - Carica LoRA personaggio (2-3 LoRA)
3. `CLIPTextEncode` - Encode prompt positivo/negativo
4. `KSampler` - Generazione immagine
5. `VAEDecode` - Decodifica latente
6. `SaveImage` - Salvataggio

### 6.4 Video Generation - Il Movimento

**Modello:** Wan2.1 I2V (Image-to-Video)

**Processo:**
1. Upload immagine base a RunPod
2. ComfyUI workflow video:
   - `WanImageToVideo`: Genera 81 frame
   - `RIFE VFI`: Interpola a 162 frame (2x)
   - `VHS_VideoCombine`: Esporta MP4
3. Download video ~10 secondi

**Parametri:**
- Risoluzione: 480x896 (portrait)
- FPS: 16
- Frame: 162 (da 81 generati)
- Motion speed: 6/10

---

## PARTE VII: QUEST SYSTEM - LE AVVENTURE

### 7.1 Concetto di Quest in Luna RPG

Una quest non è semplicemente "vai a prendi X". È una micro-storia con:
- **Attivazione:** Condizioni che la fanno iniziare
- **Stadi:** Fasi progressive della storia
- **Scelte:** Il player influenza l'evoluzione
- **Ricompense:** Affinità, item, sblocchi

### 7.2 Tipi di Attivazione

1. **Auto:** Si attiva automaticamente quando le condizioni sono soddisfatte
   ```yaml
   activation_type: "auto"
   activation_conditions:
     - type: affinity
       value: 50
   ```

2. **Trigger:** Si attiva quando un flag specifico viene settato
   ```yaml
   activation_type: "trigger"
   trigger_event: "luna_confession"
   ```

3. **Choice (NUOVO):** Richiede scelta esplicita del player via UI
   ```yaml
   activation_type: "choice"
   requires_player_choice: true
   choice_title: "Un'Opportunità Speciale"
   choice_description: "Luna ti offre aiuto..."
   ```

### 7.3 Ciclo di Vita di una Quest

```
NOT_STARTED
    ↓ (check_activations trova condizioni soddisfatte)
PENDING_CHOICE (se type="choice") → [Player sceglie] → ACTIVE
    ↓ (se type="auto")
ACTIVE
    ↓ (exit_conditions soddisfatte)
COMPLETED / FAILED
```

### 7.4 Esempio Completo: "Private Lesson"

```yaml
# Definizione YAML
quests:
  luna_private_lesson:
    id: "luna_private_lesson"
    title: "Lezione Privata"
    description: "Luna ti aiuta con i compiti dopo scuola"
    character: "luna"
    
    # Attivazione con scelta
    activation_type: "choice"
    requires_player_choice: true
    choice_title: "Un'Offerta Speciale"
    choice_description: |
      Luna ti guarda con un sorriso. 
      "Hai difficoltà con matematica? 
       Posso aiutarti dopo scuola... solo noi due."
    accept_button_text: "Sì, grazie!"
    decline_button_text: "No, grazie"
    
    # Condizioni per apparire
    activation_conditions:
      - type: affinity
        target: luna
        operator: gte
        value: 60
      - type: location
        value: school_classroom
    
    # Fasi della quest
    stages:
      # Fase 1: Inizio
      start:
        title: "La Lezione"
        narrative_prompt: |
          Luna è seduta alla cattedra. 
          I libri di matematica sono sparsi sul banco.
          "Cominciamo?" chiede con voce dolce.
        
        # Azioni all'ingresso
        on_enter:
          - action: set_location
            target: school_classroom
          - action: set_emotional_state
            character: luna
            value: focused
        
        # Come uscire da questa fase
        exit_conditions:
          - type: action
            pattern: "study|learn|ask|question"
            # Player deve chiedere/studiare
        
        # Transizioni
        transitions:
          - condition: "action_matched"
            target_stage: "romantic_moment"
      
      # Fase 2: Svolta romantica
      romantic_moment:
        title: "Un Momento di Intimità"
        narrative_prompt: |
          Mentre spieghi, le vostre mani si toccano.
          Luna arrossisce e distoglie lo sguardo.
          "Scusa..." mormora, "mi sono distatta."
        
        on_enter:
          - action: set_emotional_state
            character: luna
            value: flustered
        
        exit_conditions:
          - type: action
            pattern: "comfort|reassure|flirt"
        
        transitions:
          - condition: "action_matched"
            target_stage: "completion"
      
      # Fase finale
      completion:
        title: "Successo!"
        narrative_prompt: |
          "Grazie per l'aiuto," dici.
          Luna ti sorride. "È stato un piacere.
          Possiamo farlo di nuovo... quando vuoi."
        
        on_enter:
          - action: change_affinity
            character: luna
            value: 15
          - action: complete_quest
            quest_id: "luna_private_lesson"
        
        # Ricompense
        rewards:
          affinity:
            luna: 15
          flags:
            luna_lesson_completed: true
```

---

## PARTE VIII: UI LAYER - L'INTERFACCIA

### 8.1 Layout della MainWindow

```
┌──────────────────────────────────────────────────────────────────────────┐
│  🔊 Audio  ☀️ Time  👤 Luna  🎮 New  💾 Save  📂 Load  ⚙️ Settings       │
├───────────────┬──────────────────────────┬────────────────────────────────┤
│               │                          │                                │
│   LEFT PANEL  │      CENTER PANEL        │        RIGHT PANEL             │
│    220px      │        550px             │          630px                 │
│               │                          │                                │
│ ┌───────────┐ │   ┌──────────────────┐   │  ┌──────────┬──────────────┐  │
│ │Personality│ │   │                  │   │  │ Quest    │ Companion    │  │
│ │ Profile   │ │   │   IMAGE          │   │  │ Tracker  │ Status       │  │
│ │           │ │   │   DISPLAY        │   │  │          │              │  │
│ ├───────────┤ │   │                  │   │  ├──────────┼──────────────┤  │
│ │  Global   │ │   │   (ComfyUI       │   │  │ Companion│ Story Log    │  │
│ │  Event    │ │   │    Output)       │   │  │ Locator  │              │  │
│ ├───────────┤ │   │                  │   │  └──────────┴──────────────┘  │
│ │ Location  │ │   └──────────────────┘   │  ┌──────────────────────────┐  │
│ │ Widget    │ │                          │  │ [Scrivi messaggio...   ] │  │
│ ├───────────┤ │                          │  │              [▶ Invia]   │  │
│ │  Outfit   │ │                          │  └──────────────────────────┘  │
│ │  Widget   │ │                          │                                │
│ └───────────┘ │                          │                                │
├───────────────┴──────────────────────────┴────────────────────────────────┤
│ Ready                    🎲 Turn: 5          📍 School Library            │
└──────────────────────────────────────────────────────────────────────────┘
```

### 8.2 Widgets Principali

**1. QuestTrackerWidget**
```
┌─ 📋 Quest ───────────────┐
│ 🟢 Private Lesson         │
│   Luna ti aspetta...      │
│                           │
│ ⚪ Unresolved Tension     │
│   (Sblocca a 75 affinità) │
└───────────────────────────┘
```

**2. CompanionStatusWidget**
```
┌─ 👥 Companions ──────────┐
│ Luna                      │
│ ████████████░░ 45/100     │
│ ❤️ Friendly              │
│                           │
│ Stella                    │
│ ████░░░░░░░░░░ 12/100     │
│ 💙 Stranger              │
└───────────────────────────┘
```

**3. CompanionLocatorWidget**
```
┌─ 📍 Where are they? ─────┐
│ Luna: Library (studying) ✅│
│ Stella: Gym area 🔒       │
│ Kara: Unknown 🔒          │
└───────────────────────────┘
```

**4. QuestChoiceWidget (Overlay)**
```
┌─────────────────────────────────────┐
│  🎯 Un'Offerta Speciale             │
│  ─────────────────────────────────  │
│  Luna ti guarda con un sorriso...   │
│  "Posso aiutarti dopo scuola?"      │
│                                     │
│  [✅ Sì, grazie!]      Verde       │
│  [❌ No, grazie]       Rosso       │
│  [❓ Dimmi di più]     Blu         │
│                                     │
│  [Annulla]                          │
└─────────────────────────────────────┘
⛔ Input bloccato finché non scegli
```

### 8.3 Feedback Visualizer

Sistema di notifiche toast che appaiono in basso a destra:

```
┌─────────────────────────┐  ← Appare e scompare
│  ❤️ +2 Affinity         │     dopo 3 secondi
│  Luna likes you more!   │
└─────────────────────────┘

┌─────────────────────────┐
│  📜 Quest Started       │
│  Private Lesson         │
└─────────────────────────┘

┌─────────────────────────┐
│  💾 Salvato             │
│  Partita salvata (ID: 5)│
└─────────────────────────┘
```

---

## PARTE IX: DATABASE & PERSISTENCE

### 9.1 Filosofia della Persistenza

**Principio:** Il giocatore deve poter chiudere e riaprire il gioco trovando ESATTAMENTE la stessa situazione.

**Cosa viene salvato:**
- Tutto il GameState
- Storia conversazioni completa
- Memoria fatti estratti
- Stato di TUTTE le quest

### 9.2 Schema Database

```sql
-- Tabella principale: sessioni
game_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    world_id TEXT NOT NULL,           -- 'school', 'prehistoric_tribe'
    companion TEXT NOT NULL,          -- Companione iniziale
    created_at TIMESTAMP,             -- Quando iniziata
    updated_at TIMESTAMP              -- Ultimo salvataggio
)

-- Stato completo (JSON serializzato)
game_states (
    session_id INTEGER PRIMARY KEY,
    turn_count INTEGER DEFAULT 0,
    time_of_day TEXT,                 -- 'Morning', 'Afternoon'...
    current_location TEXT,
    active_companion TEXT,
    state_json TEXT                   -- GameState completo come JSON
)

-- Affinità (per querying/reporting)
affinity (
    session_id INTEGER,
    character TEXT,
    value INTEGER,
    PRIMARY KEY (session_id, character)
)

-- Quest (stato runtime)
quest_states (
    session_id INTEGER,
    quest_id TEXT,
    status TEXT,                      -- 'active', 'completed', 'failed'
    current_stage TEXT,               -- Stage corrente
    started_at INTEGER,               -- Turno inizio
    completed_at INTEGER              -- Turno fine (se completata)
)

-- Memoria conversazioni
conversation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    role TEXT,                        -- 'user', 'assistant', 'system'
    content TEXT,                     -- Testo messaggio
    turn_number INTEGER,
    visual_en TEXT,                   -- Descrizione visiva
    tags_en TEXT                      -- Tag SD
)

-- Fatti ricordati
memory_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    content TEXT,                     -- "Player ama il caffè"
    importance INTEGER,               -- 1-10
    turn_number INTEGER,
    associated_npc TEXT               -- A chi riguarda
)
```

### 9.3 Processo di Salvataggio

```python
async def save_game(self):
    # 1. Serializza GameState
    state_json = game_state.model_dump_json()
    
    # 2. Salva stato principale
    await db.execute(
        "INSERT OR REPLACE INTO game_states VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, turn_count, time, location, companion, state_json)
    )
    
    # 3. Salva affinità (per querying)
    for char, value in game_state.affinity.items():
        await db.execute(
            "INSERT OR REPLACE INTO affinity VALUES (?, ?, ?)",
            (session_id, char, value)
        )
    
    # 4. Salva quest
    for quest_id, instance in quest_states.items():
        await db.execute(
            "INSERT OR REPLACE INTO quest_states VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, quest_id, instance.status, 
             instance.current_stage_id, instance.started_at, 
             instance.completed_at)
        )
    
    # 5. Commit
    await db.commit()
```

---

## PARTE X: ESEMPIO COMPLETO - FLUSSO TURN

### 10.1 Scenario

**Situazione iniziale:**
- Turno: 5
- Location: School Library
- Companion: Luna
- Affinità con Luna: 45/100 (Friendly)
- Outfit Luna: Teacher suit, ma si è tolta le scarpe
- Quest attiva: "Private Lesson" (stage: start)

**Input player:** "Luna, mi piaci molto. Vuoi uscire con me?"

### 10.2 Esecuzione Passo-Passo

**STEP 1: Personality Analysis**
```python
# AffinityCalculator analizza input
patterns_found = [
    ("mi piaci", "friendly", +2),
    ("molto", "intensifier", 0),
    ("vuoi uscire", "romantic", +3)
]
total_delta = +5 (max raggiunto)

# PersonalityEngine analizza comportamento
behaviors = [ROMANTIC, CONFIDENT]
```

**STEP 2: StoryDirector**
```python
# Nessun beat attivo per queste condizioni
story_context = ""
```

**STEP 3: Quest Engine**
```python
# Controlla se quest "Private Lesson" progredisce
quest = quest_engine.get_active_quest("luna_private_lesson")
current_stage = quest.stages["start"]

# Valuta exit_conditions
# Condition: type="action", pattern="study|learn|ask"
# Input: "mi piaci molto..." → NON matcha
# Quest NON progredisce
```

**STEP 4: System Prompt Building**
```python
prompt = """
=== WORLD CONTEXT ===
School setting, slice of life visual novel...

=== LOCATION ===
School Library - Quiet, bookshelves, afternoon light...

=== ACTIVE COMPANION ===
Luna, 32, Teacher
Base: stsdebbie, 1girl, mature woman...
Current outfit: teacher_suit, barefoot
Emotional state: default

=== PERSONALITY PROFILE ===
Player archetype: Romantic
Luna impression: trust +20, attraction +30

=== MEMORY ===
Recent: Player asked for help with homework
Fact: Player likes coffee

=== ACTIVE QUESTS ===
Private Lesson: Luna is teaching you math...

=== NARRATIVE GUIDELINES ===
Respond in Italian...

=== RESPONSE FORMAT ===
{"text": "...", "visual_en": "...", "updates": {...}}
"""
```

**STEP 5: LLM Generation**
```python
response = await llm_manager.generate(prompt, json_mode=True)

# Risposta LLM:
{
    "text": "Luna arrossisce visibilmente. 'Mi... mi piaci anche tu,' 
             balbetta. 'Ma qui è la biblioteca... qualcuno potrebbe 
             sentirci.' Ti guarda con occhi speranzosi.",
    "visual_en": "Luna blushing, looking down shyly, sitting at desk, 
                  barefoot, afternoon light",
    "tags_en": ["masterpiece", "soft lighting", "library"],
    "updates": {
        "affinity_change": {"luna": 3},
        "npc_emotion": "flustered"
    }
}
```

**STEP 6: Validation**
```python
# Override affinity con calcolo deterministico
validated_updates = {
    "affinity_change": {"luna": +5},  # Da calculator, non da LLM
    "npc_emotion": "flustered"
}
```

**STEP 7: Apply Updates**
```python
state_manager.change_affinity("luna", +5)  # 45 → 50
state_manager.current.npc_states["luna"].emotional_state = "flustered"
state_manager.advance_turn()  # 5 → 6
```

**STEP 8: Media Generation (async)**
```python
# Non blocca il return
asyncio.create_task(
    media_pipeline.generate_image(
        companion=luna,
        visual_en="Luna blushing, looking down...",
        outfit=current_outfit  # includes barefoot
    )
)
```

**STEP 9: Save**
```python
await state_manager.save(db)
# Tutto salvato: turno 6, affinità 50, stato emotivo flustered
```

**STEP 10: Return Result**
```python
return TurnResult(
    text="Luna arrossisce visibilmente...",
    image_path="storage/images/Luna_772299225.png",
    affinity_changes={"luna": 5},
    new_quests=[],
    turn_number=6
)
```

**UI Update:**
- Story log: Mostra testo risposta
- Immagine: Mostra Luna che arrossisce
- Affinity bar: Sale da 45 a 50
- Companion status: Luna diventa "flustered"

---

## APPENDICE A: CHECKLIST RICOSTRUZIONE

Per ricostruire Luna RPG v4 da zero:

### Fase 1: Setup Progetto
- [ ] Poetry init con Python 3.11+
- [ ] Installare dipendenze (pyproject.toml)
- [ ] Creare struttura directory src/luna/

### Fase 2: Core Models
- [ ] Implementare TUTTI i modelli in models.py
- [ ] Validare con test Pydantic

### Fase 3: Database
- [ ] Creare schema SQL
- [ ] Implementare DatabaseManager async
- [ ] Testare CRUD

### Fase 4: State Management
- [ ] Implementare StateManager
- [ ] Testare save/load

### Fase 5: AI Integration
- [ ] Implementare BaseLLMProvider
- [ ] Implementare GeminiProvider
- [ ] Implementare MoonshotProvider
- [ ] Implementare LLMManager con fallback

### Fase 6: Game Engine
- [ ] Implementare GameEngine
- [ ] Implementare game loop 10 step
- [ ] Integrare tutti i sistemi

### Fase 7: Sistemi Gameplay
- [ ] QuestEngine
- [ ] PersonalityEngine
- [ ] AffinityCalculator
- [ ] OutfitModifier
- [ ] LocationManager
- [ ] MemoryManager

### Fase 8: Media
- [ ] ImagePromptBuilder
- [ ] ComfyClient
- [ ] MediaPipeline

### Fase 9: UI
- [ ] MainWindow con layout 4 pannelli
- [ ] Tutti i widgets
- [ ] QuestChoiceWidget

### Fase 10: World Content
- [ ] Creare world YAML
- [ ] Testare caricamento

### Fase 11: Integration Testing
- [ ] Test flusso completo
- [ ] Test save/load
- [ ] Test error handling

---

## APPENDICE B: GLOSSARIO

- **Companion:** Personaggio principale con cui interagisce il player
- **Affinity:** Punteggio relazione 0-100
- **Quest:** Sotto-storia con obiettivi e ricompense
- **Turn:** Un ciclo completo input→output
- **Stage:** Fase di una quest
- **Prompt:** Istruzioni fornite all'AI
- **LoRA:** Low-Rank Adaptation, tecnica per addestrare personaggi in SD
- **ComfyUI:** Interfaccia node-based per Stable Diffusion
- **RunPod:** Cloud GPU per esecuzione ComfyUI

---

**FINE DOCUMENTAZIONE COMPLETA**

*Questo documento contiene tutto il necessario per comprendere, modificare e ricostruire Luna RPG v4.*
