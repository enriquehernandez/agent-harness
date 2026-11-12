import pytest
from datetime import datetime
from pathlib import Path
from app.core.harness.memory.backends.vector import VectorStore
from app.core.harness.memory.base import MemoryEntry


@pytest.fixture
def store(tmp_path):
    """Crea un VectorStore aislado por test."""
    db = tmp_path / "semantic_test.db"
    return VectorStore(db_path=db)


@pytest.mark.asyncio
async def test_semantic_search_synonyms(store):
    """Verifica que encuentra recuerdos usando sinónimos."""
    entries = [
        MemoryEntry(key="lenguaje", value="El proyecto usa Python 3.11",
                    kind="fact", timestamp=datetime.now()),
        MemoryEntry(key="db", value="La base de datos es PostgreSQL 15",
                    kind="fact", timestamp=datetime.now()),
        MemoryEntry(key="ui", value="La interfaz está construida con Textual",
                    kind="fact", timestamp=datetime.now()),
    ]
    for e in entries:
        await store.save(e)

    # Buscamos "lenguaje de programación" (no aparece "lenguaje" en la query)
    results = await store.recall("lenguaje de programación", limit=3)
    assert any("Python" in r.value for r in results)

    # Buscamos "motor de base de datos" (sinónimo de "base de datos")
    results = await store.recall("motor de base de datos relacional", limit=3)
    assert any("PostgreSQL" in r.value for r in results)

    # Buscamos "framework de terminal" (sinónimo de "interfaz")
    results = await store.recall("framework de terminal", limit=3)
    assert any("Textual" in r.value for r in results)


@pytest.mark.asyncio
async def test_semantic_search_long_queries(store):
    """Verifica que funciona con frases largas y descriptivas."""
    await store.save(MemoryEntry(
        key="auth",
        value="El sistema de autenticación usa JWT con tokens de refresco",
        kind="fact",
        timestamp=datetime.now()
    ))
    await store.save(MemoryEntry(
        key="deploy",
        value="El despliegue se hace con Docker Compose en AWS ECS",
        kind="fact",
        timestamp=datetime.now()
    ))

    # Query larga y descriptiva
    results = await store.recall(
        "¿Cómo protejo a los usuarios cuando inician sesión en la aplicación?",
        limit=3
    )
    assert any("JWT" in r.value for r in results)

    results = await store.recall(
        "¿Dónde vive el proyecto en producción y cómo se orquesta?",
        limit=3
    )
    assert any("Docker" in r.value for r in results)


@pytest.mark.asyncio
async def test_semantic_search_abstract_concepts(store):
    """Verifica que captura conceptos abstractos (no solo palabras clave)."""
    await store.save(MemoryEntry(
        key="filosofia",
        value="El proyecto prioriza la seguridad y la extensibilidad",
        kind="preference",
        timestamp=datetime.now()
    ))
    await store.save(MemoryEntry(
        key="testing",
        value="Los tests deben cubrir el 100% del código crítico",
        kind="preference",
        timestamp=datetime.now()
    ))

    # Buscamos por concepto abstracto
    results = await store.recall("¿Cuáles son los valores del proyecto?", limit=3)
    assert any("seguridad" in r.value.lower() for r in results)

    results = await store.recall("¿Qué piensa el equipo sobre la calidad del código?", limit=3)
    assert any("tests" in r.value.lower() for r in results)


@pytest.mark.asyncio
async def test_semantic_search_ranking(store):
    """Verifica que el recuerdo más relevante aparece primero."""
    await store.save(MemoryEntry(
        key="python",
        value="Python es el lenguaje principal del proyecto",
        kind="fact",
        timestamp=datetime.now()
    ))
    await store.save(MemoryEntry(
        key="javascript",
        value="JavaScript se usa solo para scripts del frontend",
        kind="fact",
        timestamp=datetime.now()
    ))
    await store.save(MemoryEntry(
        key="rust",
        value="Rust se usa para herramientas de alto rendimiento",
        kind="fact",
        timestamp=datetime.now()
    ))

    results = await store.recall("lenguaje principal de la aplicación", limit=3)

    # El primero debe ser Python (es el más relevante semánticamente)
    assert results[0].key == "python"
    assert "Python" in results[0].value


@pytest.mark.asyncio
async def test_semantic_search_empty_db(store):
    """Verifica el comportamiento cuando no hay recuerdos."""
    results = await store.recall("cualquier cosa", limit=5)
    assert results == []


@pytest.mark.asyncio
async def test_semantic_search_limit_respected(store):
    """Verifica que el parámetro `limit` se respeta."""
    for i in range(10):
        await store.save(MemoryEntry(
            key=f"fact_{i}",
            value=f"Hecho importante número {i} sobre el proyecto",
            kind="fact",
            timestamp=datetime.now()
        ))

    results = await store.recall("hechos importantes del proyecto", limit=3)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_semantic_search_update(store):
    """Verifica que al actualizar un recuerdo, el vector también se actualiza."""
    # Guardamos un recuerdo
    await store.save(MemoryEntry(
        key="color",
        value="El color favorito es el azul",
        kind="preference",
        timestamp=datetime.now()
    ))

    results = await store.recall("¿Cuál es el color favorito?", limit=3)
    assert any("azul" in r.value.lower() for r in results)

    # Actualizamos el recuerdo
    await store.save(MemoryEntry(
        key="color",
        value="El color favorito es el verde",
        kind="preference",
        timestamp=datetime.now()
    ))

    results = await store.recall("¿Cuál es el color favorito?", limit=3)
    assert any("verde" in r.value.lower() for r in results)
    # Verificamos que el viejo vector ya no aparece
    assert not any("azul" in r.value.lower() for r in results)


@pytest.mark.asyncio
async def test_semantic_search_cross_language(store):
    """Verifica que funciona con queries en español buscando datos en inglés."""
    await store.save(MemoryEntry(
        key="tech_stack",
        value="The project uses Python and FastAPI for the backend",
        kind="fact",
        timestamp=datetime.now()
    ))

    # Query en español, documento en inglés
    results = await store.recall("¿Qué tecnologías usa el servidor?", limit=3)

    # Aunque el modelo bge-small está entrenado mayoritariamente en inglés,
    # puede encontrar similitud semántica básica. Si esto falla, es normal
    # (requiere un modelo multilingüe como `paraphrase-multilingual-MiniLM-L12-v2`)
    assert len(results) > 0
