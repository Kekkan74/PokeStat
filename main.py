import os
import sys

# Asegurar que en Windows la terminal trabaje siempre en UTF-8 y no falle en cp1252
os.environ["PYTHONIOENCODING"] = "utf-8"

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pokestat.cli import app

if __name__ == "__main__":
    app()
