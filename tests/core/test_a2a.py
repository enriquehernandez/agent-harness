import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from app.core.harness.a2a.base import AgentCard
from app.core.harness.a2a.strategies.supervisor import SupervisorStrategy
from app.core.harness.a2a.strategies.sequential import SequentialStrategy
from app.core.harness.a2a.strategies.swarm import SwarmStrategy
from app.core.harness.a2a.orchestrator import OrchestratorTool
from app.core.harness.tool import ToolRegistry
from app.core.harness.context import ContextManager
from app.core.llm.base import LLMResponse


@pytest.fixture
def mock_registry():
    return {
        "analyst": AgentCard(
            name="analyst", description="Analiza código",
            system_prompt="Eres un analista", tools=ToolRegistry(), mode="isolated"
        ),
        "writer": AgentCard(
            name="writer", description="Escribe docs",
            system_prompt="Eres un escritor", tools=ToolRegistry(), mode="fork"
        )
    }


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.chat = AsyncMock(return_value=LLMResponse(content="analyst"))
    return llm


@pytest.mark.asyncio
async def test_supervisor_routes_to_correct_agent(mock_llm, mock_registry):
    """Verifica que el supervisor elige el agente correcto."""
    from app.core.harness.permissions import PermissionGate
    gate = PermissionGate(ask_user=None)  # 🔥 Gate vacío
    strategy = SupervisorStrategy(mock_llm, mock_registry, permissions=gate)

    with patch("app.core.harness.a2a.strategies.supervisor.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(
            return_value=MagicMock(final_answer="Análisis completado"))
        MockLoop.return_value = mock_instance

        result = await strategy.execute("Analiza este código")

        assert result.success is True
        assert "analyst" in result.content.lower()
        assert "Análisis completado" in result.content


@pytest.mark.asyncio
async def test_supervisor_unknown_agent(mock_llm, mock_registry):
    """Verifica el comportamiento cuando el LLM elige un agente inexistente."""
    mock_llm.chat.return_value = LLMResponse(content="ghost_agent")
    strategy = SupervisorStrategy(mock_llm, mock_registry, permissions=None)

    result = await strategy.execute("Tarea rara")

    assert result.success is False
    assert "ghost_agent" in result.error


@pytest.mark.asyncio
async def test_sequential_pipeline(mock_llm, mock_registry):
    """Verifica que el pipeline ejecuta los agentes en orden."""
    strategy = SequentialStrategy(
        mock_llm, mock_registry, permissions=None, sequence=["analyst", "writer"])

    with patch("app.core.harness.a2a.strategies.sequential.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(side_effect=[
            MagicMock(final_answer="Análisis del código"),
            MagicMock(final_answer="Documentación generada")
        ])
        MockLoop.return_value = mock_instance

        result = await strategy.execute("Analiza y documenta")

        assert result.success is True
        assert "Análisis del código" in result.content
        assert "Documentación generada" in result.content
        assert mock_instance.run.call_count == 2


@pytest.mark.asyncio
async def test_orchestrator_tool_supervisor_strategy(mock_llm, mock_registry):
    """Cubre el OrchestratorTool con estrategia supervisor."""
    with patch("app.core.config.settings.A2A_STRATEGY", "supervisor"):
        with patch("app.core.harness.a2a.orchestrator.SupervisorStrategy") as MockStrategy:
            mock_strategy = MagicMock()
            mock_strategy.execute = AsyncMock(
                return_value=MagicMock(success=True, content="ok"))
            MockStrategy.return_value = mock_strategy

            tool = OrchestratorTool(mock_llm, mock_registry, permissions=None)
            result = await tool.run("tarea")

            assert result.success is True


@pytest.mark.asyncio
async def test_orchestrator_passes_context_from_provider(mock_llm, mock_registry):
    """El orchestrator entrega el contexto actual a la estrategia."""
    ctx = ContextManager(system_prompt="Sistema")
    ctx.add_user("Mensaje del padre")

    with patch("app.core.config.settings.A2A_STRATEGY", "supervisor"):
        with patch("app.core.harness.a2a.orchestrator.SupervisorStrategy") as MockStrategy:
            mock_strategy = MagicMock()
            mock_strategy.execute = AsyncMock(
                return_value=MagicMock(success=True, content="ok"))
            MockStrategy.return_value = mock_strategy

            tool = OrchestratorTool(
                mock_llm, mock_registry, permissions=None,
                context_provider=lambda: ctx)
            await tool.run("tarea")

            mock_strategy.execute.assert_awaited_once_with("tarea", context=ctx)


@pytest.mark.asyncio
async def test_orchestrator_fork_agent_receives_parent_history(mock_llm, mock_registry):
    """Un agente en modo fork recibe el historial del contexto de la TUI."""
    ctx = ContextManager(system_prompt="Sistema")
    ctx.add_user("Contexto previo del padre")
    mock_llm.chat.return_value = LLMResponse(content="writer")

    with patch("app.core.config.settings.A2A_STRATEGY", "supervisor"):
        with patch("app.core.harness.a2a.strategies.supervisor.AgentLoop") as MockLoop:
            MockLoop.return_value.run = AsyncMock(
                return_value=MagicMock(final_answer="Hecho"))
            tool = OrchestratorTool(
                mock_llm, mock_registry, permissions=None,
                context_provider=lambda: ctx)
            await tool.run("tarea")

            agent_ctx = MockLoop.return_value.run.call_args.kwargs["context"]
            assert [m["content"] for m in agent_ctx.messages] == [
                "Eres un escritor",
                "Contexto previo del padre",
                "Continúas la tarea iniciada por el agente principal. "
                "El historial anterior es contexto heredado; tu tarea "
                "se indica en el siguiente mensaje.",
            ]


def test_fork_context_marks_inherited_history(mock_llm, mock_registry):
    """El fork distingue el historial heredado de la tarea que llega después."""
    strategy = SupervisorStrategy(mock_llm, mock_registry, permissions=None)
    ctx = ContextManager(system_prompt="Sistema")
    ctx.add_user("Contexto previo del padre")
    ctx.add_assistant("Respuesta previa")

    agent_ctx = strategy._fork_context(mock_registry["writer"], ctx)

    assert [m["role"] for m in agent_ctx.messages] == [
        "system", "user", "assistant", "user"
    ]
    assert agent_ctx.messages[0]["content"] == "Eres un escritor"
    assert agent_ctx.messages[-1]["content"] == (
        "Continúas la tarea iniciada por el agente principal. "
        "El historial anterior es contexto heredado; tu tarea "
        "se indica en el siguiente mensaje."
    )


def test_fork_context_without_history_has_no_preamble(mock_llm, mock_registry):
    """Sin historial heredado no se añade el preámbulo de continuación."""
    strategy = SupervisorStrategy(mock_llm, mock_registry, permissions=None)
    ctx = ContextManager(system_prompt="Sistema")

    agent_ctx = strategy._fork_context(mock_registry["writer"], ctx)

    assert agent_ctx.messages == [
        {"role": "system", "content": "Eres un escritor"}
    ]


def test_isolated_context_ignores_parent_history(mock_llm, mock_registry):
    """El modo isolated no hereda mensajes ni añade preámbulo."""
    strategy = SupervisorStrategy(mock_llm, mock_registry, permissions=None)
    ctx = ContextManager(system_prompt="Sistema")
    ctx.add_user("Contexto previo del padre")

    agent_ctx = strategy._fork_context(mock_registry["analyst"], ctx)

    assert agent_ctx.messages == [
        {"role": "system", "content": "Eres un analista"}
    ]


@pytest.mark.asyncio
async def test_orchestrator_unknown_strategy(mock_llm, mock_registry):
    """Cubre estrategia desconocida."""
    with patch("app.core.config.settings.A2A_STRATEGY", "inventada"):
        tool = OrchestratorTool(mock_llm, mock_registry, permissions=None)
        result = await tool.run("tarea")

        assert result.success is False
        assert "desconocida" in result.error


@pytest.mark.asyncio
async def test_supervisor_reads_persisted_permissions(tmp_path, monkeypatch, mock_llm, mock_registry):
    """Verifica que el subagente lee los permisos persistidos."""
    from app.core.harness.a2a.strategies.supervisor import SupervisorStrategy
    from app.core.harness.permissions import PermissionGate

    # 🔥 Cambiamos al directorio temporal y creamos el archivo en la ruta que espera settings
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness" / "permissions.json").write_text(
        '{"session_allowed": ["read_text_file:test.txt"]}')

    gate = PermissionGate(ask_user=None)
    strategy = SupervisorStrategy(mock_llm, mock_registry, permissions=gate)

    # Verificamos que el método _load_persisted_permissions lee el archivo
    persisted = strategy._load_persisted_permissions()
    assert "read_text_file:test.txt" in persisted


@pytest.mark.parametrize(
    "strategy_cls, kwargs",
    [
        (SupervisorStrategy, {}),
        (SequentialStrategy, {"sequence": ["analyst"]}),
        (SwarmStrategy, {}),
    ],
)
def test_strategies_without_permissions_file(
    tmp_path, monkeypatch, mock_llm, mock_registry, strategy_cls, kwargs
):
    """Sin .harness/permissions.json no hay permisos persistidos."""
    from app.core.harness.permissions import PermissionGate

    monkeypatch.chdir(tmp_path)  # no existe .harness/permissions.json
    gate = PermissionGate(ask_user=None)
    strategy = strategy_cls(mock_llm, mock_registry, permissions=gate, **kwargs)
    assert strategy._load_persisted_permissions() == set()


@pytest.mark.asyncio
async def test_supervisor_unknown_agent(mock_llm, mock_registry):
    """Cubre el caso de agente no encontrado."""
    from app.core.harness.permissions import PermissionGate
    mock_llm.chat.return_value = LLMResponse(content="ghost_agent")
    gate = PermissionGate(ask_user=None)
    strategy = SupervisorStrategy(mock_llm, mock_registry, permissions=gate)

    result = await strategy.execute("Tarea rara")
    assert result.success is False
    assert "ghost_agent" in result.error


@pytest.mark.asyncio
async def test_sequential_pipeline(mock_llm, mock_registry):
    """Cubre la estrategia sequential."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.sequential import SequentialStrategy

    gate = PermissionGate(ask_user=None)
    strategy = SequentialStrategy(
        mock_llm, mock_registry, permissions=gate, sequence=["analyst", "writer"])

    with patch("app.core.harness.a2a.strategies.sequential.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(side_effect=[
            MagicMock(final_answer="Análisis del código"),
            MagicMock(final_answer="Documentación generada")
        ])
        MockLoop.return_value = mock_instance

        result = await strategy.execute("Analiza y documenta")

        assert result.success is True
        assert "Análisis del código" in result.content
        assert "Documentación generada" in result.content
        assert mock_instance.run.call_count == 2


@pytest.mark.asyncio
async def test_orchestrator_unknown_strategy(mock_llm, mock_registry):
    """Cubre estrategia desconocida en el OrchestratorTool."""
    from app.core.harness.a2a.orchestrator import OrchestratorTool
    from unittest.mock import patch

    with patch("app.core.config.settings.A2A_STRATEGY", "inventada"):
        tool = OrchestratorTool(mock_llm, mock_registry, permissions=None)
        result = await tool.run("tarea")

        assert result.success is False
        assert "desconocida" in result.error


@pytest.mark.asyncio
async def test_orchestrator_exception(mock_llm, mock_registry):
    """Cubre el except del OrchestratorTool."""
    from app.core.harness.a2a.orchestrator import OrchestratorTool
    from unittest.mock import patch

    with patch("app.core.config.settings.A2A_STRATEGY", "supervisor"):
        with patch("app.core.harness.a2a.orchestrator.SupervisorStrategy") as MockStrategy:
            MockStrategy.side_effect = Exception("Fallo simulado")
            tool = OrchestratorTool(mock_llm, mock_registry, permissions=None)
            result = await tool.run("tarea")

            assert result.success is False
            assert "Fallo simulado" in result.error


@pytest.mark.asyncio
async def test_orchestrator_exception(mock_llm, mock_registry):
    """Cubre el except del OrchestratorTool."""
    from app.core.harness.a2a.orchestrator import OrchestratorTool
    from unittest.mock import patch

    with patch("app.core.config.settings.A2A_STRATEGY", "supervisor"):
        with patch("app.core.harness.a2a.orchestrator.SupervisorStrategy") as MockStrategy:
            MockStrategy.side_effect = Exception("Fallo simulado")
            tool = OrchestratorTool(mock_llm, mock_registry, permissions=None)
            result = await tool.run("tarea")

            assert result.success is False
            assert "Fallo simulado" in result.error


@pytest.mark.asyncio
async def test_sequential_agent_not_found(mock_llm, mock_registry):
    """Cubre el caso de agente no encontrado en sequential."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.sequential import SequentialStrategy

    gate = PermissionGate(ask_user=None)
    strategy = SequentialStrategy(
        mock_llm, mock_registry, permissions=gate, sequence=["ghost_agent"])

    # Si no hay agentes en la secuencia, devuelve éxito con contenido vacío
    result = await strategy.execute("Tarea")
    assert result.success is True
    assert result.content == ""


@pytest.mark.asyncio
async def test_sequential_fork_mode(mock_llm, mock_registry):
    """Cubre el modo fork en sequential."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.sequential import SequentialStrategy
    from app.core.harness.context import ContextManager

    gate = PermissionGate(ask_user=None)
    strategy = SequentialStrategy(
        mock_llm, mock_registry, permissions=gate, sequence=["writer"])

    ctx = ContextManager(system_prompt="Test")
    ctx.add_user("Mensaje previo")

    with patch("app.core.harness.a2a.strategies.sequential.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(
            return_value=MagicMock(final_answer="Hecho"))
        MockLoop.return_value = mock_instance

        result = await strategy.execute("Tarea", context=ctx)
        assert result.success is True


@pytest.mark.asyncio
async def test_supervisor_fork_mode(mock_llm, mock_registry):
    """Cubre el modo fork en supervisor."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.context import ContextManager

    gate = PermissionGate(ask_user=None)
    mock_llm.chat.return_value = LLMResponse(content="writer")
    strategy = SupervisorStrategy(mock_llm, mock_registry, permissions=gate)

    ctx = ContextManager(system_prompt="Test")
    ctx.add_user("Mensaje previo")

    with patch("app.core.harness.a2a.strategies.supervisor.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(
            return_value=MagicMock(final_answer="Hecho"))
        MockLoop.return_value = mock_instance

        result = await strategy.execute("Tarea", context=ctx)
        assert result.success is True


@pytest.mark.asyncio
async def test_orchestrator_sequential_strategy(mock_llm, mock_registry):
    """Cubre la rama 'sequential' del OrchestratorTool (líneas 41-43)."""
    from app.core.harness.a2a.orchestrator import OrchestratorTool
    from unittest.mock import patch

    # Forzamos la estrategia sequential
    with patch("app.core.config.settings.A2A_STRATEGY", "sequential"):
        with patch("app.core.config.settings.A2A_SEQUENCE", "analyst,writer"):
            tool = OrchestratorTool(mock_llm, mock_registry, permissions=None)

            # Parcheamos la estrategia para que no ejecute nada real
            with patch("app.core.harness.a2a.orchestrator.SequentialStrategy") as MockSeq:
                mock_instance = MagicMock()
                mock_instance.execute = AsyncMock(
                    return_value=MagicMock(success=True, content="ok"))
                MockSeq.return_value = mock_instance

                result = await tool.run("tarea")

                assert result.success is True
                # Verificamos que se creó con la secuencia correcta
                MockSeq.assert_called_once_with(
                    mock_llm, mock_registry, None, ["analyst", "writer"]
                )


@pytest.mark.asyncio
async def test_supervisor_loads_persisted_permissions(tmp_path, monkeypatch, mock_llm, mock_registry):
    """Cubre la línea 72: añadir patrones al sub_gate desde permissions.json."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.supervisor import SupervisorStrategy

    # 🔥 Cambiamos al directorio temporal
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness" / "permissions.json").write_text(
        '{"session_allowed": ["read_text_file:test.txt", "bash:ls"]}'
    )

    gate = PermissionGate(ask_user=None)
    # Forzamos que el supervisor elija a "analyst"
    mock_llm.chat.return_value = LLMResponse(content="analyst")
    strategy = SupervisorStrategy(mock_llm, mock_registry, permissions=gate)

    # Parcheamos AgentLoop para que no se ejecute
    with patch("app.core.harness.a2a.strategies.supervisor.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(
            return_value=MagicMock(final_answer="Hecho"))
        MockLoop.return_value = mock_instance

        await strategy.execute("Tarea")

        # Verificamos que el sub_gate tiene los permisos inyectados
        # (esto cubre la línea 72)
        called_args = MockLoop.call_args
        sub_gate = called_args.kwargs["permissions"]
        assert "read_text_file:test.txt" in sub_gate.session_allowed
        assert "bash:ls" in sub_gate.session_allowed


@pytest.mark.asyncio
async def test_parallel_strategy(mock_llm, mock_registry):
    """Verifica que parallel lanza agentes en paralelo."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.parallel import ParallelStrategy

    gate = PermissionGate(ask_user=None)
    strategy = ParallelStrategy(
        mock_llm, mock_registry, permissions=gate,
        agents_to_run=["analyst", "writer"]
    )

    with patch("app.core.harness.a2a.strategies.parallel.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        # Cada agente devuelve algo distinto
        mock_instance.run = AsyncMock(side_effect=[
            MagicMock(final_answer="Análisis"),
            MagicMock(final_answer="Documentación")
        ])
        MockLoop.return_value = mock_instance

        result = await strategy.execute("Tarea")

        assert result.success is True
        assert "analyst" in result.content
        assert "writer" in result.content
        assert mock_instance.run.call_count == 2


@pytest.mark.asyncio
async def test_parallel_loads_persisted_permissions(tmp_path, monkeypatch, mock_llm, mock_registry):
    """Un permiso aprobado con 'a' no debe volver a preguntarse en parallel."""
    from app.core.harness.a2a.strategies.parallel import ParallelStrategy
    from app.core.harness.permissions import Decision, PermissionGate

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness" / "permissions.json").write_text(
        '{"session_allowed": ["bash:ls"]}', encoding="utf-8")

    ask_user = AsyncMock(return_value="n")
    parent_gate = PermissionGate(ask_user=ask_user)
    strategy = ParallelStrategy(
        mock_llm, mock_registry, permissions=parent_gate,
        agents_to_run=["analyst"]
    )

    with patch("app.core.harness.a2a.strategies.parallel.AgentLoop") as MockLoop:
        MockLoop.return_value.run = AsyncMock(
            return_value=MagicMock(final_answer="Hecho"))
        await strategy.execute("Tarea")

    sub_gate = MockLoop.call_args.kwargs["permissions"]
    assert await sub_gate.check("bash", {"command": "ls"}) == Decision.ALLOW
    ask_user.assert_not_called()


@pytest.mark.asyncio
async def test_parallel_subagents_share_parent_gate_state(tmp_path, monkeypatch, mock_llm, mock_registry):
    """Una aprobación en un subagente paralelo alcanza al padre y a sus hermanos."""
    from app.core.harness.a2a.strategies.parallel import ParallelStrategy
    from app.core.harness.permissions import Decision, PermissionGate

    monkeypatch.chdir(tmp_path)
    ask_user = AsyncMock(return_value="a")
    parent_gate = PermissionGate(ask_user=ask_user)
    strategy = ParallelStrategy(
        mock_llm, mock_registry, permissions=parent_gate,
        agents_to_run=["analyst", "writer"]
    )

    with patch("app.core.harness.a2a.strategies.parallel.AgentLoop") as MockLoop:
        MockLoop.return_value.run = AsyncMock(side_effect=[
            MagicMock(final_answer="Análisis"),
            MagicMock(final_answer="Documentación"),
        ])
        await strategy.execute("Tarea")

    gates = [call.kwargs["permissions"] for call in MockLoop.call_args_list]
    assert await gates[0].check("bash", {"command": "ls"}) == Decision.ALLOW
    ask_user.assert_awaited_once()
    ask_user.reset_mock()

    assert await gates[1].check("bash", {"command": "ls"}) == Decision.ALLOW
    assert await parent_gate.check("bash", {"command": "ls"}) == Decision.ALLOW
    ask_user.assert_not_awaited()


@pytest.mark.asyncio
async def test_parallel_no_valid_agents(mock_llm, mock_registry):
    """Cubre el caso de parallel sin agentes válidos."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.parallel import ParallelStrategy

    gate = PermissionGate(ask_user=None)
    strategy = ParallelStrategy(
        mock_llm, mock_registry, permissions=gate,
        agents_to_run=["ghost_agent"]
    )

    result = await strategy.execute("Tarea")
    assert result.success is False
    assert "Ningún agente válido" in result.error


@pytest.mark.asyncio
async def test_swarm_strategy_no_handoff(mock_llm, mock_registry):
    """Verifica que swarm termina cuando no hay handoff."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.swarm import SwarmStrategy

    gate = PermissionGate(ask_user=None)
    strategy = SwarmStrategy(
        mock_llm, mock_registry, permissions=gate,
        start_agent="analyst"
    )

    with patch("app.core.harness.a2a.strategies.swarm.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(
            return_value=MagicMock(final_answer="Análisis completado"))
        MockLoop.return_value = mock_instance

        result = await strategy.execute("Tarea")

        assert result.success is True
        assert "analyst" in result.content
        assert "Análisis completado" in result.content


@pytest.mark.asyncio
async def test_swarm_strategy_with_handoff(mock_llm, mock_registry):
    """Verifica que swarm hace handoff correctamente."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.swarm import SwarmStrategy

    gate = PermissionGate(ask_user=None)
    strategy = SwarmStrategy(
        mock_llm, mock_registry, permissions=gate,
        start_agent="analyst"
    )

    with patch("app.core.harness.a2a.strategies.swarm.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        # Analista pide handoff al writer, writer termina
        mock_instance.run = AsyncMock(side_effect=[
            MagicMock(final_answer="HANDOFF: writer\nAnálisis listo"),
            MagicMock(final_answer="Documentación completa")
        ])
        MockLoop.return_value = mock_instance

        result = await strategy.execute("Tarea")

        assert result.success is True
        assert "analyst" in result.content
        assert "writer" in result.content
        assert mock_instance.run.call_count == 2


@pytest.mark.asyncio
async def test_swarm_max_hops(mock_llm, mock_registry):
    """Cubre el límite de saltos del swarm."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.swarm import SwarmStrategy

    gate = PermissionGate(ask_user=None)
    strategy = SwarmStrategy(
        mock_llm, mock_registry, permissions=gate,
        start_agent="analyst"
    )

    with patch("app.core.harness.a2a.strategies.swarm.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        # Siempre hace handoff (simulando un bucle)
        mock_instance.run = AsyncMock(return_value=MagicMock(
            final_answer="HANDOFF: analyst\nSigo"))
        MockLoop.return_value = mock_instance

        result = await strategy.execute("Tarea")

        assert result.success is True
        assert "Límite de 5 saltos" in result.content


@pytest.mark.asyncio
async def test_supervisor_uses_agent_specific_model(mock_llm, mock_registry):
    """Verifica que el supervisor usa el modelo específico del agente."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.supervisor import SupervisorStrategy
    from unittest.mock import patch
    from app.core.config import settings

    # Asignamos un modelo al analyst
    mock_registry["analyst"].model = "openai/gpt-4o"
    mock_llm.chat.return_value = LLMResponse(content="analyst")

    gate = PermissionGate(ask_user=None)
    strategy = SupervisorStrategy(mock_llm, mock_registry, permissions=gate)

    with patch("app.core.harness.a2a.strategies.supervisor.AgentLoop") as MockLoop:
        with patch("app.core.harness.a2a.strategies.supervisor.get_llm") as mock_get_llm:
            mock_agent_llm = MagicMock()
            mock_get_llm.return_value = mock_agent_llm

            mock_instance = MagicMock()
            mock_instance.run = AsyncMock(
                return_value=MagicMock(final_answer="Hecho"))
            MockLoop.return_value = mock_instance

            await strategy.execute("Analiza")

            # 🔥 Verificamos que se llamó a get_llm con el proveedor y el modelo
            mock_get_llm.assert_called_with(
                settings.LLM_PROVIDER,
                model="openai/gpt-4o"
            )


@pytest.mark.asyncio
async def test_orchestrator_unknown_strategy(mock_llm, mock_registry):
    """Cubre la rama de estrategia desconocida en OrchestratorTool."""
    from app.core.harness.a2a.orchestrator import OrchestratorTool
    from unittest.mock import patch

    with patch("app.core.config.settings.A2A_STRATEGY", "inventada"):
        tool = OrchestratorTool(mock_llm, mock_registry, permissions=None)
        result = await tool.run("tarea")

        assert result.success is False
        assert "desconocida" in result.error


@pytest.mark.asyncio
async def test_orchestrator_exception(mock_llm, mock_registry):
    """Cubre el except del OrchestratorTool."""
    from app.core.harness.a2a.orchestrator import OrchestratorTool
    from unittest.mock import patch

    with patch("app.core.config.settings.A2A_STRATEGY", "supervisor"):
        with patch("app.core.harness.a2a.orchestrator.SupervisorStrategy") as MockStrategy:
            MockStrategy.side_effect = Exception("Fallo simulado")
            tool = OrchestratorTool(mock_llm, mock_registry, permissions=None)
            result = await tool.run("tarea")

            assert result.success is False
            assert "Fallo simulado" in result.error


@pytest.mark.asyncio
async def test_supervisor_agent_not_found(mock_llm, mock_registry):
    """Cubre el logger.warning cuando el supervisor no encuentra agente."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.supervisor import SupervisorStrategy

    mock_llm.chat.return_value = LLMResponse(content="ghost_agent")
    gate = PermissionGate(ask_user=None)
    strategy = SupervisorStrategy(mock_llm, mock_registry, permissions=gate)

    result = await strategy.execute("Tarea rara")

    assert result.success is False
    assert "ghost_agent" in result.error


@pytest.mark.asyncio
async def test_sequential_agent_not_found(mock_llm, mock_registry):
    """Cubre el logger.warning cuando sequential no encuentra agente."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.sequential import SequentialStrategy

    gate = PermissionGate(ask_user=None)
    strategy = SequentialStrategy(
        mock_llm, mock_registry, permissions=gate, sequence=["ghost_agent"]
    )

    result = await strategy.execute("Tarea")

    # Si no hay agentes válidos, devuelve éxito con contenido vacío
    assert result.success is True
    assert result.content == ""


@pytest.mark.asyncio
async def test_parallel_no_valid_agents(mock_llm, mock_registry):
    """Cubre el caso de parallel sin agentes válidos."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.parallel import ParallelStrategy

    gate = PermissionGate(ask_user=None)
    strategy = ParallelStrategy(
        mock_llm, mock_registry, permissions=gate, agents_to_run=[
            "ghost_agent"]
    )

    result = await strategy.execute("Tarea")

    assert result.success is False
    assert "Ningún agente válido" in result.error


@pytest.mark.asyncio
async def test_parallel_with_exception(mock_llm, mock_registry):
    """Cubre el manejo de excepciones en parallel."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.parallel import ParallelStrategy
    from unittest.mock import patch

    gate = PermissionGate(ask_user=None)
    strategy = ParallelStrategy(
        mock_llm, mock_registry, permissions=gate, agents_to_run=["analyst"]
    )

    with patch("app.core.harness.a2a.strategies.parallel.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(
            side_effect=Exception("Error en parallel"))
        MockLoop.return_value = mock_instance

        result = await strategy.execute("Tarea")

        assert result.success is True
        assert "Error en parallel" in result.content


@pytest.mark.asyncio
async def test_swarm_agent_not_found(mock_llm, mock_registry):
    """Cubre el logger.warning de agente no encontrado en swarm."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.swarm import SwarmStrategy

    gate = PermissionGate(ask_user=None)
    strategy = SwarmStrategy(
        mock_llm, mock_registry, permissions=gate, start_agent="ghost_agent"
    )

    result = await strategy.execute("Tarea")

    assert result.success is True
    assert "Límite de 5 saltos" in result.content or result.content == ""


@pytest.mark.asyncio
async def test_swarm_max_hops(mock_llm, mock_registry):
    """Cubre el límite de saltos del swarm."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.swarm import SwarmStrategy
    from unittest.mock import patch

    gate = PermissionGate(ask_user=None)
    strategy = SwarmStrategy(
        mock_llm, mock_registry, permissions=gate, start_agent="analyst"
    )

    with patch("app.core.harness.a2a.strategies.swarm.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        # Siempre hace handoff (simulando un bucle)
        mock_instance.run = AsyncMock(return_value=MagicMock(
            final_answer="HANDOFF: analyst\nSigo"
        ))
        MockLoop.return_value = mock_instance

        result = await strategy.execute("Tarea")

        assert result.success is True
        assert "Límite de 5 saltos" in result.content


@pytest.mark.asyncio
async def test_orchestrator_parallel_strategy(mock_llm, mock_registry):
    """Cubre la rama 'parallel' del OrchestratorTool."""
    from app.core.harness.a2a.orchestrator import OrchestratorTool
    from unittest.mock import patch

    with patch("app.core.config.settings.A2A_STRATEGY", "parallel"):
        with patch("app.core.config.settings.A2A_PARALLEL_AGENTS", "analyst,writer"):
            tool = OrchestratorTool(mock_llm, mock_registry, permissions=None)

            with patch("app.core.harness.a2a.orchestrator.ParallelStrategy") as MockPar:
                mock_instance = MagicMock()
                mock_instance.execute = AsyncMock(
                    return_value=MagicMock(success=True, content="ok"))
                MockPar.return_value = mock_instance

                result = await tool.run("tarea")
                assert result.success is True
                MockPar.assert_called_once()


@pytest.mark.asyncio
async def test_orchestrator_swarm_strategy(mock_llm, mock_registry):
    """Cubre la rama 'swarm' del OrchestratorTool."""
    from app.core.harness.a2a.orchestrator import OrchestratorTool
    from unittest.mock import patch

    with patch("app.core.config.settings.A2A_STRATEGY", "swarm"):
        with patch("app.core.config.settings.A2A_SWARM_START", "analyst"):
            tool = OrchestratorTool(mock_llm, mock_registry, permissions=None)

            with patch("app.core.harness.a2a.orchestrator.SwarmStrategy") as MockSwarm:
                mock_instance = MagicMock()
                mock_instance.execute = AsyncMock(
                    return_value=MagicMock(success=True, content="ok"))
                MockSwarm.return_value = mock_instance

                result = await tool.run("tarea")
                assert result.success is True
                MockSwarm.assert_called_once()


@pytest.mark.asyncio
async def test_parallel_agent_with_model_and_fork(mock_llm, mock_registry):
    """Cubre el modo fork y modelo específico en parallel."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.parallel import ParallelStrategy
    from app.core.harness.context import ContextManager

    # Asignamos un modelo al analyst
    mock_registry["analyst"].model = "openai/gpt-4o"
    mock_registry["analyst"].mode = "fork"

    gate = PermissionGate(ask_user=None)
    strategy = ParallelStrategy(
        mock_llm, mock_registry, permissions=gate, agents_to_run=["analyst"]
    )

    ctx = ContextManager(system_prompt="Test")
    ctx.add_user("Mensaje previo")

    with patch("app.core.harness.a2a.strategies.parallel.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(
            return_value=MagicMock(final_answer="Hecho"))
        MockLoop.return_value = mock_instance

        await strategy.execute("Tarea", context=ctx)
        assert MockLoop.called


@pytest.mark.asyncio
async def test_sequential_with_persisted_permissions_and_model(mock_llm, mock_registry, tmp_path, monkeypatch):
    """Cubre las líneas 23-25, 60 y 65 de sequential.py."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.sequential import SequentialStrategy

    # 1. Creamos un permissions.json falso
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness" /
     "permissions.json").write_text('{"session_allowed": ["read_file:test.txt"]}')

    # 2. Asignamos un modelo al analyst
    mock_registry["analyst"].model = "openai/gpt-4o"

    gate = PermissionGate(ask_user=None)
    strategy = SequentialStrategy(
        mock_llm, mock_registry, permissions=gate, sequence=["analyst"]
    )

    with patch("app.core.harness.a2a.strategies.sequential.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(
            return_value=MagicMock(final_answer="Hecho"))
        MockLoop.return_value = mock_instance

        await strategy.execute("Tarea")
        assert MockLoop.called


@pytest.mark.asyncio
async def test_swarm_with_persisted_permissions_fork_and_model(mock_llm, mock_registry, tmp_path, monkeypatch):
    """Cubre las líneas 26-28, 55-56, 72 y 77 de swarm.py."""
    from app.core.harness.permissions import PermissionGate
    from app.core.harness.a2a.strategies.swarm import SwarmStrategy
    from app.core.harness.context import ContextManager

    # 1. Creamos un permissions.json falso
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".harness").mkdir()
    (tmp_path / ".harness" /
     "permissions.json").write_text('{"session_allowed": ["read_file:test.txt"]}')

    # 2. Asignamos un modelo y modo fork al writer
    mock_registry["writer"].model = "openai/gpt-4o"
    mock_registry["writer"].mode = "fork"

    gate = PermissionGate(ask_user=None)
    strategy = SwarmStrategy(
        mock_llm, mock_registry, permissions=gate, start_agent="writer"
    )

    ctx = ContextManager(system_prompt="Test")
    ctx.add_user("Mensaje previo")

    with patch("app.core.harness.a2a.strategies.swarm.AgentLoop") as MockLoop:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(
            return_value=MagicMock(final_answer="Hecho"))
        MockLoop.return_value = mock_instance

        await strategy.execute("Tarea", context=ctx)
        assert MockLoop.called


def test_a2a_ignores_corrupt_persisted_permissions(tmp_path):
    """Un permissions.json corrupto no impide arrancar un subagente."""
    perm_file = tmp_path / "permissions.json"
    perm_file.write_text("{json roto", encoding="utf-8")
    strategy = SupervisorStrategy(MagicMock(), {}, None)

    with patch("app.core.config.Settings.permissions_file",
               new_callable=PropertyMock, return_value=perm_file):
        assert strategy._load_persisted_permissions() == set()
