import json
import logging
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import app.core.logger as logger_module
from app.core.config import settings
from app.core.logger import DebugEventCollector


def test_log_file_uses_todays_date():
    """El archivo de log se llama aaaammdd_harness.log."""
    expected = settings.logs_dir / f"{datetime.now():%Y_%m_%d}_harness.log"

    assert settings.log_file == expected
    assert Path(logger_module.file_handler.baseFilename).name == expected.name


def test_daily_file_handler_rotates_at_midnight(tmp_path):
    """El handler abre el archivo del día nuevo sin perder el anterior."""
    with patch.object(logger_module, "datetime") as clock:
        clock.now.return_value.date.return_value = date(2026, 11, 25)
        handler = logger_module.DailyFileHandler(tmp_path)
        first = Path(handler.baseFilename)

        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="primero", args=(), exc_info=None)
        handler.emit(record)

        clock.now.return_value.date.return_value = date(2026, 11, 26)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="segundo", args=(), exc_info=None)
        handler.emit(record)
        handler.close()

    assert first.name == "2026_11_25_harness.log"
    assert Path(handler.baseFilename).name == "2026_11_26_harness.log"
    assert first.read_text(encoding="utf-8").endswith("primero\n")
    assert Path(handler.baseFilename).read_text(encoding="utf-8").endswith(
        "segundo\n")


def test_debug_event_collector():
    collector = DebugEventCollector()
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="", lineno=0,
        msg='{"model": "test-model", "messages": []}', args=(), exc_info=None
    )

    collector.emit(record)
    assert len(collector.events) == 1
    # 🔥 Ahora el summary incluye "..." al final
    assert collector.events[0]["summary"].startswith(
        "LLM Request (test-model)")


def test_debug_event_collector_limit():
    collector = DebugEventCollector()
    for i in range(55):
        record = logging.LogRecord(
            name="test", level=logging.DEBUG, pathname="", lineno=0,
            msg=f"Message {i}", args=(), exc_info=None
        )
        collector.emit(record)

    # Solo debe mantener los últimos 50
    assert len(collector.events) == 50
    assert collector.events[-1]["summary"] == "Message 54"


def test_debug_event_collector_json_error():
    """Cubre el except de JSON parsing (línea 36, 38)."""
    collector = DebugEventCollector()
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="", lineno=0,
        msg="{malformed json", args=(), exc_info=None
    )
    collector.emit(record)
    assert len(collector.events) == 1
    # Debe caer al fallback (no es JSON válido)
    assert collector.events[0]["summary"] == "{malformed json"


def test_debug_event_collector_json_no_model():
    """Cubre la línea 36: JSON válido sin modelo."""
    import logging
    from app.core.logger import DebugEventCollector
    collector = DebugEventCollector()
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="", lineno=0,
        msg='{"other_key": "value"}', args=(), exc_info=None
    )
    collector.emit(record)
    assert collector.events[0]["summary"] == "JSON Payload"


def test_debug_event_collector_multimodal():
    import logging
    from app.core.logger import DebugEventCollector
    collector = DebugEventCollector()

    msg = '{"model": "test", "messages": [{"role": "user", "content": [{"type": "text", "text": "Hola"}]}]}'
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="", lineno=0,
        msg=msg, args=(), exc_info=None
    )
    collector.emit(record)
    assert "Hola" in collector.events[0]["summary"]


def test_debug_event_collector_simple_content():
    import logging
    from app.core.logger import DebugEventCollector
    collector = DebugEventCollector()
    msg = '{"model": "test", "messages": [{"role": "user", "content": "Hola mundo"}]}'
    record = logging.LogRecord(name="test", level=logging.DEBUG,
                               pathname="", lineno=0, msg=msg, args=(), exc_info=None)
    collector.emit(record)
    assert "Hola mundo" in collector.events[0]["summary"]


def test_debug_event_collector_formats_hook_handler_log():
    """El resumen del panel identifica el evento, tipo, estado y matcher."""
    collector = DebugEventCollector()
    payload = {
        "hook": "handler",
        "event": "PreToolUse",
        "type": "prompt",
        "status": "denied",
        "duration_ms": 12.34,
        "matcher": "bash",
        "input": {"tool_name": "bash"},
        "output": {"denied": True},
    }
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg=json.dumps(payload), args=(), exc_info=None
    )

    collector.emit(record)

    event = collector.events[0]
    assert event["summary"] == (
        "🪝 PreToolUse · prompt · denied · 12.34ms · [bash]")
    assert '"tool_name": "bash"' in event["payload"]
    assert '"denied": true' in event["payload"]


def test_debug_event_collector_hook_handler_without_matcher():
    """Sin matcher el resumen no añade el sufijo."""
    collector = DebugEventCollector()
    payload = {
        "hook": "handler",
        "event": "UserPromptSubmit",
        "type": "agent",
        "status": "ok",
        "duration_ms": 10,
    }
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg=json.dumps(payload), args=(), exc_info=None
    )

    collector.emit(record)

    assert collector.events[0]["summary"] == (
        "🪝 UserPromptSubmit · agent · ok · 10ms")


def test_debug_event_collector_formats_hook_emit_log():
    """El evento global muestra paralelismo cuando se usó."""
    collector = DebugEventCollector()
    payload = {
        "hook": "emit",
        "event": "UserPromptSubmit",
        "handlers": 3,
        "duration_ms": 1500.0,
        "parallel": True,
        "output": {"denied": False},
    }
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg=json.dumps(payload), args=(), exc_info=None
    )

    collector.emit(record)

    assert collector.events[0]["summary"] == (
        "🪝 emit · UserPromptSubmit · 3 handlers · 1500.0ms · parallel")


def test_debug_event_collector_formats_serial_hook_emit_without_matcher():
    """Sin matcher ni paralelismo el resumen queda más corto."""
    collector = DebugEventCollector()
    payload = {
        "hook": "emit",
        "event": "Stop",
        "handlers": 1,
        "duration_ms": 0.5,
        "parallel": False,
    }
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg=json.dumps(payload), args=(), exc_info=None
    )

    collector.emit(record)

    assert collector.events[0]["summary"] == (
        "🪝 emit · Stop · 1 handlers · 0.5ms")


def test_log_agent_flow():
    """Cubre la función log_agent_flow y get_agent_flow."""
    from app.core.logger import log_agent_flow, get_agent_flow, debug_collector

    # Limpiamos el flujo previo
    debug_collector.agent_flow.clear()

    log_agent_flow("analyst", "start")
    log_agent_flow("analyst", "end")

    flow = get_agent_flow()
    assert len(flow) == 2
    assert flow[0]["agent"] == "analyst"
    assert flow[0]["action"] == "start"
    assert flow[1]["action"] == "end"


def test_log_agent_flow_max_limit():
    """Cubre el pop(0) cuando agent_flow supera los 50 eventos."""
    from app.core.logger import log_agent_flow, get_agent_flow, debug_collector

    debug_collector.agent_flow.clear()

    for i in range(55):
        log_agent_flow("test_agent", f"action_{i}")

    flow = get_agent_flow()
    assert len(flow) == 50  # Solo se guardan los últimos 50
    assert flow[0]["action"] == "action_5"  # Los primeros 5 fueron eliminados
