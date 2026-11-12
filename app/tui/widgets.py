import json
import re
from rich.table import Table
from rich.tree import Tree
from rich.syntax import Syntax
from rich.markdown import Markdown as RichMarkdown
from rich.console import Group
from textual.widgets import Static
from app.core.logger import logger


class RichMessage(Static):
    """Widget que procesa Markdown, tablas, árboles y código."""

    def __init__(self, text: str, **kwargs):
        super().__init__(**kwargs)
        self.text = text

    def render(self):
        # 🔥 LOG DE DEPURACIÓN (reemplaza al print)
        has_table = "```table" in self.text
        has_tree = "```tree" in self.text
        has_json = "```json" in self.text

        if has_table or has_tree or has_json:
            logger.debug(
                f"RichMessage renderizando bloque rico. Table={has_table}, Tree={has_tree}, JSON={has_json}")

        if not has_table and not has_tree and not has_json:
            return RichMarkdown(self.text)

        return self._process_blocks(self.text)

    def _process_blocks(self, text: str):
        blocks = []
        # Regex para capturar ```table, ```tree, ```json
        pattern = r"```(table|tree|json)\s*\n(.*?)\n```"
        last_end = 0

        for match in re.finditer(pattern, text, re.DOTALL):
            start, end = match.span()
            if start > last_end:
                blocks.append(RichMarkdown(text[last_end:start]))

            block_type = match.group(1)
            content = match.group(2).strip()

            try:
                if block_type == "json":
                    data = json.loads(content)
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        table = Table(title="JSON Data")
                        for key in data[0].keys():
                            table.add_column(key)
                        for row in data:
                            table.add_row(*[str(v) for v in row.values()])
                        blocks.append(table)
                    else:
                        blocks.append(
                            Syntax(content, "json", theme="monokai", line_numbers=True))

                elif block_type == "tree":
                    tree = Tree("📁 Root")
                    for line in content.split("\n"):
                        if line.strip():
                            tree.add(line.strip())
                    blocks.append(tree)

                elif block_type == "table":
                    # 🔥 Parseamos el formato Markdown estándar: | a | b |
                    lines = [line.strip()
                             for line in content.split("\n") if line.strip()]
                    if len(lines) < 2:
                        raise ValueError("Tabla mal formada")

                    # Extraemos las celdas de la cabecera
                    headers = [c.strip()
                               for c in lines[0].split("|") if c.strip()]
                    table = Table()
                    for h in headers:
                        table.add_column(h)

                    # Saltamos la línea separadora (| --- | --- |)
                    for line in lines[2:]:
                        cells = [c.strip()
                                 for c in line.split("|") if c.strip()]
                        if len(cells) == len(headers):
                            table.add_row(*cells)

                    blocks.append(table)

            except Exception as e:
                blocks.append(RichMarkdown(
                    f"⚠️ Error renderizando bloque `{block_type}`: {e}"))

            last_end = end

        if last_end < len(text):
            blocks.append(RichMarkdown(text[last_end:]))

        return Group(*blocks)
