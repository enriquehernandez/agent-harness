from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.core.harness.tool import FunctionTool, ToolResult
from app.tools.filesystem import ReadFileTool, WriteFileTool
from app.tools.shell import BashTool
from app.tools.skills import LoadSkillTool


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
async def test_edit_file_applies_edits(tmp_path):
    from app.tools.filesystem import EditFileTool

    target = tmp_path / "note.txt"
    target.write_text("uno\ndos\nuno\n", encoding="utf-8")
    tool = EditFileTool(base_dir=str(tmp_path))

    result = await tool.run(path="note.txt", edits=[
        {"oldText": "uno", "newText": "UNO"},
        {"oldText": "dos", "newText": "DOS"},
    ])

    assert result.success is True
    assert target.read_text(encoding="utf-8") == "UNO\nDOS\nUNO\n"


@pytest.mark.asyncio
async def test_edit_file_is_registered_in_core_tools():
    from app.core.harness.tool import ToolRegistry
    from app.tools import register_core_tools

    registry = ToolRegistry()
    register_core_tools(registry)

    assert registry.get("edit_file") is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("path, edits, expected", [
    ("../fuera.txt", [{"oldText": "a", "newText": "b"}], "Access denied"),
    ("missing.txt", [{"oldText": "a", "newText": "b"}], "does not exist"),
    ("note.txt", [{"oldText": "", "newText": "b"}], "oldText"),
    ("note.txt", [{"oldText": "no está", "newText": "b"}], "not found"),
])
async def test_edit_file_rejects_invalid_input(tmp_path, path, edits, expected):
    from app.tools.filesystem import EditFileTool

    (tmp_path / "note.txt").write_text("contenido", encoding="utf-8")
    result = await EditFileTool(base_dir=str(tmp_path)).run(path=path, edits=edits)

    assert result.success is False
    assert expected in result.error


@pytest.mark.asyncio
async def test_edit_file_read_error(tmp_path):
    from app.tools.filesystem import EditFileTool

    (tmp_path / "note.txt").write_text("contenido", encoding="utf-8")
    with patch.object(Path, "read_text", side_effect=OSError("boom")):
        result = await EditFileTool(base_dir=str(tmp_path)).run(
            path="note.txt", edits=[{"oldText": "a", "newText": "b"}])

    assert result.success is False
    assert "boom" in result.error


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


@pytest.mark.asyncio
@pytest.mark.parametrize("approved", [
    "python scripts/capture_snapshot.py --out report.md",
    "python scripts/capture_snapshot.py",
])
async def test_bash_tool_executes_approved_command_verbatim(approved):
    """P0.2: BashTool no reescribe el comando aprobado ni exporta por su cuenta."""
    tool = BashTool()
    assert not hasattr(tool, "export_observations")

    with patch("asyncio.create_subprocess_shell") as mock_shell:
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"OK", b"")
        mock_process.returncode = 0
        mock_shell.return_value = mock_process

        result = await tool.run(approved)

        assert result.success is True
        assert mock_shell.call_args[0][0] == approved


@pytest.mark.asyncio
async def test_load_skill_tool_not_found():
    """Cubre el error de skill no encontrada."""
    tool = LoadSkillTool()
    result = await tool.run("skill_inexistente_123")
    assert result.success is False
    assert "no encontrada" in result.error


@pytest.mark.asyncio
async def test_load_skill_tool_success(tmp_path):
    """Cubre la carga exitosa de una skill."""
    skills_dir = tmp_path / ".agents" / "skills" / "test_skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("# Test Skill\nInstrucciones.")

    tool = LoadSkillTool()
    tool.skills_dir = tmp_path / ".agents" / "skills"

    result = await tool.run("test_skill")
    assert result.success is True
    assert "# Test Skill" in result.content
    assert "test_skill" in result.content


@pytest.mark.asyncio
async def test_skill_tool_discover_no_dir():
    """Cubre skills.py línea 28: return [] si no existe el dir."""
    from app.tools.skills import LoadSkillTool
    tool = LoadSkillTool()
    tool.skills_dir = Path("/ruta/que/no/existe")
    assert tool.discover_skills() == []


@pytest.mark.asyncio
async def test_observations_tool(tmp_path):
    """Cubre observations.py líneas 23-56."""
    from app.tools.observations import ExportObservationsTool
    from app.core.harness.tool import ToolRegistry, FunctionTool

    registry = ToolRegistry()
    registry.register(FunctionTool(
        name="dummy", description="[MCP] Test", parameters_schema={}, func=lambda: ""
    ))

    class MockClient:
        class ServerParams:
            command = "uv"
        server_params = ServerParams()

    tool = ExportObservationsTool(
        registry=registry, mcp_clients=[MockClient()])

    out_file = tmp_path / "out.json"
    result = await tool.run(str(out_file))

    assert result.success is True
    assert out_file.exists()

    import json
    data = json.loads(out_file.read_text())
    assert len(data["tools"]) == 1
    assert data["mcp_servers"][0]["name"] == "uv"


@pytest.mark.asyncio
async def test_observations_classifies_real_mcp_tool(tmp_path):
    """Una tool MCP real debe exportarse con origin='MCP'."""
    import json
    from app.tools.observations import ExportObservationsTool
    from app.core.harness.tool import ToolRegistry
    from app.mcp.client import MCPToolProxy

    registry = ToolRegistry()
    registry.register(MCPToolProxy(
        name="mcp_fs_read", description="Lee un archivo",
        parameters_schema={}, client=MagicMock(), server_name="fs",
    ))
    tool = ExportObservationsTool(registry=registry, mcp_clients=[])

    out_file = tmp_path / "out.json"
    await tool.run(str(out_file))

    data = json.loads(out_file.read_text())
    assert data["tools"][0]["origin"] == "MCP"


@pytest.mark.asyncio
async def test_read_document_tool(tmp_path):
    """Cubre ReadDocumentTool para todos los formatos."""
    from app.tools.documents import ReadDocumentTool
    from unittest.mock import patch

    tool = ReadDocumentTool(base_dir=str(tmp_path))

    # 1. Archivo no existe
    res = await tool.run("no_existe.pdf")
    assert res.success is False
    assert "not found" in res.error

    # 2. Archivo fuera del base_dir
    res = await tool.run("../test.pdf")
    assert res.success is False
    assert "Access denied" in res.error

    # 3. PDF
    fake_pdf = tmp_path / "test.pdf"
    fake_pdf.write_text("fake")
    with patch("app.tools.documents.PdfReader") as mock_reader:
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Texto del PDF"
        mock_reader.return_value.pages = [mock_page]

        res = await tool.run("test.pdf")
        assert res.success is True
        assert "Texto del PDF" in res.content

    # 4. DOCX
    fake_docx = tmp_path / "test.docx"
    fake_docx.write_text("fake")
    with patch("app.tools.documents.Document") as mock_doc:
        mock_p = MagicMock()
        mock_p.text = "Texto del DOCX"
        mock_doc.return_value.paragraphs = [mock_p]
        mock_doc.return_value.tables = []

        res = await tool.run("test.docx")
        assert res.success is True
        assert "Texto del DOCX" in res.content

    # 5. XLSX
    fake_xlsx = tmp_path / "test.xlsx"
    fake_xlsx.write_text("fake")
    with patch("app.tools.documents.load_workbook") as mock_wb:
        mock_sheet = MagicMock()
        mock_sheet.iter_rows.return_value = [(1, 2), (3, 4)]
        mock_wb.return_value.sheetnames = ["Hoja1"]
        mock_wb.return_value.__getitem__.return_value = mock_sheet

        res = await tool.run("test.xlsx")
        assert res.success is True
        assert "1 | 2" in res.content

    # 6. PPTX
    fake_pptx = tmp_path / "test.pptx"
    fake_pptx.write_text("fake")
    with patch("app.tools.documents.Presentation") as mock_pptx:
        mock_slide = MagicMock()
        mock_shape = MagicMock()
        mock_shape.text = "Texto del PPTX"
        mock_slide.shapes = [mock_shape]
        mock_pptx.return_value.slides = [mock_slide]

        res = await tool.run("test.pptx")
        assert res.success is True
        assert "Texto del PPTX" in res.content

    # 7. Formato no soportado
    fake_txt = tmp_path / "test.txt"
    fake_txt.write_text("Hello")
    res = await tool.run("test.txt")
    assert res.success is False
    assert "no soportado" in res.error


@pytest.mark.asyncio
async def test_read_document_empty_and_truncated(tmp_path):
    """Cubre líneas 55, 59 y 84-87 de documents.py."""
    from app.tools.documents import ReadDocumentTool
    from unittest.mock import patch, MagicMock
    from app.core.config import settings

    tool = ReadDocumentTool(base_dir=str(tmp_path))

    # 1. Documento vacío (línea 55)
    fake_pdf = tmp_path / "empty.pdf"
    fake_pdf.write_text("fake")
    with patch("app.tools.documents.PdfReader") as mock_reader:
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""
        mock_reader.return_value.pages = [mock_page]

        res = await tool.run("empty.pdf")
        assert res.success is True
        assert "no contiene texto extraíble" in res.content

    # 2. Documento con mucho texto (línea 59)
    fake_pdf2 = tmp_path / "large.pdf"
    fake_pdf2.write_text("fake")
    with patch("app.tools.documents.PdfReader") as mock_reader:
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "A" * 20000
        mock_reader.return_value.pages = [mock_page]

        with patch.object(settings, "MAX_DOCUMENT_CHARS", 100):
            res = await tool.run("large.pdf")
            assert res.success is True
            assert "[DOCUMENTO TRUNCADO]" in res.content
            assert "MAX_DOCUMENT_CHARS" in res.content
            assert "caracteres" in res.content

    # 3. DOCX con tablas (líneas 84-87)
    fake_docx = tmp_path / "table.docx"
    fake_docx.write_text("fake")
    with patch("app.tools.documents.Document") as mock_doc:
        mock_doc.return_value.paragraphs = []

        mock_table = MagicMock()
        mock_cell1 = MagicMock()
        mock_cell1.text = "Celda 1"
        mock_cell2 = MagicMock()
        mock_cell2.text = "Celda 2"
        mock_row = MagicMock()
        mock_row.cells = [mock_cell1, mock_cell2]
        mock_table.rows = [mock_row]

        mock_doc.return_value.tables = [mock_table]

        res = await tool.run("table.docx")
        assert res.success is True
        assert "Celda 1 | Celda 2" in res.content


@pytest.mark.asyncio
async def test_read_document_legacy_formats(tmp_path):
    """Los formatos legacy .xls, .doc y .ppt extraen texto."""
    from app.tools.documents import ReadDocumentTool
    import xlrd

    tool = ReadDocumentTool(base_dir=str(tmp_path))
    assert "DOC" in tool.description and "XLS" in tool.description and "PPT" in tool.description

    # .xls con celda de fecha
    (tmp_path / "test.xls").write_text("fake")
    sheet = MagicMock()
    sheet.name = "Ventas"
    sheet.nrows = 2
    sheet.ncols = 2
    cell_text = MagicMock(ctype=xlrd.XL_CELL_TEXT, value="Producto")
    cell_number = MagicMock(ctype=xlrd.XL_CELL_NUMBER, value=3)
    cell_date = MagicMock(ctype=xlrd.XL_CELL_DATE, value=45000)
    cell_empty = MagicMock(ctype=xlrd.XL_CELL_EMPTY, value="")
    sheet.cell.side_effect = [
        cell_text, cell_number, cell_date, cell_empty]
    book = MagicMock()
    book.sheets.return_value = [sheet]
    with patch("app.tools.documents.xlrd.open_workbook", return_value=book):
        with patch("app.tools.documents.xlrd.xldate_as_datetime", return_value="2023-01-01"):
            res = await tool.run("test.xls")
    assert res.success is True
    assert "Producto | 3" in res.content
    assert "2023-01-01" in res.content

    # .doc: el texto está en UTF-16LE dentro del stream WordDocument
    (tmp_path / "test.doc").write_text("fake")
    with patch("app.tools.documents.olefile.OleFileIO") as MockOle:
        ole = MockOle.return_value.__enter__.return_value
        ole.openstream.return_value.read.return_value = (
            "Informe legacy".encode("utf-16-le"))
        res = await tool.run("test.doc")
    assert res.success is True
    assert "Informe legacy" in res.content
    ole.openstream.assert_called_with("WordDocument")

    # .ppt: el texto está en el stream PowerPoint Document
    (tmp_path / "test.ppt").write_text("fake")
    with patch("app.tools.documents.olefile.OleFileIO") as MockOle:
        ole = MockOle.return_value.__enter__.return_value
        ole.openstream.return_value.read.return_value = (
            "Diapositiva legacy".encode("utf-16-le"))
        res = await tool.run("test.ppt")
    assert res.success is True
    assert "Diapositiva legacy" in res.content
    ole.openstream.assert_called_with("PowerPoint Document")


def test_read_document_legacy_text_fallback():
    """Las cadenas se extraen en UTF-16LE o, si no hay, en Latin-1."""
    from app.tools.documents import _printable_runs

    assert _printable_runs("Informe legacy".encode("utf-16-le"), "utf-16-le") == "Informe legacy"
    assert _printable_runs(b"\x00\x01Texto Latin-1\x00", "latin-1") == "Texto Latin-1"
    assert _printable_runs(b"corto", "latin-1") == ""


@pytest.mark.asyncio
async def test_read_document_pptx(tmp_path):
    """Cubre líneas 94-97 de documents.py (_read_pptx)."""
    from app.tools.documents import ReadDocumentTool
    from unittest.mock import patch, MagicMock

    tool = ReadDocumentTool(base_dir=str(tmp_path))

    fake_pptx = tmp_path / "test.pptx"
    fake_pptx.write_text("fake")
    with patch("app.tools.documents.Presentation") as mock_pptx:
        mock_slide = MagicMock()
        mock_shape = MagicMock()
        mock_shape.text = "Texto del PPTX"
        mock_slide.shapes = [mock_shape]
        mock_pptx.return_value.slides = [mock_slide]

        res = await tool.run("test.pptx")
        assert res.success is True
        assert "Texto del PPTX" in res.content
