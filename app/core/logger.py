import logging
import json
from datetime import date, datetime
from pathlib import Path

from app.core.config import settings


class DailyFileHandler(logging.FileHandler):
    """FileHandler que cambia de archivo cuando cambia el día."""

    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir
        self.current_date = datetime.now().date()
        super().__init__(self._path(self.current_date), encoding="utf-8")

    @staticmethod
    def _filename(day: date) -> str:
        return f"{day:%Y_%m_%d}_harness.log"

    def _path(self, day: date) -> str:
        return str((self.logs_dir / self._filename(day)).resolve())

    def emit(self, record):
        today = datetime.now().date()
        with self.lock:
            if today != self.current_date:
                self.close()
                self.current_date = today
                self.baseFilename = self._path(today)
                self.stream = self._open()
            super().emit(record)


logger = logging.getLogger("agent_harness")
logger.setLevel(settings.LOG_LEVEL)
logger.propagate = False  # 🔥 Evita que se propague al root logger (y a stderr)

# 1. File handler (always saves everything)
log_file = settings.log_file  # 🔥 Ruta diaria centralizada

file_handler = DailyFileHandler(settings.logs_dir)
file_handler.setFormatter(logging.Formatter(
    '[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
logger.addHandler(file_handler)

# 2. Memory handler for the Debug Panel


class DebugEventCollector(logging.Handler):
    def __init__(self):
        super().__init__()
        self.events = []
        self.agent_flow = []  # 🔥 Nueva lista para el flujo de agentes

    def emit(self, record):
        # 🔥 Detectar eventos especiales de A2A
        if record.name == "agent_flow":
            self.agent_flow.append({
                "timestamp": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "agent": getattr(record, "agent_name", "unknown"),
                "action": getattr(record, "action", "unknown"),
            })
            if len(self.agent_flow) > 50:
                self.agent_flow.pop(0)
            return

        if record.levelno >= logging.DEBUG:
            msg = record.getMessage()
            payload = msg
            summary = msg

            # Try to extract the model if it's a JSON request
            try:
                if msg.strip().startswith("{"):
                    parsed = json.loads(msg)
                    if parsed.get("hook") == "handler":
                        summary = (
                            f"🪝 {parsed.get('event', '?')} · "
                            f"{parsed.get('type', '?')} · "
                            f"{parsed.get('status', '?')} · "
                            f"{parsed.get('duration_ms', '?')}ms"
                        )
                        if parsed.get("matcher"):
                            summary += f" · [{parsed['matcher']}]"
                    elif parsed.get("hook") == "emit":
                        summary = (
                            f"🪝 emit · {parsed.get('event', '?')} · "
                            f"{parsed.get('handlers', '?')} handlers · "
                            f"{parsed.get('duration_ms', '?')}ms"
                        )
                        if parsed.get("parallel"):
                            summary += " · parallel"
                    elif "model" in parsed and "messages" in parsed:
                        # 🔥 Extraemos el último mensaje del usuario
                        user_msg = ""
                        for m in reversed(parsed["messages"]):
                            if m["role"] == "user":
                                content = m.get("content", "")
                                if isinstance(content, list):
                                    # Multimodal: buscamos el texto
                                    for c in content:
                                        if c.get("type") == "text":
                                            user_msg = c.get("text", "")
                                            break
                                else:
                                    user_msg = content
                                break

                        summary = f"LLM Request ({parsed['model']}): {user_msg[:60]}..."
                    else:
                        summary = "JSON Payload"
                    payload = json.dumps(parsed, indent=2, ensure_ascii=False)
            except Exception:
                pass

            event = {
                "timestamp": datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                "type": record.levelname,
                "summary": summary,
                "payload": payload
            }
            self.events.append(event)
            if len(self.events) > 50:
                self.events.pop(0)


# Global collector instance
debug_collector = DebugEventCollector()
logger.addHandler(debug_collector)


# # Handler para stdout (útil para scripts)
# stream_handler = logging.StreamHandler()
# stream_handler.setFormatter(logging.Formatter(
#     '[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
# logger.addHandler(stream_handler)


def get_debug_events():
    """Returns the list of captured debug events."""
    return debug_collector.events


def log_agent_flow(agent_name: str, action: str):
    """Emite un evento de flujo de agente al collector para el diagrama."""
    record = logging.LogRecord(
        name="agent_flow",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg=f"{agent_name}:{action}",
        args=(),
        exc_info=None,
    )
    record.agent_name = agent_name
    record.action = action
    debug_collector.emit(record)


def get_agent_flow():
    """Devuelve el flujo de agentes para el panel de debug."""
    return debug_collector.agent_flow
