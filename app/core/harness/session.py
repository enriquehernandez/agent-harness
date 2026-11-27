import json
import re
from datetime import datetime
from pathlib import Path
from app.core.config import settings
from app.core.harness.context import ContextManager

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _validate_session_id(session_id: str) -> None:
    """Un ID de sesión es un nombre de archivo plano, nunca una ruta."""
    if not isinstance(session_id, str) or not _SESSION_ID_RE.fullmatch(session_id):
        raise ValueError(f"ID de sesión no válido: {session_id!r}")


def merge_session_history(current_messages: list[dict],
                          loaded_messages: list[dict]) -> list[dict]:
    """Conserva el `system` vigente al restaurar un historial guardado.

    El archivo de sesión nunca puede aportar instrucciones de sistema: solo
    sobreviven los mensajes `system` que ya estaban en el contexto actual.
    """
    system = [
        msg for msg in current_messages
        if isinstance(msg, dict) and msg.get("role") == "system"
    ]
    history = [
        msg for msg in loaded_messages
        if isinstance(msg, dict) and msg.get("role") != "system"
    ]
    return system + history


class SessionManager:
    """Gestiona el guardado y carga de sesiones en .harness/sessions/."""

    def __init__(self, session_id: str | None = None):
        session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        _validate_session_id(session_id)
        self.session_id = session_id
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
        """Carga el historial, sin mensajes `system` y tolerando JSON corrupto."""
        if not self.session_file.exists():
            return []
        try:
            data = json.loads(self.session_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        messages = data.get("messages", []) if isinstance(data, dict) else []
        return [msg for msg in messages
                if isinstance(msg, dict) and msg.get("role") != "system"]

    @classmethod
    def new(cls) -> "SessionManager":
        """Crea una nueva sesión y guarda su JSON inicial en disco."""
        instance = cls()
        data = {
            "session_id": instance.session_id,
            "timestamp": datetime.now().isoformat(),
            "message_count": 0,
            "messages": []
        }
        instance.session_file.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return instance

    @staticmethod
    def list_sessions() -> list[dict]:
        """Lista todas las sesiones guardadas con su metadata."""
        sessions = []
        for f in sorted(settings.sessions_dir.glob("*.json"), reverse=True):
            try:
                _validate_session_id(f.stem)
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
        """Elimina una sesión guardada, nunca una ruta arbitraria."""
        try:
            _validate_session_id(session_id)
        except ValueError:
            return False
        session_file = settings.sessions_dir / f"{session_id}.json"
        if session_file.exists():
            session_file.unlink()
            return True
        return False
