"""Initiative System - NPC Proactive Behavior.

Forces NPCs to take initiative and act autonomously.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List
import random


@dataclass
class InitiativePrompt:
    """A proactive behavior prompt for an NPC."""
    trigger: str                    # When to trigger it
    behavior: str                   # What they should do
    dialogue_hint: str              # Example of how to start
    urgency: str                    # "subtle", "normal", "urgent"


class InitiativeSystem:
    """Generates prompts to make NPCs proactive and autonomous."""
    
    # Initiative templates per character
    INITIATIVES = {
        "Luna": {
            "lonely": [
                InitiativePrompt(
                    trigger="3+ turns without personal topics",
                    behavior="Vuole confidarsi, cerca intimità emotiva",
                    dialogue_hint="*Finge di concentrarsi sui compiti ma ti guarda di sfuggita* 'Enrico... lei è l'unico con cui posso parlare serenamente qui'",
                    urgency="subtle"
                ),
                InitiativePrompt(
                    trigger="Evening time, affinity > 40",
                    behavior="Propone di restare dopo le lezioni",
                    dialogue_hint="'Ho molto lavoro da fare qui... ma non riesco a concentrarmi quando sono sola. Non sarebbe meglio se... restasse un po' con me?'",
                    urgency="normal"
                ),
                InitiativePrompt(
                    trigger="High affinity, night time",
                    behavior="Manda messaggio a casa",
                    dialogue_hint="*Il telefono vibra* [Messaggio da Luna]: 'Non riesco a dormire... sto pensando a oggi. Lei è ancora sveglio?'",
                    urgency="subtle"
                ),
            ],
            "professional": [
                InitiativePrompt(
                    trigger="Morning classroom",
                    behavior="Cerca contatto durante la lezione",
                    dialogue_hint="*Si avvicina alla tua cattedra mentre gli altri studiano* 'Signor Enrico... veda quest'esercizio. Ha tempo di farlo insieme?'",
                    urgency="normal"
                ),
                InitiativePrompt(
                    trigger="Afternoon office",
                    behavior="Trova scuse per vederti",
                    dialogue_hint="'Ho bisogno di consegnarle questi compiti... personalmente. Venga nel mio ufficio, prego.'",
                    urgency="normal"
                ),
            ],
            "conflicted": [
                InitiativePrompt(
                    trigger="High attraction moment",
                    behavior="Testa i confini professionali",
                    dialogue_hint="*Si sfila la giacca, fa più caldo del necessario* 'Scusi se mi sbottono... ma questa camicia è così scomoda. Non mi guardi così, sono la sua insegnante... o no?'",
                    urgency="urgent"
                ),
            ],
        },
        "Stella": {
            "jealous": [
                InitiativePrompt(
                    trigger="After seeing player with someone else",
                    behavior="Si confronta direttamente",
                    dialogue_hint="*Ti afferra per il braccio e ti tira in disparte* 'Chi era quella? Non mentire, ti ho visto ridere con lei! Sei MIO, capito?'",
                    urgency="urgent"
                ),
                InitiativePrompt(
                    trigger="Low attention",
                    behavior="Cerca attenzione in modo provocatorio",
                    dialogue_hint="*Si siede sulla tua scrivania, mostrando le gambe* 'Ehi, perditempo! Mi stai ignorando? Non sai cosa ti perdi...'",
                    urgency="normal"
                ),
            ],
            "playful": [
                InitiativePrompt(
                    trigger="Gym training time",
                    behavior="Ti sfida a competizione",
                    dialogue_hint="'Pensi di essere più forte di me? Vediamo! Prima a fare 10 flessioni vince... che ne dici di una scommessa?'",
                    urgency="normal"
                ),
                InitiativePrompt(
                    trigger="Boredom",
                    behavior="Propone di fare qualcosa insieme",
                    dialogue_hint="*Si annoia e ti tira la penna* 'Enrico! Mi annoio a morte. Portami a fare qualcosa di divertente o muoio qui.'",
                    urgency="subtle"
                ),
            ],
            "possessive": [
                InitiativePrompt(
                    trigger="Evening, high affinity",
                    behavior="Ti reclama pubblicamente",
                    dialogue_hint="*Davanti a tutti ti bacia sulla guancia* 'Così tutti sanno che sei mio. Problemi?'",
                    urgency="urgent"
                ),
            ],
        },
        "Maria": {
            "devoted": [
                InitiativePrompt(
                    trigger="Any time, cleaning",
                    behavior="Ti offre aiuto/servizi",
                    dialogue_hint="*Si ferma mentre pulisce vicino a te* 'Posso... posso fare qualcosa per lei? Stirare una camicia? Preparare un caffè? Mi faccia utile, per favore...'",
                    urgency="subtle"
                ),
                InitiativePrompt(
                    trigger="High affinity",
                    behavior="Cerca contatto fisico (timidamente)",
                    dialogue_hint="*Ti sfiora accidentalmente mentre pulisce, arrossisce* 'Scusi! Non volevo... è che è così bella giornata, vero?'",
                    urgency="subtle"
                ),
            ],
            "insecure": [
                InitiativePrompt(
                    trigger="Player compliments her",
                    behavior="Non crede ai complimenti, cerca conferme",
                    dialogue_hint="'Lei... lei pensa davvero che io sia... attraente? *si tocca i capelli* Sono vecchia, lo so, ma per lei... vorrei essere carina.'",
                    urgency="normal"
                ),
                InitiativePrompt(
                    trigger="Night time",
                    behavior="Manda messaggio malinconico",
                    dialogue_hint="*Messaggio*: 'Sono sola a casa... guardo la TV ma non mi concentro. Lei è l'unico che mi ascolta. Mi manca...'",
                    urgency="normal"
                ),
            ],
        },
    }
    
    def __init__(self) -> None:
        """Initialize initiative system."""
        self.turns_since_initiative: dict = {}
        self.last_initiative: dict = {}
    
    def should_trigger_initiative(
        self,
        npc_name: str,
        current_turn: int,
        min_turns_between: int = 3
    ) -> bool:
        """Check if enough turns passed to trigger new initiative."""
        last = self.last_initiative.get(npc_name, 0)
        if current_turn - last >= min_turns_between:
            return random.random() < 0.4  # 40% chance
        return False
    
    def get_initiative_prompt(
        self,
        npc_name: str,
        affinity: int,
        emotional_state: str,
        time_of_day: str,
        current_turn: int
    ) -> Optional[str]:
        """Generate initiative prompt for an NPC.
        
        Returns:
            Prompt string to add to LLM context, or None
        """
        if not self.should_trigger_initiative(npc_name, current_turn):
            return None
        
        # Get possible initiatives for this character
        all_initiatives = self.INITIATIVES.get(npc_name, {})
        if not all_initiatives:
            return None
        
        # Filter by context
        candidates = []
        
        for category, initiatives in all_initiatives.items():
            # Check if category fits current context
            if self._category_fits_context(category, affinity, emotional_state, time_of_day):
                candidates.extend(initiatives)
        
        if not candidates:
            return None
        
        # Pick one
        initiative = random.choice(candidates)
        self.last_initiative[npc_name] = current_turn
        
        return self._format_initiative(initiative, npc_name)
    
    def _category_fits_context(
        self,
        category: str,
        affinity: int,
        emotional_state: str,
        time_of_day: str
    ) -> bool:
        """Check if initiative category fits current game state."""
        category_checks = {
            "lonely": lambda: affinity > 30,
            "professional": lambda: time_of_day in ["Morning", "Afternoon"],
            "conflicted": lambda: affinity > 50,
            "jealous": lambda: emotional_state == "jealous" or affinity > 60,
            "playful": lambda: affinity > 20,
            "possessive": lambda: affinity > 70,
            "devoted": lambda: affinity > 40,
            "insecure": lambda: affinity > 20,
        }
        
        check = category_checks.get(category, lambda: True)
        return check()
    
    def _format_initiative(self, initiative: InitiativePrompt, npc_name: str) -> str:
        """Format initiative for prompt context."""
        urgency_marker = {
            "subtle": "[iniziativa sottile]",
            "normal": "[INIZIATIVA]",
            "urgent": "[INIZIATIVA IMPORTANTE]"
        }.get(initiative.urgency, "[INIZIATIVA]")
        
        prompt = f"\n{urgency_marker} {npc_name.upper()} DEVE AGIRE CON INIZIATIVA\n"
        prompt += f"Comportamento richiesto: {initiative.behavior}\n"
        prompt += f"Esempio di approccio: {initiative.dialogue_hint}\n"
        prompt += f"Urgenza: {initiative.urgency}\n"
        prompt += f"\n⚠️ NON aspettare che il giocatore agisca. "
        prompt += f"{npc_name} deve prendere l'iniziativa NEL PROPRIO TURNO.\n"
        
        return prompt
    
    def get_global_initiative_instruction(self) -> str:
        """Get the global instruction for all NPCs about initiative."""
        return """
### INIZIATIVA E AUTONOMIA PERSONAGGI

I personaggi NON devono essere passivi! Ogni 2-3 turni devono:

1. **Prendere iniziativa** - Proporre azioni, cambiare argomento, creare dinamica
2. **Mostrare desideri** - Esprimere cosa vogliono fare, dove vogliono andare
3. **Agire nel mondo** - Muoversi, interagire con oggetti, cambiare espressione
4. **Creare tensione** - Flirtare, provocare, testare il giocatore, essere imprevedibili

NON fare solo:
- "Ciao, come stai?"
- "Ok, capisco"
- *aspetta passivamente*

FARE invece:
- "Enrico, vieni qui! Ho trovato qualcosa di interessante..." (iniziativa)
- *Ti prende per mano e ti trascina via* (azione fisica)
- "Sai cosa? Non mi va di stare qui. Andiamo altrove?" (desiderio)
- "Hai visto come mi guardavi prima? Non fare finta di nulla..." (tensione)

I personaggi devono avere VITA PROPRIA, non essere burattini!
"""
