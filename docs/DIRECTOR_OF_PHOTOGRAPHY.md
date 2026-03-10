# Director of Photography (DoP) System

**Versione:** 1.0  
**Data:** 2026-03-08  
**Stato:** Implementato e operativo

---

## Panoramica

Il sistema **Director of Photography (DoP)** è un'intelligenza artificiale che simula un direttore della fotografia cinematografico esperto, decidendo l'orientamento ottimale (aspect ratio) per ogni scena generata.

## Motivazione

Le immagini quadrate (1024x1024) non sono sempre la scelta ottimale:
- **Panorami e ambienti ampi** richiedono formato orizzontale (landscape)
- **Ritratti e figure intere** beneficiano del formato verticale (portrait)
- **Scene bilanciate** funzionano bene in formato quadrato (square)

## Aspect Ratio Supportati

| Tipo | Dimensioni | Rapporto | Uso Ideale |
|------|-----------|----------|------------|
| **Landscape** | 736 × 512 | ~1.44:1 | Panorami, gruppi, azione orizzontale, ambienti ampi |
| **Portrait** | 512 × 736 | ~0.69:1 | Ritratti, figure intere, primi piani, architetture verticali |
| **Square** | 1024 × 1024 | 1:1 | Medium shot, scene bilanciate, default versatile |

### Vincolo Tecnico

Tutte le dimensioni sono **divisibili per 16**, requisito necessario per la compatibilità con WanVideo I2V (Image-to-Video).

```
736 ÷ 16 = 46  ✓
512 ÷ 16 = 32  ✓
1024 ÷ 16 = 64 ✓
```

## Architettura

### Componenti

```
┌─────────────────────────────────────────────────────────────┐
│                    DirectorOfPhotography                     │
│              (src/luna/media/aspect_ratio_director.py)      │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
   │   LANDSCAPE  │   │   PORTRAIT   │   │    SQUARE    │
   │   736×512    │   │   512×736    │   │  1024×1024   │
   └──────────────┘   └──────────────┘   └──────────────┘
```

### Flusso Decisionale

```
1. LLM Analisi Scena
   ↓ (genera aspect_ratio + dop_reasoning)
2. TurnOrchestrator
   ↓ (passa a MediaPipeline)
3. MediaPipeline.generate_all()
   ↓ (include aspect_ratio)
4. ImagePromptBuilder.build()
   ↓ (crea ImagePrompt)
5. ComfyUIClient.generate()
   ↓ (applica dimensioni)
6. VideoClient.generate_video()
   ↓ (preserva proporzioni)
7. Output: Immagine + Video coerenti
```

## Implementazione

### 1. AspectRatioDirector

**File:** `src/luna/media/aspect_ratio_director.py`

**Classi principali:**
- `AspectRatio` (Enum): landscape, portrait, square
- `AspectRatioChoice` (dataclass): ratio, width, height, reason
- `DirectorOfPhotography` (classe): logica decisionale

**Analisi Keyword:**

Il sistema analizza la descrizione della scena cercando indicatori specifici:

```python
# Landscape indicators
["panorama", "wide", "broad", "expansive", "group", "crowd", 
 "chase", "pursuit", "street", "field", "horizon"]

# Portrait indicators  
["full body", "standing", "tall", "portrait", "headshot",
 "vertical", "tower", "staircase", "looking up"]

# Square indicators
["medium shot", "waist up", "balanced", "centered", 
 "sitting", "seated", "conversation"]
```

**Punteggio Contestuale:**
- Location type (corridoi → landscape, torri → portrait)
- Pose hint (standing → portrait, sitting → square)
- Composition hint (wide → landscape, close_up → square)
- Numero di personaggi (solo → portrait, gruppo → landscape)

### 2. Prompt LLM

**File:** `src/luna/core/prompt_builder.py`

**Sezione aggiunta al system prompt:**

```markdown
=== 🎬 DIRECTOR OF PHOTOGRAPHY (DoP) - ASPECT RATIO ===

Sei un Direttore della Fotografia (DoP) esperto con 20 anni di carriera...

**LANDSCAPE (736x512) - Scelta per:**
- Panorami, ambienti ampi, orizzonti
- Scene d'azione orizzontale
- Gruppi di personaggi

**PORTRAIT (512x736) - Scelta per:**
- Ritratti classici, primi piani verticali
- Figure intere in piedi
- Architetture alte

**SQUARE (1024x1024) - Scelta per:**
- Medium shot bilanciati
- Conversazioni intime
- Scelta sicura quando in dubbio
```

**Output JSON richiesto:**
```json
{
  "aspect_ratio": "landscape|portrait|square",
  "dop_reasoning": "Spiegazione della scelta cinematografica"
}
```

### 3. Modelli Dati

**File:** `src/luna/core/models.py`

```python
class ImagePrompt(LunaBaseModel):
    ...
    aspect_ratio: str = Field(default="square")
    dop_reasoning: str = Field(default="")

class LLMResponse(LunaBaseModel):
    ...
    aspect_ratio: str = Field(default="square")
    dop_reasoning: str = Field(default="")
```

### 4. Generazione Immagini

**File:** `src/luna/media/comfy_client.py`

```python
ASPECT_RATIOS = {
    "landscape": (736, 512),
    "portrait": (512, 736),
    "square": (1024, 1024),
}

# Nel workflow ComfyUI
workflow["7"]["inputs"]["width"] = width
workflow["7"]["inputs"]["height"] = height
```

### 5. Generazione Video

**File:** `src/luna/media/video_client.py`

Preservazione dell'aspect ratio:
```python
def _calculate_video_dimensions(self, img_width, img_height):
    # Calcola dimensioni preservando aspect ratio
    # Assicura divisibilità per 16
    # Minimum 512x512
```

## Esempi Pratici

| Scena | Aspect Ratio | Dimensioni | Ragionamento |
|-------|-------------|------------|--------------|
| Luna in piedi nel corridoio | Portrait | 512×736 | Figura intera, enfasi verticalità |
| Aula piena di studenti | Landscape | 736×512 | Ampio campo visivo, gruppo |
| Luna seduta alla scrivania | Square | 1024×1024 | Medium shot bilanciato |
| Inseguimento nel parco | Landscape | 736×512 | Azione orizzontale, movimento |
| Primo piano emotivo | Portrait | 512×736 | Intimità verticale, volto |
| Panorama della città | Landscape | 736×512 | Orizzonte, ampiezza |
| Scale a chiocciola | Portrait | 512×736 | Architettura verticale |
| Dialogo intimo | Square | 1024×1024 | Bilanciamento soggetti |

## Vantaggi

1. **Cinematograficità:** Le immagini sembrano fotogrammi di film
2. **Coerenza visiva:** Video eredita proporzioni corrette dall'immagine
3. **Versatilità:** Ogni scena ha l'orientamento più adatto
4. **Nessuna deformazione:** LoRAs funzionano bene con tutti gli aspect ratio
5. **Compatibilità:** WanVideo accetta tutte le risoluzioni (divisibili per 16)

## Files Coinvolti

| File | Modifica |
|------|----------|
| `src/luna/media/aspect_ratio_director.py` | Nuovo - Core logic |
| `src/luna/core/models.py` | Aggiunti campi aspect_ratio |
| `src/luna/media/builders.py` | Supporto aspect_ratio in ImagePrompt |
| `src/luna/media/pipeline.py` | Passa aspect_ratio ai generatori |
| `src/luna/media/comfy_client.py` | Applica dimensioni dinamiche |
| `src/luna/media/video_client.py` | Preserva aspect ratio nel video |
| `src/luna/core/prompt_builder.py` | Sezione DoP nel system prompt |
| `src/luna/systems/turn_orchestrator.py` | Estrae aspect_ratio dalla risposta LLM |

## Note Tecniche

### Perché queste dimensioni?

- **736×512**: ~1.44:1, simile al formato cinematografico 1.43:1 (IMAX) o 1.66:1 (European widescreen)
- **512×736**: ~0.69:1, ideale per ritratti verticali (formato 2:3 invertito)
- **1024×1024**: 1:1, formato Instagram/classico, versatile

### Compatibilità WanVideo

Wan2.1 I2V richiede dimensioni multiple di 16 per la tokenizzazione corretta. Tutte le nostre dimensioni soddisfano questo requisito:
- 736 = 16 × 46
- 512 = 16 × 32
- 1024 = 16 × 64

### Fallback

Se l'LLM restituisce un aspect_ratio non riconosciuto, il sistema fallback a square (1024×1024).

## Future Enhancement

Potenziali miglioramenti futuri:
- Aspect ratio ultra-wide (21:9) per scene epiche
- Aspect ratio verticali più stretti (9:16) per mobile-first
- Analisi ML della scena invece di keyword matching
- Preferenze utente per aspect ratio default

---

**Documentazione creata:** 2026-03-08  
**Ultimo aggiornamento:** 2026-03-08
