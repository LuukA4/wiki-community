import json
import re
import time

from .schemas import build_extract_schema, schema_json

SYSTEM_PROMPT = (
    "Je bent een extractie-assistent voor een fantasy-wiki. Je krijgt tekst uit een Google Drive "
    "lore-document (Nederlands) en een JSON-schema. Haal ALLE entiteiten op die expliciet in de tekst "
    "voorkomen en zet ze in het gevraagde JSON-formaat. Verzin niets: alleen entiteiten die in de tekst "
    "staan. Gebruik null of [] voor missende velden. Verwijder wiki-link tekens {} uit namen. "
    "Geef bij 'jaar' een getal (negatief = vóór jaar 0). Antwoord met ALLEEN geldige JSON, geen tekst eromheen."
)


def build_user_prompt(title: str, text: str, types) -> str:
    return (
        f"Document: {title}\n\n"
        f"Extraheer de volgende entiteitstypes als arrays in één JSON-object: {', '.join(types)}\n"
        f"JSON-schema:\n{schema_json(types)}\n\n"
        f"TEKST:\n{text}"
    )


def parse_json_object(raw: str) -> dict:
    if not raw:
        return {}
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return {}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return data if isinstance(data, dict) else {}


class Extractor:
    def __init__(self, api_key: str, model: str, pause: float = 0.5):
        from mistralai import Mistral

        self.client = Mistral(api_key=api_key)
        self.model = model
        self.pause = pause

    def extract_chunk(self, title: str, text: str, types) -> dict:
        schema = build_extract_schema(types)
        response = self.client.chat.complete(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(title, text, types)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "lore_extract", "schema": schema, "strict": False},
            },
            temperature=0,
        )
        time.sleep(self.pause)
        parsed = parse_json_object(response.choices[0].message.content)
        result = {}
        for t in types:
            items = parsed.get(t)
            if isinstance(items, list):
                result[t] = items
        return result
