import asyncio

# 🔥 IMPORTANTE: Importar textual_image ANTES de arrancar la app
try:
    import textual_image.renderable  # noqa: F401
except ImportError:
    pass  # Si no está instalado, la app funcionará sin imágenes

from app.tui.app import run_tui


def main():
    """Entry point. `run_tui` es síncrono (Textual gestiona su propio loop)."""
    run_tui()


if __name__ == "__main__":
    main()
