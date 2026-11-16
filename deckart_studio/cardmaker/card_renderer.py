from math import cos, sin, tau
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPainterPath

from deckart_studio.cardmaker.asset_library import CardAssetLibrary
from deckart_studio.cardmaker.card_design import (
    CardDesign, custom_display_title, is_split_design, split_design_parts, uses_custom_display_name,
)
from deckart_studio.cardmaker.card_template import CardTemplate
from deckart_studio.cardmaker.fullart_plates import paint_fullart_overlay
from deckart_studio.cardmaker.fullart_styles import tint_for_frame_color
from deckart_studio.cardmaker.plate_geometry import PLATE_RIGHT, PLATE_TEXT_INSET, SUBTITLE_TEXT_Y
from deckart_studio.cardmaker.text_colors import resolved_text_color
from deckart_studio.cardmaker.symbols import mana_cost_tokens
from deckart_studio.cardmaker.text_layout import (
    RulesTextLayouter, SymbolItem, WordItem, font_factory_for, laid_line_width, symbol_side,
)

PREVIEW_SCALE = 2.0
EXPORT_SCALE = 2.0
ART_BACKGROUND = QColor(20, 20, 24)
BORDER_COLOR = QColor(0, 0, 0)
TEXT_COLOR = QColor(0, 0, 0)
CLEAR_FILL = QColor(255, 255, 255)
CLEAR_OUTLINE = QColor(0, 0, 0)
CLEAR_OUTLINE_TITLE = 2.0
CLEAR_OUTLINE_BODY = 1.8
CLEAR_OUTLINE_SMALL = 1.2
MANA_CLUSTER_STEP = 31.0
SPLIT_TITLE_ROW_STEP = 34.0
CUSTOM_NAME_SUBTITLE_SIZE_RATIO = 0.52
CUSTOM_NAME_SUBTITLE_GAP = 4.0


class CardRenderer:
    """Paints a CardDesign onto a card-sized QImage using the template's frame, fonts, and symbols."""

    def __init__(self, assets: CardAssetLibrary):
        self.assets = assets

    def render(self, design: CardDesign, scale: float = PREVIEW_SCALE) -> QImage:
        template = self.assets.template(design.template_id)
        image = QImage(round(template.canvas_width * scale), round(template.canvas_height * scale),
                       QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
                               | QPainter.RenderHint.TextAntialiasing)
        painter.scale(scale, scale)
        self._paint(painter, design, template)
        painter.end()
        return image

    def _paint(self, painter: QPainter, design: CardDesign, template: CardTemplate) -> None:
        canvas = QRect(0, 0, template.canvas_width, template.canvas_height)
        painter.fillRect(canvas, BORDER_COLOR)
        self._paint_art(painter, design, template)
        if not template.is_clear():
            self._paint_frame(painter, design, template, canvas)
        self._paint_mana_cost(painter, design, template)
        self._paint_title_and_type(painter, design, template)
        self._paint_rules_text(painter, design, template)
        self._paint_power_toughness(painter, design, template)
        self._paint_bottom_info(painter, design, template)
        self._apply_corner_mask(painter, canvas)

    def _paint_art(self, painter: QPainter, design: CardDesign, template: CardTemplate) -> None:
        window = template.art_window()
        painter.fillRect(window, ART_BACKGROUND)
        art = self.assets.image(Path(design.art_path)) if design.art_path else None
        if art is None or art.isNull():
            return
        painter.save()
        painter.setClipRect(window)
        painter.drawImage(art_target_rect(art, window, design), art)
        painter.restore()

    def _paint_frame(self, painter: QPainter, design: CardDesign, template: CardTemplate, canvas: QRect) -> None:
        color = template.color(design.color_id)
        if template.is_fullart():
            self._paint_fullart_frame(painter, design)
        else:
            painter.drawImage(canvas, masked_frame(self.assets.image(color.frame), self.assets.image(template.frame_mask)))
        if design.is_legendary() and design.show_legendary_crown and template.legendary_supported and color.legendary:
            painter.drawImage(canvas, self.assets.image(color.legendary))
        if design.is_creature() and color.pt_box is not None and not template.is_clear():
            box = template.layout.get("pt", {}).get("box", [571, 929, 137, 75])
            painter.drawImage(QRectF(*box), self.assets.image(color.pt_box))

    def _paint_fullart_frame(self, painter: QPainter, design: CardDesign) -> None:
        paint_fullart_overlay(
            painter,
            self.assets.plate_textures,
            design,
            tint_for_frame_color(design.color_id),
            self.assets.image,
        )

    def _paint_mana_cost(self, painter: QPainter, design: CardDesign, template: CardTemplate) -> None:
        if is_split_design(design):
            self._paint_split_mana_rows(painter, design, template)
            return
        self._paint_mana_row(painter, design.mana_cost, template, float(template.layout.get("mana", {}).get("y", 59)))

    def _paint_split_mana_rows(self, painter: QPainter, design: CardDesign, template: CardTemplate) -> None:
        _, manas, _ = split_design_parts(design)
        base_y = float(template.layout.get("mana", {}).get("y", 59))
        for row, mana in enumerate(manas):
            self._paint_mana_row(painter, mana, template, base_y + row * SPLIT_TITLE_ROW_STEP)

    def _paint_mana_row(self, painter: QPainter, mana_cost: str, template: CardTemplate, y: float) -> None:
        tokens = mana_cost_tokens(mana_cost)
        if not tokens:
            return
        spec = template.layout.get("mana", {})
        radius = float(spec.get("radius", 17.5))
        step = MANA_CLUSTER_STEP if template.is_clear() else float(spec.get("step", 39))
        diameter = radius * 2
        right = float(spec.get("right_x", 692))
        width = mana_row_width(len(tokens), diameter, step)
        left = right - width
        if template.is_clear():
            paint_mana_fade(painter, left, y, width, diameter)
        x = left
        for token in tokens:
            self._paint_symbol(painter, token, QRectF(x, y, diameter, diameter), shadow=not template.is_clear())
            x += step

    def _paint_symbol(self, painter: QPainter, token: str, target: QRectF, shadow: bool) -> None:
        symbol = self.assets.symbol_image(token)
        if shadow:
            painter.setBrush(QColor(0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(target.translated(-1, 3.5))
        if symbol is not None and not symbol.isNull():
            painter.save()
            clip = QPainterPath()
            clip.addEllipse(target)
            painter.setClipPath(clip)
            painter.drawImage(target, symbol)
            painter.restore()
        else:
            self._paint_symbol_fallback(painter, token, target)

    def _paint_symbol_fallback(self, painter: QPainter, token: str, target: QRectF) -> None:
        painter.setBrush(QColor(200, 200, 200))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(target)
        painter.setPen(TEXT_COLOR)
        painter.setFont(self.assets.font("Beleren Bold", target.height() * 0.6))
        painter.drawText(target, Qt.AlignmentFlag.AlignCenter, token)

    def _paint_title_and_type(self, painter: QPainter, design: CardDesign, template: CardTemplate) -> None:
        if uses_custom_display_name(design):
            self._paint_custom_display_titles(painter, design, template)
        elif is_split_design(design):
            self._paint_split_titles(painter, design, template)
        else:
            self._paint_single_title(painter, design, template)
        type_spec = template.layout.get("type", {})
        type_limit = template.canvas_width - float(type_spec.get("x", 62)) - 100
        self._paint_single_line(painter, design.type_line, type_spec, type_limit, template,
                               CLEAR_OUTLINE_BODY, design.center_description,
                               resolved_text_color(design, template, "type"))

    def _paint_custom_display_titles(self, painter: QPainter, design: CardDesign, template: CardTemplate) -> None:
        primary, subtitle = custom_display_title(design)
        if not primary:
            return
        title_spec = template.layout.get("title", {})
        mana_spec = template.layout.get("mana", {})
        base_x = float(title_spec.get("x", 62))
        base_y = float(title_spec.get("y", 56))
        mana_for_limit = design.mana_cost
        if is_split_design(design):
            _, manas, _ = split_design_parts(design)
            mana_for_limit = manas[0] if manas else design.mana_cost
        mana_step = MANA_CLUSTER_STEP if template.is_clear() else float(mana_spec.get("step", 39))
        radius = float(mana_spec.get("radius", 17.5))
        diameter = radius * 2
        mana_width = mana_row_width(len(mana_cost_tokens(mana_for_limit)), diameter, mana_step)
        title_limit = template.canvas_width - base_x - mana_width - 28
        main_size = float(title_spec.get("size", 40))
        main_spec = dict(title_spec)
        main_font = self._font_fitting(main_spec.get("font", "Beleren Bold"), main_size, primary,
                                       title_limit, main_spec.get("spacing", 0.0))
        self._paint_single_line(painter, primary, main_spec, title_limit, template, CLEAR_OUTLINE_TITLE,
                               design.center_title, resolved_text_color(design, template, "title"))
        if not subtitle:
            return
        subtitle_spec, subtitle_limit = self._subtitle_layout(template, title_spec, base_y, main_font,
                                                             title_limit, main_size)
        self._paint_single_line(painter, subtitle, subtitle_spec, subtitle_limit, template, CLEAR_OUTLINE_BODY,
                               design.center_subtitle, resolved_text_color(design, template, "subtitle"))

    def _paint_single_title(self, painter: QPainter, design: CardDesign, template: CardTemplate) -> None:
        mana_spec = template.layout.get("mana", {})
        mana_step = MANA_CLUSTER_STEP if template.is_clear() else float(mana_spec.get("step", 39))
        mana_width = mana_row_width(len(mana_cost_tokens(design.mana_cost)), float(mana_spec.get("radius", 17.5)) * 2,
                                   mana_step)
        title_limit = template.canvas_width - float(template.layout.get("title", {}).get("x", 62)) - mana_width - 28
        self._paint_single_line(painter, design.name, template.layout.get("title", {}), title_limit, template,
                               CLEAR_OUTLINE_TITLE, design.center_title,
                               resolved_text_color(design, template, "title"))

    def _paint_split_titles(self, painter: QPainter, design: CardDesign, template: CardTemplate) -> None:
        names, manas, _ = split_design_parts(design)
        title_spec = template.layout.get("title", {})
        mana_spec = template.layout.get("mana", {})
        base_x = float(title_spec.get("x", 62))
        base_y = float(title_spec.get("y", 56))
        mana_step = MANA_CLUSTER_STEP if template.is_clear() else float(mana_spec.get("step", 39))
        radius = float(mana_spec.get("radius", 17.5))
        diameter = radius * 2
        right = float(mana_spec.get("right_x", 692))
        for row, (name, mana) in enumerate(zip(names, manas)):
            mana_width = mana_row_width(len(mana_cost_tokens(mana)), diameter, mana_step)
            title_limit = right - base_x - mana_width - 16
            spec = dict(title_spec)
            spec["y"] = base_y + row * SPLIT_TITLE_ROW_STEP
            self._paint_single_line(painter, name, spec, title_limit, template, CLEAR_OUTLINE_TITLE,
                                   design.center_title, resolved_text_color(design, template, "title"))

    def _subtitle_layout(self, template: CardTemplate, title_spec: dict, base_y: float, main_font,
                         title_limit: float, main_size: float) -> tuple[dict, float]:
        raw = template.layout.get("subtitle")
        subtitle_spec = dict(raw) if raw else {key: value for key, value in title_spec.items() if key != "size"}
        if raw and raw.get("size"):
            subtitle_spec["size"] = float(raw["size"])
        else:
            subtitle_spec["size"] = max(16.0, main_size * CUSTOM_NAME_SUBTITLE_SIZE_RATIO)
        if template.is_fullart():
            subtitle_spec["x"] = float(subtitle_spec.get("x", PLATE_TEXT_INSET + 38))
            subtitle_spec["y"] = float(subtitle_spec.get("y", SUBTITLE_TEXT_Y))
            return subtitle_spec, PLATE_RIGHT - float(subtitle_spec["x"]) - PLATE_TEXT_INSET
        metrics = QFontMetricsF(main_font)
        subtitle_spec.setdefault("x", title_spec.get("x", 62))
        subtitle_spec["y"] = float(subtitle_spec.get(
            "y", base_y + metrics.ascent() + metrics.descent() + CUSTOM_NAME_SUBTITLE_GAP))
        return subtitle_spec, title_limit

    def _paint_single_line(self, painter: QPainter, text: str, spec: dict, max_width: float,
                           template: CardTemplate, outline_width: float, centered: bool = False,
                           fill: QColor | None = None) -> None:
        size = float(spec.get("size", 40))
        font = self._font_fitting(spec.get("font", "Beleren Bold"), size, text, max_width, spec.get("spacing", 0.0))
        left = float(spec.get("x", 62))
        width = QFontMetricsF(font).horizontalAdvance(text)
        x = left + max(0.0, (max_width - width) / 2) if centered else left
        origin = QPointF(x, float(spec.get("y", 56)) + QFontMetricsF(font).ascent())
        paint_line_text(painter, origin, text, font, template.is_clear(), outline_width, fill)

    def _font_fitting(self, logical: str, size: float, text: str, max_width: float, spacing: float):
        while size > 12:
            font = self.assets.font(logical, size)
            font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, spacing)
            if QFontMetricsF(font).horizontalAdvance(text) <= max_width:
                return font
            size -= 1
        return self.assets.font(logical, size)

    def _paint_rules_text(self, painter: QPainter, design: CardDesign, template: CardTemplate) -> None:
        spec = template.layout.get("text", {})
        box = QRectF(float(spec.get("x", 66)), float(spec.get("y", 650)), float(spec.get("width", 682)),
                     float(spec.get("height", 292)) - (18 if design.is_creature() else 0))
        layouter = RulesTextLayouter(font_factory_for(self.assets, spec.get("font", "MPlantin")))
        laid = layouter.fit(design.rules_text, box, float(spec.get("max_size", 31)), float(spec.get("min_size", 17)))
        top_offset = box.top() + max(0.0, (box.height() - laid.total_height) / 2)
        for line in laid.lines:
            left = box.left()
            if design.center_description:
                left += max(0.0, (box.width() - laid_line_width(line)) / 2)
            self._paint_line(painter, line, left, top_offset, laid.font_size, spec.get("font", "MPlantin"),
                            template, resolved_text_color(design, template, "rules"))

    def _paint_line(self, painter: QPainter, line, left: float, top_offset: float, size: float, font_name: str,
                    template: CardTemplate, fill: QColor) -> None:
        baseline = top_offset + line.baseline
        for placed in line.items:
            if isinstance(placed.item, WordItem):
                font = self.assets.font(font_name, size, placed.item.italic)
                paint_line_text(painter, QPointF(left + placed.x, baseline), placed.item.text, font,
                                template.is_clear(), CLEAR_OUTLINE_BODY, fill)
            elif isinstance(placed.item, SymbolItem):
                side = symbol_side(size)
                target = QRectF(left + placed.x, baseline - side * 0.88, side, side)
                self._paint_symbol(painter, placed.item.token, target, shadow=False)

    def _paint_power_toughness(self, painter: QPainter, design: CardDesign, template: CardTemplate) -> None:
        if not design.is_creature():
            return
        spec = template.layout.get("pt", {})
        font = self.assets.font(spec.get("font", "Beleren Bold"), float(spec.get("size", 39)))
        metrics = QFontMetricsF(font)
        text = design.power_toughness()
        center_x = float(spec.get("text_center_x", 645))
        baseline = float(spec.get("text_y", 936)) + metrics.ascent()
        origin = QPointF(center_x - metrics.horizontalAdvance(text) / 2, baseline)
        paint_line_text(painter, origin, text, font, template.is_clear(), CLEAR_OUTLINE_TITLE,
                        resolved_text_color(design, template, "pt"))

    def _paint_bottom_info(self, painter: QPainter, design: CardDesign, template: CardTemplate) -> None:
        self._paint_info_line(painter, design.artist, template.layout.get("artist", {}), "Matrix Bold Small Caps", 24,
                             template, resolved_text_color(design, template, "artist"))
        if not template.is_clear():
            self._paint_artist_brush(painter, design, template.layout.get("artist", {}))
        self._paint_info_line(painter, design.legal_text, template.layout.get("legal", {}), "MPlantin", 17, template,
                             resolved_text_color(design, template, "legal"))

    def _paint_info_line(self, painter: QPainter, text: str, spec: dict, default_font: str, default_size: float,
                         template: CardTemplate, fill: QColor) -> None:
        if not text:
            return
        font = self.assets.font(spec.get("font", default_font), float(spec.get("size", default_size)))
        origin = QPointF(float(spec.get("x", 48)), float(spec.get("y", 995)) + QFontMetricsF(font).ascent())
        if template.is_clear():
            paint_outlined_text(painter, origin, text, font, fill, CLEAR_OUTLINE, CLEAR_OUTLINE_SMALL)
            return
        painter.setFont(font)
        painter.setPen(fill)
        painter.drawText(origin, text)

    def _paint_artist_brush(self, painter: QPainter, design: CardDesign, spec: dict) -> None:
        brush = self.assets.artist_brush()
        if not design.artist or brush is None or "brush" not in spec:
            return
        x, y = spec["brush"]
        template = self.assets.template(design.template_id)
        painter.drawImage(QRectF(float(x), float(y), 21, 13),
                          tinted(brush, resolved_text_color(design, template, "artist")))

    def _apply_corner_mask(self, painter: QPainter, canvas: QRect) -> None:
        mask = self.assets.card_mask()
        if mask is None or mask.isNull():
            return
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawImage(canvas, mask)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)


def mana_row_width(count: int, diameter: float, step: float) -> float:
    if count <= 0:
        return 0.0
    return diameter + (count - 1) * step


def paint_mana_fade(painter: QPainter, left: float, top: float, width: float, height: float) -> None:
    """Subtle rectangle behind the whole mana row, fading out toward the title."""
    fade = 54.0
    pad = 5.0
    bar = QRectF(left - fade, top - pad, fade + width + pad + 2, height + pad * 2)
    gradient = QLinearGradient(bar.left(), bar.center().y(), left, bar.center().y())
    gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
    gradient.setColorAt(1.0, QColor(0, 0, 0, 80))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(bar, 4.0, 4.0)


def paint_line_text(painter: QPainter, origin: QPointF, text: str, font: QFont, outlined: bool,
                    outline_width: float, fill: QColor | None = None) -> None:
    color = fill or TEXT_COLOR
    if outlined:
        paint_outlined_text(painter, origin, text, font, color, CLEAR_OUTLINE, outline_width)
        return
    painter.setFont(font)
    painter.setPen(color)
    painter.drawText(origin, text)


def outline_offsets(width: float) -> list[QPointF]:
    count = 16
    return [QPointF(cos(index * tau / count) * width, sin(index * tau / count) * width) for index in range(count)]


def paint_outlined_text(painter: QPainter, origin: QPointF, text: str, font: QFont,
                        fill: QColor, outline: QColor, outline_width: float) -> None:
    painter.save()
    painter.setFont(font)
    painter.setPen(outline)
    for offset in outline_offsets(outline_width):
        painter.drawText(origin + offset, text)
    painter.setPen(fill)
    painter.drawText(origin, text)
    painter.restore()


def art_target_rect(art: QImage, window: QRect, design: CardDesign) -> QRectF:
    """Cover the art window with the image (like CSS background-size: cover), then apply the user's zoom and pan."""
    cover_scale = max(window.width() / art.width(), window.height() / art.height()) * max(0.05, design.art_zoom)
    width, height = art.width() * cover_scale, art.height() * cover_scale
    left = window.center().x() - width / 2 + design.art_offset_x
    top = window.center().y() - height / 2 + design.art_offset_y
    return QRectF(left, top, width, height)


def masked_frame(frame: QImage, mask: QImage | None) -> QImage:
    if mask is None or mask.isNull():
        return frame
    result = frame.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(result)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    painter.drawImage(result.rect(), mask)
    painter.end()
    return result


def tinted(source: QImage, color: QColor) -> QImage:
    result = QImage(source.size(), QImage.Format.Format_ARGB32_Premultiplied)
    result.fill(color)
    painter = QPainter(result)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    painter.drawImage(0, 0, source)
    painter.end()
    return result
