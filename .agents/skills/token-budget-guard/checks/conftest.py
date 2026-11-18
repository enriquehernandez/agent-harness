import sys
from pathlib import Path

# Añadir el directorio scripts al path para que los tests puedan importar
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
