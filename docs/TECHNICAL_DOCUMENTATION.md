# mcp-agent — Documentación Técnica

## 1. Descripción General

**mcp-agent** es un paquete Python que implementa un agente basado en el **Model Context Protocol (MCP)**. El proyecto sigue el estándar PEP 621 para metadatos de proyectos Python y está empaquetado utilizando **Hatchling** como backend de construcción.

El paquete expone una interfaz de línea de comandos (CLI) denominada `mcp-agent`, lo que permite su invocación directa desde la terminal tras la instalación.

---

## 2. Especificaciones del Proyecto

| Campo | Valor |
|-------|-------|
| **Nombre del paquete** | `mcp-agent` |
| **Versión** | `0.1.0` |
| **Descripción** | Model Context Protocol agent |
| **Versión mínima de Python** | `>=3.10` |
| **Estándar de metadatos** | PEP 621 (`pyproject.toml`) |
| **Backend de construcción** | Hatchling |
| **Layout del código fuente** | `src/` (`src/mcp_agent`) |
| **Punto de entrada de consola** | `mcp-agent = "mcp_agent.cli:main"` |

---

## 3. Dependencias de Ejecución

El proyecto declara las siguientes dependencias en la sección `[project]` de `pyproject.toml`:

| Dependencia | Versión mínima | Propósito |
|-------------|----------------|-----------|
| `mcp[cli]` | `>=1.0.0` | SDK del Modelo de Contexto con extras de CLI |
| `pydantic` | `>=2.0.0` | Validación y parseo de datos |
| `pyyaml` | `>=6.0` | Lectura y escritura de archivos YAML |
| `python-dotenv` | `>=1.0.0` | Carga de variables de entorno desde archivos `.env` |

---

## 4. Puntos de Entrada de Consola

Se define un script de consola en la sección `[project.scripts]`:

```
mcp-agent = "mcp_agent.cli:main"
```

Al instalar el paquete, se crea el comando `mcp-agent` en el entorno, el cual ejecuta la función `main` definida en el módulo `mcp_agent.cli`.

---

## 5. Sistema de Construcción

El proyecto utiliza **Hatchling** como backend de compilación, configurado en la sección `[build-system]`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

El objetivo de rueda (`wheel`) está configurado bajo `[tool.hatch.build.targets.wheel]` con el siguiente empaquetado:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/mcp_agent"]
```

Esto indica que el código fuente del paquete Python se encuentra bajo el directorio `src/mcp_agent` (layout `src/`).

---

## 6. Instalación

Para instalar el paquete en modo desarrollo (editable):

```bash
pip install -e .
```

Para instalar el paquete en modo producción:

```bash
pip install .
```

Tras la instalación, el comando `mcp-agent` estará disponible en la PATH del entorno.

---

## 7. Uso de la CLI

Una vez instalado, el paquete expone el siguiente comando:

```bash
mcp-agent
```

Este comando delega la ejecución en la función `main` del módulo `mcp_agent.cli`. Consulte la ayuda integrada para conocer las opciones y subcomandos disponibles:

```bash
mcp-agent --help
```

---

## 8. Requisitos del Entorno

- **Python:** 3.10 o superior.
- **Gestor de paquetes:** `pip` (o compatible con PEP 621 / `pyproject.toml`).
- **Backend de construcción:** Hatchling (instalado automáticamente como requisito de build).

---

## 9. Notas sobre el Ecosistema MCP

El proyecto depende del SDK oficial del **Model Context Protocol (MCP)** (`mcp[cli]`), lo que sugiere que el agente está diseñado para interactuar con servidores y herramientas compatibles con MCP, permitiendo la exposición de capacidades de contexto a modelos de lenguaje u otros consumidores del protocolo.

---

## 10. Historial de Cambios

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 0.1.0 | — | Versión inicial del proyecto |

---

*Documentación generada a partir del análisis del archivo `pyproject.toml` conforme al estándar PEP 621.*
