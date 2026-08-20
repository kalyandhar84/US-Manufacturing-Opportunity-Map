"""Build a zip for Azure App Service zip deploy (Oryx + Streamlit)."""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "app.zip"

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "dist",
    ".cursor",
}
SKIP_FILE_NAMES = {".env", ".env.local", "last_refresh.txt"}
SKIP_SUFFIXES = {".pyc", ".sqlite-wal", ".sqlite-shm"}


def should_skip(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if any(part in SKIP_DIR_NAMES for part in rel.parts):
        return True
    if "data" in rel.parts and "raw" in rel.parts:
        return True
    if path.name in SKIP_FILE_NAMES:
        return True
    if path.suffix in SKIP_SUFFIXES:
        return True
    if path.parent.name == "mail" and path.suffix == ".txt":
        return True
    return False


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in ROOT.rglob("*"):
            if not path.is_file() or should_skip(path):
                continue
            zf.write(path, path.relative_to(ROOT).as_posix())
            count += 1
    print(f"Wrote {count} files to {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
