# Quest Choice System - Documentazione

## Panoramica

Il **Quest Choice System** permette di creare quest che richiedono una scelta esplicita del giocatore tramite UI, invece di affidarsi all'interpretazione testuale dell'LLM.

## Vantaggi

- ✅ **Deterministico**: Il giocatore clicca, non scrive
- ✅ **Chiarezza**: Nessuna ambiguità su accettare/rifiutare
- ✅ **UI Intuitiva**: Bottoni colorati con icone
- ✅ **Controllo**: Il sistema sa esattamente cosa vuole il giocatore

---

## Come Usare

### 1. Tipo di Attivazione `"choice"`

Nel file YAML della quest, usa `activation_type: "choice"`:

```yaml
quests:
  luna_private_lesson:
    id: luna_private_lesson
    title: "Lezione Privata"
    description: "Luna ti propone una lezione privata dopo scuola"
    character: "luna"
    
    # Tipo choice: richiede approvazione del giocatore
    activation_type: "choice"
    requires_player_choice: true
    choice_title: "Proposta Speciale"
    choice_description: "Luna ti guarda con un sorriso... 'Vuoi che ti aiuti con i compiti? Solo noi due...'"
    accept_button_text: "Sì, volentieri!"
    decline_button_text: "No, grazie"
    
    activation_conditions:
      - type: affinity
        target: luna
        operator: gte
        value: 60
      - type: location
        operator: eq
        value: school_library
    
    stages:
      start:
        narrative_prompt: "Luna ti aspetta nella biblioteca..."
        on_enter:
          - action: set_emotional_state
            character: luna
            value: flirty
```

### 2. Parametri di Configurazione

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `activation_type` | string | `"auto"` | `"choice"` per richiedere scelta |
| `requires_player_choice` | bool | `false` | Abilita sistema di scelta |
| `choice_title` | string | `""` | Titolo del dialogo di scelta |
| `choice_description` | string | `""` | Descrizione/dettagli della scelta |
| `accept_button_text` | string | `"Accetta"` | Testo bottone accetta |
| `decline_button_text` | string | `"Rifiuta"` | Testo bottone rifiuta |

### 3. Confronto Tipi di Attivazione

```yaml
# AUTO: Si attiva automaticamente quando le condizioni sono soddisfatte
activation_type: "auto"
activation_conditions:
  - type: affinity
    value: 50

# TRIGGER: Si attiva quando un flag specifico è settato
activation_type: "trigger"
trigger_event: "luna_confession"

# CHOICE: Mostra UI di scelta quando condizioni soddisfatte
activation_type: "choice"
requires_player_choice: true
activation_conditions:
  - type: affinity
    value: 60
```

---

## Flusso del Sistema

```
┌─────────────────────────────────────────────────────────────┐
│  1. Turno di gioco                                          │
│     ↓                                                       │
│  2. QuestEngine.check_activations()                         │
│     ↓                                                       │
│  3. Trova quest con activation_type="choice"               │
│     ↓                                                       │
│  4. Aggiunge a pending_choice_quests                       │
│     ↓                                                       │
│  5. UI: _check_pending_quest_choices()                     │
│     ↓                                                       │
│  6. Mostra QuestChoiceWidget                               │
│     ↓                                                       │
│  7. Giocatore clicca: [Accetta] / [Rifiuta] / [Info]       │
│     ↓                                                       │
│  8. resolve_quest_choice(accepted=True/False)              │
│     ↓                                                       │
│  9a. Accettata → activate_quest() → Quest attiva!          │
│  9b. Rifiutata → Rimane in lista rifiutate                 │
└─────────────────────────────────────────────────────────────┘
```

---

## API per Sviluppatori

### Engine API

```python
# Ottieni quest in attesa di scelta
pending = engine.get_pending_quest_choices()
# Returns: [{"quest_id": "...", "title": "...", "description": "...", "giver": "..."}]

# Risolvi una scelta
quest_title = await engine.resolve_quest_choice("quest_id", accepted=True)
```

### UI API

```python
# Mostra scelta quest
main_window.show_quest_choice(
    quest_id="luna_private_lesson",
    title="Lezione Privata",
    description="Luna ti propone...",
    giver_name="Luna"
)

# Mostra scelta binaria generica
main_window.show_binary_choice(
    title="Decisione",
    question="Vuoi proseguire?",
    yes_text="Sì",
    no_text="No"
)

# Mostra scelte custom
from luna.ui.quest_choice_widget import QuestChoice

main_window.show_custom_choices(
    title="Scegli l'azione",
    context="Cosa vuoi fare?",
    choices=[
        QuestChoice("fight", "Combatti", "Attacca il nemico", "⚔️", "negative"),
        QuestChoice("flee", "Scappa", "Fuggi via", "🏃", "neutral"),
        QuestChoice("talk", "Parla", "Negozia", "💬", "positive"),
    ]
)
```

---

## Esempi Avanzati

### Quest con Scelta Multipla

```yaml
quests:
  mystery_solver:
    id: mystery_solver
    title: "Il Mistero della Biblioteca"
    activation_type: "choice"
    requires_player_choice: true
    choice_title: "Un Mistero da Risolvere"
    choice_description: "Hai trovato strani rumori provenienti dalla biblioteca di notte. Vuoi investigare?"
    
    stages:
      start:
        narrative_prompt: "Sei davanti alla porta della biblioteca..."
        exit_conditions:
          - type: action
            pattern: "entra|apri|guarda"
            target_stage: investigate
      investigate:
        narrative_prompt: "All'interno trovi strani simboli..."
```

### Quest che si Attiva Dopo Scelta

```yaml
quests:
  luna_romance_route:
    id: luna_romance_route
    title: "Il Cuore di Luna"
    description: "Luna ti ha confessato i suoi sentimenti"
    activation_type: "choice"
    requires_player_choice: true
    choice_title: "Una Confessione"
    choice_description: "Luna ti guarda negli occhi... 'Mi piaci... molto. E tu?'"
    accept_button_text: "Anche a me piaci"
    decline_button_text: "Sei solo un'amica"
    
    activation_conditions:
      - type: affinity
        target: luna
        value: 80
        operator: gte
      - type: flag
        target: luna_confessed
        value: true
```

---

## Troubleshooting

### La scelta non appare

- Verifica che `activation_type` sia `"choice"`
- Controlla che le `activation_conditions` siano soddisfatte
- Assicurati che `requires_player_choice: true`

### La quest si attiva senza chiedere

- Non usare `activation_type: "auto"` con condizioni simili
- Verifica che non ci siano duplicati

### Il bottone "Accetta" non funziona

- Controlla i log: `[QuestEngine] Player ACCEPTED quest: ...`
- Verifica che la quest esista ancora nelle definitions

---

## Note Implementative

1. **Solo una scelta alla volta**: Il sistema mostra una scelta per volta
2. **Persistenza**: Le quest pendenti sono in memoria, non nel DB
3. **Rifiuto permanente**: Se rifiutata, la quest non si riattiva automaticamente
4. **Override LLM**: Il sistema bypassa completamente l'interpretazione LLM
