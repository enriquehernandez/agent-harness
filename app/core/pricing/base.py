from abc import ABC, abstractmethod

from app.core.logger import logger


class PricingSource(ABC):
    """Fuente de precios (API, JSON o fake)."""

    @abstractmethod
    async def get_prices(self) -> dict[str, dict]:
        """Devuelve {modelo: {"input": float, "output": float}} en USD por token."""
        ...


class PricingProvider:
    """Calcula el coste usando una fuente de precios."""

    def __init__(self, source: PricingSource):
        self.source = source
        self._prices: dict[str, dict] | None = None

    async def _ensure_prices(self) -> dict[str, dict]:
        if self._prices is None:
            self._prices = await self.source.get_prices()
        return self._prices

    async def get_cost(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        prices = await self._ensure_prices()
        pricing = prices.get(model_name)
        if not pricing:
            logger.warning(
                f"Modelo '{model_name}' no encontrado en el catálogo de precios.")
            return 0.0

        input_price = pricing.get("input", 0.0) or 0.0
        output_price = pricing.get("output", 0.0) or 0.0
        return (prompt_tokens * input_price) + (completion_tokens * output_price)

    async def get_cost_pricing(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> dict:
        prices = await self._ensure_prices()
        pricing = prices.get(model_name)
        if not pricing:
            logger.warning(
                f"Modelo '{model_name}' no encontrado en el catálogo de precios.")
            return {"input_cost": 0.0, "output_cost": 0.0}

        input_price = pricing.get("input", 0.0) or 0.0
        output_price = pricing.get("output", 0.0) or 0.0
        return {
            "input_cost": prompt_tokens * input_price,
            "output_cost": completion_tokens * output_price,
        }
