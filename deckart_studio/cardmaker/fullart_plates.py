from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen

from deckart_studio.cardmaker.plate_geometry import (
    BOTTOM_FADE_TOP, CANVAS_HEIGHT, CANVAS_WIDTH, TEXT_PLATE, TITLE_PLATE, TYPE_PLATE,
)
from deckart_studio.cardmaker.plate_textures import PlateTextureLibrary

PLATE_RADIUS = 10.0
LINE_WIDTH = 1.8
LINE_COLOR = QColor(28, 28, 30)
SMOOTH_FILL = QColor(214, 210, 202)


def paint_aligned_plate(painter: QPainter, rect: QRectF, sheet: QImage | None, opacity: float) -> None:
    clip = rounded_rect_path(rect, PLATE_RADIUS)
    painter.save()
    painter.setClipPath(clip)
    painter.setOpacity(opacity)
    if sheet is None or sheet.isNull():
        painter.fillPath(clip, SMOOTH_FILL)
    else:
        painter.drawImage(QRectF(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT), sheet)
    painter.restore()
    painter.setPen(QPen(with_alpha(LINE_COLOR, max(0.65, opacity)), LINE_WIDTH))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(clip)


def paint_fullart_overlay(painter: QPainter, texture_library: PlateTextureLibrary,
                          texture_id: str, head_opacity: float, body_opacity: float) -> None:
    texture = texture_library.get(texture_id)
    sheet = texture_library.image(texture.sheet)
    opacity = max(head_opacity, body_opacity)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    paint_bottom_fade(painter)
    for rect in (TITLE_PLATE, TYPE_PLATE, TEXT_PLATE):
        paint_aligned_plate(painter, rect, sheet, opacity)


def paint_bottom_fade(painter: QPainter) -> None:
    gradient = QLinearGradient(0, BOTTOM_FADE_TOP, 0, CANVAS_HEIGHT)
    gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
    gradient.setColorAt(1.0, QColor(0, 0, 0, 210))
    painter.fillRect(QRectF(0, BOTTOM_FADE_TOP, CANVAS_WIDTH, CANVAS_HEIGHT - BOTTOM_FADE_TOP), gradient)


def with_alpha(color: QColor, opacity: float) -> QColor:
    result = QColor(color)
    result.setAlphaF(max(0.0, min(1.0, opacity)))
    return result


def rounded_rect_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path
