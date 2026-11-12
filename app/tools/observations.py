import json
from pathlib import Path
from app.core.harness.tool import BaseTool, ToolResult


class ExportObservationsTool(BaseTool):
    def __init__(self, registry, mcp_clients):
        self.name = "export_observations"
        self.description = (
            "Exporta el inventario de tools, skills y MCP servers del agente a un archivo JSON."
        )
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "out_path": {
                    "type": "string",
                    "description": "Ruta donde guardar el JSON (por defecto 'observations.json')."
                }
            }
        }
        self.registry = registry
        self.mcp_clients = mcp_clients

    async def run(self, out_path: str = "observations.json") -> ToolResult:
        try:
            tools = []
            for name in self.registry.names():
                tool = self.registry.get(name)
                tools.append({
                    "name": name,
                    "description": tool.description,
                    "origin": "MCP" if "[MCP]" in tool.description else "Local"
                })

            skills = []
            skills_dir = Path(".agents/skills")
            if skills_dir.exists():
                for d in skills_dir.iterdir():
                    if d.is_dir() and (d / "SKILL.md").exists():
                        skills.append({"name": d.name})

            mcp_servers = []
            for client in self.mcp_clients:
                mcp_servers.append({"name": client.server_params.command})

            data = {
                "tools": tools,
                "skills": skills,
                "mcp_servers": mcp_servers
            }

            Path(out_path).write_text(json.dumps(
                data, indent=2, ensure_ascii=False), encoding="utf-8")
            return ToolResult(success=True, content=f"✅ Observaciones exportadas a `{out_path}`.")
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
