# tests/test_host_install.py
import json
import yaml
from mempalace import host_install as hi

VENV = r"C:\dev\mempalace\.venv\Scripts\python.exe"


def test_backup_file_copies_with_timestamp(tmp_path):
    f = tmp_path / "c.json"
    f.write_text("original", encoding="utf-8")
    bak = hi.backup_file(f)
    assert bak is not None and bak.exists()
    assert bak.read_text(encoding="utf-8") == "original"
    assert ".bak." in bak.name


def test_backup_file_absent_returns_none(tmp_path):
    assert hi.backup_file(tmp_path / "nope.json") is None


def test_within_tree_allows_under_root_and_globals(tmp_path):
    root = tmp_path / "dev"
    glob = tmp_path / "home" / ".mempalace"
    (root).mkdir()
    (glob).mkdir(parents=True)
    assert hi.within_tree(root / "AGENTS.md", root, [glob]) is True
    assert hi.within_tree(glob / "trees.yaml", root, [glob]) is True


def test_within_tree_refuses_sibling_tree(tmp_path):
    dev = tmp_path / "dev"
    pdev = tmp_path / "pdev"
    dev.mkdir()
    pdev.mkdir()
    # a C:\dev run must NOT target a C:\pdev path
    assert hi.within_tree(pdev / "AGENTS.md", dev, []) is False


def test_write_trees_yaml_safe_dump_roundtrips_windows_paths(tmp_path):
    p = tmp_path / "trees.yaml"
    entries = [
        {"path": r"C:\dev", "account": "alan@fwfg.com"},
        {"path": r"C:\pdev", "account": "ja.powell@gmail.com"},
    ]
    assert hi.write_trees_yaml(p, entries, dry_run=False) is True
    loaded = yaml.safe_load(p.read_text(encoding="utf-8"))   # must parse cleanly
    assert {e["path"] for e in loaded} == {r"C:\dev", r"C:\pdev"}
    assert {e["account"] for e in loaded} == {"alan@fwfg.com", "ja.powell@gmail.com"}


def test_write_trees_yaml_idempotent(tmp_path):
    p = tmp_path / "trees.yaml"
    entries = [{"path": r"C:\dev", "account": "alan@fwfg.com"}]
    hi.write_trees_yaml(p, entries, dry_run=False)
    assert hi.write_trees_yaml(p, entries, dry_run=False) is False   # no change


def test_write_trees_yaml_merges_and_overrides(tmp_path):
    p = tmp_path / "trees.yaml"
    hi.write_trees_yaml(p, [{"path": r"C:\dev", "account": "old@x"}], dry_run=False)
    hi.write_trees_yaml(p, [{"path": r"C:\dev", "account": "alan@fwfg.com"},
                            {"path": r"C:\pdev", "account": "ja.powell@gmail.com"}], dry_run=False)
    loaded = {e["path"]: e["account"] for e in yaml.safe_load(p.read_text(encoding="utf-8"))}
    assert loaded == {r"C:\dev": "alan@fwfg.com", r"C:\pdev": "ja.powell@gmail.com"}


def test_write_trees_yaml_dry_run_writes_nothing(tmp_path):
    p = tmp_path / "trees.yaml"
    assert hi.write_trees_yaml(p, [{"path": r"C:\dev", "account": "a@x"}], dry_run=True) is True
    assert not p.exists()


def _mcp_fixture(tmp_path):
    p = tmp_path / ".mcp.json"
    p.write_text(json.dumps({"mcpServers": {"mempalace": {
        "command": r"C:\Users\x\AppData\Local\Programs\Python\Python312\python.exe",
        "args": ["-m", "mempalace.mcp_server"]}}}), encoding="utf-8")
    return p


def test_repoint_json_mcp_sets_command_harness_no_account(tmp_path):
    p = _mcp_fixture(tmp_path)
    assert hi.repoint_json_mcp(p, "mempalace", VENV, "claude-code", dry_run=False) is True
    s = json.loads(p.read_text(encoding="utf-8"))["mcpServers"]["mempalace"]
    assert s["command"] == VENV
    assert s["args"] == ["-m", "mempalace.mcp_server"]
    assert s["env"]["MEMPALACE_HARNESS"] == "claude-code"
    assert "MEMPALACE_ACCOUNT" not in s["env"]            # does NOT add when absent


def test_repoint_json_mcp_preserves_existing_account(tmp_path):
    p = tmp_path / ".mcp.json"
    p.write_text(json.dumps({"mcpServers": {"mempalace": {
        "command": "old.exe", "args": ["-m", "mempalace.mcp_server"],
        "env": {"MEMPALACE_HARNESS": "claude-code",
                "MEMPALACE_ACCOUNT": "alan@fwfg.com"}}}}), encoding="utf-8")
    hi.repoint_json_mcp(p, "mempalace", VENV, "claude-code", dry_run=False)
    env = json.loads(p.read_text(encoding="utf-8"))["mcpServers"]["mempalace"]["env"]
    assert env["MEMPALACE_ACCOUNT"] == "alan@fwfg.com"    # pin PRESERVED until --strip-account
    assert env["MEMPALACE_HARNESS"] == "claude-code"


def test_repoint_json_mcp_idempotent_and_backs_up(tmp_path):
    p = _mcp_fixture(tmp_path)
    hi.repoint_json_mcp(p, "mempalace", VENV, "claude-code", dry_run=False)
    assert any(".bak." in f.name for f in tmp_path.iterdir())   # backup made
    assert hi.repoint_json_mcp(p, "mempalace", VENV, "claude-code", dry_run=False) is False


def test_repoint_json_mcp_missing_server_or_file_is_noop(tmp_path):
    assert hi.repoint_json_mcp(tmp_path / "absent.json", "mempalace", VENV, "claude-code", False) is False
    p = tmp_path / "x.json"
    p.write_text('{"mcpServers": {}}', encoding="utf-8")
    assert hi.repoint_json_mcp(p, "mempalace", VENV, "claude-code", False) is False


def _hooks_fixture(tmp_path, harness_in_cmd):
    p = tmp_path / "hooks.json"
    cmd = f"python -m mempalace hook run --hook stop --harness {harness_in_cmd}"
    p.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [
        {"type": "command", "command": cmd}]}]}}), encoding="utf-8")
    return p


def test_repoint_hooks_explicit_python_and_harness(tmp_path):
    p = _hooks_fixture(tmp_path, "claude-code")          # codex file had wrong harness
    assert hi.repoint_hook_commands(p, VENV, "codex", dry_run=False) is True
    cmd = json.loads(p.read_text(encoding="utf-8"))["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert cmd == f'"{VENV}" -m mempalace hook run --hook stop --harness codex'


def test_repoint_hooks_quotes_python_with_spaces(tmp_path):
    p = _hooks_fixture(tmp_path, "claude-code")
    spaced = r"C:\Program Files\mp\.venv\Scripts\python.exe"
    assert hi.repoint_hook_commands(p, spaced, "claude-code", dry_run=False) is True
    cmd = json.loads(p.read_text(encoding="utf-8"))["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert cmd == f'"{spaced}" -m mempalace hook run --hook stop --harness claude-code'
    # idempotent even with the quoted, space-containing path
    assert hi.repoint_hook_commands(p, spaced, "claude-code", dry_run=False) is False


def test_repoint_hooks_idempotent(tmp_path):
    p = _hooks_fixture(tmp_path, "claude-code")
    hi.repoint_hook_commands(p, VENV, "claude-code", dry_run=False)
    assert hi.repoint_hook_commands(p, VENV, "claude-code", dry_run=False) is False


def test_repoint_hooks_ignores_non_mempalace_commands(tmp_path):
    p = tmp_path / "h.json"
    p.write_text(json.dumps({"hooks": {"SessionStart": [{"hooks": [
        {"type": "command", "command": "powershell.exe -File x.ps1"}]}]}}), encoding="utf-8")
    assert hi.repoint_hook_commands(p, VENV, "claude-code", dry_run=False) is False
