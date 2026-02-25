# Contesto LLM Completo - Situazioni Trasmesse

**Versione:** 2.0  
**Data:** 2026-02-21  
**Stato:** ✅ COMPLETO

---

## 🎯 Panoramica

Il sistema trasmette all'LLM **tutte le situazioni rilevanti** definite nei file YAML del world, garantendo coerenza narrativa.

---

## 📋 ELENCO COMPLETO SITUAZIONI

### 1. 🌍 World Context
**Fonte:** `_meta.yaml`

| Campo | Stato | Esempio |
|-------|-------|---------|
| `meta.lore` | ✅ | "A provincial high school where lives intertwine..." |
| `meta.genre` | ✅ | "Slice of Life, Romance" |
| `meta.description` | ✅ | "A new student transfers to Leonardo da Vinci high school..." |

---

### 2. 🕐 Time Context
**Fonte:** `time.yaml`

| Campo | Stato | Esempio |
|-------|-------|---------|
| `time.<slot>.ambient_description` | ✅ | "School is over, clubs are active, secret meetings begin" |
| `time.<slot>.lighting` | ✅ | "sunset colors, orange sky, golden hour" |

**Output nel prompt:**
```markdown
=== TIME OF DAY ===
Atmosphere: School is over, clubs are active, secret meetings begin
Lighting: sunset colors, orange sky, golden hour
```

---

### 3. 🗺️ Location Context
**Fonte:** `locations.yaml`

| Campo | Stato | Esempio |
|-------|-------|---------|
| `locations.<id>.name` | ✅ | "Biblioteca" (UI) |
| `locations.<id>.description` | ✅ | "Shelves full of books, study tables, solemn silence" |
| `locations.<id>.visual_style` | ✅ | "bookshelves, reading lamps, quiet" |
| `locations.<id>.lighting` | ✅ | "soft indoor" |
| `locations.<id>.time_descriptions.<time>` | ✅ | "Total silence. Only a few diligent students... and you two" |

**Output nel prompt:**
```markdown
=== CURRENT SITUATION ===
Location: school_library
Time: Evening

=== LOCATION ATMOSPHERE ===
Total silence. Only a few diligent students... and you two

=== LOCATION VISUALS ===
Style: bookshelves, reading lamps, quiet
Lighting: soft indoor
```

---

### 4. 👤 Companion Context
**Fonte:** `maria.yaml`, `stella.yaml`, `luna.yaml`

#### 4.1 Base Info
| Campo | Stato | Esempio |
|-------|-------|---------|
| `name` | ✅ | "Maria" |
| `role` | ✅ | "Cleaning Lady" |
| `age` | ✅ | 42 |
| `base_personality` | ✅ | "Timid, insecure, feels invisible" |
| `base_prompt` | ✅ | "score_9, stsSmith, mature female..." |

#### 4.2 Background & Relationship ⭐ NUOVO
| Campo | Stato | Esempio |
|-------|-------|---------|
| `background` | ✅ **NEW** | "Worked at the school for 15 years, no one ever noticed the woman beyond the uniform" |
| `relationship_to_player` | ✅ **NEW** | "The protagonist is the first who treats her as a woman and defends her" |

**Output nel prompt:**
```markdown
=== COMPANION BACKGROUND ===
History: Worked at the school for 15 years, no one ever noticed the woman beyond the uniform
Relationship Dynamic: The protagonist is the first who treats her as a woman and defends her
```

#### 4.3 Emotional State
| Campo | Stato | Esempio |
|-------|-------|---------|
| `state name` | ✅ | "grateful" |
| `description` | ✅ | "Grateful for the defense/attention" |
| `dialogue_tone` | ✅ | "Grateful to the point of tears" |

**Output nel prompt:**
```markdown
=== EMOTIONAL STATE ===
State: grateful
Description: Grateful for the defense/attention
Dialogue Style: Grateful to the point of tears
```

#### 4.4 Affinity Tier ⭐ NUOVO
| Campo | Stato | Esempio |
|-------|-------|---------|
| `tier range` | ✅ | "26-50" |
| `name` | ✅ | "The Surprise" |
| `tone` | ✅ | "Incredulous that someone speaks kindly to her" |
| `examples` | ✅ **NEW** | "Why are you so kind to me?", "No one ever helps me..." |
| `voice_markers` | ✅ **NEW** | "Excessive gratitude", "Insecurity about attractiveness" |

**Output nel prompt:**
```markdown
=== AFFINITY LEVEL: 26-50 ===
Stage: The Surprise
Tone: Incredulous that someone speaks kindly to her

Example Dialogue:
  - "Why are you so kind to me?"
  - "No one ever helps me..."

Voice Markers:
  • Excessive gratitude
  • Insecurity about attractiveness
```

---

### 5. 📖 Story Beats
**Fonte:** `_meta.yaml`

| Campo | Stato | Esempio |
|-------|-------|---------|
| `premise` | ✅ | "Story of conquest and maturation in a provincial high school" |
| `themes` | ✅ | "conquest", "intimacy", "eros", "transgression" |
| `hard_limits` | ✅ | "All characters are consenting adults (18+)" |
| `active beat` | ✅ | "Maria notices someone finally sees her as a woman" |

---

### 6. 📜 Quests
**Fonte:** file companion (`maria.yaml`, etc.)

| Campo | Stato | Esempio |
|-------|-------|---------|
| `narrative_prompt` (stage) | ✅ | "A student insults Maria for dropping his books. The protagonist intervenes..." |

---

### 7. 🌍 Global Events
**Fonte:** `global_events.yaml`

| Campo | Stato | Esempio |
|-------|-------|---------|
| `title` | ✅ | "Sudden Rainstorm" |
| `atmosphere_change` | ✅ | "dramatic, trapped, intimate" |
| `narrative_prompt` | ✅ | "Dark clouds suddenly envelop the school..." |
| `visual_tags` | ✅ | "rain", "wet", "dark_sky" |

**Output nel prompt:**
```markdown
=== ACTIVE WORLD EVENT ===
🌧️ Sudden Rainstorm
Atmosphere: dramatic, trapped, intimate

NARRATIVE CONTEXT:
Dark clouds suddenly envelop the school. Thunder rumbles...
```

---

## 📝 Esempio Completo System Prompt

```markdown
=== LUNA RPG - SYSTEM INSTRUCTIONS ===

Genre: Slice of Life, Romance, Erotic (18+)
World: Provincial School

=== WORLD ===
The Liceo "Leonardo da Vinci" is a historic institute in an Italian provincial town...

=== ACTIVE COMPANION ===
Name: Maria
Role: Cleaning Lady
Age: 42
Personality: Timid, insecure, feels invisible...
Current Affinity: 30/100

=== EMOTIONAL STATE ===
State: grateful
Description: Grateful for the defense/attention
Dialogue Style: Grateful to the point of tears

=== COMPANION BACKGROUND ===
History: Worked at the school for 15 years, no one ever noticed the woman beyond the uniform
Relationship Dynamic: The protagonist is the first who treats her as a woman and defends her

=== AFFINITY LEVEL: 26-50 ===
Stage: The Surprise
Tone: Incredulous that someone speaks kindly to her

Example Dialogue:
  - "Why are you so kind to me?"
  - "No one ever helps me..."

Voice Markers:
  • Excessive gratitude
  • Insecurity about attractiveness

=== CHARACTER BASE PROMPT (CRITICAL FOR IMAGES) ===
BASE PROMPT: score_9, score_8_up, stsSmith, ultra-detailed...

=== CURRENT SITUATION ===
Location: school_library
Time: Evening
Turn: 15
Outfit: cleaning_uniform

=== TIME OF DAY ===
Atmosphere: School is over, clubs are active, secret meetings begin
Lighting: sunset colors, orange sky, golden hour

=== LOCATION ATMOSPHERE ===
Total silence. Only a few diligent students... and you two

=== LOCATION VISUALS ===
Style: bookshelves, reading lamps, quiet
Lighting: soft indoor

=== ACTIVE QUESTS ===
Quest "The Defense": A student insults Maria for dropping his books...

[CRITICAL GAMEPLAY RULES...]
[OUTPUT FORMAT...]
```

---

## ✅ Checklist Implementazione

### Completato ✅
- [x] World lore/description
- [x] Time slot context (ambient_description, lighting)
- [x] Location base description
- [x] Location time descriptions
- [x] Location visual style
- [x] Companion base info
- [x] **Companion background (NEW)**
- [x] **Companion relationship (NEW)**
- [x] Emotional state (description, dialogue_tone)
- [x] **Affinity tier examples (NEW)**
- [x] **Affinity tier voice markers (NEW)**
- [x] Story beats (premise, themes, hard_limits)
- [x] Quest narrative prompts
- [x] Global events (complete)

### Modello Dati Aggiornato ✅
- [x] `CompanionDefinition.background`
- [x] `CompanionDefinition.relationship_to_player`
- [x] `WorldLoader` carica `core_traits`

---

## 🔮 Futuri Miglioramenti (Priorità Bassa)

1. **Schedule Activity**: Cosa sta facendo il companion ora
2. **Dynamic Location States**: crowded, empty, locked
3. **Player Character Background**: Storia del protagonista
4. **Gameplay Actions**: Azioni sbloccate per tier

---

## 📚 Documentazione Correlata

- `docs/EVENT_SYSTEM_SPEC.md` - Schema eventi
- `docs/LLM_CONTEXT_SPEC.md` - Specifica completa contesto
- `docs/IMPLEMENTATION_PLAN.md` - Piano implementazione
- `docs/WORLD_CREATION_GUIDE.md` - Guida creazione mondi
