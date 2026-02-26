import re
import json
import logging

logger = logging.getLogger("luna.ai.repair")


class JSONRepair:
    """Classe contenitore per compatibilità con il sistema esistente."""

    @staticmethod
    def repair(bad_json: str, **kwargs) -> dict:
        """Metodo statico richiesto da GeminiClient."""
        return repair_json(bad_json, **kwargs)


def repair_json(bad_json: str, **kwargs) -> dict:
    """
    Riparatore avanzato per JSON malformati degli LLM.
    Accetta **kwargs per ignorare parametri extra come 'strict'.
    """
    if not bad_json:
        return {}

    # 1. Pulizia iniziale: rimuove markdown o testo extra fuori dalle parentesi
    bad_json = bad_json.strip()
    # Rimuove blocchi di codice markdown se presenti (```json ... ```)
    bad_json = re.sub(r'```(?:json)?', '', bad_json)

    match = re.search(r'(\{.*\})', bad_json, re.DOTALL)
    if match:
        bad_json = match.group(1)

    try:
        return json.loads(bad_json)
    except json.JSONDecodeError:
        pass

    # 2. Correzione virgolette interne non protette
    # Cerca di proteggere le virgolette che non sono delimitatori di campo
    def fix_quotes(match):
        key = match.group(1)
        value = match.group(2)
        # Protegge le virgolette non precedute da backslash
        value = re.sub(r'(?<!\\)"', r'\"', value)
        return f'"{key}": "{value}"'

    # Regex per trovare coppie "chiave": "valore"
    repaired = re.sub(r'"([^"]+)":\s*"(.+?)"(?=\s*[,}])', fix_quotes, bad_json, flags=re.DOTALL)

    # 3. Aggiunta di virgole mancanti tra i campi
    repaired = re.sub(r'"\s*\n\s*"', '",\n"', repaired)

    # 4. Bilanciamento delle parentesi
    open_braces = repaired.count('{')
    close_braces = repaired.count('}')
    if open_braces > close_braces:
        repaired += '}' * (open_braces - close_braces)

    # 5. Caratteri di controllo (Tab, Newline mal messi, ecc)
    repaired = repaired.replace('\t', ' ').replace('\b', '')

    try:
        # Tenta il parsing con il JSON riparato
        return json.loads(repaired)
    except json.JSONDecodeError as e:
        logger.error(f"Riparazione fallita: {e}")
        # Fallback estremo via regex
        return _emergency_regex_extract(bad_json)


def _emergency_regex_extract(text: str) -> dict:
    """Estrae i campi necessari via regex se il JSON è irrecuperabile."""
    data = {
        "text": "Mi scusi, c'è stato un errore di comunicazione tecnica nel mio modulo logico.",
        "visual_en": "1girl, solo, looking at viewer, cinematic lighting",
        "tags_en": ["masterpiece", "high quality"],
        "updates": {}
    }

    # Estrazione grezza del testo narrativo
    text_match = re.search(r'"text":\s*"(.+?)"', text, re.DOTALL)
    if text_match:
        data["text"] = text_match.group(1)

    # Estrazione grezza della descrizione visiva
    vis_match = re.search(r'"visual_en":\s*"(.+?)"', text, re.DOTALL)
    if vis_match:
        data["visual_en"] = vis_match.group(1)

    return data