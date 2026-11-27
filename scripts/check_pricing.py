import asyncio
import json
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.core.config import settings
from app.core.pricing import get_pricing
from app.core.pricing.sources.api_source import APIPricingSource
from scripts._isolated_data import isolated_data_dir

console = Console()


async def _diagnose() -> int:
    """Comprueba pricing usando solo rutas aisladas; devuelve código de salida."""
    console.print(Panel.fit(
        "[bold]Diagnóstico del Sistema de Pricing[/bold]\n"
        "Verifica que la API de OpenRouter devuelve los precios y que se cachean correctamente.",
        border_style="cyan"
    ))

    # 1. Verificar la configuración
    console.print("\n[bold]1. Configuración actual:[/bold]")
    console.print(
        f"  - `PRICING_CONFIG_FILE`: `{settings.PRICING_CONFIG_FILE}`")
    console.print(
        f"  - `PRICING_CACHE_TTL_DAYS`: `{settings.PRICING_CACHE_TTL_DAYS}`")
    console.print(
        f"  - Archivo de config existe: `{settings.pricing_config_path.exists()}`")
    console.print(f"  - Archivo de caché: `{settings.pricing_cache_file}`")
    console.print(
        f"  - Caché existe: `{settings.pricing_cache_file.exists()}`")

    # 2. Leer la configuración de openrouter
    console.print(
        "\n[bold]2. Configuración de OpenRouter en pricing_config.json:[/bold]")
    config_path = settings.pricing_config_path
    if not config_path.exists():
        console.print(
            "[red]❌ No existe pricing_config.json. No se puede continuar.[/red]")
        return 1

    config_data = json.loads(config_path.read_text())
    openrouter_conf = config_data.get("providers", {}).get("openrouter")
    if not openrouter_conf:
        console.print("[red]❌ No hay configuración para 'openrouter'.[/red]")
        return 1

    console.print(json.dumps(openrouter_conf, indent=2))

    # 3. Forzar la descarga (ignorando el caché por un momento)
    console.print("\n[bold]3. Consultando la API de OpenRouter...[/bold]")
    source = APIPricingSource(
        url=openrouter_conf["url"],
        model_field=openrouter_conf["model_field"],
        input_field=openrouter_conf["input_field"],
        output_field=openrouter_conf["output_field"],
    )

    # El caché vive en el directorio aislado: se aparta para forzar la descarga
    backup = None
    if settings.pricing_cache_file.exists():
        backup = settings.pricing_cache_file.with_suffix(".bak")
        settings.pricing_cache_file.rename(backup)
        console.print(f"  [dim]Caché movido a {backup}[/dim]")

    try:
        prices = await source.get_prices()
        if not prices:
            console.print("[red]❌ La API no devolvió precios.[/red]")
            return 1

        # 4. Mostrar resultados
        console.print(
            f"\n[bold green]✅ Precios descargados: {len(prices)} modelos.[/bold green]")

        # Tabla resumen
        table = Table(title="Muestra de precios (5 modelos)")
        table.add_column("Modelo", style="cyan")
        table.add_column("Input ($/token)", style="green")
        table.add_column("Output ($/token)", style="green")
        table.add_column("¿Es gratis?", style="yellow")

        for i, (model, data) in enumerate(list(prices.items())[:5]):
            is_free = data["input"] == 0.0 and data["output"] == 0.0
            table.add_row(
                model,
                f"{data['input']:.10f}",
                f"{data['output']:.10f}",
                "✅ Sí" if is_free else "❌ No"
            )
        console.print(table)

        # 5. Verificar modelos gratuitos
        console.print("\n[bold]4. Modelos gratuitos (input=0 y output=0):[/bold]")
        free_models = [m for m, d in prices.items() if d["input"] ==
                       0.0 and d["output"] == 0.0]
        console.print(
            f"  Total de modelos gratuitos: [bold]{len(free_models)}[/bold]")
        for m in free_models[:5]:
            console.print(f"  - `{m}`")
        if len(free_models) > 5:
            console.print(f"  [dim]... y {len(free_models) - 5} más[/dim]")

        # 6. Verificar que el caché se ha escrito
        console.print("\n[bold]5. Verificando el archivo de caché:[/bold]")
        if settings.pricing_cache_file.exists():
            cache_data = json.loads(settings.pricing_cache_file.read_text())
            cache_prices = cache_data.get("prices", {})
            console.print(
                f"  [green]✅ Caché escrito con {len(cache_prices)} modelos.[/green]")
            console.print(f"  - Timestamp: `{cache_data.get('timestamp')}`")

            # Verificar que los modelos gratuitos están en el caché
            free_in_cache = [m for m, d in cache_prices.items() if d.get(
                "input") == 0.0 and d.get("output") == 0.0]
            console.print(
                f"  - Modelos gratuitos en caché: `{len(free_in_cache)}`")
        else:
            console.print("[red]❌ El caché no se ha escrito.[/red]")

        # 7. Verificar el provider de pricing
        console.print("\n[bold]6. Verificando el PricingProvider:[/bold]")
        pricing = get_pricing("openrouter")
        console.print(f"  - Source type: `{type(pricing.source).__name__}`")

        cost = await pricing.get_cost("openai/gpt-4o", 1000, 500)
        console.print(
            f"  - Coste de 1000 input + 500 output en `openai/gpt-4o`: [bold]${cost:.6f}[/bold]")

        cost_free = await pricing.get_cost("nvidia/nemotron-3.5-super-vl:free", 1000, 500)
        console.print(
            f"  - Coste de 1000 input + 500 output en `nvidia/nemotron-3.5-super-vl:free`: [bold]${cost_free:.6f}[/bold]")

        console.print("\n[bold green]✅ Diagnóstico completado.[/bold green]")
        return 0
    except Exception as e:
        console.print(f"[red]❌ Error durante el diagnóstico: {e}[/red]")
        return 1
    finally:
        # Se restaure o no la descarga, el caché original vuelve a su sitio
        if backup is not None and backup.exists():
            settings.pricing_cache_file.unlink(missing_ok=True)
            backup.replace(settings.pricing_cache_file)
            console.print("\n[dim]Caché original restaurada.[/dim]")


async def main(data_dir: Path | None = None) -> int:
    """Aísla las rutas de datos y devuelve el código de salida del diagnóstico."""
    with isolated_data_dir(data_dir):
        return await _diagnose()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
