import re
from pathlib import Path

import olefile
import xlrd
from pypdf import PdfReader
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation
from app.core.config import settings
from app.core.harness.tool import BaseTool, ToolResult
from app.core.logger import logger

# Las cadenas legibles de los formatos OLE (.doc/.ppt) aparecen como rutas de
# caracteres imprimibles; el mínimo evita confundir cabeceras binarias con texto.
_PRINTABLE_RUN = re.compile(r"[\x20-\x7e\xa1-\xff\r\n\t]{6,}")


def _printable_runs(data: bytes, encoding: str) -> str:
    """Extrae cadenas legibles de un stream binario decodificado con `encoding`."""
    decoded = data.decode(encoding, errors="ignore")
    return "\n".join(
        run.strip()
        for run in _PRINTABLE_RUN.findall(decoded)
        if run.strip()
    )


def _is_within_base_dir(target: Path, base_dir: Path) -> bool:
    """Comprueba que `target` está dentro de `base_dir` (resuelto)."""
    try:
        target.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False


class ReadDocumentTool(BaseTool):
    def __init__(self, base_dir: str = "."):
        self.name = "read_document"
        self.description = (
            "Extrae el texto de un documento. Soporta PDF, DOC/DOCX, XLS/XLSX y PPT/PPTX. "
            "Úsalo cuando el usuario adjunte un archivo binario y quieras leer su contenido."
        )
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Ruta del archivo a leer (ej. '.harness/temp_attachments/cv.pdf').",
                }
            },
            "required": ["path"],
        }
        self.base_dir = Path(base_dir).resolve()

    async def run(self, path: str) -> ToolResult:
        try:
            target = (self.base_dir / path).resolve()
            if not _is_within_base_dir(target, self.base_dir):
                return ToolResult(success=False, content="", error="Access denied: outside base directory.")

            if not target.is_file():
                return ToolResult(success=False, content="", error=f"File '{path}' not found.")

            ext = target.suffix.lower()
            logger.info(
                f"ReadDocumentTool: procesando '{path}' (formato: {ext})")

            if ext == ".pdf":
                text = self._read_pdf(target)
            elif ext == ".docx":
                text = self._read_docx(target)
            elif ext == ".doc":
                text = self._read_doc(target)
            elif ext == ".xlsx":
                text = self._read_xlsx(target)
            elif ext == ".xls":
                text = self._read_xls(target)
            elif ext == ".pptx":
                text = self._read_pptx(target)
            elif ext == ".ppt":
                text = self._read_ppt(target)
            else:
                return ToolResult(
                    success=False, content="",
                    error=f"Formato '{ext}' no soportado por read_document.",
                )

            if not text.strip():
                return ToolResult(
                    success=True,
                    content=(
                        "(El documento no contiene texto extraíble. "
                        "Podría estar vacío o ser una imagen escaneada.)"
                    ),
                )

            max_chars = settings.MAX_DOCUMENT_CHARS
            if len(text) > max_chars:
                total = len(text)
                text = text[:max_chars]
                text += (
                    f"\n\n--- ⚠️ [DOCUMENTO TRUNCADO] ---\n"
                    f"El documento tiene {total:,} caracteres en total, pero solo se han extraído "
                    f"los primeros {max_chars:,} debido al límite `MAX_DOCUMENT_CHARS` configurado "
                    f"en `.env`. Si necesitas el resto del contenido, pide al usuario que te "
                    f"proporcione una parte específica o aumenta el límite."
                )

            return ToolResult(success=True, content=text)

        except Exception as e:
            logger.error(f"ReadDocumentTool error: {e}", exc_info=True)
            return ToolResult(success=False, content="", error=str(e))

    def _read_pdf(self, path: Path) -> str:
        reader = PdfReader(str(path))
        text = ""
        for i, page in enumerate(reader.pages):
            page_text = (page.extract_text() or "").strip()
            if page_text:
                text += f"--- Página {i+1} ---\n"
                text += page_text + "\n\n"
        return text

    def _read_docx(self, path: Path) -> str:
        doc = Document(str(path))
        text = ""
        for p in doc.paragraphs:
            if p.text.strip():
                text += p.text + "\n"
        for i, table in enumerate(doc.tables):
            text += f"\n--- Tabla {i+1} ---\n"
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells]
                text += " | ".join(row_text) + "\n"
        return text

    def _read_doc(self, path: Path) -> str:
        with olefile.OleFileIO(str(path)) as ole:
            data = ole.openstream("WordDocument").read()
        # Word 97 guarda el texto en UTF-16LE o en páginas de 8 bits.
        return _printable_runs(data, "utf-16-le") or _printable_runs(data, "latin-1")

    def _read_xls(self, path: Path) -> str:
        book = xlrd.open_workbook(str(path))
        text = ""
        for sheet in book.sheets():
            text += f"--- Hoja: {sheet.name} ---\n"
            for row in range(sheet.nrows):
                values = []
                for col in range(sheet.ncols):
                    cell = sheet.cell(row, col)
                    value = cell.value
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        value = xlrd.xldate_as_datetime(value, book.datemode)
                    values.append(str(value) if value != "" else "")
                if any(values):
                    text += " | ".join(values) + "\n"
            text += "\n"
        return text

    def _read_xlsx(self, path: Path) -> str:
        wb = load_workbook(str(path), data_only=True)
        text = ""
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            text += f"--- Hoja: {sheet_name} ---\n"
            for row in sheet.iter_rows(values_only=True):
                if any(cell is not None for cell in row):
                    row_text = [
                        str(cell) if cell is not None else "" for cell in row]
                    text += " | ".join(row_text) + "\n"
            text += "\n"
        return text

    def _read_pptx(self, path: Path) -> str:
        prs = Presentation(str(path))
        text = ""
        for i, slide in enumerate(prs.slides):
            text += f"--- Diapositiva {i+1} ---\n"
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    text += shape.text + "\n"
            text += "\n"
        return text

    def _read_ppt(self, path: Path) -> str:
        with olefile.OleFileIO(str(path)) as ole:
            data = ole.openstream("PowerPoint Document").read()
        # Los atoms de texto de PowerPoint 97 son UTF-16LE o de 8 bits.
        return _printable_runs(data, "utf-16-le") or _printable_runs(data, "latin-1")
