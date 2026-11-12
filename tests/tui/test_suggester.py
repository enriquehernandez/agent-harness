from unittest.mock import AsyncMock

import pytest
from app.tui.suggester import SkillSuggester, CombinedSuggester


@pytest.mark.asyncio
async def test_skill_suggester_empty(tmp_path):
    """Cubre el caso de no skills."""
    dir = tmp_path / "skills"
    dir.mkdir()
    suggester = SkillSuggester(skills_dir=str(dir))
    assert await suggester.get_suggestion("@") is None


@pytest.mark.asyncio
async def test_skill_suggester_logic(tmp_path):
    """Cubre la lógica de búsqueda de skills."""
    dir = tmp_path / "skills"
    skill_dir = dir / "test_skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("")

    suggester = SkillSuggester(skills_dir=str(dir))

    # Valor sin @
    assert await suggester.get_suggestion("algo") is None
    # Valor exactamente @
    assert await suggester.get_suggestion("@") == "@test_skill"
    # Valor parcial
    assert await suggester.get_suggestion("@te") == "@test_skill"
    # Valor que no coincide
    assert await suggester.get_suggestion("@xyz") is None


@pytest.mark.asyncio
async def test_combined_suggester():
    """Cubre la combinación de comandos y skills."""
    suggester = CombinedSuggester(["/help", "/quit"])

    # Comandos
    assert await suggester.get_suggestion("/h") == "/help"
    # Skills (delegado)
    with pytest.MonkeyPatch.context() as m:
        m.setattr(suggester.skill_suggester, "get_suggestion",
                  AsyncMock(return_value="@skill"))
        assert await suggester.get_suggestion("@s") == "@skill"
    # Nada
    assert await suggester.get_suggestion("algo") is None


def test_skill_suggester_dir_not_exists():
    """Cubre la línea 15 de suggester.py: retorno temprano si no existe la carpeta."""
    suggester = SkillSuggester(skills_dir="/ruta/inventada/123")
    assert suggester._skills == []
