# Piano Implementazione - Contesto LLM Completo

**Data:** 2026-02-21  
**Stato:** Analisi completa delle situazioni mancanti

---

## 📊 Stato Attuale: Cosa è Già Implementato

### ✅ FUNZIONANTE (testato)
1. World lore/description
2. Companion base (name, role, age, personality)
3. Emotional state base (nome)
4. Time slot context (ambient_description, lighting) 
5. Location time descriptions
6. Emotional state dettagliato (description, dialogue_tone)
7. Global events (completo)
8. Story beats (premise, themes, hard_limits, beat attivo)
9. Quest narrative prompts

---

## 🔴 MANCANTE - Priorità Alta

### 1. Companion Background & Relationship
**File:** `maria.yaml`, `stella.yaml`, `luna.yaml`  
**Campi:**
```yaml
personality_system:
  core_traits:
    background: "..."                 # Storia personale
    relationship_to_player: "..."     # Dinamica relazione
```

**Esempio da trasmettere:**
```markdown
=== COMPANION BACKGROUND ===
Background: Never married, lives alone, feels invisible, used to being ignored
Relationship: The protagonist is the first who treats her as a woman and defends her
```

**Implementazione:**
```python
# In PromptBuilder._build_companion_context()
if companion.emotional_states:  # Dati personality_system
    personality = companion.emotional_states  # È un dict
    if isinstance(personality, dict):
        background = personality.get('background', '')
        relationship = personality.get('relationship_to_player', '')
        if background or relationship:
            lines.append("\n=== BACKGROUND ===")
            if background:
                lines.append(f"History: {background}")
            if relationship:
                lines.append(f"Relationship Dynamic: {relationship}")
```

---

### 2. Affinity Tier Examples & Voice Markers
**File:** `maria.yaml`, `stella.yaml`, `luna.yaml`  
**Campi:**
```yaml
affinity_tiers:
  "26-50":
    examples:                         # Esempi dialogo
      - "Why are you so kind to me?"
    voice_markers:                    # Pattern linguistici
      - "Excessive gratitude"
      - "Insecurity about attractiveness"
```

**Esempio da trasmettere:**
```markdown
=== AFFINITY LEVEL: The Surprise (26-50) ===
Tone: Incredulous that someone speaks kindly to her

Example Dialogue:
- "Why are you so kind to me?"
- "No one ever helps me..."

Voice Markers:
- Excessive gratitude
- Insecurity about attractiveness
- Questions about own beauty
```

**Implementazione:**
```python
# Nuovo metodo: PromptBuilder._build_affinity_tier_context()
def _build_affinity_tier_context(self, companion, affinity):
    if not companion.affinity_tiers:
        return ""
    
    # Trova il tier corrente
    current_tier_data = None
    current_tier_name = ""
    for tier_range, data in sorted(companion.affinity_tiers.items()):
        # Parse "26-50" -> min=26, max=50
        parts = tier_range.split('-')
        if len(parts) == 2:
            min_val = int(parts[0])
            if affinity >= min_val:
                current_tier_data = data
                current_tier_name = tier_range
    
    if not current_tier_data:
        return ""
    
    lines = [f"=== AFFINITY LEVEL: {current_tier_name} ==="]
    
    if isinstance(current_tier_data, dict):
        name = current_tier_data.get('name', '')
        tone = current_tier_data.get('tone', '')
        examples = current_tier_data.get('examples', [])
        voice_markers = current_tier_data.get('voice_markers', [])
        
        if name:
            lines.append(f"Stage: {name}")
        if tone:
            lines.append(f"Tone: {tone}")
        if examples:
            lines.append("\nExample Dialogue:")
            for ex in examples[:3]:  # Max 3 esempi
                lines.append(f'  - "{ex}"')
        if voice_markers:
            lines.append("\nVoice Markers:")
            for vm in voice_markers:
                lines.append(f"  • {vm}")
    
    return "\n".join(lines)
```

---

### 3. Location Visual Style & Lighting
**File:** `locations.yaml`  
**Campi:**
```yaml
locations:
  school_library:
    visual_style: "bookshelves, reading lamps, quiet"
    lighting: "soft indoor"
```

**Esempio da trasmettere:**
```markdown
=== LOCATION VISUALS ===
Style: bookshelves, reading lamps, quiet
Lighting: soft indoor
```

**Implementazione:**
```python
# Nuovo metodo: PromptBuilder._build_location_visual_context()
def _build_location_visual_context(self, game_state):
    location = self.world.locations.get(game_state.current_location)
    if not location:
        return ""
    
    visual_style = getattr(location, 'visual_style', '')
    lighting = getattr(location, 'lighting', '')
    
    if not visual_style and not lighting:
        return ""
    
    lines = ["=== LOCATION VISUALS ==="]
    if visual_style:
        lines.append(f"Style: {visual_style}")
    if lighting:
        lines.append(f"Lighting: {lighting}")
    
    return "\n".join(lines)
```

---

## 🟡 MANCANTE - Priorità Media

### 4. Player Character Background
**File:** `_meta.yaml`  
**Campo:** `player_character.identity.background`

**Esempio:**
```markdown
=== PLAYER CHARACTER ===
Background: A transfer student, determined and charismatic
```

---

### 5. Companion Schedule Activity
**File:** `maria.yaml`, etc.  
**Campo:** `schedule.<time>.activity`

**Esempio:**
```markdown
=== CURRENT ACTIVITY ===
Maria is currently: Morning cleaning rounds in the corridors
```

---

### 6. Quest Meta Description
**File:** file companion  
**Campo:** `quests.<id>.meta.description`

**Esempio:**
```markdown
=== ACTIVE QUESTS ===
- La Difesa: The protagonist defends Maria from a bully student
```

---

## 📋 Piano Implementazione Step-by-Step

### Step 1: Verificare Caricamento Dati (WorldLoader)

Controllare che questi campi siano caricati correttamente:
- [ ] `personality_system.core_traits.background`
- [ ] `personality_system.core_traits.relationship_to_player`
- [ ] `affinity_tiers.*.examples`
- [ ] `affinity_tiers.*.voice_markers`
- [ ] `locations.*.visual_style`
- [ ] `locations.*.lighting`

**Test:**
```python
world = loader.load_world('school_life_complete')
maria = world.companions['Maria']
print(maria.emotional_states.get('background'))  # Dovrebbe funzionare
```

### Step 2: Aggiungere Metodi a PromptBuilder

Aggiungere in `src/luna/core/prompt_builder.py`:

1. `_build_companion_background_context()` 
2. `_build_affinity_tier_context()`
3. `_build_location_visual_context()`

### Step 3: Integrare in build_system_prompt()

Chiamare i nuovi metodi nel flusso principale:

```python
def build_system_prompt(...):
    # ... existing code ...
    
    # NUOVO: Companion background
    background_context = self._build_companion_background_context(game_state)
    if background_context:
        sections.extend([background_context, ""])
    
    # NUOVO: Affinity tier examples
    affinity_context = self._build_affinity_tier_context(companion, affinity)
    if affinity_context:
        sections.extend([affinity_context, ""])
    
    # NUOVO: Location visuals
    visual_context = self._build_location_visual_context(game_state)
    if visual_context:
        sections.extend([visual_context, ""])
```

### Step 4: Test End-to-End

Testare che le nuove sezioni appaiano nel system prompt:

```python
builder = PromptBuilder(world)
prompt = builder.build_system_prompt(game_state, ...)
print(prompt)
# Verificare presenza:
# - === COMPANION BACKGROUND ===
# - === AFFINITY LEVEL ===
# - === LOCATION VISUALS ===
```

---

## 🎯 Template per Test

```python
# Test completo situazioni
from luna.systems.world import get_world_loader
from luna.core.models import GameState, TimeOfDay
from luna.core.prompt_builder import PromptBuilder

loader = get_world_loader()
world = loader.load_world('school_life_complete')
builder = PromptBuilder(world)

# Test con Maria, Evening, school_library
game_state = GameState(
    world_id='school_life_complete',
    active_companion='Maria',
    time_of_day=TimeOfDay.EVENING,
    current_location='school_library',
    affinity={'Maria': 30}  # Tier 26-50
)

# Stampa sezioni specifiche
print("=== BACKGROUND ===")
print(builder._build_companion_background_context(game_state))

print("\n=== AFFINITY TIER ===")
companion = world.companions['Maria']
print(builder._build_affinity_tier_context(companion, 30))

print("\n=== LOCATION VISUALS ===")
print(builder._build_location_visual_context(game_state))
```

---

## ✅ Criteri Completamento

- [ ] Tutti i campi "Priorità Alta" sono trasmessi all'LLM
- [ ] Il system prompt include le nuove sezioni
- [ ] I test passano
- [ ] La documentazione è aggiornata
- [ ] Esempio di output system prompt verificato
