import logging
from app.core.config import settings


def setup_logger():
    logger = logging.getLogger("agent_harness")
    logger.setLevel(settings.LOG_LEVEL)

    if not logger.handlers:
        # 🔥 En lugar de StreamHandler (que imprime en consola), usamos FileHandler
        # para no romper la TUI. O simplemente no añadimos handler si estamos en modo TUI.
        # Por ahora, lo dejamos en un archivo silencioso.
        handler = logging.FileHandler("harness_debug.log", encoding="utf-8")
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger()
