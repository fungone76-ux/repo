# Multi-NPC Dialogue System

**Versione:** 1.0  
**Ultimo aggiornamento:** 2026-02-24

---

## 🎭 Panoramica

Il Multi-NPC Dialogue System permette ai personaggi presenti nella stessa scena di **interagire tra loro**, non solo rispondere al player. Quando un NPC ha un rapporto estremo (odio/amore) con l'NPC attivo, può intervenire nel dialogo.

### Caratteristiche Chiave

- **Max 3 sequenze** per turno (anti-spam)
- **Attivabile/disattivabile** (globale, per scena, per NPC)
- **File separati** (`src/luna/systems/multi_npc/`)
- **Impatto visivo** con immagini che seguono chi parla

---

## 🎬 Esempio di Interazione

```
[Sei con Luna, Maria è presente]

Tu: "Ciao Luna, come va?"
↓
Luna: "Bene, grazie per chiedere."
→ 🖼️ Immagine: Luna (primo piano) + Maria (sullo sfondo)
↓
Maria: "Pfft, non ti fidare di lei!"
→ 🖼️ Immagine: Maria (primo piano) + Luna (sullo sfondo)  
↓
Luna: *sguardo glaciale* "Stia zitta, signorina."
→ 🖼️ Immagine: Luna (primo piano) + Maria (sullo sfondo)
↓
[Turno finisce - max 3 sequenze raggiunto]
```

**Tempo stimato:** ~90 secondi (3 immagini × 30s)

---

## ⚙️ Configurazione

### A) Disabilitazione Globale

```python
# In GameEngine o configurazione runtime
self.multi_npc_manager.enabled = False  # Disabilita completamente
```

### B) Disabilitazione per Scena (Flag)

```yaml
# Nel world YAML o via quest
flags:
  "disable_multi_npc": true  # Disabilita per questa scena/sessione
```

### C) Disabilitazione per NPC

```yaml
# Nel file del companion
companion:
  name: "Luna"
  allow_multi_npc_interrupts: false  # Questo NPC non interverà mai
```

---

## 🔗 Configurazione Rapporti NPC-NPC

I rapporti si configurano nel YAML di ogni companion:

```yaml
companion:
  name: "Stella"
  
  npc_links:
    Luna:
      rapport: -60        # Disprezzo forte (interverà criticando Luna)
      jealousy_sensitivity: 0.8
    Maria:
      rapport: 20         # Neutrale (non interverà)
```

### Valori Rapporto

| Range | Tipo Interazione | Descrizione |
|-------|-----------------|-------------|
| -100 a -50 | HOSTILE | Interrompe con critiche, derisione |
| -49 a -30 | HOSTILE (debole) | Occasionalmente critica |
| -29 a 29 | NEUTRAL | Raramente osserva |
| 30 a 49 | SUPPORTIVE (debole) | Occasionalmente difende |
| 50 a 100 | SUPPORTIVE | Interrompe con difesa, accordo |

---

## 🧠 Architettura

### File Structure

```
src/luna/systems/multi_npc/
├── __init__.py              # Esporta classi pubbliche
├── manager.py               # MultiNPCManager - coordinatore principale
├── interaction_rules.py     # Regole rapporti e trigger
└── dialogue_sequence.py     # Gestione sequenze (max 3)
```

### Flusso Dati

```
1. Player Input
   ↓
2. MultiNPCManager.process_turn()
   - Check enabled
   - Get present NPCs
   - Check relationships
   - Build DialogueSequence (max 3 turns)
   ↓
3. PromptBuilder aggiunge contesto Multi-NPC al system prompt
   ↓
4. LLM genera dialogo con interventi
   ↓
5. UI mostra sequenzialmente:
   - Testo NPC A
   - Genera immagine A (focus)
   - Testo NPC B (intervento)
   - Genera immagine B (focus)
   - Testo NPC A (chiusura)
   - Genera immagine A (focus)
```

---

## 🎮 Utilizzo nel GameEngine

```python
# In GameEngine.process_turn()

# 1. Check for multi-NPC interaction
sequence = self.multi_npc_manager.process_turn(
    player_input=user_input,
    active_npc=game_state.active_companion,
    present_npcs=present_npcs,  # Auto-detected if None
    game_state=game_state,
)

if sequence:
    # Add multi-NPC context to system prompt
    multi_npc_context = self.multi_npc_manager.format_prompt_for_llm(
        sequence, npc_personalities
    )
    
    # Generate with LLM
    llm_response = await self.llm_manager.generate(
        system_prompt=system_prompt + multi_npc_context,
        ...
    )
    
    # Parse response for multiple NPCs
    # Generate images sequentially for each turn
```

---

## 🎨 Integrazione UI

### Box Dialogo Separati

Ogni NPC ha il proprio box con colore distintivo:

```
┌─────────────────────┐
│ 🟦 Luna: "..."      │
└─────────────────────┘
┌─────────────────────┐
│ 🟥 Maria: "..."     │
└─────────────────────┘
┌─────────────────────┐
│ 🟦 Luna: "..."      │
└─────────────────────┘
```

### Immagini Sequenziali

L'immagine cambia focus seguendo chi parla:
- **Turno 1:** Luna primo piano, Maria sfocata/sullo sfondo
- **Turno 2:** Maria primo piano, Luna sfocata/sullo sfondo
- **Turno 3:** Luna primo piano, Maria sfocata/sullo sfondo

---

## ⚡ Performance

### Tempi Stimati (SD WebUI locale)

| Step | Tempo |
|------|-------|
| Testo Luna (A) | Istantaneo |
| Genera Immagine A | 30-45s |
| Testo Maria (B) | Istantaneo |
| Genera Immagine B | 30-45s |
| Testo Luna (C) | Istantaneo |
| Genera Immagine C | 30-45s |
| **Totale** | **~90-135s** |

**Nota:** Il player attende tra ogni immagine. Questo è intenzionale per creare un'esperienza "cinematografica".

---

## 🔮 Futuro / TODO

- [ ] **Quest-triggered changes**: Modificare rapporti NPC-NPC via quest
- [ ] **Gossip system**: NPC assenti "sente parlare" del player
- [ ] **Caching immagini**: Riutilizzare pose simili per velocizzare
- [ ] **Priorità interventi**: Se 3+ NPC presenti, solo il più estremo interviene
- [ ] **Animazioni**: Transizioni smooth tra focus cambiati

---

## 📚 Collegamenti

- `src/luna/systems/multi_npc/` - Implementazione
- `docs/PERSONALITY_SYSTEM.md` - Rapporti NPC-NPC
- `docs/WORLD_CREATION_GUIDE.md` - Configurazione YAML

---

**Stato:** Implementazione base completa. Pronto per testing. 🎭
