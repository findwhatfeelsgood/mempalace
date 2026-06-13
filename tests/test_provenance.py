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
