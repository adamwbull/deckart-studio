from pathlib import Path
import sys

from deckart_studio.version import APP_NAME, APP_VERSION


def version_tuple(version: str) -> tuple[int, int, int, int]:
    parts = []
    for part in version.split("."):
        digits = "".join(character for character in part if character.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 4:
        parts.append(0)
    return parts[0], parts[1], parts[2], parts[3]


def version_info_text(version: str) -> str:
    filevers = version_tuple(version)
    joined = ",".join(str(part) for part in filevers)
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({joined}),
    prodvers=({joined}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'{APP_NAME}'),
        StringStruct(u'FileDescription', u'{APP_NAME}'),
        StringStruct(u'FileVersion', u'{version}'),
        StringStruct(u'InternalName', u'DeckArtStudio'),
        StringStruct(u'LegalCopyright', u'Copyright (c) {APP_NAME} contributors'),
        StringStruct(u'OriginalFilename', u'DeckArtStudio.exe'),
        StringStruct(u'ProductName', u'{APP_NAME}'),
        StringStruct(u'ProductVersion', u'{version}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""


def write_version_info(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(version_info_text(APP_VERSION), encoding="utf-8")
    return path


def main(argv: list[str]) -> int:
    destination = Path(argv[1]) if len(argv) > 1 else Path("packaging/file_version_info.txt")
    write_version_info(destination)
    print(f"version info written: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
