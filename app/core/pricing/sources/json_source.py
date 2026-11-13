import json
from pathlib import Path
from app.core.pricing.base import PricingSource
from app.core.logger import logger


class JSONPricingSource(PricingSource):
    """Lee precios desde un archivo JSON local (editado a mano por el usuario)."""

    def __init__(self, json_path: Path):
        self.json_path = json_path

    async def get_prices(self) -> dict[str, dict]:
        if not self.json_path.exists():
            logger.warning(
                f"No existe el archivo de precios: {self.json_path}")
            return {}
        try:
            return json.loads(self.json_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Error leyendo precios de {self.json_path}: {e}")
            return {}
