from mempalace.config import match_tree, MempalaceConfig

TREES = [
    {"path": r"C:\dev", "account": "alan@fwfg.com"},
    {"path": r"C:\pdev", "account": "ja.powell@gmail.com"},
]


def test_exact_and_nested_match():
    assert match_tree(r"C:\dev", TREES) == ("alan@fwfg.com", r"C:\dev")
    assert match_tree(r"C:\dev\mempalace", TREES) == ("alan@fwfg.com", r"C:\dev")
    assert match_tree(r"C:\pdev\foo\bar", TREES) == ("ja.powell@gmail.com", r"C:\pdev")


def test_no_match_returns_none():
    assert match_tree(r"C:\Users\alan", TREES) == (None, None)


def test_boundary_not_substring():
    # C:\developer must NOT match C:\dev
    assert match_tree(r"C:\developer\x", TREES) == (None, None)


def test_case_insensitive():
    assert match_tree(r"c:\DEV\Mempalace", TREES) == ("alan@fwfg.com", r"C:\dev")


def test_longest_prefix_wins():
    trees = [
        {"path": r"C:\dev", "account": "work@x"},
        {"path": r"C:\dev\personal-sub", "account": "personal@x"},
    ]
    assert match_tree(r"C:\dev\personal-sub\proj", trees) == ("personal@x", r"C:\dev\personal-sub")


def test_skips_malformed_entries():
    trees = [{"path": r"C:\dev"}, {"account": "x"}, {"path": r"C:\dev", "account": "ok@x"}]
    assert match_tree(r"C:\dev\x", trees) == ("ok@x", r"C:\dev")


def test_load_trees_missing_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMPALACE_TREES_PATH", str(tmp_path / "nope.yaml"))
    assert MempalaceConfig(config_dir=tmp_path).load_trees() == []


def test_load_trees_reads_entries(tmp_path, monkeypatch):
    p = tmp_path / "trees.yaml"
    p.write_text(
        '- path: "C:\\\\dev"\n  account: "alan@fwfg.com"\n'
        '- path: "C:\\\\pdev"\n  account: "ja.powell@gmail.com"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("MEMPALACE_TREES_PATH", str(p))
    trees = MempalaceConfig(config_dir=tmp_path).load_trees()
    assert {e["account"] for e in trees} == {"alan@fwfg.com", "ja.powell@gmail.com"}


def test_load_trees_corrupt_is_empty(tmp_path, monkeypatch):
    p = tmp_path / "trees.yaml"
    p.write_text("{ this: is: not: valid", encoding="utf-8")
    monkeypatch.setenv("MEMPALACE_TREES_PATH", str(p))
    assert MempalaceConfig(config_dir=tmp_path).load_trees() == []


def _trees_file(tmp_path, monkeypatch, here):
    p = tmp_path / "trees.yaml"
    # Use single-quoted YAML scalars so Windows backslashes are not treated as
    # escape sequences (YAML double-quoted strings process \U, \a, etc.).
    p.write_text(f"- path: '{here}'\n  account: 'alan@fwfg.com'\n", encoding="utf-8")
    monkeypatch.setenv("MEMPALACE_TREES_PATH", str(p))
    return MempalaceConfig(config_dir=tmp_path)


def test_resolve_account_env_wins(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MEMPALACE_ACCOUNT", "override@x")
    cfg = _trees_file(tmp_path, monkeypatch, str(tmp_path))
    assert cfg.resolve_account() == ("override@x", "env", None)


def test_resolve_account_tree_when_no_env(tmp_path, monkeypatch):
    monkeypatch.delenv("MEMPALACE_ACCOUNT", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    cfg = _trees_file(tmp_path, monkeypatch, str(tmp_path))   # tmp_path is a prefix of work
    acct, source, matched = cfg.resolve_account()
    assert acct == "alan@fwfg.com" and source == "tree"
    assert matched == str(tmp_path)


def test_resolve_account_none_when_no_match(tmp_path, monkeypatch):
    monkeypatch.delenv("MEMPALACE_ACCOUNT", raising=False)
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    cfg = MempalaceConfig(config_dir=tmp_path)
    monkeypatch.setenv("MEMPALACE_TREES_PATH", str(tmp_path / "absent.yaml"))
    assert cfg.resolve_account() == (None, "none", None)


def test_tree_account_for_cwd_ignores_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MEMPALACE_ACCOUNT", "override@x")   # env set, but ignored here
    cfg = _trees_file(tmp_path, monkeypatch, str(tmp_path))
    acct, matched = cfg.tree_account_for_cwd()
    assert acct == "alan@fwfg.com"            # from CWD, not env


def test_account_property_uses_resolution(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MEMPALACE_ACCOUNT", raising=False)
    cfg = _trees_file(tmp_path, monkeypatch, str(tmp_path))
    assert cfg.account == "alan@fwfg.com"
