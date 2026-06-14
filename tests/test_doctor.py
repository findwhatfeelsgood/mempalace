from mempalace import cli


def test_doctor_report_keys_and_provenance(monkeypatch):
    monkeypatch.setenv("MEMPALACE_HARNESS", "codex")
    monkeypatch.setenv("MEMPALACE_ACCOUNT", "alan@fwfg.com")
    monkeypatch.delenv("MEMPALACE_MODEL", raising=False)
    r = cli.doctor_report()
    for k in ("executable", "package_path", "version", "base_version", "palace_path",
              "registry_path", "provenance", "bootstrap_tool_available"):
        assert k in r
    assert "fwfg" in r["version"] and r["version"].startswith("3.3.0")  # fork marker
    assert r["base_version"] == "3.3.0"                # upstream baseline preserved
    assert set(r["provenance"]) == {"harness", "account", "model", "machine", "session"}
    assert r["provenance"]["harness"] == "codex"
    assert r["provenance"]["account"] == "alan@fwfg.com"
    assert r["provenance"]["model"] is None
    assert r["provenance"]["machine"]                 # hostname default, non-empty
    assert r["bootstrap_tool_available"] is True       # this is the fork


def test_doctor_version_is_fwfg_marked():
    from mempalace.version import __version__, FWFG_VERSION
    assert __version__ == "3.3.0"                       # upstream baseline untouched
    assert FWFG_VERSION.startswith("3.3.0")
    assert "fwfg" in FWFG_VERSION


def test_doctor_shows_tree_resolution(tmp_path, monkeypatch):
    p = tmp_path / "trees.yaml"
    p.write_text(f"- path: '{tmp_path}'\n  account: 'alan@fwfg.com'\n", encoding="utf-8")
    monkeypatch.setenv("MEMPALACE_TREES_PATH", str(p))
    monkeypatch.delenv("MEMPALACE_ACCOUNT", raising=False)
    monkeypatch.chdir(tmp_path)
    from mempalace import cli
    r = cli.doctor_report()
    assert r["account_source"] == "tree"
    assert r["resolved_account"] == "alan@fwfg.com"
    assert r["tree_account"] == "alan@fwfg.com"
    assert r["matched_tree"] == str(tmp_path)


def test_doctor_env_override_still_shows_tree(tmp_path, monkeypatch):
    p = tmp_path / "trees.yaml"
    p.write_text(f"- path: '{tmp_path}'\n  account: 'alan@fwfg.com'\n", encoding="utf-8")
    monkeypatch.setenv("MEMPALACE_TREES_PATH", str(p))
    monkeypatch.setenv("MEMPALACE_ACCOUNT", "pinned@x")
    monkeypatch.chdir(tmp_path)
    from mempalace import cli
    r = cli.doctor_report()
    assert r["account_source"] == "env" and r["resolved_account"] == "pinned@x"
    # the CWD-derived value is still visible -> safe to verify before stripping
    assert r["tree_account"] == "alan@fwfg.com"
    assert r["matched_tree"] == str(tmp_path)
