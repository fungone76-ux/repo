# Analisi Contesto LLM - Cosa Deve Essere Trasmesso

## 📊 Stato Attuale: Trasmissione al LLM

### ✅ GIÀ TRASMESSO

| Sorgente | Campo | Stato | Note |
|----------|-------|-------|------|
| `_meta.yaml` | `lore` | ✅ | Incluso nel system prompt |
| `_meta.yaml` | `description` | ✅ | Fallback se lore manca |
| `_meta.yaml` | `genre` | ✅ | Header system prompt |
| Companion | `base_personality` | ✅ | In companion context |
| Companion | `emotional_state` (nome) | ✅ | Solo nome dello stato |
| Companion | `dialogue_tone` (tone) | ✅ | Solo stringa tone |
| Companion | `wardrobe` | ✅ | Solo nomi outfit |
| Companion | `base_prompt` | ✅ | CRITICAL per immagini |
| Global Events | Tutti i campi | ✅ | Event System v1.0 completo |
| Story Beats | `premise` | ✅ | Via StoryDirector |
| Story Beats | `themes` | ✅ | Via StoryDirector |
| Story Beats | `hard_limits` | ✅ | Via StoryDirector |
| Story Beats | `beat` attivo | ✅ | Via StoryDirector |
| Quests | `narrative_prompt` stage | ✅ | Via QuestEngine |
| Location | `name`, `description` | ✅ | Via LocationManager |
| Game State | `time_of_day` | ✅ | Solo valore (es. "Evening") |

---

### ⚠️ NON TRASMESSO (MA PRESENTE NEI YAML)

#### 1. **Time Slots - Ambient Descriptions** 
**File:** `time.yaml`

```yaml
time:
  Evening:
    name: "Sera"
    lighting: "sunset colors, orange sky, golden hour"
    ambient_description: "Scuola finita, club attivi, incontri segreti."  # ❌ NON TRASMESSO
```

**Problema:** Il tempo viene menzionato come "Evening" ma non viene trasmesso:
- `lighting` - Per coerenza visiva immagini
- `ambient_description` - Per atmosfera narrativa

**Impatto:** L'LLM non sa che "Evening" significa "scuola finita, club attivi, incontri segreti"

---

#### 2. **Emotional States Dettagliati**
**File:** `maria.yaml`, `stella.yaml`, `luna.yaml`

```yaml
emotional_states:
  grateful:
    description: "Grata per la difesa/d attenzione"  # ❌ NON TRASMESSO
    dialogue_tone: "Riconoscente al limite delle lacrime"  # ❌ NON TRASMESSO
    trigger_flags: ["maria_defended"]  # ❌ NON TRASMESSO
```

**Problema:** Solo il nome dello stato emotivo viene trasmesso:
```
Emotional State: grateful
```

Ma mancano:
- La descrizione dello stato (per contesto LLM)
- Il tone specifico del dialogo
- I trigger flags che hanno causato lo stato

**Impatto:** L'LLM sa che Maria è "grateful" ma non sa cosa significa per il suo comportamento

---

#### 3. **Affinity Tiers Dettagliati**
**File:** `maria.yaml`, `stella.yaml`, `luna.yaml`

```yaml
affinity_tiers:
  "26-50":
    name: "La Sorpresa"
    tone: "Incredula che qualcuno le parli gentilmente"
    examples:  # ❌ NON TRASMESSI
      - "Perché sei così gentile con me?"
      - "Nessuno mi aiuta mai..."
    voice_markers:  # ❌ NON TRASMESSI
      - "Gratitudine eccessiva"
      - "Insicurezza sulla propria attrattiva"
```

**Problema:** Solo il `tone` viene estratto (parzialmente), ma mancano:
- Esempi di dialogo specifici
- Voice markers (pattern linguistici)
- Nome del tier (es. "La Sorpresa")

**Impatto:** L'LLM non ha esempi concreti di come parlare il personaggio a quel livello di affinità

---

#### 4. **Location Time Descriptions**
**File:** `locations.yaml`

```yaml
school_library:
  time_descriptions:  # ❌ NON TRASMESSO
    Evening: "Silenzio totale. Solo qualche studente diligente... e voi due."
```

**Problema:** Le location hanno descrizioni diverse in base all'orario, ma solo la descrizione base viene trasmessa.

**Impatto:** Biblioteca di sera ha la stessa descrizione di Biblioteca di mattina

---

#### 5. **Location Dynamic States**
**File:** `locations.yaml`

```yaml
school_corridor:
  dynamic_descriptions:  # ❌ NON TRASMESSO
    crowded: "Il corridoio è stracolmo di studenti. Difficile muoversi."
    empty: "Il corridoio è deserto. I tuoi passi echeggiano."
```

**Problema:** Gli stati dinamici (crowded, empty, etc.) non vengono trasmessi all'LLM

**Impatto:** L'LLM non sa se la location è affollata o vuota

---

#### 6. **Personality System - Core Traits**
**File:** `maria.yaml`, `stella.yaml`, `luna.yaml`

```yaml
personality_system:
  core_traits:
    role: "Bidella"  # ✅ Già in companion.role
    age: "42"  # ✅ Già in companion.age
    base_personality: "..."  # ✅ Già incluso
    background: "Lavora nella scuola da 15 anni..."  # ❌ NON TRASMESSO
    relationship_to_player: "Il protagonista è il primo..."  # ❌ NON TRASMESSO
```

**Problema:** `background` e `relationship_to_player` non sono trasmessi

**Impatto:** L'LLM manca del contesto storico della relazione

---

#### 7. **Schedule/Activity (Living World)**
**File:** `maria.yaml`, `stella.yaml`, `luna.yaml`

```yaml
schedule:
  Morning:
    preferred_location: "school_corridor"
    outfit: "cleaning_uniform"
    activity: "Pulizie mattutine nei corridoi"  # ❌ NON TRASMESSO
```

**Problema:** L'attività corrente del personaggio non viene trasmessa

**Impatto:** L'LLM non sa cosa sta facendo Maria quando il player la incontra

---

#### 8. **Gameplay Systems Configuration**
**File:** `_meta.yaml`

```yaml
gameplay_systems:
  affinity:
    tiers:  # ❌ NON TRASMESSO (dettagli)
      - threshold: 50
        name: "Amico"
        unlocked_actions: ["flirt", "regalo", "abbraccio"]  # ❌ NON TRASMESSO
```

**Problema:** Le azioni sbloccate non sono trasmesse all'LLM

**Impatto:** L'LLM non sa che azioni sono disponibili a quel livello di affinità

---

## 🎯 Priorità di Implementazione

### 🔴 ALTA (Impatto Narrativo Maggiore)

1. **Time Slots - Ambient Descriptions**
   - Aggiungere al prompt builder
   - Usare `world.time_slots[game_state.time_of_day].ambient_description`
   - Include anche `lighting` per coerenza immagini

2. **Emotional States Dettagliati**
   - Aggiungere `description` e `dialogue_tone` al companion context
   - Lookup dallo YAML basato su `npc_state.emotional_state`

3. **Location Time Descriptions**
   - Usare descrizione appropriata in base all'orario
   - Fallback a descrizione base se time_description manca

### 🟡 MEDIA (Migliora Coerenza)

4. **Affinity Tiers - Examples & Voice Markers**
   - Aggiungere esempi di dialogo al companion context
   - Aiuta l'LLM a imitare lo stile corretto

5. **Personality System - Background & Relationship**
   - Aggiungere `background` e `relationship_to_player`
   - Contesto storico per relazioni più profonde

### 🟢 BASSA (Nice to Have)

6. **Location Dynamic States**
   - Richiede tracking stato dinamico location
   - Aggiungere `current_state` a LocationInstance

7. **Schedule Activity**
   - Aggiungere attività corrente al companion context
   - Richiede check schedule basato su time_of_day

8. **Gameplay Systems - Unlocked Actions**
   - Aggiungere azioni sbloccate al prompt
   - Utile per gameplay hints

---

## 💡 Raccomandazioni Immediate

### Implementare Subito:

```python
# In PromptBuilder.build_system_prompt() - aggiungere:

# 1. Time Slot Context
time_slot = self.world.time_slots.get(game_state.time_of_day)
if time_slot:
    sections.extend([
        "=== TIME OF DAY ===",
        f"Period: {time_slot.time_of_day.value}",
        f"Atmosphere: {time_slot.ambient_description}",
        f"Lighting: {time_slot.lighting}",  # Per immagini
        "",
    ])

# 2. Emotional State Dettagliato
companion_def = self.world.companions.get(game_state.active_companion)
if companion_def and npc_state:
    emotional_state_def = companion_def.emotional_states.get(npc_state.emotional_state)
    if emotional_state_def:
        sections.extend([
            "=== EMOTIONAL STATE ===",
            f"State: {npc_state.emotional_state}",
            f"Description: {emotional_state_def.description}",
            f"Dialogue Tone: {emotional_state_def.dialogue_tone}",
            "",
        ])

# 3. Location Time Description
location_def = self.world.locations.get(game_state.current_location)
if location_def:
    time_desc = location_def.time_descriptions.get(game_state.time_of_day)
    if time_desc:
        sections.extend([
            "=== LOCATION ATMOSPHERE ===",
            time_desc,
            "",
        ])
```

---

## 📋 Checklist Implementazione

- [ ] **TimeSlot Context Builder** - Trasmettere ambient_description e lighting
- [ ] **EmotionalState Context Builder** - Trasmettere description e dialogue_tone
- [ ] **LocationTime Context Builder** - Trasmettere time_descriptions
- [ ] **AffinityTier Context Builder** - Trasmettere examples e voice_markers
- [ ] **Personality Background** - Aggiungere background e relationship_to_player
- [ ] **Validazione** - Verificare coerenza narrativa con test
