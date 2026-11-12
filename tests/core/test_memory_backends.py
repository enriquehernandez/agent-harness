import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.tools.memory import MemorySaveTool, MemoryRecallTool
from app.core.harness.memory.base import MemoryEntry

from app.core.harness.memory.base import MemoryEntry
from app.core.harness.memory.backends.sqlite import SQLiteStore
from app.core.harness.memory.backends.session_files import SessionFilesStore
from app.core.harness.memory.backends.in_memory import InMemoryRingStore
from app.core.harness.memory.backends.fanout import FanoutStore


@pytest.fixture
def sample_entries():
    return [
        MemoryEntry(key="test1", value="Hello world",
                    timestamp=datetime.now(), kind="fact"),
        MemoryEntry(key="test2", value="Python is great",
                    timestamp=datetime.now(), kind="fact"),
    ]


# ==========================================
# SQLITE STORE
# ==========================================

@pytest.mark.asyncio
async def test_sqlite_store(tmp_path):
    store = SQLiteStore(db_path=str(tmp_path / "test.db"))
    entry = MemoryEntry(key="test", value="Hello world",
                        timestamp=datetime.now())
    await store.save(entry)

    results = await store.recall("Hello")
    assert len(results) == 1
    assert results[0].key == "test"

    preamble = store.preamble()
    assert "test" in preamble

    await store.clear()
    assert len(await store.recall("Hello")) == 0


# ==========================================
# SESSION FILES STORE
# ==========================================

@pytest.mark.asyncio
async def test_session_files_store(tmp_path):
    store = SessionFilesStore(base_dir=tmp_path)
    entry = MemoryEntry(key="test", value="Hello world",
                        timestamp=datetime.now())
    await store.save(entry)

    # Verificamos que se creó el archivo
    assert (tmp_path / "test.md").exists()
    assert (tmp_path / "summary.md").exists()

    results = await store.recall("Hello")
    assert len(results) == 1
    assert results[0].key == "test"

    preamble = store.preamble()
    assert "test" in preamble

    await store.clear()
    assert len(await store.recall("Hello")) == 0


# ==========================================
# IN MEMORY STORE
# ==========================================

@pytest.mark.asyncio
async def test_in_memory_store():
    store = InMemoryRingStore(capacity=3)

    # Guardamos 4 entradas (el ring buffer solo mantiene 3)
    for i in range(4):
        entry = MemoryEntry(
            key=f"test{i}", value=f"Value {i}", timestamp=datetime.now())
        await store.save(entry)

    # Verificamos que solo hay 3
    all_entries = await store.get_all()
    assert len(all_entries) == 3

    results = await store.recall("Value")
    assert len(results) <= 3

    preamble = store.preamble()
    assert "Value" in preamble

    await store.clear()
    assert len(await store.get_all()) == 0


# ==========================================
# FANOUT STORE
# ==========================================

@pytest.mark.asyncio
async def test_fanout_store(tmp_path):
    # Creamos dos stores
    sqlite_store = SQLiteStore(db_path=str(tmp_path / "test.db"))
    files_store = SessionFilesStore(base_dir=tmp_path / "files")

    # Los combinamos
    fanout = FanoutStore(primary=sqlite_store, secondary=files_store)

    entry = MemoryEntry(key="test", value="Hello world",
                        timestamp=datetime.now())
    await fanout.save(entry)

    # Verificamos que se guardó en ambos
    assert len(await sqlite_store.recall("Hello")) == 1
    assert len(await files_store.recall("Hello")) == 1

    # Verificamos que el preamble funciona
    preamble = fanout.preamble()
    assert "test" in preamble

    # Limpiamos
    await fanout.clear()
    assert len(await sqlite_store.recall("Hello")) == 0
    assert len(await files_store.recall("Hello")) == 0


# ==========================================
# FACTORY
# ==========================================

def test_memory_factory():
    from app.core.harness.memory.factory import create_memory_store

    # SQLite
    store = create_memory_store("sqlite")
    assert isinstance(store, SQLiteStore)

    # Files
    store = create_memory_store("files")
    assert isinstance(store, SessionFilesStore)

    # Memory
    store = create_memory_store("memory")
    assert isinstance(store, InMemoryRingStore)

    # Desconocido
    with pytest.raises(ValueError, match="Backend desconocido"):
        create_memory_store("unknown")


def test_fanout_initialization():
    from app.core.harness.memory.backends.fanout import FanoutStore
    from app.core.harness.memory.backends.sqlite import SQLiteStore
    from app.core.harness.memory.backends.session_files import SessionFilesStore

    store = FanoutStore(primary=SQLiteStore(), secondary=SessionFilesStore())
    assert store.primary is not None
    assert store.secondary is not None


@pytest.mark.asyncio
async def test_in_memory_preamble_empty():
    from app.core.harness.memory.backends.in_memory import InMemoryRingStore
    store = InMemoryRingStore()
    assert store.preamble() == ""


@pytest.mark.asyncio
async def test_session_files_get_all(tmp_path):
    from app.core.harness.memory.backends.session_files import SessionFilesStore
    store = SessionFilesStore(base_dir=tmp_path)

    # Guardamos varias entradas
    await store.save(MemoryEntry(key="a", value="1", timestamp=datetime.now()))
    await store.save(MemoryEntry(key="b", value="2", timestamp=datetime.now()))

    all_entries = await store.get_all()
    assert len(all_entries) == 2


@pytest.mark.asyncio
async def test_sqlite_get_all(tmp_path):
    from app.core.harness.memory.backends.sqlite import SQLiteStore
    store = SQLiteStore(db_path=str(tmp_path / "test.db"))

    await store.save(MemoryEntry(key="a", value="1", timestamp=datetime.now()))
    await store.save(MemoryEntry(key="b", value="2", timestamp=datetime.now()))

    all_entries = await store.get_all()
    assert len(all_entries) == 2


def test_factory_unknown():
    from app.core.harness.memory.factory import create_memory_store
    with pytest.raises(ValueError, match="Backend desconocido"):
        create_memory_store("unknown")


@pytest.mark.asyncio
async def test_memory_save_tool():
    """Cubre MemorySaveTool."""
    mock_store = MagicMock()
    mock_store.save = AsyncMock()

    tool = MemorySaveTool(store=mock_store)
    result = await tool.run(key="test", value="Hello world")

    assert result.success is True
    assert "Memory saved" in result.content
    mock_store.save.assert_called_once()


@pytest.mark.asyncio
async def test_memory_recall_tool_empty():
    """Cubre MemoryRecallTool sin resultados."""
    mock_store = MagicMock()
    mock_store.recall = AsyncMock(return_value=[])

    tool = MemoryRecallTool(store=mock_store)
    result = await tool.run(query="test")

    assert result.success is True
    assert "No memories found" in result.content


@pytest.mark.asyncio
async def test_memory_recall_tool_with_results():
    """Cubre MemoryRecallTool con resultados."""
    mock_store = MagicMock()
    mock_store.recall = AsyncMock(return_value=[
        MemoryEntry(key="test", value="Hello world", timestamp=datetime.now())
    ])

    tool = MemoryRecallTool(store=mock_store)
    result = await tool.run(query="test")

    assert result.success is True
    assert "Memories found" in result.content
    assert "Hello world" in result.content


@pytest.mark.asyncio
async def test_memory_save_tool_error():
    """Cubre el except de MemorySaveTool."""
    mock_store = MagicMock()
    mock_store.save = AsyncMock(side_effect=Exception("Save error"))

    tool = MemorySaveTool(store=mock_store)
    result = await tool.run(key="test", value="Hello")

    assert result.success is False
    assert "Save error" in result.error


@pytest.mark.asyncio
async def test_memory_recall_tool_error():
    """Cubre el except de MemoryRecallTool."""
    mock_store = MagicMock()
    mock_store.recall = AsyncMock(side_effect=Exception("Recall error"))

    tool = MemoryRecallTool(store=mock_store)
    result = await tool.run(query="test")

    assert result.success is False
    assert "Recall error" in result.error


@pytest.mark.asyncio
async def test_fanout_recall_and_get_all(tmp_path):
    from app.core.harness.memory.backends.fanout import FanoutStore
    from app.core.harness.memory.backends.sqlite import SQLiteStore
    from app.core.harness.memory.backends.session_files import SessionFilesStore
    from app.core.harness.memory.base import MemoryEntry
    from datetime import datetime

    sqlite = SQLiteStore(db_path=str(tmp_path / "test.db"))
    files = SessionFilesStore(base_dir=tmp_path / "files")
    fanout = FanoutStore(primary=sqlite, secondary=files)

    entry = MemoryEntry(key="test", value="Hello", timestamp=datetime.now())
    await fanout.save(entry)

    # Cubre recall
    results = await fanout.recall("Hello")
    assert len(results) == 1

    # Cubre get_all
    all_entries = await fanout.get_all()
    assert len(all_entries) == 1


@pytest.mark.asyncio
async def test_session_files_edge_cases(tmp_path):
    from app.core.harness.memory.backends.session_files import SessionFilesStore
    from app.core.harness.memory.base import MemoryEntry
    from datetime import datetime

    store = SessionFilesStore(base_dir=tmp_path)

    # Cubre preamble sin summary (línea 43)
    assert store.preamble() == ""

    # Cubre break del recall (línea 36)
    for i in range(10):
        await store.save(MemoryEntry(key=f"key{i}", value=f"Value {i}", timestamp=datetime.now()))

    results = await store.recall("Value", limit=1)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_sqlite_preamble_empty(tmp_path):
    from app.core.harness.memory.backends.sqlite import SQLiteStore
    store = SQLiteStore(db_path=str(tmp_path / "test.db"))
    assert store.preamble() == ""


def test_factory_fanout():
    from app.core.harness.memory.factory import create_memory_store
    from app.core.harness.memory.backends.fanout import FanoutStore
    store = create_memory_store("fanout")
    assert isinstance(store, FanoutStore)
