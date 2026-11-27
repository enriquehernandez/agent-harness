# 🍳 La Analogía de la Cocina: Entendiendo el Agent Harness

Para entender cómo funciona este proyecto, imagina que el **Harness es una cocina profesional de alto rendimiento**. Cada componente del código tiene un equivalente exacto en el mundo de la gastronomía.

# 🗺️ Mapa Visual: La Cocina del Agent Harness

```mermaid
flowchart TD
    %% Estilos
    classDef agent fill:#f9c74f,stroke:#f9844a,stroke-width:2px,color:#000;
    classDef memory fill:#90be6d,stroke:#43aa8b,stroke-width:2px,color:#000;
    classDef tools fill:#577590,stroke:#4d908e,stroke-width:2px,color:#fff;
    classDef hooks fill:#f94144,stroke:#f3722c,stroke-width:2px,color:#fff;
    classDef checks fill:#277da1,stroke:#4d908e,stroke-width:2px,color:#fff;
    classDef docs fill:#f8961e,stroke:#f9c74f,stroke-width:1px,color:#000,stroke-dasharray: 5 5;
    classDef finance fill:#d90429,stroke:#ef233c,stroke-width:2px,color:#fff;

    %% Nodos Principales
    Chef[("👨‍🍳 El Chef\n(Agente / LLM)")]:::agent

    %% Despensa y Contexto
    subgraph Despensa [🗄️ La Despensa y el Pizarrón - Memoria y Contexto]
        AGENTS[("📜 AGENTS.md\n(Normas de la cocina)")]:::docs
        TASKS[("📝 tasks/actual.md\n(Pizarrón: se consulta si preguntan)")]:::docs
        MEM[("🧠 Memoria a Largo Plazo\n(Recetario de clientes)")]:::memory
        SESS[("📁 Sesiones\n(Historial de comandas)")]:::memory
    end

    %% Herramientas
    subgraph Utensilios [🔪 Los Utensilios - Tools]
        BASH["🛠️ bash"]
        FILES["📁 write_file / read_file"]
        SKILLS["📖 load_skill\n(Libro de recetas)"]
        PREV["🖼️ Vista previa\n(HalfcellImage / TerminalImage)"]
    end
    class Utensilios tools

    %% Hooks y Permisos
    subgraph Seguridad [🛡️ Los Hooks - Seguridad y Automatización]
        PERM{"✋ PermissionGate\n(¿Dejar pasar?)"}:::hooks
        TIMER["⏱️ Hooks de Evento\n(Temporizadores - metáfora)"]:::hooks
    end

    %% Subagentes
    subgraph Equipo [🤝 El Equipo - A2A / Subagentes]
        CRITIC[("🧐 Crítico\n(Auto-reflexión)")]:::agent
        REVIEWER[("🕵️ Sous-Chef\n(Reviewer)")]:::agent
        A2A[("🏃 Ayudantes\n(A2A)")]:::agent
    end

    %% Validación y Costos
    subgraph Calidad [🧪 Control de Calidad]
        TESTS[("📋 checks/tests.md\n(Prueba de sabor)")]:::checks
        COST[("💰 PricingProvider\n(La cuenta del restaurante)")]:::finance
    end

    %% Conexiones
    AGENTS -. "Inyectado al inicio" .-> Chef
    TASKS -. "Inyectado al inicio" .-> Chef
    SESS <-->|Guardar / Cargar| Chef
    MEM <-->|memory_save / recall| Chef
    
    Chef -->|Quiere usar| Utensilios
    Utensilios -->|Interceptado por| PERM
    PERM -->|Aprobado| Utensilios
    
    Chef -->|delegate| Equipo
    Equipo -->|Devuelve feedback| Chef
    Chef -->|Antes de servir: REJECTED ⚠️| CRITIC
    CRITIC -->|Feedback al chef| Chef
    
    Chef -->|Al terminar| Calidad
    Calidad -->|Si pasa| Entrega((🍽️ Plato Terminado))
    Calidad -->|Si falla| Chef
    Chef -. "Cada uso cuesta $" .-> COST
```


## 🧑‍🍳 El Equipo de Cocina (Los Agentes)

*   **El Chef Principal (El Agente / LLM):** Es el cerebro. Toma las decisiones, lee las órdenes, decide qué cocinar y en qué orden. No sabe todo de memoria, pero sabe cómo buscar y usar lo que tiene.
*   **El Crítico (Auto-reflexión):** Antes de servir, prueba el plato contra las normas cargadas al arranque (`AGENTS.md` y `tasks/actual.md`). Si dice `REJECTED: …`, el chef vuelve a intentarlo (máx. 2 veces) y en el chat aparece `⚠️ Corrección aplicada: …`; la TUI redibuja el Markdown con la respuesta corregida. Usa el modelo de `A2A_REVIEWER_MODEL` si está configurado.
*   **El Sous-Chef (Subagente Reviewer):** El chef principal le pasa un plato y le dice: *"Prueba esto y dime si le falta sal"*. Es tu herramienta `delegate_to_reviewer`.
*   **Los Ayudantes (Sistema A2A - Agent-to-Agent):** Cuando hay mucho trabajo, el chef delega. *"Tú pela las papas, tú corta la cebolla"*. Dependiendo de la estrategia (`sequential`, `parallel`, `swarm`), los ayudantes trabajan en línea o al mismo tiempo.

## 🏗️ La Infraestructura (El Entorno)

*   **La Cocina (El Harness):** La infraestructura física. Los fogones (el motor del LLM), la despensa (la base de datos) y el espacio de trabajo.
*   **Los Utensilios (Las Tools):** Cuchillos, licuadoras, hornos. Son las herramientas (`bash`, `write_file`, `read_file`). El chef las usa para manipular los ingredientes. No puede cocinar sin ellas.
*   **La Vitrina (Vista previa de imágenes):** Al pegar una imagen, la TUI la muestra con `HalfcellImage` si `TERM_PROGRAM=WarpTerminal` y con `TerminalImage` en los demás terminales; el archivo se envía al modelo en Base64 (`image/png` para PNG, `image/jpeg` para el resto).
*   **Las Comandas Guardadas (Las Sesiones / `SessionManager`):** Cada vez que el restaurante cierra, se guardan las comandas en un libro (archivos JSON en `.harness/sessions/`). Al día siguiente, el chef lee la última comanda y sabe exactamente en qué mesa se quedó trabajando. El libro solo acepta nombres de comanda simples, sin rutas; una comanda ilegible cuenta como vacía y las notas de sistema escritas en el libro nunca sustituyen las reglas que el chef ya trae en la mesa.

## 📖 Las Instrucciones (La Información)

*   **Las Recetas (Los Skills / `.md`):** El chef no memoriza cómo hacer un Soufflé. Cuando le piden uno, lee la receta (`load_skill` o `@nombre-skill`) y ejecuta los pasos exactos.
*   **La Despensa y el Pizarrón:** 
    *   `AGENTS.md`: Las normas de la cocina ("Los cuchillos se afilan así").
    *   `tasks/actual.md`: El pizarrón de tareas; se inyecta en el system prompt junto con `AGENTS.md` y la memoria, pero el chef no lo menciona ni reanuda salvo que el cliente pregunte por el estado.
    *   **Memoria:** El recetario de gustos de los clientes (ej. "El cliente 1 prefiere la carne sin sal"). Por defecto es SQLite en `.harness/memory.db`, **no** `summary.md` (ese archivo solo aparece con el backend `files`).
    *   `docs/` y `checks/`: No se inyectan en el prompt; están en la despensa para consultarlos con herramientas cuando hacen falta.

## 🛡️ Los Hooks: El "Chef Supervisor" (metáfora)

En una cocina real, no basta con que el chef sepa usar los utensilios; necesitas a alguien (o algo) que supervise, automatice y ponga límites. **Los "Hooks" son una metáfora de ese "Chef Supervisor" invisible: no existe un subsistema de hooks en el código.**

*   **El Temporizador (Hooks de Evento — metáfora):** *"A los 20 minutos, haz sonar la campana para sacarlo"* es solo una forma de describir reacciones automáticas. No hay un registro de hooks: en el código solo hay enganches puntuales, como el colector de eventos del `logger` (`DebugEventCollector`, que alimenta el panel F1).
*   **La Regla de Seguridad (Hook de Intercepción - PermissionGate):** Si el chef intenta meter la mano en el horno a 200°C, el supervisor lo detiene y deja la petición en la cola con un número de ticket y el nombre del turno: *"¡Alto! Necesito autorización de la gerencia (el humano) para abrir el horno"* (`/permissions reply <ticket> once|always|reject`). No se limita a `bash` o `write_file`: también cubre lecturas y listados (`read_file`, `read_text_file`, `list_dir`, `list_directory`, `edit_file`); responder `always` guarda la firma y auto-aprueba esa acción en el futuro, mientras que `reject` cierra los tickets pendientes de ese mismo turno.
*   **La Preparación Previa (sin atajos ocultos):** El chef pone en la mesa los ingredientes exactos y el horno recibe esa misma orden: `BashTool` ejecuta el comando aprobado sin inyectar `--tools observations.json`. Si hace falta el inventario, el modelo pide `export_observations` como tool independiente y esa escritura pasa por el `PermissionGate`.

## 💰 El Dueño del Restaurante (Los Costos / PricingProvider)

Cocinar no es gratis. Cada vez que el chef usa un ingrediente importado (un LLM caro), gasta dinero. 
El `PricingProvider` es el **Dueño del Restaurante**. Lleva la cuenta exacta de cuánto cuesta cada plato (tokens de entrada y salida). Si el chef usa un modelo muy caro (como GPT-4o) o un modelo barato (como Groq), el dueño sabe exactamente cuánto descontar de la caja registradora (`/cost`). Langfuse es el cuaderno donde también se apuntan usage y coste de cada generación.

## 🛡️ El Control de Calidad

*   **Las Normas de Sanidad (Los Checks / Tests):** El chef no puede decir "Plato terminado" si no ha pasado por la prueba de sabor (tests unitarios). Si la comida no cumple con el estándar de calidad (`checks/tests.md` y el informe de cobertura del 100%), se tira a la basura y se vuelve a empezar.

---

## 💡 ¿Cómo usar esta analogía al desarrollar?

Cuando algo falle en el Harness, pregúntate:
1.  *¿El chef está leyendo la receta equivocada?* ➡️ Problema de Skill.
2.  *¿El chef no tiene el cuchillo adecuado?* ➡️ Problema de Tool/Registry.
3.  *¿El supervisor se quedó dormido y no frenó al chef?* ➡️ Problema de PermissionGate (no de un subsistema de hooks).
4.  *¿La cocina está tan llena de humo que el chef no ve?* ➡️ Problema de ventana de contexto (Demasiados tokens).
5.  *¿Nos quedamos sin presupuesto a mitad del servicio?* ➡️ Problema de Pricing/Token usage.
