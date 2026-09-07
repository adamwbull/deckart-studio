DeckArt Studio
==============

Custom card art for Tabletop Simulator MTG decks.

GETTING STARTED
  Prefer the MSI installer from the GitHub Release when you want Start Menu, Windows Search,
  a desktop shortcut, and an optional taskbar pin. This zip is the portable copy.
  1. Unzip this folder anywhere (keep DeckArtStudio.exe together with the _internal folder).
  2. Run DeckArtStudio.exe.
  3. Click "1. Import deck from Moxfield..." and paste a Moxfield deck link (or a deck list).
     The deck is written straight into your Tabletop Simulator "Saved Objects" folder.
     Main deck, Commander(s), Sideboard, Maybeboard and Tokens each become their own stack;
     they spawn side by side in TTS. Pasted lists mark commanders with *CMDR* or a "Commander" header.
  4. Pick art for cards by clicking them, dragging images from Explorer onto them,
     or hit "3. Make deck single art..." to pick Full Art, Clear Art, or another frame and rebuild every card.
     Clear Art is full-bleed like Full Art, but with no plates: white text and a black outline sit on the picture.
     "Set artist on all cards..." (toolbar) reprints one artist credit on every face without changing the frame.
     The gallery picker has Gallery, AI Recommended, and Original tabs (click a folder heading to collapse it);
     AI Recommended lists DeckArt/generated_ai and any folder whose name ends in _ai.
     The "Original" tab fetches the card's official printings from Scryfall.

STACKS
  The "Stack:" bar under the action buttons switches between the piles in the save (the first one is
  the main deck). "+ Add card..." looks a card up on Scryfall and adds copies to the current stack;
  "+ New stack..." creates another pile. Right-click any card to set it as commander (it moves into a
  "Commander" stack beside the main deck, created if needed), move it to another stack, or remove it.
  Empty stacks are dropped when you save.

CARD BACK
  The "Card back (all cards)" box at the top right shows the back every card uses. Click it, press
  "Change card back..." or drop an image onto it to swap the back of every card in the save.
  5. "Save deck" writes the changes back. In Tabletop Simulator: Objects > Saved Objects > your deck.
  6. IMPORTANT - always run "5. Publish to Steam Cloud..." before loading a deck in TTS. It uploads every
     image that lives on your PC AND every image hosted on cards.scryfall.io to Steam Cloud (same place
     TTS's Cloud Manager uses) and rewrites the deck to the public links. Steam must be running.
     Why: Tabletop Simulator's old TLS stack cannot download from cards.scryfall.io at all (the host only
     offers an ECDSA certificate), so freshly imported cards show as blank/poker cards for everyone until
     published. The orange warning in the action bar tells you how many images still need publishing.
     Steam and Tabletop Simulator are auto-detected from your Steam libraries; if TTS lives somewhere
     unusual, point "Tabletop Simulator folder" at it in Settings. The Publish window shows what it found.

FOLDERS (all changeable in Settings (folders)... on the toolbar)
  TTS Saved Objects   Auto-detected: Documents\My Games\Tabletop Simulator\Saves\Saved Objects
  DeckArt folder      Documents\DeckArt Studio\DeckArt  - drop your art here (or add other folders
                      in the Gallery panel). Sub-folders ending in _ai show under "AI Recommended".
                      DeckArt\rendered holds every card face the Card Maker produces.
                      DeckArt\generated_ai holds every Gemini image from Card Maker.
  Gemini API key      Settings. Used by the right-hand Gemini art panel in Card Maker
                      (Nano Banana 2 or Nano Banana 2 Lite). Styles include Western Anime
                      and other fully instructed looks. Images save even if you
                      do not click Save to deck.
  Updates             Toolbar "Check for updates…" and a startup check (on by default)
                      download newer Windows zips from GitHub Releases. MSI installs
                      take the MSI when a later release includes one.
  Original art cache  Where original Scryfall card art is downloaded.
  Settings/cache      %LOCALAPPDATA%\DeckArtStudio  (settings.json, backups of every deck before
                      the first save, thumbnail cache, logs).

PORTABLE MODE
  Create an empty file named portable.txt next to DeckArtStudio.exe and all settings/cache
  will live in a "data" folder beside the EXE instead of %LOCALAPPDATA%.

TROUBLESHOOTING
  DeckArtStudio-debug.exe is the same app with a console window so errors are visible.
  Run "DeckArtStudio-debug.exe --selftest" to check the installation; it should end with SELFTEST OK.
  Crash details are also written to %LOCALAPPDATA%\DeckArtStudio\logs\deckart_studio.log.

Uses card data and images from Scryfall (https://scryfall.com). Not affiliated with Wizards of the Coast.
