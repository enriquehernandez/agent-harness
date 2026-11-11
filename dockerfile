# Usamos una imagen base ligera de Python
FROM python:3.11-slim-bookworm

# Instalamos Node.js (necesario para MCP de npx) y dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Instalamos uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Directorio de trabajo
WORKDIR /app

# Copiamos solo los archivos de dependencias para aprovechar el cache de Docker
COPY pyproject.toml uv.lock ./

# Instalamos dependencias con uv
RUN uv sync --no-dev

# Copiamos el resto del código
COPY . .

# Exponemos un puerto (por si luego usas la API)
EXPOSE 8000

# Comando por defecto: iniciar la TUI
# Nota: La TUI necesita una terminal interactiva (-it) en docker run
CMD ["uv", "run", "python", "-m", "app.main"]