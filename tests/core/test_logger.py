import logging
import pytest
from app.core.logger import DebugEventCollector


def test_debug_event_collector():
    collector = DebugEventCollector()
    record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="", lineno=0,
        msg='{"model": "test-model", "messages": []}', args=(), exc_info=None
    )

    collector.emit(record)
    assert len(collector.events) == 1
    assert collector.events[0]["summary"] == "LLM Request (test-model)"
    assert "test-model" in collector.events[0]["payload"]


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
