# Regole di Codifica - Luna RPG v4

**Data:** 2026-03-03  
**Regola fondamentale:** Nuove feature = Nuovi file

---

## 🚨 Regola d'Oro

> **NON aggiungere codice a file che superano le 500 righe.**  
> Crea un nuovo file dedicato.

---

## 📁 Struttura File per Nuove Feature

### 1. Sistemi di Gameplay

**File esistenti (congelati):**
- `engine.py` - ~2470 righe ⚠️ CONGELATO (in riduzione!)
- `personality.py` - OK per bug fix, NON nuove feature

**Nuovi file (esempi recenti):**
```
src/luna/systems/
├── movement.py           # 🆕 V4: Gestione movimento (estratto da engine)
├── state_memory.py       # 🆕 V4: Unificazione stato + memoria
├── intro.py              # 🆕 V4: Generazione scena iniziale
├── inventory.py          # Sistema inventario
├── crafting.py           # Sistema crafting
├── trading.py            # Sistema economia avanzata
└── achievements.py       # Sistema achievement
```

### 2. AI e Prompts

**File esistenti (congelati):**
- `prompt_builder.py` - ~1000 righe ⚠️ CONGELATO
- `gemini.py` - OK per bug fix

**Nuovi file:**
```
src/luna/ai/prompts/
├── combat.py             # Prompt per combattimento
├── exploration.py        # Prompt per esplorazione
└── dialogue_types.py     # Tipi di dialogo speciali
```

### 3. Media e Immagini

**File esistenti (congelati):**
- `builders.py` - ~1000 righe ⚠️ CONGELATO

**Nuovi file:**
```
src/luna/media/builders/
├── cinematic.py          # Builder per scene cinematiche
├── portrait.py           # Builder per ritratti
└── action.py             # Builder per azioni dinamiche
```

### 4. Utilità e Helpers

```
src/luna/utils/
├── text_cleaner.py       # Pulizia testo LLM
├── validators.py         # Validazione risposte
└── formatters.py         # Formattazione output
```

---

## ✅ Cosa SI può fare nei file esistenti

| Azione | Permesso | Esempio |
|--------|----------|---------|
| Bug fix | ✅ Sì | Correggere errore in `engine.py` |
| Refactor locale | ✅ Sì | Estrarre funzione interna |
| Commenti | ✅ Sì | Aggiungere documentazione |
| Type hints | ✅ Sì | Migliorare tipizzazione |
| Ottimizzazione | ⚠️ Con cautela | Se non cambia logica |
| Estrarre codice | ✅ Sì | Spostare in nuovo file |

## ❌ Cosa NON si può fare nei file esistenti

| Azione | Permesso | Alternativa |
|--------|----------|-------------|
| Nuova classe/feature | ❌ No | Nuovo file dedicato |
| Nuova logica gameplay | ❌ No | `src/luna/systems/nuovo.py` |
| Nuovo tipo di prompt | ❌ No | `src/luna/ai/prompts/nuovo.py` |
| Aggiungere 50+ righe | ❌ No | Spezzare in più file |

---

## 📝 Esempio Pratico

### Scenario: Voglio aggiungere un sistema di crafting

**❌ SBAGLIATO:**
```python
# In src/luna/core/engine.py (già troppo lungo!)
class GameEngine:
    ...
    def craft_item(self, recipe):  # NO! File già pieno
        ...
```

**✅ CORRETTO:**
```python
# In src/luna/systems/crafting.py (file nuovo!)
class CraftingSystem:
    def craft_item(self, recipe):
        ...

# In src/luna/core/engine.py (solo import)
from luna.systems.crafting import CraftingSystem

class GameEngine:
    def __init__(...):
        self.crafting = CraftingSystem()  # Solo inizializzazione
```

---

## 🎯 Vantaggi di questa regola

1. **File piccoli = più facili da leggere**
2. **Un file = una responsabilità**
3. **Bug isolati** - se rompi crafting, non rompi il gioco base
4. **Test facili** - testi solo il file nuovo
5. **Collaborazione** - più persone lavorano su file diversi

---

## 📊 Limite righe per file (guida)

| Tipo | Max righe | Azione se superato |
|------|-----------|-------------------|
| `engine.py` | 2500 | ⚠️ In riduzione! Estrarre codice |
| `prompt_builder.py` | 1000 | ✅ Congelato |
| `builders.py` | 1000 | ✅ Congelato |
| Nuovi file | 500 | Crea sotto-moduli |

---

## 🔒 File Congelati (solo bug fix)

- `src/luna/core/engine.py` - In ottimizzazione, estrarre codice quando possibile
- `src/luna/core/prompt_builder.py`
- `src/luna/media/builders.py`

---

## 🆕 File Creati Recentemente (Marzo 2026)

| File | Descrizione | Righe |
|------|-------------|-------|
| `systems/movement.py` | Gestione movimento player | ~250 |
| `systems/state_memory.py` | Stato + memoria unificati | ~250 |
| `systems/intro.py` | Generazione scena iniziale | ~200 |

---

## 🎭 Convenzione NPC Templates (V4.1)

### Quando creare un NPC Template

Crea un template in `npc_templates.yaml` quando:
- L'NPC appare in **location specifiche** (es. segretaria in segreteria)
- Ha **tratti visivi persistenti** (capelli rossi, occhiali, etc.)
- Deve essere **riconoscibile** tra incontri multipli

### Struttura Template

```yaml
npc_templates:
  nome_template:
    id: "nome_template"           # ID univoco
    name: "Nome Visualizzato"     # Nome nell'UI
    role: "Ruolo"                 # Es. "Segretaria Scolastica"
    base_prompt: "..."            # Prompt SD (inglese)
    visual_tags: ["red hair", ...] # Tag per consistenza
    physical_description: "..."   # Descrizione per LLM
    personality: "..."            # Tratti carattere
    voice_tone: "..."             # Tono voce
    aliases: ["alias1", "alias2"] # Trigger detection
    spawn_locations: ["loc1"]     # Location ammesse
    recurring: true               # Può riapparire
    importance: "medium"          # low/medium/high
```

### Fallback

Se non c'è un template, il sistema crea un NPC generico usando:
- `npc_logic.female_hints` / `npc_logic.male_hints` per gender detection
- `fallback_female.base_prompt` / `fallback_male.base_prompt` per aspetto

---

**Ultimo aggiornamento:** 2026-03-03  
**Deciso da:** Kimi + Utente
