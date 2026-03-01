# Regole di Codifica - Luna RPG v4

**Data:** 2026-02-24  
**Regola fondamentale:** Nuove feature = Nuovi file

---

## 🚨 Regola d'Oro

> **NON aggiungere codice a file che superano le 500 righe.**  
> Crea un nuovo file dedicato.

---

## 📁 Struttura File per Nuove Feature

### 1. Sistemi di Gameplay

**File esistenti (congelati):**
- `engine.py` - ~1200 righe ⚠️ CONGELATO
- `personality.py` - OK per bug fix, NON nuove feature

**Nuovi file:**
```
src/luna/systems/
├── inventory.py          # Sistema inventario (nuovo)
├── crafting.py           # Sistema crafting (nuovo)
├── trading.py            # Sistema economia avanzata (nuovo)
└── achievements.py       # Sistema achievement (nuovo)
```

### 2. AI e Prompts

**File esistenti (congelati):**
- `prompt_builder.py` - ~1000 righe ⚠️ CONGELATO
- `gemini.py` - OK per bug fix

**Nuovi file:**
```
src/luna/ai/prompts/
├── combat.py             # Prompt per combattimento (nuovo)
├── exploration.py        # Prompt per esplorazione (nuovo)
└── dialogue_types.py     # Tipi di dialogo speciali (nuovo)
```

### 3. Media e Immagini

**File esistenti (congelati):**
- `builders.py` - ~1000 righe ⚠️ CONGELATO

**Nuovi file:**
```
src/luna/media/builders/
├── cinematic.py          # Builder per scene cinematiche (nuovo)
├── portrait.py           # Builder per ritratti (nuovo)
└── action.py             # Builder per azioni dinamiche (nuovo)
```

### 4. Utilità e Helpers

```
src/luna/utils/
├── text_cleaner.py       # Pulizia testo LLM (nuovo)
├── validators.py         # Validazione risposte (nuovo)
└── formatters.py         # Formattazione output (nuovo)
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
| `engine.py` | 1200 | ✅ Congelato |
| `prompt_builder.py` | 1000 | ✅ Congelato |
| `builders.py` | 1000 | ✅ Congelato |
| Nuovi file | 500 | Crea sotto-moduli |

---

## 🔒 File Congelati (solo bug fix)

- `src/luna/core/engine.py`
- `src/luna/core/prompt_builder.py`
- `src/luna/media/builders.py`

**Questi file funzionano.** Non li tocchiamo se non per bug critici.

---

**Ultimo aggiornamento:** 2026-02-24  
**Deciso da:** Kimi + Utente
