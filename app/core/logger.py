import logging
import json
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger("agent_harness")
logger.setLevel(settings.LOG_LEVEL)

# 1. File handler (always saves everything)
file_handler = logging.FileHandler("harness_debug.log", encoding="utf-8")
file_handler.setFormatter(logging.Formatter(
    '[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%H:%M:%S'))
logger.addHandler(file_handler)

# 2. Memory handler for the Debug Panel


class DebugEventCollector(logging.Handler):
    def __init__(self):
        super().__init__()
        self.events = []

    def emit(self, record):
        if record.levelno >= logging.DEBUG:
            msg = record.getMessage()
            payload = msg
            summary = msg

            # Try to extract the model if it's a JSON request
            try:
                if msg.strip().startswith("{"):
                    parsed = json.loads(msg)
                    if "model" in parsed and "messages" in parsed:
                        summary = f"LLM Request ({parsed['model']})"
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


def get_debug_events():
    """Returns the list of captured debug events."""
    return debug_collector.events
