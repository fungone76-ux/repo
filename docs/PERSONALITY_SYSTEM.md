# Personality System Guide

**Versione:** 1.0  
**Ultimo aggiornamento:** 2026-02-21

---

## 🎭 Panoramica

Il Personality System traccia il comportamento del giocatore e le impressioni che ogni NPC ha del player. Il sistema influisce direttamente sulle risposte dell'LLM, rendendo ogni personaggio reattivo alla "personalità" unica mostrata dal player.

---

## 📊 Le 5 Dimensioni dell'Impressione

Ogni NPC traccia il player su 5 assi (-100 a +100):

| Dimensione | Descrizione | Effetto sul Comportamento |
|------------|-------------|---------------------------|
| **Trust** | Quanto si fidano del player | 0 = neutrale, 80 = condivide segreti, -50 = sospettoso |
| **Attraction** | Interesse romantico/fisico | 0 = amicizia, 80 = flirt intenso, -50 = repulsa |
| **Fear** | Paura/intimidazione | 0 = comfort, 50 = nervosismo, -30 = sfida |
| **Curiosity** | Interesse nel conoscerti | 0 = indifferente, 60 = fa molte domande |
| **Dominance Balance** | Chi comanda | -50 = player dominante, 0 = pari, 50 = NPC dominante |

---

## 🎯 Archetipi del Player

Quando emergono pattern comportamentali consistenti, il sistema assegna un archetipo:

| Comportamento Dominante | Archetipo |
|------------------------|-----------|
| ROMANTIC | "The Romantic" |
| DOMINANT | "The Dominant" |
| SHY | "The Shy Strategist" |
| AGGRESSIVE | "The Aggressor" |
| CURIOUS | "The Investigator" |
| TEASING | "The Playful Tease" |
| PROTECTIVE | "The Guardian" |
| SUBMISSIVE | "The Submissive" |

Richiede **3+ occorrenze** dello stesso comportamento per attivare l'archetipo.

---

## ⚙️ Configurazione nel YAML

### Default (Nuovi Incontri)

Se non specificato, tutti i valori partono da **0** (neutrale):

```yaml
companion:
  name: "Luna"
  role: "Insegnante"
  # ... altri campi ...
  # NON specificare starting_impression
  # Risultato: Trust=0, Attraction=0, Fear=0, Curiosity=0, Power=0
```

### Relazioni Esistenti (Configurazione Custom)

Per personaggi che conoscono già il player (moglie, amico d'infanzia, nemico):

```yaml
companion:
  name: "Luna"
  role: "Compagna Fedele"
  background: "Tua moglie da 5 anni, ti conosce meglio di chiunque altro"
  relationship_to_player: "Wife deeply in love"
  
  # Valori iniziali personalizzati
  starting_impression:
    trust: 85           # Si fida ciecamente
    attraction: 90      # Passione romantica
    fear: -20           # Completamente a suo agio
    curiosity: 40       # Ancora interessata a scoprirti
    dominance_balance: 10  # Leggermente dominante (ti "gestisce")
```

### Esempi per Tipologia

**Amica d'infanzia:**
```yaml
starting_impression:
  trust: 70
  attraction: 20      # Potenziale non esplorato
  fear: -30
  curiosity: 30
  dominance_balance: 0
```

**Nemico/Jealous Rival:**
```yaml
starting_impression:
  trust: -40          # Sospettoso
  attraction: 10      # Attrazione conflittuale
  fear: 20            # Intimidito dalle tue capacità
  curiosity: 60       # Ossessione nel sapere i tuoi piani
  dominance_balance: 30  # Cerca di controllarti
```

**Autorità Rispettata (Professore):**
```yaml
starting_impression:
  trust: 30           # Apertura professionale
  attraction: 0       # Neutrale
  fear: -10           # Comfort
  curiosity: 20       # Interesse accademico
  dominance_balance: 40  # Chiaramente in posizione di potere
```

---

## 🔄 Come Evolvono i Valori

### Impatto delle Azioni del Player

| Azione del Player | Effetto |
|-------------------|---------|
| "Sei bellissima" | Attraction +15 |
| "Proteggimi" | Trust +15, Fear -10 |
| Ordini minacciosi | Fear +15, Trust -10 |
| Domande personali | Curiosity +10 |
| Sfida l'autorità | Dominance Balance -20 (player prende potere) |
| Cedere/Obbidire | Dominance Balance +15 (NPC prende potere) |

### Modificatori per Intensità

I comportamenti rilevati hanno intensità crescente:
- **Subtle** (1-2 volte): Effetto base
- **Moderate** (3-5 volte): Effetto ×1.5
- **Strong** (6+ volte): Effetto ×2

---

## 📝 Integrazione con l'LLM

### Cosa Vede l'LLM

Il system prompt include automaticamente:

```
=== PSYCHOLOGICAL CONTEXT ===
=== BEHAVIORAL PATTERNS ===
- romantic: STRONG (5 times)
- protective: MODERATE (3 times)

=== IMPRESSION OF PLAYER ===
Trust: 45 (High)
Attraction: 60 (Very High)
Fear: -10 (Low)
Curiosity: 25 (High)
Power Balance: -30 (Player Dominant)

=== PERSONALITY RESPONSE GUIDE ===
Use the impression scores above to guide the character's behavior:

TRUST (how much they believe in you):
  -100 to -50: Suspicious, questions motives, keeps secrets
  -49 to 0: Cautious, polite but distant
  1 to 50: Friendly, shares minor personal details
  51 to 100: Fully open, shares secrets, vulnerable

[... guide complete per tutte le dimensioni ...]
```

### Come Influenza le Risposte

Con **Trust 80** + **Attraction 70**:
- L'NPC condivide pensieri intimi
- Flirt naturale e reciproco
- Gestures fisici (toccare mano, avvicinarsi)
- Ti difende davanti agli altri

Con **Trust -30** + **Fear 40**:
- Risposte corte, evasive
- Non condivide informazioni personali
- Ti osserva con sospetto
- Segue le tue istruzioni solo se costretta

---

## 🔄 Auto-Switch Companion

Il sistema rileva automaticamente quando vuoi parlare con un altro personaggio analizzando il tuo input.

### Come Funziona

Quando scrivi un messaggio, il sistema cerca:

1. **Nome del companion** (es. "Luna", "Stella", "Maria")
2. **Aliases espliciti** (definiti nel YAML)
   - Esempio: "Nena" per Elena, "Prof" per Luna
3. **Ruolo/Professione** (rilevamento smart)
   - "professoressa" → trova chi ha `role: "Insegnante"`
   - "bidella" → trova chi ha `role: "Bidella"`
   - "studente" → trova chi ha `role: "Studentessa"`

### Esempi Pratici

```
[Sei con Luna]

Tu: "Ciao Stella, come va?"
    ↓
[Rileva "Stella"]
[Auto-switch: Luna → Stella]
📍 Ora parli con Stella (prima: Luna)

Tu: "Professoressa, una domanda"
    ↓
[Rileva "professoressa" → ruolo di Luna]
[Auto-switch: Stella → Luna]
📍 Ora parli con Luna (prima: Stella)
```

### Configurazione nel YAML

```yaml
companion:
  name: "Luna"
  role: "Insegnante di Matematica"
  
  # Aliases espliciti (oltre al nome)
  aliases:
    - "Professoressa Luna"
    - "Prof"
    - "La prof di mate"
```

**Nota**: Il ruolo (`role`) viene automaticamente analizzato per parole chiave comuni come "insegnante", "professoressa", "bidella", "studente", ecc.

---

## 🎮 UI e Feedback

### Widget Personality (Pannello Sinistro)

Mostra in tempo reale:
- Archetipo corrente (o "Analyzing...")
- 5 barre di progresso colorate
- Lista comportamenti rilevati
- **Si aggiorna automaticamente quando cambi companion via auto-switch**

### Notifiche Toast

Appaiono quando:
- Viene rilevato un nuovo comportamento ("Luna has noticed... You seem Romantic")
- Cambia l'archetipo ("You are now: The Romantic")
- Impressioni cambiano significativamente

### Toolbar Indicator

🎭 Mostra l'archetipo corrente o "Analyzing... (2/3)"

---

## 💾 Persistenza

I valori personality sono **salvati nel database**:
- `behavioral_memory`: Contatori comportamenti
- `impression`: Tutte le 5 dimensioni
- `detected_archetype`: Archetipo calcolato

Al caricamento di una partita, il sistema ripristina esattamente lo stato personality del salvataggio.

---

## 🌟 Best Practices per World Creators

### 1. Nuovi Incontri (Default)
Per storie dove il player incontra il personaggio per la prima volta:
- **NON** specificare `starting_impression`
- Lascia che il player "costruisca" la relazione dalle interazioni
- Usa i behavioral patterns per guidare l'evoluzione naturale

### 2. Relazioni Pre-esistenti
Per storie con background condiviso (fantasy con party esistente, slice of life con amici):
- Configura `starting_impression` per riflettere la storia
- Usa `background` e `relationship_to_player` per contesto narrativo
- Bilancia i valori per creare dinamiche interessanti

### 3. Contrasti Drammatici
Crea tensione con valori conflittuali:
```yaml
# Moglie che ti ama ma non si fida più
trust: -20
attraction: 80

# Nemico che ti rispetta ma ti teme
fear: 60
dominance_balance: -40  # Sei più forte
```

### 4. Evoluzione Narrativa
Non mettere tutto al massimo all'inizio. Lascia spazio per:
- Quest che aumentano Trust
- Eventi che cambiano Power Balance
- Momenti di crisi che modificano Attraction

---

## 🔧 Troubleshooting

**Problema:** I valori non cambiano  
**Soluzione:** Verifica che `personality_engine` sia inizializzato in `GameEngine`

**Problema:** L'LLM ignora i valori personality  
**Soluzione:** Verifica che `personality_engine` venga passato a `PromptBuilder.build_system_prompt()`

**Problema:** Archetipo non rilevato  
**Soluzione:** Servono 3+ occorrenze dello stesso comportamento. Controlla che le regex in `BEHAVIOR_PATTERNS` matchino l'input.

---

## 📚 Collegamenti

- [WORLD_CREATION_GUIDE.md](WORLD_CREATION_GUIDE.md) - Configurazione generale world
- [NARRATIVE_SYSTEMS_GUIDE.md](NARRATIVE_SYSTEMS_GUIDE.md) - Story Beats, Quests, Global Events
- `src/luna/systems/personality.py` - Implementazione sistema
- `src/luna/core/models.py` - Modelli dati (Impression, PersonalityState)

---

**Nota:** Il Personality System è generico e funziona con **qualsiasi world** senza modifiche al codice. I valori iniziali sono l'unica configurazione necessaria, e solo se si desidera una relazione pre-esistente.
