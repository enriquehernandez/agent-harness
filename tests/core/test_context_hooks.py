"""Ciclo de vida del contexto adicional aportado por los hooks."""

from app.core.harness.context import ContextManager


def _hook_contexts(ctx):
    return [msg["content"] for msg in ctx.messages
            if "CONTEXTO ADICIONAL DE HOOK" in str(msg.get("content", ""))]


def test_append_hook_context_creates_one_temporary_user_message():
    ctx = ContextManager()

    ctx.append_hook_context("usa python")

    assert len(ctx.messages) == 1
    assert ctx.messages[0]["role"] == "user"
    assert _hook_contexts(ctx) == [
        "[SISTEMA - CONTEXTO ADICIONAL DE HOOK]: usa python"]


def test_append_hook_context_concatenates_into_same_message():
    ctx = ContextManager()

    ctx.append_hook_context("contexto uno")
    ctx.append_hook_context("contexto dos")

    assert len(_hook_contexts(ctx)) == 1
    assert "contexto uno\ncontexto dos" in _hook_contexts(ctx)[0]


def test_append_hook_context_ignores_empty_input():
    ctx = ContextManager()

    ctx.append_hook_context("")

    assert ctx.messages == []


def test_remove_hook_context_deletes_temporary_message():
    ctx = ContextManager()
    ctx.add_user("mensaje real")
    ctx.append_hook_context("usa python")

    ctx.remove_hook_context()

    assert _hook_contexts(ctx) == []
    assert [msg["content"] for msg in ctx.messages] == ["mensaje real"]


def test_remove_hook_context_without_temporary_message_is_noop():
    ctx = ContextManager()

    ctx.remove_hook_context()

    assert ctx.messages == []


def test_remove_hook_context_after_compaction_is_noop():
    ctx = ContextManager()
    ctx.append_hook_context("usa python")
    ctx.messages.clear()

    ctx.remove_hook_context()

    assert ctx.messages == []
