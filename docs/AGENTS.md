# Luna RPG v4 - Stato Progetto

## Data: 2026-03-03

---

## Novità del Giorno ✅

### 🆕 NPC Schedule System - V4.1 Dynamic Routines ⭐

**File:**
- `src/luna/systems/schedule_manager.py` - Nuovo sistema routine NPC
- `src/luna/core/engine.py` - Integrazione auto-switch e contesto LLM

**Caratteristiche:**
- ✅ **Routine giornaliere**: Ogni NPC ha location preferita per ogni fase del giorno
- ✅ **Auto-switch**: Entri in una location → trovi automaticamente chi c'è
- ✅ **Sempre interagibile**: Puoi sempre parlare con chiunque (anche se "lontano")
- ✅ **Contesto LLM**: L'NPC sa dove è e cosa sta facendo
- ✅ **Query routine**: Chiedi "dove è Luna?" per sapere la sua posizione

**Esempio Routine:**
```
LUNA:
☀️ Morning: school_classroom (insegna)
🌅 Afternoon: school_office_luna (corregge)
🌆 Evening: school_office_luna (prepara)
🌙 Night: luna_home (riposa)

STELLA:
☀️ Morning: school_classroom (segue lezioni)
🌅 Afternoon: school_gym (allenamento)
🌆 Evening: bar_town (si rilassa)
🌙 Night: stella_home (a casa)
```

**Flusso Auto-Switch:**
```
Player entra in school_gym (pomeriggio)
   ↓
ScheduleManager trova: Stella è qui!
   ↓
Auto-switch: Player inizia a parlare con Stella
   ↓
LLM sa: "Stella sta allenando basket in palestra"
   ↓
Immagine: Stella in gym_uniform nella palestra
```

**Comandi Query:**
- "dove è Luna?" → "📍 Luna è a school_office_luna. Prepara lezioni per domani"
- "routine di Stella" → Mostra tutta la giornata tipo di Stella

---

### 🆕 Time Manager System - V4.1 Hybrid Adaptive

**File:**
- `src/luna/systems/time_manager.py` - Nuovo sistema gestione tempo
- `src/luna/core/engine.py` - Integrazione
- `src/luna/ui/main_window.py` - UI aggiornata (rimosso pulsante manuale)

**Caratteristiche:**
- ✅ **Fase 1 (Auto-advance):** Tempo avanza automaticamente ogni 5 turni
- ✅ **Fase 2 (Rest commands):** Comandi "vado a dormire", "riposo", etc.
- ✅ **Fase 3 (Deadlines):** Quest con scadenze temporali
- ✅ Rimosso pulsante manuale "Time" - più immersivo

**Comandi Rest riconosciuti:**
- "dormo", "dormire", "vado a dormire"
- "finisco la giornata", "vado a casa"
- "riposo", "mi riposo", "a letto"

**Esempio flusso:**
```
Turno 1-5: Mattina (conversazioni)
→ Auto-advance: "🌅 Il sole sale più alto... è pomeriggio."

Turno 6-10: Pomeriggio
→ Player: "vado a dormire"
→ Rest advance: "💤 Decidi di riposare... Ora è Night."

Turno 11-15: Notte
→ Auto-advance: "☀️ Una nuova alba... è mattino."
```

**Impatto UI:**
- ❌ Rimosso bottone "☀️ Time" dalla toolbar
- ✅ Label tempo non cliccabile in status bar
- ✅ Tooltip: "Time advances automatically every 5 turns"

---

### 1. Movement System Refactor ⭐

**File:**
- `src/luna/systems/movement.py` - Nuovo sistema movimento
- `src/luna/core/engine.py` - Integrazione

**Caratteristiche:**
- ✅ Estratto completo da engine.py
- ✅ Companion **sempre** rimane indietro (V4.1)
- ✅ Switch automatico a `companion="_solo_"`
- ✅ Parametri per immagini solo mode

**Flusso movimento:**
```
Utente: "vado in bagno"
   ↓
MovementHandler rileva intento
   ↓
Risolve "bagno" → school_bathroom_male
   ↓
LocationManager esegue movimento
   ↓
Companion rimane indietro
   ↓
Switch a "_solo_"
   ↓
Genera immagine bagno VUOTO (solo mode)
```

---

### 2. Solo Mode - Immagini Location Vuote ⭐

**Quando si attiva:**
- Player si muove senza companion
- Companion switcha a `"_solo_"`

**Meccanica:**
- ❌ Nessun LoRA del personaggio
- ✅ Usa `location_visual_style` dalla location
- ✅ Genera scena vuota (solo ambiente)

**Esempi:**
| Input | Location | Immagine |
|-------|----------|----------|
| "vado in bagno" | school_bathroom_male | Bagno vuoto, piastrelle bianche |
| "vado in corridoio" | school_corridor | Corridoio vuoto, armadietti |
| "vado in palestra" | school_gym | Palestra vuota, parquet |

---

### 3. StateMemoryManager - Unificazione Salvataggio ⭐

**File:** `src/luna/systems/state_memory.py`

**Unifica in un'unica classe:**
- Game state (location, outfit, affinità)
- Quest states
- Event states
- StoryDirector state
- Personality states
- Short-term memory (messaggi)
- Long-term memory (fatti)

**Prima** (engine.py):
```python
async with self.db.session() as db_session:
    await self.state_manager.save(db_session)
    for quest_state in self.quest_engine.get_all_states():
        await self.db.save_quest_state(...)
    if self.event_manager:
        await self.db.save_global_event_states(...)
    if self.story_director:
        await self.db.save_story_director_state(...)
    if self.personality_engine:
        await self.db.update_session(...)
# 30+ righe!
```

**Ora:**
```python
await self.state_memory.save_all()  # Una riga!
```

---

### 4. IntroGenerator - Estrazione ⭐

**File:** `src/luna/systems/intro.py`

**Estratto da engine.py:**
- `generate_intro()` → `IntroGenerator.generate()`
- `_build_intro_prompt()` → `IntroGenerator._build_prompt()`

**Vantaggi:**
- engine.py snellito (-100 righe)
- Single responsibility
- Più facile testare

---

### 5. TurnResult Spostato in Models

**Prima:**
```python
from luna.core.engine import TurnResult  # ❌ Circular import risk
```

**Ora:**
```python
from luna.core.models import TurnResult  # ✅ Pulito
```

---

### 6. Nuovi NPC Aggiunti

**File:** `worlds/school_life_complete/npc_templates.yaml`

| NPC | Ruolo | Location |
|-----|-------|----------|
| **Psicologa** | Dottoressa scolastica | Studio psicologia |
| **Farmacista** | Gestisce farmacia locale | Farmacia |
| **Parroco** | Sacerdote della chiesa locale | Chiesa |
| **Commesso** | Lavora in negozio | Negozio |
| **Barista** | Gestisce il bar | Bar |
| **Bibliotecaria** | Gestisce biblioteca | Biblioteca |
| **Allenatore** | Insegnante educazione fisica | Palestra |
| **Infermiera** | Infermeria scolastica | Infermeria |
| **Segretaria** | Amministrazione scuola | Segreteria |

**Totale NPC:** 14 → 23

---

### 7. Nuova Location: Segreteria

**File:** `worlds/school_life_complete/locations.yaml`

```yaml
school_secretary:
  name: "Segreteria Scolastica"
  visual_style: "office desks, filing cabinets, fluorescent lighting..."
  aliases: ["segreteria", "ufficio amministrativo"]
```

---

## 🐛 Bug Fix Oggi

| Problema | Soluzione |
|----------|-----------|
| **StartupDialog non seleziona companion** | Aggiunto selezione `last_companion` dopo caricamento world |
| **NPC temporanei in lista companion** | Skippa `is_temporary=True` nella lista |
| Messaggi persi durante movimento | Aggiunto `add_message()` prima del return |
| Stato non salvato dopo farewell | Aggiunto `save_all()` nel farewell |
| Parametri MovementHandler invertiti | Fix ordine: `(world, location_manager, game_state)` |
| Circular import TurnResult | Spostato in `models.py` |
| **Movimento a location con `requires_parent`** | Rimosso check parent - movimento libero |
| **NPC template non caricati** | Aggiunto `npc_templates` a `WorldDefinition` |
| **NPC generico non sostituito da template** | Ora rimuove generico prima di creare template |

---

## 📊 Statistiche Engine

| Metrica | Prima | Dopo |
|---------|-------|------|
| Righe engine.py | ~2700 | ~2470 |
| File systems/ | 16 | 18 (+2 nuovi) |
| Metodi in engine | 35+ | 30 (-5 estratti) |

---

## 🏗️ Nuova Architettura

```
src/luna/systems/
├── movement.py              # 🆕 Gestione movimento
├── state_memory.py          # 🆕 Stato + memoria unificati
├── intro.py                 # 🆕 Generazione intro
├── memory.py                # Memoria breve/lungo termine
├── location.py              # Gestione location
├── quests.py                # Sistema quest
├── personality.py           # Personalità NPC
└── ...
```

---

## Riepilogo Contenuti Totali

| Categoria | Numero |
|-----------|--------|
| **Quest** | 12 |
| **Story Beats** | 9 |
| **Global Events** | 6 |
| **Random Events** | 10 |
| **Daily Events** | 12 |
| **NPC Templates** | 23 (+9 oggi) |
| **Outfit** | 18 |
| **Location** | 20 (+1 oggi) |
| **TOTALE** | **~110** |

---

## Documentazione Disponibile

| File | Descrizione |
|------|-------------|
| `docs/CHANGELOG.md` | Cronologia modifiche |
| `AGENTS.md` | Guida per agenti AI |
| `docs/QUEST_CHOICE_SYSTEM.md` | Sistema scelte quest |
| `docs/EVENT_SYSTEM_SPEC.md` | Sistema eventi |
| `docs/MULTI_NPC_SYSTEM.md` | Gestione multipli NPC |
| `docs/PERSONALITY_SYSTEM.md` | Sistema personalità |
| `docs/WORLD_CREATION_GUIDE.md` | Creazione world |

---

## API Key Richieste (`.env`)

```bash
GEMINI_API_KEY=your_key_here
MOONSHOT_API_KEY=your_key_here  # fallback
```

---

## World Creati

| World | Stato | Companion | Location | Eventi |
|-------|-------|-----------|----------|--------|
| **school_life_complete** | ✅ Completo | Luna, Stella, Maria | 20 | 28 |

---

## Prossimi Step Consigliati

1. ✅ **Movement Refactor**
2. ✅ **Solo Mode**
3. ✅ **StateMemoryManager**
4. ⬜ **Test gameplay end-to-end**
5. ⬜ Aggiungere più quest con tipo "choice"
6. ⬜ Tutorial iniziale per nuovi giocatori

---

*Ultimo aggiornamento: 2026-03-03*
