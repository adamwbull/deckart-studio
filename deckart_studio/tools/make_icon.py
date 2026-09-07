"""Draw the app icon (a stack of two cards) and write a multi-size .ico for the EXE.

Usage: python -m deckart_studio.tools.make_icon <output.ico>
"""
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen

ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
BACK_CARD_COLOR = QColor("#2f3542")
FRONT_CARD_COLOR = QColor("#e6c15b")
ART_COLOR = QColor("#3b7dd8")
OUTLINE_COLOR = QColor("#14161a")


def make_icon(output: Path) -> None:
    images = [draw_icon(size) for size in ICON_SIZES]
    output.parent.mkdir(parents=True, exist_ok=True)
    write_ico(images, output)


def draw_icon(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    unit = size / 32
    draw_card(painter, QRectF(4 * unit, 2 * unit, 18 * unit, 26 * unit), BACK_CARD_COLOR, unit, rotated=True)
    draw_card(painter, QRectF(10 * unit, 5 * unit, 18 * unit, 26 * unit), FRONT_CARD_COLOR, unit, rotated=False)
    painter.end()
    return image


def draw_card(painter: QPainter, rect: QRectF, color: QColor, unit: float, rotated: bool) -> None:
    painter.save()
    if rotated:
        painter.translate(rect.center())
        painter.rotate(-12)
        painter.translate(-rect.center())
    painter.setPen(QPen(OUTLINE_COLOR, max(1.0, unit * 0.8)))
    painter.setBrush(color)
    painter.drawRoundedRect(rect, 2 * unit, 2 * unit)
    art = rect.adjusted(2.5 * unit, 3 * unit, -2.5 * unit, -9 * unit)
    painter.setBrush(ART_COLOR)
    painter.drawRoundedRect(art, unit, unit)
    painter.restore()


def write_ico(images: list[QImage], output: Path) -> None:
    png_blobs = [png_bytes(image) for image in images]
    header = (0).to_bytes(2, "little") + (1).to_bytes(2, "little") + len(images).to_bytes(2, "little")
    directory = b""
    offset = 6 + 16 * len(images)
    for image, blob in zip(images, png_blobs):
        directory += ico_directory_entry(image.width(), len(blob), offset)
        offset += len(blob)
    output.write_bytes(header + directory + b"".join(png_blobs))


def ico_directory_entry(size: int, length: int, offset: int) -> bytes:
    dimension = 0 if size >= 256 else size
    return (bytes([dimension, dimension, 0, 0]) + (1).to_bytes(2, "little") + (32).to_bytes(2, "little")
            + length.to_bytes(4, "little") + offset.to_bytes(4, "little"))


def png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


if __name__ == "__main__":
    application = QGuiApplication(sys.argv)
    make_icon(Path(sys.argv[1]))
    print("icon written:", sys.argv[1])
