from app.core.config import settings
from app.core.harness.memory.base import MemoryEntry
from app.core.harness.memory.factory import create_memory_store
from rich.table import Table
from rich.panel import Panel
from rich.console import Console
import asyncio
import shutil
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

console = Console()

# ==========================================
# DATOS DE PRUEBA (Harta info)
# ==========================================
TEST_ENTRIES = [
    MemoryEntry(
        key="tech_stack",
        value="Python 3.11, uv, Textual, pytest, mcp, openai SDK. El proyecto usa una TUI moderna.",
        timestamp=datetime.now(),
        kind="fact"
    ),
    MemoryEntry(
        key="database",
        value="SQLite es la base de datos local. No requiere servidor. Usa FTS5 para búsqueda de texto completo.",
        timestamp=datetime.now(),
        kind="fact"
    ),
    MemoryEntry(
        key="user_preference",
        value="El usuario prefiere respuestas concisas y en español. No le gustan las explicaciones largas.",
        timestamp=datetime.now(),
        kind="preference"
    ),
    MemoryEntry(
        key="architecture",
        value="El proyecto sigue una arquitectura hexagonal con puertos y adaptadores. El AgentLoop es el núcleo.",
        timestamp=datetime.now(),
        kind="fact"
    ),
    MemoryEntry(
        key="mcp_servers",
        value="Servidores MCP configurados: filesystem, git, fetch y local_dev. Se cargan desde mcp_config.json.",
        timestamp=datetime.now(),
        kind="fact"
    ),
    MemoryEntry(
        key="debug_tips",
        value="Para depurar, usar /debug on en la TUI y revisar el panel lateral con F1. Los logs van a harness_debug.log.",
        timestamp=datetime.now(),
        kind="fact"
    ),
    MemoryEntry(
        key="streaming",
        value="El streaming se implementa en AgentLoop.stream() y se renderiza en la TUI con Markdown.update().",
        timestamp=datetime.now(),
        kind="fact"
    ),
    MemoryEntry(
        key="subagents",
        value="El agente principal puede delegar tareas a subagentes (DelegateTool) que tienen su propio contexto aislado.",
        timestamp=datetime.now(),
        kind="fact"
    ),
    MemoryEntry(
        key="permissions",
        value="El PermissionGate usa diff-first approval: muestra un diff antes de modificar archivos. Los permisos se guardan en .harness_permissions.json.",
        timestamp=datetime.now(),
        kind="fact"
    ),
    MemoryEntry(
        key="todo_list",
        value="Tareas pendientes: implementar SQLiteStore, añadir tests de memoria, actualizar documentación.",
        timestamp=datetime.now(),
        kind="fact"
    ),
]

# ==========================================
# FUNCIÓN DE PRUEBA
# ==========================================


async def test_backend(backend_name: str):
    console.print(
        f"\n[bold cyan]🔍 Probando backend: {backend_name.upper()}[/bold cyan]")

    # Limpiamos datos previos (si es files o sqlite)
    if backend_name == "files":
        shutil.rmtree(settings.memory_files_dir, ignore_errors=True)
    elif backend_name == "sqlite":
        settings.memory_db.unlink(missing_ok=True)

    # Creamos el store
    store = create_memory_store(backend_name)

    # 1. Guardar todas las entradas
    console.print(f"  [dim]Guardando {len(TEST_ENTRIES)} entradas...[/dim]")
    for entry in TEST_ENTRIES:
        await store.save(entry)

    # 2. Verificar el preámbulo
    preamble = store.preamble()
    console.print(f"  [dim]Preámbulo generado ({len(preamble)} chars).[/dim]")
    assert "Long-Term Memory" in preamble or "Short-Term Memory" in preamble, "Preámbulo vacío o incorrecto"

    # 3. Buscar por coincidencia exacta
    results = await store.recall("SQLite")
    console.print(
        f"  [dim]Búsqueda 'SQLite': {len(results)} resultados.[/dim]")
    assert len(results) > 0, "No se encontró 'SQLite'"
    assert any(
        "database" in r.key for r in results), "Resultado incorrecto para 'SQLite'"

    # 4. Buscar por coincidencia parcial (case-insensitive)
    results = await store.recall("python")
    console.print(
        f"  [dim]Búsqueda 'python': {len(results)} resultados.[/dim]")
    assert len(results) > 0, "No se encontró 'python'"

    # 5. Buscar por coincidencia en el valor (no en la key)
    results = await store.recall("servidor")
    console.print(
        f"  [dim]Búsqueda 'servidor': {len(results)} resultados.[/dim]")
    assert len(results) > 0, "No se encontró 'servidor'"

    # 6. Buscar algo que no existe
    results = await store.recall("inexistente_123")
    console.print(
        f"  [dim]Búsqueda 'inexistente': {len(results)} resultados.[/dim]")
    assert len(results) == 0, "Se encontró algo que no debería existir"

    # 7. Verificar que el preámbulo tiene contenido útil
    preamble = store.preamble(limit=3)
    console.print(
        f"  [dim]Preámbulo con límite 3 ({len(preamble)} chars).[/dim]")
    assert len(preamble) > 0, "Preámbulo vacío"

    # 8. Limpiar y verificar que todo se borró
    await store.clear()
    results = await store.recall("SQLite")
    console.print(
        f"  [dim]Después de clear, búsqueda 'SQLite': {len(results)} resultados.[/dim]")
    assert len(results) == 0, "La memoria no se limpió correctamente"

    console.print(
        f"  [bold green]✅ {backend_name.upper()} pasó todas las pruebas.[/bold green]")


async def test_migration():
    """Prueba migrar de un backend a otro."""
    console.print(
        f"\n[bold cyan]🔄 Probando migración entre backends[/bold cyan]")

    shutil.rmtree(settings.memory_files_dir, ignore_errors=True)
    settings.memory_db.unlink(missing_ok=True)

    # 1. Guardamos en archivos
    source = create_memory_store("files")
    for entry in TEST_ENTRIES:
        await source.save(entry)

    # 2. Obtenemos TODAS las entradas (sin límite)
    entries = await source.get_all()
    console.print(f"  [dim]Entradas a migrar: {len(entries)}[/dim]")
    assert len(entries) == len(
        TEST_ENTRIES), f"Se esperaban {len(TEST_ENTRIES)} entradas, se obtuvieron {len(entries)}"

    # 3. Migramos a SQLite
    target = create_memory_store("sqlite")
    for entry in entries:
        await target.save(entry)

    # 4. Verificamos que en SQLite están los datos
    results = await target.recall("SQLite")
    console.print(
        f"  [dim]Después de migrar, búsqueda 'SQLite' en SQLite: {len(results)} resultados.[/dim]")
    assert len(results) > 0, "La migración no copió los datos"

    # 5. Verificamos que el total de entradas coincide
    all_entries = await target.get_all()
    console.print(
        f"  [dim]Total de entradas en SQLite: {len(all_entries)}[/dim]")
    assert len(all_entries) == len(
        TEST_ENTRIES), "No se migraron todas las entradas"

    console.print(
        f"  [bold green]✅ Migración files -> sqlite pasó.[/bold green]")


async def main():
    console.print(Panel.fit(
        "[bold]Test de Backends de Memoria[/bold]\n"
        "Ejercicio 3: Backend de memoria intercambiable",
        border_style="cyan"
    ))

    # Tabla de resumen
    table = Table(title="Resumen de Pruebas")
    table.add_column("Prueba", style="cyan")
    table.add_column("Estado", style="green")

    # Ejecutamos las pruebas
    for backend in ["files", "sqlite", "memory"]:
        try:
            await test_backend(backend)
            table.add_row(f"Backend: {backend}", "✅ PASÓ")
        except Exception as e:
            table.add_row(f"Backend: {backend}", f"❌ FALLÓ: {e}")

    try:
        await test_migration()
        table.add_row("Migración files -> sqlite", "✅ PASÓ")
    except Exception as e:
        table.add_row("Migración files -> sqlite", f"❌ FALLÓ: {e}")

    console.print(table)
    console.print(
        "\n[bold green]🏁 Todas las pruebas completadas.[/bold green]")


if __name__ == "__main__":
    asyncio.run(main())
