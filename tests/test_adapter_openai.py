import sys

import pytest
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


def test_save_cadence_pending_tracks_unsaved_turns():
    c = adapter.SaveCadence(interval=15)
    assert c.pending() is False            # nothing recorded yet
    for _ in range(7):
        c.tick()
    assert c.pending() is True             # 7 unsaved turns -> session-end must flush
    c.reset()
    assert c.pending() is False and c.count == 0


def test_save_cadence_pending_false_at_interval_boundary():
    c = adapter.SaveCadence(interval=2)
    assert c.tick() is False               # count 1
    assert c.pending() is True             # one unsaved turn pending
    assert c.tick() is True                # count 2 -> due (boundary)
    assert c.pending() is False            # boundary reached; the due-flush covers it


def test_save_cadence_rejects_bad_interval():
    with pytest.raises(ValueError):
        adapter.SaveCadence(interval=0)


class _FakeRaw:
    def __init__(self, name):
        self.name = name


class _FakeItem:
    def __init__(self, type_, name=None):
        self.type = type_
        self.raw_item = _FakeRaw(name) if name else object()


class _FakeResult:
    def __init__(self, items):
        self.new_items = items


def test_saved_in_result_detects_diary_write():
    res = _FakeResult([
        _FakeItem("message_output_item"),
        _FakeItem("tool_call_item", "mempalace_diary_write"),
    ])
    assert adapter.saved_in_result(res) is True


def test_saved_in_result_detects_add_drawer():
    res = _FakeResult([_FakeItem("tool_call_item", "mempalace_add_drawer")])
    assert adapter.saved_in_result(res) is True


def test_saved_in_result_false_when_no_write_tool():
    res = _FakeResult([
        _FakeItem("tool_call_item", "mempalace_search"),
        _FakeItem("message_output_item"),
    ])
    assert adapter.saved_in_result(res) is False


def test_saved_in_result_handles_missing_attrs():
    assert adapter.saved_in_result(object()) is False
    assert adapter.saved_in_result(_FakeResult([])) is False


def test_flush_due_runs_save_prompt_and_verifies():
    calls = []

    def fake_run(prompt):
        calls.append(prompt)
        return _FakeResult([_FakeItem("tool_call_item", "mempalace_diary_write")])

    adapter.flush_due(fake_run)
    assert len(calls) == 1
    assert "save" in calls[0].lower() or "diary" in calls[0].lower()


def test_flush_due_retries_once_then_raises():
    calls = []

    def never_saves(prompt):
        calls.append(prompt)
        return _FakeResult([_FakeItem("message_output_item")])

    with pytest.raises(adapter.FlushError):
        adapter.flush_due(never_saves)
    assert len(calls) == 2  # initial + one retry


def test_flush_due_second_attempt_succeeds():
    state = {"n": 0}

    def saves_on_retry(prompt):
        state["n"] += 1
        if state["n"] == 1:
            return _FakeResult([])
        return _FakeResult([_FakeItem("tool_call_item", "mempalace_add_drawer")])

    adapter.flush_due(saves_on_retry)  # no raise
    assert state["n"] == 2
