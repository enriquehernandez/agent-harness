import json
from pathlib import Path
from app.core.harness.tool import BaseTool, ToolResult


class LoadSkillTool(BaseTool):
    def __init__(self, registry=None):
        self.name = "load_skill"
        self.description = (
            "Carga las instrucciones de una 'skill' (habilidad) específica. "
            "Úsalo cuando necesites un manual de instrucciones detallado."
        )
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "El nombre de la skill a cargar (ej. 'improve-codebase-architecture')."
                }
            },
            "required": ["skill_name"]
        }
        self.skills_dir = Path(".agents/skills")
        self.registry = registry  # 🔥 Referencia al ToolRegistry

    def discover_skills(self) -> list[str]:
        if not self.skills_dir.exists():
            return []
        return sorted([
            d.name for d in self.skills_dir.iterdir()
            if d.is_dir() and (d / "SKILL.md").exists()
        ])

    async def run(self, skill_name: str) -> ToolResult:
        skill_path = self.skills_dir / skill_name / "SKILL.md"

        if not skill_path.exists():
            return ToolResult(
                success=False,
                content="",
                error=f"Skill '{skill_name}' no encontrada. Disponibles: {', '.join(self.discover_skills())}"
            )

        try:
            content = skill_path.read_text(encoding="utf-8")
            skill_base_dir = self.skills_dir / skill_name
            return ToolResult(
                success=True,
                content=(
                    f"### 📖 Instrucciones de la skill '{skill_name}':\n\n"
                    f"**IMPORTANTE**: Los archivos de esta skill (scripts, references, etc.) "
                    f"están en la ruta: `{skill_base_dir}`. "
                    f"Cuando la skill mencione un archivo (ej. 'references/capture_snapshot.py'), "
                    f"debes usar la ruta completa: `{skill_base_dir}/references/capture_snapshot.py`.\n\n"
                    f"{content}"
                )
            )
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
