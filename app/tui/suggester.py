from pathlib import Path
from textual.suggester import Suggester, SuggestFromList


class SkillSuggester(Suggester):
    """Sugiere skills instaladas cuando el usuario escribe '@'."""

    def __init__(self, skills_dir: str = ".agents/skills"):
        super().__init__(case_sensitive=False)
        self.skills_dir = Path(skills_dir)
        self._skills = self._load_skills()

    def _load_skills(self) -> list[str]:
        if not self.skills_dir.exists():
            return []

        skills = []
        for d in self.skills_dir.iterdir():
            if d.is_dir() and (d / "SKILL.md").exists():
                skills.append(f"@{d.name}")
        return sorted(skills)

    async def get_suggestion(self, value: str) -> str | None:
        if not value.startswith("@"):
            return None

        if value == "@":
            return self._skills[0] if self._skills else None

        for skill in self._skills:
            if skill.startswith(value):
                return skill

        return None


class CombinedSuggester(Suggester):
    """Combina el autocompletado de comandos (/) y de skills (@)."""

    def __init__(self, commands: list[str]):
        super().__init__(case_sensitive=False)
        self.cmd_suggester = SuggestFromList(commands, case_sensitive=False)
        self.skill_suggester = SkillSuggester()

    async def get_suggestion(self, value: str) -> str | None:
        if value.startswith("@"):
            return await self.skill_suggester.get_suggestion(value)
        if value.startswith("/"):
            return await self.cmd_suggester.get_suggestion(value)
        return None
