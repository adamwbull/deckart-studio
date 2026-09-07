# DeckArt Studio

Custom Magic: The Gathering card faces for Tabletop Simulator. Import a Moxfield list or pasted deck, restyle cards as Full Art / Clear Art / M15 / 8th Edition, generate Gemini art in Card Maker, then publish images to Steam Cloud so TTS can load them.

This repository is the **application only**. Personal decks, generated art, and local gallery folders stay on your machine.

## Features

- Import Moxfield decks and pasted lists (commanders, sideboard, tokens)
- Card Maker with Clear Art, Full Art plates, textures, and custom display names
- Gemini **Nano Banana 2** / **Nano Banana 2 Lite** art generation from a Google API key
- Generated images save to `DeckArt/generated_ai` immediately (AI Recommended gallery)
- Publish local and Scryfall images to Steam Cloud for TTS
- Auto-update from [GitHub Releases](https://github.com/adamwbull/deckart-studio/releases)

## Run from source

Windows, Python 3.13+:

```bat
deckart.bat
```

or:

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m deckart_studio
```

## Build a Windows zip

```bat
powershell -ExecutionPolicy Bypass -File packaging\build_exe.ps1
```

Output: `dist\DeckArtStudio-<version>-win64.zip`

## Releases

Push a version tag matching `APP_VERSION` in `deckart_studio/version.py`:

```bat
git tag v0.6.8
git push origin v0.6.8
```

GitHub Actions builds the zip and publishes a Release. The installed app checks that Release on startup and can download/install it.

## Gemini art

1. Create an API key in [Google AI Studio](https://aistudio.google.com/apikey)
2. Settings → Gemini API key
3. Open Card Maker → right-hand **Gemini art** panel
4. Pick Nano Banana 2 or Lite, an art style, and a prompt
5. Generate. The PNG is written to your DeckArt `generated_ai` folder even if you do not save the card

Not affiliated with Wizards of the Coast or Google. Card data from [Scryfall](https://scryfall.com).
