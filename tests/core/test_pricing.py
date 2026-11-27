import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from datetime import datetime, timedelta

from app.core.pricing.base import PricingProvider, PricingSource
from app.core.pricing.sources.fake_source import FakePricingSource
from app.core.pricing.sources.json_source import JSONPricingSource
from app.core.pricing.sources.api_source import APIPricingSource
from app.core.pricing.registry import (
    get_pricing, _build_source, _expand_env_vars, ensure_prices_loaded,
)


class TestFakePricingSource:
    @pytest.mark.asyncio
    async def test_fake_source_returns_empty(self):
        source = FakePricingSource()
        assert await source.get_prices() == {}


class TestJSONPricingSource:
    @pytest.mark.asyncio
    async def test_json_source_reads_valid_file(self, tmp_path):
        file = tmp_path / "pricing.json"
        file.write_text('{"gpt-4o": {"input": 2.5e-6, "output": 1e-5}}')
        source = JSONPricingSource(file)
        prices = await source.get_prices()
        assert "gpt-4o" in prices
        assert prices["gpt-4o"]["input"] == 2.5e-6

    @pytest.mark.asyncio
    async def test_json_source_handles_missing_file(self, tmp_path):
        source = JSONPricingSource(tmp_path / "no_existe.json")
        assert await source.get_prices() == {}

    @pytest.mark.asyncio
    async def test_json_source_handles_corrupt_file(self, tmp_path):
        file = tmp_path / "corrupt.json"
        file.write_text("no es json")
        source = JSONPricingSource(file)
        assert await source.get_prices() == {}


class TestAPIPricingSource:
    @pytest.mark.asyncio
    async def test_api_source_fetches_and_caches(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        with patch("app.core.pricing.sources.api_source.settings") as mock_settings:
            mock_settings.pricing_cache_file = cache_file
            mock_settings.PRICING_CACHE_TTL_DAYS = 1

            source = APIPricingSource(
                url="https://example.com/api",
                model_field="id",
                input_field="pricing.prompt",
                output_field="pricing.completion",
            )

            with patch("httpx.AsyncClient.get") as mock_get:
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "data": [
                        {"id": "model1", "pricing": {
                            "prompt": "0.000001", "completion": "0.000002"}},
                        {"id": "free_model"},  # Sin pricing
                        {"id": "bad_model", "pricing": {"prompt": {},
                                                        "completion": []}},  # 🔥 Datos inválidos
                    ]
                }
                mock_get.return_value = mock_response

                prices = await source.get_prices()

                assert "model1" in prices
                assert prices["model1"]["input"] == 0.000001
                assert "free_model" in prices
                assert prices["free_model"]["input"] == 0.0
                # Verificamos que el modelo con datos inválidos no explota
                assert "bad_model" in prices
                assert prices["bad_model"]["input"] == 0.0
                assert cache_file.exists()

    @pytest.mark.asyncio
    async def test_api_source_uses_cache(self, tmp_path):
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "prices": {"cached_model": {"input": 0.1, "output": 0.2}},
        }))

        with patch("app.core.pricing.sources.api_source.settings") as mock_settings:
            mock_settings.pricing_cache_file = cache_file
            mock_settings.PRICING_CACHE_TTL_DAYS = 1

            source = APIPricingSource(
                url="https://example.com/api",
                model_field="id",
                input_field="pricing.prompt",
                output_field="pricing.completion",
            )

            with patch("httpx.AsyncClient.get") as mock_get:
                prices = await source.get_prices()
                assert "cached_model" in prices
                mock_get.assert_not_called()  # No debe consultar la API


class TestPricingProvider:
    @pytest.mark.asyncio
    async def test_get_cost(self):
        class MockSource(PricingSource):
            async def get_prices(self):
                return {"model1": {"input": 2.5e-6, "output": 1e-5}}

        provider = PricingProvider(MockSource())
        cost = await provider.get_cost("model1", 1000, 500)
        assert cost == (1000 * 2.5e-6) + (500 * 1e-5)

    @pytest.mark.asyncio
    async def test_get_cost_unknown_model(self):
        class MockSource(PricingSource):
            async def get_prices(self):
                return {}

        provider = PricingProvider(MockSource())
        cost = await provider.get_cost("unknown", 1000, 500)
        assert cost == 0.0

    @pytest.mark.asyncio
    async def test_get_cost_pricing(self):
        class MockSource(PricingSource):
            async def get_prices(self):
                return {"model1": {"input": 2.5e-6, "output": 1e-5}}

        provider = PricingProvider(MockSource())
        result = await provider.get_cost_pricing("model1", 1000, 500)
        assert result == {
            "input_cost": 1000 * 2.5e-6,
            "output_cost": 500 * 1e-5,
        }

    @pytest.mark.asyncio
    async def test_get_cost_pricing_unknown_model(self):
        class MockSource(PricingSource):
            async def get_prices(self):
                return {}

        provider = PricingProvider(MockSource())
        result = await provider.get_cost_pricing("unknown", 1000, 500)
        assert result == {"input_cost": 0.0, "output_cost": 0.0}

    @pytest.mark.asyncio
    async def test_get_cost_pricing_missing_prices(self):
        class MockSource(PricingSource):
            async def get_prices(self):
                return {"free_model": {"input": None, "output": None}}

        provider = PricingProvider(MockSource())
        result = await provider.get_cost_pricing("free_model", 1000, 500)
        assert result == {"input_cost": 0.0, "output_cost": 0.0}


class TestRegistry:
    def test_expand_env_vars(self):
        with patch.dict("os.environ", {"TEST_VAR": "value"}):
            assert _expand_env_vars("${TEST_VAR}") == "value"
            assert _expand_env_vars("plain") == "plain"

    def test_build_source_api(self):
        config = {"source": "api",
                  "url": "https://example.com/api", "model_field": "id"}
        source = _build_source(config)
        assert isinstance(source, APIPricingSource)

    def test_build_source_json(self):
        config = {"source": "json", "json_file": "pricing.json"}
        source = _build_source(config)
        assert isinstance(source, JSONPricingSource)

    def test_build_source_fake(self):
        config = {"source": "fake"}
        source = _build_source(config)
        assert isinstance(source, FakePricingSource)

    def test_get_pricing_unknown_provider(self):
        provider = get_pricing("unknown_provider")
        assert isinstance(provider.source, FakePricingSource)


def test_expand_env_vars_non_string():
    """Cubre la línea 16: valor que no es string."""
    from app.core.pricing.registry import _expand_env_vars
    assert _expand_env_vars(42) == 42
    assert _expand_env_vars({"a": 1}) == {"a": 1}


def test_get_pricing_no_config_file(tmp_path):
    """Cubre las líneas 42-44: cuando no existe pricing_config.json."""
    from app.core.pricing.registry import get_pricing
    from app.core.pricing.sources.fake_source import FakePricingSource
    from unittest.mock import patch

    # 🔥 Solución: Parcheamos el método .exists() de Path para que devuelva False
    # cuando se pregunte por pricing_config.json
    original_exists = Path.exists

    def mock_exists(self):
        if self.name == "pricing_config.json":
            return False
        return original_exists(self)

    with patch("pathlib.Path.exists", mock_exists):
        provider = get_pricing("openrouter")
        assert isinstance(provider.source, FakePricingSource)


def test_ensure_prices_loaded(tmp_path, monkeypatch):
    """Cubre ensure_prices_loaded."""
    from app.core.pricing.registry import ensure_prices_loaded
    from unittest.mock import patch, AsyncMock

    monkeypatch.chdir(tmp_path)
    (tmp_path / "pricing_config.json").write_text(
        '{"providers": {"openrouter": {"source": "api", "url": "http://test"}}}')

    with patch("app.core.pricing.sources.api_source.APIPricingSource.get_prices", new_callable=AsyncMock) as mock_get:
        import asyncio
        asyncio.run(ensure_prices_loaded("openrouter"))
        mock_get.assert_called_once()


def test_get_pricing_falls_back_on_broken_config(tmp_path):
    """Un pricing_config.json corrupto degrada a FakePricingSource."""
    from app.core.pricing import registry as registry_module

    config_path = tmp_path / "pricing_config.json"
    config_path.write_text("{config rota", encoding="utf-8")

    with patch("app.core.config.Settings.pricing_config_path",
               new_callable=PropertyMock, return_value=config_path):
        provider = registry_module.get_pricing("openai")

    assert isinstance(provider.source, FakePricingSource)


@pytest.mark.asyncio
async def test_ensure_prices_loaded_skips_missing_and_unknown(tmp_path):
    """No se consulta la API si no hay config o el proveedor no está declarado."""
    config_path = tmp_path / "pricing_config.json"

    with patch("app.core.config.Settings.pricing_config_path",
               new_callable=PropertyMock, return_value=config_path), \
            patch("app.core.pricing.registry._build_source") as build:
        await ensure_prices_loaded("openai")
        config_path.write_text(json.dumps({"providers": {}}), encoding="utf-8")
        await ensure_prices_loaded("openai")

    build.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_prices_loaded_ignores_source_error(tmp_path):
    """Un fallo al descargar precios no impide arrancar la app."""
    config_path = tmp_path / "pricing_config.json"
    config_path.write_text(json.dumps({
        "providers": {"openai": {"source": "api", "url": "http://test"}}
    }), encoding="utf-8")

    with patch("app.core.config.Settings.pricing_config_path",
               new_callable=PropertyMock, return_value=config_path), \
            patch("app.core.pricing.registry._build_source") as build:
        build.return_value.get_prices = AsyncMock(
            side_effect=Exception("sin red"))
        await ensure_prices_loaded("openai")

    build.return_value.get_prices.assert_awaited_once()


class TestAPIPricingSourceErrors:
    @pytest.mark.asyncio
    async def test_corrupt_cache_and_models_without_id(self, tmp_path):
        """La caché rota se ignora y los modelos sin id se omiten."""
        cache_file = tmp_path / "cache.json"
        cache_file.write_text("{cache rota", encoding="utf-8")

        with patch("app.core.pricing.sources.api_source.settings") as mock_settings:
            mock_settings.pricing_cache_file = cache_file
            mock_settings.PRICING_CACHE_TTL_DAYS = 1
            source = APIPricingSource(
                url="https://example.com/api", model_field="id",
                input_field="pricing.prompt", output_field="pricing.completion",
            )

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                response = MagicMock()
                response.raise_for_status.return_value = None
                response.json.return_value = {"data": [
                    {"name": "modelo sin id"},
                    {"id": "modelo", "pricing": {
                        "prompt": "1", "completion": "2"}},
                ]}
                mock_get.return_value = response

                prices = await source.get_prices()

        assert prices == {"modelo": {"input": 1.0, "output": 2.0}}

    @pytest.mark.asyncio
    async def test_api_failure_returns_empty_prices(self, tmp_path):
        """Si la API falla, se devuelve un diccionario vacío y no se lanza."""
        with patch("app.core.pricing.sources.api_source.settings") as mock_settings:
            mock_settings.pricing_cache_file = tmp_path / "cache.json"
            mock_settings.PRICING_CACHE_TTL_DAYS = 1
            source = APIPricingSource(
                url="https://example.com/api", model_field="id",
                input_field="pricing.prompt", output_field="pricing.completion",
            )

            with patch("httpx.AsyncClient.get", new_callable=AsyncMock,
                       side_effect=Exception("sin red")):
                assert await source.get_prices() == {}
