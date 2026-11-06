import pytest
from app.core.harness.tool import FunctionTool
from app.tools.filesystem import ReadFileTool, WriteFileTool
from app.tools.shell import BashTool


@pytest.mark.asyncio
async def test_write_and_read_file(tmp_path):
    # tmp_path es una fixture de pytest que crea un directorio temporal
    tool_write = WriteFileTool(base_dir=str(tmp_path))
    tool_read = ReadFileTool(base_dir=str(tmp_path))

    result_write = await tool_write.run(path="test.txt", content="Hola Mundo")
    assert result_write.success is True

    result_read = await tool_read.run(path="test.txt")
    assert result_read.success is True
    assert result_read.content == "Hola Mundo"


@pytest.mark.asyncio
async def test_read_file_traversal_protection(tmp_path):
    tool_read = ReadFileTool(base_dir=str(tmp_path))
    # Intento de salir del directorio base
    result = await tool_read.run(path="../../../etc/passwd")
    assert result.success is False
    assert "Acceso denegado" in result.error


@pytest.mark.asyncio
async def test_bash_tool_success():
    tool = BashTool()
    result = await tool.run(command="echo 'Hola'")
    assert result.success is True
    assert "Hola" in result.content


@pytest.mark.asyncio
async def test_bash_tool_timeout():
    tool = BashTool(timeout_seconds=1)
    result = await tool.run(command="sleep 2")
    assert result.success is False
    assert "Timeout" in result.error


@pytest.mark.asyncio
async def test_function_tool_async():
    """Cubre la rama donde la función inyectada es asíncrona."""
    async def async_func(x: int) -> int:
        return x * 2

    tool = FunctionTool(
        name="async_tool",
        description="Test",
        parameters_schema={},
        func=async_func
    )
    result = await tool.run(x=5)
    assert result.success is True
    assert result.content == "10"


@pytest.mark.asyncio
async def test_filesystem_errors(tmp_path):
    from app.tools.filesystem import ReadFileTool, WriteFileTool
    from unittest.mock import patch

    # 1. Creamos un archivo real para que exista
    test_file = tmp_path / "archivo.txt"
    test_file.write_text("Hola")

    tool_read = ReadFileTool(base_dir=str(tmp_path))

    # 2. Ahora parcheamos el read_text para que lance PermissionError
    with patch("pathlib.Path.read_text", side_effect=PermissionError("Denied")):
        res = await tool_read.run(path="archivo.txt")
        assert res.success is False
        assert "Denied" in res.error

    tool_write = WriteFileTool(base_dir=str(tmp_path))
    # Simulamos un error al escribir
    with patch("pathlib.Path.write_text", side_effect=PermissionError("Denied")):
        res = await tool_write.run(path="archivo.txt", content="Hola")
        assert res.success is False
        assert "Denied" in res.error


@pytest.mark.asyncio
async def test_bash_tool_error():
    from app.tools.shell import BashTool
    tool = BashTool()
    # Comando que falla
    result = await tool.run(command="comando_que_no_existe_123")
    assert result.success is False
    assert "not found" in result.error or "Exit code" in result.error


@pytest.mark.asyncio
async def test_filesystem_permission_errors(tmp_path):
    from app.tools.filesystem import ReadFileTool, WriteFileTool

    # 1. ReadFile con ruta fuera de base
    tool_read = ReadFileTool(base_dir=str(tmp_path))
    res1 = await tool_read.run(path="/etc/passwd")
    assert res1.success is False
    assert "Acceso denegado" in res1.error

    # 2. WriteFile con ruta fuera de base
    tool_write = WriteFileTool(base_dir=str(tmp_path))
    res2 = await tool_write.run(path="/etc/passwd", content="hack")
    assert res2.success is False
    assert "Acceso denegado" in res2.error


@pytest.mark.asyncio
async def test_bash_tool_general_exception():
    from app.tools.shell import BashTool
    from unittest.mock import patch

    tool = BashTool()

    # Cubre el except general del BashTool
    with patch("asyncio.create_subprocess_shell", side_effect=Exception("Boom")):
        res = await tool.run(command="ls")
        assert res.success is False
        assert res.error == "Boom"


@pytest.mark.asyncio
async def test_filesystem_errors(tmp_path):
    from app.tools.filesystem import ReadFileTool, WriteFileTool
    from unittest.mock import patch

    # 🔥 Crear el archivo para que pase el is_file()
    test_file = tmp_path / "archivo.txt"
    test_file.write_text("Hola")

    tool_read = ReadFileTool(base_dir=str(tmp_path))

    # Simulamos un error de permisos al leer
    with patch("pathlib.Path.read_text", side_effect=PermissionError("Denied")):
        res = await tool_read.run(path="archivo.txt")
        assert res.success is False
        assert "Denied" in res.error

    tool_write = WriteFileTool(base_dir=str(tmp_path))
    # Simulamos un error al escribir
    with patch("pathlib.Path.write_text", side_effect=PermissionError("Denied")):
        res = await tool_write.run(path="archivo.txt", content="Hola")
        assert res.success is False
        assert "Denied" in res.error


@pytest.mark.asyncio
async def test_function_tool_exception():
    from app.core.harness.tool import FunctionTool

    def crash():
        raise ValueError("Crash")
    tool = FunctionTool(name="crash", description="",
                        parameters_schema={}, func=crash)
    res = await tool.run()
    assert res.success is False
    assert "Crash" in res.error


def test_registry_contains(basic_registry):
    # Cubre el __contains__ de ToolRegistry (línea 80)
    assert "add" in basic_registry
    assert "no_existe" not in basic_registry


@pytest.mark.asyncio
async def test_filesystem_read_not_found_and_truncate(tmp_path):
    from app.tools.filesystem import ReadFileTool, WriteFileTool

    tool_read = ReadFileTool(base_dir=str(tmp_path))
    tool_write = WriteFileTool(base_dir=str(tmp_path))

    # 1. Cubre línea 30 (archivo no existe)
    res = await tool_read.run(path="fantasma.txt")
    assert "no existe" in res.error

    # 2. Cubre línea 35 (truncado)
    huge_text = "A" * 11000
    await tool_write.run(path="huge.txt", content=huge_text)
    res_huge = await tool_read.run(path="huge.txt")
    assert "[TRUNCADO]" in res_huge.content
