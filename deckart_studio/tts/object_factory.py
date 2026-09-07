"""Builders for the raw TTS saved-object dictionaries: cards, decks (stacks) and their 1x1 image sheets."""
import secrets
from dataclasses import dataclass

from deckart_studio.tts.card_face import CARDS_PER_SHEET_ID

STANDARD_CARD_BACK_URL = "https://backs.scryfall.io/large/0/a/0aeebaf5-8c7d-4636-9e82-8c27447861f7.jpg"
STACK_SPACING_X = 4.0


@dataclass
class BuiltCard:
    """One physical card destined for a TTS deck: name, rules text, and its face image."""

    name: str
    description: str
    face_url: str


def single_image_sheet(face_url: str, template: dict | None = None) -> dict:
    template = template or {}
    return {
        "FaceURL": face_url,
        "BackURL": template.get("BackURL", ""),
        "NumWidth": 1,
        "NumHeight": 1,
        "BackIsHidden": template.get("BackIsHidden", True),
        "UniqueBack": False,
        "Type": template.get("Type", 0),
    }


def build_card_object(sheet_id: int, card: BuiltCard, back_url: str) -> dict:
    card_object = base_object("Card", card.name)
    card_object["Description"] = card.description
    card_object["CardID"] = sheet_id * CARDS_PER_SHEET_ID
    card_object["SidewaysCard"] = False
    card_object["CustomDeck"] = {str(sheet_id): single_image_sheet(card.face_url, {"BackURL": back_url})}
    return card_object


def build_deck_object(stack_name: str, card_objects: list[dict], position_x: float = 0.0,
                      tags: tuple[str, ...] = ()) -> dict:
    deck = base_object("Deck", stack_name)
    deck["Transform"]["posX"] = position_x
    deck["Tags"] = list(tags)
    deck["SidewaysCard"] = False
    deck["DeckIDs"] = [card_object["CardID"] for card_object in card_objects]
    deck["CustomDeck"] = {key: dict(sheet) for card_object in card_objects
                          for key, sheet in card_object.get("CustomDeck", {}).items()}
    deck["ContainedObjects"] = card_objects
    return deck


def base_object(object_name: str, nickname: str) -> dict:
    return {
        "GUID": secrets.token_hex(3),
        "Name": object_name,
        "Transform": {"posX": 0.0, "posY": 1.0, "posZ": 0.0, "rotX": 0.0, "rotY": 180.0, "rotZ": 180.0,
                      "scaleX": 1.0, "scaleY": 1.0, "scaleZ": 1.0},
        "Nickname": nickname,
        "Description": "",
        "GMNotes": "",
        "AltLookAngle": {"x": 0.0, "y": 0.0, "z": 0.0},
        "ColorDiffuse": {"r": 0.713235259, "g": 0.713235259, "b": 0.713235259},
        "LayoutGroupSortIndex": 0, "Value": 0, "Locked": False, "Grid": True, "Snap": True,
        "IgnoreFoW": False, "MeasureMovement": False, "DragSelectable": True, "Autoraise": True,
        "Sticky": True, "Tooltip": True, "GridProjection": False, "HideWhenFaceDown": True, "Hands": True,
        "LuaScript": "", "LuaScriptState": "", "XmlUI": "",
    }
