import sys
from mempalace.adapters import openai as adapter


def test_mcp_server_params_sets_provenance_env_and_merges_os_environ(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")  # representative existing env var
    params = adapter.mcp_server_params(
        account="alan@fwfg.com", model="gpt-4o",
        palace_path="/p/palace", registry_path="/p/registry.yaml", session="run-1",
    )
    assert params["command"] == sys.executable
    assert params["args"] == ["-m", "mempalace.mcp_server"]
    env = params["env"]
    # provenance is set, harness is fixed for this adapter
    assert env["MEMPALACE_HARNESS"] == "openai-agents-sdk"
    assert env["MEMPALACE_ACCOUNT"] == "alan@fwfg.com"
    assert env["MEMPALACE_MODEL"] == "gpt-4o"
    assert env["MEMPALACE_SESSION"] == "run-1"
    assert env["MEMPALACE_PALACE_PATH"] == "/p/palace"
    assert env["MEMPALACE_REGISTRY_PATH"] == "/p/registry.yaml"
    assert env["MEMPALACE_MACHINE"]  # defaulted to hostname
    # os.environ is merged (PATH preserved) so the subprocess can spawn python
    assert env["PATH"] == "/usr/bin"


def test_mcp_server_params_omits_unset_optionals(monkeypatch):
    for k in ("MEMPALACE_MODEL", "MEMPALACE_ACCOUNT", "MEMPALACE_SESSION"):
        monkeypatch.delenv(k, raising=False)
    params = adapter.mcp_server_params(account=None)
    env = params["env"]
    assert env["MEMPALACE_HARNESS"] == "openai-agents-sdk"
    assert "MEMPALACE_MODEL" not in env
    assert "MEMPALACE_ACCOUNT" not in env
    assert "MEMPALACE_SESSION" not in env


def test_with_memory_instructions_prepends_bootstrap():
    base = "You are a helpful CFO assistant."
    out = adapter.with_memory_instructions(base)
    assert adapter.BOOTSTRAP_INSTRUCTIONS in out
    assert base in out
    assert out.startswith(adapter.BOOTSTRAP_INSTRUCTIONS)  # memory protocol first
    # mentions the bootstrap tool by name so the model calls it
    assert "mempalace_bootstrap" in adapter.BOOTSTRAP_INSTRUCTIONS


def test_with_memory_instructions_handles_empty_base():
    assert adapter.with_memory_instructions("") == adapter.BOOTSTRAP_INSTRUCTIONS
    assert adapter.with_memory_instructions(None) == adapter.BOOTSTRAP_INSTRUCTIONS


def test_save_cadence_fires_every_interval():
    cadence = adapter.SaveCadence(interval=3)
    results = [cadence.tick() for _ in range(7)]
    # fires on the 3rd and 6th tick only
    assert results == [False, False, True, False, False, True, False]


def test_save_cadence_due_and_reset():
    cadence = adapter.SaveCadence(interval=2)
    cadence.tick()           # count 1
    assert cadence.pending() is False
    cadence.tick()           # count 2 -> due
    # tick() already returned True at the boundary; pending tracks "unsaved turns exist"
    cadence.reset()
    assert cadence.count == 0


def test_save_cadence_rejects_bad_interval():
    import pytest
    with pytest.raises(ValueError):
        adapter.SaveCadence(interval=0)
