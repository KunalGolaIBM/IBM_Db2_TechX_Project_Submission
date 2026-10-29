from pathlib import Path

ROOT = Path(__file__).resolve().parent

with open(ROOT / "README.md", "r", encoding="utf-8") as f:
    README_TEXT = f.read()

print("Sharthi AI source package initialized.")
