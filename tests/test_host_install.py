# tests/test_host_install.py
import json
from pathlib import Path

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


def _codex_fixture(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(
        "model = 'gpt-5.5'\n\n"
        "[mcp_servers.mempalace]\n"
        "command = 'C:\\\\Users\\\\x\\\\python.exe'\n"
        "args = [\"-m\", \"mempalace.mcp_server\"]\n\n"
        "[mcp_servers.other]\n"
        "command = 'node.exe'\n",
        encoding="utf-8")
    return p


def test_repoint_codex_toml_sets_command_and_env(tmp_path):
    import tomllib
    p = _codex_fixture(tmp_path)
    assert hi.repoint_codex_toml(p, VENV, "codex", dry_run=False) is True
    c = tomllib.load(open(p, "rb"))
    mp = c["mcp_servers"]["mempalace"]
    assert mp["command"] == VENV
    assert mp["env"]["MEMPALACE_HARNESS"] == "codex"
    assert c["mcp_servers"]["other"]["command"] == "node.exe"   # untouched


def test_repoint_codex_toml_idempotent(tmp_path):
    p = _codex_fixture(tmp_path)
    hi.repoint_codex_toml(p, VENV, "codex", dry_run=False)
    assert hi.repoint_codex_toml(p, VENV, "codex", dry_run=False) is False


def test_repoint_codex_toml_preserves_existing_account(tmp_path):
    import tomllib
    p = tmp_path / "config.toml"
    p.write_text(
        "[mcp_servers.mempalace]\n"
        "command = 'old.exe'\n"
        'args = ["-m", "mempalace.mcp_server"]\n\n'
        "[mcp_servers.mempalace.env]\n"
        'MEMPALACE_HARNESS = "claude-code"\n'
        'MEMPALACE_ACCOUNT = "alan@fwfg.com"\n',
        encoding="utf-8")
    hi.repoint_codex_toml(p, VENV, "codex", dry_run=False)
    env = tomllib.load(open(p, "rb"))["mcp_servers"]["mempalace"]["env"]
    assert env["MEMPALACE_ACCOUNT"] == "alan@fwfg.com"   # PRESERVED until --strip-account
    assert env["MEMPALACE_HARNESS"] == "codex"


def test_repoint_codex_toml_does_not_add_account_when_absent(tmp_path):
    import tomllib
    p = _codex_fixture(tmp_path)   # fixture has no account
    hi.repoint_codex_toml(p, VENV, "codex", dry_run=False)
    env = tomllib.load(open(p, "rb"))["mcp_servers"]["mempalace"].get("env", {})
    assert "MEMPALACE_ACCOUNT" not in env


AGENTS_MARKER = "## MemPalace memory (required)"


def test_ensure_agents_section_appends_when_absent(tmp_path):
    p = tmp_path / "AGENTS.md"
    p.write_text("# Tree\n\nsome rules\n", encoding="utf-8")
    assert hi.ensure_agents_section(p, dry_run=False) is True
    assert AGENTS_MARKER in p.read_text(encoding="utf-8")
    assert "mempalace_bootstrap" in p.read_text(encoding="utf-8")


def test_ensure_agents_section_idempotent(tmp_path):
    p = tmp_path / "AGENTS.md"
    p.write_text("# Tree\n", encoding="utf-8")
    hi.ensure_agents_section(p, dry_run=False)
    assert hi.ensure_agents_section(p, dry_run=False) is False


def test_ensure_agents_section_missing_file_is_noop(tmp_path):
    assert hi.ensure_agents_section(tmp_path / "absent.md", dry_run=False) is False


def test_strip_account_host_only_leaves_project(tmp_path):
    host = tmp_path / "claude.json"
    host.write_text(json.dumps({"mcpServers": {"mempalace": {"command": "p",
        "env": {"MEMPALACE_HARNESS": "claude-code", "MEMPALACE_ACCOUNT": "alan@fwfg.com"}}}}), encoding="utf-8")
    proj = tmp_path / ".mcp.json"
    proj.write_text(json.dumps({"mcpServers": {"mempalace": {"command": "p",
        "env": {"MEMPALACE_HARNESS": "claude-code", "MEMPALACE_ACCOUNT": "alan@fwfg.com"}}}}), encoding="utf-8")
    removed = hi.strip_account(host_paths=[host], project_paths=[proj], scope="host", dry_run=False)
    assert any("claude.json" in str(r) for r in removed)
    assert "MEMPALACE_ACCOUNT" not in json.loads(host.read_text())["mcpServers"]["mempalace"]["env"]
    # project-scoped pin preserved (the escape hatch)
    assert "MEMPALACE_ACCOUNT" in json.loads(proj.read_text())["mcpServers"]["mempalace"]["env"]


def test_strip_account_all_removes_project_too(tmp_path):
    proj = tmp_path / ".mcp.json"
    proj.write_text(json.dumps({"mcpServers": {"mempalace": {"command": "p",
        "env": {"MEMPALACE_ACCOUNT": "alan@fwfg.com"}}}}), encoding="utf-8")
    hi.strip_account(host_paths=[], project_paths=[proj], scope="all", dry_run=False)
    assert "MEMPALACE_ACCOUNT" not in json.loads(proj.read_text())["mcpServers"]["mempalace"]["env"]


def test_strip_account_idempotent_and_dry_run(tmp_path):
    host = tmp_path / "claude.json"
    host.write_text(json.dumps({"mcpServers": {"mempalace": {"command": "p",
        "env": {"MEMPALACE_ACCOUNT": "a@x"}}}}), encoding="utf-8")
    assert hi.strip_account([host], [], "host", dry_run=True)            # would remove
    assert "MEMPALACE_ACCOUNT" in json.loads(host.read_text())["mcpServers"]["mempalace"]["env"]  # dry-run wrote nothing
    hi.strip_account([host], [], "host", dry_run=False)
    assert hi.strip_account([host], [], "host", dry_run=False) == []     # idempotent


def test_parse_py_launcher_extracts_paths():
    text = (" -V:3.14 *        C:\\Users\\a\\pythoncore-3.14-64\\python.exe\n"
            " -V:3.12          C:\\Users\\a\\Programs\\Python\\Python312\\python.exe\n")
    paths = hi.parse_py_launcher(text)
    assert r"C:\Users\a\pythoncore-3.14-64\python.exe" in paths
    assert r"C:\Users\a\Programs\Python\Python312\python.exe" in paths


def test_uninstall_stale_uses_exact_interpreter_never_bare(tmp_path):
    calls = []
    def fake_run(cmd):
        calls.append(cmd)
        # report mempalace present only for the first interpreter
        return "Name: mempalace" if cmd[:2] == [r"C:\py1.exe", "-m"] and "show" in cmd else ""
    removed = hi.uninstall_stale(
        interpreters=[r"C:\py1.exe", r"C:\py2.exe"],
        venv_python=r"C:\dev\mempalace\.venv\Scripts\python.exe",
        yes=True, dry_run=False, _runner=fake_run)
    # every command starts with an explicit interpreter path (has drive letter colon), never bare "python"/"pip"
    assert all(":" in c[0] for c in calls)
    assert r"C:\py1.exe" in removed and r"C:\py2.exe" not in removed
    # the uninstall for py1 was issued by exact interpreter
    assert [r"C:\py1.exe", "-m", "pip", "uninstall", "-y", "mempalace"] in calls


def test_uninstall_stale_skips_venv(tmp_path):
    venv = r"C:\dev\mempalace\.venv\Scripts\python.exe"
    calls = []
    hi.uninstall_stale([venv], venv, yes=True, dry_run=False, _runner=lambda c: (calls.append(c), "")[1])
    assert calls == []     # the venv interpreter is never touched


def test_run_install_refuses_pdev_target_from_dev_run(tmp_path, monkeypatch):
    dev = tmp_path / "dev"
    pdev = tmp_path / "pdev"
    dev.mkdir()
    pdev.mkdir()
    (pdev / "AGENTS.md").write_text("# personal\n", encoding="utf-8")
    # a dev run must not touch pdev's AGENTS.md
    assert hi.within_tree(pdev / "AGENTS.md", dev, []) is False
    # ensure run_install only ever calls ensure_agents_section on within-tree paths:
    targeted = hi.agents_targets_for_tree(tree_root=dev, known_trees=[dev, pdev])
    assert all(hi.within_tree(t, dev, []) for t in targeted)
    assert (pdev / "AGENTS.md") not in [Path(t) for t in targeted]


def test_main_default_run_does_not_strip(monkeypatch):
    # argparse: default run has strip_account False
    args = hi.parse_args(["--dry-run"])
    assert args.strip_account is False and args.strip_all_account_overrides is False
    args2 = hi.parse_args(["--strip-account"])
    assert args2.strip_account is True
