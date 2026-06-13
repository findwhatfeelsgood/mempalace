import importlib

from mempalace.config import MempalaceConfig


def test_provenance_defaults(monkeypatch, tmp_path):
    for k in ("MEMPALACE_HARNESS", "MEMPALACE_MODEL", "MEMPALACE_ACCOUNT",
              "MEMPALACE_MACHINE", "MEMPALACE_SESSION"):
        monkeypatch.delenv(k, raising=False)
    cfg = MempalaceConfig(config_dir=tmp_path)
    prov = cfg.provenance()
    assert prov["harness"] == "unknown"
    assert prov["machine"]  # hostname, non-empty
    assert "model" not in prov and "account" not in prov and "session" not in prov


def test_provenance_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMPALACE_HARNESS", "openai-agents-sdk")
    monkeypatch.setenv("MEMPALACE_MODEL", "gpt-4o")
    monkeypatch.setenv("MEMPALACE_ACCOUNT", "alan@fwfg.com")
    monkeypatch.setenv("MEMPALACE_MACHINE", "laptop-7")
    monkeypatch.setenv("MEMPALACE_SESSION", "run-123")
    cfg = MempalaceConfig(config_dir=tmp_path)
    assert cfg.provenance() == {
        "harness": "openai-agents-sdk", "model": "gpt-4o",
        "account": "alan@fwfg.com", "machine": "laptop-7", "session": "run-123",
    }


def test_add_drawer_stamps_provenance(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMPALACE_PALACE_PATH", str(tmp_path / "palace"))
    monkeypatch.setenv("MEMPALACE_HARNESS", "openai-agents-sdk")
    monkeypatch.setenv("MEMPALACE_ACCOUNT", "alan@fwfg.com")
    monkeypatch.delenv("MEMPALACE_MODEL", raising=False)
    import mempalace.config as config
    import mempalace.mcp_server as srv
    importlib.reload(config)
    importlib.reload(srv)

    res = srv.tool_add_drawer(wing="provtest", room="r", content="hello world", model="gpt-4o")
    assert res["success"]
    got = srv._get_collection().get(ids=[res["drawer_id"]], include=["metadatas"])
    meta = got["metadatas"][0]
    assert meta["harness"] == "openai-agents-sdk"
    assert meta["account"] == "alan@fwfg.com"
    assert meta["model"] == "gpt-4o"          # per-call override wins over (unset) env
    assert meta["machine"]


def test_diary_write_stamps_provenance(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMPALACE_PALACE_PATH", str(tmp_path / "palace2"))
    monkeypatch.setenv("MEMPALACE_HARNESS", "claude-code")
    monkeypatch.setenv("MEMPALACE_MODEL", "claude-opus-4-8")
    monkeypatch.setenv("MEMPALACE_ACCOUNT", "alan@fwfg.com")
    import mempalace.config as config
    import mempalace.mcp_server as srv
    importlib.reload(config)
    importlib.reload(srv)

    res = srv.tool_diary_write(agent_name="claude-code", entry="SESSION:x|done|★")
    assert res["success"]
    got = srv._get_collection().get(ids=[res["entry_id"]], include=["metadatas"])
    meta = got["metadatas"][0]
    assert meta["type"] == "diary_entry"
    assert meta["harness"] == "claude-code"
    assert meta["model"] == "claude-opus-4-8"
    assert meta["account"] == "alan@fwfg.com"


def test_add_drawer_canonicalizes_wing_via_registry(monkeypatch, tmp_path):
    palace = tmp_path / "palace3"
    monkeypatch.setenv("MEMPALACE_PALACE_PATH", str(palace))
    monkeypatch.setenv("MEMPALACE_HARNESS", "openai-agents-sdk")
    monkeypatch.setenv("MEMPALACE_ACCOUNT", "alan@fwfg.com")
    from mempalace import wing_registry as wr
    reg_path = tmp_path / "wing_registry.yaml"
    wr.save_registry(wr.Registry(entries=[wr.WingEntry(
        slug="fwfg-deploy", kind="project", account="alan@fwfg.com", aliases=["fwfg_deploy"])]), reg_path)
    monkeypatch.setenv("MEMPALACE_REGISTRY_PATH", str(reg_path))

    import mempalace.config as config
    import mempalace.mcp_server as srv
    importlib.reload(config)
    importlib.reload(srv)

    res = srv.tool_add_drawer(wing="fwfg_deploy", room="decisions", content="x y z")
    assert res["wing"] == "fwfg-deploy"          # canonicalized
    meta = srv._get_collection().get(ids=[res["drawer_id"]], include=["metadatas"])["metadatas"][0]
    assert meta["wing"] == "fwfg-deploy"
    assert meta["wing_status"] == "canonical"
