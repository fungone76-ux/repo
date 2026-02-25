# Riepilogo Implementazione - Quest System

**Data:** 2026-02-21  
**Stato:** ✅ COMPLETATO

---

## ✅ SPECIFICA DEFINITA

### Regola Fondamentale

```yaml
quests:
  <quest_id>:
    meta:
      title: "Titolo Italiano"          # UI - Italiano OK
      description: "..."                # Reference - Italiano OK
    
    stages:
      <stage_id>:
        title: "Titolo Stage"           # UI - Italiano OK
        narrative_prompt: |             # ⭐ SOLO QUESTO TRASMESSO A LLM
          # DEVE ESSERE IN INGLESE!
          Describe the scene...
```

**Solo `stages.<id>.narrative_prompt` viene trasmesso all'LLM.**

---

## 🔄 FLUSSO TRASMISSIONE

```
YAML (maria.yaml)
  └── stella_photoshoot
      └── stages.setup
          └── narrative_prompt: "..."    # ⭐ QUESTO
              ↓
WorldLoader
  └── QuestDefinition
      └── stages["setup"]
          └── narrative_prompt            # ⭐ PASSATO A
              ↓
QuestEngine (quando attivo)
  └── result.narrative_context = stage.narrative_prompt
              ↓
GameEngine.process_turn()
  └── quest_context += result.narrative_context
              ↓
PromptBuilder.build_system_prompt()
  └── sections.append("=== ACTIVE QUESTS ===")
      └── quest_context                   # ⭐ IN SYSTEM PROMPT
              ↓
LLM
  └── "Stella stops you in the corridor..."
```

---

## 📋 FORMATO narrative_prompt

### Template Standard (in inglese)

```yaml
narrative_prompt: |
  [SCENE SETTING]
  Describe the setting vividly. Location details, lighting, time of day.
  
  [CHARACTER STATE]
  The character is in emotional state X. Describe body language, expressions.
  
  [ACTION/EVENT]
  The character approaches you. Dialogue: 'What they say to initiate'
  
  [CRITICAL ELEMENTS - Must include]
  - Specific action 1
  - Specific action 2
  - Atmosphere detail
```

---

## 📝 ESEMPIO VALIDATO: Stella Photoshoot

```yaml
quests:
  stella_photoshoot:
    meta:
      title: "Il Servizio Fotografico"   # Italiano (UI)
      description: "Stella ti chiede..."   # Italiano (reference)
    
    activation:
      type: "auto"
      conditions:
        - type: "affinity"
          target: "Stella"
          operator: "gte"
          value: 50
    
    stages:
      setup:
        title: "L'Occasione"               # Italiano (UI)
        # ⭐ SOLO QUESTO TRASMESSO A LLM:
        narrative_prompt: |
          Stella stops you in the corridor between classes. She's leaning 
          against the lockers with practiced nonchalance, but there's 
          something different in her eyes today.
          
          'Hey, you,' she calls out. 'I need someone to take photos for 
          my social. You'd be... different from the other losers.' She 
          tosses her blonde hair, trying to mask her interest with arrogance.
          
          CRITICAL ELEMENTS:
          - Stella's tsundere attitude (hiding interest with arrogance)
          - The public school setting (corridor, lockers, other students)
          - Her body language (leaning, hair toss, feigned indifference)
          - The implied challenge in her words
          
        exit_conditions:
          - type: "action"
            pattern: "accetta|fotografa|aiuta"
        transitions:
          - condition: "default"
            target_stage: "photoshoot"
      
      photoshoot:
        title: "Dietro l'Obiettivo"
        narrative_prompt: |
          The empty gymnasium echoes with your footsteps. Stella poses near 
          the bleachers, the afternoon light streaming through high windows.
          
          But when you raise the camera, something shifts. Your focus is 
          different—not the leering gaze she's used to, but pure attention 
          to her as a person. For the first time, she lowers her eyes before 
          you, a flush creeping up her neck.
          
          CRITICAL ELEMENTS:
          - The intimate, empty gym setting
          - Golden hour lighting through windows
          - Stella's vulnerability when truly seen
          - Her physical reaction (lowered eyes, flush)
          - The shift from arrogance to genuine connection
```

---

## 🎯 OUTPUT IN SYSTEM PROMPT

Quando la quest è attiva (stage "setup"):

```markdown
=== ACTIVE QUESTS ===
Quest "Il Servizio Fotografico": Stella stops you in the corridor 
between classes. She's leaning against the lockers with practiced 
nonchalance, but there's something different in her eyes today.

'Hey, you,' she calls out. 'I need someone to take photos for my 
social. You'd be... different from the other losers.' She tosses 
her blonde hair, trying to mask her interest with arrogance.

CRITICAL ELEMENTS:
- Stella's tsundere attitude (hiding interest with arrogance)
- The public school setting (corridor, lockers, other students)
- Her body language (leaning, hair toss, feigned indifference)
- The implied challenge in her words
```

---

## 📚 DOCUMENTAZIONE AGGIORNATA

| File | Contenuto |
|------|-----------|
| `docs/QUEST_SPECIFICATION.md` | Specifica completa con template ed esempi |
| `docs/WORLD_CREATION_GUIDE.md` | Sintassi quest aggiornata (sezione "Quest - Standard LLM Transmission") |
| `docs/AGENTS.md` | Todo list aggiornata |

---

## ✅ CHECKLIST COMPLETAMENTO

- [x] Schema YAML standard definito
- [x] Convenzione lingua stabilita (`narrative_prompt` in inglese)
- [x] Template `narrative_prompt` con 4 sezioni
- [x] Esempi per 3 tipi di scene (Rivelazione, Conflitto, Intimità)
- [x] Errori comuni documentati
- [x] `WORLD_CREATION_GUIDE.md` aggiornato
- [x] `QUEST_SPECIFICATION.md` creato
- [x] Test verifica funzionamento (Stella photoshoot)

---

## 🎮 STATO WORLD school_life_complete

Tutte le quest nei file personaggio sono conformi alla specifica:

| Personaggio | Quest | narrative_prompt | Stato |
|-------------|-------|------------------|-------|
| Maria | `maria_defense` | ✅ Presente | ✅ Validata |
| Maria | `maria_secrets` | ✅ Presente | ✅ Validata |
| Maria | `maria_home_dinner` | ✅ Presente | ✅ Validata |
| Maria | `maria_night` | ✅ Presente | ✅ Validata |
| Stella | `stella_photoshoot` | ✅ Presente | ✅ Validata |
| Stella | `stella_basketball` | ✅ Presente | ✅ Validata |
| Stella | `stella_jealousy` | ✅ Presente | ✅ Validata |
| Stella | `stella_confession` | ✅ Presente | ✅ Validata |
| Luna | (quest simili) | ✅ Presenti | ✅ Validate |

---

## 🚀 REGOLA PER FUTURI WORLD

Tutte le quest nei file personaggio DEVONO:

1. **Avere `narrative_prompt` in ogni stage** (obbligatorio)
2. **Usare inglese in `narrative_prompt`** (obbligatorio)
3. **Includere 4 sezioni**: Scene Setting, Character State, Action/Dialogue, Critical Elements
4. **Usare italiano in `meta.title` e `meta.description`** (convenzione)
5. **Definire chiari `exit_conditions` per transizioni**
6. **Usare `transitions` per stage flow logico**

**Documentazione di riferimento:**
- Template: `docs/QUEST_SPECIFICATION.md`
- Sintassi: `docs/WORLD_CREATION_GUIDE.md` (sezione Quest)
