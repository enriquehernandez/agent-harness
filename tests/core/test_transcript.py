import pytest
from app.core.harness.transcript import render_transcript


def test_render_transcript_txt():
    """Cubre la línea 16: formato de texto por defecto."""
    messages = [{"role": "user", "content": "Hola"}]
    result = render_transcript(messages, fmt="txt")
    assert "[user] Hola" in result


def test_render_transcript_json():
    messages = [{"role": "user", "content": "Hola"}]
    result = render_transcript(messages, fmt="json")
    assert '"role": "user"' in result


def test_render_transcript_markdown():
    messages = [{"role": "user", "content": "Hola"}]
    result = render_transcript(messages, fmt="markdown")
    assert "### User" in result
