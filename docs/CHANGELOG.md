# Changelog - Luna RPG v4

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

### ✅ Fix
- Companion detection migliorato (alias)
- Outfit modifier fix (componenti custom)
- Prompt LLM fix (no echo player input)

---

## [2026-02-26] - Video System & Outfit Modifier

### ⭐ Aggiunto

#### Video Generation System
- **Modello:** Wan2.1 I2V FP8
- **Risoluzione:** 480x896
- **Durata:** ~10 secondi (162 frame @ 16fps)
- **Frame Interpolation:** RIFE 2x
- **Nodi:** ComfyUI-Frame-Interpolation, KJNodes, WanVideoWrapper

#### Outfit Modifier
- **File:** `src/luna/systems/outfit_modifier.py`
- Pattern riconoscimento: togli scarpe, senza giacca, sbottonata...
- Traduzione IT→EN per SD prompts
- UI bottoni: Cambia (random), Modifica (custom)

### ✅ Fix
- RIFE error 400 fix (`clear_cache_after_n_frames: 10`)
- Colori video saturati (prompt ottimizzato)

---

## [2026-02-25] - Multi-NPC & Personality System

### ⭐ Aggiunto

#### Multi-NPC System
- Conversazioni con più NPC contemporaneamente
- Sequenze di turni (Player → NPC1 → Player → NPC2)
- Generazione immagini multiple per sequenza

#### Personality System
- Analisi comportamento player
- Archetipi: Gentle, Dominant, Romantic, Mysterious, Playful
- Adattamento risposte NPC in base ad archetipo

### ✅ Fix
- Auto-switch companion per NPC temporanei
- NPC base prompt (senza LoRA) per generici

---

## [2026-02-24] - World System & Eventi

### ⭐ Aggiunto

#### World: Terra degli Antenati
- 3 companion: Kara (Sciamana), Naya (Cacciatrice), Zara (Figlia del Capo)
- 6 location: villaggio, giungla, caverna, fiume, montagna, tempio
- 15 global events, 20 random events, 15 daily events

#### Event System
- Global events (narrativi)
- Random events (ripetibili)
- Daily events (routine)

---

## [2026-02-23] - Setup Iniziale

### ⭐ Aggiunto

#### Core Systems
- GameEngine orchestrazione
- LLM Manager (Gemini + Moonshot fallback)
- State Manager (persistenza)
- Media Pipeline (ComfyUI/RunPod)

#### World: School
- 2 companion: Luna (Prof), Stella (Studente)
- 13 location scuola
- Quest base

#### UI Base
- MainWindow layout 4 pannelli
- Story log
- Image display
- Input area

---

## Legenda

- **⭐ Aggiunto** - Nuova feature
- **✅ Modificato** - Cambiamento esistente
- **🐛 Fix** - Bug risolto
- **⚠️ Rimosso** - Feature deprecata

---

*Per dettagli tecnici vedere AGENTS.md e documentazione specifica in docs/*
