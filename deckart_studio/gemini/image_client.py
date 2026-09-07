import base64
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError

from deckart_studio.gemini.art_styles import general_instructions, instruction_for_style
from deckart_studio.net import fetch_json
from deckart_studio.settings import AppSettings

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
class GeneratedArt:
    path: Path
    prompt: str
    model_id: str


class GeminiImageError(RuntimeError):
    pass


def model_choices() -> list[tuple[str, str]]:
    return [(entry["label"], model_id) for model_id, entry in IMAGE_MODELS.items()]


def compose_art_prompt(style: str, user_prompt: str, card_name: str = "", type_line: str = "") -> str:
    sections = [general_instructions()]
    if card_name.strip():
        sections.append(f"Card name: {card_name.strip()}.")
    if type_line.strip():
        sections.append(f"Type line: {type_line.strip()}.")
    style_text = instruction_for_style(style)
    if style_text:
        sections.append(style_text)
    if user_prompt.strip():
        sections.append(user_prompt.strip())
    return " ".join(sections)


def slug_for(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "generated"


class GeminiImageClient:
    def generate_card_art(self, settings: AppSettings, style: str, user_prompt: str,
                          card_name: str = "", type_line: str = "") -> GeneratedArt:
        api_key = settings.gemini_api_key.strip()
        if not api_key:
            raise GeminiImageError("Add a Gemini API key in Settings before generating art.")
        model = IMAGE_MODELS.get(settings.gemini_model_id, IMAGE_MODELS["nano-banana-2"])
        prompt = compose_art_prompt(style, user_prompt, card_name, type_line)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "responseFormat": {"image": {"aspectRatio": CARD_ASPECT_RATIO, "imageSize": model["image_size"]}},
            },
        }
        try:
            response = fetch_json(
                GEMINI_GENERATE_URL.format(model=model["api_id"]),
                body=payload,
                timeout=180.0,
                headers={"x-goog-api-key": api_key},
            )
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:400]
            raise GeminiImageError(f"Gemini request failed ({error.code}): {detail}") from error
        image_bytes, mime_type = first_image_from_response(response)
        destination = save_generated_image(settings.generated_ai_folder(), card_name, style, image_bytes, mime_type)
        return GeneratedArt(destination, prompt, settings.gemini_model_id)


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
