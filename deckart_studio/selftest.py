"""Headless health check used by the build script:  DeckArtStudio.exe --selftest [--online]

Runs entirely against a temporary data folder, so it never touches the user's settings or decks.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

from PySide6.QtGui import QAction, QColor, QImage
from PySide6.QtWidgets import QApplication

from deckart_studio.app_paths import resource_root
from deckart_studio.cardmaker.asset_library import CardAssetLibrary
from deckart_studio.cardmaker.card_design import CardDesign
from deckart_studio.cardmaker.card_renderer import EXPORT_SCALE, PREVIEW_SCALE, CardRenderer
from deckart_studio.hosting.deck_publisher import mirror_filename_for, prepare_payload
from deckart_studio.hosting.steam_cloud import SteamCloud, SteamCloudError
from deckart_studio.hosting.steam_install import steam_status
from deckart_studio.hosting.tts_compat import is_tts_unreachable
from deckart_studio.image_source import ImageSource, local_path_to_url, tts_safe_url
from deckart_studio.gallery.gallery_library import group_name_for
from deckart_studio.moxfield.board_stacks import group_entries_by_stack, stack_label
from deckart_studio.moxfield.deck_entry import parse_decklist_text
from deckart_studio.settings import AppSettings, backup_directory
from deckart_studio.tts.board import COMMANDER_TAG
from deckart_studio.tts.deck_builder import BuiltCard, BuiltStack, build_stacks_save
from deckart_studio.tts.deck_document import DeckDocument
from deckart_studio.tts.saved_objects import discover_deck_files
from deckart_studio.ui.app_icon import application_icon
from deckart_studio.version import APP_NAME, APP_VERSION

SAMPLE_DECKLIST = """1 The Tenth Doctor (WHO) 1 *F* *CMDR*
1 Rose Tyler (WHO) 2 *CMDR*
2 Sol Ring (C21) 263
SIDEBOARD:
1 Command Tower
Maybeboard
1 Island
Tokens
1 Treasure
"""


class SelfTest:
    """Each check_* method asserts one thing; the runner reports pass/fail per check."""

    def __init__(self, online: bool):
        self.online = online
        self.workspace = Path(tempfile.mkdtemp(prefix="deckart_selftest_"))
        os.environ["DECKART_STUDIO_DATA"] = str(self.workspace / "data")
        self.application = QApplication.instance() or QApplication(sys.argv)
        self.settings = self._isolated_settings()
        self.assets = CardAssetLibrary().load()
        self.deck_path: Path | None = None

    def _isolated_settings(self) -> AppSettings:
        settings = AppSettings(saved_objects_folder=str(self.workspace / "Saved Objects"),
                               deck_art_folder=str(self.workspace / "DeckArt"))
        settings.apply_defaults()
        settings.save()
        return settings

    def checks(self) -> list[Callable[[], str]]:
        checks = [self.check_resources_present, self.check_templates_and_symbols, self.check_render_every_template,
                  self.check_settings_round_trip, self.check_decklist_parsing, self.check_decklist_stacks,
                  self.check_build_and_edit_deck, self.check_stack_editing, self.check_commander_split,
                  self.check_gallery_grouping, self.check_app_icon,
                  self.check_publish_url_rewrite, self.check_unreachable_host_detection, self.check_tts_url_sanitizing,
                  self.check_steam_detection,
                  self.check_main_window_boots, self.check_session_stacks, self.check_split_card_design,
                  self.check_custom_display_name, self.check_imported_italics, self.check_fullart_plates,
                  self.check_fullart_chrome, self.check_gemini_prompt,
                  self.check_update_versioning, self.check_token_lookup, self.check_batch_artist_override,
                  self.check_dialogs_construct, self.check_gallery_ai_tab]
        if self.online:
            checks.extend([self.check_scryfall_online, self.check_steam_cloud_upload])
        return checks

    def check_resources_present(self) -> str:
        root = resource_root() / "assets" / "cardmaker"
        textures = root / "textures" / "textures.json"
        assert (root / "templates").is_dir(), f"missing templates at {root}"
        assert (root / "fonts").is_dir(), f"missing fonts at {root}"
        assert textures.is_file(), f"missing plate textures at {textures}"
        return str(root)

    def check_templates_and_symbols(self) -> str:
        ids = {template.id for template in self.assets.template_list()}
        assert {"fullart", "m15", "clearart"} <= ids, f"templates found: {ids}"
        assert self.assets.symbols.count() >= 20, "too few mana symbols loaded"
        return f"{len(ids)} templates, {self.assets.symbols.count()} symbols"

    def check_render_every_template(self) -> str:
        renderer = CardRenderer(self.assets)
        art_path = self._synthetic_art()
        rendered = []
        for template in self.assets.template_list():
            design = sample_design(template.id, art_path)
            image = renderer.render(design, EXPORT_SCALE)
            assert not image.isNull() and image.width() > 700, f"{template.id} rendered nothing"
            renderer.render(design, PREVIEW_SCALE)
            rendered.append(template.id)
        return ", ".join(rendered)

    def _synthetic_art(self) -> str:
        image = QImage(800, 600, QImage.Format.Format_ARGB32)
        image.fill(QColor(40, 90, 160))
        path = self.workspace / "art.png"
        image.save(str(path))
        return str(path)

    def check_settings_round_trip(self) -> str:
        reloaded = AppSettings.load()
        assert reloaded.deck_art_folder == self.settings.deck_art_folder, "deck_art_folder did not persist"
        assert str(self.settings.deck_art_root()) in reloaded.gallery_folders, "DeckArt root not a gallery source"
        assert (self.settings.deck_art_root() / "README.txt").exists(), "DeckArt README not created"
        assert self.settings.generated_ai_folder().is_dir(), "generated_ai folder was not created"
        assert reloaded.art_styles, "default art styles were not saved"
        assert "Western Anime" in reloaded.art_styles, reloaded.art_styles
        assert AppSettings.from_dict({}).check_for_updates is True, "startup update check must default on"
        assert reloaded.check_for_updates is True, "startup update check did not persist on"
        return reloaded.deck_art_folder

    def check_decklist_parsing(self) -> str:
        entries = parse_decklist_text(SAMPLE_DECKLIST)
        commanders = [entry.name for entry in entries if entry.board == "commanders"]
        mainboard = [entry for entry in entries if entry.board == "mainboard"]
        assert commanders == ["The Tenth Doctor", "Rose Tyler"], commanders
        assert [entry.name for entry in mainboard] == ["Sol Ring"] and mainboard[0].quantity == 2, mainboard
        return f"{len(entries)} entries, {len(commanders)} commanders"

    def check_decklist_stacks(self) -> str:
        grouped = group_entries_by_stack(parse_decklist_text(SAMPLE_DECKLIST))
        assert list(grouped) == ["main", "commander", "sideboard", "maybeboard", "tokens"], list(grouped)
        assert [entry.name for entry in grouped["tokens"]] == ["Treasure"], grouped["tokens"]
        labels = [stack_label(key, "My Deck", len(grouped[key])) for key in grouped]
        assert labels == ["My Deck", "Commanders", "Sideboard", "Maybeboard", "Tokens"], labels
        assert stack_label("commander", "My Deck", 1) == "Commander"
        return " | ".join(labels)

    def check_build_and_edit_deck(self) -> str:
        main = [sample_card(f"Card {index}", index) for index in range(3)]
        sideboard = [sample_card(f"Side {index}", 10 + index) for index in range(2)]
        folder = Path(self.settings.saved_objects_folder)
        folder.mkdir(parents=True, exist_ok=True)
        self.deck_path = folder / "selftest-deck.json"
        save = build_stacks_save("Selftest Deck", [BuiltStack("Selftest Deck", main), BuiltStack("Sideboard", sideboard)])
        self.deck_path.write_text(json.dumps(save), encoding="utf-8")
        assert self.deck_path in discover_deck_files(folder), "deck not discovered"
        assert_unique_card_ids(save)
        return self._edit_and_reload_deck()

    def _edit_and_reload_deck(self) -> str:
        document = DeckDocument.load(self.deck_path)
        assert len(document.cards()) == 5, f"expected 5 cards, got {len(document.cards())}"
        assert [board.name for board in document.boards()] == ["Selftest Deck", "Sideboard"], document.boards()
        new_face = ImageSource.from_local(self.workspace / "art.png")
        document.set_face(document.cards()[1], new_face.to_tts_url(prefer_remote=False))
        document.save()
        assert any(backup_directory().glob("selftest-deck-*.json")), "no backup written"
        reloaded = DeckDocument.load(self.deck_path)
        assert reloaded.cards()[1].face_source().local_path == self.workspace / "art.png", "face edit did not persist"
        return "2 stacks / 5 cards, face edit + backup verified"

    def check_stack_editing(self) -> str:
        document = DeckDocument.load(self.deck_path)
        main, sideboard = document.boards()
        document.add_card(sideboard, sample_card("Added", 99))
        document.move_card(main.cards[0], sideboard)
        document.remove_card(document.boards()[0].cards[0])
        tokens = document.add_board("Tokens")
        document.add_card(tokens, sample_card("Treasure", 77))
        document.add_board("Empty stack")
        names = [(board.name, [card.nickname for card in board.cards]) for board in document.boards()]
        expected = [("Selftest Deck", ["Card 2"]), ("Sideboard", ["Side 0", "Side 1", "Added", "Card 0"]),
                    ("Tokens", ["Treasure"]), ("Empty stack", [])]
        assert names == expected, names
        assert_deck_objects_consistent(document)
        scratch = self.workspace / "stacks-scratch.json"
        document.save_as(scratch)
        saved_names = [board.name for board in DeckDocument.load(scratch).boards()]
        assert saved_names == ["Selftest Deck", "Sideboard", "Tokens"], saved_names
        return "add/move/remove/new stack verified; empty stack dropped on save"

    def check_commander_split(self) -> str:
        document = DeckDocument.load(self.deck_path)
        document.split_commanders([document.boards()[0].cards[0]])
        names = [(board.name, board.is_commander, board.card_count()) for board in document.boards()]
        assert names == [("Selftest Deck", False, 2), ("Commander", True, 1), ("Sideboard", False, 2)], names
        document.split_commanders([document.boards()[0].cards[0]])
        commander = document.commander_board()
        assert commander.name == "Commanders" and commander.card_count() == 2, (commander.name, commander.card_count())
        assert COMMANDER_TAG in commander.container["Tags"], "commander stack is not tagged"
        assert_deck_objects_consistent(document)
        return "commander stack created beside the main deck, renamed to Commanders at 2 cards"

    def check_app_icon(self) -> str:
        icon = application_icon()
        sizes = icon.availableSizes()
        assert len(sizes) >= 5 and not icon.pixmap(32, 32).isNull(), f"app icon incomplete: {sizes}"
        return f"{len(sizes)} sizes"

    def check_gallery_grouping(self) -> str:
        root = Path(self.settings.deck_art_root())
        assert group_name_for(root / "doctorwho" / "companions" / "rose.png", root) == "doctorwho / companions"
        assert group_name_for(root / "top.png", root) == root.name
        return "folder groups derived from gallery root"

    def check_publish_url_rewrite(self) -> str:
        document = DeckDocument.load(self.deck_path)
        local_paths = document.local_image_paths()
        assert local_paths == [self.workspace / "art.png"], f"unexpected local images: {local_paths}"
        replaced = document.replace_image_urls({local_path_to_url(local_paths[0]): "https://example.invalid/cloud.jpg"})
        assert replaced >= 1 and not document.local_image_paths(), "file:// URL was not rewritten"
        payload, suffix = prepare_payload(local_paths[0])
        assert suffix == ".png" and payload[:4] == b"\x89PNG", "payload preparation changed a small PNG"
        return f"{replaced} link(s) rewritten, payload {len(payload)} bytes"

    def check_unreachable_host_detection(self) -> str:
        scryfall_face = "https://cards.scryfall.io/large/front/5/e/5e36bd92-5cec-46a5-9ab3-ce4c81574770.jpg"
        assert is_tts_unreachable(scryfall_face), "cards.scryfall.io must be flagged as unreachable for TTS"
        assert not is_tts_unreachable("https://backs.scryfall.io/large/0/a/0aeebaf5.jpg"), "backs.scryfall.io is reachable"
        assert not is_tts_unreachable("https://steamusercontent-a.akamaihd.net/ugc/1/ABC/"), "Steam CDN is reachable"
        assert not is_tts_unreachable(local_path_to_url(self.workspace / "art.png")), "file URLs are not remote"
        document = DeckDocument.load(self.deck_path)
        document.replace_image_urls({url: scryfall_face for url in list(document.image_urls())[:1]})
        assert document.unreachable_image_urls() == [scryfall_face], document.unreachable_image_urls()
        assert scryfall_face in document.unpublished_image_urls(), "unreachable URL not queued for publishing"
        assert mirror_filename_for(scryfall_face).endswith(".jpg"), mirror_filename_for(scryfall_face)
        return f"{len(document.unpublished_image_urls())} link(s) queued for Publish"

    def check_tts_url_sanitizing(self) -> str:
        scryfall = "https://cards.scryfall.io/large/front/b/f/bf5e0a50.jpg?1783914672"
        assert tts_safe_url(scryfall) == "https://cards.scryfall.io/large/front/b/f/bf5e0a50.jpg", tts_safe_url(scryfall)
        steam = "https://steamusercontent-a.akamaihd.net/ugc/1/ABC/"
        assert tts_safe_url(steam) == steam, "non-image URLs must pass through untouched"
        document = DeckDocument.load(self.deck_path)
        document.replace_image_urls({url: scryfall for url in document.image_urls()})
        repaired = document.sanitize_image_urls()
        assert repaired > 0 and not any("?" in url for url in document.image_urls()), "deck links not sanitized"
        return f"query stripped; {repaired} deck link(s) repaired"

    def check_steam_detection(self) -> str:
        status = steam_status()
        return status.describe().replace("\n", " | ")

    def check_steam_cloud_upload(self) -> str:
        try:
            with SteamCloud() as cloud:
                url = cloud.upload("DeckArtStudio_selftest.txt", b"DeckArt Studio self-test")
        except SteamCloudError as error:
            return f"skipped ({str(error).splitlines()[0]})"
        assert url.startswith("https://") and "/ugc/" in url, url
        return url

    def check_main_window_boots(self) -> str:
        from deckart_studio.ui.app_context import AppContext
        from deckart_studio.ui.main_window import MainWindow
        self.context = AppContext(self.settings)
        self.context.refresh_gallery()
        self.window = MainWindow(self.context)
        self.window.show()
        self._pump_events(0.5)
        assert self.context.session.has_deck(), "main window did not open the selftest deck"
        title = self.window.windowTitle()
        assert title.startswith(f"{APP_NAME} {APP_VERSION}"), title
        assert self.context.session.document.path.name in title, title
        settings_labels = [action.text() for action in self.window.findChildren(QAction)]
        assert "Settings" in settings_labels
        assert "Settings (folders)…" not in settings_labels
        return f"opened {self.context.session.document.path.name}"

    def check_session_stacks(self) -> str:
        session = self.context.session
        assert session.board_names() == ["Selftest Deck", "Sideboard"], session.board_names()
        assert len(session.cards()) == 3, "main stack should be shown first"
        session.set_active_board(1)
        assert len(session.cards()) == 2, "switching stacks did not change the visible cards"
        session.add_cards(sample_card("Session card", 55), 2)
        assert len(session.cards()) == 4, "add_cards did not add two copies"
        session.move_card(3, 0)
        session.remove_card(2)
        assert [len(board.cards) for board in session.boards()] == [4, 2], [len(board.cards) for board in session.boards()]
        assert session.render_scope_name() == "selftest-deck - Sideboard", session.render_scope_name()
        assert session.render_scope_name_for(0) == "selftest-deck", session.render_scope_name_for(0)
        from deckart_studio.ui.deck_restyle_dialog import snapshot_entire_deck
        snapped = snapshot_entire_deck(session)
        assert len(snapped) == len(session.all_cards()), (len(snapped), len(session.all_cards()))
        assert {card.board_index for card in snapped} == {0, 1}, {card.board_index for card in snapped}
        session.set_active_board(0)
        self._pump_events(0.3)
        assert not session.common_back_source().is_empty(), "no common card back resolved"
        return "switch/add/move/remove through the session verified"

    def check_split_card_design(self) -> str:
        from deckart_studio.cardmaker.card_design import design_from_scryfall, is_split_design
        from deckart_studio.cardmaker.card_renderer import CardRenderer, EXPORT_SCALE
        from deckart_studio.original_art.scryfall_client import ScryfallClient
        card = ScryfallClient().named("Wear // Tear")
        design = design_from_scryfall(card, "clearart")
        assert is_split_design(design), design.mana_cost
        assert design.name == "Wear // Tear", design.name
        assert design.mana_cost == "{1}{R} // {W}", design.mana_cost
        assert "Wear —" in design.rules_text and "Tear —" in design.rules_text, design.rules_text
        image = CardRenderer(self.assets).render(design, EXPORT_SCALE)
        assert not image.isNull(), "split card did not render"
        return f"{design.name} | {design.mana_cost}"

    def check_custom_display_name(self) -> str:
        from deckart_studio.cardmaker.card_design import CardDesign, custom_display_title, uses_custom_display_name
        from deckart_studio.cardmaker.card_renderer import CardRenderer, EXPORT_SCALE
        design = sample_design("clearart", self._synthetic_art())
        assert not uses_custom_display_name(design), "custom name should be off by default"
        design.use_custom_name = True
        design.custom_name = "The Doctor"
        design.real_name = "Selftest Wizard"
        primary, subtitle = custom_display_title(design)
        assert primary == "The Doctor" and subtitle == "Selftest Wizard", (primary, subtitle)
        image = CardRenderer(self.assets).render(design, EXPORT_SCALE)
        assert not image.isNull(), "custom display name card did not render"
        design.custom_name = ""
        design.name = "River's Trick"
        design.real_name = "Dovin's Veto"
        primary, subtitle = custom_display_title(design)
        assert primary == "River's Trick" and subtitle == "Dovin's Veto", (primary, subtitle)
        image = CardRenderer(self.assets).render(design, EXPORT_SCALE)
        assert not image.isNull(), "display-name-only custom card did not render"
        design.template_id = "fullart"
        design.center_title = True
        design.center_subtitle = True
        design.center_description = True
        assert not CardRenderer(self.assets).render(design, EXPORT_SCALE).isNull(), "centered full art names did not render"
        assert design.center_subtitle is True
        return f"{design.name} over {design.real_name}"

    def check_imported_italics(self) -> str:
        from deckart_studio.cardmaker.card_design import format_imported_rules, rules_with_flavor
        from deckart_studio.cardmaker.text_layout import WordItem, tokenize_paragraph
        from deckart_studio.ui.card_maker_dialog import split_description

        reminder = format_imported_rules("Flying (This creature can't be blocked except by creatures with flying or reach.)")
        assert "*(This creature can't be blocked except by creatures with flying or reach.)*" in reminder, reminder
        type_line, imported = split_description(
            'Creature — Human\nFlying (This creature can\'t be blocked.)\n"A remembered line."\n— Himmel'
        )
        assert type_line == "Creature — Human"
        assert "*(This creature can't be blocked.)*" in imported, imported
        assert '*"A remembered line."*' in imported, imported
        assert "*— Himmel*" in imported, imported
        combined = rules_with_flavor({
            "oracle_text": "Flying (This creature can't be blocked.)",
            "flavor_text": '"Line one."\n— Name',
        })
        assert "*(This creature can't be blocked.)*" in combined, combined
        assert '*"Line one."*' in combined, combined
        assert "*— Name*" in combined, combined
        words = [item for item in tokenize_paragraph("*(This creature can't be blocked.)*") if isinstance(item, WordItem)]
        assert words and all(item.italic for item in words), words
        twice = format_imported_rules(reminder)
        assert twice == reminder, twice
        return "reminder and flavor italics applied on import"

    def check_fullart_plates(self) -> str:
        from deckart_studio.cardmaker.card_renderer import CardRenderer, EXPORT_SCALE
        from deckart_studio.cardmaker.plate_textures import LEGACY_TEXTURE_IDS
        smooth = sample_design("fullart", self._synthetic_art())
        smooth.plate_texture_id = "smooth"
        stone = sample_design("fullart", self._synthetic_art())
        stone.plate_texture_id = "stone"
        granite = sample_design("fullart", self._synthetic_art())
        granite.plate_texture_id = "granite"
        renderer = CardRenderer(self.assets)
        assert not renderer.render(smooth, EXPORT_SCALE).isNull(), "smooth full art did not render"
        assert not renderer.render(stone, EXPORT_SCALE).isNull(), "stone full art did not render"
        assert not renderer.render(granite, EXPORT_SCALE).isNull(), "granite full art did not render"
        assert self.assets.plate_textures.get("arcane").id == LEGACY_TEXTURE_IDS["arcane"]
        stone_sheet = self.assets.plate_textures.image(self.assets.plate_textures.get("stone").sheet)
        assert stone_sheet is not None and not stone_sheet.isNull()
        assert texture_grain(stone_sheet) > 2.5, "stone plate is a flat color, not a photograph"
        count = len(self.assets.plate_textures.list())
        assert count >= 8, count
        return f"{count} photographic plate sheets, stone + granite OK"

    def check_fullart_chrome(self) -> str:
        from deckart_studio.cardmaker.fullart_styles import plate_style_list
        from deckart_studio.cardmaker.plate_geometry import TITLE_PLATE
        renderer = CardRenderer(self.assets)
        art = self._synthetic_art()
        rendered = []
        for style in plate_style_list():
            design = sample_design("fullart", art)
            design.plate_style_id = style.id
            design.color_id = "blue"
            image = renderer.render(design, EXPORT_SCALE)
            assert not image.isNull(), style.id
            rendered.append((style.id, image))
        blue = sample_design("fullart", art)
        blue.color_id = "blue"
        red = sample_design("fullart", art)
        red.color_id = "red"
        blue_pixel = title_plate_sample(renderer.render(blue, EXPORT_SCALE))
        red_pixel = title_plate_sample(renderer.render(red, EXPORT_SCALE))
        assert blue_pixel != red_pixel, (blue_pixel, red_pixel)
        inked = sample_design("fullart", art)
        inked.title_color = "#ff00aa"
        default_pixel = title_name_sample(renderer.render(blue, EXPORT_SCALE))
        pink_pixel = title_name_sample(renderer.render(inked, EXPORT_SCALE))
        assert pink_pixel != default_pixel, (pink_pixel, default_pixel)
        eighth = self.assets.template("8th")
        assert eighth.resolve_color_id("vehicle") == "artifact", eighth.resolve_color_id("vehicle")
        assert TITLE_PLATE.width() > 0
        from deckart_studio.cardmaker.card_design import CHROME_PIECES
        piece = QImage(int(TITLE_PLATE.width()), int(TITLE_PLATE.height()), QImage.Format.Format_ARGB32)
        piece.fill(QColor(255, 0, 0))
        piece_path = self.workspace / "title-piece.png"
        piece.save(str(piece_path))
        custom = sample_design("fullart", art)
        custom.chrome_mode = CHROME_PIECES
        custom.title_piece_path = str(piece_path)
        red = title_plate_sample(renderer.render(custom, EXPORT_SCALE))
        assert red[0] > 180 and red[0] > red[1] and red[0] > red[2], red
        return f"{len(rendered)} plate styles, frame tint, text color, and custom title piece"

    def check_gemini_prompt(self) -> str:
        from deckart_studio.gemini.art_styles import DEFAULT_ART_STYLES, STYLE_INSTRUCTIONS, merge_default_art_styles
        from deckart_studio.gemini.image_client import (
            CardArtContext, compose_art_prompt, first_image_from_response, generation_config, slug_for,
        )
        from deckart_studio.ui.ai_art_panel import friendly_worker_error
        lives = CardArtContext(true_name="Parallel Lives", type_line="Enchantment")
        western = compose_art_prompt("Western Anime", "Two Jennys on a rooftop", lives)
        oil = compose_art_prompt("Painterly oil", "Two Jennys on a rooftop", lives)
        custom = compose_art_prompt("My custom neon", "alley rain", CardArtContext(true_name="Sol Ring"))
        renamed = compose_art_prompt(
            "Western Anime",
            "a rooftop standoff",
            CardArtContext(true_name="Dovin's Veto", display_name="River's Trick",
                           type_line="Instant", rules_text="Counter target spell."),
        )
        assert "Parallel Lives" in western and "Two Jennys" in western
        assert "technical background" in western and "Do not paint names" in western
        assert "cel-shad" in western.lower() and "lower third" in western
        assert "card frame" in western
        assert "oil painting" in oil.lower() and "cel-shad" not in oil.lower()
        assert "Art style: My custom neon." in custom
        assert "True card name: Dovin's Veto." in renamed
        assert "Custom display name: River's Trick." in renamed
        assert "Counter target spell." in renamed
        assert "Do not illustrate the rules literally" in renamed
        assert generation_config("2K")["imageConfig"]["aspectRatio"] == "2:3"
        assert "responseFormat" not in generation_config("2K")
        assert friendly_worker_error("GeminiImageError: Gemini request failed (400): bad aspect") == (
            "Gemini request failed (400): bad aspect"
        )
        assert set(DEFAULT_ART_STYLES) == set(STYLE_INSTRUCTIONS)
        assert all(len(text) > 280 for text in STYLE_INSTRUCTIONS.values())
        merged = merge_default_art_styles(["Painterly oil", "My neon"])
        assert merged[0] == "Western Anime" and "Painterly oil" in merged and merged[-1] == "My neon"
        assert slug_for("The Tenth Doctor") == "the-tenth-doctor"
        fake = {"candidates": [{"content": {"parts": [{"inlineData": {"data": "aGVsbG8=", "mimeType": "image/png"}}]}}]}
        data, mime = first_image_from_response(fake)
        assert data == b"hello" and mime == "image/png"
        return "western anime + card identity + imageConfig"

    def check_update_versioning(self) -> str:
        from deckart_studio.ui.main_window import window_title
        from deckart_studio.updates import (
            is_msi_install, is_newer_version, release_msi_url, release_zip_url, update_download_folder,
            updater_process_flags, version_tuple, write_msi_updater_script,
        )
        assert version_tuple("0.7.5") > version_tuple("0.7.4")
        assert is_newer_version("0.7.5", "0.6.9")
        assert not is_newer_version("0.7.5", "0.7.5")
        assets = {"assets": [
            {"name": "DeckArtStudio-0.7.5-win64.zip", "browser_download_url": "https://example.invalid/app.zip"},
            {"name": "DeckArtStudio-0.7.5-win64.msi", "browser_download_url": "https://example.invalid/app.msi"},
        ]}
        assert release_zip_url(assets, "0.7.5").endswith("app.zip")
        assert release_msi_url(assets, "0.7.5").endswith("app.msi")
        assert update_download_folder().name == "DeckArtStudioUpdates"
        assert update_download_folder(self.workspace).resolve() == self.workspace.resolve()
        marker = self.workspace / "install_kind.txt"
        marker.write_text("msi", encoding="utf-8")
        assert is_msi_install(self.workspace)
        assert window_title() == f"{APP_NAME} {APP_VERSION}"
        assert window_title("selftest.json", "0.8.0") == (
            f"{APP_NAME} {APP_VERSION} — selftest.json — update 0.8.0 available"
        )
        script = write_msi_updater_script(Path("C:/tmp/DeckArtStudio.msi"), self.workspace, 4242)
        bat = script.read_text(encoding="utf-8")
        assert "timeout" not in bat
        assert "ping -n 2 127.0.0.1" in bat
        assert "Start-Process msiexec" in bat
        assert "4242" in bat
        assert updater_process_flags() & subprocess.DETACHED_PROCESS == 0
        return "semver + zip/msi lookup"

    def check_gallery_ai_tab(self) -> str:
        from deckart_studio.gallery.gallery_library import GallerySection
        from deckart_studio.ui.gallery_dock import SECTION_CHOICES
        from deckart_studio.ui.gallery_picker_dialog import GalleryPickerDialog
        from deckart_studio.ui.gallery_picker_panel import AI_TAB
        image = QImage(64, 64, QImage.Format.Format_ARGB32)
        image.fill(QColor(20, 140, 90))
        generated = self.settings.generated_ai_folder() / "selftest_ai.png"
        image.save(str(generated))
        self.context.refresh_gallery()
        dialog = GalleryPickerDialog(self.context, "AI tab", "Card back", False, self.window)
        titles = dialog._panel.tab_titles()
        assert any(title.startswith("AI Recommended") for title in titles), titles
        assert any(title.startswith("Gallery") for title in titles), titles
        assert any(title.startswith("Original") for title in titles), titles
        dialog._panel.show_section(GallerySection.AI_RECOMMENDED)
        assert dialog._panel._tabs.currentIndex() == AI_TAB
        assert SECTION_CHOICES["AI Recommended"] == (GallerySection.AI_RECOMMENDED,)
        recommended = self.context.gallery.images(GallerySection.AI_RECOMMENDED)
        assert any(item.path == generated.resolve() for item in recommended), recommended
        dialog.close()
        return "AI Recommended tab, dock section, generated_ai classification"

    def check_token_lookup(self) -> str:
        from deckart_studio.cardmaker.token_lookup import lookup_token_card
        from deckart_studio.original_art.scryfall_client import ScryfallClient
        token = lookup_token_card(ScryfallClient(), "Soldier", "Token Creature — Soldier\n")
        assert token is not None and token.get("name") == "Soldier", token
        assert "Goblin" not in token.get("type_line", ""), token.get("type_line")
        return "Soldier token resolves to Soldier face, not Goblin"

    def check_batch_artist_override(self) -> str:
        from deckart_studio.cardmaker.deck_batch import BatchCard
        batch = self.context.deck_face_batch()
        card = BatchCard(0, 0, "Selftest Wizard", "Creature\nDoes things.", None, "selftest")
        forced = batch._design_for(card, None, "clearart", "paidforwinrar")
        assert forced.artist == "paidforwinrar", forced.artist
        assert forced.template_id == "clearart", forced.template_id
        kept = batch._design_for(card, None, None, "Ada")
        assert kept.artist == "Ada", kept.artist
        assert kept.template_id == "fullart", kept.template_id
        return "artist override and keep-template fallback"

    def check_dialogs_construct(self) -> str:
        from deckart_studio.ui.add_card_dialog import AddCardDialog
        from deckart_studio.ui.card_maker_dialog import CardMakerDialog
        from deckart_studio.ui.deck_restyle_dialog import DeckRestyleDialog
        from deckart_studio.ui.gallery_picker_dialog import GalleryPickerDialog
        from deckart_studio.ui.import_deck_dialog import ImportDeckDialog
        from deckart_studio.ui.publish_dialog import PublishDialog
        from deckart_studio.ui.settings_dialog import SettingsDialog
        card = self.context.session.card(0)
        dialogs = [CardMakerDialog(self.context, card, self.window), DeckRestyleDialog(self.context, self.window),
                   DeckRestyleDialog(self.context, self.window, artist_only=True),
                   ImportDeckDialog(self.context, self.window), SettingsDialog(self.context, self.window),
                   PublishDialog(self.context, self.window), AddCardDialog(self.context, "Selftest Deck", self.window),
                   GalleryPickerDialog(self.context, "Card back", "Card back", False, self.window)]
        for dialog in dialogs:
            dialog.show()
        self._pump_events(0.4)
        for dialog in dialogs:
            dialog.close()
        return ", ".join(type(dialog).__name__ for dialog in dialogs)

    def check_scryfall_online(self) -> str:
        card = self.context.scryfall.named("Sol Ring")
        assert card.get("name") == "Sol Ring", card
        suggestions = self.context.scryfall.autocomplete("Tenth Doc")
        assert any("Tenth Doctor" in name for name in suggestions), suggestions
        return "named + autocomplete OK"

    def _pump_events(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.application.processEvents()
            time.sleep(0.02)


def sample_card(name: str, image_number: int) -> BuiltCard:
    return BuiltCard(name=name, description="Creature\nDoes things.", face_url=f"https://example.invalid/{image_number}.png")


def assert_unique_card_ids(save: dict) -> None:
    card_ids = [card["CardID"] for stack in save["ObjectStates"] for card in stack["ContainedObjects"]]
    assert len(card_ids) == len(set(card_ids)), f"CardIDs collide across stacks: {card_ids}"


def assert_deck_objects_consistent(document: DeckDocument) -> None:
    """Every stack's DeckIDs and CustomDeck must mirror the cards it actually contains, or TTS shows blanks."""
    for board in document.boards():
        state = board.container
        assert state["DeckIDs"] == [card.card_id for card in board.cards], (board.name, state["DeckIDs"])
        assert set(state["CustomDeck"]) == {str(card.sheet_id) for card in board.cards}, (board.name, state["CustomDeck"].keys())


def title_plate_sample(image: QImage) -> tuple[int, int, int]:
    from deckart_studio.cardmaker.plate_geometry import TITLE_PLATE
    x = int((TITLE_PLATE.left() + 8) * EXPORT_SCALE)
    y = int((TITLE_PLATE.center().y()) * EXPORT_SCALE)
    color = image.pixelColor(x, y)
    return color.red(), color.green(), color.blue()


def title_name_sample(image: QImage) -> tuple[int, int, int]:
    x = int(90 * EXPORT_SCALE)
    y = int(62 * EXPORT_SCALE)
    color = image.pixelColor(x, y)
    return color.red(), color.green(), color.blue()


def texture_grain(image: QImage) -> float:
    deltas = []
    offset = 4
    for y in range(0, image.height() - offset, 11):
        for x in range(0, image.width() - offset, 11):
            here = image.pixelColor(x, y)
            neighbor = image.pixelColor(x + offset, y)
            deltas.append(abs(_luminance(here) - _luminance(neighbor)))
    return sum(deltas) / max(1, len(deltas))


def _luminance(color: QColor) -> float:
    return color.red() * 0.3 + color.green() * 0.59 + color.blue() * 0.11


def sample_design(template_id: str, art_path: str) -> CardDesign:
    return CardDesign(template_id=template_id, color_id="blue", name="Selftest Wizard", mana_cost="{2}{U}{U}",
                      type_line="Legendary Creature — Wizard", rules_text="Flying\n{T}: Draw a card.\n*Flavor.*",
                      power="2", toughness="3", artist="Selftest", art_path=art_path)


def run_selftest(argv: list[str]) -> int:
    print(f"{APP_NAME} {APP_VERSION} self-test (frozen={getattr(sys, 'frozen', False)})")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    suite = SelfTest(online="--online" in argv)
    failures = 0
    for check in suite.checks():
        failures += not _run_check(check)
    print("SELFTEST OK" if failures == 0 else f"SELFTEST FAILED ({failures} failing)")
    return 0 if failures == 0 else 1


def _run_check(check: Callable[[], str]) -> bool:
    try:
        detail = check()
    except Exception as error:
        print(f"  FAIL  {check.__name__}: {type(error).__name__}: {error}")
        return False
    print(f"  ok    {check.__name__}: {detail}")
    return True


if __name__ == "__main__":
    raise SystemExit(run_selftest(sys.argv[1:]))
