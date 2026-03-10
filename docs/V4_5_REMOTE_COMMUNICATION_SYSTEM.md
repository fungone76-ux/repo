# V4.5 Remote Communication & Invitation System

## Overview

Il sistema V4.5 introduce la comunicazione remota (telefono/messaggi) con NPC e il sistema di inviti a casa del giocatore.

## Features

### 1. Comunicazione Remota

**File:** `src/luna/systems/remote_communication.py`

Quando il giocatore scrive un messaggio a un NPC (es. "scrivo a Luna"), il sistema:

1. **Rileva il pattern** di comunicazione remota
2. **Switcha il companion attivo** al target (anche se non nella stessa location)
3. **Genera l'immagine** del target nella sua location effettiva (da schedule)
4. **Aggiunge contesto** al prompt LLM: "Stai ricevendo un messaggio..."
5. **Calcola affinity/personality** sul target remoto

**Pattern riconosciuti:**
- "scrivo a [NPC]"
- "mando un messaggio a [NPC]"
- "chiamo [NPC]"
- "mandami [foto]"
- "chiedo a [NPC]"

**Esempio flusso:**
```
Player (a casa): "Scrivo a Luna che mi manca"
→ Companion switcha a Luna
→ Luna risponde dal suo ufficio
→ Immagine generata: Luna all'ufficio
→ Affinity calcolata con Luna
```

### 2. Sistema di Inviti

**File:** `src/luna/systems/invitation_manager.py`

Permette di invitare NPC a casa propria via messaggio.

**Funzionamento:**
1. **Invito**: "Vieni a casa mia stasera" → Registrato con `arrival_time`
2. **Accettazione**: NPC risponde positivamente ("Va bene", "Ok", ecc.)
3. **Attesa**: L'invito è in sospeso fino al cambio fase
4. **Arrivo**: Al tempo stabilito, messaggio narrativo:
   > *Mentre ti rilassi in salotto, senti suonare il campanello. Aprendo la porta, trovi [NPC] che è venuto come promesso.*

**Tempi supportati:**
- mattina (morning)
- pomeriggio (afternoon)
- sera (evening)
- notte (night)

### 3. Messaggio Narrativo Cambio Fase

Quando un companion se ne va al cambio fase:

```
⏰ La campanella suona. È pomeriggio.

*Luna raccoglie le sue cose.* "Devo andare in ufficio a correggere i compiti."

[La Luna è andata in: Ufficio Professoresse]
```

**Vantaggi:**
- Immersivo (narrativa invece di notifica tecnica)
- Informativo (sai dove trovare l'NPC)
- Non invasivo (flusso di gioco continua)

### 4. Regole di Follow

Quando ti sposti di location:

**Un companion ti segue SOLO se:**
- Affinity ≥ 65
- È stato ESPLICITAMENTE INVITATO ("vieni con me", "seguimi")
- È un companion principale (non NPC temporaneo)

**Altrimenti:**
- Companion rimane indietro
- Switch automatico a modalità SOLO
- Messaggio narrativo all'arrivo se segue

### 5. Pulizia Memoria Nuova Partita

Quando inizi una nuova partita:
- SQLite: messaggi e fatti cancellati
- ChromaDB: memoria semantica cancellata
- Session ID nuovo garantisce isolamento

**Log:**
```
[GameEngine] New game - clearing memory for session 123
[Memory] Semantic memory cleared
[Memory] Database records cleared
```

## File Modificati

| File | Modifiche |
|------|-----------|
| `remote_communication.py` | Nuovo - gestione comunicazione remota |
| `invitation_manager.py` | Nuovo - gestione inviti NPC |
| `turn_orchestrator.py` | Integrazione sistemi V4.5, calcolo affinity Python |
| `memory.py` | Metodo `clear()` per pulizia completa |
| `engine.py` | Chiamata `memory.clear()` su nuova partita |
| `phase_manager.py` | Eventi phase change (già esistente) |

## Flusso Completo Esempio

### Scenario: Invitare Stella a casa

**Mattino (Morning)**
```
Player: "Scrivo a Stella, vieni a casa mia stasera?"
→ Switch a Stella
→ Stella: "Va bene, passo dopo cena!"
→ Invito registrato (arrival: evening)
```

**Giorno**
- Player continua a giocare normalmente
- Invito in attesa

**Sera (Evening)**
```
⏰ La campanella suona. È sera.

*Mentre ti rilassi in salotto, senti suonare il campanello. 
Aprendo la porta, trovi Stella che è venuta come promesso.*

→ Stella diventa companion attivo
→ Location: player_home
```

## Technical Notes

### Affinity Calculation

L'affinity è ora calcolata da Python (deterministico) invece che dall'LLM:

```python
calculator = get_calculator()
affinity_result = calculator.calculate(
    user_input=user_input,
    companion_name=game_state.active_companion,
    turn_count=game_state.turn_count,
)
```

**Vantaggi:**
- Prevedibile
- Bilanciato
- Funziona in comunicazione remota

### Image Generation

Per comunicazione remota:
1. Companion attivo = target del messaggio
2. Location = schedule location del target
3. Outfit = outfit del target per quella fase

### State Management

Variabili di stato nel TurnOrchestrator:
- `_in_remote_communication`: bool
- `_remote_communication_target`: str (NPC name)
- `_pending_invitations`: dict

## Testing

### Test Comunicazione Remota
1. Essere in location diversa da Luna
2. Scrivere "Scrivo a Luna, come stai?"
3. Verificare che:
   - Companion switchi a Luna
   - Immagine mostri Luna nella sua location
   - Affinity cambi per Luna

### Test Invito
1. Scrivere "Vieni a casa mia stasera" a un NPC
2. Attendere cambio fase a Evening
3. Verificare messaggio arrivo campanello

### Test Cambio Fase
1. Giocare 8 turni
2. Verificare messaggio narrativo campanella
3. Verificare companion se ne vada correttamente
