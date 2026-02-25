# Guida Creazione Mondi YAML - Luna RPG v4

Questa guida ti aiuta a creare mondi di gioco completi per Luna RPG v4.

## ⚠️ IMPORTANTE: Contenuto Adult (18+)

Luna RPG v4 è progettato per contenuti **maturi/adult (18+)**.

### Linee Guida Contenuti

- **Tutti i personaggi** devono essere descritti come adulti (18+)
- **Tutte le interazioni** sono consensuali tra adulti
- Il tono può essere romantico, passionale, intimo
- Scene suggestive gestite con tatto ed eleganza

### Configurazione in `_meta.yaml`

```yaml
meta:
  id: "mio_mondo"
  name: "Il Mio Mondo"
  genre: "Romance"  # o "Slice of Life", "Drama", etc
  content_rating: "adult"  # Indica contenuto 18+
  
# Istruzioni aggiuntive per l'LLM
content_settings:
  mature_content: true
  romance_level: "high"  # low, medium, high
  intimacy_allowed: true
```

L'LLM riceverà automaticamente le linee guida appropriate dal file
`src/luna/ai/content_guidelines.py`.

---

## 📁 Struttura File

### Formato Modulare (Consigliato)
```
worlds/mio_mondo/
├── _meta.yaml           # Metadata, player, endgame
├── elena.yaml           # Personaggio + quest + milestones
├── marco.yaml           # Altro personaggio
├── locations.yaml       # Luoghi
├── time.yaml            # Ciclo temporale
├── global_events.yaml   # Eventi globali (atmosfera)
├── random_events.yaml   # Eventi casuali esplorativi
└── daily_events.yaml    # Eventi giornalieri (routine)
```

### Formato Legacy (Singolo file)
```
worlds/mio_mondo.yaml    # Tutto in un file
```

---

## 📄 _meta.yaml - Metadati

```yaml
meta:
  id: "mio_mondo"                    # ID univoco (obbligatorio)
  name: "Il Mio Mondo"               # Nome visualizzato (obbligatorio)
  genre: "Slice of Life"             # Genere
  description: "Un mondo di esempio"
  lore: |
    Storia del mondo...
    Puoi usare markdown multi-linea.

# Configurazione NPC generici
npc_logic:
  female_hints: ["donna", "ragazza", "signora"]
  male_hints: ["uomo", "ragazzo", "signore"]
  female_prompt: "young woman, detailed face"
  male_prompt: "young man, detailed face"

# Personaggio giocatore
player_character:
  identity:
    name: "Protagonista"
    age: 18
    background: "Nuovo studente"
  starting_stats:
    strength: 10
    mind: 10
    charisma: 10

# Condizioni di vittoria
endgame:
  description: "Conquista tutte le ragazze"
  victory_conditions:
    - type: "companion_conquered"
      target: "Elena"
      requires:
        - affinity: 100
        - flag: "elena_confessed_love"
    - type: "companion_conquered"
      target: "Marco"
      requires:
        - affinity: 100
        - flag: "marco_trust_complete"

# Sistemi di gameplay attivi (SELEZIONALI!)
gameplay_systems:
  # Sistema base - quasi sempre attivo
  affinity:
    enabled: true
    tiers:
      - threshold: 0
        name: "Sconosciuto"
        description: "Appena conosciuti"
      - threshold: 25
        name: "Conoscente"
        unlocked_actions: ["chat", "chiedi_come_sta"]
      - threshold: 50
        name: "Amico"
        unlocked_actions: ["flirta", "regalo", "abbraccio"]
        unlocked_outfits: ["casual"]
      - threshold: 75
        name: "Intimo"
        unlocked_actions: ["appuntamento"]
      - threshold: 100
        name: "Fidanzato"
        unlocked_actions: ["bacio", "intimo"]
  
  # Per mondi fantasy/horror
  combat:
    enabled: false  # Cambia a true se vuoi combattimenti
    type: "turn_based"
    stats: ["forza", "destrezza", "magia"]
    dice: "d20"
    allow_escape: true
    actions:
      - action_id: "attack"
        name: "Attacca"
        damage: 10
        stat_check: "forza"
      - action_id: "spell"
        name: "Incantesimo"
        damage: 15
        stat_check: "magia"
  
  # Per mondi con item
  inventory:
    enabled: false
    max_slots: 20
    categories: ["arma", "armatura", "consumabile", "chiave", "varie"]
  
  # Per mondi con economia
  economy:
    enabled: true
    currency: "euro"
    starting_amount: 100
    prices:
      caffè: 2
      regalo_fiori: 15
      cena: 50
    shops:
      default:
        - item_id: "caffè"
          name: "Caffè"
          price: 2
        - item_id: "fiori"
          name: "Mazzo di fiori"
          price: 15
  
  # Per mondi investigativi
  clues:
    enabled: false
    mysteries:
      - "omicidio_villa"
      - "rapina_banca"
  
  # Per mondi sopravvivenza
  survival:
    enabled: false
    needs: ["fame", "sete", "energia"]
    decay_rate: 2.0
    critical_threshold: 20
  
  # Per mondi con fazioni
  reputation:
    enabled: false
    factions:
      studenti:
        starting: 0
        description: "Alunni della scuola"
      professori:
        starting: 10
        description: "Corpo docente"
  
  # Per mondi con karma
  morality:
    enabled: false
    alignment_axes: ["bene_male", "ordine_caos"]
    starting_alignment:
      bene_male: 0
      ordine_caos: 0
```

---

## 🎬 Story Beats - Struttura Narrativa

Gli **Story Beats** sono momenti narrativi obbligatori che **Python controlla**, mentre **l'AI esegue** scrivendo la scena.

Questo sistema previene che l'AI "sbarella" (divaghi, dimentichi la trama, introduca elementi incongruenti).

### Concetto Chiave

- **Python decide COSA deve succedere** (i beat)
- **AI scrive COME succede** (stile, dialoghi, atmosfera)
- **Python valida** che l'AI abbia incluso gli elementi richiesti

### Sintassi

```yaml
story_beats:
  # Premessa base - l'AI deve sempre rispettarla
  premise: |
    Questa è una storia di MATURAZIONE in un liceo.
    Focus sulle RELAZIONI, non su eventi esterni.
  
  # Temi da esplorare
  themes:
    - "Primo amore"
    - "Scoperta di sé"
  
  # Vincoli assoluti (l'AI non può violarli)
  hard_limits:
    - "NESSUN personaggio può morire"
    - "NO magia o soprannaturale"
    - "NO cambi di setting"
  
  # Beat narrativi obbligatori
  beats:
    - id: "incontro"                    # ID univoco
      description: "Elena lascia cadere i libri"  # Cosa deve succedere
      trigger: "turn <= 5 AND location == 'Biblioteca'"  # Quando si attiva
      required_elements: ["elena", "libri", "aiuto"]     # Elementi obbligatori
      tone: "awkward_cute"              # Tono
      once: true                        # Solo una volta?
      consequence: "affinity += 5"      # Conseguenze
```

### Campi del Beat

| Campo | Descrizione | Esempio |
|-------|-------------|---------|
| `id` | Identificatore univoco | `"primo_bacio"` |
| `description` | Cosa deve succedere | `"Elena bacia il protagonista"` |
| `trigger` | Condizione attivazione | `"turn >= 20 AND affinity > 80"` |
| `required_elements` | Elementi che DEVONO apparire | `["elena", "bacio", "emozione"]` |
| `tone` | Tono narrativo | `"romantic"`, `"melancholic"` |
| `once` | `true` = una sola volta | `true` o `false` |
| `consequence` | Modifiche stato | `"affinity += 10, flag:x = true"` |
| `priority` | Priorità (1=max) | `1` per beat urgenti |

### Trigger Conditions

Puoi usare variabili del game state nei trigger:

```yaml
trigger: "turn >= 10"                           # Turno
trigger: "location == 'Biblioteca'"             # Location
trigger: "elena_affinity > 30"                  # Affinità
trigger: "flag:crisi_attiva == true"            # Flag
trigger: "turn >= 15 AND elena_affinity > 40"   # Combinazioni
```

### Esempio Completo - Arco Romantico

```yaml
story_beats:
  premise: "Storia di primo amore con finale romantico"
  
  themes: ["amore", "imbarazzo", "coraggio"]
  
  hard_limits:
    - "Niente morti"
    - "Niente magia"
    - "Resta nel contesto scuola"
  
  beats:
    # ATTO 1: Conoscenza
    - id: "incontro"
      description: "Incontro in biblioteca, lei lascia cadere libri"
      trigger: "turn <= 5"
      required_elements: ["elena", "libri", "aiuto", "sguardo"]
      tone: "awkward"
      once: true
      
    - id: "prima_parola"
      description: "Si presentano, scambio di nomi"
      trigger: "turn >= 3 AND turn <= 10"
      required_elements: ["elena", "nome", "presentazione"]
      tone: "shy"
      consequence: "elena_affinity += 5"
      
    # ATTO 2: Complicazione
    - id: "gelosia"
      description: "Elena vede protagonista con un'altra, malinteso"
      trigger: "turn >= 15 AND elena_affinity > 40"
      required_elements: ["elena", "gelosia", "allontanamento", "tristezza"]
      tone: "melancholic"
      consequence: "elena_affinity -= 10, flag:crisi = true"
      priority: 1
      
    - id: "chiarimento"
      description: "Protagonista spiega, perdono"
      trigger: "flag:crisi == true AND turn >= 20"
      required_elements: ["elena", "chiarimento", "perdono"]
      tone: "hopeful"
      consequence: "elena_affinity += 15, flag:crisi = false"
      
    # ATTO 3: Climax
    - id: "confessione"
      description: "Elena confessa i suoi sentimenti"
      trigger: "turn >= 30 AND elena_affinity >= 80"
      required_elements: ["elena", "confessione", "coraggio", "scelta"]
      tone: "romantic_dramatic"
      once: true
      consequence: "flag:elena_innamorata = true"
```

---

## 👤 Personaggio (elena.yaml)

### Campi Visivi Importanti

| Campo | Scopo | Esempio |
|-------|-------|---------|
| `base_prompt` | **SACRO** - Usato per generazione immagini. Deve contenere LoRA trigger, caratteristiche fisiche, quality tags | `elena_character, brown hair, green eyes, score_9, masterpiece` |
| `physical_description` | Descrizione narrativa per l'LLM | "Elena ha lunghi capelli castani e occhi verdi..." |

**Nota**: `base_prompt` viene SEMPRE incluso all'inizio di ogni prompt di immagine per garantire consistenza visiva. Non omettere i quality tags (score_9, score_8_up, masterpiece)!

```yaml
# Definizione companion
companion:
  name: "Elena"                      # Nome (obbligatorio)
  role: "Studentessa"                # Ruolo nel mondo
  age: 19
  base_personality: "Timida ma curiosa, ama la lettura"
  
  # === CONFIGURAZIONE VISIVA (IMPORTANTE!) ===
  
  # BASE_PROMPT: Usato per generazione immagini (SACRO!)
  # Deve contenere: LoRA trigger, caratteristiche fisiche fisso, quality tags
  # Questo prompt viene SEMPRE incluso all'inizio di ogni immagine
  base_prompt: |
    elena_character, brown hair, green eyes, long hair,
    detailed face, masterpiece, best quality, score_9, score_8_up
  
  # PHYSICAL_DESCRIPTION: Descrizione per l'LLM (narrativa)
  # Usata nel system prompt per descrivere il personaggio all'LLM
  # Può essere più descrittiva e narrativa
  physical_description: |
    Elena ha lunghi capelli castani che le arrivano alle spalle,
    occhi verdi intensi, un viso delicato con legghe lentiggini sul naso.
    Ha un fisico snello e portamento elegante.
  
  # === ALIAS PER AUTO-SWITCH COMPANION ===
  # Nomi alternativi che fanno switchare automaticamente a questo personaggio
  # quando menzionati nel testo del giocatore
  aliases:
    - "Elena"                    # Nome base (automatico)
    - "Nena"                     # Soprannome
    - "La ragazza della biblioteca"  # Descrizione identificativa
  
  # Outfit System V2 - Stili con descrizione consistente
  # La description dal wardrobe è usata per coerenza visiva tra turni
  default_outfit: "school_uniform"
  wardrobe:
    # STYLE: school_uniform
    # La description è usata nel prompt per coerenza visiva
    school_uniform:
      description: "Blue blazer, white shirt, red ribbon, pleated skirt"
      # Opzionale: sd_prompt per maggiore controllo sulla generazione immagine
      # sd_prompt: "blue blazer, white shirt, red ribbon tie, pleated skirt, knee socks"
      
    # STYLE: casual  
    casual:
      description: "Pink sweater, jeans, sneakers"
      
    # STYLE: sleepwear
    sleepwear:
      description: "Cute bear pajamas, fluffy slippers"
      
    # STYLE: special
    # Per stati speciali: asciugamano, etc
    towel:
      description: "Only towel wrapped around body after shower"
      special: true  # Segna come stato speciale
      
    # NOTA: La description deve essere consistente! 
    # Il sistema usa questa description per garantire che l'outfit 
    # sia sempre lo stesso tra un turno e l'altro.
    # NON cambiare la description a meno che non sia un nuovo outfit.
  
  # Sistema personalità dinamica
  personality_system:
    core_traits:
      role: "Studentessa"
      age: "19"
      base_personality: "Timida ma curiosa"
    
    emotional_states:
      default:
        description: "Normale e riservata"
        dialogue_tone: "Parla piano, usa frasi corte"
      nervosa:
        trigger_flags: ["elena_nervosa"]
        description: "Agitata e arrossisce"
        dialogue_tone: "Balbetta, guarda via, gioca con i capelli"
      felice:
        trigger_flags: ["elena_felice"]
        description: "Allegra e aperta"
        dialogue_tone: "Sorride spesso, tono vivace"
    
    affinity_tiers:
      "0-25":
        name: "La Sconosciuta"
        tone: "Fredda e formale"
        examples:
          - "Scusi, devo andare..."
          - "Non so chi sia lei"
        voice_markers:
          - "Usa 'Lei' formale"
          - "Evita contatto visivo"
      "26-50":
        name: "La Conoscente"
        tone: "Cordiale ma cauta"
        examples:
          - "Oh, ciao! Come va?"
          - "Mi piace questo posto"
      "51-75":
        name: "L'Amica"
        tone: "Calda e confidenziale"
        examples:
          - "Sono contenta di vederti!"
          - "Posso confidarmi con te?"
        voice_markers:
          - "Usa 'tu' informale"
          - "Parla di sé in prima persona"
      "76-100":
        name: "L'Amante"
        tone: "Intima e provocante"
        examples:
          - "Mi fai battere il cuore..."
          - "Resta con me stanotte"
  
  # === STARTING IMPRESSION (OPZIONALE) ===
  # Valori iniziali delle 5 dimensioni personality
  # Se non specificato: tutti 0 (neutrale) - nuovo incontro
  # Usare per relazioni pre-esistenti (moglie, amico, nemico)
  
  # Esempio: Moglie fedele (relazione esistente)
  # starting_impression:
  #   trust: 85           # Si fida ciecamente
  #   attraction: 90      # Passione romantica
  #   fear: -20           # Completamente a suo agio
  #   curiosity: 40       # Ancora interessata
  #   dominance_balance: 10  # Leggermente dominante
  
  # Esempio: Nemico (relazione conflittuale)
  # starting_impression:
  #   trust: -40          # Sospettoso
  #   attraction: 10      # Attrazione conflittuale
  #   fear: 20            # Intimidito
  #   curiosity: 60       # Ossessione
  #   dominance_balance: 30  # Cerca controllo
  
  # NOTA: Per nuovi incontri, OMETTERE questa sezione
  # I valori partiranno da 0 e cresceranno con le interazioni
  
  # Schedule giornaliero (Living World)
  # NOTA: Le location nello schedule sono suggerimenti
  # Il companion segue il player, ma può rifiutare location inappropriate
  schedule:
    Morning:
      preferred_location: "school_classroom"  # Dove vorrebbe essere
      outfit: "school_uniform"                # Stile outfit
      activity: "Lezione di matematica"
    Afternoon:
      preferred_location: "library"
      outfit: "school_uniform"
      activity: "Studia e legge"
    Evening:
      preferred_location: "elena_home"
      outfit: "casual"
      activity: "Cena e relax"
    Night:
      preferred_location: "elena_home"
      outfit: "sleepwear"
      activity: "Dorme"
  
  # === AUTO-SWITCH COMPANION ===
  # Il sistema rileva automaticamente quando il player vuole parlare con un altro personaggio
  # analizzando il testo inserito. Quando rileva un nome/alias/ruolo, switcha automaticamente.
  #
  # ORDINE DI PRIORITÀ DEL RILEVAMENTO:
  # 1. Nome esatto del companion (es. "Elena")
  # 2. Aliases espliciti definiti sopra (es. "Nena", "La ragazza della biblioteca")
  # 3. Ruolo/Professione (es. "professoressa", "bidella", "studente")
  #
  # ESEMPI PRATICI DI SWITCH:
  #
  # Tu sei con Luna e scrivi:
  # "Ciao Stella"           → Switch a Stella
  # "Professoressa, aiuto"  → Switch a Luna (se role="Insegnante")
  # "Ehi bidella"           → Switch a Maria (se role="Bidella")
  # "Bella giornata"        → Nessun switch (nessun match)
  #
  # NOTIFICA IN CHAT:
  # Quando avviene lo switch, appare un messaggio di sistema:
  # 📍 Ora parli con Stella (prima: Luna)
  #
  # PERSONALITY WIDGET:
  # Si aggiorna automaticamente mostrando i valori del nuovo companion
  # (Trust, Attraction, Fear, Curiosity, Power Balance)
  
  # Relazioni con altri NPC
  relations:
    Marco:
      initial_rapport: 20
      jealousy: 0.3
    Sofia:
      initial_rapport: 80
      jealousy: 0.0

# Quest dedicate a Elena
quests:
  elena_primo_incontro:
    meta:
      title: "Primo Incontro"
      character: "Elena"
      hidden: false
    
    activation:
      type: "auto"
      conditions:
        - type: "location"
          operator: "eq"
          value: "Biblioteca"
    
    stages:
      start:
        title: "Libri e Sguardi"
        narrative_prompt: "Elena ti nota mentre leggi. Sembra interessata."
        exit_conditions:
          - type: "action"
            pattern: "parla|saluta|sorrid"
        transitions:
          - condition: "condition_0"
            target_stage: "conversazione"
      
      conversazione:
        title: "Prima Conversazione"
        narrative_prompt: "Elena è timida ma risponde ai tuoi tentativi di conversazione."
        on_enter:
          - action: "change_affinity"
            character: "Elena"
            value: 5
        exit_conditions:
          - type: "turn_count"
            operator: "gte"
            value: 3
        transitions:
          - condition: "condition_0"
            target_stage: "completato"
      
      completato:
        title: "Conoscenza Fatta"
        narrative_prompt: "Hai fatto amicizia con Elena."
        on_enter:
          - action: "add_flag"
            key: "elena_conosciuta"
            value: true
        transitions:
          - condition: "default"
            target_stage: "_complete"
    
    rewards:
      affinity:
        Elena: 10
      flags:
        elena_quest_completa: true

# Milestones di Elena
milestones:
  - id: "elena_amica"
    name: "La sua Fiducia"
    condition:
      affinity: 50
      flag: "elena_conosciuta"
    icon: "🔓"
  
  - id: "elena_innamorata"
    name: "Il suo Cuore"
    condition:
      affinity: 100
      flag: "elena_bacio"
    icon: "❤️"
```

---

## 🗺️ locations.yaml - Location System V2 (Full Immersion)

Il nuovo sistema location supporta gerarchia, stati dinamici, discovery e molto altro.

### Sintassi Completa

```yaml
locations:
  # LOCATION BASE
  - id: "school"
    name: "Liceo Sakura"
    description: "Il liceo frequentato dai protagonisti."
    visual_style: "school building, modern architecture"
    lighting: "natural daylight"
    
    # CONNETTIVITÀ
    connected_to: ["park", "station"]  # Location raggiungibili
    
  # LOCATION CON GERARCHIA (Sub-location)
  - id: "school_hallway"
    name: "Corridoio della Scuola"
    description: "Il corridoio principale, sempre affollato tra le lezioni."
    
    # GERARCHIA
    parent_location: "school"           # Devi essere in 'school' per entrare
    requires_parent: true               # Obbligatorio: sì
    
    # ALIAS (riconoscimento naturale)
    aliases: ["corridoio", "hallway", "passaggio"]
    
    # CONNETTIVITÀ
    connected_to: ["school_classroom", "school_bathroom", "courtyard"]
    
    # NPC PRESENTI
    available_characters: ["Elena", "Marco", "random_student"]
    
    # COMPORTAMENTO COMPANION
    companion_can_follow: true
    companion_refuse_message: "Non mi piace questo posto, aspetto fuori."
    
    # STATI DINAMICI (cambiabili durante il gioco)
    dynamic_descriptions:
      crowded: "Il corridoio è stracolmo di studenti. Difficile muoversi."
      empty: "Il corridoio è deserto. I tuoi passi echeggiano."
      locked: "Il corridoio è chiuso per pulizie."
    
    # VARIAZIONI TEMPORALI
    time_descriptions:
      Morning: "Studenti frettolosi corrono alle lezioni."
      Night: "Oscurità totale. Solo le luci di emergenza."
  
  # SUB-LOCATION: Bagno
  - id: "school_bathroom"
    name: "Bagni della Scuola"
    description: "Bagni pubblici con specchi rotti e odore di disinfettante."
    parent_location: "school"
    requires_parent: true
    aliases: ["bagni", "bagno", "toilette", "wc", "servizi"]
    
    # COMPANION PUÒ RIFIUTARE
    companion_can_follow: false
    companion_refuse_message: "Non posso entrare nei bagni maschili! Aspetto fuori."
    
    # ACCESSO ORARIO
    available_times: ["Morning", "Afternoon", "Evening"]
    closed_description: "I bagni sono chiusi per pulizia notturna."
  
  # LOCATION NASCOSTA (Discovery)
  - id: "secret_basement"
    name: "Seminterrato Abbandonato"
    description: "Un locale polveroso con vecchi documenti scolastici."
    parent_location: "school"
    requires_parent: true
    
    # NASCOSTO FINO A DISCOVERY
    hidden: true
    discovery_hint: "Senti strani rumori provenire da sotto..."
    
    # RICHIEDE CONDIZIONE
    requires_flag: "found_secret_door"
    
    connected_to: []
    available_characters: []
  
  # LOCATION PUBBLICA
  - id: "park"
    name: "Parco Cittadino"
    description: "Un grande parco verde con panchine e laghetto."
    aliases: ["parco", "giardino pubblico"]
    connected_to: ["school", "cafe"]
    available_characters: ["random_npc"]
    
    time_descriptions:
      Morning: "Joggers e gente con i cani."
      Afternoon: "Bambini che giocano, famiglie in picnic."
      Night: "Illuminato da lampioni, qualche coppia in giro."
```

### Campi Location

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `id` | string | ID univoco (obbligatorio) |
| `name` | string | Nome visualizzato |
| `description` | string | Descrizione base |
| `parent_location` | string | Location padre (per gerarchia) |
| `requires_parent` | bool | Se true, devi essere nel parent per entrare |
| `aliases` | list | Nomi alternativi che il player può usare |
| `hidden` | bool | Se true, non visibile finché non scoperta |
| `discovery_hint` | string | Indizio mostrato quando vicini |
| `requires_flag` | string | Flag necessario per accesso |
| `requires_item` | string | Item necessario (es. "key_basement") |
| `available_times` | list | Orari accesso (vuoto = sempre) |
| `closed_description` | string | Messaggio quando chiuso |
| `companion_can_follow` | bool | Se false, companion rifiuta |
| `companion_refuse_message` | string | Cosa dice il companion se rifiuta |
| `dynamic_descriptions` | dict | Descrizioni per stato (crowded, empty, etc) |
| `time_descriptions` | dict | Descrizioni per ora del giorno |
| `connected_to` | list | Location raggiungibili da qui |
| `available_characters` | list | NPC che possono spawnare qui |

### Stati Dinamici Disponibili

```yaml
dynamic_descriptions:
  normal: "Stato normale"           # Default
  crowded: "Affollato"              # Tanta gente
  empty: "Deserto"                  # Nessuno
  locked: "Chiuso a chiave"         # Inaccessibile
  damaged: "Danneggiato"            # Dopo evento/combattimento
  decorated: "Decorato"             # Per festa/evento
  dark: "Al buio"                   # Luci spente
  cleaning: "In pulizia"            # Non accessibile
```

---

## ⏰ time.yaml - Time Manager

```yaml
# Ciclo temporale
time:
  Morning:
    name: "Mattina"
    lighting: "morning sunlight, fresh"
    ambient_description: "L'inizio della giornata, studenti arrivano"
    
  Afternoon:
    name: "Pomeriggio"
    lighting: "afternoon golden hour"
    ambient_description: "Lezioni in corso, sole alto"
    
  Evening:
    name: "Sera"
    lighting: "sunset colors, orange sky"
    ambient_description: "Scuola finita, tramonto"
    
  Night:
    name: "Notte"
    lighting: "moonlight, dark"
    ambient_description: "Silenzio notturno, stelle"
```

### UI del Tempo

Nell'interfaccia di gioco, il tempo è mostrato nella **status bar** con un'icona:
- ☀️ **MORNING** 
- 🌅 **AFTERNOON**
- 🌆 **EVENING**  
- 🌙 **NIGHT**

**Clicca sull'icona** per avanzare al prossimo periodo. Ogni nuovo giorno (Morning dopo Night) resetta automaticamente l'outfit del companion.

---

## 🌍 global_events.yaml

**⚠️ IMPORTANTE: Convenzione Bilingue Italiano/Inglese**

Anche se il gioco genera contenuto in italiano, i campi che l'LLM legge devono essere in **inglese** per garantire la migliore comprensione:

| Campo | Lingua | Motivo |
|-------|--------|--------|
| `meta.title` | Italiano o Inglese | Visualizzato in UI |
| `meta.description` | **Inglese** | Contesto per LLM |
| `effects.atmosphere_change` | **Inglese** | Tono emotivo per LLM |
| `narrative_prompt` | **Inglese** | Istruzioni narrative per LLM |
| `effects.visual_tags` | **Inglese** | Tag per image generation |
| `effects.location_modifiers[].message` | Italiano | Messaggio mostrato al giocatore |

### Schema Completo

```yaml
# Eventi globali (meteo, situazioni, eventi speciali)
global_events:
  rainstorm:
    meta:
      title: "Temporale Improvviso"           # UI: può essere italiano
      description: "A heavy rainstorm traps everyone at school"  # LLM: IN INGLESE!
      icon: "🌧️"                              # Emoji per UI (opzionale)
    
    trigger:
      type: "random"                          # random, conditional, time, location, affinity, flag, scheduled
      chance: 0.15                            # Probabilità 0-1 (per random)
      allowed_times: ["Afternoon", "Evening"] # Limita a fasce orarie (opzionale)
      
      # Per trigger type: conditional
      # conditions:
      #   - type: "companion" | "time" | "location" | "affinity" | "flag" | "random"
      #     target: "Maria"                    # Nome companion/locazione
      #     operator: "eq" | "gt" | "lt" | "gte" | "lte" | "in"
      #     value: 30                          # Valore da confrontare
    
    effects:
      duration: 3                             # Durata in turni (obbligatorio)
      
      # --- Campi per LLM (NARRATIVE) - IN INGLESE! ---
      atmosphere_change: "dramatic, trapped, intimate"  # Tono emotivo
      visual_tags: ["rain", "wet", "dark_sky", "puddles"]  # Tag SD
      
      # --- Campi per Gameplay (MECHANICS) ---
      location_modifiers:                     # Modifica location
        - location: "school_entrance"
          blocked: true                       # Blocca accesso
          message: "La pioggia è troppo forte per uscire."  # Italiano OK
      
      location_lock: "school_classroom"       # Blocca player in locazione
      
      affinity_multiplier: 1.5                # Moltiplicatore affinità
      
      # Azioni automatiche all'avvio
      on_start:
        - action: "set_flag"
          key: "rainstorm_active"
          value: true
        - action: "set_emotional_state"
          character: "{current_companion}"    # Placeholder sostituito runtime
          state: "flustered"
      
      # Azioni automatiche alla fine
      on_end:
        - action: "set_flag"
          key: "rainstorm_active"
          value: false
    
    # PROMPT NARRATIVO PER LLM - IN INGLESE!
    # Placeholder supportati: {current_companion}, {location}, {time}, {player_name}
    narrative_prompt: |
      Dark clouds suddenly envelop the school. Thunder rumbles through the halls. 
      Students crowd at the windows in excited chatter. You are trapped at school 
      with {current_companion}, creating an intimate, inescapable atmosphere...
  
  # Esempio: Evento a turno specifico
  school_festival:
    meta:
      title: "Festa Scolastica"
      description: "The annual school festival is happening today"
    
    trigger:
      type: "scheduled"
      turn: 20                                # Si attiva al turno 20
    
    effects:
      duration: 5
      atmosphere_change: "festive, lively, social"
      visual_tags: ["decorations", "crowd", "colorful", "balloons"]
      
      on_start:
        - action: "set_location"
          target: "gym"                       # Sposta player
    
    narrative_prompt: |
      Today is the annual school festival! The gymnasium is decorated with 
      colorful banners and balloons. Students mill about, enjoying food stalls 
      and games. The atmosphere is lively and festive...
```

### Placeholder Supportati

Nei campi `narrative_prompt` e nelle azioni `on_start`/`on_end`:

| Placeholder | Sostituzione | Esempio |
|-------------|--------------|---------|
| `{current_companion}` | Nome companion attivo | "Luna" |
| `{location}` | Location corrente | "school_classroom" |
| `{time}` | Orario (Morning/Afternoon/Evening/Night) | "Evening" |
| `{player_name}` | Nome del giocatore | "Protagonist" |

### Tipi di Trigger

| Tipo | Descrizione | Parametri Richiesti |
|------|-------------|---------------------|
| `random` | Casuale ogni turno | `chance: 0.15` |
| `conditional` | Multiple condizioni | `conditions: [...]` |
| `time` | Orario specifico | `time_of_day: "Evening"` |
| `location` | Location corrente | `location: "school_entrance"` |
| `affinity` | Soglia affinità | `target: "Luna"`, `threshold: 30` |
| `flag` | Flag settato | `flag: "event_unlocked"` |
| `scheduled` | Turno specifico | `turn: 20` |

### Validazione Automatica

All'avvio del gioco, il sistema valida tutti gli eventi e avvisa se:
- Mancano campi obbligatori (`title`, `description`, `duration`, `atmosphere_change`, `narrative_prompt`)
- I campi LLM sono in italiano invece che in inglese
- Il formato YAML è invalido

---

## 🎲 random_events.yaml - Eventi Esplorativi

I **Random Events** sono eventi casuali che possono accadere durante l'esplorazione. Sono **ripetibili**, basati sulla location, e offrono scelte al giocatore.

### Caratteristiche

- **Ripetibili**: Possono accadere più volte (con cooldown)
- **Location-based**: Legati a specifiche location
- **Scelte multiple**: Il giocatore decide come rispondere
- **Effetti vari**: Cambiano stats, affinità, inventario

### Schema Completo

```yaml
events:
  event_id_unico:
    location: "villaggio"           # Location richiesta
    locations: ["giungla", "fiume"] # Alternative: lista di location
    repeatable: true                # Può ripetersi?
    cooldown: 5                     # Turni di attesa tra ripetizioni
    weight: 10                      # Peso per probabilità (1-100)
    
    conditions:                     # Condizioni opzionali
      time: ["Morning", "Evening"]
      affinity_naya: ">=30"
      flag: "prima_prova_completata"
    
    narrative: |                    # Testo narrativo (italiano)
      Descrivi la scena. Cosa vede il giocatore?
      Cosa sta succedendo? Atmosfera?
    
    choices:                        # Scelte disponibili (2-4)
      - text: "Azione 1"
        condition:                  # Opzionale: richiede...
          item: "coltello"          # ...un item
          quantity: 1               # ...in quantità
        check:                      # Opzionale: stat check
          stat: "strength"          # stat da usare
          difficulty: 12            # DC (10-20)
        effect:                     # Effetti al successo
          affinity_naya: 5
          energy: -10
          add_item: "pelliccia"
          set_flag: "evento_completato"
        success: "Testo se check riuscito"
        failure: "Testo se check fallito"
        followup: "Testo sempre mostrato"
      
      - text: "Azione 2"
        effect:
          affinity_all: -2
        followup: "Conseguenze della scelta"
```

### Effetti Supportati

| Effetto | Descrizione | Esempio |
|---------|-------------|---------|
| `affinity_<nome>` | Cambia affinità con NPC | `affinity_naya: 5` |
| `affinity_all` | Cambia affinità con tutti | `affinity_all: -2` |
| `add_item` | Aggiunge item | `add_item: "coltello"` |
| `remove_item` | Rimuove item | `remove_item: "cibo"` |
| `energy` | Modifica energia | `energy: -10` |
| `health` | Modifica salute | `health: -20` |
| `reputation` | Modifica reputazione | `reputation: 5` |
| `karma` | Modifica karma | `karma: -10` |
| `set_flag` | Setta un flag | `set_flag: "evento_visto"` |

### Esempio Pratico

```yaml
events:
  guerriero_sbronzo:
    location: "villaggio"
    repeatable: true
    cooldown: 5
    weight: 10
    conditions:
      time: ["Evening", "Night"]
    
    narrative: |
      Un guerriero barcollante ti blocca la strada. Ha gli occhi rossi e l'alito
      che puzza di fermentato. "Tu... tu vuoi rubarmi la donna!" balbetta.
      Vuole combattere. È chiaramente ubriaco e confuso, ma pericoloso.
    
    choices:
      - text: "Cerca di calmarlo"
        check: { stat: "charisma", difficulty: 12 }
        success: "Lo convinci a sedersi. Piange, racconta di un amore perduto."
        failure: "Ti prende a pugni! Doloroso, ma eviti il peggio."
        effect: { energy: -5 }
      
      - text: "Battilo"
        check: { stat: "strength", difficulty: 10 }
        success: "Un pugno preciso. Crolla come un sacco."
        failure: "Lotta confusa. Entrambi sanguinanti."
      
      - text: "Chiama aiuto"
        followup: "Altri guerrieri lo trascinano via. 'Non sai difenderti?'"
```

---

## 📅 daily_events.yaml - Eventi Giornalieri

I **Daily Events** rappresentano la routine della vita quotidiana. Accadono **una volta al giorno** (per time slot), sono basati sull'orario, e possono avere effetti automatici o scelte.

### Caratteristiche

- **Orario fisso**: Legati a Morning/Afternoon/Evening/Night
- **Una volta per periodo**: Non si ripetono nello stesso time slot
- **Priorità**: Eventi con priorità alta vengono scelti prima
- **Effetti automatici**: Possono applicare effetti senza scelta

### Schema Completo

```yaml
events:
  event_id:
    time: "Morning"                 # Orario richiesto
    times: ["Morning", "Afternoon"] # Alternative
    frequency: "daily"              # Sempre "daily"
    priority: 5                     # 1-10 (alto = più probabile)
    
    location: "villaggio"           # Opzionale: filtra per location
    locations: ["loc1", "loc2"]     # Opzionale: multiple location
    
    narrative: |                    # Testo descrittivo
      Descrivi la scena del daily event
    
    # OPZIONALE: Scelte (come random_events)
    choices:
      - text: "Opzione 1"
        effect: { energy: +10 }
        followup: "Risultato"
    
    # OPZIONALE: Effetti automatici (se no choices)
    effects:
      - type: "restore_stat"
        stat: "energy"
        value: 30
      - type: "modify_stat"
        stat: "water"
        value: -10
      - type: "message"
        text: "Messaggio da mostrare"
      - type: "market_available"
        duration: 1
```

### Tipi di Effetti

| Tipo | Descrizione | Parametri |
|------|-------------|-----------|
| `restore_stat` | Ripristina una stat | `stat`, `value` |
| `modify_stat` | Modifica una stat | `stat`, `value` |
| `message` | Mostra un messaggio | `text` |
| `market_available` | Attiva mercato | `duration` |

### Esempio Pratico

```yaml
events:
  preparazione_caccia:
    time: "Morning"
    frequency: "daily"
    location: ["villaggio", "giungla_edge"]
    priority: 5
    
    narrative: |
      I cacciatori si radunano. Controllano armi, si tingono di terra.
      Naya è al centro, dà ordini con gesti secchi.
      "Oggi cerchiamo il grande cervo" dice. Ti guarda. "Vieni?"
    
    choices:
      - text: "Unisciti alla caccia"
        effect: { start_activity: "hunt", energy: -20 }
        followup: "Naya annuisce. 'Vediamo se tieni il passo.'"
      
      - text: "Osserva e impara"
        effect: { skill: "hunting", experience: 10 }
      
      - text: "Declina educatamente"
        effect: { affinity_naya: -2 }
        followup: "Naya alza un sopracciglio. 'Paura di sporcarti le mani?'"
  
  riposo_caldo:
    time: "Afternoon"
    frequency: "daily"
    priority: 1
    
    narrative: |
      Il sole è alto, implacabile. La tribù rallenta.
      È tempo di riposo, di sonnellini all'ombra.
    
    effects:
      - type: "modify_stat"
        stat: "water"
        value: -10
      - type: "message"
        text: "☀️ Calura pomeridiana. Meglio riposare."
```

### Differenze Chiave: Random vs Daily

| Aspetto | Random Events | Daily Events |
|---------|---------------|--------------|
| **Trigger** | Casuale (15% per turno) | Orario specifico |
| **Ripetibilità** | Sì (con cooldown) | No (1 per time slot) |
| **Scelte** | Sempre | Opzionale |
| **Location** | Filtro principale | Opzionale |
| **Effetti** | Solo tramite scelte | Automatici o scelte |
| **Priorità** | Weight | Priority |

---

## 🎨 Sintassi Quest - Standard LLM Transmission

**⚠️ IMPORTANTE:** Solo il campo `narrative_prompt` della quest viene trasmesso all'LLM. Deve essere in **INGLESE** e dettagliato.

### Convenzione Lingua

| Campo | Lingua | Destinazione |
|-------|--------|--------------|
| `meta.title` | Italiano | UI/Quest Log |
| `meta.description` | Italiano | Reference autore |
| `stages.<id>.title` | Italiano | UI/Stage indicator |
| `stages.<id>.narrative_prompt` | **INGLESE** | ⭐ **TRASMESSO A LLM** |

### Schema Completo

```yaml
quests:
  <quest_id>:                       # ID univoco (snake_case)
    # ============================================================
    # META (Informative - NON trasmesse a LLM)
    # ============================================================
    meta:
      title: "Titolo Italiano"      # UI/Quest Log
      description: "Descrizione..." # Reference autore (italiano OK)
      character: "NomePersonaggio"  # Link companion
      hidden: false                 # Visibilità in UI
    
    # ============================================================
    # ATTIVAZIONE (Meccanica - NON trasmessa)
    # ============================================================
    activation:
      type: "auto" | "manual" | "trigger"
      conditions:                   # Valutate da QuestEngine
        - type: "affinity" | "location" | "time" | "flag"
          target: "NomePersonaggio"
          operator: "gte" | "eq"
          value: 50
    
    # ============================================================
    # STAGES - SOLO narrative_prompt TRASMESSO A LLM
    # ============================================================
    stages:
      <stage_id>:                   # es. "setup", "confronto", "finale"
        
        # --- Campi UI (NON trasmessi) ---
        title: "Titolo Stage"       # UI/Log
        description: "..."          # Reference
        
        # ⭐ CAMPO CRITICO: Istruzioni narrative per LLM (IN INGLESE!)
        narrative_prompt: |
          [SCENE SETTING]
          Describe the setting vividly. Location, lighting, atmosphere.
          
          [CHARACTER STATE]
          The character is in emotional state X. Body language, expressions.
          
          [ACTION/EVENT]
          The character approaches you. Dialogue: 'What they say'
          
          [CRITICAL ELEMENTS]
          - Must include specific detail 1
          - Must include specific detail 2
          - Atmosphere elements
        
        # --- Azioni Meccaniche (NON trasmesse) ---
        on_enter:
          - action: "set_location"
            target: "location_id"
          - action: "set_emotional_state"
            character: "NomePersonaggio"
            value: "stato_emotivo"
        
        # --- Condizioni (Valutate da Python) ---
        exit_conditions:
          - type: "action"
            pattern: "accetta|aiuta|bacia"
          - type: "turn_count"
            operator: "gte"
            value: 3
        
        # --- Transizioni ---
        transitions:
          - condition: "default"
            target_stage: "next_stage"  # o "_complete", "_fail"
    
    # ============================================================
    # RICOMPENSE (Meccaniche)
    # ============================================================
    rewards:
      affinity:
        NomePersonaggio: 25
      flags:
        quest_completata: true
```

### Esempi narrative_prompt

#### Tipo 1: Rivelazione Emotiva
```yaml
narrative_prompt: |
  In the quiet library at sunset, dust particles dance in the golden light.
  
  Maria approaches you hesitantly, unable to meet your eyes. When she finally 
  looks up, her eyes are wet with unshed tears.
  
  'Fifteen years,' she whispers. 'Fifteen years and you're the first person 
  to see me... really see me.'
  
  CRITICAL ELEMENTS:
  - Maria's nervous body language (wrung hands, downcast eyes)
  - The emotional weight of her confession
  - The intimate, private setting
  - Her vulnerability and confusion
```

#### Tipo 2: Conflitto
```yaml
narrative_prompt: |
  The school corridor is packed with students, but Stella cuts through like 
  a storm. She grabs your arm, her grip surprisingly strong.
  
  'WHO WAS SHE?' she demands, voice rising. 'I saw you laughing with her!'
  Her eyes flash with anger, but beneath it lies genuine hurt.
  
  CRITICAL ELEMENTS:
  - Public setting with students watching
  - Stella's physical possessiveness
  - Mix of anger and vulnerability
  - Accusatory dialogue with fear underneath
```

#### Tipo 3: Intimità
```yaml
narrative_prompt: |
  Luna's office is small and intimate, lit only by her desk lamp. The door 
  is closed—the first time you've been truly alone.
  
  She stands closer than propriety allows. 'I shouldn't...' she starts, but 
  doesn't move away. Her hand reaches out, hesitates, then rests on your chest.
  
  CRITICAL ELEMENTS:
  - Intimate setting (closed door, warm lighting)
  - Luna's internal conflict (professional vs personal)
  - Physical proximity and tension
  - The forbidden nature of the moment
```

### Errori Comuni

```yaml
# ❌ ERRORE: narrative_prompt in italiano
narrative_prompt: "Maria ti ferma nel corridoio..."

# ✅ CORRETTO: narrative_prompt in inglese
narrative_prompt: "Maria stops you in the corridor..."

# ❌ ERRORE: narrative_prompt troppo breve/vago
narrative_prompt: "Maria è arrabbiata."

# ✅ CORRETTO: Dettagliato e descrittivo
narrative_prompt: |
  Maria corners you in the empty classroom. Her usual composure is 
  shattered—hands shaking, eyes rimmed red. 'You think you can just 
  play with me?' Her voice cracks. 'I'm not one of your conquests.'
  But her trembling gives away her true feelings...

# ❌ ERRORE: Manca narrative_prompt
stages:
  start:
    title: "Inizio"
    # Manca narrative_prompt!

# ✅ CORRETTO: narrative_prompt presente
stages:
  start:
    title: "Inizio"
    narrative_prompt: "Describe the scene where..."
```

### Azioni on_enter Disponibili

```yaml
on_enter:
  - action: "set_location"          # Cambia location
    target: "location_id"
  
  - action: "set_outfit"            # Cambia outfit character
    character: "NomePersonaggio"
    outfit: "outfit_key"
  
  - action: "set_emotional_state"   # Cambia stato emotivo
    character: "NomePersonaggio"
    value: "stato"
  
  - action: "set_flag"              # Setta flag
    key: "flag_name"
    value: true
  
  - action: "change_affinity"       # Modifica affinità
    character: "NomePersonaggio"
    value: 10
  
  - action: "set_time"              # Cambia orario
    target: "Evening"
  
  - action: "start_quest"           # Avvia altra quest
    quest_id: "altra_quest"
```

### Tipi di Exit Conditions

```yaml
exit_conditions:
  - type: "action"          # Pattern input player
    pattern: "bacia|abbraccia|aiuta"
  
  - type: "affinity"        # Soglia affinità
    target: "NomePersonaggio"
    operator: "gte"
    value: 50
  
  - type: "location"        # Location specifica
    operator: "eq"
    value: "location_id"
  
  - type: "turn_count"      # Numero turni
    operator: "gte"
    value: 3
  
  - type: "flag"            # Flag settato
    target: "flag_name"
    operator: "eq"
    value: true
```

---

## 🎽 Outfit System V2 - Coerenza Visiva

Il nuovo sistema outfit dà libertà all'LLM di inventare dettagli mantenendo coerenza.

### Come Funziona

**NON più descizioni fisse** come:
```yaml
# VECCHIO (non usare più)
wardrobe:
  casual: "t-shirt blu, jeans, sneakers"
```

**ORA: Stili + Componenti strutturati**:
```yaml
wardrobe:
  # Stile: l'LLM inventa i dettagli
  casual:
    description: "Vestiti casual per il tempo libero"
  
  # L'LLM può rispondere:
  # "Indosso una maglietta rosa e jeans strappati, sono a piedi nudi"
  # → Salvato come OutfitState con componenti
```

### Modifica Componenti

L'LLM può modificare outfit parzialmente:

```json
{
  "outfit_update": {
    "modify_components": {
      "shoes": "none"        // Tolto le scarpe
    },
    "description": "Ora sono a piedi nudi sull'erba"
  }
}
```

**Componenti disponibili**:
- `top`: t-shirt, shirt, sweater, dress, bikini_top...
- `bottom`: jeans, pants, shorts, skirt, bikini_bottom...
- `shoes`: none/barefoot, sandals, sneakers, boots, socks...
- `outerwear`: jacket, coat, cardigan...
- `accessories`: glasses, hat, jewelry...
- `special`: towel, apron, lingerie... (override completo)

### Prompt SD Generati Automaticamente

Quando il player è `barefoot`:
- **Positive**: `"barefoot, bare feet, no shoes"`
- **Negative**: `"shoes, footwear, socks, sneakers"`

Le immagini saranno coerenti: se una volta è a piedi nudi, tutte le immagini successive lo saranno fino a cambiamento esplicito.

---

## 🚶 Comandi di Movimento Naturali

Il player si muove **scrivendo naturalmente**, non con comandi tecnici.

### Esempi Validi

| Input Player | Risultato |
|--------------|-----------|
| "Vado in biblioteca" | Muove a "library" (se raggiungibile) |
| "Andiamo nei bagni" | Risolve alias → "school_bathroom" |
| "Torniamo in classe" | Torna a "school_classroom" |
| "Raggiungiamo il parco" | Va a "park" |
| "Usciamo dal corridoio" | Esce da hallway |

### Pattern Riconosciuti

- `vado [dove]` / `vai [dove]`
- `andiamo [dove]` / `raggiungiamo [dove]`
- `torniamo [dove]` / `torna [dove]`
- `entra [dove]` / `entriamo [dove]`
- `uscire [da dove]` / `uscite [da dove]`

### Cosa Può Bloccare il Movimento

1. **Location bloccata**: `"È chiuso a chiave"`
2. **Companion rifiuta**: `"Non posso entrare nei bagni maschili!"`
3. **Orario**: `"È chiuso a quest'ora"`
4. **Requisito mancante**: `"Ti serve: key_basement"`
5. **Parent mancante**: `"Devi essere in Scuola per entrare qui"`

### Location Nascoste (Discovery)

Location con `hidden: true` non compaiono nella lista finché non scoperte:

```yaml
- id: "secret_room"
  hidden: true
  discovery_hint: "Senti rumori strani dietro la libreria..."
```

Il player può scoprirle:
- Esplorando narrativamente: `"Ispeziono la libreria"`
- Risolvendo puzzle
- Dopo certi eventi

---

## ✅ Checklist World Completo

### Core
- [ ] `_meta.yaml` con id, name, genre
- [ ] `gameplay_systems` configurati
- [ ] **`story_beats` definiti** (consigliato per coerenza narrativa)
  - [ ] `premise` che descrive la storia
  - [ ] Almeno 3-5 `beats` per struttura
  - [ ] `hard_limits` per vincoli assoluti

### Personaggi
- [ ] Almeno un personaggio in `{nome}.yaml`
- [ ] Companion ha `name`, `base_prompt`, `wardrobe`
- [ ] **`base_prompt` ben formato** (fondamentale per consistenza visiva!)
  - [ ] Contiene LoRA trigger word (es. `elena_character`)
  - [ ] Include quality tags: `score_9`, `score_8_up`, `masterpiece`
  - [ ] Descrive caratteristiche fisiche chiave: capelli, occhi, corporatura
- [ ] **`physical_description` per narrativa** (descrizione all'LLM)
- [ ] **Wardrobe usa stili** (non descrizioni fisse)
  - [ ] Ogni outfit ha solo `description` dello stile
  - [ ] L'LLM inventerà i dettagli specifici

### Location (Nuovo Sistema V2)
- [ ] `locations.yaml` con almeno 3 luoghi
- [ ] **Gerarchia definita** (parent/child se necessario)
- [ ] **Alias** per riconoscimento naturale
- [ ] **Connettività** (`connected_to`)
- [ ] Location nascoste con `hidden: true` (opzionale)
- [ ] Location che bloccano companion (`companion_can_follow: false`)

### Tempo
- [ ] `time.yaml` con 4 time slots (Morning, Afternoon, Evening, Night)

### Quest
- [ ] Almeno una quest definita
- [ ] Stage "start" esiste nelle quest
- [ ] Azioni `set_location` o `set_outfit` se necessarie

### Validazione
- [ ] Validazione YAML passa (usare `yamllint`)
- [ ] Test caricamento: `python -c "from luna.systems.world import WorldLoader; w = WorldLoader().load_world('mio_mondo'); print(w.name)"`

---

## 🔧 Comandi Utili

```bash
# Validare YAML
yamllint worlds/mio_mondo/_meta.yaml

# Testare caricamento mondo
python -c "from luna.systems.world import WorldLoader; w = WorldLoader().load_world('mio_mondo'); print(w.name)"
```

---

## 📚 Esempio Completo: "School Life"

Ecco un esempio minimale ma completo che usa tutti i nuovi sistemi:

### `_meta.yaml`
```yaml
meta:
  id: "school_life"
  name: "School Life"
  genre: "Slice of Life"
  description: "Una storia di primo amore al liceo"

player_character:
  identity:
    name: "Protagonista"
    age: 17
    background: "Nuovo studente trasferito"

gameplay_systems:
  affinity:
    enabled: true
    tiers:
      - threshold: 0
        name: "Sconosciuta"
      - threshold: 50
        name: "Amica"
        unlocked_outfits: ["casual"]
      - threshold: 100
        name: "Fidanzata"
        unlocked_outfits: ["sleepwear"]
```

### `locations.yaml`
```yaml
locations:
  - id: "school_hallway"
    name: "Corridoio"
    description: "Il corridoio principale della scuola."
    aliases: ["corridoio", "passaggio"]
    connected_to: ["school_classroom", "school_bathroom"]
    
    dynamic_descriptions:
      crowded: "Affollato di studenti che cambiano aula."
      empty: "Deserto durante le lezioni."
    
    time_descriptions:
      Morning: "Studenti frettolosi arrivano in ritardo."
      Night: "Silenzio assoluto, luci soffuse."
  
  - id: "school_bathroom"
    name: "Bagni"
    description: "Bagni della scuola."
    parent_location: "school"
    requires_parent: true
    aliases: ["bagni", "bagno", "toilette"]
    
    companion_can_follow: false
    companion_refuse_message: "Aspetto fuori, non posso entrare qui!"
    
    available_times: ["Morning", "Afternoon", "Evening"]
    closed_description: "Chiuso per pulizia."
  
  - id: "secret_rooftop"
    name: "Tetto della Scuola"
    description: "Un posto segreto con vista sulla città."
    parent_location: "school"
    requires_parent: true
    hidden: true
    discovery_hint: "Noti una porta metallica con cartello 'Vietato l'accesso'..."
    requires_flag: "found_rooftop_key"
    connected_to: []
```

### `elena.yaml` - Esempio Completo
```yaml
companion:
  name: "Elena"
  role: "Studentessa"
  age: 17
  base_personality: "Timida, ama leggere, segretamente romantica"
  
  # Aliases per auto-switch companion
  # Quando il player scrive questi nomi, switcha automaticamente a Elena
  aliases:
    - "Elena"
    - "Nena"                    # Soprannome usato dagli amici
    - "La timida"               # Descrizione riconoscibile
    - "La ragazza dei libri"    # Caratteristica distintiva
  
  base_prompt: |
    elena_character, brown hair, green eyes, 
    detailed face, masterpiece
  
  # Outfit System V2
  default_outfit: "school_uniform"
  wardrobe:
    school_uniform:
      description: "Uniforme scolastica"
    
    casual:
      description: "Vestiti casual per il tempo libero"
    
    sleepwear:
      description: "Pigiama e camicia da notte"
    
    towel:
      description: "Solo asciugamano dopo doccia"
      special: true
  
  schedule:
    Morning:
      preferred_location: "school_classroom"
      outfit: "school_uniform"
    
    Afternoon:
      preferred_location: "school_library"
      outfit: "school_uniform"
    
    Evening:
      preferred_location: "park"
      outfit: "casual"
    
    Night:
      preferred_location: "elena_home"
      outfit: "sleepwear"
```

### `luna.yaml` - Esempio con Ruolo Professionale
```yaml
companion:
  name: "Luna"
  role: "Insegnante di Matematica"
  age: 38
  base_personality: "Severa ma passionale, divorziata, cerca attenzione"
  
  # Aliases per auto-switch
  # Oltre a questi, anche "professoressa", "insegnante", "prof" funzioneranno
  # grazie al rilevamento automatico basato sul ruolo!
  aliases:
    - "Luna"
    - "Professoressa Luna"
    - "Prof"
    - "La prof di mate"
  
  base_prompt: |
    luna_teacher, mature woman, brown hair, glasses,
    business suit, detailed face, masterpiece
  
  # ... resto della configurazione
```

### Interazione Esempio

```
Player: "Vado nei bagni"
↓
Sistema: Riconosce "bagni" → school_bathroom
        Controlla: sei in "school"? ✓
        Controlla: Elena segue? ✗
↓
Elena: "Aspetto fuori, non posso entrare qui!"
↓
Player è ora in: school_bathroom
Elena è in: school_hallway (aspetta)
```

---

## 🔊 Audio TTS (Text-to-Speech)

Luna RPG v4 supporta la sintesi vocale per la narrazione.

### Requisiti

```bash
# Installa le dipendenze audio
pip install gtts pygame

# Oppure per Google Cloud TTS (migliore qualità)
pip install google-cloud-texttospeech
```

### Configurazione

In `.env` o `settings`:
```yaml
# Percorso credenziali Google Cloud (opzionale)
google_credentials_path: "google_credentials.json"

# Lingua (default: it-IT)
audio_language: "it-IT"
```

### Uso

1. **Toggle Audio**: Nella toolbar della MainWindow, click su 🔊/🔇
2. **Abilita in Settings**: Startup Dialog → Settings → Enable Audio
3. **Volume**: Controllato dal sistema operativo

### Voci Disponibili

- **it-IT-Standard-A**: Voce italiana standard (femminile)
- **it-IT-Standard-B**: Voce italiana standard (maschile)
- Altre voci disponibili in base al provider

### Fallback

Se Google Cloud non è disponibile, usa automaticamente **gTTS** (gratuito).

---

**Buona creazione!** 🎮

---

## 📚 Documentazione Collegata

- **[NARRATIVE_SYSTEMS_GUIDE.md](NARRATIVE_SYSTEMS_GUIDE.md)** - Story Beats, Quests, Global Events
- **[QUEST_SPECIFICATION.md](QUEST_SPECIFICATION.md)** - Schema formale per le quest
- **[PERSONALITY_SYSTEM.md](PERSONALITY_SYSTEM.md)** - Configurazione personality e impression

---

## 📝 NOTE TECNICHE - Correzioni Sintassi Quest (v4)

### ⚠️ Importante: Sintassi Corretta delle Quest

Dopo l'implementazione del sistema di validazione Pydantic, ecco la sintassi corretta:

#### 1. Transizioni
**❌ ERRATO:**
```yaml
transitions:
  - condition: "default"
    target: "_complete"  # ← SBAGLIATO!
```

**✅ CORRETTO:**
```yaml
transitions:
  - condition: "default"
    target_stage: "_complete"  # ← CORRETTO!
```

#### 2. Azioni Emotional State
**❌ ERRATO:**
```yaml
on_enter:
  - action: "set_emotional_state"
    character: "Elena"
    state: "felice"  # ← SBAGLIATO!
```

**✅ CORRETTO:**
```yaml
on_enter:
  - action: "set_emotional_state"
    character: "Elena"
    value: "felice"  # ← USA 'value' NON 'state'!
```

#### 3. Azioni Cambio Location
**❌ ERRATO:**
```yaml
on_enter:
  - action: "set_location"
    target: "Biblioteca"  # ← Usa 'target' solo per questo!
```

**✅ CORRETTO:**
```yaml
on_enter:
  - action: "set_location"
    target: "Biblioteca"  # ← 'target' è corretto per set_location
```

### Riassunto Campi

| Azione | Campo Personaggio | Campo Valore |
|--------|------------------|--------------|
| `set_emotional_state` | `character` | `value` (non `state`!) |
| `set_location` | - | `target` |
| `set_outfit` | `character` | `outfit` |
| `set_flag` | - | `key` + `value` |
| `change_affinity` | `character` | `value` |
| `set_time` | - | `target` |

### Transizioni Valide

```yaml
transitions:
  - condition: "condition_0"      # Prima exit_condition
    target_stage: "nome_stage"    # ID stage valido
  - condition: "default"          # Fallback
    target_stage: "_complete"     # Completa quest
  - condition: "condition_1"
    target_stage: "_fail"         # Fallisce quest
```

**Valori speciali per `target_stage`:**
- `"_complete"` - Completa la quest con successo
- `"_fail"` - Fallisce la quest
- `"nome_stage"` - ID di uno stage definito nella quest


---

## 📝 Changelog - Modifiche Recenti (2026-02-24)

### Sistema Alias per Auto-Switch Companion
Aggiunto supporto per `aliases` nel companion YAML per riconoscimento flessibile:

```yaml
companion:
  name: "Stella"
  aliases: 
    - "studentessa"
    - "bionda" 
    - "ragazza bionda"
    - "compagna di classe"
```

**Parole chiave per switch automatico:**

| Companion | Switch per Nome | Switch per Ruolo | Switch per Alias |
|-----------|-----------------|------------------|------------------|
| **Luna** | "luna" | "professoressa", "insegnante", "prof" | "professoressa di matematica" |
| **Stella** | "stella" | "studentessa", "studente" | "bionda", "ragazza bionda", "compagna di classe" |
| **Maria** | "maria" | "bidella" | "signora delle pulizie", "donna delle pulizie", "signora matura" |

### Outfit System V3 - Modalità
- **Consistent Mode**: Chiave presente nel wardrobe → usa descrizione YAML
- **Creative Mode**: Descrizione libera del LLM → usa direttamente il testo

### NPC Temporanei (Generici)
Quando il giocatore interagisce con NPC non definiti:
1. Creato al volo con `is_temporary=True`
2. Switch automatico (affinità fissa a 0)
3. Label UI mostra "NPC:" invece del nome
4. Immagine usa `NPC_BASE` senza LoRA specifici

---

*Guida aggiornata al: 2026-02-24*
