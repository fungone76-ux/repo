# Guida Completa: I Tre Livelli Narrativi di Luna RPG v4

**Versione:** 1.0  
**Data:** 2026-02-21  
**Scopo:** Spiegare l'architettura narrativa a tre livelli del gioco

---

## 🎯 Panoramica: La Piramide Narrativa

Luna RPG v4 utilizza un sistema narrativo a **tre livelli** che lavorano insieme per creare una storia coerente, strutturata ma flessibile:

```
┌─────────────────────────────────────────────────────────────┐
│  LIVELLO 1: STORY BEATS (Main Story)                        │
│  ├── File: _meta.yaml                                       │
│  ├── Scope: Narrativa globale del mondo                     │
│  └── Funzione: Momenti obbligatori, archi narrativi         │
├─────────────────────────────────────────────────────────────┤
│  LIVELLO 2: QUESTS (Character Stories)                      │
│  ├── File: <personaggio>.yaml                               │
│  ├── Scope: Storie individuali per personaggio              │
│  └── Funzione: Sviluppo relazioni, eventi strutturati       │
├─────────────────────────────────────────────────────────────┤
│  LIVELLO 3: GLOBAL EVENTS (World State)                     │
│  ├── File: global_events.yaml                               │
│  ├── Scope: Atmosfera mondiale, situazioni ambientali       │
│  └── Funzione: Mood, contesto, variabilità                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Tabella Comparativa

| Aspetto | Story Beats | Quests | Global Events |
|---------|-------------|--------|---------------|
| **File** | `_meta.yaml` | `maria.yaml`, `stella.yaml`, etc. | `global_events.yaml` |
| **Scope** | Mondo intero | Singolo personaggio | Mondo intero |
| **Tipo** | Momenti chiave | Storie strutturate | Situazioni atmosferiche |
| **Trigger** | Affinità personaggio | Affinità/Locazione/Flag | Random/Tempo/Locazione |
| **Ripetibilità** | ❌ No (once) | ❌ No | ✅ Sì (con cooldown) |
| **Priorità LLM** | 🔴 Alta (obbligatorio) | 🟡 Media | 🟢 Bassa (contesto) |
| **Campo LLM** | `description` | `narrative_prompt` | `narrative_prompt` |
| **Lingua** | Italiano (UI) | Inglese (LLM) | Inglese (LLM) |

---

## 🎭 LIVELLO 1: STORY BEATS (Main Story)

### Definizione
I **Story Beats** sono i **momenti narrativi obbligatori** che definiscono l'arco completo della storia. Sono la "trama principale" che deve essere rispettata.

### File
```yaml
# _meta.yaml
story_beats:
  premise: "..."           # Premessa generale
  themes: [...]            # Temi da esplorare
  hard_limits: [...]       # Vincoli assoluti
  beats:                   # Momenti chiave
    - id: "beat_id"
      description: "..."   # ⭐ Trasmesso a LLM
      trigger: "..."       # Condizione attivazione
      required_elements:   # Elementi obbligatori
        - "elemento1"
        - "elemento2"
      tone: "..."          # Tono richiesto
      once: true           # Non ripetibile
      consequence: "..."   # Effetto dopo beat
```

### Esempio Pratico
```yaml
story_beats:
  premise: |
    Storia di conquista in un liceo di provincia.
    Tre donne, tre archi: Maria (invisibile→devota), 
    Stella (snob→gelosa), Luna (rigida→trasgressiva).
  
  themes:
    - "conquista"
    - "intimità"
    - "trasgressione"
  
  hard_limits:
    - "Tutti i personaggi sono adulti consenzienti (18+)"
    - "Nessuna forza o coercizione"
  
  beats:
    - id: "maria_primo_sguardo"
      description: "Maria si accorge che qualcuno finalmente la vede come donna"
      trigger: "maria_affinity >= 20"
      required_elements: ["sguardo", "sorpresa", "arrossire"]
      tone: "awkward_intimate"
      once: true
      consequence: "maria_flag_first_noticed = true"
    
    - id: "stella_gelosia_esplosiva"
      description: "Stella esplode di gelosia e ti reclama pubblicamente"
      trigger: "stella_affinity >= 75 AND reputation.studenti > 10"
      required_elements: ["gelosia", "confronto", "possessività"]
      tone: "dramatic_possessive"
      once: true
      consequence: "stella_flag_possessive = true"
```

### Output nel System Prompt (quando attivo)
```markdown
=== MANDATORY NARRATIVE BEAT ===

=== MOMENTO NARRATIVO OBBLIGATORIO ===

Devi narrare ESATTAMENTE questo evento:
Maria si accorge che qualcuno finalmente la vede come donna

TONO RICHIESTO: awkward_intimate

ELEMENTI OBBLIGATORI (devono apparire nella scena):
  - sguardo
  - sorpresa
  - arrossire

CONTESTO ATTUALE:
  Turno: 15
  Location: school_corridor
  Companion attivo: Maria
  Affinità: 22

ISTRUZIONE: Scrivi la scena includendo TUTTI gli elementi obbligatori.
======================================

CRITICAL: Include this event in your response.
```

### Caratteristiche Chiave
- ✅ **Obbligatorio**: L'LLM DEVE narrare questo momento
- ✅ **Validato**: Python verifica che tutti gli elementi siano presenti
- ✅ **Consequenze**: Può settare flag, cambiare stati
- ✅ **Univoco**: Ogni beat (con `once: true`) accade una sola volta

---

## 📜 LIVELLO 2: QUESTS (Character Stories)

### Definizione
Le **Quests** sono **storie strutturate** legate a un singolo personaggio. Hanno stage progressivi e narrative prompts dettagliati.

### File
```yaml
# <personaggio>.yaml
quests:
  <quest_id>:              # ID univoco
    meta:
      title: "..."         # Titolo UI (italiano)
      description: "..."   # Reference (italiano)
      character: "Nome"
      hidden: false
    
    activation:
      type: "auto"
      conditions: [...]    # Condizioni attivazione
    
    stages:
      <stage_id>:
        title: "..."       # Titolo UI (italiano)
        narrative_prompt: | # ⭐ SOLO QUESTO trasmesso a LLM (inglese!)
          Describe the scene...
        on_enter: [...]    # Azioni automatiche
        exit_conditions: [...]
        transitions: [...]
    
    rewards:
      affinity: {...}
      flags: {...}
```

### Esempio Pratico
```yaml
quests:
  stella_photoshoot:
    meta:
      title: "Il Servizio Fotografico"      # Italiano (UI)
      description: "Stella ti chiede di fotografarla..."  # Italiano
      character: "Stella"
      hidden: false
    
    activation:
      type: "auto"
      conditions:
        - type: "affinity"
          target: "Stella"
          operator: "gte"
          value: 50
    
    stages:
      setup:
        title: "L'Occasione"                # Italiano (UI)
        narrative_prompt: |                  # ⭐ IN INGLESE - Trasmesso!
          Stella stops you in the corridor between classes. She's leaning 
          against the lockers with practiced nonchalance...
          
          'Hey, you,' she calls out. 'I need someone to take photos...'
          
          CRITICAL ELEMENTS:
          - Stella's tsundere attitude
          - The public school setting
          - Her body language (leaning, hair toss)
        
        exit_conditions:
          - type: "action"
            pattern: "accetta|fotografa|aiuta"
        transitions:
          - condition: "default"
            target_stage: "photoshoot"
      
      photoshoot:
        title: "Dietro l'Obiettivo"          # Italiano (UI)
        narrative_prompt: |                  # ⭐ IN INGLESE - Trasmesso!
          The empty gymnasium echoes with your footsteps...
    
    rewards:
      affinity:
        Stella: 25
      flags:
        stella_photoshoot_done: true
```

### Output nel System Prompt (quando attiva)
```markdown
=== ACTIVE QUESTS ===
Quest "Il Servizio Fotografico": Stella stops you in the corridor 
between classes. She's leaning against the lockers with practiced 
nonchalance, but there's something different in her eyes today.

'Hey, you,' she calls out. 'I need someone to take photos for 
my social. You'd be... different from the other losers.'

CRITICAL ELEMENTS:
- Stella's tsundere attitude (hiding interest with arrogance)
- The public school setting (corridor, lockers, other students)
- Her body language (leaning, hair toss, feigned indifference)
```

### Caratteristiche Chiave
- ✅ **Personaggio-specifica**: Legata a un singolo NPC
- ✅ **Stage-based**: Progressione narrativa strutturata
- ✅ **Azioni**: `on_enter` può cambiare location, outfit, stati
- ✅ **Ripetibile?**: No, una volta completata è fatta

---

## 🌍 LIVELLO 3: GLOBAL EVENTS (World State)

### Definizione
I **Global Events** sono **situazioni atmosferiche** che colpiscono l'intero mondo di gioco. Cambiano il mood e le condizioni ambientali.

### File
```yaml
# global_events.yaml
global_events:
  <event_id>:
    meta:
      title: "..."              # Titolo UI
      description: "..."        # Reference
    
    trigger:
      type: "random" | "conditional" | ...
      chance: 0.15              # Probabilità
      allowed_times: [...]      # Fasce orarie
    
    effects:
      duration: 3               # Durata turni
      atmosphere_change: "..."  # ⭐ Tono (inglese)
      visual_tags: [...]        # ⭐ Tag immagini (inglese)
      location_modifiers: [...] # Blocchi location
      on_start: [...]          # Azioni avvio
      on_end: [...]            # Azioni fine
    
    narrative_prompt: |         # ⭐ Trasmesso a LLM (inglese!)
      Describe the event...
```

### Esempio Pratico
```yaml
global_events:
  rainstorm:
    meta:
      title: "Temporale Improvviso"           # Italiano (UI)
      description: "Una pioggia torrenziale blocca tutti a scuola"
    
    trigger:
      type: "random"
      chance: 0.15
      allowed_times: ["Afternoon", "Evening"]
    
    effects:
      duration: 3
      atmosphere_change: "dramatic, trapped, intimate"  # ⭐ IN INGLESE
      visual_tags: ["rain", "wet", "dark_sky", "puddles"]
      location_modifiers:
        - location: "school_entrance"
          blocked: true
          message: "La pioggia è troppo forte per uscire."
      on_start:
        - action: "set_emotional_state"
          character: "{current_companion}"
          state: "flustered"
    
    narrative_prompt: |                          # ⭐ IN INGLESE - Trasmesso!
      Dark clouds suddenly envelop the school. Thunder rumbles through 
      the halls. Students crowd at the windows in excited chatter. 
      You are trapped at school with {current_companion}, creating an 
      intimate, inescapable atmosphere...
```

### Output nel System Prompt (quando attivo)
```markdown
=== ACTIVE WORLD EVENT ===
🌧️ Sudden Rainstorm
Atmosphere: dramatic, trapped, intimate

⚡ The event has just started!

NARRATIVE CONTEXT:
Dark clouds suddenly envelop the school. Thunder rumbles through 
the halls. Students crowd at the windows in excited chatter. 
You are trapped at school with Stella, creating an intimate, 
inescapable atmosphere...

WORLD STATE CHANGES:
• Location 'school_entrance' is BLOCKED: La pioggia è troppo forte per uscire.

VISUAL NOTES:
Scene should include: rain, wet, dark_sky, puddles
```

### Caratteristiche Chiave
- ✅ **Mondiale**: Colpisce tutto il mondo, non un singolo personaggio
- ✅ **Atmosferico**: Cambia mood, luce, condizioni
- ✅ **Ripetibile**: Può accadere più volte (con cooldown)
- ✅ **Imprevedibile**: Spesso attivazione random

---

## 🔄 ESEMPIO COMPLETO: Interazione dei Tre Livelli

### Scenario
**Condizioni:**
- Affinità con Stella: 52 (triggera sia beat che quest)
- Orario: Afternoon
- Evento attivo: `rainstorm`
- Location: `school_corridor`

**Cosa si attiva?**
1. **Story Beat**: `stella_servizio_fotografico` (affinità >= 50)
2. **Quest**: `stella_photoshoot` stage "setup" (affinità >= 50)
3. **Global Event**: `rainstorm` (random + orario)

**System Prompt risultante:**
```markdown
=== TIME OF DAY ===
Atmosphere: The heart of the school day, lessons in progress
Lighting: afternoon bright, clear sky

=== ACTIVE COMPANION ===
Name: Stella
Current Affinity: 52/100
[... altri dettagli ...]

=== AFFINITY LEVEL: 51-75 ===
Stage: The Jealous One
Tone: Possessive, controlling
Example Dialogue:
  - "Who was that girl?! Answer me!"
  - "If you don't reply in 3 seconds..."

=== LOCATION VISUALS ===
Style: lockers, posters, natural light
Lighting: indoor daylight

=== MANDATORY NARRATIVE BEAT ===          ⬅️ STORY BEAT (obbligatorio)
Devi narrare ESATTAMENTE questo evento:
Il servizio fotografico dove Stella capisce che sei diverso

TONO RICHIESTO: tense_romantic
ELEMENTI OBBLIGATORI:
  - fotocamera
  - sguardo
  - cambiamento

=== ACTIVE QUESTS ===                     ⬅️ QUEST (situazione)
Quest "Il Servizio Fotografico": Stella stops you in the corridor...
'Hey, you, I need someone to take photos...'

=== ACTIVE WORLD EVENT ===                ⬅️ GLOBAL EVENT (atmosfera)
🌧️ Sudden Rainstorm
Atmosphere: dramatic, trapped, intimate
NARRATIVE CONTEXT: Dark clouds suddenly envelop the school...
```

**Cosa fa l'LLM?**
L'LLM riceve **tutti e tre** i livelli e deve integrarli:
1. **Story Beat**: DEVE includere il momento della "rivelazione" con fotocamera
2. **Quest**: DEVE usare il setup della quest (Stella nel corridoio)
3. **Global Event**: DEVE includere la pioggia che blocca tutti a scuola

**Narrativa risultante (esempio):**
> The afternoon light cuts through the sudden storm clouds as Stella 
> corners you by the lockers. Rain drums against the windows, trapping 
> everyone inside. 'Perfect weather for indoor photos, don't you think?' 
> She holds out her camera, but her eyes study you differently now—not 
> as another admirer, but as someone who sees *her*. The way you look 
> at her through the lens... it's not hunger, it's attention. For the 
> first time, she lowers her gaze first.

---

## 📋 CONVENZIONI LINGUA

### Story Beats
| Campo | Lingua | Esempio |
|-------|--------|---------|
| `premise` | **Inglese** | "Story of conquest in a provincial high school..." |
| `themes` | **Inglese** | "conquest", "intimacy", "transgression" |
| `hard_limits` | **Inglese** | "All characters are consenting adults (18+)" |
| `beats.*.description` | **Inglese** | "Maria realizes someone finally sees her as a woman" |
| `meta.title` (event) | Italiano | "Temporale Improvviso" |

### Quests
| Campo | Lingua | Esempio |
|-------|--------|---------|
| `meta.title` | Italiano | "Il Servizio Fotografico" |
| `meta.description` | Italiano | "Stella ti chiede di fotografarla..." |
| `stages.*.title` | Italiano | "L'Occasione" |
| `stages.*.narrative_prompt` | **Inglese** | "Stella stops you in the corridor..." |

### Global Events
| Campo | Lingua | Esempio |
|-------|--------|---------|
| `meta.title` | Italiano | "Temporale Improvviso" |
| `meta.description` | **Inglese** | "A heavy rainstorm traps everyone at school" |
| `effects.atmosphere_change` | **Inglese** | "dramatic, trapped, intimate" |
| `narrative_prompt` | **Inglese** | "Dark clouds suddenly envelop..." |

---

## ✅ CHECKLIST CREAZIONE WORLD

Quando crei un nuovo world, verifica:

### Story Beats (`_meta.yaml`)
- [ ] `premise` definito (in inglese)
- [ ] `themes` elencati (in inglese)
- [ ] `hard_limits` specificati (in inglese)
- [ ] Almeno 2-3 beats per personaggio principale
- [ ] Ogni beat ha `trigger` valido
- [ ] Ogni beat ha `required_elements`
- [ ] Ogni beat ha `tone` appropriato

### Quests (`<personaggio>.yaml`)
- [ ] 2-4 quest per personaggio principale
- [ ] Ogni quest ha `activation.conditions`
- [ ] Ogni stage ha `narrative_prompt` in inglese
- [ ] `narrative_prompt` include Critical Elements
- [ ] Transizioni logiche tra stage

### Global Events (`global_events.yaml`)
- [ ] 3-6 eventi vari (meteo, situazioni, etc.)
- [ ] Eventi diversi per orario (giorno/notte)
- [ ] `narrative_prompt` in inglese
- [ ] `atmosphere_change` in inglese
- [ ] `visual_tags` appropriati

---

## 📚 DOCUMENTAZIONE CORRELATA

- `EVENT_SYSTEM_SPEC.md` - Dettagli Global Events
- `QUEST_SPECIFICATION.md` - Dettagli Quests
- `WORLD_CREATION_GUIDE.md` - Guida creazione mondi
- `LLM_CONTEXT_SPEC.md` - Trasmissione contesto LLM

---

## 🎮 RIASSUNTO FINALE

| Se vuoi... | Usa... | File |
|------------|--------|------|
| Momenti narrativi **obbligatori** | **Story Beats** | `_meta.yaml` |
| Storie strutturate per **personaggio** | **Quests** | `<personaggio>.yaml` |
| **Atmosfera** e situazioni ambientali | **Global Events** | `global_events.yaml` |

**Regola d'oro:** Tutti e tre i sistemi coesistono e si integrano nel system prompt per creare una narrativa ricca, strutturata ma flessibile!
