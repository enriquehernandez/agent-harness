# app/tools/critic.py
from app.core.harness.tool import BaseTool, ToolResult
from app.core.llm.base import BaseLLM


class CriticTool(BaseTool):
    def __init__(self, llm: BaseLLM):
        self.name = "critic_review"
        self.description = "Revisa una respuesta propuesta para detectar errores o violaciones de las reglas del AGENTS.md."
        self.llm = llm
        self.parameters_schema = {
            "type": "object",
            "properties": {
                "proposed_response": {"type": "string"},
                "agent_rules": {"type": "string"}
            },
            "required": ["proposed_response", "agent_rules"]
        }

    async def run(self, proposed_response: str, agent_rules: str) -> ToolResult:
        prompt = (
            "You are a strict Quality Assurance Reviewer for an AI Agent.\n"
            "Your job is to review the agent's proposed response based on the project rules.\n\n"
            f"### PROJECT RULES:\n{agent_rules}\n\n"
            f"### PROPOSED RESPONSE:\n{proposed_response}\n\n"
            "REVIEW INSTRUCTIONS:\n"
            "1. If the user's request is related to software engineering, coding, or modifying files, the response MUST strictly comply with the PROJECT RULES.\n"
            "2. If the user's request is casual (e.g., a joke, a greeting, a general question), DO NOT enforce software engineering rules. Just verify that the response is coherent and follows basic safety.\n\n"
            "If the response is correct and does not violate the logical context, reply EXACTLY with: APPROVED\n"
            "If the response has serious errors, hallucinations, or breaks the rules when it shouldn't, reply EXACTLY with: REJECTED\n"
            "If rejected, on the next line, briefly explain the reason and how to fix it."
        )

        try:
            # Usamos el LLM del crítico para evaluar
            response = await self.llm.chat(messages=[{"role": "user", "content": prompt}])
            content = response.content or ""

            if "APPROVED" in content:
                return ToolResult(success=True, content="APPROVED")
            else:
                return ToolResult(success=True, content=f"REJECTED: {content}")
        except Exception as e:
            return ToolResult(success=False, content="", error=f"Error en el crítico: {e}")
