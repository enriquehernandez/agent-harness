import json
from unittest.mock import patch, mock_open
from pathlib import Path
from unittest.mock import patch

import pytest
from app.core.harness.permissions import PermissionGate, Decision


@pytest.fixture(autouse=True)
def clean_permissions_file():
    path = Path(".harness_permissions.json")
    if path.exists():
        path.unlink()
    yield
    if path.exists():
        path.unlink()


@pytest.mark.asyncio
async def test_permission_gate_allow():
    gate = PermissionGate()
    gate.policies = {"safe_tool": Decision.ALLOW}
    decision = await gate.check("safe_tool", {})
    assert decision == Decision.ALLOW


@pytest.mark.asyncio
async def test_permission_gate_deny():
    gate = PermissionGate()
    gate.policies = {"bad_tool": Decision.DENY}
    decision = await gate.check("bad_tool", {})
    assert decision == Decision.DENY


@pytest.mark.asyncio
async def test_permission_gate_ask_deny_no_ui():
    gate = PermissionGate()
    gate.policies = {"danger_tool": Decision.ASK}
    decision = await gate.check("danger_tool", {})
    assert decision == Decision.DENY


@pytest.mark.asyncio
async def test_permission_gate_ask_user_yes():
    async def mock_ask_user(tool, signature, args, diff_text):
        return "y"

    gate = PermissionGate(ask_user=mock_ask_user)
    gate.policies = {"danger_tool": Decision.ASK}
    decision = await gate.check("danger_tool", {})
    assert decision == Decision.ALLOW


@pytest.mark.asyncio
async def test_permission_gate_ask_user_always():
    async def mock_ask_user(tool, signature, args, diff_text):
        return "a"

    gate = PermissionGate(ask_user=mock_ask_user)
    gate.policies = {"danger_tool": Decision.ASK}

    decision1 = await gate.check("danger_tool", {})
    assert decision1 == Decision.ALLOW

    decision2 = await gate.check("danger_tool", {})
    assert decision2 == Decision.ALLOW
    assert "danger_tool" in gate.session_allowed


@pytest.mark.asyncio
async def test_permission_gate_ask_user_no():
    async def mock_ask_user(tool, signature, args, diff_text):
        return "n"

    gate = PermissionGate(ask_user=mock_ask_user)
    gate.policies = {"danger_tool": Decision.ASK}
    decision = await gate.check("danger_tool", {})
    assert decision == Decision.DENY


def test_permission_gate_generate_diff_write():
    gate = PermissionGate()
    args = {"path": "new_file.txt", "content": "Hello\nWorld"}
    diff = gate._generate_diff(args)
    assert diff is not None
    assert "+Hello" in diff
    assert "+World" in diff


def test_permission_gate_generate_diff_edit(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Old content")

    gate = PermissionGate()
    args = {"path": str(test_file), "edits": [
        {"oldText": "Old", "newText": "New"}]}
    diff = gate._generate_diff(args)
    assert diff is not None
    assert "-Old content" in diff
    assert "+New content" in diff


def test_permission_gate_load_error(tmp_path):
    perm_file = tmp_path / "corrupt.json"
    perm_file.write_text("INVALID JSON")
    gate = PermissionGate(persist_file=perm_file)
    assert len(gate.session_allowed) == 0


def test_permission_gate_save_error(tmp_path):
    gate = PermissionGate(persist_file=tmp_path / "subdir" / "file.json")
    gate._save_persisted_permissions()


def test_permission_gate_signature():
    gate = PermissionGate()
    assert gate._get_signature("bash", {"command": "ls -la"}) == "bash:ls -la"
    assert gate._get_signature(
        "write_file", {"path": "test.txt"}) == "write_file:test.txt"
    assert gate._get_signature("custom_tool", {}) == "custom_tool"


def test_permission_gate_diff_no_file():
    gate = PermissionGate()
    args = {"path": "non_existent.txt", "edits": [
        {"oldText": "a", "newText": "b"}]}
    diff = gate._generate_diff(args)
    assert "does not exist" in diff


def test_permission_gate_diff_edit_not_found(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Content")
    gate = PermissionGate()
    args = {"path": str(test_file), "edits": [
        {"oldText": "NotFound", "newText": "New"}]}
    diff = gate._generate_diff(args)
    assert "not found" in diff


@pytest.mark.asyncio
async def test_permission_gate_ask_denied_final():
    async def mock_ask_user(tool, signature, args, diff_text):
        return "invalid_response"

    gate = PermissionGate(ask_user=mock_ask_user)
    gate.policies = {"tool": Decision.ASK}
    decision = await gate.check("tool", {})
    assert decision == Decision.DENY


# 🔥 NUEVO: Cubre los excepts de lectura (líneas 76-78 y 95-96)
def test_permissions_edge_cases(tmp_path):
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello")
    gate = PermissionGate()

    # Simulamos error de lectura
    with patch("pathlib.Path.read_text", side_effect=Exception("Read error")):
        diff = gate._generate_diff({"path": str(test_file), "edits": [
                                   {"oldText": "a", "newText": "b"}]})
        assert "Could not read file" in diff


def test_permissions_forced_edge_lines(tmp_path):
    """Fuerza las líneas 45-46 y 76-78 de permissions.py."""
    from app.core.harness.permissions import PermissionGate

    # 1. Forzar 45-46: error al cargar el archivo
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("INVALID JSON")
    gate = PermissionGate(persist_file=corrupt_file)
    assert len(gate.session_allowed) == 0

    # 2. Forzar 76-78: error al leer el archivo para el diff
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello")

    gate2 = PermissionGate()
    with patch("pathlib.Path.read_text", side_effect=Exception("Read error")):
        diff = gate2._generate_diff({"path": str(test_file), "edits": [
                                    {"oldText": "a", "newText": "b"}]})
        assert "Could not read file" in diff


def test_permissions_forced_lines(tmp_path):
    """Fuerza las líneas 45-46 y 76-78 de permissions.py."""
    from app.core.harness.permissions import PermissionGate

    # 1. Forzar 45-46: error al cargar el archivo
    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("INVALID JSON")

    # Mockeamos open para que json.load lance una excepción
    with patch("builtins.open", mock_open(read_data="INVALID JSON")):
        with patch("json.load", side_effect=Exception("JSON Error")):
            gate = PermissionGate(persist_file=corrupt_file)
            # El except se ejecuta y hace pass
            assert len(gate.session_allowed) == 0

    # 2. Forzar 76-78: error al leer el archivo para el diff
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello")

    gate2 = PermissionGate()
    with patch("pathlib.Path.read_text", side_effect=Exception("Read error")):
        diff = gate2._generate_diff({"path": str(test_file), "edits": [
                                    {"oldText": "a", "newText": "b"}]})
        assert "Could not read file" in diff


def test_permissions_load_loop_45_46(tmp_path):
    """Fuerza la ejecución del for en _load_persisted_permissions."""
    from app.core.harness.permissions import PermissionGate
    import json

    # Creamos un archivo válido con un patrón guardado
    perm_file = tmp_path / "valid_perms.json"
    perm_file.write_text(json.dumps({"session_allowed": ["bash:ls -la"]}))

    # Al instanciar el Gate, debe cargar el permiso y ejecutar el for
    gate = PermissionGate(persist_file=perm_file)

    assert "bash:ls -la" in gate.session_allowed


def test_permissions_generate_diff_error_76_78(tmp_path):
    """Fuerza el except de _generate_diff para write_file."""
    from app.core.harness.permissions import PermissionGate
    from unittest.mock import patch

    # Creamos un archivo real para que entre en el if path.exists()
    real_file = tmp_path / "real.txt"
    real_file.write_text("Original Content")

    gate = PermissionGate()

    # Simulamos un error al leer el archivo
    with patch("pathlib.Path.read_text", side_effect=Exception("Read error")):
        diff = gate._generate_diff({
            "path": str(real_file),
            "content": "New content"
        })

    # Como falló la lectura, old_content es "", y el diff se genera desde vacío
    assert "New content" in diff
