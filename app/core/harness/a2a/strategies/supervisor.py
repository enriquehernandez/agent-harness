import json
from pathlib import Path
from app.core.harness.a2a.base import A2AStrategy, AgentCard
from app.core.harness.loop import AgentLoop
from app.core.harness.tool import ToolResult
from app.core.harness.context import ContextManager
from app.core.harness.permissions import PermissionGate, Decision
from app.core.logger import logger
from app.core.config import settings


class SupervisorStrategy(A2AStrategy):
    """Estrategia dinámica: un LLM router decide a qué agente delegar."""

    def _load_persisted_permissions(self) -> set[str]:
        """Lee los permisos persistidos de .harness/permissions.json."""
        perm_file = settings.permissions_file
        if not perm_file.exists():
            return set()
        try:
            data = json.loads(perm_file.read_text())
            return set(data.get("session_allowed", []))
        except Exception:
            return set()

    async def execute(self, task: str, context: ContextManager = None) -> ToolResult:
        # 1. Construimos el prompt de enrutamiento
        agents_desc = "\n".join([
            f"- {name}: {card.description}"
            for name, card in self.agents.items()
        ])

        router_prompt = (
            f"Eres un supervisor. Tienes los siguientes agentes disponibles:\n{agents_desc}\n\n"
            f"Tu tarea es: '{task}'\n\n"
            "Responde ÚNICAMENTE con el nombre del agente más adecuado. "
            "Si ninguno es adecuado, responde 'none'."
        )

        # 2. El supervisor (LLM) decide
        ctx = ContextManager(system_prompt=router_prompt)
        ctx.add_user(task)
        decision = await self.llm.chat(messages=ctx.get_messages())

        agent_name = (decision.content or "").strip().lower()
        chosen_agent = self.agents.get(agent_name)

        if not chosen_agent:
            logger.warning(
                f"Supervisor no encontró agente para: '{agent_name}'")
            return ToolResult(success=False, content="", error=f"Agente '{agent_name}' no encontrado.")

        # 3. Delegamos al agente elegido
        logger.info(f"Supervisor delegando a: {chosen_agent.name}")

        # Preparamos el contexto según el modo del agente
        if chosen_agent.mode == "fork" and context:
            agent_ctx = ContextManager(
                system_prompt=chosen_agent.system_prompt)
            agent_ctx.messages = context.messages.copy()
        else:
            agent_ctx = ContextManager(
                system_prompt=chosen_agent.system_prompt)

        # 4. Creamos un PermissionGate específico para el subagente
        #    que lee los permisos persistidos + hereda el ask_user del padre
        sub_gate = PermissionGate(ask_user=self.permissions.ask_user)

        # 🔥 Leemos los permisos persistidos de .harness/permissions.json
        persisted = self._load_persisted_permissions()
        for pattern in persisted:
            sub_gate.session_allowed.add(pattern)

        # 🔥 Heredamos también las políticas del padre
        sub_gate.policies = self.permissions.policies.copy()

        # 5. Ejecutamos el AgentLoop con el sub_gate
        loop = AgentLoop(
            llm=self.llm,
            tools=chosen_agent.tools,
            permissions=sub_gate
        )
        result = await loop.run(task, context=agent_ctx)

        return ToolResult(
            success=True,
            content=f"[Delegado a {chosen_agent.name}]\n{result.final_answer}"
        )
