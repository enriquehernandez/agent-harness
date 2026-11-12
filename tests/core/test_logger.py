import logging
from app.core.logger import DebugEventCollector


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
