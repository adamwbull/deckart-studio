import re
from dataclasses import dataclass, field

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont, QFontMetricsF

from deckart_studio.cardmaker.symbols import SYMBOL_TOKEN

INLINE_TOKEN = re.compile(r"(\{[^}]+\}|\*|\s+)")
LINE_HEIGHT_FACTOR = 1.08
PARAGRAPH_GAP_FACTOR = 0.45
SYMBOL_SIZE_FACTOR = 0.9
SYMBOL_GAP_FACTOR = 0.08


@dataclass
class WordItem:
    text: str
    italic: bool


@dataclass
class SymbolItem:
    token: str


@dataclass
class SpaceItem:
    pass


InlineItem = WordItem | SymbolItem | SpaceItem


@dataclass
class PlacedItem:
    item: InlineItem
    x: float
    width: float


@dataclass
class LaidLine:
    items: list[PlacedItem] = field(default_factory=list)
    top: float = 0.0
    baseline: float = 0.0
    height: float = 0.0


@dataclass
class LaidText:
    lines: list[LaidLine]
    font_size: float
    total_height: float


def tokenize_paragraph(paragraph: str) -> list[InlineItem]:
    items: list[InlineItem] = []
    italic = False
    for piece in INLINE_TOKEN.split(paragraph):
        if not piece:
            continue
        if piece == "*":
            italic = not italic
        elif SYMBOL_TOKEN.fullmatch(piece):
            items.append(SymbolItem(piece[1:-1]))
        elif piece.isspace():
            items.append(SpaceItem())
        else:
            items.append(WordItem(piece, italic))
    return items


class RulesTextLayouter:
    """Wraps rules text with inline mana symbols into a box, shrinking the font until it fits."""

    def __init__(self, font_factory):
        self._font_factory = font_factory

    def fit(self, text: str, box: QRectF, max_size: float, min_size: float) -> LaidText:
        size = max_size
        laid = self._layout(text, box.width(), size)
        while laid.total_height > box.height() and size > min_size:
            size -= 1
            laid = self._layout(text, box.width(), size)
        return laid

    def _layout(self, text: str, width: float, size: float) -> LaidText:
        lines: list[LaidLine] = []
        y = 0.0
        for paragraph_index, paragraph in enumerate(text.splitlines() or [""]):
            if paragraph_index:
                y += size * PARAGRAPH_GAP_FACTOR
            y = self._layout_paragraph(paragraph, width, size, y, lines)
        return LaidText(lines, size, y)

    def _layout_paragraph(self, paragraph: str, width: float, size: float, y: float, lines: list[LaidLine]) -> float:
        metrics = QFontMetricsF(self._font_factory(size, False))
        italic_metrics = QFontMetricsF(self._font_factory(size, True))
        line_height = size * LINE_HEIGHT_FACTOR
        current = LaidLine(top=y, baseline=y + metrics.ascent(), height=line_height)
        cursor = 0.0
        for item in tokenize_paragraph(paragraph):
            item_width = self._measure(item, size, metrics, italic_metrics)
            if cursor + item_width > width and current.items and not isinstance(item, SpaceItem):
                lines.append(current)
                y += line_height
                current = LaidLine(top=y, baseline=y + metrics.ascent(), height=line_height)
                cursor = 0.0
            if isinstance(item, SpaceItem) and cursor == 0.0:
                continue
            current.items.append(PlacedItem(item, cursor, item_width))
            cursor += item_width
        lines.append(current)
        return y + line_height

    @staticmethod
    def _measure(item: InlineItem, size: float, metrics: QFontMetricsF, italic_metrics: QFontMetricsF) -> float:
        if isinstance(item, SymbolItem):
            return size * (SYMBOL_SIZE_FACTOR + SYMBOL_GAP_FACTOR)
        if isinstance(item, SpaceItem):
            return metrics.horizontalAdvance(" ")
        return (italic_metrics if item.italic else metrics).horizontalAdvance(item.text)


def laid_line_width(line: LaidLine) -> float:
    if not line.items:
        return 0.0
    last = line.items[-1]
    return last.x + last.width


def symbol_side(size: float) -> float:
    return size * SYMBOL_SIZE_FACTOR


def font_factory_for(assets, logical_name: str):
    def factory(size: float, italic: bool) -> QFont:
        return assets.font(logical_name, size, italic)
    return factory
