# app/tui/widgets/file_aware_input.py
import asyncio
from pathlib import Path
import shutil
from textual.widgets import Input
from textual import events
from app.core.logger import logger


class FileAwareInput(Input):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._processing_paste = False
        self._pending_files = []
        self._batch_timer = None

    def _clean_path(self, text: str) -> str:
        text = text.strip().strip("'\"")
        text = text.replace("\\", "")
        return text

    async def _process_batch(self) -> None:
        """Procesa todos los archivos acumulados en un solo lote."""
        await asyncio.sleep(0.2)  # Esperar a que terminen de llegar
        files_to_process = self._pending_files.copy()
        self._pending_files.clear()
        for path_str in files_to_process:
            await self._process_single_file(path_str)

    async def _process_single_file(self, path_str: str) -> None:
        try:
            p = Path(path_str).expanduser()
            if p.exists() and p.is_file():
                project_root = Path.cwd()
                if not p.resolve().is_relative_to(project_root):
                    temp_dir = project_root / ".harness" / "temp_attachments"
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    dest = temp_dir / p.name
                    shutil.copy2(p, dest)
                    p = dest
                    await self.app.write_to_chat(f"📎 Archivo copiado a `{dest.relative_to(project_root)}` para poder leerlo.", type="system")
                await self.app.handle_file_paste(str(p))
        except Exception as e:
            logger.error(
                f"FileAwareInput: error procesando archivo: {e}", exc_info=True)

    async def _on_paste(self, event) -> None:
        clean_path = self._clean_path(event.text)
        if clean_path and Path(clean_path).exists() and Path(clean_path).is_file():
            self._pending_files.append(clean_path)
            if self._batch_timer:
                self._batch_timer.cancel()
            self._batch_timer = asyncio.create_task(self._process_batch())
            event.prevent_default()
            event.stop()

    async def on_key(self, event: events.Key) -> None:
        if event.key == "ctrl+u":
            # action_clear_input es síncrono; hacer `await` lanza TypeError.
            self.app.action_clear_input()
            event.prevent_default()
            event.stop()

    def watch_value(self, value: str) -> None:
        if self._processing_paste:
            self._processing_paste = False
            return

        clean_path = self._clean_path(value)
        allowed_exts = [
            ".pdf", ".txt", ".md", ".py", ".csv", ".json",
            ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
            ".png", ".jpg", ".jpeg", ".gif", ".webp"
        ]

        if clean_path.startswith("/") and any(clean_path.endswith(ext) for ext in allowed_exts):
            p = Path(clean_path)
            if p.exists() and p.is_file():
                self._pending_files.append(clean_path)
                self._processing_paste = True
                self.value = ""
                if self._batch_timer:
                    self._batch_timer.cancel()
                self._batch_timer = asyncio.create_task(self._process_batch())
