import json
from datetime import datetime
from pathlib import Path
from app.core.config import settings
from app.core.harness.context import ContextManager


class SessionManager:
    """Gestiona el guardado y carga de sesiones en .harness/sessions/."""

    def __init__(self, session_id: str | None = None):
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_file = settings.sessions_dir / f"{self.session_id}.json"

    def save(self, ctx: ContextManager, agent_loop=None) -> None:
        """Guarda el historial de la conversación."""
        settings.sessions_dir.mkdir(parents=True, exist_ok=True)

        # Limpiamos mensajes con contenido vacío o tool_calls vacíos
        messages = []
        for msg in ctx.get_messages():
            if msg.get("content") or msg.get("tool_calls"):
                messages.append(msg)

        data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "message_count": len(messages),
            "messages": messages
        }

        # 🔥 Guardamos los contadores de reparación si existen
        if agent_loop and hasattr(agent_loop, "repair_counts"):
            data["repair_counts"] = agent_loop.repair_counts

        self.session_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return str(self.session_file)

    def load_metadata(self) -> dict:
        """Carga los metadatos de la sesión (incluyendo repair_counts)."""
        if not self.session_file.exists():
            return {}
        try:
            data = json.loads(self.session_file.read_text(encoding="utf-8"))
            return data
        except Exception:
            return {}

    def load(self) -> list[dict]:
        """Carga el historial de la conversación."""
        if not self.session_file.exists():
            return []
        data = json.loads(self.session_file.read_text(encoding="utf-8"))
        return data.get("messages", [])

    @staticmethod
    def list_sessions() -> list[dict]:
        """Lista todas las sesiones guardadas con su metadata."""
        sessions = []
        for f in sorted(settings.sessions_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sessions.append({
                    "id": f.stem,
                    "timestamp": data.get("timestamp", ""),
                    "message_count": data.get("message_count", 0),
                })
            except Exception:
                pass
        return sessions

    @staticmethod
    def delete_session(session_id: str) -> bool:
        """Elimina una sesión guardada."""
        session_file = settings.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            return True
        return False
