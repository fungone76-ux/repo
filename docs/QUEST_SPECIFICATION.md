# SPECIFICA FORMALE: Quest System - Trasmissione LLM

**Versione:** 1.0  
**Data:** 2026-02-21  
**Stato:** Standard per tutti i world Luna RPG v4

---

## 🎯 PRINCIPIO FONDAMENTALE

Le quest nei file personaggio DEVONO seguire questo schema per garantire coerenza narrativa e corretta trasmissione all'LLM.

```
┌─────────────────────────────────────────────────────────────────┐
│  YAML Quest Definition                                          │
│     ↓                                                           │
│  WorldLoader → QuestDefinition (validazione)                    │
│     ↓                                                           │
│  QuestEngine → Attivazione e gestione stage                     │
│     ↓                                                           │
│  GameEngine → Estrazione narrative_prompt attivo                │
│     ↓                                                           │
│  PromptBuilder → "=== ACTIVE QUESTS ==="                        │
│     ↓                                                           │
│  LLM genera risposta coerente con la situazione quest           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 SCHEMA YAML STANDARD

```yaml
# File: <personaggio>.yaml

quests:
  <quest_id>:                       # ID univoco (snake_case)
    # ============================================================
    # SEZIONE META (Informative - NON trasmesse a LLM)
    # ============================================================
    meta:
      title: "Titolo Italiano"      # UI/Quest Log - Italiano OK
      description: "Descrizione..." # Reference autore - Italiano OK
      character: "NomePersonaggio"  # Link al companion
      hidden: false                 # Visibilità in UI
    
    # ============================================================
    # ATTIVAZIONE (Meccanica - NON trasmessa a LLM)
    # ============================================================
    activation:
      type: "auto" | "manual" | "trigger"
      conditions:                   # Valutate da QuestEngine
        - type: "affinity" | "location" | "time" | "flag" | ...
          target: "NomePersonaggio"
          operator: "gte" | "eq" | ...
          value: 50
    
    # ============================================================
    # SEZIONE STAGES (CRITICA - Trasmessa a LLM)
    # ============================================================
    stages:
      <stage_id>:                   # ID stage (es. "start", "confronto", "finale")
        
        # --- Campi Informativi (NON trasmessi) ---
        title: "Titolo Stage"       # UI/Log - Italiano OK
        description: "..."          # Reference - Italiano OK
        
        # ⭐ CAMPO CRITICO: Istruzioni narrative per LLM
        # DEVE essere in INGLESE
        narrative_prompt: |
          Describe the scene vividly. The character approaches you nervously 
          in the empty classroom. 'I... I need to tell you something,' she 
          stammers, clutching her bag. Golden hour light filters through 
          the windows, illuminating dust particles. The atmosphere is heavy 
          with unspoken tension.
          
          CRITICAL ELEMENTS TO INCLUDE:
          - Character's nervous body language
          - The hesitation in her voice
          - The intimate setting
          - Her eventual confession of feelings
        
        # --- Azioni Meccaniche (NON trasmesse) ---
        on_enter:                   # Azioni all'ingresso stage
          - action: "set_location"
            target: "school_classroom"
          - action: "set_emotional_state"
            character: "NomePersonaggio"
            value: "flustered"
        
        on_exit: []                 # Azioni all'uscita
        
        # --- Condizioni (Valutate da Python) ---
        exit_conditions:
          - type: "action"
            pattern: "ascolta|accetta|aiuta"
          - type: "turn_count"
            operator: "gte"
            value: 3
        
        # --- Transizioni (Gestite da Python) ---
        transitions:
          - condition: "default"
            target_stage: "next_stage"  # o "_complete", "_fail"
    
    # ============================================================
    # RICOMPENSE (Meccaniche - NON trasmesse)
    # ============================================================
    rewards:
      affinity:
        NomePersonaggio: 25
      flags:
        quest_completata: true
```

---

## 🔤 CONVENZIONE LINGUA

### IN INGLESE (Trasmesso a LLM)

| Campo | Motivo | Esempio |
|-------|--------|---------|
| `stages.<id>.narrative_prompt` | Istruzioni narrative dirette | "The character approaches you nervously..." |

### IN ITALIANO (Reference autore/UI)

| Campo | Motivo | Esempio |
|-------|--------|---------|
| `meta.title` | Visualizzazione UI/Quest Log | "Il Servizio Fotografico" |
| `meta.description` | Reference per autore world | "Stella ti chiede di fotografarla..." |
| `stages.<id>.title` | Visualizzazione stage in UI | "L'Occasione" |
| `stages.<id>.description` | Reference per autore | "Stella ti ferma nel corridoio..." |

---

## 🎨 FORMATO narrative_prompt

Il campo `narrative_prompt` è l'**UNICO** campo della quest trasmesso all'LLM. Deve essere formattato correttamente:

### Template Standard

```yaml
narrative_prompt: |
  [SCENE SETTING - Where, when, atmosphere]
  Describe the scene setting vividly. Location details, lighting, time of day.
  
  [CHARACTER STATE - Emotional/physical state]
  The character is in emotional state X. Describe body language, facial expressions.
  
  [ACTION/EVENT - What happens]
  The character approaches/does/says something specific.
  Direct dialogue in quotes: 'What the character says to initiate'
  
  [CRITICAL ELEMENTS - Must include]
  - Specific action 1
  - Specific action 2
  - Atmosphere detail
  
  [PLAYER CHOICE CONTEXT - Implicit or explicit]
  The player can respond by... / The scene leads to...
```

### Esempi per Tipo di Quest

#### 1. Incontro/Rivelazione
```yaml
narrative_prompt: |
  In the quiet library at sunset, dust particles dance in the golden light 
  filtering through tall windows.
  
  Maria approaches you hesitantly, her cleaning cart forgotten. She wrings 
  her hands, unable to meet your eyes at first. When she finally looks up, 
  her eyes are wet with unshed tears.
  
  'Fifteen years,' she whispers, voice trembling. 'Fifteen years and you're 
  the first person to see me... really see me.' She takes a shaky breath.
  'I don't know what to do with that.'
  
  CRITICAL ELEMENTS:
  - Maria's nervous body language (wrung hands, downcast eyes)
  - The emotional weight of her confession
  - The intimate, private setting of the library
  - Her vulnerability and confusion
  - The historical context (15 years invisible)
```

#### 2. Conflitto/Confronto
```yaml
narrative_prompt: |
  The school corridor is packed with students changing classes, but Stella 
  cuts through the crowd like a storm. She grabs your arm, her grip surprisingly 
  strong.
  
  Her eyes flash with anger, but beneath it lies genuine hurt. 'WHO WAS SHE?' 
  she demands, voice rising above the hallway chaos. Students turn to stare. 
  Stella doesn't care—her focus is entirely on you, possessive and desperate.
  
  'I saw you laughing with her. Touching her arm.' Her voice cracks slightly. 
  'You think this is a game? I'm not one of your groupies you can discard.'
  
  CRITICAL ELEMENTS:
  - Public setting (crowded corridor, students watching)
  - Stella's physical action (grabbing arm, possessive)
  - The mix of anger and vulnerability
  - Accusatory dialogue with genuine fear underneath
  - Social pressure from onlookers
```

#### 3. Intimità/Romantica
```yaml
narrative_prompt: |
  Luna's office is small, intimate, lit only by her desk lamp. The door is 
  closed—the first time you've been alone together without the pretense of 
  tutoring.
  
  She stands closer than propriety allows, her professor persona cracking. 
  The divorce papers on her desk corner are visible, a silent testament to 
  her isolation. Her perfume—something sophisticated and subtle—fills the 
  warm air between you.
  
  'I shouldn't...' she starts, but doesn't move away. Her hand reaches out, 
  hesitates, then rests on your chest. 'Tell me to stop. Please.' But her 
  eyes beg you to stay.
  
  CRITICAL ELEMENTS:
  - Intimate setting (closed door, warm lighting)
  - Luna's internal conflict (professional vs personal)
  - Physical proximity and tension
  - The forbidden nature of the moment
  - Her explicit request contrasted with her true desire
```

---

## ⚙️ CICLO DI VITA QUEST

### 1. Definizione (YAML)
```yaml
quests:
  maria_confession:
    meta: {...}
    stages:
      approach:          # Stage iniziale
        narrative_prompt: "..."  # Questo viene trasmesso
```

### 2. Attivazione (QuestEngine)
- Condizioni soddisfatte (es. affinity >= 50)
- Quest diventa "active"
- Stage iniziale caricato

### 3. Trasmissione LLM (GameEngine → PromptBuilder)
```python
# QuestEngine fornisce
narrative_context = "Quest 'Il Servizio Fotografico': [narrative_prompt dello stage attivo]"

# PromptBuilder lo inserisce nel system prompt
=== ACTIVE QUESTS ===
Quest "Il Servizio Fotografico": Stella ti ferma nel corridoio...
```

### 4. Cambio Stage
- Player soddisfa `exit_conditions`
- `on_enter` del nuovo stage eseguito
- Nuovo `narrative_prompt` caricato
- LLM riceve il nuovo contesto

---

## ✅ CHECKLIST VALIDAZIONE QUEST

Prima di considerare una quest completa, verificare:

- [ ] `quest_id` è univoco e in snake_case
- [ ] `meta.title` è descrittivo (italiano OK)
- [ ] `activation.conditions` sono logiche e testabili
- [ ] **Ogni stage ha `narrative_prompt`** (in INGLESE!)
- [ ] `narrative_prompt` include:
  - [ ] Scene setting (dove, quando, atmosfera)
  - [ ] Character state (emozioni, body language)
  - [ ] Azione/dialogo iniziale
  - [ ] Critical elements (cosa DEVE includere la scena)
- [ ] `exit_conditions` sono chiare
- [ ] `transitions` puntano a stage esistenti o "_complete"/"_fail"
- [ ] `rewards` sono bilanciate

---

## 🚫 ERRORI COMUNI

### ❌ ERRORE 1: `narrative_prompt` in italiano
```yaml
# SBAGLIATO
narrative_prompt: "Stella ti ferma nel corridoio..."

# CORRETTO
narrative_prompt: "Stella stops you in the corridor..."
```

### ❌ ERRORE 2: `narrative_prompt` mancante
```yaml
# SBAGLIATO
stages:
  start:
    title: "Inizio"
    # Manca narrative_prompt!

# CORRETTO
stages:
  start:
    title: "Inizio"
    narrative_prompt: "Describe the scene where..."
```

### ❌ ERRORE 3: `narrative_prompt` troppo breve
```yaml
# SBAGLIATO - Insufficiente per LLM
narrative_prompt: "Stella è arrabbiata."

# CORRETTO - Dettagliato
narrative_prompt: |
  Stella corners you in the empty classroom after hours. Her usual composure 
  is shattered—hands shaking, eyes rimmed red. 'You think you can just play 
  with me?' Her voice cracks. 'I'm not one of your conquests.' But her 
  trembling gives away her true feelings...
```

### ❌ ERRORE 4: Target stage inesistente
```yaml
# SBAGLIATO
transitions:
  - condition: "default"
    target_stage: "finale"  # Non esiste!

# CORRETTO
transitions:
  - condition: "default"
    target_stage: "conclusion"  # Esiste nella lista stages
```

---

## 📚 ESEMPIO COMPLETO: Quest Validata

```yaml
quests:
  maria_confession:
    meta:
      title: "La Confessione di Maria"
      description: "Maria confessa la sua solitudine e si offre completamente"
      character: "Maria"
      hidden: false
    
    activation:
      type: "auto"
      conditions:
        - type: "affinity"
          target: "Maria"
          operator: "gte"
          value: 85
        - type: "location"
          operator: "eq"
          value: "maria_home"
    
    stages:
      
      approach:
        title: "Il Momento"
        narrative_prompt: |
          Maria's small apartment is warm and intimate, the smell of her pasta 
          al forno still lingering. She's changed into a simple dress—something 
          she clearly doesn't wear often, tugging at it self-consciously.
          
          The dinner is done, the silence between you heavy with unspoken tension. 
          Maria wrings a dish towel, then suddenly drops it, approaching you with 
          determination that wars with her fear.
          
          'I know I'm old,' she starts, voice barely above a whisper. 'I know I'm 
          not beautiful like those young girls. But...' Her eyes lift to yours, 
          desperate and devoted. 'No one will ever love you like I can. I'm yours. 
          Completely. Just... don't send me away.'
          
          CRITICAL ELEMENTS:
          - Maria's vulnerability and insecurity about age/appearance
          - The domestic, intimate setting
          - Her explicit offering of total devotion
          - The desperation beneath her courage
          - The contrast between her self-doubt and absolute love
        
        exit_conditions:
          - type: "turn_count"
            operator: "gte"
            value: 3
        transitions:
          - condition: "default"
            target_stage: "response"
      
      response:
        title: "La Risposta"
        narrative_prompt: |
          Maria waits, trembling, for your response. Her hands clench and unclench 
          at her sides. She looks ready to flee or faint depending on what you say.
          
          The apartment feels too small, the air too thick. Every second of silence 
          seems to physically wound her.
          
          CRITICAL ELEMENTS:
          - Her anxious waiting
          - Physical signs of stress (trembling, clenched hands)
          - The charged silence
          - Player's response determines her emotional trajectory
        
        exit_conditions:
          - type: "turn_count"
            operator: "gte"
            value: 2
        transitions:
          - condition: "default"
            target_stage: "_complete"
    
    rewards:
      affinity:
        Maria: 30
      flags:
        maria_confessed_love: true
        maria_devoted: true
```

---

## 🔄 INTEGRAZIONE CON ALTRI SISTEMI

### Relazione con Story Beats
- Le quest possono sbloccare story beats tramite flags
- Esempio: `maria_confessed_love` flag triggera beat "Maria Devotion"

### Relazione con Emotional States
- `on_enter` può cambiare `emotional_state`
- Esempio: `"set_emotional_state": "devoted"`

### Relazione con Location
- `on_enter` può spostare player: `"set_location": "maria_home"`
- Questo aggiorna anche il location context per LLM

---

## 📖 DOCUMENTAZIONE CORRELATA

- `WORLD_CREATION_GUIDE.md` - Guida completa creazione mondi
- `EVENT_SYSTEM_SPEC.md` - Eventi globali
- `LLM_CONTEXT_SPEC.md` - Contesto LLM generale

---

## ✅ APPROVAZIONE SPECIFICA

Questa specifica è:
- ✅ Definita
- ✅ Validata sul world `school_life_complete`
- ✅ Pronta per implementazione in nuovi world

**Ultima modifica:** 2026-02-21
