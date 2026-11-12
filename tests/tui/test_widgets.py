import pytest
from unittest.mock import patch
from app.tui.widgets import RichMessage


def test_rich_message_plain_text():
    """Cubre el render de texto sin bloques."""
    msg = RichMessage("Hola, mundo")
    renderable = msg.render()
    # Debe ser un RichMarkdown, no un Group
    from rich.markdown import Markdown
    assert isinstance(renderable, Markdown)


def test_rich_message_json_table():
    """Cubre el render de un bloque JSON que se convierte en tabla."""
    text = '```json\n[{"a": 1, "b": 2}, {"a": 3, "b": 4}]\n```'
    msg = RichMessage(text)
    renderable = msg.render()
    # Es un Group con un Table dentro
    from rich.console import Group
    from rich.table import Table
    assert isinstance(renderable, Group)
    assert any(isinstance(child, Table) for child in renderable.renderables)


def test_rich_message_tree():
    """Cubre el render de un bloque tree."""
    text = '```tree\nroot\n  child\n```'
    msg = RichMessage(text)
    renderable = msg.render()
    from rich.console import Group
    from rich.tree import Tree
    assert isinstance(renderable, Group)
    assert any(isinstance(child, Tree) for child in renderable.renderables)


def test_rich_message_table():
    """Cubre el render de un bloque table."""
    text = '```table\n| A | B |\n| --- | --- |\n| 1 | 2 |\n```'
    msg = RichMessage(text)
    renderable = msg.render()
    from rich.console import Group
    from rich.table import Table
    assert isinstance(renderable, Group)
    assert any(isinstance(child, Table) for child in renderable.renderables)


def test_rich_message_invalid_json():
    """Cubre el except de JSON inválido."""
    text = '```json\n{invalid}\n```'
    msg = RichMessage(text)
    renderable = msg.render()
    from rich.console import Group
    from rich.markdown import Markdown
    assert isinstance(renderable, Group)
    # Debe haber un Markdown (el del error) en lugar de un Syntax
    assert any(isinstance(child, Markdown) for child in renderable.renderables)
    # Y ningún Syntax (porque el JSON falló)
    from rich.syntax import Syntax
    assert not any(isinstance(child, Syntax)
                   for child in renderable.renderables)


def test_rich_message_invalid_table():
    """Cubre el except de tabla mal formada (menos de 2 líneas)."""
    text = '```table\n| A | B |\n```'
    msg = RichMessage(text)
    renderable = msg.render()
    from rich.console import Group
    from rich.markdown import Markdown
    from rich.table import Table
    assert isinstance(renderable, Group)
    # Debe haber un Markdown (error), no una Table
    assert any(isinstance(child, Markdown) for child in renderable.renderables)
    assert not any(isinstance(child, Table)
                   for child in renderable.renderables)


def test_rich_message_text_after_block():
    """Cubre el texto que va después del bloque."""
    text = '```tree\nroot\n```\nTexto final.'
    msg = RichMessage(text)
    renderable = msg.render()
    from rich.console import Group
    from rich.markdown import Markdown
    assert isinstance(renderable, Group)
    assert any(isinstance(child, Markdown) for child in renderable.renderables)


def test_rich_message_text_before_block():
    """Cubre la línea 43: texto antes de un bloque."""
    text = 'Aquí va un texto previo.\n```tree\nroot\n```'
    msg = RichMessage(text)
    renderable = msg.render()
    from rich.console import Group
    from rich.markdown import Markdown
    assert isinstance(renderable, Group)
    # El primer elemento debe ser el Markdown con el texto previo
    assert isinstance(renderable.renderables[0], Markdown)


def test_rich_message_json_dict_not_list():
    """Cubre la línea 59: JSON válido pero que no es lista de dicts."""
    text = '```json\n{"a": 1, "b": 2}\n```'
    msg = RichMessage(text)
    renderable = msg.render()
    from rich.console import Group
    from rich.syntax import Syntax
    assert isinstance(renderable, Group)
    # Debe ser un Syntax (bloque de código resaltado), no una Table
    assert any(isinstance(child, Syntax) for child in renderable.renderables)
