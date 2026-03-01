"""Personality Analysis con Instructor - Validazione rigorosa.

Questo modulo sostituisce l'analisi personalità basata su regex
con un'analisi LLM strutturata e validata via Pydantic.
"""
from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

from luna.ai.llm_instructor import get_instructor_client


class BehaviorAnalysis(BaseModel):
    """Schema per analisi comportamentale."""
    
    behaviors_detected: List[str] = Field(
        default_factory=list,
        description="Lista comportamenti rilevati: romantic, dominant, aggressive, shy, curious, teasing, protective, submissive"
    )
    intensity: str = Field(
        default="moderate",
        description="Intensità: subtle, moderate, strong"
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0, le=1.0,
        description="Confidenza analisi 0-1"
    )
    reasoning: str = Field(
        default="",
        description="Spiegazione del perché questi comportamenti sono stati rilevati"
    )


class ImpressionUpdate(BaseModel):
    """Schema per aggiornamento impressione NPC."""
    
    trust_delta: int = Field(
        default=0, ge=-20, le=20,
        description="Cambio fiducia (-20 a +20)"
    )
    attraction_delta: int = Field(
        default=0, ge=-20, le=20,
        description="Cambio attrazione (-20 a +20)"
    )
    fear_delta: int = Field(
        default=0, ge=-20, le=20,
        description="Cambio paura (-20 a +20)"
    )
    curiosity_delta: int = Field(
        default=0, ge=-20, le=20,
        description="Cambio curiosità (-20 a +20)"
    )
    dominance_delta: int = Field(
        default=0, ge=-20, le=20,
        description="Cambio bilanciamento potere (-20 a +20)"
    )
    emotional_state: Optional[str] = Field(
        default=None,
        description="Nuovo stato emotivo se cambiato"
    )
    note: str = Field(
        default="",
        description="Note sull'interazione"
    )


class PersonalityAnalysisResult(BaseModel):
    """Risultato completo analisi personalità."""
    
    behavior_analysis: BehaviorAnalysis = Field(
        default_factory=BehaviorAnalysis,
        description="Analisi comportamenti"
    )
    impression_update: ImpressionUpdate = Field(
        default_factory=ImpressionUpdate,
        description="Aggiornamento impressione"
    )
    archetype_detected: Optional[str] = Field(
        default=None,
        description="Archetipo rilevato: Gentle, Dominant, Romantic, Mysterious, Playful"
    )
    suggested_response_tone: str = Field(
        default="neutral",
        description="Tono suggerito per risposta: neutral, warm, formal, playful, concerned"
    )


class PersonalityInstructorAnalyzer:
    """Analyzer personalità via Instructor (LLM strutturato).
    
    Vantaggi vs regex:
    - Contesto-aware (capisce sfumature)
    - Più preciso (ragionamento LLM)
    - Output strutturato garantito
    - Gestisce ambiguità
    """
    
    SYSTEM_PROMPT = """Sei un analista comportamentale esperto. Analizza l'input del giocatore e determina:

1. COMPORTAMENTI: Quali pattern comportamentali rilevi?
   - romantic: espressioni d'affetto, flirt
   - dominant: ordini, controllo, possessività
   - aggressive: rabbia, minacce, violenza
   - shy: timidezza, esitazione, imbarazzo
   - curious: domande, interesse, investigazione
   - teasing: provocazioni, gioco, sarcasmo
   - protective: difesa, preoccupazione, cura
   - submissive: sottomissione, obbedienza, passività

2. IMPRESSIONE: Come dovrebbe cambiare la percezione dell'NPC?
   - trust: fiducia (+ se onesto, - se bugie)
   - attraction: attrazione romantica
   - fear: paura/intimidazione
   - curiosity: interesse nel conoscere meglio
   - dominance: chi controlla la situazione?

3. ARCHETIPO: Quale profilo emerge?
   - Gentle: gentile, premuroso, rispettoso
   - Dominant: controllante, assertivo, leader
   - Romantic: affettuoso, passionale, devoto
   - Mysterious: imprevedibile, enigmatico, riservato
   - Playful: scherzoso, ironico, leggero

Rispondi in JSON seguendo rigorosamente lo schema richiesto."""
    
    def __init__(
        self,
        provider: str = "openai",
        model: Optional[str] = None,
    ):
        """Initialize analyzer.
        
        Args:
            provider: "openai" (Moonshot) o "gemini"
            model: Model name
        """
        self.client = get_instructor_client(
            provider=provider,
            model=model,
        )
    
    async def analyze(
        self,
        user_input: str,
        current_companion: str,
        current_impression: dict,
        conversation_history: Optional[List[str]] = None,
    ) -> PersonalityAnalysisResult:
        """Analizza input player con LLM strutturato.
        
        Args:
            user_input: Cosa ha detto il player
            current_companion: Chi è l'NPC attivo
            current_impression: Stato attuale impressione
            conversation_history: Contesto conversazione
            
        Returns:
            Risultato analisi validato
        """
        # Costruisci contesto
        context = f"""Contesto:
- Companion attivo: {current_companion}
- Impressione attuale: {current_impression}
- Storia: {' | '.join(conversation_history[-3:]) if conversation_history else 'Inizio conversazione'}

Input del giocatore: "{user_input}"

Analizza comportamento e determina aggiornamenti."""
        
        result = await self.client.generate(
            response_model=PersonalityAnalysisResult,
            system_prompt=self.SYSTEM_PROMPT,
            user_input=context,
        )
        
        return result
    
    async def quick_behavior_check(
        self,
        user_input: str,
    ) -> List[str]:
        """Check rapido comportamenti (per filtering).
        
        Args:
            user_input: Input utente
            
        Returns:
            Lista comportamenti rilevati
        """
        # Modello semplificato per risposta veloce
        class QuickBehavior(BaseModel):
            behaviors: List[str] = Field(
                default_factory=list,
                description="Comportamenti rilevati"
            )
        
        result = await self.client.generate(
            response_model=QuickBehavior,
            system_prompt="Analizza rapidamente l'input e elenca comportamenti rilevati.",
            user_input=user_input,
        )
        
        return result.behaviors


# Factory
def get_personality_analyzer(
    provider: str = "openai",
    model: Optional[str] = None,
) -> PersonalityInstructorAnalyzer:
    """Get analyzer instance."""
    return PersonalityInstructorAnalyzer(provider=provider, model=model)
