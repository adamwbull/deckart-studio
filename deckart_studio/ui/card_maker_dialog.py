from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QScrollArea, QSlider, QSplitter, QVBoxLayout, QWidget,
)

from deckart_studio.cardmaker.card_design import CardDesign, design_from_scryfall, ensure_real_name
from deckart_studio.cardmaker.card_lookup import CardLookup
from deckart_studio.cardmaker.card_renderer import EXPORT_SCALE, PREVIEW_SCALE
from deckart_studio.gallery.thumbnail_loader import resolve_source_path
from deckart_studio.image_source import ImageSource
from deckart_studio.tts.card_face import CardFace
from deckart_studio.gemini.image_client import CardArtContext
from deckart_studio.ui.ai_art_panel import AiArtPanel
from deckart_studio.ui.app_context import AppContext
from deckart_studio.ui.card_name_search import CardNameSearch
from deckart_studio.ui.drop_zone import DropZone
from deckart_studio.ui.gallery_picker_dialog import pick_image_for_card
from deckart_studio.ui.styles import PRIMARY_BUTTON_STYLE
from deckart_studio.ui.symbol_palette import SymbolPalette
from deckart_studio.ui.workers import run_in_background

PREVIEW_WIDTH = 520
PREVIEW_DEBOUNCE_MS = 120
ZOOM_SLIDER_SCALE = 100
OPACITY_SLIDER_SCALE = 100


class CardMakerDialog(QDialog):
    """Design a full custom card face (frame, art, name, mana, rules, P/T…) with a live preview."""

    def __init__(self, context: AppContext, card: CardFace, parent: QWidget | None = None):
        super().__init__(parent)
        self.context = context
        self.card = card
        self.design, self._loaded_from_store = initial_design(context, card)
        ensure_real_name(self.design, card.nickname)
        self.result_source: ImageSource | None = None
        self._symbol_target: QWidget | None = None
        self._preview = QLabel()
        self._status = QLabel()
        self._preview_timer = QTimer(self)
        self._build_widgets()
        self._build_layout()
        self._bind_widgets()
        self.setWindowTitle(f"Card Maker — {card.nickname}")
        self.resize(1680, 920)
        self._prefill_from_scryfall_if_blank()
        self.schedule_preview()

    def _build_widgets(self) -> None:
        self._search = CardNameSearch(self.context.scryfall)
        self._template = QComboBox()
        self._color = QComboBox()
        self._name = QLineEdit(self.design.name)
        self._name_label = QLabel("Card name")
        self._use_custom_name = QCheckBox("Custom display name")
        self._custom_name = QLineEdit(self.design.custom_name)
        self._custom_name.setEnabled(False)
        self._custom_name.setPlaceholderText("Optional — overrides display name when filled")
        self._real_name = QLineEdit(self.design.real_name)
        self._real_name.setEnabled(False)
        self._real_name.setPlaceholderText("Shown smaller under the display name")
        self._mana = QLineEdit(self.design.mana_cost)
        self._type = QLineEdit(self.design.type_line)
        self._rules = QPlainTextEdit(self.design.rules_text)
        self._power = QLineEdit(self.design.power)
        self._toughness = QLineEdit(self.design.toughness)
        self._artist = QLineEdit(self.design.artist)
        self._legal = QLineEdit(self.design.legal_text)
        self._crown = QCheckBox("Legendary crown when type line says Legendary")
        self._art_label = QLabel()
        self._zoom = QSlider(Qt.Orientation.Horizontal)
        self._offset_x = QSlider(Qt.Orientation.Horizontal)
        self._offset_y = QSlider(Qt.Orientation.Horizontal)
        self._plate_texture = QComboBox()
        self._plate_opacity = QSlider(Qt.Orientation.Horizontal)
        self._plate_opacity_label = QLabel()
        self._plate_panel = QWidget()
        self._palette = SymbolPalette(self.context.card_assets)
        self._ai_panel = AiArtPanel(self.context)
        self._populate_choice_widgets()

    def _populate_choice_widgets(self) -> None:
        for template in self.context.card_assets.template_list():
            self._template.addItem(template.name, template.id)
        self._template.setCurrentIndex(max(0, self._template.findData(self.design.template_id)))
        self._refresh_color_choices()
        self._crown.setChecked(self.design.show_legendary_crown)
        self._use_custom_name.setChecked(self.design.use_custom_name)
        self._custom_name.setText(self.design.custom_name)
        self._custom_name.setEnabled(self.design.use_custom_name)
        self._real_name.setText(self.design.real_name)
        self._real_name.setEnabled(self.design.use_custom_name)
        self._refresh_name_field_labels()
        self._zoom.setRange(50, 300)
        self._zoom.setValue(int(self.design.art_zoom * ZOOM_SLIDER_SCALE))
        self._offset_x.setRange(-400, 400)
        self._offset_x.setValue(int(self.design.art_offset_x))
        self._offset_y.setRange(-400, 400)
        self._offset_y.setValue(int(self.design.art_offset_y))
        self._rules.setPlaceholderText("Rules text. Use {U}, {T}, {2} for symbols and *asterisks* for flavor/italics.")
        self._mana.setPlaceholderText("{2}{U}{U}")
        self._search.set_text(self.card.nickname)
        self._populate_plate_texture_choices()
        self._plate_opacity.setRange(40, 100)
        self._plate_opacity.setValue(int(max(self.design.head_opacity, self.design.body_opacity) * OPACITY_SLIDER_SCALE))
        self._update_opacity_labels()
        self._refresh_plate_panel_visibility()
        self._update_art_label()

    def _populate_plate_texture_choices(self) -> None:
        self._plate_texture.blockSignals(True)
        self._plate_texture.clear()
        for texture in self.context.card_assets.plate_textures.list():
            self._plate_texture.addItem(texture.label, texture.id)
        index = max(0, self._plate_texture.findData(self.design.plate_texture_id))
        self._plate_texture.setCurrentIndex(index)
        self._plate_texture.blockSignals(False)

    def _update_opacity_labels(self) -> None:
        self._plate_opacity_label.setText(f"{self._plate_opacity.value()}%")

    def _refresh_plate_panel_visibility(self) -> None:
        template = self.context.card_assets.template(self._template.currentData())
        self._plate_panel.setVisible(template.is_fullart())

    def _refresh_color_choices(self) -> None:
        template = self.context.card_assets.template(self._template.currentData())
        self._color.blockSignals(True)
        self._color.clear()
        for color in template.colors.values():
            self._color.addItem(color.label, color.id)
        self._color.setCurrentIndex(max(0, self._color.findData(self.design.color_id)))
        self._color.blockSignals(False)

    def _build_layout(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._form_scroll_area())
        splitter.addWidget(self._preview_column())
        splitter.addWidget(self._ai_panel)
        splitter.setSizes([560, 560, 360])
        layout = QVBoxLayout(self)
        layout.addWidget(splitter, 1)
        layout.addLayout(self._button_row())

    def _form_scroll_area(self) -> QScrollArea:
        form_host = QWidget()
        form = QFormLayout(form_host)
        form.addRow(self._search_heading(), self._search)
        form.addRow("Template", self._template)
        form.addRow("Frame color", self._color)
        form.addRow("", self._plate_options_panel())
        form.addRow(self._name_label, self._name)
        form.addRow("", self._use_custom_name)
        form.addRow("Custom name", self._custom_name)
        form.addRow("Real card name", self._real_name)
        form.addRow("Artwork", self._artwork_controls())
        form.addRow("Art zoom", self._zoom)
        form.addRow("Art X", self._offset_x)
        form.addRow("Art Y", self._offset_y)
        form.addRow("Mana cost", self._mana)
        form.addRow("Type line", self._type)
        form.addRow("Rules text", self._rules)
        form.addRow("Click to insert a symbol", self._palette)
        form.addRow("Power / Toughness", self._power_toughness_row())
        form.addRow("Legal text", self._legal)
        form.addRow("Artist", self._artist)
        form.addRow("", self._crown)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_host)
        return scroll

    def _plate_options_panel(self) -> QWidget:
        layout = QFormLayout(self._plate_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        opacity_row = QWidget()
        opacity_layout = QHBoxLayout(opacity_row)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.addWidget(self._plate_opacity, 1)
        opacity_layout.addWidget(self._plate_opacity_label)
        layout.addRow("Plate texture", self._plate_texture)
        layout.addRow("Plate opacity", opacity_row)
        return self._plate_panel

    @staticmethod
    def _search_heading() -> QLabel:
        heading = QLabel("Look up card")
        heading.setStyleSheet("font-weight: bold;")
        return heading

    def _artwork_controls(self) -> QWidget:
        host = QWidget()
        pick_button = QPushButton("Pick from gallery…")
        pick_button.clicked.connect(self._pick_art_from_gallery)
        original_button = QPushButton("Use original card art")
        original_button.clicked.connect(lambda: self._fetch_original_art(self._name.text() or self.card.nickname))
        drop = DropZone("…or drop an image file here")
        drop.sourcesDropped.connect(lambda sources: self._set_art(sources[0]))
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._art_label)
        layout.addWidget(pick_button)
        layout.addWidget(original_button)
        layout.addWidget(drop)
        return host

    def _power_toughness_row(self) -> QWidget:
        host = QWidget()
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        self._power.setPlaceholderText("Power (blank = not a creature)")
        self._toughness.setPlaceholderText("Toughness")
        layout.addWidget(self._power)
        layout.addWidget(QLabel("/"))
        layout.addWidget(self._toughness)
        return host

    def _preview_column(self) -> QWidget:
        column = QWidget()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self._preview.setMinimumWidth(PREVIEW_WIDTH)
        self._status.setWordWrap(True)
        layout = QVBoxLayout(column)
        layout.addWidget(self._preview, 1)
        layout.addWidget(self._status)
        return column

    def _button_row(self) -> QHBoxLayout:
        save_button = QPushButton("Save to deck")
        save_button.setStyleSheet(PRIMARY_BUTTON_STYLE)
        save_button.setDefault(True)
        save_button.setToolTip("Render this face, put it on the card and save the deck JSON in Saved Objects")
        save_button.clicked.connect(self._save_to_deck)
        export_button = QPushButton("Export PNG…")
        export_button.clicked.connect(self._export_png)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addWidget(export_button)
        row.addStretch(1)
        row.addWidget(cancel_button)
        row.addWidget(save_button)
        return row

    def _bind_widgets(self) -> None:
        self._search.cardChosen.connect(self._prefill_from_scryfall)
        self._template.currentIndexChanged.connect(self._on_template_changed)
        self._color.currentIndexChanged.connect(self.schedule_preview)
        for line_edit in (self._name, self._mana, self._type, self._power, self._toughness, self._artist, self._legal,
                          self._custom_name, self._real_name):
            line_edit.textChanged.connect(self.schedule_preview)
        self._name.textChanged.connect(self._on_name_changed)
        self._rules.textChanged.connect(self.schedule_preview)
        self._crown.toggled.connect(self.schedule_preview)
        self._use_custom_name.toggled.connect(self._on_custom_name_toggled)
        self._plate_texture.currentIndexChanged.connect(self.schedule_preview)
        self._plate_opacity.valueChanged.connect(self._on_plate_opacity_changed)
        for slider in (self._zoom, self._offset_x, self._offset_y):
            slider.valueChanged.connect(self.schedule_preview)
        self._palette.symbolClicked.connect(self._insert_symbol)
        self._ai_panel.artGenerated.connect(self._set_art_path)
        self._ai_panel.openSettingsRequested.connect(self._open_settings)
        for line_edit in (self._name, self._type, self._custom_name, self._real_name):
            line_edit.textChanged.connect(self._sync_ai_card_context)
        self._rules.textChanged.connect(self._sync_ai_card_context)
        self._use_custom_name.toggled.connect(self._sync_ai_card_context)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self.refresh_preview)
        QApplication.instance().focusChanged.connect(self._on_focus_changed)
        self._sync_ai_card_context()

    def _on_custom_name_toggled(self, enabled: bool) -> None:
        self._custom_name.setEnabled(enabled)
        self._real_name.setEnabled(enabled)
        if enabled and not self._real_name.text().strip():
            nickname = self.card.nickname.strip()
            display = self._name.text().strip()
            self._real_name.setText(nickname if nickname and nickname != display else display)
        self._refresh_name_field_labels()
        self.schedule_preview()

    def _on_name_changed(self) -> None:
        if not self._use_custom_name.isChecked():
            self._real_name.setText(self._name.text())

    def _refresh_name_field_labels(self) -> None:
        if self._use_custom_name.isChecked():
            self._name_label.setText("Display name")
        else:
            self._name_label.setText("Card name")

    def _on_plate_opacity_changed(self) -> None:
        self._update_opacity_labels()
        self.schedule_preview()

    def _sync_ai_card_context(self) -> None:
        if self._use_custom_name.isChecked():
            display = self._custom_name.text().strip() or self._name.text().strip()
            true_name = self._real_name.text().strip() or self._name.text().strip()
        else:
            display = ""
            true_name = self._name.text().strip()
        self._ai_panel.set_card_context(CardArtContext(
            true_name=true_name,
            display_name=display,
            type_line=self._type.text(),
            rules_text=self._rules.toPlainText(),
        ))

    def _open_settings(self) -> None:
        from deckart_studio.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.context, self)
        if dialog.exec():
            self._ai_panel.reload_from_settings()

    def _on_template_changed(self) -> None:
        self.design.color_id = self._color.currentData() or self.design.color_id
        self._refresh_color_choices()
        self._refresh_plate_panel_visibility()
        self.schedule_preview()

    def _on_focus_changed(self, _old: QWidget | None, new: QWidget | None) -> None:
        if new in (self._mana, self._rules):
            self._symbol_target = new

    def _insert_symbol(self, token: str) -> None:
        target = self._symbol_target or self._rules
        if target is self._mana:
            self._mana.insert(token)
        else:
            self._rules.insertPlainText(token)
        target.setFocus()

    def _pick_art_from_gallery(self) -> None:
        outcome = pick_image_for_card(self.context, self.card, self)
        if outcome.source is not None:
            self._set_art(outcome.source)

    def _set_art(self, source: ImageSource) -> None:
        self._set_art_path(str(resolve_source_path(source.display_key())))

    def _set_art_path(self, path: str) -> None:
        self.design.art_path = path
        self._update_art_label()
        self.schedule_preview()

    def _update_art_label(self) -> None:
        self._art_label.setText(Path(self.design.art_path).name if self.design.art_path else "No artwork chosen")

    def _prefill_from_scryfall_if_blank(self) -> None:
        if not self._loaded_from_store and self.card.nickname:
            self._prefill_from_scryfall(self.card.nickname)

    def _prefill_from_scryfall(self, card_name: str) -> None:
        self._status.setText(f"Looking up “{card_name}” on Scryfall…")
        run_in_background(lambda report: self.context.scryfall.named(card_name),
                          self._on_scryfall_card, lambda error: self._status.setText("Scryfall lookup failed."), owner=self)

    def _on_scryfall_card(self, card: object) -> None:
        fetched = design_from_scryfall(card, self._template.currentData())
        fetched.art_path, fetched.legal_text = self.design.art_path, self.design.legal_text
        self.design = fetched
        self._load_design_into_widgets()
        self._status.setText(f"Filled from Scryfall: {fetched.name}")
        if not self.design.art_path:
            self._download_art_crop(card)

    def _fetch_original_art(self, card_name: str) -> None:
        self._status.setText(f"Fetching original art for “{card_name}”…")
        run_in_background(lambda report: self.context.scryfall.named(card_name),
                          self._download_art_crop, lambda error: self._status.setText("Scryfall lookup failed."), owner=self)

    def _download_art_crop(self, card: object) -> None:
        run_in_background(lambda report: CardLookup.art_crop_path(card),
                          self._on_art_crop, lambda error: self._status.setText("Could not download the original art."),
                          owner=self)

    def _on_art_crop(self, path: object) -> None:
        if path:
            self._set_art_path(str(path))
            self._status.setText("Using the original card art.")

    def _load_design_into_widgets(self) -> None:
        self._name.setText(self.design.name)
        self._custom_name.setText(self.design.custom_name)
        self._real_name.setText(self.design.real_name)
        self._use_custom_name.setChecked(self.design.use_custom_name)
        self._custom_name.setEnabled(self.design.use_custom_name)
        self._real_name.setEnabled(self.design.use_custom_name)
        self._refresh_name_field_labels()
        self._populate_plate_texture_choices()
        self._plate_opacity.setValue(int(max(self.design.head_opacity, self.design.body_opacity) * OPACITY_SLIDER_SCALE))
        self._update_opacity_labels()
        self._refresh_plate_panel_visibility()
        self._mana.setText(self.design.mana_cost)
        self._type.setText(self.design.type_line)
        self._rules.setPlainText(self.design.rules_text)
        self._power.setText(self.design.power)
        self._toughness.setText(self.design.toughness)
        self._artist.setText(self.design.artist)
        self._refresh_color_choices()
        self.schedule_preview()

    def _read_widgets_into_design(self) -> CardDesign:
        self.design.template_id = self._template.currentData() or self.design.template_id
        self.design.color_id = self._color.currentData() or self.design.color_id
        name = self._name.text()
        self.design.name = name
        self.design.mana_cost = self._mana.text()
        self.design.use_custom_name = self._use_custom_name.isChecked()
        self.design.custom_name = self._custom_name.text()
        self.design.real_name = self._real_name.text() if self.design.use_custom_name else name
        self.design.plate_texture_id = self._plate_texture.currentData() or "stone"
        opacity = self._plate_opacity.value() / OPACITY_SLIDER_SCALE
        self.design.head_opacity = opacity
        self.design.body_opacity = opacity
        self.design.type_line, self.design.rules_text = self._type.text(), self._rules.toPlainText()
        self.design.power, self.design.toughness = self._power.text(), self._toughness.text()
        self.design.artist, self.design.legal_text = self._artist.text(), self._legal.text()
        self.design.show_legendary_crown = self._crown.isChecked()
        self.design.art_zoom = self._zoom.value() / ZOOM_SLIDER_SCALE
        self.design.art_offset_x, self.design.art_offset_y = float(self._offset_x.value()), float(self._offset_y.value())
        return self.design

    def schedule_preview(self) -> None:
        self._preview_timer.start(PREVIEW_DEBOUNCE_MS)

    def refresh_preview(self) -> None:
        image = self.context.card_renderer.render(self._read_widgets_into_design(), PREVIEW_SCALE)
        pixmap = QPixmap.fromImage(image).scaledToWidth(PREVIEW_WIDTH, Qt.TransformationMode.SmoothTransformation)
        self._preview.setPixmap(pixmap)

    def _save_to_deck(self) -> None:
        self.result_source = self._render_into_store()
        self.context.session.assign_face(self.card.index, self.result_source)
        self.context.session.save()
        self.accept()

    def _render_into_store(self) -> ImageSource:
        design = self._read_widgets_into_design()
        scope = self.context.session.render_scope_name()
        render_path = self.context.design_store.render_path(scope, self.card.index, design.name or self.card.nickname)
        self._render_to(design, render_path)
        self.context.design_store.save(design, render_path)
        self.context.thumbnails.forget(str(render_path))
        return ImageSource.from_local(render_path, design.name)

    def _export_png(self) -> None:
        target, _filter = QFileDialog.getSaveFileName(self, "Export card PNG", f"{self._name.text() or 'card'}.png", "PNG (*.png)")
        if target:
            self._render_to(self._read_widgets_into_design(), Path(target))
            self._status.setText(f"Exported {target}")

    def _render_to(self, design: CardDesign, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.context.card_renderer.render(design, EXPORT_SCALE).save(str(path), "PNG")


def initial_design(context: AppContext, card: CardFace) -> tuple[CardDesign, bool]:
    face = context.session.face_source(card)
    stored = context.design_store.load_design_for_face(face.local_path)
    if stored is not None:
        ensure_real_name(stored, card.nickname)
        return stored, True
    design = CardDesign(name=card.nickname, real_name=card.nickname)
    design.type_line, design.rules_text = split_description(card.description)
    if face.local_path is not None and context.gallery.contains(face.local_path):
        design.art_path = str(face.local_path)
    return design, False


def split_description(description: str) -> tuple[str, str]:
    lines = description.strip().splitlines()
    if not lines:
        return "", ""
    return lines[0].strip(), "\n".join(line for line in lines[1:]).strip()


def design_card_face(context: AppContext, card: CardFace, parent: QWidget | None) -> ImageSource | None:
    dialog = CardMakerDialog(context, card, parent)
    dialog.exec()
    return dialog.result_source
