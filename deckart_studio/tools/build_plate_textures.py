"""Build Full Art plate sheets from photographic CC0 materials (ambientCG).

Run: .venv\\Scripts\\python.exe -m deckart_studio.tools.build_plate_textures
"""
import json
import sys
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage

from deckart_studio.app_paths import project_root, resource_root
from deckart_studio.cardmaker.plate_geometry import CANVAS_HEIGHT, CANVAS_WIDTH

TEXTURES_ROOT = resource_root() / "assets" / "cardmaker" / "textures"
CACHE_ROOT = project_root() / "build" / "texture-src"
AMBIENTCG = "https://ambientcg.com/get?file={id}_1K-JPG.zip"
TEXTURE_SPECS = [
    ("stone", "Stone", "Marble001", 0.00, 1.62),
    ("alabaster", "Alabaster", "Marble004", 0.00, 1.55),
    ("granite", "Granite", "Rock023", 0.18, 1.20),
    ("parchment", "Parchment", "Paper006", 0.00, 1.45),
    ("plaster", "Plaster", "Plaster001", 0.00, 1.42),
    ("slate", "Slate", "Marble006", 0.22, 1.28),
    ("wood", "Wood", "Wood026", 0.14, 1.32),
    ("leather", "Leather", "Leather011", 0.18, 1.28),
    ("steel", "Steel", "Metal009", 0.08, 1.65),
]


def build() -> None:
    TEXTURES_ROOT.mkdir(parents=True, exist_ok=True)
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    remove_legacy_crops()
    catalog = [{"id": "smooth", "label": "Smooth", "sheet": None}]
    for texture_id, label, source_id, lift, contrast in TEXTURE_SPECS:
        source = load_color_map(source_id)
        sheet = prepare_sheet(source, lift, contrast)
        filename = f"{texture_id}.png"
        sheet.save(str(TEXTURES_ROOT / filename))
        catalog.append({"id": texture_id, "label": label, "sheet": filename})
        print("wrote", texture_id, sheet.size())
    (TEXTURES_ROOT / "textures.json").write_text(json.dumps({"textures": catalog}, indent=2), encoding="utf-8")
    print("catalog:", len(catalog), "textures")


def remove_legacy_crops() -> None:
    for path in TEXTURES_ROOT.glob("*-head.png"):
        path.unlink()
    for path in TEXTURES_ROOT.glob("*-body.png"):
        path.unlink()


def load_color_map(source_id: str) -> QImage:
    cached = next(CACHE_ROOT.glob(f"**/{source_id}*Color.jpg"), None)
    if cached is None:
        cached = next(CACHE_ROOT.glob(f"**/{source_id}_1K-JPG_Color.jpg"), None)
    if cached is not None and cached.is_file():
        image = QImage(str(cached))
        if not image.isNull():
            return image
    color_dir = CACHE_ROOT / "color"
    color_dir.mkdir(parents=True, exist_ok=True)
    zip_path = CACHE_ROOT / f"{source_id}.zip"
    if not zip_path.is_file() or zip_path.stat().st_size < 10000:
        download_zip(source_id, zip_path)
    extracted = extract_color_jpg(zip_path, color_dir)
    image = QImage(str(extracted))
    if image.isNull():
        raise RuntimeError(f"Could not read photographic texture {source_id}")
    return image


def download_zip(source_id: str, destination: Path) -> None:
    request = Request(AMBIENTCG.format(id=source_id), headers={"User-Agent": "DeckArtStudio/0.7.2"})
    with urlopen(request, timeout=120) as response:
        destination.write_bytes(response.read())


def extract_color_jpg(zip_path: Path, destination_folder: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if name.lower().endswith("_color.jpg"):
                target = destination_folder / Path(name).name
                target.write_bytes(archive.read(name))
                return target
    raise RuntimeError(f"No color map in {zip_path.name}")


def prepare_sheet(source: QImage, lift: float, contrast: float) -> QImage:
    fitted = cover_canvas(source)
    return adjust_readability(fitted, lift, contrast)


def cover_canvas(source: QImage) -> QImage:
    scale = max(CANVAS_WIDTH / source.width(), CANVAS_HEIGHT / source.height())
    width = max(CANVAS_WIDTH, int(source.width() * scale + 0.5))
    height = max(CANVAS_HEIGHT, int(source.height() * scale + 0.5))
    scaled = source.scaled(width, height, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
    left = max(0, (scaled.width() - CANVAS_WIDTH) // 2)
    top = max(0, (scaled.height() - CANVAS_HEIGHT) // 2)
    return scaled.copy(QRect(left, top, CANVAS_WIDTH, CANVAS_HEIGHT))


def adjust_readability(image: QImage, lift: float, contrast: float) -> QImage:
    source = image.convertToFormat(QImage.Format.Format_ARGB32)
    mean = mean_luminance(source)
    result = QImage(source.size(), QImage.Format.Format_ARGB32)
    for y in range(source.height()):
        for x in range(source.width()):
            color = source.pixelColor(x, y)
            result.setPixelColor(x, y, contrast_color(color, mean, lift, contrast))
    return result


def mean_luminance(image: QImage) -> float:
    total = 0.0
    count = image.width() * image.height()
    step = 4
    samples = 0
    for y in range(0, image.height(), step):
        for x in range(0, image.width(), step):
            total += luminance(image.pixelColor(x, y))
            samples += 1
    return total / max(1, samples)


def contrast_color(color: QColor, mean: float, lift: float, contrast: float) -> QColor:
    channels = []
    for value in (color.red(), color.green(), color.blue()):
        lifted = value + (255 - value) * lift
        pushed = mean + (lifted - mean) * contrast
        channels.append(max(0, min(255, int(pushed))))
    return QColor(*channels)


def luminance(color: QColor) -> float:
    return color.red() * 0.3 + color.green() * 0.59 + color.blue() * 0.11


if __name__ == "__main__":
    application = QGuiApplication(sys.argv)
    build()
