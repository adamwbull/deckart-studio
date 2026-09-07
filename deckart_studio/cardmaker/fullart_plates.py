from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen

from deckart_studio.cardmaker.plate_geometry import (
    BOTTOM_FADE_TOP, CANVAS_HEIGHT, CANVAS_WIDTH, TEXT_BOX_SAMPLE, TEXT_PLATE, TITLE_BAR_SAMPLE,
    TITLE_PLATE, TYPE_PLATE,
)
from deckart_studio.cardmaker.plate_textures import PlateTexture, PlateTextureLibrary

SHADOW_ALPHA = 120


def sample_frame_color(frame: QImage, relative_point: tuple[float, float]) -> QColor:
    x = int(relative_point[0] * (frame.width() - 1))
    y = int(relative_point[1] * (frame.height() - 1))
    return frame.pixelColor(x, y)


def paint_textured_plate(painter: QPainter, rect: QRectF, tint: QColor, texture_image: QImage | None,
                         opacity: float, radius: float) -> None:
    draw_plate_shadow(painter, rect, radius)
    clip = rounded_rect_path(rect, radius)
    painter.save()
    painter.setClipPath(clip)
    if texture_image is None or texture_image.isNull():
        painter.fillPath(clip, plate_gradient(rect, tint, opacity))
    else:
        painter.setOpacity(opacity)
        painter.drawImage(rect, texture_image)
        painter.setOpacity(1.0)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        painter.fillRect(rect, with_alpha(tint, 0.48))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    painter.restore()
    painter.setPen(QPen(with_alpha(tint.darker(180), opacity), 3))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(clip)
    painter.setPen(QPen(QColor(255, 255, 255, int(80 * opacity)), 1.5))
    painter.drawPath(inset_rounded_rect_path(rect, radius, 3))


def paint_head_plate(painter: QPainter, rect: QRectF, tint: QColor, texture: PlateTexture,
                     texture_library: PlateTextureLibrary, opacity: float, radius: float) -> None:
    paint_textured_plate(painter, rect, tint, texture_library.image(texture.head), opacity, radius)


def paint_body_plate(painter: QPainter, rect: QRectF, tint: QColor, texture: PlateTexture,
                     texture_library: PlateTextureLibrary, opacity: float, radius: float) -> None:
    paint_textured_plate(painter, rect, tint, texture_library.image(texture.body), opacity, radius)


def paint_fullart_overlay(painter: QPainter, source_frame: QImage, texture_library: PlateTextureLibrary,
                          texture_id: str, head_opacity: float, body_opacity: float) -> None:
    bar_color = sample_frame_color(source_frame, TITLE_BAR_SAMPLE)
    box_color = sample_frame_color(source_frame, TEXT_BOX_SAMPLE)
    texture = texture_library.get(texture_id)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    paint_bottom_fade(painter)
    paint_head_plate(painter, TITLE_PLATE, bar_color, texture, texture_library, head_opacity, radius=16)
    paint_head_plate(painter, TYPE_PLATE, bar_color, texture, texture_library, head_opacity, radius=12)
    paint_body_plate(painter, TEXT_PLATE, box_color, texture, texture_library, body_opacity, radius=14)


def paint_bottom_fade(painter: QPainter) -> None:
    gradient = QLinearGradient(0, BOTTOM_FADE_TOP, 0, CANVAS_HEIGHT)
    gradient.setColorAt(0.0, QColor(0, 0, 0, 0))
    gradient.setColorAt(1.0, QColor(0, 0, 0, 210))
    painter.fillRect(QRectF(0, BOTTOM_FADE_TOP, CANVAS_WIDTH, CANVAS_HEIGHT - BOTTOM_FADE_TOP), gradient)


def draw_plate_shadow(painter: QPainter, rect: QRectF, radius: float) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    for spread, alpha in ((6, SHADOW_ALPHA // 4), (3, SHADOW_ALPHA // 2), (0, SHADOW_ALPHA)):
        painter.setBrush(QColor(0, 0, 0, alpha))
        shadow = rect.adjusted(-spread, -spread, spread, spread).translated(0, 4)
        painter.drawRoundedRect(shadow, radius + spread, radius + spread)


def plate_gradient(rect: QRectF, base: QColor, opacity: float) -> QLinearGradient:
    gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    gradient.setColorAt(0.0, with_alpha(base.lighter(118), opacity))
    gradient.setColorAt(1.0, with_alpha(base.darker(106), opacity))
    return gradient


def with_alpha(color: QColor, opacity: float) -> QColor:
    result = QColor(color)
    result.setAlphaF(max(0.0, min(1.0, opacity)))
    return result


def rounded_rect_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def inset_rounded_rect_path(rect: QRectF, radius: float, inset: float) -> QPainterPath:
    return rounded_rect_path(rect.adjusted(inset, inset, -inset, -inset), max(2.0, radius - 2))
