# SPECIFICA: Contesto LLM - Tutte le Situazioni da Trasmettere

**Versione:** 1.0  
**Data:** 2026-02-21  
**Scopo:** Definire COMPLETAMENTE cosa deve essere trasmesso dall'engine Python all'LLM

---

## 🎯 Principio Fondamentale

```
┌─────────────────────────────────────────────────────────────────┐
│  YAML (World Definition)                                        │
│     ↓                                                           │
│  Python (GameEngine) - Selezione e Formattazione                │
│     ↓                                                           │
│  System Prompt (IN INGLESE) → LLM → Risposta (IN ITALIANO)      │
└─────────────────────────────────────────────────────────────────┘
```

**Regola d'oro:** Campi destinati all'LLM devono essere in **INGLESE** per massima comprensione.

---

## 📋 CATEGORIE DI SITUAZIONI

### 1. 🌍 WORLD CONTEXT (`_meta.yaml`)

#### Campi Già Trasmessi ✅
| Campo YAML | Tipo | Lingua | Destinazione LLM |
|------------|------|--------|------------------|
| `meta.genre` | string | Inglese | Header system prompt |
| `meta.lore` | string | **Inglese** | Sezione WORLD |
| `meta.description` | string | **Inglese** | Fallback se lore manca |

#### Campi NON Trasmessi (da valutare)
| Campo YAML | Descrizione | Priorità |
|------------|-------------|----------|
| `player_character.identity.background` | Background del protagonista | Media |
| `player_character.starting_stats` | Stats iniziali | Bassa |
| `gameplay_systems.affinity.tiers` | Tier affinità con descrizioni | Media |
| `gameplay_systems.economy` | Sistema economico | Bassa |
| `gameplay_systems.reputation.factions` | Fazioni reputazione | Bassa |

#### Convenzione
```yaml
_meta.yaml:
  meta:
    lore: |                           # ✅ IN INGLESE - Contesto narrativo
      A provincial high school where lives intertwine...
  
  player_character:
    identity:
      background: |                   # ⚠️ IN INGLESE - Per contesto player
        A transfer student determined to connect deeply...
```

---

### 2. 📍 TIME CONTEXT (`time.yaml`)

#### Schema Completo
```yaml
time:
  <TimeOfDay>:
    name: "string"                    # UI: Italiano OK
    lighting: "string"                # ✅ IN INGLESE - Per immagini
    ambient_description: "string"     # ✅ IN INGLESE - Atmosfera narrativa
```

#### Cosa Trasmettere
| Campo | Destinazione | Esempio |
|-------|--------------|---------|
| `lighting` | Visual generation | "sunset colors, orange sky, golden hour" |
| `ambient_description` | Narrative context | "School is over, clubs are active, secret meetings begin" |

#### Formato nel System Prompt
```markdown
=== TIME OF DAY ===
Period: Evening
Atmosphere: School is over, clubs are active, secret meetings begin
Lighting: sunset colors, orange sky, golden hour
```

#### Stato Implementazione
- ✅ `lighting` - Trasmesso
- ✅ `ambient_description` - Trasmesso
- ⚠️ `name` - Non necessario (UI only)

---

### 3. 🗺️ LOCATION CONTEXT (`locations.yaml`)

#### Schema Completo
```yaml
locations:
  <location_id>:
    # --- Core (obbligatori) ---
    id: "string"
    name: "string"                    # UI: Italiano OK
    description: "string"             # ✅ IN INGLESE - Descrizione base
    
    # --- Visual (per immagini) ---
    visual_style: "string"            # ✅ IN INGLESE - Stile visivo
    lighting: "string"                # ✅ IN INGLESE - Illuminazione
    
    # --- Situazionali (contesto narrativo) ---
    time_descriptions:                # ✅ IN INGLESE - Per orario specifico
      Morning: "..."
      Afternoon: "..."
      Evening: "..."
      Night: "..."
    
    dynamic_descriptions:             # ✅ IN INGLESE - Per stato dinamico
      crowded: "..."
      empty: "..."
      locked: "..."
    
    # --- Meccaniche (non per LLM) ---
    connected_to: [...]               # ❌ Navigazione - non LLM
    aliases: [...]                    # ❌ Parsing input - non LLM
    available_times: [...]            # ❌ Meccanica - non LLM
    available_characters: [...]       # ❌ Meccanica - non LLM
    companion_can_follow: bool        # ❌ Meccanica - non LLM
    companion_refuse_message: "..."   # ❌ UI/Gameplay - non LLM
```

#### Convenzione Lingua
| Campo | Lingua | Motivo |
|-------|--------|--------|
| `name` | Italiano | Visualizzato in UI |
| `description` | **Inglese** | Contesto LLM |
| `visual_style` | **Inglese** | Tag SD/ImageGen |
| `lighting` | **Inglese** | Tag SD/ImageGen |
| `time_descriptions.*` | **Inglese** | Contesto LLM situazionale |
| `dynamic_descriptions.*` | **Inglese** | Contesto LLM situazionale |

#### Priorità Trasmissione
1. **Alta:** `description`, `time_descriptions` (corrente)
2. **Media:** `visual_style`, `lighting`
3. **Bassa:** `dynamic_descriptions` (richiede stato runtime)

---

### 4. 👤 COMPANION CONTEXT (`<name>.yaml`)

#### Schema Completo - Sezioni

##### 4.1 Identità di Base
```yaml
companion:
  name: "string"                      # ✅ Identificatore
  role: "string"                      # ✅ IN INGLESE - Contesto sociale
  age: number                         # ✅ Per dinamiche relazione
  base_personality: "string"          # ✅ IN INGLESE - Personalità base
  physical_description: "string"      # ✅ IN INGLESE - Per descrizioni
  base_prompt: "string"               # ✅ IN INGLESE - CRITICAL per immagini
```

##### 4.2 Outfit System
```yaml
  wardrobe:
    <style_key>:
      description: "string"           # ✅ IN INGLESE - Per scene
      special: bool                   # ⚠️ Flag meccanico
```

##### 4.3 Personality System (CRITICO)
```yaml
  personality_system:
    core_traits:
      role: "string"                  # ⚠️ Duplicato companion.role
      age: "string"                   # ⚠️ Duplicato companion.age
      base_personality: "string"      # ⚠️ Duplicato companion.base_personality
      background: "string"            # ✅ IN INGLESE - Storia personale
      relationship_to_player: "string" # ✅ IN INGLESE - Dinamica relazione
    
    emotional_states:
      <state_name>:
        description: "string"         # ✅ IN INGLESE - Cosa significa lo stato
        dialogue_tone: "string"       # ✅ IN INGLESE - Come parlare
        trigger_flags: [...]          # ⚠️ Meccanico
    
    affinity_tiers:
      "<range>":                      # es. "0-25", "26-50"
        name: "string"                # ✅ IN INGLESE - Nome tier (es. "The Invisible")
        tone: "string"                # ✅ IN INGLESE - Tono generale
        examples:                     # ✅ IN INGLESE - Esempi dialogo
          - "Example line 1"
          - "Example line 2"
        voice_markers:                # ✅ IN INGLESE - Pattern linguistici
          - "Marker 1"
          - "Marker 2"
```

##### 4.4 Schedule (Living World)
```yaml
  schedule:
    <TimeOfDay>:
      preferred_location: "loc_id"    # ⚠️ Meccanico
      outfit: "style_key"             # ⚠️ Meccanico
      activity: "string"              # ✅ IN INGLESE - Cosa sta facendo ora
```

##### 4.5 Quests (vedi sezione 6)

##### 4.6 Milestones (Achievements)
```yaml
  milestones:
    - id: "string"
      name: "string"                  # UI: Italiano OK
      condition: {...}                # ⚠️ Meccanico
      icon: "emoji"                   # UI: non LLM
```

#### Convenzione Lingua Companion
| Sezione | Campo | Lingua | Priorità |
|---------|-------|--------|----------|
| Base | `role` | **Inglese** | Alta |
| Base | `base_personality` | **Inglese** | Alta |
| Base | `physical_description` | **Inglese** | Alta |
| Personality | `background` | **Inglese** | Alta |
| Personality | `relationship_to_player` | **Inglese** | Alta |
| Emotional | `description` | **Inglese** | Alta |
| Emotional | `dialogue_tone` | **Inglese** | Alta |
| Affinity | `name` (tier) | **Inglese** | Media |
| Affinity | `tone` | **Inglese** | Media |
| Affinity | `examples` | **Inglese** | Media |
| Affinity | `voice_markers` | **Inglese** | Media |
| Schedule | `activity` | **Inglese** | Bassa |

---

### 5. 🎭 STORY BEATS (`_meta.yaml`)

#### Schema
```yaml
story_beats:
  premise: "string"                   # ✅ IN INGLESE - Premessa narrativa
  themes:                             # ✅ IN INGLESE - Temi da esplorare
    - "theme1"
    - "theme2"
  hard_limits:                        # ✅ IN INGLESE - Vincoli assoluti
    - "limit1"
    - "limit2"
  soft_guidelines:                    # ⚠️ IN INGLESE - Linee guida
    - "guideline1"
  
  beats:
    - id: "string"
      description: "string"           # ✅ IN INGLESE - Cosa deve succedere
      trigger: "string"               # ⚠️ Meccanico (Python eval)
      required_elements: [...]        # ⚠️ Meccanico (validazione)
      tone: "string"                  # ✅ IN INGLESE - Tono scena
      consequence: "string"           # ⚠️ Meccanico
```

#### Cosa Trasmettere
- ✅ `premise` - Sempre, come contesto base
- ✅ `themes` - Lista temi
- ✅ `hard_limits` - Vincoli narrativi
- ✅ `beat attivo` - Quando triggerato: `description` + `tone`

---

### 6. 📜 QUESTS (nei file companion)

#### Schema
```yaml
quests:
  <quest_id>:
    meta:
      title: "string"                 # UI: Italiano OK
      description: "string"           # ✅ IN INGLESE - Contesto quest
      character: "name"               # ⚠️ Meccanico
      hidden: bool                    # ⚠️ Meccanico
    
    stages:
      <stage_id>:
        title: "string"               # UI: Italiano OK
        description: "string"         # ⚠️ UI/quest log
        narrative_prompt: "string"    # ✅ IN INGLESE - Istruzioni LLM!
        
        on_enter: [...]               # ⚠️ Meccanico (azioni)
        on_exit: [...]                # ⚠️ Meccanico (azioni)
```

#### Cosa Trasmettere
- ✅ `narrative_prompt` dello stage attivo - **CRITICO per coerenza quest**

---

### 7. 🌍 GLOBAL EVENTS (`global_events.yaml`)

#### Schema (già implementato v1.0)
```yaml
global_events:
  <event_id>:
    meta:
      title: "string"                 # UI: Italiano OK
      description: "string"           # ✅ IN INGLESE - Contesto evento
      icon: "emoji"                   # UI: non LLM
    
    trigger: {...}                    # ⚠️ Meccanico
    
    effects:
      duration: number                # ⚠️ Meccanico
      atmosphere_change: "string"     # ✅ IN INGLESE - Tono atmosfera
      visual_tags: [...]              # ✅ IN INGLESE - Tag immagini
      location_modifiers:             # ⚠️ Meccanico + UI
        - location: "loc_id"
          blocked: bool
          message: "string"           # ❌ UI: Italiano (messaggio player)
      on_start: [...]                 # ⚠️ Meccanico (azioni)
      on_end: [...]                   # ⚠️ Meccanico (azioni)
    
    narrative_prompt: "string"        # ✅ IN INGLESE - **CRITICO**
```

#### Già Implementato ✅
- Event System v1.0 completo
- Trasmissione `narrative_prompt`, `atmosphere_change`, `visual_tags`
- Validazione schema

---

## 📝 RIEPILOGO PER IMPLEMENTAZIONE

### Priorità Alta (Implementare Subito)

1. **Companion Personality Background**
   - `personality_system.core_traits.background`
   - `personality_system.core_traits.relationship_to_player`

2. **Companion Emotional States Dettagli**
   - Già implementato: `description`, `dialogue_tone`

3. **Companion Affinity Tiers**
   - `affinity_tiers.<range>.examples`
   - `affinity_tiers.<range>.voice_markers`

4. **Location Visual Style**
   - `locations.<id>.visual_style`
   - `locations.<id>.lighting` (se diverso da time slot)

### Priorità Media (Implementare Dopo)

5. **Player Character Background**
   - `player_character.identity.background`

6. **Companion Schedule Activity**
   - `schedule.<time>.activity`

7. **Quest Meta Description**
   - `quests.<id>.meta.description`

### Priorità Bassa (Nice to Have)

8. **Affinity Tiers Names**
   - `affinity_tiers.<range>.name` (es. "The Devoted")

9. **Dynamic Location States**
   - Richiede implementazione stato runtime
   - `locations.<id>.dynamic_descriptions`

10. **Gameplay Systems Info**
    - Azioni sbloccate per tier
    - Fazioni reputazione

---

## 🔧 SPECIFICA IMPLEMENTAZIONE

### Pattern per Nuovi Metodi in PromptBuilder

```python
def _build_<situazione>_context(self, game_state: GameState) -> str:
    """Build <situazione> context for LLM.
    
    Args:
        game_state: Current game state
        
    Returns:
        Formatted context string or empty
    """
    # 1. Recupera dati dal world/game_state
    data = self.world.<qualcosa>.get(...)
    
    # 2. Se non c'è, return ""
    if not data:
        return ""
    
    # 3. Formatta per LLM (in inglese)
    lines = ["=== SECTION NAME ==="]
    lines.append(f"Field: {data.field}")
    
    # 4. Return formatted string
    return "\n".join(lines)
```

### Convenzione Nomi Sezioni Prompt

```markdown
=== WORLD CONTEXT ===
=== TIME OF DAY ===
=== LOCATION ATMOSPHERE ===
=== ACTIVE COMPANION ===
=== EMOTIONAL STATE ===
=== AFFINITY TIER ===
=== STORY BEAT ===
=== ACTIVE QUESTS ===
=== ACTIVE WORLD EVENT ===
=== PSYCHOLOGICAL CONTEXT ===
```

---

## ✅ CHECKLIST IMPLEMENTAZIONE

### Da Fare Ora (Alta Priorità)
- [ ] `_build_companion_background_context()` - background + relationship
- [ ] `_build_affinity_tier_examples()` - examples + voice_markers
- [ ] `_build_location_visual_context()` - visual_style + lighting

### Da Fare Dopo (Media Priorità)
- [ ] `_build_player_background_context()` - player background
- [ ] `_build_companion_activity_context()` - schedule activity
- [ ] `_build_quest_meta_context()` - quest descriptions

### Documentazione
- [ ] Aggiornare `WORLD_CREATION_GUIDE.md` con convenzioni lingua
- [ ] Creare template YAML con esempi in inglese
- [ ] Aggiornare `EVENT_SYSTEM_SPEC.md` con riferimenti
