import json
import httpx
from datetime import datetime, timedelta
from app.core.pricing.base import PricingSource
from app.core.config import settings
from app.core.logger import logger


class APIPricingSource(PricingSource):
    """Consulta la API del proveedor con caché en disco y TTL configurable."""

    def __init__(self, url: str, model_field: str, input_field: str, output_field: str):
        self.url = url
        self.model_field = model_field
        self.input_field = input_field
        self.output_field = output_field
        self.cache_file = settings.pricing_cache_file
        self.ttl_days = settings.PRICING_CACHE_TTL_DAYS

    def _get_nested(self, data: dict, field: str):
        """Accede a un campo anidado con notación 'a.b.c'."""
        keys = field.split(".")
        value = data
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None
        return value

    async def get_prices(self) -> dict[str, dict]:
        # 1. Intentar cargar desde caché si es válido
        if self.cache_file.exists():
            try:
                data = json.loads(self.cache_file.read_text())
                timestamp = datetime.fromisoformat(data["timestamp"])
                if datetime.now() - timestamp < timedelta(days=self.ttl_days):
                    logger.debug(
                        f"Precios cargados desde caché ({len(data['prices'])} modelos)")
                    return data["prices"]
            except Exception:
                pass

        # 2. Consultar la API
        try:
            logger.info(f"Consultando precios en {self.url}...")
            async with httpx.AsyncClient() as client:
                resp = await client.get(self.url, timeout=10)
                resp.raise_for_status()
                response_data = resp.json()

                models = response_data.get("data", response_data)

                prices = {}
                for m in models:
                    model_id = self._get_nested(m, self.model_field)
                    if not model_id:
                        continue

                    input_price = self._get_nested(m, self.input_field)
                    output_price = self._get_nested(m, self.output_field)

                    # 🔥 Protegemos contra datos inválidos (dicts, None, strings no numéricos)
                    try:
                        in_val = float(
                            input_price) if input_price is not None else 0.0
                    except (ValueError, TypeError):
                        in_val = 0.0

                    try:
                        out_val = float(
                            output_price) if output_price is not None else 0.0
                    except (ValueError, TypeError):
                        out_val = 0.0

                    prices[model_id] = {"input": in_val, "output": out_val}

                # Guardar en caché
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                self.cache_file.write_text(json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "prices": prices,
                }, indent=2))
                logger.info(f"Precios actualizados ({len(prices)} modelos)")
                return prices

        except Exception as e:
            logger.warning(f"Error consultando API de precios: {e}")
            return {}
