import json
import os
from pathlib import Path
from app.core.pricing.base import PricingProvider, PricingSource
from app.core.pricing.sources.api_source import APIPricingSource
from app.core.pricing.sources.json_source import JSONPricingSource
from app.core.pricing.sources.fake_source import FakePricingSource
from app.core.config import settings
from app.core.logger import logger


def _expand_env_vars(value: str) -> str:
    """Expande ${VAR} con variables de entorno."""
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def _build_source(config: dict) -> PricingSource:
    source_type = config.get("source", "fake")

    if source_type == "api":
        return APIPricingSource(
            url=_expand_env_vars(config["url"]),
            model_field=config.get("model_field", "id"),
            input_field=config.get("input_field", "pricing.prompt"),
            output_field=config.get("output_field", "pricing.completion"),
        )
    elif source_type == "json":
        return JSONPricingSource(Path(config.get("json_file", "pricing.json")))
    else:
        return FakePricingSource()


def get_pricing(provider_name: str) -> PricingProvider:
    """
    Carga pricing_config.json y devuelve el PricingProvider correspondiente.
    Si el proveedor no está configurado, devuelve Fake (coste 0).
    """
    config_path = settings.pricing_config_path

    if not config_path.exists():
        logger.warning(f"No existe {config_path}, usando FakePricing")
        return PricingProvider(source=FakePricingSource())

    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        providers = config_data.get("providers", {})
        provider_conf = providers.get(provider_name.lower())

        if not provider_conf:
            logger.warning(
                f"Proveedor '{provider_name}' no configurado en pricing_config.json")
            return PricingProvider(source=FakePricingSource())

        source = _build_source(provider_conf)
        return PricingProvider(source=source)

    except Exception as e:
        logger.error(f"Error cargando pricing_config.json: {e}")
        return PricingProvider(source=FakePricingSource())


async def ensure_prices_loaded(provider_name: str) -> None:
    """Fuerza la descarga de precios si no existe caché."""
    config_path = settings.pricing_config_path
    if not config_path.exists():
        return

    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        providers = config_data.get("providers", {})
        provider_conf = providers.get(provider_name.lower())

        if not provider_conf:
            return

        source = _build_source(provider_conf)
        await source.get_prices()
    except Exception as e:
        logger.warning(f"No se pudo cargar precios al arrancar: {e}")
