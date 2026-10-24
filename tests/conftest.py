import sys
from pathlib import Path

# Permite `from src import ...` al correr `pytest` desde la raíz del repo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
