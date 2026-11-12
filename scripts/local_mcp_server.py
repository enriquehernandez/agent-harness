from mcp.server.mcpserver import MCPServer
import platform
import sys
import subprocess
import os

mcp = MCPServer("LocalDevServer")


@mcp.tool()
def get_system_info() -> str:
    """Devuelve información sobre el sistema operativo actual (OS, Python, CPU)."""
    return f"OS: {platform.system()} {platform.release()}\nPython: {sys.version}\nArquitectura: {platform.machine()}"


@mcp.tool()
def run_tests() -> str:
    """Ejecuta la suite de tests del proyecto (pytest) y devuelve el resultado o los errores."""
    if os.environ.get("HARNESS_E2E") == "1":
        return "⏭️ run_tests saltado en modo E2E (HARNESS_E2E=1)."
    try:
        # 🔥 Añadimos --ignore=tests/integration para evitar el bucle infinito
        result = subprocess.run(
            ["uv", "run", "pytest", "tests/", "-q", "--ignore=tests/integration"],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return f"✅ Todos los tests pasaron con éxito.\n\n{result.stdout}"
        else:
            return f"❌ Hubo fallos en los tests:\n\n{result.stdout}\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "⚠️ El comando de tests excedió el tiempo límite de 60 segundos."
    except Exception as e:
        return f"Error ejecutando los tests: {str(e)}"


@mcp.tool()
def analyze_code_complexity(file_path: str) -> str:
    """Analiza la complejidad de un archivo Python (número de líneas, funciones y clases)."""
    if not os.path.exists(file_path):
        return f"El archivo {file_path} no existe."

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    num_lines = len(lines)
    num_functions = sum(1 for line in lines if line.strip().startswith(
        "def ") or line.strip().startswith("async def "))
    num_classes = sum(1 for line in lines if line.strip().startswith("class "))

    return f"📊 Análisis de `{file_path}`:\n- Líneas totales: {num_lines}\n- Funciones: {num_functions}\n- Clases: {num_classes}"


@mcp.tool()
def echo_message(message: str) -> str:
    """Hace eco de un mensaje. Útil para probar la conexión."""
    return f"El servidor local_dev dice: {message}"


if __name__ == "__main__":
    mcp.run()
