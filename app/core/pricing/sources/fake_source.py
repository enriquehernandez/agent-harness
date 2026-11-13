from app.core.pricing.base import PricingSource


class FakePricingSource(PricingSource):
    """Sin coste (para tests)."""

    async def get_prices(self) -> dict[str, dict]:
        return {}
