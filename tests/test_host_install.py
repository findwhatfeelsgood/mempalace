# tests/test_host_install.py
from mempalace import host_install as hi


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
