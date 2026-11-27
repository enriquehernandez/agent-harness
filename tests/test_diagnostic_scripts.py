"""Regresiones de los scripts de diagnóstico: never tocan datos reales."""

import json

import pytest
from unittest.mock import AsyncMock, patch

from app.core.config import settings
from scripts import check_pricing, verify_memory_backends


def _seed_cache(path, prices):
    sentinel = {
        "timestamp": "2000-01-01T00:00:00",
        "prices": prices,
    }
    path.write_text(json.dumps(sentinel), encoding="utf-8")
    return sentinel


def _write_pricing_config(path):
    path.write_text(json.dumps({"providers": {"openrouter": {
        "source": "api",
        "url": "https://example.test/prices",
        "model_field": "id",
        "input_field": "input",
        "output_field": "output",
    }}}), encoding="utf-8")


@pytest.mark.asyncio
async def test_verify_memory_uses_temp_dir_and_leaves_real_data_intact(
        tmp_path, monkeypatch):
    """El script no borra ni la DB ni los archivos de memoria reales."""
    real = tmp_path / "real_harness"
    (real / "memory").mkdir(parents=True)
    db = real / "memory.db"
    db.write_text("REAL_DB_SENTINEL", encoding="utf-8")
    marker = real / "memory" / "marker.md"
    marker.write_text("REAL_MEMORY_SENTINEL", encoding="utf-8")
    monkeypatch.setattr(settings, "DATA_DIR", real)

    code = await verify_memory_backends.main()

    assert code == 0
    assert db.read_text(encoding="utf-8") == "REAL_DB_SENTINEL"
    assert marker.read_text(encoding="utf-8") == "REAL_MEMORY_SENTINEL"
    assert settings.DATA_DIR == real


@pytest.mark.asyncio
async def test_verify_memory_returns_nonzero_when_a_backend_fails(
        tmp_path, monkeypatch):
    """Un backend que falla hace que el script termine con error."""
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(
        verify_memory_backends, "test_backend",
        AsyncMock(side_effect=AssertionError("backend roto")))
    monkeypatch.setattr(
        verify_memory_backends, "test_migration", AsyncMock())

    code = await verify_memory_backends.main()

    assert code == 1
    assert settings.DATA_DIR == tmp_path / "data"


def test_isolated_data_dir_restores_settings_on_error(tmp_path, monkeypatch):
    """El contexto devuelve DATA_DIR a su valor original aunque falle."""
    from scripts._isolated_data import isolated_data_dir

    original = tmp_path / "original"
    monkeypatch.setattr(settings, "DATA_DIR", original)

    with pytest.raises(RuntimeError, match="boom"):
        with isolated_data_dir() as data_dir:
            assert data_dir != original
            assert settings.DATA_DIR == data_dir
            raise RuntimeError("boom")

    assert settings.DATA_DIR == original


@pytest.mark.asyncio
async def test_check_pricing_leaves_real_cache_intact(tmp_path, monkeypatch):
    """El diagnóstico en directorio aislado no mueve la caché real."""
    real = tmp_path / "real_harness"
    real.mkdir()
    cache = real / "pricing_cache.json"
    sentinel = _seed_cache(cache, {
        "REAL": {"input": 9.0, "output": 9.0}})
    monkeypatch.setattr(settings, "DATA_DIR", real)

    config = tmp_path / "pricing_config.json"
    _write_pricing_config(config)
    monkeypatch.setattr(settings, "PRICING_CONFIG_FILE", str(config))

    prices = {"fake/model": {"input": 1.0, "output": 2.0}}
    with patch.object(check_pricing.APIPricingSource, "get_prices",
                      new_callable=AsyncMock, return_value=prices):
        code = await check_pricing.main()

    assert code == 0
    assert json.loads(cache.read_text(encoding="utf-8")) == sentinel
    assert not (real / "pricing_cache.json.bak").exists()
    assert settings.DATA_DIR == real


@pytest.mark.asyncio
async def test_check_pricing_restores_backup_when_download_raises(
        tmp_path, monkeypatch):
    """Si la descarga falla, se restaura el backup y se devuelve error."""
    data = tmp_path / "data"
    data.mkdir()
    cache = data / "pricing_cache.json"
    sentinel = _seed_cache(cache, {
        "KEEP": {"input": 3.0, "output": 4.0}})
    original_data_dir = settings.DATA_DIR

    config = tmp_path / "pricing_config.json"
    _write_pricing_config(config)
    monkeypatch.setattr(settings, "PRICING_CONFIG_FILE", str(config))

    with patch.object(check_pricing.APIPricingSource, "get_prices",
                      new_callable=AsyncMock,
                      side_effect=RuntimeError("red caída")):
        code = await check_pricing.main(data_dir=data)

    assert code == 1
    assert json.loads(cache.read_text(encoding="utf-8")) == sentinel
    assert not (data / "pricing_cache.json.bak").exists()
    assert settings.DATA_DIR == original_data_dir


@pytest.mark.asyncio
async def test_check_pricing_missing_config_returns_nonzero(tmp_path, monkeypatch):
    """Sin configuración de precios el script termina con error."""
    monkeypatch.setattr(
        settings, "PRICING_CONFIG_FILE", str(tmp_path / "missing.json"))

    assert await check_pricing.main() == 1
