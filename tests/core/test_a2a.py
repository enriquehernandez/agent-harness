import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.harness.a2a.base import AgentCard
from app.core.harness.a2a.strategies.supervisor import SupervisorStrategy
from app.core.harness.a2a.strategies.sequential import SequentialStrategy
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
