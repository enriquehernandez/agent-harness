import pytest
from app.core.harness.tool import FunctionTool
from app.tools.filesystem import ReadFileTool, WriteFileTool
from app.tools.shell import BashTool


@pytest.mark.asyncio
async def test_write_and_read_file(tmp_path):
    tool_write = WriteFileTool(base_dir=str(tmp_path))
    tool_read = ReadFileTool(base_dir=str(tmp_path))

    result_write = await tool_write.run(path="test.txt", content="Hello World")
    assert result_write.success is True

    result_read = await tool_read.run(path="test.txt")
    assert result_read.success is True
    assert result_read.content == "Hello World"


@pytest.mark.asyncio
async def test_read_file_traversal_protection(tmp_path):
    tool_read = ReadFileTool(base_dir=str(tmp_path))
    result = await tool_read.run(path="../../../etc/passwd")
    assert result.success is False
    assert "Access denied" in result.error


@pytest.mark.asyncio
async def test_bash_tool_success():
    tool = BashTool()
    result = await tool.run(command="echo 'Hello'")
    assert result.success is True
    assert "Hello" in result.content


@pytest.mark.asyncio
async def test_bash_tool_timeout():
    tool = BashTool(timeout_seconds=1)
    result = await tool.run(command="sleep 2")
    assert result.success is False
    assert "Timeout" in result.error


@pytest.mark.asyncio
async def test_function_tool_async():
    """Covers the branch where the injected function is asynchronous."""
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
    test_file = tmp_path / "file.txt"
    test_file.write_text("Hello")

    tool_read = ReadFileTool(base_dir=str(tmp_path))

    from unittest.mock import patch
    with patch("pathlib.Path.read_text", side_effect=PermissionError("Denied")):
        res = await tool_read.run(path="file.txt")
        assert res.success is False
        assert "Denied" in res.error

    tool_write = WriteFileTool(base_dir=str(tmp_path))
    with patch("pathlib.Path.write_text", side_effect=PermissionError("Denied")):
        res = await tool_write.run(path="file.txt", content="Hello")
        assert res.success is False
        assert "Denied" in res.error


@pytest.mark.asyncio
async def test_bash_tool_error():
    tool = BashTool()
    result = await tool.run(command="command_that_does_not_exist_123")
    assert result.success is False
    assert "not found" in result.error or "Exit code" in result.error


@pytest.mark.asyncio
async def test_bash_tool_general_exception():
    from unittest.mock import patch
    tool = BashTool()

    with patch("asyncio.create_subprocess_shell", side_effect=Exception("Boom")):
        res = await tool.run(command="ls")
        assert res.success is False
        assert res.error == "Boom"


@pytest.mark.asyncio
async def test_function_tool_exception():
    def crash():
        raise ValueError("Crash")
    tool = FunctionTool(name="crash", description="",
                        parameters_schema={}, func=crash)
    res = await tool.run()
    assert res.success is False
    assert "Crash" in res.error


def test_registry_contains(basic_registry):
    assert "add" in basic_registry
    assert "not_exists" not in basic_registry


@pytest.mark.asyncio
async def test_filesystem_write_error(tmp_path):
    """Cubre el except de WriteFileTool."""
    from app.tools.filesystem import WriteFileTool
    from unittest.mock import patch
    tool = WriteFileTool(base_dir=str(tmp_path))
    with patch("pathlib.Path.write_text", side_effect=Exception("Write error")):
        res = await tool.run(path="test.txt", content="Hello")
        assert res.success is False
        assert "Write error" in res.error


@pytest.mark.asyncio
async def test_filesystem_read_error_and_write_error(tmp_path):
    """Cubre el except de ReadFileTool y WriteFileTool (línea 29, 33, 58)."""
    from app.tools.filesystem import ReadFileTool, WriteFileTool
    from unittest.mock import patch

    # 1. Read error (línea 29)
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello")
    tool_read = ReadFileTool(base_dir=str(tmp_path))
    with patch("pathlib.Path.read_text", side_effect=Exception("Read error")):
        res = await tool_read.run(path="test.txt")
        assert res.success is False
        assert "Read error" in res.error

    # 2. Write error (línea 58)
    tool_write = WriteFileTool(base_dir=str(tmp_path))
    with patch("pathlib.Path.write_text", side_effect=Exception("Write error")):
        res = await tool_write.run(path="test.txt", content="Hello")
        assert res.success is False
        assert "Write error" in res.error


@pytest.mark.asyncio
async def test_filesystem_read_missing_truncate_and_write_denied(tmp_path):
    """Cubre las líneas 29, 33 y 58 de filesystem.py."""
    from app.tools.filesystem import ReadFileTool, WriteFileTool

    tool_read = ReadFileTool(base_dir=str(tmp_path))
    tool_write = WriteFileTool(base_dir=str(tmp_path))

    # 1. Read missing (línea 29)
    res = await tool_read.run(path="ghost.txt")
    assert "does not exist" in res.error

    # 2. Truncate (línea 33)
    huge_content = "A" * 11000
    huge_file = tmp_path / "huge.txt"
    huge_file.write_text(huge_content)
    res = await tool_read.run(path="huge.txt")
    assert "[TRUNCATED]" in res.content

    # 3. Write denied (línea 58)
    res = await tool_write.run(path="../outside.txt", content="Hack")
    assert "Access denied" in res.error
