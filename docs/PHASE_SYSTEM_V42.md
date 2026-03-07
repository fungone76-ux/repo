# Phase System V4.2 - Technical Specification

## Overview

Il Phase System V4.2 gestisce il ciclo giorno/notte con **8 turni per fase**:
- Mattina (8 turni) → Pomeriggio (8) → Sera (8) → Notte (8)
- **32 turni totali = 1 giorno completo**

## Key Features

### 1. Phase Transitions (Cambio Fase)
Quando scadono gli 8 turni:
- ⏰ **Tempo avanza** automaticamente
- 🚶 **NPC si spostano** secondo la loro routine
- 👤 **Player rimane** nella location corrente
- 👋 **Auto-switch a solo** se il companion lascia la location

### 2. Freeze System (Pausa Turni)
Blocca il conteggio turni durante scene importanti:

**Comandi Player:**
- `pausa`, `freeze`, `blocca turni` → Blocca
- `riprendi`, `unfreeze` → Riprende
- `stato turni` → Mostra turni rimanenti

**Auto-freeze:**
- Scene romantiche: "ti amo", "mi piaci", "baciami"
- Scene critiche: "non andare", "pericolo", "fermati"

### 3. NPC Schedules (Routine Giornaliere)
Ogni NPC ha una schedule che definisce:
- 📍 **Location** per ogni fascia oraria
- 👕 **Outfit** consigliato
- 📝 **Activity** (descrizione per LLM)

## File Structure

```
src/luna/systems/
├── phase_manager.py       # Gestione fasi e freeze
├── schedule_manager.py    # Routine NPC
└── time_manager.py        # Deadline quest (legacy)

worlds/
├── school_life_complete/  # Usa companion_schedules.yaml
└── prehistoric_tribe/
    └── companion_schedules.yaml # Schedule custom
```

## Configuration

### Per World Esistente (senza schedule)
```python
# Schedule auto-generate per tutti i companions
# Basate su spawn_locations e first location
```

### Per World con Schedule Custom
```yaml
# worlds/TUO_WORLD/companion_schedules.yaml
npc_schedules:
  NomeNPC:
    morning:
      location: "location_id"
      activity: "Descrizione attività"
      outfit: "wardrobe_style"
    afternoon:
      location: "altra_location"
      activity: "Altra attività"
      outfit: "altro_style"
    evening:
      location: "casa"
      activity: "Cena e riposo"
      outfit: "casual"
    night:
      location: "casa" 
      activity: "Dorme"
      outfit: "nightwear"
```

## API Reference

### PhaseManager
```python
from luna.systems.phase_manager import PhaseManager, PhaseConfig

phase_manager = PhaseManager(
    game_state=game_state,
    schedule_manager=schedule_manager,
    config=PhaseConfig(turns_per_phase=8),
    on_phase_change=callback,
)

# A fine turno
result = phase_manager.on_turn_end()
if result:
    # Phase changed!
    print(result.time_message)
    print(result.npc_movements)

# Freeze/Unfreeze
phase_manager.freeze("Scene importante")
phase_manager.unfreeze()
```

### ScheduleManager
```python
from luna.systems.schedule_manager import ScheduleManager

schedule_manager = ScheduleManager(
    game_state=game_state,
    world=world,  # opzionale
)

# Query location
loc = schedule_manager.get_npc_location("Kara")
activity = schedule_manager.get_npc_activity("Kara")

# Trova NPC presenti
npcs_here = schedule_manager.get_present_npcs("villaggio")
```

## Integration with Other Systems

| Sistema | Interazione |
|---------|-------------|
| **Quest** | Deadline continuano a funzionare |
| **Events** | Eventi globali attivati ogni turno |
| **Story Beats** | Indipendenti, basati su testo LLM |
| **Movement** | Quando player si muove, auto-switch a NPC presente |

## TurnResult Flags

```python
@dataclass
class TurnResult:
    # ... existing fields ...
    
    # V4.2 Phase System
    phase_change_result: Optional[PhaseChangeResult] = None
    companion_left_due_to_phase: bool = False
    needs_location_refresh: bool = False  # UI rigenera immagine
```

## Migration Guide

### Da V4.1 a V4.2
1. Aggiungi `phase_manager` in `engine.py` (già fatto)
2. Passa `world` a `ScheduleManager` (già fatto)
3. Opzionale: crea `npc_schedules.yaml` per world custom

### World Legacy (senza cambiamenti)
Funzionano senza modifiche usando schedule default.

## Examples

### Prehistoric Tribe Schedules
```yaml
# File: companion_schedules.yaml
npc_schedules:
  Kara:  # Sciamana
    morning: { location: "caverna", activity: "Prepara pozioni", outfit: "ritual_paint" }
    afternoon: { location: "villaggio", activity: "Dice il futuro", outfit: "ritual_paint" }
    evening: { location: "caverna", activity: "Meditazione", outfit: "cave_dweller" }
    night: { location: "caverna", activity: "Dorme", outfit: "nightwear" }
    
  Naya:  # Cacciatrice
    morning: { location: "giungla", activity: "Caccia", outfit: "huntress_gear" }
    afternoon: { location: "giungla", activity: "Continua caccia", outfit: "tracking" }
    evening: { location: "villaggio", activity: "Torna con preda", outfit: "huntress_gear" }
    night: { location: "villaggio", activity: "Riposa", outfit: "nightwear" }
```

## Technical Details

### Phase Change Flow
```
1. on_turn_end() chiamato
2. turns_in_phase >= 8? → Phase change triggered
3. Advance time (Morning → Afternoon)
4. Move all NPCs to new schedule location
5. Check if player's companion left
6. If yes: switch to "_solo_", generate empty location image
7. Build phase change message
8. Return PhaseChangeResult
```

### Freeze Logic
```
1. User says "pausa" OR auto-freeze triggered
2. frozen = True
3. on_turn_end() returns None immediately
4. Phase doesn't advance
5. User says "riprendi" → frozen = False
```

## Changelog V4.2

### Added
- PhaseManager with 8 turns per phase
- Freeze/unfreeze system
- Auto-freeze for romantic/critical scenes
- NPC schedules loaded from YAML
- Generic schedule generation for any world
- `generate_solo_location_image()` for empty locations

### Changed
- ScheduleManager now accepts `world` parameter
- PhaseManager iterates over all scheduled NPCs (not hardcoded)
- TurnResult includes phase change flags

### Fixed
- Time slot parsing (case-insensitive)
- Backward compatibility with school_life
