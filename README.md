# DeckArt Studio

Custom Magic: The Gathering card faces for Tabletop Simulator. Import a Moxfield list or pasted deck, restyle cards as Full Art / Clear Art / M15 / 8th Edition, generate Gemini art in Card Maker, then publish images to Steam Cloud so TTS can load them.

This repository is the **application only**. Personal decks, generated art, and local gallery folders stay on your machine.

## Features

- Import Moxfield decks and pasted lists (commanders, sideboard, tokens)
- Card Maker with Clear Art, Full Art plates, textures, and custom display names
- Gemini **Nano Banana 2** / **Nano Banana 2 Lite** art generation, including a **Western Anime** style and full per-style illustration instructions
- Generated images save to `DeckArt/generated_ai` immediately (AI Recommended gallery)
- Publish local and Scryfall images to Steam Cloud for TTS
- Auto-update from [GitHub Releases](https://github.com/adamwbull/deckart-studio/releases) (startup check on by default)
- Windows MSI: Start Menu, Search, optional desktop shortcut and taskbar pin

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

## Build Windows zip and MSI

```bat
powershell -ExecutionPolicy Bypass -File packaging\build_exe.ps1
```

Output:

- `dist\DeckArtStudio-<version>-win64.zip` (portable / in-place updates)
- `dist\DeckArtStudio-<version>-win64.msi` (Program Files, Start Menu, Search)

The MSI offers desktop shortcut and taskbar pin during setup. The zip is still required so older installs can auto-update.

## Releases

Push a version tag matching `APP_VERSION` in `deckart_studio/version.py`:

```bat
git tag v0.7.0
git push origin v0.7.0
```

GitHub Actions builds the zip and MSI and publishes a Release. Installed copies check that Release on startup (on by default) and can download/install it.

To Authenticode-sign a local build (needed to clear the SmartScreen unknown-publisher warning), set `DECKART_SIGN_PFX` to an OV/EV or Azure Trusted Signing PFX and optionally `DECKART_SIGN_PASSWORD`. A self-signed certificate will not remove that warning.

## Gemini art

1. Create an API key in [Google AI Studio](https://aistudio.google.com/apikey)
2. Settings → Gemini API key
3. Open Card Maker → right-hand **Gemini art** panel
4. Pick Nano Banana 2 or Lite, an art style (Western Anime is the new default), and a prompt
5. Generate. The PNG is written to your DeckArt `generated_ai` folder even if you do not save the card. Each style already carries full layout, lighting, and technique instructions.

Not affiliated with Wizards of the Coast or Google. Card data from [Scryfall](https://scryfall.com).
