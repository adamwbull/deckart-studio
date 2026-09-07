from deckart_studio.original_art.scryfall_client import ScryfallClient


def is_token_description(description: str) -> bool:
    return description.lstrip().lower().startswith("token")


def lookup_token_card(scryfall: ScryfallClient, nickname: str, description: str) -> dict | None:
    type_line = description.splitlines()[0].strip() if description else ""
    try:
        card = scryfall.named(nickname)
    except Exception:
        return None
    if card.get("card_faces"):
        return token_card_from_faces(card, nickname, type_line)
    if type_line and card.get("type_line") != type_line:
        return None
    return card if "token" in (card.get("type_line") or "").lower() else None


def token_card_from_faces(card: dict, nickname: str, type_line: str) -> dict | None:
    faces = card.get("card_faces", [])
    for face in faces:
        if face.get("name", "").lower() == nickname.lower() and (not type_line or face.get("type_line") == type_line):
            return merge_token_face(card, face)
    for face in faces:
        if type_line and face.get("type_line") == type_line:
            return merge_token_face(card, face)
    return None


def merge_token_face(card: dict, face: dict) -> dict:
    merged = dict(card)
    merged["name"] = face.get("name", card.get("name", ""))
    merged["type_line"] = face.get("type_line", "")
    merged["oracle_text"] = face.get("oracle_text", "")
    merged["power"] = face.get("power", "")
    merged["toughness"] = face.get("toughness", "")
    merged["mana_cost"] = face.get("mana_cost", "")
    merged["colors"] = face.get("colors", card.get("colors", []))
    merged["image_uris"] = face.get("image_uris", {})
    merged.pop("card_faces", None)
    return merged
