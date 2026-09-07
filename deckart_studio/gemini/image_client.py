import base64
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from deckart_studio.gemini.art_styles import general_instructions, instruction_for_style
from deckart_studio.net import fetch_json
from deckart_studio.settings import AppSettings

LOGGER = logging.getLogger(__name__)
GEMINI_GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CARD_ASPECT_RATIO = "2:3"

IMAGE_MODELS = {
    "nano-banana-2": {
        "label": "Nano Banana 2",
        "api_id": "gemini-3.1-flash-image",
        "image_size": "2K",
    },
    "nano-banana-2-lite": {
        "label": "Nano Banana 2 Lite",
        "api_id": "gemini-3.1-flash-lite-image",
        "image_size": "1K",
    },
}


@dataclass(frozen=True)
class CardArtContext:
    true_name: str = ""
    display_name: str = ""
    type_line: str = ""
    rules_text: str = ""


@dataclass(frozen=True)
class GeneratedArt:
    path: Path
    prompt: str
    model_id: str


class GeminiImageError(RuntimeError):
    pass


def model_choices() -> list[tuple[str, str]]:
    return [(entry["label"], model_id) for model_id, entry in IMAGE_MODELS.items()]


def compose_art_prompt(style: str, user_prompt: str, context: CardArtContext | None = None) -> str:
    sections = [general_instructions(), card_identity_text(context or CardArtContext())]
    style_text = instruction_for_style(style)
    if style_text:
        sections.append(style_text)
    if user_prompt.strip():
        sections.append(user_prompt.strip())
    return " ".join(section for section in sections if section)


def card_identity_text(context: CardArtContext) -> str:
    true_name = context.true_name.strip()
    display_name = context.display_name.strip()
    type_line = context.type_line.strip()
    rules_text = " ".join(context.rules_text.split())
    if not any((true_name, display_name, type_line, rules_text)):
        return ""
    parts = [
        "The next lines are the printed card identity. Use them only as technical background "
        "so you know what the card is. Do not paint names, type lines, rules, or mana. "
        "Do not illustrate the rules literally; suggest the idea of the card."
    ]
    if true_name:
        parts.append(f"True card name: {true_name}.")
    if display_name and display_name != true_name:
        parts.append(f"Custom display name: {display_name}.")
    if type_line:
        parts.append(f"Type line: {type_line}.")
    if rules_text:
        parts.append(f"Rules text: {rules_text}.")
    return " ".join(parts)


def slug_for(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "generated"


class GeminiImageClient:
    def generate_card_art(self, settings: AppSettings, style: str, user_prompt: str,
                          context: CardArtContext | None = None) -> GeneratedArt:
        api_key = settings.gemini_api_key.strip()
        if not api_key:
            raise GeminiImageError("Add a Gemini API key in Settings before generating art.")
        card = context or CardArtContext()
        model = IMAGE_MODELS.get(settings.gemini_model_id, IMAGE_MODELS["nano-banana-2"])
        prompt = compose_art_prompt(style, user_prompt, card)
        LOGGER.info("generate start model=%s style=%s true_name=%s", model["api_id"], style, card.true_name)
        try:
            response = fetch_json(
                generate_url(model["api_id"], api_key),
                body={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": generation_config(model["image_size"]),
                },
                timeout=180.0,
            )
        except HTTPError as error:
            raise GeminiImageError(http_error_message(error)) from error
        except URLError as error:
            raise GeminiImageError(f"Could not reach Gemini: {error.reason}") from error
        image_bytes, mime_type = first_image_from_response(response)
        destination = save_generated_image(settings.generated_ai_folder(), card.true_name, style, image_bytes, mime_type)
        LOGGER.info("generate saved %s", destination.name)
        return GeneratedArt(destination, prompt, settings.gemini_model_id)


def generate_url(model_id: str, api_key: str) -> str:
    return f"{GEMINI_GENERATE_URL.format(model=model_id)}?{urlencode({'key': api_key})}"


def generation_config(image_size: str) -> dict:
    return {
        "responseModalities": ["TEXT", "IMAGE"],
        "imageConfig": {"aspectRatio": CARD_ASPECT_RATIO, "imageSize": image_size},
    }


def http_error_message(error: HTTPError) -> str:
    raw = error.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
        detail = str((payload.get("error") or {}).get("message") or raw)
    except ValueError:
        detail = raw
    return f"Gemini request failed ({error.code}): {detail[:300]}"


def first_image_from_response(response: dict) -> tuple[bytes, str]:
    for candidate in response.get("candidates") or []:
        for part in (candidate.get("content") or {}).get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data") or {}
            data = inline.get("data")
            if data:
                mime_type = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                return base64.b64decode(data), mime_type
    raise GeminiImageError(response_error_message(response))


def response_error_message(response: dict) -> str:
    if response.get("error"):
        return str(response["error"].get("message") or response["error"])
    return "Gemini returned no image. Try a shorter prompt or the Lite model."


def save_generated_image(folder: Path, card_name: str, style: str, image_bytes: bytes, mime_type: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    extension = "jpg" if "jpeg" in mime_type else "png"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{slug_for(card_name)}-{slug_for(style)}-{stamp}.{extension}"
    path = folder / filename
    path.write_bytes(image_bytes)
    return path
