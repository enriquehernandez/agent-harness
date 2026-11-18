from pathlib import Path
import pandas as pd
from pypdf import PdfReader
from docx import Document
from openpyxl import load_workbook
from pptx import Presentation
from app.core.config import settings
from app.core.harness.tool import BaseTool, ToolResult
from app.core.logger import logger


class ReadDocumentTool(BaseTool):
    def __init__(self, base_dir: str = "."):
        self.name = "read_document"
        self.description = (
            "Extrae el texto de un documento. Soporta PDF, DOCX, XLSX y PPTX. "
            "Úsalo cuando el usuario adjunte un archivo binario y quieras leer su contenido."
        )
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Ruta del archivo a leer (ej. '.harness/temp_attachments/cv.pdf')."
                }
            },
            "required": ["path"]
        }
        self.base_dir = Path(base_dir).resolve()

    async def run(self, path: str) -> ToolResult:
        try:
            target = (self.base_dir / path).resolve()
            if not str(target).startswith(str(self.base_dir)):
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
            elif ext == ".xlsx":
                text = self._read_xlsx(target)
            elif ext == ".pptx":
                text = self._read_pptx(target)
            else:
                return ToolResult(success=False, content="", error=f"Formato '{ext}' no soportado por read_document.")

            if not text.strip():
                return ToolResult(success=True, content="(El documento no contiene texto extraíble. Podría estar vacío o ser una imagen escaneada.)")

            # 🔥 TRUNCADO CONFIGURABLE CON MENSAJE CLARO
            max_chars = settings.MAX_DOCUMENT_CHARS
            if len(text) > max_chars:
                total = len(text)
                text = text[:max_chars]
                truncation_msg = (
                    f"\n\n--- ⚠️ [DOCUMENTO TRUNCADO] ---\n"
                    f"El documento tiene {total:,} caracteres en total, pero solo se han extraído los primeros {max_chars:,} "
                    f"debido al límite `MAX_DOCUMENT_CHARS` configurado en `.env`. "
                    f"Si necesitas el resto del contenido, pide al usuario que te proporcione una parte específica o aumenta el límite."
                )
                text += truncation_msg

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

    def _read_xlsx(self, path: Path) -> str:
        wb = load_workbook(str(path), data_only=True)
        text = ""
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            text += f"--- Hoja: {sheet_name} ---\n"
            for row in sheet.iter_rows(values_only=True):
                # Filtrar filas completamente vacías
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
