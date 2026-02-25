# Event System Specification v1.0

## Overview

Il sistema degli Eventi Globali permette di definire eventi dinamici (meteo, situazioni sociali, blackout, etc.) che influenzano la narrazione e il gameplay. Questo documento definisce lo schema completo e come i dati vengono trasmessi all'LLM.

---

## Schema YAML Completo

```yaml
global_events:
  <event_id>:
    # ============================================
    # META (Obbligatorio)
    # ============================================
    meta:
      title: "string"           # OBBLIGATORIO - Nome visualizzato
      description: "string"     # OBBLIGATORIO - Descrizione breve
      icon: "emoji"             # OPZIONALE - Default: 🌍
    
    # ============================================
    # TRIGGER (Obbligatorio)
    # ============================================
    trigger:
      type: "random|conditional|time|location|affinity|flag|scheduled"
      chance: 0.15              # OBBLIGATORIO per type=random (0-1)
      
      # Per type=conditional
      conditions:
        - type: "companion|time|location|affinity|flag|random"
          target: "string"      # Nome companion, location, etc.
          operator: "eq|gt|lt|gte|lte|in|contains"
          value: "string|number|boolean|list"
          chance: 0.4           # Solo per type=random dentro conditions
      
      allowed_times:            # OPZIONALE - Limita a fasce orarie
        - "Morning"
        - "Afternoon"
        - "Evening"
        - "Night"
    
    # ============================================
    # EFFECTS (Obbligatorio)
    # ============================================
    effects:
      duration: 3               # OBBLIGATORIO - Turni di durata (>=1)
      
      # --- Campi per LLM (NARRATIVE) ---
      atmosphere_change: "string"   # OBBLIGATORIO - Tono emotivo
                                   # Es: "dramatic, trapped", "romantic, intimate"
      
      visual_tags:                  # CONSIGLIATO - Tag per immagini
        - "rain"
        - "dark_sky"
        - "wet"
      
      # --- Campi per Gameplay (MECHANICS) ---
      location_modifiers:           # OPZIONALE - Blocca/modifica location
        - location: "school_entrance"
          blocked: true
          message: "La pioggia è troppo forte per uscire."
      
      location_lock: "loc_id"       # OPZIONALE - Blocca player in location
      
      affinity_multiplier: 1.5      # OPZIONALE - Modifica velocità affinità
      
      # Azioni automatiche all'avvio/fine
      on_start:
        - action: "set_flag"
          key: "rainstorm_active"
          value: true
        - action: "set_emotional_state"
          character: "{current_companion}"
          state: "flustered"
      
      on_end:
        - action: "set_flag"
          key: "rainstorm_active"
          value: false
    
    # ============================================
    # NARRATIVE PROMPT (Obbligatorio per LLM)
    # ============================================
    narrative_prompt: "string"    # OBBLIGATORIO - Contesto narrativo per LLM (IN INGLESE!)
                                 # Placeholder supportati:
                                 # - {current_companion} -> Nome companion attivo
                                 # - {location} -> Location corrente
                                 # - {time} -> Orario (Morning/Afternoon/etc)
                                 # - {player_name} -> Nome player
```

---

## Flusso Dati: YAML → Python → LLM

```
┌─────────────────────────────────────────────────────────────────────┐
│  YAML Definition (global_events.yaml)                               │
│  ├─ meta.title                                                      │
│  ├─ meta.description                                                │
│  ├─ meta.icon                                                       │
│  ├─ trigger.*                                                       │
│  ├─ effects.*                                                       │
│  └─ narrative_prompt                                                │
└──────────────────────────┬──────────────────────────────────────────┘
                           ↓ parse (WorldLoader)
┌─────────────────────────────────────────────────────────────────────┐
│  GlobalEventDefinition (Pydantic Model)                             │
│  ├─ id, title, description                                          │
│  ├─ trigger_type, trigger_chance, trigger_conditions                │
│  ├─ effects: GlobalEventEffect                                      │
│  │   ├─ duration                                                    │
│  │   ├─ atmosphere_change  ←──────┐                                 │
│  │   ├─ visual_tags               │                                 │
│  │   ├─ location_modifiers        │                                 │
│  │   └─ ...                       │                                 │
│  └─ narrative_prompt  ←───────────┘                                 │
└──────────────────────────┬──────────────────────────────────────────┘
                           ↓ activate (GlobalEventManager)
┌─────────────────────────────────────────────────────────────────────┐
│  GlobalEventInstance (Runtime)                                      │
│  ├─ event_id, name, description, icon                               │
│  ├─ duration_turns, remaining_turns  ← Decrementa ogni turno        │
│  ├─ effects: dict                                                   │
│  └─ narrative_prompt  ← NEW: Ora incluso!                           │
└──────────────────────────┬──────────────────────────────────────────┘
                           ↓ build_context (EventContextBuilder)
┌─────────────────────────────────────────────────────────────────────┐
│  EventContext (LLM-Optimized)                                       │
│  ├─ header: "🌧️ Temporale Improvviso"                              │
│  ├─ atmosphere: "dramatic, trapped"                                 │
│  ├─ narrative: "Nuvole nere... con Luna"  ← Variabili sostituite    │
│  ├─ urgency_hint: "beginning|ongoing|ending"                        │
│  ├─ world_state_changes: ["Location X blocked", ...]                │
│  ├─ visual_tags: ["rain", "dark_sky", ...]                          │
│  └─ remaining_turns, total_turns                                    │
└──────────────────────────┬──────────────────────────────────────────┘
                           ↓ to_prompt_section
┌─────────────────────────────────────────────────────────────────────┐
│  System Prompt (LLM Input)                                          │
│  === ACTIVE WORLD EVENT ===                                         │
│  🌧️ Temporale Improvviso                                           │
│  Atmosphere: dramatic, trapped                                      │
│                                                                     │
│  NARRATIVE CONTEXT:                                                 │
│  Nuvole nere avvolgono all'improvviso la scuola. Tuoni...           │
│                                                                     │
│  WORLD STATE CHANGES:                                               │
│  • Location 'school_entrance' is BLOCKED                            │
│                                                                     │
│  VISUAL NOTES:                                                      │
│  Scene should include: rain, dark_sky, wet                          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Campi Obbligatori per Trasmissione LLM

Perché un evento venga correttamente trasmesso all'LLM, **DEVONO** essere presenti:

| Campo | Dove | Motivo |
|-------|------|--------|
| `meta.title` | YAML | Identificazione evento nell'UI |
| `meta.description` | YAML | Contesto base |
| `effects.duration` | YAML | Gestione durata evento |
| `effects.atmosphere_change` | YAML | **TONO NARRATIVO** - Guida l'LLM sull'umore |
| `narrative_prompt` | YAML | **CONTESTO NARRATIVO** - Descrizione dettagliata |

**Se manca uno di questi campi, il sistema di validazione segnalerà un errore.**

---

## Convenzione Lingua: Bilingue Italiano/Inglese

Anche se il gioco genera narrativa in **italiano**, il **system prompt** (incluse le istruzioni evento) deve essere in **inglese** per garantire la migliore comprensione da parte dell'LLM.

### Campi in Inglese (System Prompt)
| Campo | Lingua | Motivo |
|-------|--------|--------|
| `meta.title` | Inglese o Italiano | Visualizzato in UI (può essere italiano) |
| `meta.description` | Inglese | Contesto per l'LLM |
| `effects.atmosphere_change` | **Inglese** | Istruzioni tono per LLM |
| `narrative_prompt` | **Inglese** | Contesto narrativo per LLM |
| `effects.visual_tags` | **Inglese** | Tag SD sono in inglese |

### Campi in Italiano (Gameplay/UI)
| Campo | Lingua | Motivo |
|-------|--------|--------|
| `effects.location_modifiers[].message` | Italiano | Messaggio mostrato al giocatore |

## Placeholder Supportati in narrative_prompt

I seguenti placeholder verranno automaticamente sostituiti:

| Placeholder | Sostituzione | Esempio |
|-------------|--------------|---------|
| `{current_companion}` | Nome companion attivo | "Luna" |
| `{location}` | Location corrente | "school_classroom" |
| `{time}` | Orario del giorno | "Evening" |
| `{player_name}` | Nome del player | "Protagonist" |

**Esempio:**
```yaml
narrative_prompt: "Sei intrappolato con {current_companion} in {location}..."
# Diventa:
# "Sei intrappolato con Luna in school_classroom..."
```

---

## Validazione

Il sistema include un validatore che controlla automaticamente gli eventi all'avvio:

```python
from luna.systems.event_validator import validate_world_events

# Valida tutti gli eventi nel mondo
result = validate_world_events(world)

if not result.is_valid:
    for issue in result.get_errors():
        print(f"❌ {issue.event_id}: {issue.message}")
```

### Livelli di Severità

- **ERROR**: Campo obbligatorio mancante - l'evento funzionerà male
- **WARNING**: Campo consigliato mancante - degradazione funzionalità
- **INFO**: Suggerimento per miglioramento

---

## Esempio Completo: Temporale

```yaml
global_events:
  rainstorm:
    meta:
      title: "Temporale Improvviso"           # UI: può essere italiano
      description: "A heavy rainstorm traps everyone at school"  # LLM context: IN INGLESE
      icon: "🌧️"
    
    trigger:
      type: "random"
      chance: 0.15
      allowed_times: ["Afternoon", "Evening"]
    
    effects:
      duration: 3
      
      # Per LLM
      atmosphere_change: "dramatic, trapped, intimate"
      visual_tags: ["rain", "wet", "dark_sky", "puddles", "storm"]
      
      # Per Gameplay
      location_modifiers:
        - location: "school_entrance"
          blocked: true
          message: "La pioggia è troppo forte per uscire."
      
      on_start:
        - action: "set_flag"
          key: "rainstorm_active"
          value: true
        - action: "set_emotional_state"
          character: "{current_companion}"
          state: "flustered"
      
      on_end:
        - action: "set_flag"
          key: "rainstorm_active"
          value: false
    
    narrative_prompt: "Dark clouds suddenly envelop the school. Thunder rumbles. Students crowd at the windows in excitement. You are trapped at school with {current_companion}, creating an intimate, inescapable atmosphere..."
```

---

## Output Finale nel System Prompt

Quando l'evento è attivo, il sistema prompt includerà (tutto in inglese per l'LLM):

```
=== ACTIVE WORLD EVENT ===
🌧️ Sudden Rainstorm
Atmosphere: dramatic, trapped, intimate

⚡ The event has just started! The situation is new and unfolding.

NARRATIVE CONTEXT:
Dark clouds suddenly envelop the school. Thunder. Students crowd at the 
windows. You are trapped at school with Luna. The rain creates an intimate, 
unescapable atmosphere...

WORLD STATE CHANGES:
• Location 'school_entrance' is BLOCKED: The rain is too heavy to go outside.

VISUAL NOTES:
Scene should include: rain, wet, dark_sky, puddles, storm
```

---

## API Reference

### EventContextBuilder

```python
from luna.core.event_context_builder import EventContextBuilder

builder = EventContextBuilder(world)

# Singolo evento
context = builder.build_context(event_instance, game_state)
prompt_section = context.to_prompt_section()

# Multipli eventi
combined = builder.build_combined_context([event1, event2], game_state)
```

### EventSchemaValidator

```python
from luna.systems.event_validator import EventSchemaValidator

validator = EventSchemaValidator(world)
result = validator.validate_all()

# Stampa report
validator.print_report(result)
```

---

## Checklist Implementazione Evento

- [ ] Definito `meta.title` e `meta.description`
- [ ] Definito `trigger.type` con configurazione appropriata
- [ ] Definito `effects.duration` >= 1
- [ ] Definito `effects.atmosphere_change` (tono emotivo)
- [ ] Definito `narrative_prompt` (20-100 parole consigliate)
- [ ] Aggiunti `effects.visual_tags` per coerenza immagini
- [ ] Testato con validatore (nessun errore)
- [ ] Verificato che appaia correttamente nel system prompt
