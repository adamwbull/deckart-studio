from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen

from deckart_studio.cardmaker.card_design import (
    CHROME_PIECES, CardDesign, piece_path_for, uses_custom_display_name,
)
from deckart_studio.cardmaker.fullart_styles import plate_style, style_layers
from deckart_studio.cardmaker.plate_geometry import (
    CANVAS_HEIGHT, CANVAS_WIDTH, SUBTITLE_PLATE, TEXT_PLATE, TITLE_PLATE, TYPE_PLATE,
)
from deckart_studio.cardmaker.plate_textures import PlateTextureLibrary

LINE_WIDTH = 1.2
LINE_COLOR = QColor(20, 20, 22, 90)
SMOOTH_FILL = QColor(214, 210, 202)
DARK_BASE = QColor(16, 16, 18)
CARD_SIZED_FRACTION = 0.9
SHADOW_LAYERS = ((3.0, 16), (2.0, 22), (1.0, 30))
OVERLAY_SCALE = 2.0

ImageLoader = Callable[[Path | None], QImage | None]


def paint_fullart_overlay(painter: QPainter, texture_library: PlateTextureLibrary,
                          design: CardDesign, tint: QColor, image_loader: ImageLoader) -> None:
    overlay = QImage(int(CANVAS_WIDTH * OVERLAY_SCALE), int(CANVAS_HEIGHT * OVERLAY_SCALE),
                     QImage.Format.Format_ARGB32_Premultiplied)
    overlay.fill(Qt.GlobalColor.transparent)
    layer = QPainter(overlay)
    layer.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    layer.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    layer.scale(OVERLAY_SCALE, OVERLAY_SCALE)
    paint_plates(layer, texture_library, design, tint, image_loader)
    layer.end()
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.drawImage(QRectF(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT), overlay)


def paint_plates(painter: QPainter, texture_library: PlateTextureLibrary,
                 design: CardDesign, tint: QColor, image_loader: ImageLoader) -> None:
    texture = texture_library.get(design.plate_texture_id)
    sheet = texture_library.image(texture.sheet)
    opacity = max(design.head_opacity, design.body_opacity)
    dark = plate_style(design.plate_style_id).dark
    for kind, rect in plate_slots(uses_custom_display_name(design)):
        if paint_custom_piece(painter, design, kind, rect, opacity, image_loader):
            continue
        for path in style_layers(design.plate_style_id, kind, rect):
            paint_styled_plate(painter, path, sheet, opacity, tint, dark)


def plate_slots(show_subtitle_plate: bool) -> list[tuple[str, QRectF]]:
    slots = [("title", TITLE_PLATE)]
    if show_subtitle_plate:
        slots.append(("subtitle", SUBTITLE_PLATE))
    slots.extend((("type", TYPE_PLATE), ("text", TEXT_PLATE)))
    return slots


def paint_custom_piece(painter: QPainter, design: CardDesign, kind: str, rect: QRectF,
                       opacity: float, image_loader: ImageLoader) -> bool:
    if design.chrome_mode != CHROME_PIECES:
        return False
    path = piece_path_for(design, kind)
    if not path:
        return False
    image = image_loader(Path(path))
    if image is None or image.isNull():
        return False
    painter.save()
    painter.setOpacity(opacity)
    painter.drawImage(piece_target(image, rect), image)
    painter.restore()
    return True


def piece_target(image: QImage, rect: QRectF) -> QRectF:
    if image.width() >= CANVAS_WIDTH * CARD_SIZED_FRACTION and image.height() >= CANVAS_HEIGHT * CARD_SIZED_FRACTION:
        return QRectF(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT)
    return rect


def paint_styled_plate(painter: QPainter, path: QPainterPath, sheet: QImage | None,
                       opacity: float, tint: QColor, dark: bool) -> None:
    paint_soft_shadow(painter, path, opacity)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setOpacity(opacity)
    fill_plate_body(painter, path, sheet, opacity, tint, dark)
    paint_plate_bevel(painter, path, opacity, dark)
    painter.restore()
    paint_plate_rim(painter, path, opacity)


def fill_plate_body(painter: QPainter, path: QPainterPath, sheet: QImage | None,
                    opacity: float, tint: QColor, dark: bool) -> None:
    if dark:
        painter.fillPath(path, with_alpha(DARK_BASE, min(1.0, opacity + 0.04)))
        painter.setOpacity(opacity * 0.38)
    if sheet is None or sheet.isNull():
        painter.fillPath(path, SMOOTH_FILL)
    else:
        painter.fillPath(path, QBrush(sheet))
    painter.setOpacity(opacity * (0.55 if dark else 0.34))
    painter.fillPath(path, tint)


def paint_soft_shadow(painter: QPainter, path: QPainterPath, opacity: float) -> None:
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    for offset, alpha in SHADOW_LAYERS:
        painter.setBrush(QColor(0, 0, 0, int(alpha * opacity)))
        painter.drawPath(path.translated(0, offset))
    painter.restore()


def paint_plate_bevel(painter: QPainter, path: QPainterPath, opacity: float, dark: bool) -> None:
    bounds = path.boundingRect()
    gradient = QLinearGradient(bounds.left(), bounds.top(), bounds.left(), bounds.bottom())
    highlight = 70 if dark else 48
    shade = 70 if dark else 40
    gradient.setColorAt(0.0, QColor(255, 255, 255, highlight))
    gradient.setColorAt(0.4, QColor(255, 255, 255, 0))
    gradient.setColorAt(1.0, QColor(0, 0, 0, shade))
    painter.setOpacity(opacity)
    painter.fillPath(path, gradient)


def paint_plate_rim(painter: QPainter, path: QPainterPath, opacity: float) -> None:
    painter.setBrush(Qt.BrushStyle.NoBrush)
    pen = QPen(with_alpha(LINE_COLOR, opacity))
    pen.setWidthF(LINE_WIDTH)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawPath(path)


def with_alpha(color: QColor, opacity: float) -> QColor:
    result = QColor(color)
    result.setAlphaF(max(0.0, min(1.0, opacity * color.alphaF())))
    return result
