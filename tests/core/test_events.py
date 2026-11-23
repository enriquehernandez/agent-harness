from app.core.harness.events import AgentEvent


def test_agent_event_creation():
    """Verifica la creación de un AgentEvent."""
    event = AgentEvent(type="text_chunk", data={"text": "Hola"})
    assert event.type == "text_chunk"
    assert event.data["text"] == "Hola"
