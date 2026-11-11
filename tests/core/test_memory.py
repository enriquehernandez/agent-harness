from unittest.mock import patch
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.tools.memory import MemorySaveTool, MemoryRecallTool, MEMORY_DIR, SUMMARY_FILE


@pytest.mark.asyncio
async def test_memory_save_and_recall(tmp_path):
    """Prueba guardar y recuperar recuerdos."""
    # Parcheamos la ruta de la memoria para que use tmp_path
    with patch("app.tools.memory.MEMORY_DIR", tmp_path):
        with patch("app.tools.memory.SUMMARY_FILE", tmp_path / "summary.md"):
            save_tool = MemorySaveTool()

            # 1. Guardamos un recuerdo
            res = await save_tool.run(key="test_key", value="This is a test memory")
            assert res.success is True

            # Verificamos que se creó el archivo y el summary
            assert (tmp_path / "test_key.md").exists()
            assert (tmp_path / "summary.md").exists()

            # 2. Recuperamos el recuerdo
            recall_tool = MemoryRecallTool()
            res2 = await recall_tool.run(query="test memory")
            assert res2.success is True
            assert "This is a test memory" in res2.content


@pytest.mark.asyncio
async def test_memory_recall_empty(tmp_path):
    """Prueba recuperar cuando no hay memoria."""
    with patch("app.tools.memory.MEMORY_DIR", tmp_path / "non_existent"):
        recall_tool = MemoryRecallTool()
        res = await recall_tool.run(query="anything")
        assert res.success is True
        assert "Memory is empty" in res.content


@pytest.mark.asyncio
async def test_memory_save_error(tmp_path):
    """Prueba el manejo de errores al guardar."""
    with patch("app.tools.memory.MEMORY_DIR", tmp_path):
        save_tool = MemorySaveTool()
        # Forzamos un error al escribir
        with patch("pathlib.Path.write_text", side_effect=PermissionError("Denied")):
            res = await save_tool.run(key="test", value="value")
            assert res.success is False
            assert "Denied" in res.error


@pytest.mark.asyncio
async def test_memory_save_and_recall(tmp_path):
    from app.tools.memory import MemorySaveTool, MemoryRecallTool
    from unittest.mock import patch

    with patch("app.tools.memory.MEMORY_DIR", tmp_path):
        with patch("app.tools.memory.SUMMARY_FILE", tmp_path / "summary.md"):
            save_tool = MemorySaveTool()
            res = await save_tool.run(key="test_key", value="Test memory")
            assert res.success is True

            recall_tool = MemoryRecallTool()
            res2 = await recall_tool.run(query="test memory")
            assert "Test memory" in res2.content


@pytest.mark.asyncio
async def test_memory_recall_empty(tmp_path):
    from app.tools.memory import MemoryRecallTool
    from unittest.mock import patch
    with patch("app.tools.memory.MEMORY_DIR", tmp_path / "non_existent"):
        recall_tool = MemoryRecallTool()
        res = await recall_tool.run(query="anything")
        assert "Memory is empty" in res.content


@pytest.mark.asyncio
async def test_memory_save_error(tmp_path):
    """Cubre el except de MemorySaveTool (línea 43)."""
    from app.tools.memory import MemorySaveTool
    tool = MemorySaveTool()
    with patch("app.tools.memory.MEMORY_DIR", tmp_path):
        with patch("pathlib.Path.write_text", side_effect=Exception("Write error")):
            res = await tool.run(key="test", value="value")
            assert res.success is False
            assert "Write error" in res.error


@pytest.mark.asyncio
async def test_memory_recall_error(tmp_path):
    """Cubre el except de MemoryRecallTool (línea 79, 84-85)."""
    from app.tools.memory import MemoryRecallTool
    tool = MemoryRecallTool()
    with patch("app.tools.memory.MEMORY_DIR", tmp_path):
        # Creamos un archivo corrupto
        (tmp_path / "corrupt.md").write_text("Content")
        with patch("pathlib.Path.read_text", side_effect=Exception("Read error")):
            res = await tool.run(query="test")
            assert res.success is False
            assert "Read error" in res.error


@pytest.mark.asyncio
async def test_memory_edge_cases(tmp_path):
    """Cubre las líneas 43, 79, 84-85 de memory.py."""
    from app.tools.memory import MemorySaveTool, MemoryRecallTool

    # 1. _update_summary con summary.md existente (línea 43)
    (tmp_path / "summary.md").write_text("Old summary")
    save_tool = MemorySaveTool()
    with patch("app.tools.memory.MEMORY_DIR", tmp_path):
        with patch("app.tools.memory.SUMMARY_FILE", tmp_path / "summary.md"):
            await save_tool.run(key="test", value="value")
            # Debe haber ignorado summary.md y creado el nuevo
            assert "Old summary" not in (tmp_path / "summary.md").read_text()

    # 2. MemoryRecallTool no results (línea 79)
    recall_tool = MemoryRecallTool()
    with patch("app.tools.memory.MEMORY_DIR", tmp_path):
        res = await recall_tool.run(query="nonexistent")
        assert "No memories found" in res.content

    # 3. MemoryRecallTool error (línea 84-85)
    with patch("app.tools.memory.MEMORY_DIR", tmp_path):
        (tmp_path / "corrupt.md").write_text("Content")
        with patch("pathlib.Path.read_text", side_effect=Exception("Read error")):
            res = await recall_tool.run(query="test")
            assert res.success is False
            assert "Read error" in res.error
