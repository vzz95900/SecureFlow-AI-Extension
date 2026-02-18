"""
SecureFlow AI — Extension Build Script.
Packages the Chrome extension into a ZIP for Chrome Web Store submission.

Usage:
    python scripts/build_extension.py
"""

import zipfile
import os
from pathlib import Path

# Paths
ROOT = Path(__file__).resolve().parent.parent
EXT_DIR = ROOT / "extension"
OUT_DIR = ROOT / "dist"
OUT_FILE = OUT_DIR / "secureflow-extension.zip"

# Files/dirs to exclude from the ZIP
EXCLUDE = {
    "__pycache__",
    ".DS_Store",
    "Thumbs.db",
    "*.map",
    ".git",
}


def should_include(path: Path) -> bool:
    """Filter out excluded files."""
    for part in path.parts:
        if part in EXCLUDE:
            return False
    return path.suffix not in {".map"}


def build():
    """Build the extension ZIP."""
    OUT_DIR.mkdir(exist_ok=True)

    with zipfile.ZipFile(OUT_FILE, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(EXT_DIR):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(EXT_DIR)

                if not should_include(rel_path):
                    continue

                zf.write(full_path, rel_path)
                print(f"  + {rel_path}")

    size_kb = OUT_FILE.stat().st_size / 1024
    print(f"\n✅ Extension packaged → {OUT_FILE}  ({size_kb:.1f} KB)")


if __name__ == "__main__":
    build()
