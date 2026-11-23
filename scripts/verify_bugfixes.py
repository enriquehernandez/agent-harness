# scripts/verify_bugfixes.py
"""
Verifica que los fixes de los bugs críticos están aplicados y no rompen nada.

Uso:
    uv run python scripts/verify_bugfixes.py
    uv run python scripts/verify_bugfixes.py --verbose

Exit code:
    0 → todos los checks pasan
    1 → al menos un check falla
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch


class CheckFailure(AssertionError):
    pass


class Checker:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []
        self.skipped: list[tuple[str, str]] = []

    def check(self, name: str):
        def decorator(func):
            async def wrapper():
                try:
                    if asyncio.iscoroutinefunction(func):
                        await func()
                    else:
                        func()
                    self.passed.append(name)
                    print(f"  ✅ {name}")
                except CheckFailure as e:
                    self.failed.append((name, str(e)))
                    print(f"  ❌ {name}: {e}")
                except Exception as e:
                    self.failed.append((name, f"{type(e).__name__}: {e}"))
                    print(f"  ❌ {name}: {type(e).__name__}: {e}")
                    if self.verbose:
                        import traceback
                        traceback.print_exc()
            return wrapper
        return decorator

    def summary(self) -> int:
        print("\n" + "=" * 70)
        print(f"📊 RESUMEN: {len(self.passed)} passed, "
              f"{len(self.failed)} failed, {len(self.skipped)} skipped")
        if self.failed:
            print("\n❌ FALLOS:")
            for name, err in self.failed:
                print(f"   - {name}: {err}")
            return 1
        print("\n✅ Todos los checks pasaron.")
        return 0


checker = Checker()


# ─────────────────────────────────────────────────────────────────────────────
# Bug 1
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 1: PricingProvider.get_cost_pricing con modelo desconocido")
async def check_pricing_unknown_model():
    from app.core.pricing.base import PricingProvider, PricingSource

    class EmptySource(PricingSource):
        async def get_prices(self):
            return {}

    provider = PricingProvider(EmptySource())
    result = await provider.get_cost_pricing("modelo_que_no_existe", 100, 50)

    if not isinstance(result, dict):
        raise CheckFailure(f"Esperaba dict, obtuve {type(result)}")
    if result.get("input_cost") != 0.0:
        raise CheckFailure(
            f"input_cost esperado 0.0, obtuve {result.get('input_cost')}")
    if result.get("output_cost") != 0.0:
        raise CheckFailure(
            f"output_cost esperado 0.0, obtuve {result.get('output_cost')}")


@checker.check("Bug 1: PricingProvider.get_cost con modelo conocido")
async def check_pricing_known_model():
    from app.core.pricing.base import PricingProvider, PricingSource

    class MockSource(PricingSource):
        async def get_prices(self):
            return {"m1": {"input": 2.5e-6, "output": 1e-5}}

    provider = PricingProvider(MockSource())
    cost = await provider.get_cost("m1", 1000, 500)
    expected = (1000 * 2.5e-6) + (500 * 1e-5)
    if abs(cost - expected) > 1e-12:
        raise CheckFailure(f"cost esperado {expected}, obtuve {cost}")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 2
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 2: LoopResult tiene cost_usd")
def check_loopresult_cost():
    from app.core.harness.loop import LoopResult

    r = LoopResult(final_answer="x")
    if not hasattr(r, "cost_usd"):
        raise CheckFailure("LoopResult no tiene cost_usd")
    if r.cost_usd != 0.0:
        raise CheckFailure(
            f"cost_usd default esperado 0.0, obtuve {r.cost_usd}")


@checker.check("Bug 2: stream emite 'result' tras límite de reflexiones")
async def check_stream_result_on_reflection_limit():
    from app.core.harness.loop import AgentLoop
    from app.core.harness.tool import ToolRegistry
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.context import ContextManager
    from app.core.llm.base import BaseLLM, LLMResponse

    class StreamLLM(BaseLLM):
        async def chat(self, messages, tools=None, **kw):
            return LLMResponse(content="ok")

        async def stream_chat(self, messages, tools=None, **kw):
            yield "Respuesta"

        def count_tokens(self, text): return len(text) // 4
        @property
        def supports_tool_calling(self): return True
        @property
        def max_context_window(self): return 128000

    critic = MagicMock()

    async def reject_run(**kw):
        return MagicMock(success=True, content="REJECTED: no cumple")
    critic.run = reject_run

    loop = AgentLoop(
        llm=StreamLLM(),
        tools=ToolRegistry(),
        permissions=PermissionGate(policies={}),
        critic_tool=critic,
        agent_rules="reglas",
    )
    ctx = ContextManager()

    events = []
    async for ev in loop.stream("tarea", context=ctx):
        events.append(ev)

    result_events = [e for e in events if e.type == "result"]
    if not result_events:
        raise CheckFailure(
            f"No se emitió 'result' tras 2 rechazos. Eventos: {[e.type for e in events]}"
        )
    if "cost_usd" not in result_events[0].data:
        raise CheckFailure("El evento result no incluye cost_usd")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 3
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 3: tool_end incluye success y result (ToolResult)")
async def check_tool_end_payload():
    from app.core.harness.loop import AgentLoop
    from app.core.harness.tool import ToolRegistry, FunctionTool, ToolResult
    from app.core.harness.permissions import PermissionGate, Decision
    from app.core.harness.context import ContextManager
    from app.core.llm.base import BaseLLM, LLMResponse

    def ok_tool():
        return ToolResult(success=True, content="ok")

    registry = ToolRegistry()
    registry.register(FunctionTool(
        name="ok_tool", description="", parameters_schema={}, func=ok_tool
    ))

    class StreamLLM(BaseLLM):
        async def chat(self, messages, tools=None, **kw):
            return LLMResponse(content="done")

        async def stream_chat(self, messages, tools=None, **kw):
            yield {"type": "tool_call", "id": "c1", "name": "ok_tool", "arguments": {}}

        def count_tokens(self, text): return len(text) // 4
        @property
        def supports_tool_calling(self): return True
        @property
        def max_context_window(self): return 128000

    loop = AgentLoop(
        llm=StreamLLM(),
        tools=registry,
        permissions=PermissionGate(policies={"ok_tool": Decision.ALLOW}),
    )
    ctx = ContextManager()

    events = []
    async for ev in loop.stream("t", context=ctx):
        events.append(ev)

    tool_end = [e for e in events if e.type == "tool_end"]
    if not tool_end:
        raise CheckFailure("No se emitió tool_end")
    payload = tool_end[0].data
    if "success" not in payload or "result" not in payload:
        raise CheckFailure(f"tool_end sin success/result: {payload.keys()}")
    if not isinstance(payload["success"], bool):
        raise CheckFailure(
            f"success debe ser bool, es {type(payload['success'])}")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 4
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 4: stream captura excepciones genéricas (no solo Timeout)")
async def check_stream_generic_exception():
    from app.core.harness.loop import AgentLoop
    from app.core.harness.tool import ToolRegistry
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.context import ContextManager
    from app.core.llm.base import BaseLLM, LLMResponse

    class BrokenLLM(BaseLLM):
        async def chat(self, messages, tools=None, **kw):
            return LLMResponse(content="")

        async def stream_chat(self, messages, tools=None, **kw):
            raise ConnectionError("fallo de red simulado")
            yield  # noqa

        def count_tokens(self, text): return len(text) // 4
        @property
        def supports_tool_calling(self): return True
        @property
        def max_context_window(self): return 128000

    loop = AgentLoop(
        llm=BrokenLLM(),
        tools=ToolRegistry(),
        permissions=PermissionGate(policies={}),
    )
    ctx = ContextManager()

    events = []
    async for ev in loop.stream("t", context=ctx):
        events.append(ev)

    error_events = [e for e in events if e.type == "error"]
    if not error_events:
        raise CheckFailure(
            f"Excepción genérica no capturada. Eventos: {[e.type for e in events]}"
        )
    if error_events[0].data.get("is_timeout") is not False:
        raise CheckFailure(
            "is_timeout debe ser False para excepciones no-timeout")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 5
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 5: MCPClient.connect no hace doble retry (max 3 intentos)")
async def check_mcp_no_double_retry():
    from app.mcp.client import MCPClient

    client = MCPClient(command="dummy", args=[])
    attempts = {"count": 0}

    async def failing_do_connect():
        attempts["count"] += 1
        raise Exception("fallo simulado")

    with patch.object(client, "_do_connect", side_effect=failing_do_connect):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            try:
                await client.connect()
            except Exception:
                pass

    if attempts["count"] != 3:
        raise CheckFailure(
            f"Esperaba 3 intentos, hubo {attempts['count']} (doble retry no eliminado)"
        )


@checker.check("Bug 5: MCPClient.connect es idempotente si ya hay sesión")
async def check_mcp_connect_idempotent():
    from app.mcp.client import MCPClient

    client = MCPClient(command="dummy", args=[])
    client.session = MagicMock()

    called = {"count": 0}

    async def track_do_connect():
        called["count"] += 1

    with patch.object(client, "_do_connect", side_effect=track_do_connect):
        await client.connect()

    if called["count"] != 0:
        raise CheckFailure(
            f"_do_connect llamado {called['count']} veces con sesión existente"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Bug 6
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 6: MCPClient.register_tools prefija nombres con mcp_{server}_")
async def check_mcp_prefix():
    from app.mcp.client import MCPClient
    from app.core.harness.tool import ToolRegistry

    client = MCPClient(command="dummy", args=[])

    mock_tool = MagicMock()
    mock_tool.name = "read_file"
    mock_tool.description = "lee archivos"
    mock_tool.input_schema = {"type": "object", "properties": {}}

    mock_session = MagicMock()
    mock_session.list_tools = AsyncMock(
        return_value=MagicMock(tools=[mock_tool]))
    client.session = mock_session

    registry = ToolRegistry()
    await client.register_tools(registry, server_name="fs")

    if "read_file" in registry.names():
        raise CheckFailure(
            "read_file registrada sin prefijo (colisión de nombres)")
    if "mcp_fs_read_file" not in registry.names():
        raise CheckFailure(
            f"Esperaba 'mcp_fs_read_file', tengo: {registry.names()}"
        )

    tool = registry.get("mcp_fs_read_file")
    if tool.original_name != "read_file":
        raise CheckFailure(
            f"original_name esperado 'read_file', obtuve {tool.original_name}"
        )


@checker.check("Bug 6: MCPToolProxy.run usa original_name al llamar call_tool")
async def check_mcp_proxy_uses_original_name():
    from app.mcp.client import MCPClient, MCPToolProxy

    client = MCPClient(command="dummy", args=[])
    mock_result = MagicMock()
    mock_result.content = [MagicMock(type="text", text="ok")]
    mock_result.isError = False
    mock_result.is_error = False

    mock_session = MagicMock()
    mock_session.call_tool = AsyncMock(return_value=mock_result)
    client.session = mock_session

    proxy = MCPToolProxy(
        name="mcp_fs_read_file",
        original_name="read_file",
        description="",
        parameters_schema={},
        client=client,
        server_name="fs",
    )
    result = await proxy.run(path="x")
    if not result.success:
        raise CheckFailure(f"Tool falló: {result.error}")
    mock_session.call_tool.assert_called_once_with(
        "read_file", arguments={"path": "x"})


# ─────────────────────────────────────────────────────────────────────────────
# Bug 7
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 7: _generate_diff con oldText='' no inserta entre caracteres")
def check_diff_empty_oldtext():
    from app.core.harness.permissions import PermissionGate

    with TemporaryDirectory() as td:
        p = Path(td) / "x.txt"
        p.write_text("ABC")

        gate = PermissionGate()
        diff = gate._generate_diff({
            "path": str(p),
            "edits": [{"oldText": "", "newText": "ZZZ"}],
        })

        if diff is None:
            raise CheckFailure("Esperaba mensaje de error, obtuve None")
        if "oldText" not in diff and "vacío" not in diff:
            raise CheckFailure(
                f"Esperaba mensaje de oldText vacío, obtuve: {diff}")


@checker.check("Bug 7: _generate_diff con edit normal funciona")
def check_diff_normal_edit():
    from app.core.harness.permissions import PermissionGate

    with TemporaryDirectory() as td:
        p = Path(td) / "x.txt"
        p.write_text("Old content")

        gate = PermissionGate()
        diff = gate._generate_diff({
            "path": str(p),
            "edits": [{"oldText": "Old", "newText": "New"}],
        })

        if "-Old content" not in diff or "+New content" not in diff:
            raise CheckFailure(f"Diff inesperado: {diff}")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 8
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 8: ReadFileTool bloquea /base_evil (startswith bypass)")
async def check_filesystem_traversal():
    from app.tools.filesystem import ReadFileTool

    with TemporaryDirectory() as td:
        base = Path(td) / "base"
        base.mkdir()
        evil = Path(td) / "base_evil"
        evil.mkdir()
        (evil / "secret.txt").write_text("secret")

        tool = ReadFileTool(base_dir=str(base))
        result = await tool.run(path="../base_evil/secret.txt")

        if result.success:
            raise CheckFailure("Path traversal /base_evil no bloqueado")
        if "Access denied" not in result.error:
            raise CheckFailure(
                f"Esperaba 'Access denied', obtuve: {result.error}")


@checker.check("Bug 8: WriteFileTool bloquea /base_evil")
async def check_writefile_traversal():
    from app.tools.filesystem import WriteFileTool

    with TemporaryDirectory() as td:
        base = Path(td) / "base"
        base.mkdir()
        evil = Path(td) / "base_evil"
        evil.mkdir()

        tool = WriteFileTool(base_dir=str(base))
        result = await tool.run(path="../base_evil/pwn.txt", content="x")

        if result.success:
            raise CheckFailure("WriteFileTool permitió /base_evil")
        if (evil / "pwn.txt").exists():
            raise CheckFailure("Archivo escrito fuera del sandbox")


@checker.check("Bug 8: ReadDocumentTool bloquea path traversal")
async def check_document_traversal():
    from app.tools.documents import ReadDocumentTool

    with TemporaryDirectory() as td:
        base = Path(td) / "base"
        base.mkdir()
        evil = Path(td) / "base_evil"
        evil.mkdir()
        (evil / "secret.pdf").write_text("fake")

        tool = ReadDocumentTool(base_dir=str(base))
        result = await tool.run(path="../base_evil/secret.pdf")

        if result.success:
            raise CheckFailure("ReadDocumentTool permitió /base_evil")
        if "Access denied" not in result.error:
            raise CheckFailure(
                f"Esperaba 'Access denied', obtuve: {result.error}")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 9
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 9: main.main() llama run_tui() sin asyncio.run")
def check_main_no_asyncio_run():
    import inspect
    import app.main as main_mod

    src = inspect.getsource(main_mod.main)
    if "asyncio.run(run_tui())" in src:
        raise CheckFailure("main() sigue llamando asyncio.run(run_tui())")
    if "run_tui()" not in src:
        raise CheckFailure("main() no llama a run_tui()")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 10
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 10: /permissions con session_allowed como lista")
async def check_permissions_list():
    from app.tui.commands import handle_command
    from app.core.harness.context import ContextManager

    app = MagicMock()
    app.write_to_chat = AsyncMock()
    ctx = ContextManager(system_prompt="System")

    with TemporaryDirectory() as td:
        perm_file = Path(td) / "permissions.json"
        perm_file.write_text(json.dumps(
            {"session_allowed": ["bash:ls", "read_file:x"]}))

        with patch(
            "app.core.config.Settings.permissions_file",
            new_callable=PropertyMock,
            return_value=perm_file,
        ):
            ok = await handle_command("/permissions", ctx, {}, None, app)

    if not ok:
        raise CheckFailure("handle_command devolvió False")
    msg = app.write_to_chat.call_args[0][0]
    if "bash:ls" not in msg or "read_file:x" not in msg:
        raise CheckFailure(f"Lista no renderizada: {msg}")


@checker.check("Bug 10: /permissions con session_allowed como dict (legacy)")
async def check_permissions_dict_legacy():
    from app.tui.commands import handle_command
    from app.core.harness.context import ContextManager

    app = MagicMock()
    app.write_to_chat = AsyncMock()
    ctx = ContextManager(system_prompt="System")

    with TemporaryDirectory() as td:
        perm_file = Path(td) / "permissions.json"
        perm_file.write_text(json.dumps(
            {"session_allowed": {"bash:ls": "always"}}))

        with patch(
            "app.core.config.Settings.permissions_file",
            new_callable=PropertyMock,
            return_value=perm_file,
        ):
            ok = await handle_command("/permissions", ctx, {}, None, app)

    if not ok:
        raise CheckFailure("handle_command devolvió False")
    msg = app.write_to_chat.call_args[0][0]
    if "bash:ls" not in msg:
        raise CheckFailure(f"Dict legacy no renderizado: {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 11
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 11: /model no cambia el provider (solo el modelo)")
async def check_model_does_not_change_provider():
    from app.tui.commands import handle_command
    from app.core.harness.context import ContextManager

    app = MagicMock()
    app.write_to_chat = AsyncMock()
    app.update_dashboard = MagicMock()
    app.agent_loop = MagicMock()
    ctx = ContextManager(system_prompt="System")
    state = {"provider": "fake", "model": "old"}

    with patch("app.tui.commands.get_llm") as mock_get_llm:
        mock_get_llm.return_value = MagicMock()
        await handle_command("/model nuevo-modelo", ctx, state, None, app)

    if state["provider"] != "fake":
        raise CheckFailure(f"/model cambió el provider a {state['provider']}")
    if state.get("model") != "nuevo-modelo":
        raise CheckFailure(f"/model no guardó el modelo: {state.get('model')}")


@checker.check("Bug 11: /provider cambia el provider")
async def check_provider_changes_provider():
    from app.tui.commands import handle_command
    from app.core.harness.context import ContextManager

    app = MagicMock()
    app.write_to_chat = AsyncMock()
    app.update_dashboard = MagicMock()
    app.agent_loop = MagicMock()
    ctx = ContextManager(system_prompt="System")
    state = {"provider": "fake"}

    with patch("app.tui.commands.get_llm") as mock_get_llm:
        mock_get_llm.return_value = MagicMock()
        await handle_command("/provider openai", ctx, state, None, app)

    if state["provider"] != "openai":
        raise CheckFailure(f"/provider no cambió: {state['provider']}")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 13
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 13: prompt caching no muta el messages del caller")
async def check_prompt_caching_no_mutation():
    from app.core.llm.providers.openai_provider import OpenAICompatibleProvider

    with patch("app.core.llm.providers.openai_provider.AsyncOpenAI") as mock_openai:
        mock_client = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="ok", tool_calls=None))]
        mock_response.usage = None
        mock_client.chat.completions.create = AsyncMock(
            return_value=mock_response)

        provider = OpenAICompatibleProvider(api_key="k", model="m")
        messages = [{"role": "system", "content": "System prompt"}]
        original = json.dumps(messages)

        with patch("app.core.config.settings.ENABLE_PROMPT_CACHING", True):
            await provider.chat(messages)

        if json.dumps(messages) != original:
            raise CheckFailure(
                "messages fue mutado in-place por prompt caching")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 14
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 14: LLM_PROVIDER default es 'fake'")
def check_default_provider_is_fake():
    import inspect
    from app.core import config as config_mod

    src = inspect.getsource(config_mod.Settings)
    if 'LLM_PROVIDER: str = "fake"' not in src:
        raise CheckFailure(
            "LLM_PROVIDER default no es 'fake' (README vs config)")
    if 'LLM_PROVIDER: str = "openai"' in src:
        raise CheckFailure("LLM_PROVIDER sigue siendo 'openai' por defecto")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 15
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 15: SessionFilesStore.get_all conserva kind y timestamp")
async def check_session_files_kind_timestamp():
    from app.core.harness.memory.backends.session_files import SessionFilesStore
    from app.core.harness.memory.base import MemoryEntry

    with TemporaryDirectory() as td:
        store = SessionFilesStore(base_dir=Path(td))
        ts = datetime(2024, 1, 15, 10, 30, 0)
        await store.save(MemoryEntry(
            key="pref", value="usar logger", kind="preference", timestamp=ts
        ))

        entries = await store.get_all()
        if not entries:
            raise CheckFailure("get_all vacío")
        e = entries[0]
        if e.kind != "preference":
            raise CheckFailure(f"kind perdido: {e.kind}")
        if e.timestamp != ts:
            raise CheckFailure(f"timestamp perdido: {e.timestamp}")


@checker.check("Bug 15: SessionFilesStore.recall conserva kind y timestamp")
async def check_session_files_recall_kind_timestamp():
    from app.core.harness.memory.backends.session_files import SessionFilesStore
    from app.core.harness.memory.base import MemoryEntry

    with TemporaryDirectory() as td:
        store = SessionFilesStore(base_dir=Path(td))
        ts = datetime(2024, 1, 15, 10, 30, 0)
        await store.save(MemoryEntry(
            key="pref", value="usar logger siempre", kind="preference", timestamp=ts
        ))

        results = await store.recall("logger")
        if not results:
            raise CheckFailure("recall vacío")
        if results[0].kind != "preference":
            raise CheckFailure(f"kind perdido en recall: {results[0].kind}")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 16
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 16: SQLiteStore.save no duplica la misma key")
async def check_sqlite_upsert():
    from app.core.harness.memory.backends.sqlite import SQLiteStore
    from app.core.harness.memory.base import MemoryEntry

    with TemporaryDirectory() as td:
        store = SQLiteStore(db_path=str(Path(td) / "m.db"))
        ts = datetime.now()
        await store.save(MemoryEntry(key="k", value="v1", timestamp=ts))
        await store.save(MemoryEntry(key="k", value="v2", timestamp=ts))

        all_entries = await store.get_all()
        if len(all_entries) != 1:
            raise CheckFailure(
                f"Esperaba 1 entrada, hay {len(all_entries)} (duplicado)")
        if all_entries[0].value != "v2":
            raise CheckFailure(
                f"Esperaba 'v2', obtuve '{all_entries[0].value}'")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 17
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 17: SQLiteStore.recall escapa comillas (no rompe FTS5)")
async def check_sqlite_recall_escapes():
    from app.core.harness.memory.backends.sqlite import SQLiteStore
    from app.core.harness.memory.base import MemoryEntry

    with TemporaryDirectory() as td:
        store = SQLiteStore(db_path=str(Path(td) / "m.db"))
        await store.save(MemoryEntry(
            key="k", value='comando "especial" con comillas', timestamp=datetime.now()
        ))

        try:
            results = await store.recall('"especial"')
        except Exception as e:
            raise CheckFailure(f"recall lanzó {type(e).__name__}: {e}")

        if not results:
            raise CheckFailure("recall no encontró el resultado con comillas")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 18
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 18: VectorStore.save levanta RuntimeError si RETURNING no da fila")
async def check_vector_save_none_check():
    try:
        from app.core.harness.memory.backends.vector import VectorStore
    except ImportError:
        raise CheckFailure("VectorStore no importable (¿falta sqlite-vec?)")

    with TemporaryDirectory() as td:
        try:
            store = VectorStore(db_path=Path(td) / "v.db")
        except Exception as e:
            raise CheckFailure(f"No se pudo crear VectorStore: {e}")

        store._embed = lambda text: [0.0] * 384

        from app.core.harness.memory.base import MemoryEntry
        await store.save(MemoryEntry(key="k", value="v", timestamp=datetime.now()))

        real_conn = store.conn
        fake_conn = MagicMock()
        fake_conn.__enter__ = lambda self: self
        fake_conn.__exit__ = lambda *a: None

        def fake_execute(sql, params=()):
            if "RETURNING id" in sql:
                cur = MagicMock()
                cur.fetchone.return_value = None
                return cur
            return real_conn.execute(sql, params)

        fake_conn.execute = fake_execute
        store.conn = fake_conn

        try:
            await store.save(MemoryEntry(key="k2", value="v2", timestamp=datetime.now()))
        except RuntimeError:
            store.conn = real_conn
            return
        except Exception as e:
            store.conn = real_conn
            raise CheckFailure(
                f"Esperaba RuntimeError, obtuve {type(e).__name__}: {e}")
        store.conn = real_conn
        raise CheckFailure("save no levantó RuntimeError con RETURNING vacío")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 19
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 19: FunctionTool.run propaga ToolResult(success=False)")
async def check_functiontool_propagates_result():
    from app.core.harness.tool import FunctionTool, ToolResult

    def fail_func():
        return ToolResult(success=False, content="", error="fallo simulado")

    tool = FunctionTool(
        name="fail", description="", parameters_schema={}, func=fail_func
    )
    result = await tool.run()

    if result.success is not False:
        raise CheckFailure(f"Esperaba success=False, obtuve {result.success}")
    if result.error != "fallo simulado":
        raise CheckFailure(
            f"Esperaba error 'fallo simulado', obtuve {result.error}")


@checker.check("Bug 19: FunctionTool.run envuelve valor normal en ToolResult(success=True)")
async def check_functiontool_wraps_normal():
    from app.core.harness.tool import FunctionTool

    def ok_func():
        return 42

    tool = FunctionTool(
        name="ok", description="", parameters_schema={}, func=ok_func
    )
    result = await tool.run()

    if result.success is not True:
        raise CheckFailure(f"Esperaba success=True, obtuve {result.success}")
    if result.content != "42":
        raise CheckFailure(f"Esperaba '42', obtuve '{result.content}'")


# ─────────────────────────────────────────────────────────────────────────────
# Bug 20
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Bug 20: loop emite is_correction_marker en reflexión")
async def check_correction_marker():
    from app.core.harness.loop import AgentLoop
    from app.core.harness.tool import ToolRegistry
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.context import ContextManager
    from app.core.llm.base import BaseLLM, LLMResponse

    class StreamLLM(BaseLLM):
        async def chat(self, messages, tools=None, **kw):
            return LLMResponse(content="ok")

        async def stream_chat(self, messages, tools=None, **kw):
            yield "Respuesta"

        def count_tokens(self, text): return len(text) // 4
        @property
        def supports_tool_calling(self): return True
        @property
        def max_context_window(self): return 128000

    critic = MagicMock()

    async def reject_run(**kw):
        return MagicMock(success=True, content="REJECTED: no cumple")
    critic.run = reject_run

    loop = AgentLoop(
        llm=StreamLLM(),
        tools=ToolRegistry(),
        permissions=PermissionGate(policies={}),
        critic_tool=critic,
        agent_rules="reglas",
    )
    ctx = ContextManager()

    events = []
    async for ev in loop.stream("t", context=ctx):
        events.append(ev)

    correction_events = [
        e for e in events
        if e.type == "text_chunk" and e.data.get("is_correction_marker")
    ]
    if not correction_events:
        raise CheckFailure("No se emitió text_chunk con is_correction_marker")


# ─────────────────────────────────────────────────────────────────────────────
# Regresión
# ─────────────────────────────────────────────────────────────────────────────

@checker.check("Regresión: suite de tests unitarios (pytest) pasa")
def check_pytest_suite():
    import subprocess
    result = subprocess.run(
        ["uv", "run", "pytest", "tests/", "-q", "--no-header",
         "--ignore=tests/integration", "-x"],
        capture_output=True, text=True, timeout=300,
    )
    if result.returncode != 0:
        tail = "\n".join(result.stdout.splitlines()[-30:])
        raise CheckFailure(f"pytest falló (exit {result.returncode}):\n{tail}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

async def run_all_checks(verbose: bool):
    checker.verbose = verbose  # ✅ mutar el existente (no reasignar)

    print("🔍 Verificando fixes de bugs críticos...\n")

    checks = [
        check_pricing_unknown_model,
        check_pricing_known_model,
        check_loopresult_cost,
        check_stream_result_on_reflection_limit,
        check_tool_end_payload,
        check_stream_generic_exception,
        check_mcp_no_double_retry,
        check_mcp_connect_idempotent,
        check_mcp_prefix,
        check_mcp_proxy_uses_original_name,
        check_diff_empty_oldtext,
        check_diff_normal_edit,
        check_filesystem_traversal,
        check_writefile_traversal,
        check_document_traversal,
        check_main_no_asyncio_run,
        check_permissions_list,
        check_permissions_dict_legacy,
        check_model_does_not_change_provider,
        check_provider_changes_provider,
        check_prompt_caching_no_mutation,
        check_default_provider_is_fake,
        check_session_files_kind_timestamp,
        check_session_files_recall_kind_timestamp,
        check_sqlite_upsert,
        check_sqlite_recall_escapes,
        check_vector_save_none_check,
        check_functiontool_propagates_result,
        check_functiontool_wraps_normal,
        check_correction_marker,
        check_pytest_suite,
    ]

    for check in checks:
        await check()

    return checker.summary()


def main():
    parser = argparse.ArgumentParser(
        description="Verifica fixes de bugs críticos")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Muestra traceback completo en fallos")
    args = parser.parse_args()

    exit_code = asyncio.run(run_all_checks(args.verbose))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
