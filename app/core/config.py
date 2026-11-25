from datetime import datetime
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM
    LLM_PROVIDER: str = "fake"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "openai/gpt-4o"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Seguridad
    LOG_LEVEL: str = "INFO"
    ENABLE_PROMPT_CACHING: bool = True

    # LangFuse
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = ""

    # LIMITS
    MAX_DOCUMENT_CHARS: int = 15000

    # 🔥 MEMORIA
    MEMORY_BACKEND: str = "sqlite"  # sqlite | files | memory | fanout

    # 🔥 TIMEOUTS (Nuevos)
    LLM_STREAM_TIMEOUT: float = 300.0
    TOOL_TIMEOUT: float = 30.0
    MCP_CONNECT_TIMEOUT: float = 10.0

    # 🔥 RUTAS CENTRALIZADAS
    DATA_DIR: Path = Path(".harness")

    @property
    def memory_db(self) -> Path:
        return self.DATA_DIR / "memory.db"

    @property
    def vector_db(self) -> Path:
        return self.DATA_DIR / "vector.db"

    @property
    def memory_files_dir(self) -> Path:
        return self.DATA_DIR / "memory"

    @property
    def permissions_file(self) -> Path:
        return self.DATA_DIR / "permissions.json"

    @property
    def hooks_file(self) -> Path:
        return self.DATA_DIR / "hooks.json"

    @property
    def logs_dir(self) -> Path:
        return self.DATA_DIR / "logs"

    @property
    def log_file(self) -> Path:
        """Archivo de log del día actual: `yyyy_MM_dd_harness.log`."""
        return self.logs_dir / f"{datetime.now():%Y_%m_%d}_harness.log"

    @property
    def sessions_dir(self) -> Path:
        return self.DATA_DIR / "sessions"

    # Pricing
    PRICING_CACHE_TTL_DAYS: int = 1
    PRICING_CONFIG_FILE: str = "pricing_config.json"

    @property
    def pricing_cache_file(self) -> Path:
        return self.DATA_DIR / "pricing_cache.json"

    @property
    def pricing_config_path(self) -> Path:
        return Path(self.PRICING_CONFIG_FILE)

    # A2A (Agent-to-Agent)
    A2A_STRATEGY: str = "supervisor"  # supervisor | sequential | parallel | swarm
    A2A_SEQUENCE: str = "analyst,writer,reviewer"  # Solo si strategy=sequential
    A2A_PARALLEL_AGENTS: str = "analyst,reviewer"  # Para estrategia parallel
    A2A_SWARM_START: str = "analyst"  # Para estrategia swarm

    # Modelos por agente A2A (opcionales, si se dejan vacíos usan el modelo por defecto)
    A2A_ANALYST_MODEL: str = ""
    A2A_WRITER_MODEL: str = ""
    A2A_REVIEWER_MODEL: str = ""

    def ensure_dirs(self):
        """Crea los directorios necesarios al iniciar."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.memory_files_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
settings.ensure_dirs()
