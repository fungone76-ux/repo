# Luna RPG v4 - Stato Progetto

## Data: 2026-03-01

---

## Novità del Giorno ✅

### 1. Dynamic Events System V2 - Eventi Non Bloccanti ⭐

**File:**
- `src/luna/systems/dynamic_events.py` - Gestione eventi
- `src/luna/ui/widgets.py` - GlobalEventWidget con scelte integrate
- `src/luna/core/engine.py` - Integrazione nel flusso di gioco

**Caratteristiche:**
- ✅ Eventi **non bloccano** la conversazione con Luna
- ✅ Eventi mostrati nel **widget Event** (sinistra)
- ✅ Utente può scegliere cliccando i bottoni **o** continuare a scrivere
- ✅ **Grace period** di 5 turni dopo skip (evita spam eventi)
- ✅ Supporto pattern **prima persona singolare** ("alzo", "tolgo", etc.)

**Flusso corretto:**
```
Utente: "Buongiorno Luna!"
   ↓
Luna: "Buongiorno! Come stai?"
   ↓
Event Widget: 🎲 Morning Bell (persiste fino a interazione)
   - 1. Vado in classe
   - 2. Giro ancora un po'
   - [Ignora]
   ↓
Utente: "Sto bene, tu?" (scrive normalmente)
   ↓
Luna: "Bene grazie!..."
   ↓
Event Widget: Morning Bell è ancora disponibile!
   ↓
Utente clicca "1" → Processa evento + Luna commenta
```

---

### 2. Random Events & Daily Events - Espansione Contenuti

**File:** 
- `worlds/school_life_complete/random_events.yaml` (10 eventi)
- `worlds/school_life_complete/daily_events.yaml` (12 eventi)

**Random Events (10 totali):**
| Evento | Descrizione | Chance |
|--------|-------------|--------|
| lost_student | Studente perso chiede aiuto | 25% |
| phone_call | Telefono squilla in segreteria | 20% |
| found_item | Trovi qualcosa per terra | 30% |
| overhear_conversation | Senti pettegolezzi | 35% |
| sudden_rain | Temporale estivo | 20% |
| vending_machine | Distributore bloccato | 25% |
| locked_door | Porta socchiusa (mistero) | 15% |
| music_from_gym | Musica dalla palestra | 20% |
| crying_girl | Ragazza che piange in bagno | 18% |
| teachers_lounge | Sala professori aperta | 12% |

**Daily Events (12 totali - per fascia oraria):**
- **Mattina:** Campanella, Colazione, Annunci
- **Pomeriggio:** Pranzo, Club extracurriculari, Punizioni
- **Sera:** Pulizie, Professori straordinari, Tramonto, Preparativi notte
- **Notte:** Scuola misteriosa, Guardiano, Messaggi

---

### 3. Outfit Modifier - Pattern Prima Persona

**File:** `src/luna/systems/outfit_modifier.py`

**Pattern aggiunti:**
- `alzo` / `sollevo` - per gonna/vestito
- `tolgo` / `levato` - per togliere capi
- `sbottono` - per camicia
- `strappo` - per calze
- `abbasso` - per pantaloni
- `apro` - per vestiti/cerniere
- `allento` - per cravatta

**Esempi riconosciuti:**
- "Alzo la gonna di Luna"
- "Tolgo il reggiseno"
- "Strappo le calze"
- "Apro il vestito"

---

### 4. NPC Templates - Personaggi Secondari Consistenti

**File:** `worlds/school_life_complete/npc_templates.yaml`

**14 NPC con identità visiva definita:**

| NPC | Aspetto | Location |
|-----|---------|----------|
| **Segretaria** | Paffuta, capelli rossi corti, occhiali | Segreteria |
| **Preside Bianchi** | Grasso, calvo, sudato, 55 anni | Annunci |
| **Bidello Mario** | 60 anni, grigio, baffi, tuta blu | Corridoio |
| **Guardiano Notturno** | Uniforme, torcia, diffidente | Notte |
| **Studente Perso** | 16 anni, confuso, primo anno | Corridoio |
| **Studentessa in Lacrime** | 17 anni, bionda, mascara colato | Bagno |
| **Bulli** | 18 anni, arroganti, prepotenti | Quest Maria |
| **Barista** | 40 anni, baffi, grembiule | Bar |
| **Professoressa Inglese** | 45 anni, bionda raccolta, severa | Aula |
| **Cuoca** | 50 anni, formosa, capelli grigi a chignon | Mensa |
| **Bibliotecaria** | 35 anni, neri lunghi, misteriosa | Biblioteca |
| **Infermiera** | 26 anni, bionda a coda, uniforme bianca | Infermeria |
| **Allenatore** | 40 anni, muscoloso, tuta, fischietto | Palestra |

**Caratteristiche:**
- ✅ `base_prompt` in inglese per Stable Diffusion
- ✅ `visual_tags` per consistenza immagini
- ✅ `personality` e `voice_tone` in inglese per LLM
- ✅ Sistema di **cache**: stesso NPC = stesso aspetto sempre!

---

### 5. Multi-NPC System - Affinity Requirement Abbassata

**File:** `src/luna/systems/multi_npc/manager.py`

```python
# Prima
MIN_PLAYER_AFFINITY = 20

# Dopo
MIN_PLAYER_AFFINITY = 5
```

**Cooldown:** 3 turni tra interventi dello stesso NPC

**Risultato:** Interazioni multi-NPC molto più frequenti!

---

### 6. Global Events - Probabilità Aumentate

**File:** `worlds/school_life_complete/global_events.yaml`

| Evento | Prima | Ora |
|--------|-------|-----|
| Temporale | 15% | **35%** |
| Blackout | 8% | **25%** |
| Maria Cleaning | 40% | **55%** |
| Stella Entourage | 30% | **50%** |
| Luna Discipline | 25% | **45%** |
| Aula Vuota | 20% | **40%** |

---

### 7. UI: Story Beats Widget

**File:** `src/luna/ui/widgets.py` - `StoryBeatsWidget`

Mostra i **story beats** del companion attivo:
- Progresso per affinità
- Beats completati ✅
- Beats bloccati 🔒 (con requisito visibile)

```
┌─ 🎭 Story Beats (Luna) ─────────────┐
│ ✅ Confessione Divorzio (40)        │
│ 🟢 Lezione Privata (60) pronta!     │
│ 🔒 Scelta Finale (90)               │
│ Progresso: 1/3 beats completati     │
└─────────────────────────────────────┘
```

---

### 8. UI: Quest Tracker con Bottone Attivazione

**File:** `src/luna/ui/widgets.py` - `QuestTrackerWidget`

**Nuove funzionalità:**
- Filtro per **companion attivo** (mostra solo quest di Luna/Stella/Maria)
- Icone: ⭐ disponibile | 🟢 attiva | ✅ completata
- **Bottone "🎯 Clicca qui per attivare"** per forzare attivazione quest

```
┌─ 📋 Quest (Luna) ───────────────────┐
│ ⭐ Lezione Privata                  │
│   [🎯 Clicca qui per attivare]     │
│                                     │
│ ✅ Benvenuto a Scuola               │
└─────────────────────────────────────┘
```

---

### 9. GlobalEventWidget con Scelte Integrate

**File:** `src/luna/ui/widgets.py` - `GlobalEventWidget`

**Widget Event rivisitato:**
- Mostra eventi globali e dinamici
- **Bottoni scelta** per eventi con opzioni
- Pulsante **"Ignora"** per saltare evento
- Non blocca input testuale
- Aggiornamento in tempo reale

```
┌─ 🌍 Event ─────────────────────────┐
│ 🎲 Morning Bell                    │
│ La campanella risuona...           │
│                                    │
│ [1. Vado in classe]  [2. Giro...] │
│ [Ignora]                           │
└────────────────────────────────────┘
```

---

## Riepilogo Contenuti Totali

| Categoria | Numero |
|-----------|--------|
| **Quest** | 12 |
| **Story Beats** | 9 |
| **Global Events** | 6 |
| **Random Events** | 10 |
| **Daily Events** | 12 |
| **NPC Templates** | 14 |
| **Outfit** | 18 |
| **Location** | 19 |
| **TOTALE** | **~100** |

---

## Documentazione Disponibile

| File | Descrizione |
|------|-------------|
| `docs/QUEST_CHOICE_SYSTEM.md` | Guida completa sistema scelte |
| `docs/QUEST_SPECIFICATION.md` | Specifiche sistema quest |
| `docs/EVENT_SYSTEM_SPEC.md` | Sistema eventi globali |
| `docs/MULTI_NPC_SYSTEM.md` | Gestione multipli NPC |
| `docs/PERSONALITY_SYSTEM.md` | Analisi personalità player |
| `docs/WORLD_CREATION_GUIDE.md` | Come creare nuovi world |
| `docs/RUNPOD_DAILY_STARTUP.md` | Avvio giornaliero RunPod |

---

## Configurazione Modelli LLM

File: `src/luna/config/models.yaml`

```yaml
gemini:
  primary: "gemini-2.0-flash"
  fallbacks:
    - "gemini-1.5-pro-latest"
    - "gemini-1.5-flash-latest"
  temperature: 0.95
  max_tokens: 2048
```

---

## API Key Richieste (`.env`)

```bash
GEMINI_API_KEY=your_key_here
MOONSHOT_API_KEY=your_key_here  # fallback
```

---

## World Creati

| World | Stato | Companion | Location | Eventi |
|-------|-------|-----------|----------|--------|
| **school_life_complete** | ✅ Completo | Luna, Stella, Maria | 19 | 28 (6+10+12) |

---

## Problemi Risolti Recenti

| Problema | Soluzione |
|----------|-----------|
| Eventi bloccano conversazione | Dynamic Events V2 (non-blocking) |
| Eventi si ripetono dopo skip | Grace period 5 turni |
| Pattern outfit solo terza persona | Aggiunti pattern prima persona |
| Skip evento errore AttributeError | Fix path gameplay_manager.event_manager |
| Evento skippato automaticamente | Persistenza evento nel widget fino a scelta |
| Affinità inconsistente LLM | Affinity Calculator deterministico |
| Scelte quest ambigue | Quest Choice System UI-based |
| Companion location sconosciuta | Companion Locator Widget |
| Progress non persistente | Save/Load database SQLite |
| Movimento poco intuitivo | Verbi italiani pattern matching |
| NPC generici senza identità | NPC Templates con cache |
| Multi-NPC mai attivo | Affinity requirement 20→5 |
| Outfit "No description" | Fallback wardrobe description |
| Falsi saluti | Fix farewell detection |

---

## Prossimi Step Consigliati

1. ✅ **Dynamic Events V2** (non-blocking)
2. ✅ **Pattern outfit prima persona**
3. ✅ **Event widget con scelte**
4. ⬜ **Test gameplay end-to-end**
5. ⬜ Bilanciamento valori affinità
6. ⬜ Aggiungere più quest con tipo "choice"
7. ⬜ Tutorial iniziale per nuovi giocatori

---

*Ultimo aggiornamento: 2026-03-01*
